"""법제처 국가법령정보 공동활용 OPEN API 조회 도구.

판례(대법원 중심)·헌재결정례·법령해석례·행정심판례와 노동위원회·산업재해보상보험재심사위원회·
고용보험심사위원회 결정문, 고용노동부 법령해석, 행정규칙(고시·예규·지침), 법령 본문과 조문(시점별)을
공식 API로 받는다. 브라우저와 LBOX 계정을 쓰지 않는다.

인증값(OC)은 법제처 OPEN API 사용 신청 때 받은 값이고, 호출하는 PC의 공인 IP가 신청 정보에 등록되어
있어야 한다. 인증값과 받은 본문은 PC마다 %LOCALAPPDATA%\\노동사건자동화\\ 아래에 두고 OneDrive에 올리지 않는다.
"""
from __future__ import annotations

import argparse
import html
import http.client
import importlib.util
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

# 사건번호 정규식의 단일 원본은 공통/scripts/system.py 이다.
_spec = importlib.util.spec_from_file_location('workflow_system', Path(__file__).with_name('system.py'))
_system = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_system)

BASE = 'https://www.law.go.kr/DRF/'
PAGE = 100          # API가 한 번에 돌려주는 최대 건수
DELAY = 0.3         # 호출 사이 간격(초). 공식 API이지만 한꺼번에 몰아 보내지 않는다
OPENER = urllib.request.urlopen
CALLS = {'n': 0}

# 일련번호·일자는 목록과 본문에서 필드 이름이 다른 경우가 있어 후보를 차례로 본다.
TYPES = {
    '판례': dict(target='prec', id=('판례일련번호', '판례정보일련번호'), title='사건명', no='사건번호',
               date=('선고일자',), org='법원명', period='prncYd',
               body=('판시사항', '판결요지', '참조조문', '참조판례', '판례내용')),
    '헌재': dict(target='detc', id=('헌재결정례일련번호',), title='사건명', no='사건번호',
               date=('종국일자',), org=None, period='edYd',
               body=('판시사항', '결정요지', '심판대상조문', '참조조문', '참조판례', '전문')),
    '법령해석': dict(target='expc', id=('법령해석례일련번호',), title='안건명', no='안건번호',
                 date=('회신일자', '해석일자'), org='회신기관명', period='explYd',
                 body=('질의요지', '회답', '이유')),
    '행정심판': dict(target='decc', id=('행정심판재결례일련번호', '행정심판례일련번호'), title='사건명', no='사건번호',
                 date=('의결일자',), org='재결청', period='rslYd',
                 body=('재결요지', '주문', '청구취지', '이유')),
    '노동위': dict(target='nlrc', id=('결정문일련번호',), title='제목', no='사건번호',
                date=('등록일',), org='담당부서', period=None,
                body=('판정사항', '판정요지', '판정결과', '내용')),
    '산재재심사': dict(target='iaciac', id=('결정문일련번호',), title='사건', no='사건번호',
                  date=('의결일자',), org=None, period=None,
                  body=('쟁점', '주문', '청구취지', '이유')),
    '고용보험심사': dict(target='eiac', id=('결정문일련번호',), title='사건명', no='사건번호',
                   date=('의결일자',), org=None, period=None,
                   body=('개요', '주문', '청구취지', '이유')),
    '노동부해석': dict(target='moelCgmExpc', id=('법령해석일련번호',), title='안건명', no='안건번호',
                  date=('해석일자',), org='해석기관명', period='explYd',
                  body=('질의요지', '회답', '이유', '관련법령')),
    '인권위': dict(target='nhrck', id=('결정문일련번호',), title='사건명', no='사건번호',
                date=('의결일자',), org='위원회명', period=None,
                body=('결정요지', '판단요지', '주문', '이유')),
    # 별표·서식은 본문(lawService.do)이 JSON이 아니라 뷰어 HTML로 온다. 본문 대신 한글·PDF 파일 링크를 쓴다
    '별표': dict(target='licbyl', id=('별표일련번호',), title='별표명', no='별표번호',
               date=('공포일자',), org='소관부처명', period=None, body=(), files=True),
    '행정규칙별표': dict(target='admbyl', id=('별표일련번호',), title='별표명', no='별표번호',
                   date=('발령일자',), org='소관부처명', period=None, body=(), files=True),
    # 법령·행정규칙은 본문이 중첩 구조라 render 함수로 텍스트를 만든다. 법령 본문은 MST(법령일련번호)로 받는다
    '법령': dict(target='law', id=('법령일련번호',), title='법령명한글', no='공포번호',
               date=('시행일자',), org='소관부처명', period='efYd', body=(), render='law', id_param='MST'),
    '행정규칙': dict(target='admrul', id=('행정규칙일련번호',), title='행정규칙명', no='발령번호',
                 date=('발령일자',), org='소관부처명', period='prmlYd', body=(), render='admrul'),
}
ALIASES = {v['target'].lower(): k for k, v in TYPES.items()}
SORTS = {'최신': 'ddes', '오래된': 'dasc', '제목': 'lasc', '번호': 'nasc'}
COURTS = {'대법원': '400201', '하급심': '400202'}
ORGS = {'고용노동부': '1492000'}        # 소관부처코드. 다른 부처는 숫자 코드를 그대로 넘긴다
RULE_KINDS = {'훈령': '1', '예규': '2', '고시': '3', '공고': '4', '지침': '5', '기타': '6'}


class LawGoError(Exception):
    pass


def kind_of(name):
    if name in TYPES:
        return name
    if name.lower() in ALIASES:
        return ALIASES[name.lower()]
    raise LawGoError('알 수 없는 종류: ' + name + ' (가능: ' + ', '.join(TYPES) + ')')


