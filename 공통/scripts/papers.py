"""의학 논문 조회(Europe PMC, OpenAlex).

산재처럼 의학적 인과관계가 쟁점인 사건에서 PubMed 연결(커넥터)과 함께 쓴다. 찾고 읽고 인용하는 법은
.claude/skills/의학논문-검색/SKILL.md 에 있다.

- Europe PMC: PubMed 에 더해 사전공개 논문과 일부 다른 학술지까지 찾고, 무료 공개 논문은 본문 글자까지
  검색하고 받는다. 인증키가 없다.
- OpenAlex: 의학 밖(안전공학·인간공학·사회과학)과 DOI 가 있는 국내 학술지까지 찾는다.
  무료 인증키가 있어야 한다(2026. 2. 13.부터).

인증키는 PC마다 %LOCALAPPDATA%\\노동사건자동화\\openalex.json 에 두고 OneDrive에 올리지 않는다.
인증키를 채팅에 받거나 대신 입력하지 않는다.

    python 공통/scripts/papers.py epmc "long working hours AND stroke" --limit 20
    python 공통/scripts/papers.py epmc "\\"rotator cuff\\" AND (repetitive OR overhead)" --무료만
    python 공통/scripts/papers.py epmc-text PMC8504166 --out "{사건}/참고자료/의학논문/PMC8504166.txt"
    python 공통/scripts/papers.py openalex-key 인증키
    python 공통/scripts/papers.py openalex "musculoskeletal disorders shipbuilding Korea" --since 2010
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

EPMC_BASE = 'https://www.ebi.ac.uk/europepmc/webservices/rest'
OPENALEX_WORKS = 'https://api.openalex.org/works'
DELAY = 0.3             # 호출 사이 간격(초)
OPENER = urllib.request.urlopen
CALLS = {'n': 0}


class PapersError(Exception):
    pass


def home():
    base = os.environ.get('PAPERS_HOME') or Path(os.environ.get('LOCALAPPDATA') or Path.home() / '.local' / 'share') / '노동사건자동화'
    return Path(base)


def openalex_key(given=None):
    if given:
        return given
    if os.environ.get('OPENALEX_KEY'):
        return os.environ['OPENALEX_KEY']
    config = home() / 'openalex.json'
    if config.is_file():
        value = json.loads(config.read_text(encoding='utf-8')).get('KEY')
        if value:
            return value
    raise PapersError('OpenAlex 인증키가 없습니다. openalex.org 에서 무료로 받은 뒤 '
                      'python 공통/scripts/papers.py openalex-key 인증키 로 저장하십시오.')


def set_openalex_key(value):
    path = home() / 'openalex.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'KEY': value.strip()}, ensure_ascii=False), encoding='utf-8')
    return {'저장': str(path)}


def get(url, params, *, what):
    request = urllib.request.Request(url + ('?' + urllib.parse.urlencode(params) if params else ''),
                                     headers={'Accept': 'application/json, application/xml',
                                              'User-Agent': 'Mozilla/5.0 (labor-workflow)'})
    for attempt in range(3):
        try:
            with OPENER(request, timeout=30) as response:
                raw = response.read()
            break
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode('utf-8', 'replace')[:200] if hasattr(exc, 'read') else ''
            if exc.code == 404:
                raise PapersError(f'{what}: 찾는 자료가 없습니다(HTTP 404). {detail}') from exc
            if exc.code in (401, 403, 409):
                raise PapersError(f'{what}: HTTP {exc.code} — 인증키나 하루 사용 한도를 확인하십시오. {detail}') from exc
            if attempt == 2:
                raise PapersError(f'{what}: HTTP {exc.code}: {detail}') from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            if attempt == 2:
                raise PapersError(f'{what}: 연결 실패: {exc}') from exc
        time.sleep(1.5 * (attempt + 1))
    CALLS['n'] += 1
    time.sleep(DELAY)
    return raw


def get_json(url, params, *, what):
    text = get(url, params, what=what).decode('utf-8', 'replace')
    try:
        return json.loads(text)
    except ValueError as exc:
        raise PapersError(f'{what}: JSON이 아닌 응답: ' + re.sub(r'\s+', ' ', text)[:200]) from exc


# ---------------------------------------------------------------- Europe PMC

def epmc_row(item):
    journal = (item.get('journalInfo') or {})
    issue = '·'.join(x for x in (journal.get('volume'), journal.get('issue')) if x)
    return {
        '출처': 'Europe PMC',
        'id': item.get('id'),
        'pmid': item.get('pmid'),
        'pmcid': item.get('pmcid'),
        'doi': item.get('doi'),
        '제목': item.get('title'),
        '저자': item.get('authorString'),
        '학술지': (journal.get('journal') or {}).get('title') or item.get('journalTitle'),
        '연도': item.get('pubYear'),
        '권호면': ', '.join(x for x in (issue, item.get('pageInfo')) if x),
        '논문유형': ((item.get('pubTypeList') or {}).get('pubType')) or [],
        '무료공개': item.get('isOpenAccess') == 'Y',
        '초록': re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', item.get('abstractText') or '')).strip(),
        '주소': f"https://europepmc.org/article/{item.get('source')}/{item.get('id')}" if item.get('id') else None,
    }


def epmc_search(query, *, limit=20, open_access=False, since=None):
    """Europe PMC 에서 논문을 찾는다. 검색어는 Europe PMC 문법(AND·OR·"구절"·필드)을 그대로 쓴다."""
    if not query.strip():
        raise PapersError('검색어가 비었습니다.')
    q = query
    if open_access:
        q = f'({q}) AND OPEN_ACCESS:y'
    if since:
        q = f'({q}) AND PUB_YEAR:[{int(since)} TO 3000]'
    rows, cursor, total = [], '*', 0
    while len(rows) < limit:
        data = get_json(EPMC_BASE + '/search', {'query': q, 'format': 'json', 'resultType': 'core',
                                                'pageSize': min(limit - len(rows), 100), 'cursorMark': cursor},
                        what='Europe PMC 검색')
        total = int(data.get('hitCount') or 0)
        batch = ((data.get('resultList') or {}).get('result')) or []
        rows.extend(epmc_row(item) for item in batch)
        nxt = data.get('nextCursorMark')
        if not batch or not nxt or nxt == cursor:
            break
        cursor = nxt
    return {'검색어': q, '전체': total, '받은건수': len(rows[:limit]), '호출': CALLS['n'], 'rows': rows[:limit]}


def _text(node):
    return re.sub(r'\s+', ' ', ''.join(node.itertext())).strip()


def jats_text(xml_bytes):
    """Europe PMC 본문(JATS XML)을 읽을 수 있는 글로 바꾼다. 절 제목·문단·표·그림 설명을 남기고 참고문헌은 뺀다."""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise PapersError(f'본문 XML 을 읽지 못했습니다: {exc}') from exc
    lines = []
    title = root.find('.//article-meta/title-group/article-title')
    if title is not None:
        lines.append('# ' + _text(title))
    for abstract in root.findall('.//article-meta/abstract'):
        lines.append('## 초록')
        for p in abstract.iter('p'):
            lines.append(_text(p))

    def walk(node, depth):
        for child in node:
            tag = child.tag
            if tag == 'sec':
                head = child.find('title')
                if head is not None:
                    lines.append('#' * min(depth, 6) + ' ' + _text(head))
                walk(child, depth + 1)
            elif tag == 'p':
                lines.append(_text(child))
            elif tag in ('table-wrap', 'fig'):
                label = child.find('label')
                caption = child.find('caption')
                lines.append(' '.join(x for x in ('[' + _text(label) + ']' if label is not None else '',
                                                  _text(caption) if caption is not None else '') if x))
                for tr in child.iter('tr'):
                    lines.append(' | '.join(_text(cell) for cell in tr if cell.tag in ('td', 'th')))
            elif tag not in ('title', 'ref-list'):
                walk(child, depth)

    body = root.find('body')
    if body is not None:
        walk(body, 2)
    text = '\n\n'.join(x for x in lines if x)
    if not text:
        raise PapersError('본문에서 글자를 찾지 못했습니다.')
    return text


def epmc_fulltext(pmcid):
    pmcid = pmcid.strip().upper()
    if not pmcid.startswith('PMC'):
        pmcid = 'PMC' + pmcid
    raw = get(f'{EPMC_BASE}/{pmcid}/fullTextXML', {}, what=f'{pmcid} 본문')
    return {'pmcid': pmcid, 'text': jats_text(raw)}


# ---------------------------------------------------------------- OpenAlex

def inverted_abstract(index):
    """OpenAlex 는 초록을 {낱말: [자리, ...]} 꼴로 준다. 자리 순서대로 다시 잇는다."""
    if not index:
        return ''
    words = {}
    for word, places in index.items():
        for place in places:
            words[place] = word
    return ' '.join(words[i] for i in sorted(words))


def openalex_row(item):
    authors = [((a.get('author') or {}).get('display_name')) for a in item.get('authorships') or []]
    authors = [a for a in authors if a]
    source = ((item.get('primary_location') or {}).get('source') or {})
    oa = item.get('open_access') or {}
    return {
        '출처': 'OpenAlex',
        'id': item.get('id'),
        'doi': (item.get('doi') or '').replace('https://doi.org/', '') or None,
        '제목': item.get('display_name') or item.get('title'),
        '저자': ', '.join(authors[:5]) + (' 외' if len(authors) > 5 else ''),
        '학술지': source.get('display_name'),
        '연도': item.get('publication_year'),
        '언어': item.get('language'),
        '유형': item.get('type'),
        '피인용': item.get('cited_by_count'),
        '무료공개': bool(oa.get('is_oa')),
        '무료주소': oa.get('oa_url'),
        '초록': inverted_abstract(item.get('abstract_inverted_index')),
    }


def openalex_search(query, *, limit=20, language=None, since=None, key=None):
    """OpenAlex 에서 논문을 찾는다. 검색어는 제목·초록·본문 낱말 검색이다."""
    if not query.strip():
        raise PapersError('검색어가 비었습니다.')
    filters = []
    if language:
        filters.append(f'language:{language}')
    if since:
        filters.append(f'publication_year:>{int(since) - 1}')
    params = {'search': query, 'per-page': min(limit, 50), 'api_key': openalex_key(key)}
    if filters:
        params['filter'] = ','.join(filters)
    rows, page, total = [], 1, 0
    while len(rows) < limit:
        data = get_json(OPENALEX_WORKS, {**params, 'page': page}, what='OpenAlex 검색')
        total = int((data.get('meta') or {}).get('count') or 0)
        batch = data.get('results') or []
        rows.extend(openalex_row(item) for item in batch)
        if len(batch) < params['per-page']:
            break
        page += 1
    return {'검색어': query, '조건': params.get('filter'), '전체': total, '받은건수': len(rows[:limit]),
            '호출': CALLS['n'], 'rows': rows[:limit]}


def openalex_check(key=None):
    try:
        data = openalex_search('occupational health', limit=1, key=key)
    except PapersError as exc:
        return {'ok': False, '사유': str(exc)}
    return {'ok': True, '전체': data['전체'], '저장': str(home() / 'openalex.json')}


# ---------------------------------------------------------------- 명령

def write_out(path, content):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding='utf-8')
    return str(target)


def main(argv=None):
    if sys.stdout.encoding and sys.stdout.encoding.lower() not in ('utf-8', 'utf8'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    subs = parser.add_subparsers(dest='command', required=True)
    s = subs.add_parser('epmc', help='Europe PMC 에서 논문을 찾는다(인증키 없음)')
    s.add_argument('query')
    s.add_argument('--limit', type=int, default=20)
    s.add_argument('--무료만', dest='open_access', action='store_true', help='본문이 무료 공개된 논문만')
    s.add_argument('--since', type=int, help='이 해부터 나온 논문만')
    s.add_argument('--out', help='결과를 JSON 파일로 쓴다')
    s = subs.add_parser('epmc-text', help='무료 공개 논문의 본문을 글로 받는다')
    s.add_argument('pmcid')
    s.add_argument('--out', help='본문을 글 파일로 쓴다')
    s = subs.add_parser('openalex', help='OpenAlex 에서 논문을 찾는다(무료 인증키)')
    s.add_argument('query')
    s.add_argument('--limit', type=int, default=20)
    s.add_argument('--언어', dest='language', help='논문 언어 코드(예: ko, en)')
    s.add_argument('--since', type=int, help='이 해부터 나온 논문만')
    s.add_argument('--key', help='인증키를 직접 넘긴다(저장하지 않는다)')
    s.add_argument('--out', help='결과를 JSON 파일로 쓴다')
    s = subs.add_parser('openalex-key', help='이 PC에 OpenAlex 인증키를 저장한다'); s.add_argument('value')
    s = subs.add_parser('openalex-check', help='OpenAlex 인증키가 쓰이는지 확인한다(호출 1회)')
    s.add_argument('--key')
    args = parser.parse_args(argv)
    try:
        if args.command == 'openalex-key':
            result = set_openalex_key(args.value)
        elif args.command == 'openalex-check':
            result = openalex_check(args.key)
        elif args.command == 'epmc-text':
            result = epmc_fulltext(args.pmcid)
            if args.out:
                result = {'pmcid': result['pmcid'], '파일': write_out(args.out, result['text']),
                          '글자수': len(result['text'])}
        else:
            if args.command == 'epmc':
                result = epmc_search(args.query, limit=args.limit, open_access=args.open_access, since=args.since)
            else:
                result = openalex_search(args.query, limit=args.limit, language=args.language,
                                         since=args.since, key=args.key)
            if args.out:
                saved = write_out(args.out, json.dumps(result, ensure_ascii=False, indent=2))
                result = {k: v for k, v in result.items() if k != 'rows'} | {'파일': saved, '앞 10건': result['rows'][:10]}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if args.command != 'openalex-check' or result['ok'] else 1
    except PapersError as exc:
        print('오류: ' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