def home():
    base = os.environ.get('LAWGO_HOME') or Path(os.environ.get('LOCALAPPDATA') or Path.home() / '.local' / 'share') / '노동사건자동화'
    return Path(base)


def write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    temporary.write_text(text, encoding='utf-8')
    temporary.replace(path)


def oc_value(given=None):
    if given:
        return given
    if os.environ.get('LAWGO_OC'):
        return os.environ['LAWGO_OC']
    config = home() / 'lawgo.json'
    if config.is_file():
        value = json.loads(config.read_text(encoding='utf-8')).get('OC')
        if value:
            return value
    raise LawGoError('법제처 OPEN API 인증값이 없습니다. open.law.go.kr에서 OPEN API 사용을 신청하고(이 PC의 공인 IP 등록) '
                     '`python 공통/scripts/lawgo.py set-oc 인증값`으로 저장하십시오.')


def set_oc(value):
    write(home() / 'lawgo.json', json.dumps({'OC': value}, ensure_ascii=False))
    return {'저장': str(home() / 'lawgo.json')}


def call(path, params, oc, raw=False):
    query = urllib.parse.urlencode({'OC': oc, 'type': 'HTML' if raw else 'JSON',
                                    **{k: v for k, v in params.items() if v not in (None, '')}})
    request = urllib.request.Request(BASE + path + '?' + query, headers={'User-Agent': 'Mozilla/5.0 (labor-workflow)'})
    for attempt in range(3):
        try:
            with OPENER(request, timeout=30) as response:
                body = response.read()
            break
        except urllib.error.HTTPError as exc:            # URLError 의 하위 클래스이므로 먼저 둔다
            if exc.code < 500 or attempt == 2:
                raise LawGoError(f'HTTP {exc.code}: {path}') from exc
        except (OSError, http.client.HTTPException) as exc:
            # URLError·시간 초과뿐 아니라 응답 도중 끊긴 연결(RemoteDisconnected·ConnectionResetError·
            # IncompleteRead)도 다시 시도한다. 한 번 끊겼다고 harvest 전체가 멈추지 않게 하기 위해서다.
            if attempt == 2:
                raise LawGoError(f'연결 실패: {str(exc) or type(exc).__name__}') from exc
        time.sleep(1.5 * (attempt + 1))
    CALLS['n'] += 1
    time.sleep(DELAY)
    text = body.decode('utf-8', 'replace')
    if raw:
        return text
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise LawGoError('JSON이 아닌 응답: ' + re.sub(r'\s+', ' ', text)[:200]) from exc
    if isinstance(data, dict) and 'result' in data and 'msg' in data:
        raise LawGoError(f"{data['result']} {data['msg']}".strip())
    return data


def unwrap(data):
    if isinstance(data, dict) and len(data) == 1:
        value = next(iter(data.values()))
        if isinstance(value, dict):
            return value
        raise LawGoError(str(value).strip())       # 예: {"Law": "일치하는 판례가 없습니다."}
    raise LawGoError('예상하지 못한 응답 모양: ' + json.dumps(data, ensure_ascii=False)[:200])


def list_items(root):
    for value in root.values():
        if isinstance(value, dict) and 'id' in value:
            return [value]
        if isinstance(value, list) and value and isinstance(value[0], dict) and 'id' in value[0]:
            return value
    return []


def pick(item, keys):
    for key in keys:
        if item.get(key):
            return str(item[key]).strip()
    return ''


def ymd(value):
    """'2021.11.25' '20211125' '2026.8.4.' 를 '2021-11-25' 꼴로 맞춘다.

    근로복지공단산재판례는 선고일자가 없어 '0001.01.01'로 오므로 빈 값으로 둔다(사건번호·법원명도 목록에서는 비고 본문에만 있다).
    """
    value = (value or '').strip()
    parts = re.findall(r'\d+', value)
    if len(parts) == 1 and len(parts[0]) >= 8:
        parts = [parts[0][:4], parts[0][4:6], parts[0][6:8]]
    if len(parts) >= 3 and len(parts[0]) == 4:
        return f'{parts[0]}-{int(parts[1]):02d}-{int(parts[2]):02d}' if int(parts[0]) >= 1900 else ''
    return value


def to_text(value):
    if not isinstance(value, str):
        return '' if value is None else str(value)
    text = re.sub(r'<(script|style)\b.*?</\1\s*>', '', value, flags=re.S | re.I)
    text = re.sub(r'<br\s*/?>|</p\s*>|</div\s*>|</li\s*>|</tr\s*>', '\n', text, flags=re.I)
    # 영문 이름의 HTML 태그만 지운다. '<개정 2018.3.20>' '부칙 <제8372호,2007.4.11>' 같은 조문 부기는 남긴다
    text = html.unescape(re.sub(r'</?[A-Za-z][A-Za-z0-9:-]*(?:\s[^<>]*)?/?>', '', text))
    text = re.sub(r'[ \t ]+\n', '\n', text)
    return re.sub(r'\n{3,}', '\n\n', text).strip()


def lbox_url(court, number):
    """LBOX 판례 주소를 만든다. 법원명·사건번호로 만든 추정 주소이므로 인용 전에 열어 확인한다."""
    number = (number or '').split(',')[0].strip()
    court = (court or '').replace(' ', '')
    if not court or not re.fullmatch(r'\d{2,4}[가-힣]+\d+', number):
        return ''
    return 'https://lbox.kr/case/' + court + '/' + number


def as_list(value):
    return value if isinstance(value, list) else ([] if value in (None, '') else [value])


def joined(value):
    """문자열·중첩 목록을 줄바꿈으로 이은 텍스트로 만든다(부칙·별표 내용이 목록의 목록으로 온다)."""
    if isinstance(value, list):
        return '\n'.join(x for x in (joined(v) for v in value) if x)
    if isinstance(value, dict):
        return joined(value.get('content'))
    return to_text(value)


def article_text(unit):
    """조문단위 하나를 조문내용 → 항 → 호 → 목 순서의 텍스트로 만든다. 번호는 내용 안에 들어 있다."""
    lines = [joined(unit.get('조문내용'))]
    for hang in as_list(unit.get('항')):
        if not isinstance(hang, dict):
            lines.append(joined(hang))
            continue
        lines.append(joined(hang.get('항내용')))
        for ho in as_list(hang.get('호')):
            if not isinstance(ho, dict):
                lines.append(joined(ho))
                continue
            lines.append(joined(ho.get('호내용')))
            lines += [joined(mok.get('목내용')) if isinstance(mok, dict) else joined(mok) for mok in as_list(ho.get('목'))]
    lines.append(joined(unit.get('조문참고자료')))
    return '\n'.join(x for x in lines if x)


def table_block(unit):
    link = unit.get('별표서식PDF파일링크') or unit.get('별표서식파일링크') or ''
    if isinstance(link, str) and link.startswith('/'):
        link = 'https://www.law.go.kr' + link
    head = ' '.join(x for x in (to_text(unit.get('별표구분')), to_text(unit.get('별표제목')), link) if x)
    return '\n'.join(x for x in (head, joined(unit.get('별표내용'))) if x)


def render_law(root):
    out = {}
    units = [u for u in as_list((root.get('조문') or {}).get('조문단위')) if isinstance(u, dict)]
    if units:
        out['조문'] = '\n\n'.join(article_text(u) for u in units)
    addenda = [joined(u.get('부칙내용')) for u in as_list((root.get('부칙') or {}).get('부칙단위')) if isinstance(u, dict)]
    if any(addenda):
        out['부칙'] = '\n\n'.join(a for a in addenda if a)
    tables = [u for u in as_list((root.get('별표') or {}).get('별표단위')) if isinstance(u, dict)]
    if tables:
        out['별표'] = '\n\n'.join(b for b in (table_block(u) for u in tables) if b)
    return out


def render_admrul(root):
    """행정규칙 본문. 지침은 내용이 첨부파일(HWP·PDF)에만 있는 경우가 있어 첨부파일 이름과 주소를 함께 남긴다."""
    out = {}
    articles = [joined(x) for x in as_list(root.get('조문내용'))]
    if any(articles):
        out['조문'] = '\n\n'.join(a for a in articles if a)
    addenda = root.get('부칙')
    addenda = joined(addenda.get('부칙내용')) if isinstance(addenda, dict) else joined(addenda)
    if addenda:
        out['부칙'] = addenda
    tables = root.get('별표')
    tables = [u for u in as_list(tables.get('별표단위')) if isinstance(u, dict)] if isinstance(tables, dict) else []
    if tables:
        out['별표'] = '\n\n'.join(b for b in (table_block(u) for u in tables) if b)
    files = root.get('첨부파일') if isinstance(root.get('첨부파일'), dict) else {}
    names, links = as_list(files.get('첨부파일명')), as_list(files.get('첨부파일링크'))
    if names:
        out['첨부파일'] = '\n'.join(f'{to_text(n)} {links[i] if i < len(links) else ""}'.strip() for i, n in enumerate(names))
    return out


RENDERERS = {'law': render_law, 'admrul': render_admrul}


def flat(kind, item):
    """법령·행정규칙 본문 응답의 기본정보를 목록 항목과 같은 모양으로 펼친다."""
    if kind == '법령' and isinstance(item.get('기본정보'), dict):
        info = item['기본정보']
        content = lambda v: v.get('content') if isinstance(v, dict) else v
        return {**info, '법령명한글': info.get('법령명_한글'), '법령약칭명': info.get('법령명약칭'),
                '소관부처명': content(info.get('소관부처')), '법령구분명': content(info.get('법종구분'))}
    if kind == '행정규칙' and isinstance(item.get('행정규칙기본정보'), dict):
        return item['행정규칙기본정보']
    return item


def normalize(kind, item):
    t = TYPES[kind]
    item = flat(kind, item)
    row = {'종류': kind, 'id': pick(item, t['id']), '제목': pick(item, (t['title'],)),
           '사건번호': pick(item, (t['no'],)), '일자': ymd(pick(item, t['date'])),
           '기관': pick(item, (t['org'],)) if t['org'] else ''}
    if kind == '판례':
        # 국세법령정보시스템 판례는 법원명이 비고 사건번호가 '서울행정법원-2025-구합-53785' 꼴로 온다
        m = re.fullmatch(r'([가-힣]+)-(\d{4})-([가-힣]+)-(\d+)', row['사건번호'])
        if m:
            row['기관'] = row['기관'] or m.group(1)
            row['사건번호'] = m.group(2) + m.group(3) + m.group(4)
        row['출처'] = pick(item, ('데이터출처명',))
        row['판결유형'] = pick(item, ('판결유형',))
        row['lbox'] = lbox_url(row['기관'], row['사건번호'])
        if row['id']:
            row['법제처'] = 'https://www.law.go.kr/LSW/precInfoP.do?precSeq=' + row['id']
    elif kind == '법령':
        row.update(법령ID=pick(item, ('법령ID',)), 구분=pick(item, ('법령구분명',)), 현행=pick(item, ('현행연혁코드',)),
                   약칭=pick(item, ('법령약칭명',)), 공포일자=ymd(pick(item, ('공포일자',))))
        row['링크'] = 'https://www.law.go.kr/법령/' + re.sub(r'\s', '', row['제목']) if row['제목'] else ''
    elif kind == '행정규칙':
        # 목록의 '행정규칙상세링크'에는 인증값이 들어 있으므로 옮기지 않는다
        row.update(규칙종류=pick(item, ('행정규칙종류',)), 현행=pick(item, ('현행연혁구분', '현행여부')),
                   시행일자=ymd(pick(item, ('시행일자',))), 행정규칙ID=pick(item, ('행정규칙ID',)))
        row['링크'] = 'https://www.law.go.kr/행정규칙/' + re.sub(r'\s', '', row['제목']) if row['제목'] else ''
    elif kind == '인권위':
        row['분류'] = pick(item, ('분류명',))
        row['링크'] = pick(item, ('바로보기URL',))
        row['원본'] = pick(item, ('원본다운로드URL',))
    elif t.get('files'):
        # 별표번호는 '000300'(별표 3)·'000302'(별표 3의2) 꼴이다. 앞 네 자리가 번호, 뒤 두 자리가 가지번호이다
        번호 = (row['사건번호'] or '').zfill(6)
        본, 가지 = 번호[:4].lstrip('0') or '', 번호[4:].lstrip('0')
        row['사건번호'] = ' '.join(x for x in (pick(item, ('별표종류',)), 본 + ('의' + 가지 if 가지 else '')) if x).strip()
        row['근거'] = pick(item, ('관련법령명', '관련행정규칙명'))
        for 칸, 키 in (('한글파일', '별표서식파일링크'), ('PDF파일', '별표서식PDF파일링크')):
            link = pick(item, (키,))
            row[칸] = ('https://www.law.go.kr' + link) if link.startswith('/') else link
    return row


def squash(name):
    return re.sub(r'[\s·ㆍ・]', '', name or '')


# 사건번호의 사건부호와 정규식은 공통/scripts/system.py 한 곳에만 둔다(citation_check 와 같은 정의).
CASE_TYPES = _system.CASE_TYPES
CASE_NUMBER = re.compile(_system.CASE_NUMBER)
# 법원 이름은 실제 이름 꼴로만 잡는다. LBOX 본문 머리는 화면 글자가 붙어 와서('확정원고패서울남부지방법원') 느슨하게 잡으면 앞 글자가 딸려 온다
REGIONS = '서울|부산|대구|인천|광주|대전|울산|수원|의정부|춘천|청주|전주|창원|제주'
COURT_NAME = re.compile(r'(대법원|헌법재판소|특허법원|(?:' + REGIONS + r')(?:중앙|동부|남부|북부|서부)?'
                        r'(?:고등법원|지방법원|행정법원|가정법원|회생법원|고법|지법|행법|가법)(?:[가-힣]{1,4}(?:지원|재판부))?)')
SHORT_COURTS = {'고법': '고등법원', '지법': '지방법원', '행법': '행정법원', '가법': '가정법원'}


def cited_cases(text):
    """본문·참조판례에서 인용된 사건을 (법원, 사건번호)로 뽑는다.

    '선고'(결정은 '…자')가 앞에 붙은 번호와 거기에 쉼표로 이어진 번호만 인용으로 센다('대법원 2012. 3. 29. 선고 2011두2132,
    2011두2149 판결'). 판결 머리에 붙은 상·하위 판결 목록처럼 '선고'가 없는 번호는 빠진다. 법원은 번호 앞 60자 안의 법원 이름이고,
    없으면('같은 날 선고') 앞 인용의 법원을 쓴다. 자기 사건번호는 부르는 쪽에서 뺀다.
    """
    text = to_text(text) if isinstance(text, str) else joined(text)
    found, court, chain_end = [], '', -1
    for m in CASE_NUMBER.finditer(text):
        chained = chain_end >= 0 and re.fullmatch(r'[\s,·ㆍ및]*', text[chain_end:m.start()]) is not None
        if not chained and not re.search(r'선고\s*$|선고\s|\.\s*자\s*$', text[max(0, m.start() - 25):m.start()]):
            chain_end = -1
            continue
        names = COURT_NAME.findall(text[max(0, m.start() - 60):m.start()])
        if names:
            court = re.sub('|'.join(SHORT_COURTS), lambda s: SHORT_COURTS[s.group(0)], names[-1])
        chain_end = m.end()
        pair = (court, re.sub(r'\s', '', m.group(0)))
        if court and pair not in found:
            found.append(pair)
    return found


def search(kind, query='', *, body=False, court=None, source=None, period=None, number=None, ref_law=None,
           org=None, rule_kind=None, history=False, sort='최신', limit=100, oc=None):
    kind = kind_of(kind)
    t = TYPES[kind]
    params = {'target': t['target'], 'query': query, 'search': 2 if body else None,
              'display': min(PAGE, max(1, limit)), 'sort': SORTS.get(sort, sort)}
    if period:
        if not t['period']:
            raise LawGoError(kind + '는 기간 검색을 지원하지 않습니다.')
        params[t['period']] = period
    if kind == '판례':
        if court and court not in COURTS:
            raise LawGoError('법원은 대법원 또는 하급심으로 지정하십시오.')
        params.update(org=COURTS.get(court), datSrcNm=source, nb=number, JO=ref_law)
    elif court or source or ref_law:
        raise LawGoError('법원·출처·참조법령 조건은 판례에만 쓸 수 있습니다.')
    elif number:
        field = {'헌재': 'nb', '법령해석': 'itmno', '노동부해석': 'itmno', '법령': 'nb', '행정규칙': 'nb'}.get(kind)
        if not field:
            raise LawGoError(kind + '는 번호 검색을 지원하지 않습니다. 검색어로 찾으십시오.')
        params[field] = number
    if org or rule_kind or history:
        if kind not in ('법령', '행정규칙'):
            raise LawGoError('소관부처·규칙종류·연혁 조건은 법령·행정규칙에만 쓸 수 있습니다.')
        if org:
            params['org'] = ORGS.get(org, org)
        if rule_kind:
            if kind != '행정규칙' or rule_kind not in RULE_KINDS:
                raise LawGoError('규칙종류는 행정규칙에만 쓰고 ' + '·'.join(RULE_KINDS) + ' 가운데 하나로 지정하십시오.')
            params['knd'] = RULE_KINDS[rule_kind]
        if history:       # 법령은 시행일 기준 목록에서 연혁·시행예정·현행을 모두, 행정규칙은 연혁만 받는다
            params.update(target='eflaw', nw='1,2,3') if kind == '법령' else params.update(nw=2)
    oc = oc_value(oc)
    rows, total, page = [], 0, 1
    while len(rows) < limit:
        root = unwrap(call('lawSearch.do', {**params, 'page': page}, oc))
        total = int(re.sub(r'\D', '', str(root.get('totalCnt') or '0')) or 0)
        items = list_items(root)
        if not items:
            break
        rows.extend(normalize(kind, item) for item in items)
        if len(rows) >= total:
            break
        page += 1
    return {'종류': kind, '검색어': query, '범위': '본문' if body else '제목', '전체': total,
            '받은건수': len(rows[:limit]), 'rows': rows[:limit]}


def fetch_file(url, out):
    """별표·서식의 한글·PDF 파일을 내려받는다. url 은 search 결과의 '한글파일'·'PDF파일' 값이다."""
    if not url.startswith('https://www.law.go.kr/'):
        raise LawGoError('법제처 파일 주소가 아닙니다: ' + url[:80])
    request = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (labor-workflow)'})
    try:
        with OPENER(request, timeout=60) as response:
            data = response.read()
            headers = getattr(response, 'headers', None)
            name = (headers.get('Content-Disposition') if headers else '') or ''
    except (OSError, http.client.HTTPException) as exc:     # HTTPError·URLError·끊긴 연결
        raise LawGoError(f'파일 내려받기 실패: {str(exc) or type(exc).__name__}') from exc
    CALLS['n'] += 1
    path = Path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return {'파일': str(path), '바이트': len(data), '원래이름': urllib.parse.unquote(name.split("''")[-1]) if "''" in name else ''}


def show(kind, ident, *, oc=None, refresh=False):
    kind = kind_of(kind)
    t = TYPES[kind]
    if t.get('files'):
        raise LawGoError(f"{kind}는 본문이 API로 오지 않습니다(뷰어 HTML만 옴). "
                         f"search 결과의 '한글파일'·'PDF파일' 주소를 쓰거나 file 명령으로 내려받으십시오.")
    cache = home() / '캐시' / 'lawgo' / t['target'] / (str(ident) + '.json')
    if cache.is_file() and not refresh:
        root = json.loads(cache.read_text(encoding='utf-8'))
    else:
        oc = oc_value(oc)
        try:
            root = unwrap(call('lawService.do', {'target': t['target'], t.get('id_param', 'ID'): ident}, oc))
        except LawGoError as exc:
            # 국세청 판례는 JSON으로 '일치하는 판례가 없습니다'가 온다. 인증·연결 오류는 그대로 알린다
            if kind != '판례' or str(exc).startswith(('사용자 정보', 'HTTP', '연결 실패')):
                raise LawGoError(f'{kind} {ident}: {exc}') from exc
            page = call('lawService.do', {'target': t['target'], 'ID': ident}, oc, raw=True)
            if len(to_text(page)) < 200:
                if 'precInfoP.do' in page:        # HTML도 누리집 화면을 띄우는 틀뿐이다(2026. 9. 17. 실측)
                    raise LawGoError(f'{kind} {ident}: API로 본문이 제공되지 않는 판례입니다(국세법령정보시스템 등). '
                                     f'https://www.law.go.kr/LSW/precInfoP.do?precSeq={ident} 에서 사람이 열람합니다') from exc
                raise LawGoError(f'{kind} {ident}: {exc}') from exc
            root = {'판례일련번호': str(ident), '판례내용': page}
        write(cache, json.dumps(root, ensure_ascii=False))
    meta = normalize(kind, root)
    meta['id'] = meta['id'] or str(ident)
    if t.get('render'):
        return {**meta, '본문': RENDERERS[t['render']](root)}
    return {**meta, '본문': {f: to_text(root.get(f)) for f in t['body'] if to_text(root.get(f))}}


def markdown(doc):
    head = ' '.join(x for x in (doc['기관'], doc['일자'], doc['사건번호'], doc['제목']) if x)
    lines = [f"## [{doc['종류']}] {head}", '',
             '- 법제처 일련번호: ' + doc['id']]
    for key in ('출처', '판결유형', '규칙종류', '구분', '현행', '시행일자', '법령ID', '행정규칙ID',
                '분류', '근거', '한글파일', 'PDF파일', '원본', 'lbox', '법제처', '링크', '검색어'):
        if doc.get(key):
            lines.append(f'- {key}: {doc[key]}')
    for name, text in doc['본문'].items():
        lines += ['', f'### {name}', '', text]
    return '\n'.join(lines) + '\n'


def citation_ranking(docs, rows=()):
    """받은 본문들이 인용한 판례를 '인용한 판결 수' 순서로 세운다. 여러 판결이 함께 인용한 것이 그 쟁점의 지도적 판례일 가능성이 높다.

    한 판결이 같은 판례를 여러 번 인용해도 1건으로 센다. 자기 사건번호는 뺀다. 검색 목록에 이미 있는지도 함께 적는다.
    건수가 같으면 대법원을 앞에 두고, 그다음은 docs 앞쪽(목록 상위) 판결이 먼저 인용한 순서이다. 사건번호 순으로 둘 때보다
    대법원 30건 시험의 인용 순위 상위 20건 재현율이 55%에서 63%로 높았다(2026. 9. 17., 공통/검증/판례검색).
    """
    listed = {(squash(r.get('기관')), n.strip()) for r in rows for n in (r.get('사건번호') or '').split(',')}
    counts, citing = {}, {}
    for doc in docs:
        own = {n.strip() for n in (doc.get('사건번호') or '').split(',')}
        text = '\n'.join(v for k, v in doc['본문'].items() if k in ('참조판례', '판례내용', '이유', '전문', '결정요지', '판결요지', '재결요지', '회답'))
        for court, number in cited_cases(text):
            if number in own:
                continue
            key = (court, number)
            counts[key] = counts.get(key, 0) + 1
            citing.setdefault(key, []).append(' '.join(x for x in (doc.get('기관'), doc.get('사건번호')) if x))
    ranked = sorted(counts, key=lambda k: (-counts[k], k[0] != '대법원'))       # counts 는 처음 인용된 순서를 지니고 sorted 는 안정 정렬이다
    return [{'법원': court, '사건번호': number, '인용건수': counts[(court, number)], '인용한판결': citing[(court, number)][:5],
             '목록에있음': (squash(court), number) in listed, 'lbox': lbox_url(court, number)} for court, number in ranked]


def harvest(kinds, queries, *, body=False, court=None, source=None, period=None, org=None, rule_kind=None,
            limit=300, texts=0, texts_title=(), exclude=(), oc=None, out=None):
    """texts_title: 본문은 사건명·안건명에 이 낱말 가운데 하나가 든 것에서만 고른다. 넓은 검색어에 걸린 무관한 판결이 본문과 인용 순위를 채우지 않게 한다.
    exclude: 목록·본문·인용 순위에서 뺄 사건번호. 검증에서 시험 사건 자신의 본문(정답인 참조판례가 적혀 있다)을 읽지 않게 한다."""
    oc = oc_value(oc)
    start, exclude = CALLS['n'], set(exclude)
    summary, listing = {}, {}
    for name in kinds:
        kind = kind_of(name)
        merged, origin, searches, totals = {}, {}, [], {}
        for query in queries:
            result = search(kind, query, body=body, court=court if kind == '판례' else None,
                            source=source if kind == '판례' else None,
                            period=period if TYPES[kind]['period'] else None,
                            org=org if kind in ('법령', '행정규칙') else None,
                            rule_kind=rule_kind if kind == '행정규칙' else None, limit=limit, oc=oc)
            searches.append({'검색어': query, '전체': result['전체'], '받은건수': result['받은건수']})
            totals[query] = result['전체']
            for row in result['rows']:
                if exclude & {n.strip() for n in (row['사건번호'] or '').split(',')}:
                    continue
                # 같은 판결이 출처별로 두 번 올 수 있으므로 법원·사건번호가 있으면 그것으로 합친다
                key = (row['기관'], row['사건번호']) if kind == '판례' and row['기관'] and row['사건번호'] else row['id']
                if key not in merged or (merged[key].get('출처') == '국세법령정보시스템' and row.get('출처') != '국세법령정보시스템'):
                    merged[key] = row
                origin.setdefault(key, [])
                if query not in origin[key]:
                    origin[key].append(query)
        # 여러 검색어에 걸린 것 → 전체 건수가 적은(좁은) 검색어에 걸린 것 → 최신 순. 최신순만 쓸 때보다 대법원 30건 시험의
        # 목록 상위 50건 재현율이 55%에서 61%로 높았다(2026. 9. 17., 공통/검증/판례검색)
        order = sorted(merged, key=lambda k: merged[k]['일자'], reverse=True)
        order.sort(key=lambda k: (-len(origin[k]), min(totals[q] for q in origin[k])))
        rows = [dict(merged[k], 검색어=' / '.join(origin[k])) for k in order]
        docs, failed = [], []
        tax = [r for r in rows if r.get('출처') == '국세법령정보시스템']      # API로 본문이 오지 않는다
        candidates = [r for r in rows if r.get('출처') != '국세법령정보시스템']
        if texts_title:
            candidates = [r for r in candidates if any(squash(w) in squash(r['제목']) for w in texts_title)]
        if TYPES[kind].get('files'):     # 별표·서식은 본문이 API로 오지 않는다. 목록의 파일 주소를 쓴다
            candidates = []
        for row in candidates[:texts]:
            try:
                docs.append(dict(show(kind, row['id'], oc=oc), 검색어=row['검색어']))
            except LawGoError as exc:
                if '사용자 정보 검증' in str(exc) or '연결 실패' in str(exc):
                    raise
                failed.append({'id': row['id'], '사건번호': row['사건번호'], '사유': str(exc)})
        ranking = [r for r in citation_ranking(docs, rows) if r['사건번호'] not in exclude]
        listing[kind] = {'검색': searches, 'rows': rows, '인용순위': ranking}
        summary[kind] = {'검색': searches, '합친건수': len(rows), '본문': len(docs), '본문실패': failed}
        if texts and texts_title:
            summary[kind]['본문후보'] = f"사건명에 {'·'.join(texts_title)} 가운데 하나가 든 {len(candidates)}건"
        if docs:        # 인용 순위를 믿기 전에 받은 본문이 쟁점과 맞는지 제목으로 본다
            summary[kind]['본문목록'] = [' '.join(x for x in (d.get('기관'), d.get('사건번호'), (d.get('제목') or '')[:40]) if x) for d in docs]
        if tax:
            summary[kind]['국세판례_본문미제공'] = len(tax)
        if ranking:
            summary[kind]['인용순위_상위'] = [f"{r['법원']} {r['사건번호']} ({r['인용건수']}건{'' if r['목록에있음'] else ', 목록 밖'})"
                                          for r in ranking[:15]]
        if out:
            folder = Path(out)
            write(folder / f'법제처_본문_{kind}.md', f'# 법제처 {kind} 본문 {len(docs)}건\n\n' + '\n'.join(markdown(d) for d in docs))
            summary[kind]['본문파일'] = str(folder / f'법제처_본문_{kind}.md')
    if out:
        write(Path(out) / '법제처_목록.json', json.dumps(listing, ensure_ascii=False, indent=2))
    return {'목록파일': str(Path(out) / '법제처_목록.json') if out else None, '호출': CALLS['n'] - start,
            '종류별': summary, **({} if out else {'목록': listing})}


def jo_code(number):
    """'76의2' '제76조의2' '23' 을 API의 6자리 조 번호(조 4자리 + 가지 2자리)로 바꾼다."""
    m = re.fullmatch(r'\s*(?:제\s*)?(\d+)\s*(?:조)?\s*(?:의\s*(\d+))?\s*', str(number))
    if not m:
        raise LawGoError('조 번호는 23, 76의2, 제76조의2 꼴로 적으십시오.')
    return f'{int(m.group(1)):04d}{int(m.group(2) or 0):02d}'


def jo_label(code):
    return f'제{int(code[:4])}조' + (f'의{int(code[4:])}' if int(code[4:]) else '')


def find_law(name, oc):
    items = list_items(unwrap(call('lawSearch.do', {'target': 'law', 'query': name, 'display': PAGE}, oc)))
    for item in items:
        if squash(name) in (squash(item.get('법령명한글')), squash(item.get('법령약칭명'))):
            return item
    raise LawGoError(f'이름이 일치하는 현행 법령이 없습니다: {name}'
                     + (' (후보: ' + ', '.join(i.get('법령명한글', '') for i in items[:8]) + ')' if items else ''))


def article(name, number, *, date=None, oc=None):
    """법령 조문 하나를 받는다. date(YYYYMMDD)를 주면 그날 시행 중이던 판본의 조문을 받는다."""
    oc = oc_value(oc)
    law, jo = find_law(name, oc), jo_code(number)
    version, day = law, None
    if date:
        day = re.sub(r'\D', '', date)
        if len(day) != 8:
            raise LawGoError('기준일은 20190716 꼴로 적으십시오.')
        versions, page = [], 1
        while True:
            items = list_items(unwrap(call('lawSearch.do', {'target': 'eflaw', 'LID': law['법령ID'], 'nw': '1,2,3',
                                                            'display': PAGE, 'page': page, 'sort': 'efdes'}, oc)))
            versions += [v for v in items if v.get('법령ID') == law['법령ID']]     # 제명이 바뀐 옛 판본도 법령ID는 같다
            if len(items) < PAGE:
                break
            page += 1
        past = [v for v in versions if v.get('시행일자') and v['시행일자'] <= day]
        if not past:
            raise LawGoError(f"{law['법령명한글']}: {ymd(day)} 당시 시행 중이던 판본을 찾지 못했습니다.")
        version = max(past, key=lambda v: v['시행일자'])
        params = {'target': 'eflawjosub', 'MST': version['법령일련번호'], 'efYd': version['시행일자'], 'JO': jo}
    else:
        params = {'target': 'lawjosub', 'MST': law['법령일련번호'], 'JO': jo}
    # 법령일련번호(MST)는 판본마다 달라지므로 판본·시행일·조 번호로 보관하면 개정 뒤에도 섞이지 않는다
    cache = home() / '캐시' / 'lawgo' / 'article' / f"{params['MST']}_{params.get('efYd', '현행')}_{jo}.json"
    if cache.is_file():
        data = json.loads(cache.read_text(encoding='utf-8'))
    else:
        data = unwrap(call('lawService.do', params, oc))
        write(cache, json.dumps(data, ensure_ascii=False))
    label = jo_label(jo)
    units = [u for u in as_list((data.get('조문') or {}).get('조문단위')) if isinstance(u, dict) and u.get('조문여부') != '전문']
    if not units:
        raise LawGoError(f"{law['법령명한글']} {label}: " + (f"{ymd(day)} 당시 판본(시행 {ymd(version['시행일자'])})에 없는 조문입니다"
                                                             if day else '없는 조문입니다'))
    return {'법령': version.get('법령명한글') or law['법령명한글'], '조': label, '기준': ymd(day) if day else '현행',
            '시행일자': ymd(version.get('시행일자')), '공포': f"{ymd(version.get('공포일자'))} 제{version.get('공포번호', '')}호",
            '링크': 'https://www.law.go.kr/법령/' + re.sub(r'\s', '', law['법령명한글']) + '/' + label,
            '조문': '\n\n'.join(article_text(u) for u in units)}


def article_markdown(doc):
    return (f"## {doc['법령']} {doc['조']} ({doc['기준']} 기준, 시행 {doc['시행일자']})\n\n"
            f"- 공포: {doc['공포']}\n- 링크: {doc['링크']}\n\n{doc['조문']}\n")


def check(oc=None):
    result = search('판례', number='2020다270503', limit=1, sort=None, oc=oc)
    return {'ok': result['전체'] >= 1, '확인': result['rows'][:1]}


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--oc', help='인증값을 이번 실행에만 지정한다(기본: LAWGO_OC 환경변수 또는 set-oc로 저장한 값)')
    subs = parser.add_subparsers(dest='command', required=True)
    s = subs.add_parser('set-oc', help='이 PC에 인증값을 저장한다'); s.add_argument('value')
    subs.add_parser('check', help='인증값과 IP 등록을 확인한다(호출 1회)')
    s = subs.add_parser('search', help='목록을 받는다')
    s.add_argument('kind', help='종류: ' + ', '.join(TYPES)); s.add_argument('query', nargs='?', default='')
    s.add_argument('--body', action='store_true', help='본문검색(기본은 제목·사건명 검색)')
    s.add_argument('--court', choices=sorted(COURTS)); s.add_argument('--source', help='판례 데이터출처명(예: 근로복지공단산재판례)')
    s.add_argument('--period', help='기간 20200101~20221231'); s.add_argument('--number', help='사건번호·안건번호·공포번호·발령번호')
    s.add_argument('--org', help='법령·행정규칙 소관부처(고용노동부 또는 숫자 코드)')
    s.add_argument('--rule-kind', choices=list(RULE_KINDS), help='행정규칙 종류')
    s.add_argument('--history', action='store_true', help='법령은 연혁·시행예정까지, 행정규칙은 연혁만 받는다')
    s.add_argument('--sort', default='최신', choices=sorted(SORTS)); s.add_argument('--limit', type=int, default=100)
    s.add_argument('--out', help='전체 결과를 JSON 파일로 쓴다')
    s = subs.add_parser('show', help='본문을 받는다(보관함에 있으면 요청하지 않는다). 법령은 법령일련번호(MST)를 넘긴다')
    s.add_argument('kind'); s.add_argument('id'); s.add_argument('--refresh', action='store_true')
    s.add_argument('--out', help='마크다운 파일로 쓴다')
    s = subs.add_parser('article', help='법령 조문 하나를 받는다. --date를 주면 그날 시행 중이던 조문')
    s.add_argument('law', help='법령명(예: 근로기준법, 근로기준법 시행령)'); s.add_argument('number', help='조 번호(예: 23, 76의2)')
    s.add_argument('--date', help='기준일 20190716'); s.add_argument('--out', help='마크다운 파일로 쓴다')
    s = subs.add_parser('file', help="별표·서식 파일을 내려받는다. search 결과의 '한글파일'·'PDF파일' 주소를 넘긴다")
    s.add_argument('url'); s.add_argument('--out', required=True, help='저장할 경로')
    s = subs.add_parser('harvest', help='여러 검색어·종류를 한꺼번에 받고 합친다')
    s.add_argument('--kinds', required=True, help='쉼표로 구분: ' + ','.join(TYPES))
    s.add_argument('--query', action='append', required=True, help='여러 번 쓸 수 있다')
    s.add_argument('--body', action='store_true'); s.add_argument('--court', choices=sorted(COURTS))
    s.add_argument('--source'); s.add_argument('--period')
    s.add_argument('--org', help='법령·행정규칙 소관부처'); s.add_argument('--rule-kind', choices=list(RULE_KINDS))
    s.add_argument('--limit', type=int, default=300, help='검색어마다 받을 최대 건수')
    s.add_argument('--texts', type=int, default=0, help='종류마다 본문까지 받을 건수(목록 순서대로)')
    s.add_argument('--texts-title', help='본문은 사건명·안건명에 이 낱말 가운데 하나가 든 것에서만 고른다. 쉼표로 구분(예: 보험료,사업종류)')
    s.add_argument('--out', help='결과를 쓸 폴더(예: 사건/라운드1/작업/법제처)')
    args = parser.parse_args()
    try:
        if args.command == 'set-oc':
            result = set_oc(args.value)
        elif args.command == 'check':
            result = check(args.oc)
        elif args.command == 'search':
            result = search(args.kind, args.query, body=args.body, court=args.court, source=args.source,
                            period=args.period, number=args.number, org=args.org, rule_kind=args.rule_kind,
                            history=args.history, sort=args.sort, limit=args.limit, oc=args.oc)
            if args.out:
                write(Path(args.out), json.dumps(result, ensure_ascii=False, indent=2))
                result = {k: v for k, v in result.items() if k != 'rows'} | {'파일': args.out, '앞 20건': result['rows'][:20]}
        elif args.command == 'show':
            doc = show(args.kind, args.id, oc=args.oc, refresh=args.refresh)
            if args.out:
                write(Path(args.out), markdown(doc))
                result = {'파일': args.out, '글자수': {k: len(v) for k, v in doc['본문'].items()}}
            else:
                print(markdown(doc))
                return 0
        elif args.command == 'file':
            result = fetch_file(args.url, args.out)
        elif args.command == 'article':
            doc = article(args.law, args.number, date=args.date, oc=args.oc)
            if args.out:
                write(Path(args.out), article_markdown(doc))
                result = {'파일': args.out, **{k: v for k, v in doc.items() if k != '조문'}}
            else:
                print(article_markdown(doc))
                return 0
        else:
            result = harvest([k.strip() for k in args.kinds.split(',') if k.strip()], args.query, body=args.body,
                             court=args.court, source=args.source, period=args.period, org=args.org,
                             rule_kind=args.rule_kind, limit=args.limit, texts=args.texts, oc=args.oc, out=args.out,
                             texts_title=[w.strip() for w in (args.texts_title or '').split(',') if w.strip()])
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if args.command != 'check' or result['ok'] else 1
    except (LawGoError, OSError, ValueError) as exc:
        print('오류: ' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
