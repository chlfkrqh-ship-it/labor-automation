"""대법원 누리집(대국민서비스)의 판결 게시판 조회 도구. LBOX 를 멈춘 동안(2026. 11. 11.~) 하급심 판결을 보태는 경로이다.

로그인이 없고 공개 게시판만 읽는다. 받은 목록은 법제처_목록.json 과 같은 칸의 `법원_목록.json` 으로 쓰고, 고른 게시물의
첨부 판결문은 사건 폴더에 받아 글자를 뽑는다. 쓰는 규칙은 `.claude/skills/법원판결-검색/SKILL.md`, 약관·주소 확인 기록은
`공통/판례출처.md` 에 있다.

  주요판결  전국법원 주요판결  /portal/dcboard/DcNewsListAction.work?gubun=44   각급법원이 고른 하급심 판결의 요지와 판결문(비실명)
  판례속보  판례속보          /portal/news/NewsListAction.work?gubun=4&type=5  법원도서관의 대법원 중요판결 요지·판결문, 공보 요약본
  언론보도  언론보도판결       /portal/news/NewsListAction.work?gubun=2         언론에 보도된 판결의 판결문(첨부)
  공보      판례속보의 '각급법원(제1,2심) 판결공보 요약본'에 적힌 사건 목록(법원·선고일·사건번호·사건명·확정/항소/상고).
            `공보` 명령으로 색인을 만든 뒤 harvest 가 검색어를 사건명에서 찾는다(누리집에 요청하지 않는다)

검색은 게시물 제목에서 띄어쓰기까지 같은 글자열을 찾는다. 본문은 찾지 않고, 띄어 쓴 낱말을 AND 로 걸지 않는다
(2026. 11. 11. 실측: 주요판결 '직장 내 괴롭힘' 11건, '괴롭힘 징계' 0건, 본문에만 있는 '부진정연대채무'로는 그 글이 걸리지 않았다).
그래서 검색어는 제목에 쓰일 낱말 하나나 붙어 다니는 구절로 여러 개 넣고, 여러 검색어에 걸린 글을 앞에 세운다.

지키는 것(LBOX 계정 보호와 같은 뜻)
  - 요청은 한 번에 한 건, 앞 요청과 1.5초 넘게 띄운다(다른 창에서 돌려도 사용량 파일로 간격을 잰다).
  - 하루 상한 2,000건(환경변수 SCOURT_DAILY_MAX). 넘으면 멈춘다. 상한을 올리는 것은 담당자가 정한다.
    2026. 11. 11. 처음에는 4.5초·500건으로 두었다가 같은 날 담당 노무사가 "엘박스도 아닌데 제한 걸 필요 있음?"이라고 물어
    1.5초·2,000건으로 줄였다. 같은 법원 전산망이 전자소송·나의사건검색을 운영하므로 간격은 없애지 않는다.
  - 요청 전에 그 호스트의 robots.txt 를 하루 한 번 받아 가장 긴 규칙으로 판정하고, 막힌 주소는 보내지 않는다.
    첨부 내려받기(file.scourt.go.kr/AttachDownload)는 robots.txt 가 막으므로 쓰지 않고, 허용된 폴더 주소
    (file.scourt.go.kr/dcboard/·/nboard/, www.scourt.go.kr/sjudge/)로만 받는다.
  - 403·429·503 이나 차단·자동입력 확인 화면이 오면 곧바로 멈추고 `중단.txt` 를 남긴다. 담당자가 그 파일을 지우기 전에는
    다시 보내지 않는다(확인 항목을 대신 누르지 않는다).
  - 받은 것은 %LOCALAPPDATA%\\노동사건자동화\\캐시\\scourt\\ 에 두고 다시 요청하지 않는다(목록은 그날만, 게시물·파일은 계속).

    python -B 공통/scripts/scourt.py harvest --query 해고 --query 징계양정 --views 40 --texts 5 --out "{사건}/라운드N/작업/법원"
    python -B 공통/scripts/scourt.py search 주요판결 "직장 내 괴롭힘" --limit 30
    python -B 공통/scripts/scourt.py show 주요판결 28730
    python -B 공통/scripts/scourt.py get 주요판결 28730 --out "{사건}/라운드N/작업/법원"
    python -B 공통/scripts/scourt.py 공보 --limit 300          # 각급법원 판결공보 요약본 색인을 만들거나 잇는다
    python -B 공통/scripts/scourt.py 공보찾기 2025구합54661      # 하급심 사건번호의 확정·항소·상고 표시(색인만 읽는다)
    python -B 공통/scripts/scourt.py usage                     # 오늘 보낸 요청 수와 멈춤 표시

종료 코드: 0 정상, 1 멈춤(상한·차단·robots), 2 잘못 부름.
"""
from __future__ import annotations

import argparse
import html
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile
from datetime import datetime
from pathlib import Path

_spec = importlib.util.spec_from_file_location('workflow_system', Path(__file__).with_name('system.py'))
_system = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_system)
CASE_NUMBER = re.compile(_system.CASE_NUMBER)

ROOT = Path(__file__).resolve().parents[2]
OCR_PS1 = ROOT / '4_서면작성' / 'scripts' / 'ocr_win.ps1'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0 Safari/537.36'
WWW = 'https://www.scourt.go.kr'
DELAY = float(os.environ.get('SCOURT_DELAY', '1.5'))          # 요청 사이 간격(초). 시험만 더 줄인다
DAILY_MAX = int(os.environ.get('SCOURT_DAILY_MAX', '2000'))
LIST_ROWS = 10                                              # 게시판 한 쪽의 글 수
파일_꼴 = ('.md', '.json', '.txt', '.tsv', '.csv', '.html', '.htm', '.pdf', '.docx', '.hwp', '.hwpx', '.xlsx')

BOARDS = {
    '주요판결': {'gubun': '44', 'name': '전국법원 주요판결', 'list': '/portal/dcboard/DcNewsListAction.work?gubun=44',
              'view': '/portal/dcboard/DcNewsViewAction.work?gubun=44&seqnum={seq}&cbub_code={code}'},
    '판례속보': {'gubun': '4', 'name': '판례속보', 'list': '/portal/news/NewsListAction.work?gubun=4', 'type': '5',
             'view': '/portal/news/NewsViewAction.work?seqnum={seq}&gubun=4&type=5'},
    '언론보도': {'gubun': '2', 'name': '언론보도판결', 'list': '/portal/news/NewsListAction.work?gubun=2',
             'view': '/portal/news/NewsViewAction.work?seqnum={seq}&gubun=2'},
}
ALIASES = {'44': '주요판결', '전국법원주요판결': '주요판결', '4': '판례속보', '속보': '판례속보', '2': '언론보도', '언론보도판결': '언론보도',
           'lx': '법고을', 'LX': '법고을'}
# 법원도서관 법고을(https://lx.scourt.go.kr) 판례 검색. 로그인·약관 링크·robots.txt 가 없고 화면 코드에 로봇 탐지가 없다(2026. 11. 11.).
# 종합법률정보·법제처와 같은 법원도서관 판례 자료여서(그날 두 쟁점의 결과 9건·39건이 모두 법제처 결과 안에 있었다) 법제처를 갈음하는
# 예비 경로와 판결 전문 화면 주소로 쓴다. 검색은 판결 전문에서 띄어 쓴 낱말을 모두 찾는다(AND)
LX = 'https://lx.scourt.go.kr'
LX_LIST = LX + '/search/precedent/get/list?search_txt={q}&order_by=des&order_column=d&tab_idx=0&page_no={page}&display=100&search_mode=simple'
# 첨부를 내려받는 download('파일','이름') 의 path 값과, robots.txt 가 허용한 같은 파일의 폴더 주소. 2026. 11. 11. 주요판결(게시물 화면
# path '003')은 /dcboard/, 언론보도판결(게시물 화면 path '001', 목록 화면의 함수는 '007')은 /nboard/ 로 한 건씩 받아 확인했다
ATTACH_DIRS = {'003': 'https://file.scourt.go.kr/dcboard/', '001': 'https://file.scourt.go.kr/nboard/',
               '007': 'https://file.scourt.go.kr/nboard/'}
# 주요판결의 '법원 선택'(searchOption) 값. 게시물을 올린 법원이다
COURTS = {'서울고등법원': '000200', '대전고등법원': '000600', '대구고등법원': '000300', '부산고등법원': '000400', '광주고등법원': '000500',
          '수원고등법원': '000800', '특허법원': '000700', '서울중앙지방법원': '000210', '서울동부지방법원': '000211',
          '서울남부지방법원': '000212', '서울북부지방법원': '000213', '서울서부지방법원': '000215', '서울가정법원': '000230',
          '서울행정법원': '000220', '서울회생법원': '000221', '의정부지방법원': '000214', '인천지방법원': '000240', '인천가정법원': '000228',
          '수원지방법원': '000250', '수원가정법원': '000302', '수원회생법원': '000249', '춘천지방법원': '000260', '대전지방법원': '000280',
          '대전가정법원': '000286', '대전회생법원': '000291', '청주지방법원': '000270', '대구지방법원': '000310', '대구가정법원': '000318',
          '대구회생법원': '000321', '부산지방법원': '000410', '부산가정법원': '000413', '부산회생법원': '000443', '울산지방법원': '000411',
          '울산가정법원': '000477', '창원지방법원': '000420', '광주지방법원': '000510', '광주가정법원': '000515', '광주회생법원': '000543',
          '전주지방법원': '000520', '제주지방법원': '000530'}
# 화면 구조가 없는 응답에 이 말이 있으면 차단·확인 화면으로 보고 멈춘다. '제한'은 정상 화면(메뉴·본문)에도 있어 넣지 않는다
BLOCK_WORDS = ('자동입력', '보안문자', 'captcha', 'CAPTCHA', '비정상적인 접근', '접근이 차단', '접속이 차단', '과도한 요청', '이용이 제한')
COURT = (r'(?:대법원|특허법원|[가-힣]+(?:고등|지방|가정|행정|회생)법원(?:\s+[가-힣]+지원)?'
         r'|[가-힣]+(?:고법|지법|가정법원|행법|가법|회생법원)(?:\s+[가-힣]+지원)?)')
DATE = r'\d{4}\.\s*\d{1,2}\.\s*\d{1,2}\.?'
MORE = r'(?:\s*[,·]\s*(?:' + _system.CASE_NUMBER + r'|\d{1,7}(?!\d)))*'
SENTENCE = re.compile(r'(' + COURT + r')\s+(' + DATE + r')\s*선고\s+(' + _system.CASE_NUMBER + MORE + r')\s*(?:판결|결정)')
# 판결공보 요약본의 한 줄: '서울고법 2026. 7. 10. 선고 2025나208215, 208216 판결 〔매매대금반환⋅기타분양대금청구의소〕: 상고'
GONGBO = re.compile(r'(' + COURT + r')\s+(' + DATE + r')\s*선고\s+(' + _system.CASE_NUMBER + MORE + r')\s*(?:판결|결정)\s*'
                    r'〔([^〕]+)〕\s*[:：]\s*([가-힣]+)')


class ScourtError(Exception):
    """멈춤(상한·차단·robots·연결). 종료 코드 1."""


def home() -> Path:
    base = os.environ.get('SCOURT_HOME') or os.environ.get('LAWGO_HOME') or \
        Path(os.environ.get('LOCALAPPDATA') or Path.home() / '.local' / 'share') / '노동사건자동화'
    return Path(base) / '캐시' / 'scourt'


def write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    tmp.write_text(text, encoding='utf-8')
    tmp.replace(path)


def today() -> str:
    return datetime.now().strftime('%Y-%m-%d')


# ---------------------------------------------------------------- 요청(간격·상한·robots·멈춤)
CALLS = {'n': 0}


def _opener(url, data=None, timeout=60):
    """실제 요청. 시험은 이 함수를 바꿔 끼운다. (상태 코드, Content-Type, 바이트)를 돌려준다."""
    req = urllib.request.Request(url, data=data, headers={'User-Agent': UA, 'Referer': WWW + '/portal/main.jsp'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.headers.get('Content-Type', ''), r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get('Content-Type', '') if e.headers else '', e.read() if hasattr(e, 'read') else b''


OPEN = _opener


def _usage_path() -> Path:
    return home() / '사용량.json'


def stop_marker() -> Path:
    return home() / '중단.txt'


def usage() -> dict:
    p = _usage_path()
    try:
        u = json.loads(p.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        u = {}
    if u.get('date') != today():
        u = {'date': today(), 'count': 0, 'last': u.get('last', 0)}
    return u


def _stop(reason: str):
    write(stop_marker(), f'{datetime.now():%Y-%m-%d %H:%M:%S} {reason}\n'
                         '담당자가 누리집을 사람이 열어 확인한 뒤 이 파일을 지워야 scourt.py 가 다시 요청한다.\n')
    raise ScourtError('멈춤: ' + reason + f' (멈춤 표시: {stop_marker()})')


def _send(url, data=None):
    """멈춤 표시·하루 상한·간격을 지켜 한 건 보낸다(robots.txt 요청도 이것으로 보낸다). (상태, Content-Type, 바이트)."""
    if stop_marker().is_file():
        raise ScourtError('멈춤 표시가 있어 보내지 않는다: ' + stop_marker().read_text(encoding='utf-8', errors='replace').splitlines()[0])
    u = usage()
    if u['count'] >= DAILY_MAX:
        raise ScourtError(f"오늘 요청 {u['count']}건으로 하루 상한({DAILY_MAX})에 닿았다. 상한을 올리는 것은 담당자가 정한다")
    wait = u.get('last', 0) + DELAY - time.time()
    if wait > 0:
        time.sleep(wait)
    try:
        return OPEN(url, data)
    except (urllib.error.URLError, OSError) as e:
        raise ScourtError(f'연결 실패: {url.split("?")[0]} ({e})')
    finally:
        u['count'] += 1
        u['last'] = time.time()
        write(_usage_path(), json.dumps(u))
        CALLS['n'] += 1


def _request(url, data=None, expect=None):
    """robots.txt 가 허용한 주소만 _send 로 보내고 응답을 가린다. expect 는 정상 응답에 있어야 할 글자(HTML) 또는 'file'."""
    if not robots_allows(url):
        raise ScourtError('robots.txt 가 막은 주소라 보내지 않는다: ' + url.split('?')[0])
    status, ctype, body = _send(url, data)
    if status in (403, 429, 503):
        _stop(f'HTTP {status}: {url.split("?")[0]}')
    if status != 200:
        raise ScourtError(f'HTTP {status}: {url.split("?")[0]}')
    if expect == 'file':
        if 'text/html' in ctype.lower():
            t = body.decode('cp949', 'replace')
            if any(w in t for w in BLOCK_WORDS):
                _stop('파일 대신 확인 화면이 왔다: ' + url.split('?')[0])
            raise ScourtError('파일 대신 HTML 이 왔다: ' + url.split('?')[0])
        return body
    m = re.search(r'charset=([\w-]+)', ctype)
    enc = (m.group(1) if m else 'utf-8').lower()
    t = body.decode('cp949' if enc in ('euc-kr', 'euckr', 'ks_c_5601-1987', 'cp949') else enc, 'replace')
    if expect and expect not in t:
        if any(w in t for w in BLOCK_WORDS):
            _stop('차단·확인 화면이 왔다: ' + url.split('?')[0])
        raise ScourtError('예상한 화면이 아니다(구조가 바뀌었을 수 있다): ' + url.split('?')[0])
    return t


# ---------------------------------------------------------------- robots.txt(가장 긴 규칙, 같으면 Allow)
def parse_robots(text: str) -> list:
    """User-agent: * 묶음의 (allow, 경로) 목록. RFC 9309 처럼 가장 긴 규칙이 이기고 길이가 같으면 Allow 가 이긴다.
    파이썬 urllib.robotparser 는 적힌 순서로 판정해 'Disallow: /' 뒤의 Allow 를 보지 못한다(file.scourt.go.kr)."""
    rules, agents, in_rules = [], [], False
    for line in text.splitlines():
        line = line.split('#', 1)[0].strip()
        if ':' not in line:
            continue
        k, v = (x.strip() for x in line.split(':', 1))
        k = k.lower()
        if k == 'user-agent':
            if in_rules:
                agents, in_rules = [], False
            agents.append(v)
        elif k in ('allow', 'disallow'):
            in_rules = True
            if '*' in agents and v:
                rules.append((k == 'allow', v))
    return rules


def robots_decide(rules: list, path: str) -> bool:
    best = None
    for allow, p in rules:
        pat = re.escape(p).replace(r'\*', '.*')
        if p.endswith('$'):
            pat = re.escape(p[:-1]).replace(r'\*', '.*') + '$'
        if re.match(pat, path):
            if best is None or len(p) > len(best[1]) or (len(p) == len(best[1]) and allow):
                best = (allow, p)
    return True if best is None else best[0]


def robots_allows(url: str) -> bool:
    parts = urllib.parse.urlsplit(url)
    if parts.path == '/robots.txt':
        return True
    cache = home() / 'robots' / f'{parts.netloc}_{today()}.txt'
    if not cache.is_file():
        status, _, body = _send(f'{parts.scheme}://{parts.netloc}/robots.txt')
        if status in (403, 429, 503):
            _stop(f'HTTP {status}: {parts.netloc}/robots.txt')
        if status not in (200, 404):
            raise ScourtError(f'robots.txt 를 받지 못해 보내지 않는다: {parts.netloc} (HTTP {status})')
        text = body.decode('utf-8', 'replace') if status == 200 else ''      # 없으면(404) 막은 곳이 없다
        write(cache, text)
    path = parts.path + ('?' + parts.query if parts.query else '')
    return robots_decide(parse_robots(cache.read_text(encoding='utf-8')), path)


# ---------------------------------------------------------------- 글 다듬기
def plain(x: str) -> str:
    x = re.sub(r'<!--.*?-->', '', x, flags=re.S)
    x = re.sub(r'<script.*?</script>|<style.*?</style>', '', x, flags=re.S)
    x = re.sub(r'<br\s*/?>|</p>|</div>|</li>|</tr>|</h\d>', '\n', x)
    x = html.unescape(re.sub(r'<[^>]+>', ' ', x))
    x = re.sub(r'[ \t\xa0　]+', ' ', x)
    return re.sub(r'\n\s*\n+', '\n', x).strip()


def ymd(s: str) -> str:
    m = re.search(r'(\d{4})\s*[.\-]\s*(\d{1,2})\s*[.\-]\s*(\d{1,2})', s or '')
    return '%s-%02d-%02d' % (m.group(1), int(m.group(2)), int(m.group(3))) if m else ''


def numbers(s: str) -> list:
    """'2025나208215, 208216' 처럼 뒤 번호만 적은 것도 앞 번호의 연도·부호를 붙여 펼친다."""
    out, prev = [], None
    for part in re.split(r'\s*[,·]\s*', s or ''):
        m = CASE_NUMBER.search(part)
        if m:
            n = re.sub(r'\s', '', m.group(0))
            prev = re.match(r'(\d{2,4}[가-힣]+)', n).group(1)
            out.append(n)
        elif prev and re.fullmatch(r'\d{1,7}', part.strip()):
            out.append(prev + part.strip())
    return list(dict.fromkeys(out))


def board_of(name: str) -> str:
    n = re.sub(r'\s', '', name or '')
    if n in BOARDS or n in ('공보', '법고을'):
        return n
    if n in ALIASES:
        return ALIASES[n]
    raise SystemExit(f'알 수 없는 게시판: {name} (주요판결·판례속보·언론보도·공보·법고을)')


# ---------------------------------------------------------------- 법고을(법원도서관) 판례 검색
def parse_lx(t: str) -> tuple:
    """(전체 건수, 줄 목록). 줄: 법고을 번호·법원·선고일·사건번호·사건명·요지·상세 주소."""
    m = re.search(r'id="search_cnt_hidden" value="(\d+)"', t)
    total = int(m.group(1)) if m else 0
    rows = []
    # 줄 사이에 주석·빈 줄이 끼므로 줄 머리로 자른다(2026. 11. 11. 실제 화면에서 39건 가운데 첫 줄만 읽혔다)
    parts = re.split(r'<li class="search_result_item" id="(\d+)">', t)
    for ident, body in zip(parts[1::2], parts[2::2]):
        court = plain((re.search(r'<span class="ctg[^"]*">(.*?)</span>', body, re.S) or [None, ''])[1])
        title = plain((re.search(r'<a [^>]*showViewerPopup[^>]*>(.*?)</a>', body, re.S) or [None, ''])[1])
        s = re.match(r'(' + DATE + r')\s*선고\s+(.+?)\s+(?:판결|결정)\s*\[(.*)\]\s*$', title)
        summary = plain((re.search(r'<div class="txt_wrap"[^>]*>(.*?)</div>', body, re.S) or [None, ''])[1])
        rows.append({'id': ident, '기관': re.sub(r'\s+', ' ', court), '일자': ymd(s.group(1)) if s else '',
                     '사건번호': ', '.join(numbers(s.group(2))) if s else ', '.join(numbers(title)), '사건명': s.group(3).strip() if s else title,
                     '요지': '' if summary.startswith('요약정보가 존재하지 않습니다') else summary,
                     '링크': f'{LX}/search/detail/precedent/0/{ident}'})
    return total, rows


def search_lx(query: str, limit: int = 200) -> dict:
    rows, page, total = [], 1, None
    while len(rows) < limit:
        key = 'lx|%s|%d|%s' % (query, page, today())
        cache = home() / '목록' / (re.sub(r'[\\/:*?"<>| ]+', '_', key) + '.html')
        if cache.is_file():
            t = cache.read_text(encoding='utf-8')
        else:
            t = _request(LX_LIST.format(q=urllib.parse.quote(query), page=page), expect='search_cnt_hidden')
            write(cache, t)
        n, got = parse_lx(t)
        total = n if total is None else total
        new = [r for r in got if r['id'] not in {x['id'] for x in rows}]
        if not new:
            break
        rows += new
        if len(rows) >= total:
            break
        page += 1
    return {'게시판': '법고을', '검색어': query, '전체': total or 0, '받은건수': len(rows[:limit]), 'rows': rows[:limit]}


# ---------------------------------------------------------------- 목록
LIST44 = re.compile(r"<td class=\"mhid\">(\d+)</td>\s*<td class=\"tit\">\s*<a href=\"#\" onclick=\"fn_view\('(\d+)','(\d*)'\);"
                    r"return false;\">\s*(.*?)\s*</a>\s*</td>\s*<td>\s*(.*?)\s*</td>\s*<td class=\"attach mhid\">(.*?)</td>", re.S)
LISTNEWS = re.compile(r"<td class=\"mhid\">(\d+)</td>\s*(?:<td class=\"tit\">\s*</td>\s*)?<td class=\"tit\">\s*<a href='([^']*?seqnum=(\d+)[^']*)'"
                      r"\s*>\s*(.*?)\s*</a>\s*</td>\s*<td class=\"mhid\">\s*(.*?)\s*</td>\s*<td>\s*([\d-]+)\s*</td>\s*<td class=\"attach mhid\">(.*?)</td>", re.S)


def parse_list(board: str, t: str) -> tuple:
    """(전체 건수, 마지막 쪽, 줄 목록)."""
    rows = []
    if board == '주요판결':
        for no, seq, code, title, court, att in LIST44.findall(t):
            rows.append({'번호': int(no), 'seqnum': seq, '법원코드': code, '제목': plain(title), '게시': plain(court), '게시일': '',
                         '첨부있음': 'attfile' in att})
        m = re.search(r'총\s*([\d,]+)\s*건', t)
        total = int(m.group(1).replace(',', '')) if m else (rows[0]['번호'] if rows else 0)
    else:
        for no, _href, seq, title, author, day, att in LISTNEWS.findall(t):
            rows.append({'번호': int(no), 'seqnum': seq, '법원코드': '', '제목': plain(title), '게시': plain(author), '게시일': day,
                         '첨부있음': 'attfile' in att})
        total = rows[0]['번호'] if rows else 0        # 번호는 검색 결과 안에서 내려 센다
    # 마지막 쪽: '총 17건 (1/2page)'의 2, '마지막 페이지' 단추, 건수 ÷ 10 가운데 큰 것. 쪽이 적으면 '마지막 페이지' 단추가 없다
    # (2026. 11. 11. 주요판결 '강등' 17건에서 첫 쪽 10건만 받은 일)
    pages = [int(x) for x in re.findall(r'fn_egov_select_brdMstr\((\d+)\);return false; " title="마지막', t)]
    pages += [int(x) for x in re.findall(r'총\s*[\d,]+\s*건\s*\(\s*\d+\s*/\s*(\d+)\s*page', t)]
    pages.append(-(-total // LIST_ROWS) if rows else 0)
    return total, max(pages), rows


# 대법원 사건부호(상고·재항고·특별항고). 법원 표시가 없는 글(언론보도판결)은 사건번호로 심급을 매긴다
SUPREME_TYPES = ('다카', '재다', '재두', '재도', '다', '두', '도', '므', '스', '마', '그', '모', '브', '추', '수', '우', '트')


def level(court: str, number: str) -> str:
    if court:
        return '대법원' if court == '대법원' else '하급심'
    m = re.match(r'\d{2,4}\s?([가-힣]+)', number or '')
    if not m:
        return ''
    return '대법원' if m.group(1) in SUPREME_TYPES else '하급심'


def list_page(board: str, query: str, page: int, court: str = '', typ: str = '') -> str:
    b = BOARDS[board]
    key = '%s|%s|%s|%s|%d|%s' % (board, query, court, typ, page, today())
    cache = home() / '목록' / (re.sub(r'[\\/:*?"<>| ]+', '_', key) + '.html')
    if cache.is_file():
        return cache.read_text(encoding='utf-8')
    if board == '주요판결':
        data = {'pageSize': '5', 'pageIndex': str(page), 'seqnum': '0', 'cbub_code': '', 'searchOption': court, 'searchWord': query}
    else:
        data = {'searchOption': '', 'pageIndex': str(page), 'pageSize': '5', 'searchWord': query}
        if board == '판례속보':
            data['type'] = typ or b['type']
    body = urllib.parse.urlencode({k: v.encode('cp949', 'replace') for k, v in data.items()}).encode('ascii')
    t = _request(WWW + b['list'], body, expect='tableHor')
    write(cache, t)
    return t


def search(board: str, query: str, limit: int = 200, court: str = '', typ: str = '') -> dict:
    board = board_of(board)
    if court and board == '주요판결':
        code = COURTS.get(re.sub(r'\s', '', court))
        if not code:
            raise SystemExit(f'주요판결의 법원 선택에 없는 법원: {court} (가능: {", ".join(COURTS)})')
        court = code
    elif court:
        court = ''                        # 다른 게시판은 법원으로 거르지 않는다
    rows, seen, total, last, page = [], set(), 0, 1, 1
    while page <= last and len(rows) < limit:
        total_p, last_p, got = parse_list(board, list_page(board, query, page, court, typ))
        if page == 1:
            total, last = total_p, last_p
        new = [r for r in got if r['seqnum'] not in seen]
        if not new:
            break
        if board == '주요판결':
            remember_codes(new)
        for r in new:
            seen.add(r['seqnum'])
            rows.append(r)
        page += 1
    return {'게시판': board, '검색어': query, '전체': total, '받은건수': len(rows[:limit]), 'rows': rows[:limit]}


# ---------------------------------------------------------------- 게시물
def view_url(board: str, seq: str, code: str = '') -> str:
    return WWW + BOARDS[board]['view'].format(seq=seq, code=code or '')


def parse_view(board: str, t: str, seq: str = '', code: str = '') -> dict:
    i = t.find('<table class="tableVer"')
    seg = t[i:t.find('</table>', i)] if i >= 0 else ''
    cells = {plain(a): b for a, b in re.findall(r'<th[^>]*>\s*(.*?)\s*</th>\s*<td[^>]*>(.*?)</td>', seg, re.S)}
    title = plain(cells.get('제목', ''))
    m = re.search(r"form\.path\.value\s*=\s*'(\d+)'", t)
    path = m.group(1) if m else ''
    attach = []
    att_html = cells.get('첨부파일', '')
    for url, name in re.findall(r'<a href="(https?://[^"]+)"[^>]*>\s*([^<]+?)\s*</a>', att_html):
        attach.append({'이름': html.unescape(name), '주소': url})
    for f, name in re.findall(r"download\('([^']*)','([^']*)'\)", att_html):
        base = ATTACH_DIRS.get(path)
        attach.append({'이름': html.unescape(name), '주소': (base + urllib.parse.quote(f)) if base else '',
                       **({} if base else {'사유': f"첨부 path '{path}' 의 허용 폴더를 모른다. 사람이 화면에서 받는다"})})
    k = seg.find('class="contArea"')
    body = plain(seg[k + len('class="contArea">'):]) if k >= 0 else ''
    doc = {'게시판': board, 'seqnum': seq, '법원코드': code, '제목': title, '게시': plain(cells.get('작성자', '')),
           '게시일': ymd(plain(cells.get('작성일', ''))), '첨부': attach, '요지': body, '링크': view_url(board, seq, code)}
    doc.update(case_info(board, title, body, [a['이름'] for a in attach]))
    return doc


def case_info(board: str, title: str, body: str, names=()) -> dict:
    """게시물의 판결 표시(법원·선고일·사건번호). 본문 머리의 '○ 법원 날짜 선고 번호 판결'이 먼저이다.
    공보 요약본은 여러 판결을 늘어놓은 글이므로 판결 하나로 적지 않는다(사건은 `공보` 색인이 줄마다 갖는다)."""
    if '공보 요약본' in title or '공보요약본' in title:
        return {'기관': '', '일자': '', '사건번호': ''}
    first = next((x for x in body.splitlines() if x.strip()), '')
    court, day = '', ''
    t = re.search(r'\[(대법원)\s+(' + DATE + r')\s*선고', title)     # 판례속보: '…사건[대법원 2026. 10. 30. 선고 중요판결]'
    if t:
        court, day = t.group(1), ymd(t.group(2))
    else:
        # 주요판결 본문 첫 줄 '○ 전주지방법원 남원지원 2026. 10. 8. 선고 2026가합1002 판결'. 본문 뒤쪽은 다른 판결을 인용하므로 보지 않는다
        m = SENTENCE.search(first) or SENTENCE.search(title)
        if m:
            return {'기관': re.sub(r'\s+', ' ', m.group(1)), '일자': ymd(m.group(2)), '사건번호': ', '.join(numbers(m.group(3)))}
    nums = numbers(first.split('(')[0]) if board == '판례속보' else []
    if not nums:
        p = re.findall(r'\(([^()]*)\)\s*$', title)
        nums = numbers(p[-1]) if p else []
        if p and not court:
            c = re.match(r'\s*(' + COURT + r'|[가-힣]+지원)\s', p[-1])
            court = c.group(1) if c else ''
    if not nums:
        for n in names:
            nums += numbers(n)
            if not court:
                c = re.search(COURT, n.replace('_', ' '))
                court = c.group(0) if c else ''
    return {'기관': court, '일자': day, '사건번호': ', '.join(dict.fromkeys(nums))}


def _codes_path() -> Path:
    return home() / '주요판결_법원코드.json'


def remember_codes(rows):
    """주요판결 게시물을 GET 주소로 열려면 올린 법원의 코드가 필요하다. 목록에서 본 것을 적어 두고 show·get 이 쓴다."""
    new = {r['seqnum']: r['법원코드'] for r in rows if r.get('법원코드')}
    if not new:
        return
    try:
        codes = json.loads(_codes_path().read_text(encoding='utf-8'))
    except (OSError, ValueError):
        codes = {}
    if any(codes.get(k) != v for k, v in new.items()):
        codes.update(new)
        write(_codes_path(), json.dumps(codes))


def view(board: str, seq: str, code: str = '', refresh: bool = False) -> dict:
    board = board_of(board)
    if board == '주요판결' and not code:
        try:
            code = json.loads(_codes_path().read_text(encoding='utf-8')).get(seq, '')
        except (OSError, ValueError):
            code = ''
    cache = home() / '게시물' / f'{BOARDS[board]["gubun"]}_{seq}.html'
    if cache.is_file() and not refresh:
        t = cache.read_text(encoding='utf-8')
    else:
        t = _request(view_url(board, seq, code), expect='tableVer')
        write(cache, t)
    return parse_view(board, t, seq, code)


# ---------------------------------------------------------------- 첨부 판결문과 글
def fetch_file(url: str) -> Path:
    name = urllib.parse.unquote(urllib.parse.urlsplit(url).path.rsplit('/', 1)[-1])
    cache = home() / '파일' / name
    if not cache.is_file():
        data = _request(url, expect='file')
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(data)
    return cache


def hwpx_text(path: Path) -> str:
    out = []
    with zipfile.ZipFile(path) as z:
        for n in sorted(x for x in z.namelist() if re.match(r'Contents/section\d+\.xml$', x)):
            xml = z.read(n).decode('utf-8', 'replace')
            for p in re.findall(r'<hp:p\b.*?</hp:p>', xml, re.S):
                line = ''.join(html.unescape(x) for x in re.findall(r'<hp:t\b[^>]*>(.*?)</hp:t>', p, re.S))
                out.append(re.sub(r'<[^>]+>', '', line))
    return re.sub(r'\n{3,}', '\n\n', '\n'.join(out)).strip()


def pdf_text(path: Path) -> tuple:
    """(글, 출처). 글자층이 면마다 거의 없으면 Windows 문자인식으로 읽는다."""
    import pymupdf
    doc = pymupdf.open(str(path))
    pages = [p.get_text() for p in doc]
    if sum(len(x.strip()) for x in pages) >= 40 * max(1, doc.page_count):
        return '\n'.join(f'[{i}면]\n{x.strip()}' for i, x in enumerate(pages, 1)), '글자층'
    got = ocr_pdf(doc)
    if got is None:
        return '', '글자 없음(문자인식 실패: 한국어 문자인식이 없거나 PowerShell 을 쓸 수 없다)'
    return got, '문자인식(원본 PDF 와 맞대어 옮긴다)'


def ocr_pdf(doc):
    import pymupdf
    if not OCR_PS1.is_file():
        return None
    work = Path(tempfile.mkdtemp(prefix='scourt_ocr_'))
    try:
        for i, p in enumerate(doc, 1):
            z = 2300 / max(p.rect.width, p.rect.height)
            p.get_pixmap(matrix=pymupdf.Matrix(z, z)).save(str(work / f'p{i:03d}.png'))
        r = subprocess.run(['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(OCR_PS1),
                            '-Dir', str(work), '-Filter', '*.png', '-Out', 'ocr.json'], capture_output=True, timeout=3600)
        j = work / 'ocr.json'
        if r.returncode or not j.is_file():
            return None
        data = json.loads(j.read_text(encoding='utf-8-sig'))
        data = [data] if isinstance(data, dict) else data
        out = []
        for e in sorted(data, key=lambda x: x['file']):
            ls = e.get('lines') or []
            ls = [ls] if isinstance(ls, dict) else ls
            ls = sorted(ls, key=lambda l: (round(l['y'] / 12), l['x']))
            out.append(f"[{int(re.search(r'(\d+)', e['file']).group(1))}면]\n" + '\n'.join(l['t'] for l in ls))
        return '\n'.join(out)
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return None
    finally:
        shutil.rmtree(work, ignore_errors=True)


def judgment_text(doc: dict, folder: Path) -> dict:
    """게시물의 첨부를 받아 사건 폴더의 판결문/ 에 두고 글을 뽑는다. PDF 의 글자층 → hwpx → 문자인식 순서."""
    got = {'원본': [], '글': '', '글출처': '', '실패': []}
    pdfs = [a for a in doc['첨부'] if a.get('주소') and a['이름'].lower().endswith('.pdf')]
    hwpxs = [a for a in doc['첨부'] if a.get('주소') and a['이름'].lower().endswith('.hwpx')]
    for a in doc['첨부']:
        if not a.get('주소'):
            got['실패'].append(f"{a['이름']}: {a.get('사유', '주소 없음')}")
    saved = {}
    for a in pdfs + hwpxs:
        try:
            src = fetch_file(a['주소'])
        except ScourtError as e:
            if str(e).startswith('멈춤'):
                raise
            got['실패'].append(f"{a['이름']}: {e}")
            continue
        dest = folder / '판결문' / re.sub(r'[\\/:*?"<>|]+', '_', a['이름'])
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.is_file():
            shutil.copy2(src, dest)
        saved[a['이름']] = dest
        got['원본'].append(str(dest.relative_to(folder)).replace('\\', '/'))
    for a in pdfs:
        if a['이름'] in saved:
            text, how = pdf_text(saved[a['이름']])
            if text and how == '글자층':
                got['글'], got['글출처'] = text, f"글자층({a['이름']})"
                return got
            if text and not got['글']:
                got['글'], got['글출처'] = text, f"{how}({a['이름']})"
    for a in hwpxs:                     # PDF 에 글자층이 없으면 hwpx 의 글이 문자인식보다 낫다
        if a['이름'] in saved:
            t = hwpx_text(saved[a['이름']])
            if t:
                got['글'], got['글출처'] = t, f"hwpx({a['이름']})"
                return got
    return got


def markdown(doc: dict, text: dict | None = None) -> str:
    head = ' '.join(x for x in (doc.get('기관'), doc.get('일자'), doc.get('사건번호'), doc.get('제목')) if x)
    lines = [f"## [{doc['게시판']}] {head}", '',
             f"- 게시판: {BOARDS[doc['게시판']]['name']} (seqnum {doc['seqnum']}, 게시 {doc.get('게시') or '-'} {doc.get('게시일') or ''})".rstrip(),
             f"- 링크: {doc['링크']}"]
    for a in doc.get('첨부', []):
        lines.append(f"- 첨부: {a['이름']} {a.get('주소') or '(' + a.get('사유', '주소 없음') + ')'}")
    if doc.get('검색어'):
        lines.append(f"- 검색어: {doc['검색어']}")
    if text:
        if text['원본']:
            lines.append('- 원본: ' + ', '.join(text['원본']))
        lines.append('- 글 출처: ' + (text['글출처'] or '없음'))
        for f in text['실패']:
            lines.append('- 받지 못함: ' + f)
    if doc.get('요지'):
        lines += ['', '### 게시판 본문(법원·법원도서관이 쓴 요지. 판결의 판단이 아니다)', '', doc['요지']]
    if text and text['글']:
        lines += ['', '### 판결문', '', text['글']]
    return '\n'.join(lines) + '\n'


# ---------------------------------------------------------------- 각급법원 판결공보 요약본 색인
def gongbo_index_path() -> Path:
    return home() / '공보색인.json'


def parse_gongbo(body: str) -> list:
    out = []
    for m in GONGBO.finditer(body):
        for n in numbers(m.group(3)):
            out.append({'기관': re.sub(r'\s+', ' ', m.group(1)), '일자': ymd(m.group(2)), '사건번호': n,
                        '사건명': m.group(4).strip(), '확정': m.group(5)})
    return out


def build_gongbo(limit: int = 300, start_year: int = 0) -> dict:
    idx_path = gongbo_index_path()
    try:
        idx = json.loads(idx_path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        idx = {'게시물': {}}
    done, page, last, fetched = idx['게시물'], 1, 1, 0
    stop_old = False
    while page <= last and fetched < limit and not stop_old:
        total, last_p, rows = parse_list('판례속보', list_page('판례속보', '', page, typ='1'))
        last = last_p if page == 1 else last
        if not rows:
            break
        for r in rows:
            if '각급법원' not in r['제목']:
                continue
            if start_year and r['게시일'][:4].isdigit() and int(r['게시일'][:4]) < start_year:
                stop_old = True
                break
            if r['seqnum'] in done or fetched >= limit:
                continue
            d = view('판례속보', r['seqnum'])
            fetched += 1
            done[r['seqnum']] = {'제목': d['제목'], '게시일': d['게시일'], '링크': d['링크'], '첨부': d['첨부'],
                                 '사건': parse_gongbo(d['요지'])}
        page += 1
    idx['만든날'] = today()
    write(idx_path, json.dumps(idx, ensure_ascii=False, indent=1))
    cases = sum(len(v['사건']) for v in done.values())
    return {'색인': str(idx_path), '게시물': len(done), '사건': cases, '이번에 받은 게시물': fetched,
            '사건 목록이 없는 게시물': sum(1 for v in done.values() if not v['사건'])}


def gongbo_lookup(nos) -> list:
    """사건번호로 공보 색인을 찾는다(확정·항소·상고 표시). 누리집에 요청하지 않는다."""
    try:
        idx = json.loads(gongbo_index_path().read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return []
    want = {re.sub(r'\s', '', n) for n in nos}
    return [dict(c, 게시물=post['제목'], 링크=post['링크']) for post in idx.get('게시물', {}).values() for c in post['사건']
            if c['사건번호'] in want]


def gongbo_rows(queries) -> tuple:
    try:
        idx = json.loads(gongbo_index_path().read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None, []
    rows, searches = {}, []
    for q in queries:
        qs = re.sub(r'\s', '', q)
        n = 0
        for seq, post in idx.get('게시물', {}).items():
            for c in post['사건']:
                if qs and qs in re.sub(r'\s', '', c['사건명']):
                    key = (c['기관'], c['사건번호'])
                    rows.setdefault(key, {'종류': '공보', 'id': 'gongbo-' + c['사건번호'], '제목': c['사건명'], '사건번호': c['사건번호'],
                                          '일자': c['일자'], '기관': c['기관'], '확정': c['확정'], '게시물': post['제목'],
                                          '링크': post['링크'], '첨부': post['첨부'], '_q': []})
                    if q not in rows[key]['_q']:
                        rows[key]['_q'].append(q)
                    n += 1
        searches.append({'검색어': q, '전체': n, '받은건수': n})
    return searches, list(rows.values())


# ---------------------------------------------------------------- 수확
def harvest(queries, boards=('주요판결', '판례속보', '언론보도', '공보', '법고을'), *, court='', limit=200, views=40, texts=0, out=None) -> dict:
    """게시판마다 검색어별 목록을 합치고(같은 글은 하나로), 여러 검색어에 걸린 것 → 전체 건수가 적은 검색어에 걸린 것 → 최신 순으로
    줄 세운다(법제처 harvest 와 같은 순서). 앞의 views 건은 게시물을 열어 제목 전문·사건번호·요지·첨부를 채우고, 앞의 texts 건은
    첨부 판결문을 받아 글을 뽑는다."""
    start = CALLS['n']
    listing, summary = {}, {}
    folder = Path(out) if out else None
    for b in boards:
        b = board_of(b)
        if b == '공보':
            searches, rows = gongbo_rows(queries)
            if searches is None:
                summary[b] = {'안내': '공보 색인이 없다. `scourt.py 공보` 로 먼저 만든다'}
                continue
            rows.sort(key=lambda r: r['일자'], reverse=True)
            rows.sort(key=lambda r: -len(r['_q']))
            for r in rows:
                r['검색어'] = ' / '.join(r.pop('_q'))
            listing[b] = {'검색': searches, 'rows': rows, '인용순위': []}
            summary[b] = {'검색': searches, '합친건수': len(rows),
                          '확정': sum(1 for r in rows if r['확정'] == '확정'), '안내': '사건명에서 찾은 각급법원 판결공보 사건. 판결문은 법제처(각급법원 판결공보)나 담당자가 받는다'}
            continue
        if b == '법고을':
            merged, origin, searches, totals = {}, {}, [], {}
            for q in queries:
                res = search_lx(q, limit=limit)
                searches.append({'검색어': q, '전체': res['전체'], '받은건수': res['받은건수']})
                totals[q] = res['전체']
                for r in res['rows']:
                    merged.setdefault(r['id'], r)
                    origin.setdefault(r['id'], [])
                    if q not in origin[r['id']]:
                        origin[r['id']].append(q)
            order = sorted(merged, key=lambda k: merged[k]['일자'], reverse=True)
            order.sort(key=lambda k: (-len(origin[k]), min(totals[q] for q in origin[k])))
            rows = [{'종류': b, 'id': 'lx-' + k, '제목': merged[k]['사건명'], '사건번호': merged[k]['사건번호'], '일자': merged[k]['일자'],
                     '기관': merged[k]['기관'], '검색어': ' / '.join(origin[k]), '링크': merged[k]['링크'], '요지': merged[k]['요지'][:600],
                     '심급': level(merged[k]['기관'], merged[k]['사건번호']), '상세': True} for k in order]
            listing[b] = {'검색': searches, 'rows': rows, '인용순위': []}
            summary[b] = {'검색': searches, '합친건수': len(rows), '하급심': sum(1 for r in rows if r['심급'] == '하급심'),
                          '대법원': sum(1 for r in rows if r['심급'] == '대법원'),
                          '안내': '법제처와 같은 법원도서관 판례 자료이다. 법제처 목록과 겹치는 번호는 다시 훑기에서 한 줄로 합친다'}
            continue
        merged, origin, searches, totals = {}, {}, [], {}
        for q in queries:
            res = search(b, q, limit=limit, court=court)
            searches.append({'검색어': q, '전체': res['전체'], '받은건수': res['받은건수']})
            totals[q] = res['전체']
            for r in res['rows']:
                merged.setdefault(r['seqnum'], r)
                origin.setdefault(r['seqnum'], [])
                if q not in origin[r['seqnum']]:
                    origin[r['seqnum']].append(q)
        order = sorted(merged, key=lambda k: int(k), reverse=True)              # 글 번호가 클수록 새 글이다
        order.sort(key=lambda k: (-len(origin[k]), min(totals[q] for q in origin[k])))
        rows, docs, failed = [], [], []
        for n, k in enumerate(order):
            r = merged[k]
            row = {'종류': b, 'id': f"{BOARDS[b]['gubun']}-{k}", 'seqnum': k, '제목': r['제목'], '사건번호': '', '일자': '',
                   '기관': r['게시'] if b == '주요판결' else '', '게시일': r['게시일'], '검색어': ' / '.join(origin[k]),
                   '링크': view_url(b, k, r['법원코드']), '상세': False}
            if n < views:
                try:
                    d = view(b, k, r['법원코드'])
                except ScourtError as e:
                    if str(e).startswith('멈춤') or '상한' in str(e) or 'robots' in str(e):
                        raise
                    failed.append({'seqnum': k, '사유': str(e)})
                else:
                    row.update({'제목': d['제목'], '사건번호': d['사건번호'], '일자': d['일자'], '기관': d['기관'] or row['기관'],
                                '게시일': d['게시일'], '첨부': d['첨부'], '요지': d['요지'][:600], '상세': True})
                    if len(docs) < texts and d['첨부']:
                        docs.append(dict(d, 검색어=row['검색어']))
            row['심급'] = level(row['기관'] if (row['상세'] or b == '주요판결') else '', row['사건번호'])
            if b == '주요판결' and not row['심급']:
                row['심급'] = '하급심'                  # 각급법원이 올리는 게시판이다
            rows.append(row)
        texts_out = []
        if folder and docs:
            for d in docs:
                try:
                    texts_out.append((d, judgment_text(d, folder)))
                except ScourtError as e:
                    if str(e).startswith('멈춤') or '상한' in str(e):
                        raise
                    failed.append({'seqnum': d['seqnum'], '사유': str(e)})
            write(folder / f'법원_본문_{b}.md', f'# 법원 누리집 {BOARDS[b]["name"]} 판결문 {len(texts_out)}건\n\n'
                  + '\n'.join(markdown(d, t) for d, t in texts_out))
        listing[b] = {'검색': searches, 'rows': rows, '인용순위': []}
        summary[b] = {'검색': searches, '합친건수': len(rows), '상세': sum(1 for r in rows if r['상세']),
                      '하급심': sum(1 for r in rows if r['심급'] == '하급심'), '대법원': sum(1 for r in rows if r['심급'] == '대법원'),
                      '심급 모름': sum(1 for r in rows if not r['심급']), '본문': len(texts_out), '본문실패': failed}
        if texts_out:
            summary[b]['본문목록'] = [' '.join(x for x in (d.get('기관'), d.get('사건번호'), t['글출처'][:12]) if x) for d, t in texts_out]
    if folder:
        write(folder / '법원_목록.json', json.dumps(listing, ensure_ascii=False, indent=2))
    return {'목록파일': str(folder / '법원_목록.json') if folder else None, '호출': CALLS['n'] - start, '게시판별': summary,
            '주의': '게시판은 법원·법원도서관이 고른 판결만 싣는다. 여기서 찾지 못한 것을 근거로 판례가 없다고 쓰지 않는다',
            **({} if folder else {'목록': listing})}


# ---------------------------------------------------------------- 명령
def _out_ok(p, out):
    if out and os.path.splitext(out.rstrip('/\\'))[1].lower() in 파일_꼴:
        p.error(f'--out 은 폴더 이름이다({out}). 확장자 없이 폴더를 준다')


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    subs = p.add_subparsers(dest='cmd', required=True)
    s = subs.add_parser('harvest', help='여러 검색어로 게시판들을 훑어 법원_목록.json 을 쓴다')
    s.add_argument('--query', action='append', required=True, help='제목에서 찾을 글자열(여러 번)')
    s.add_argument('--boards', default='주요판결,판례속보,언론보도,공보,법고을')
    s.add_argument('--court', default='', help='주요판결만: 게시한 법원(예: 서울행정법원)')
    s.add_argument('--limit', type=int, default=200, help='게시판·검색어마다 받을 목록 줄 수')
    s.add_argument('--views', type=int, default=40, help='게시판마다 열어 볼 게시물 수(순위 앞에서부터)')
    s.add_argument('--texts', type=int, default=0, help='게시판마다 첨부 판결문을 받을 게시물 수')
    s.add_argument('--out', help='{사건}/라운드N/작업/법원')
    s = subs.add_parser('search', help='게시판 하나를 검색어 하나로 찾는다(목록만)')
    s.add_argument('board'); s.add_argument('query'); s.add_argument('--limit', type=int, default=50); s.add_argument('--court', default='')
    s = subs.add_parser('show', help='게시물 하나를 연다')
    s.add_argument('board'); s.add_argument('seqnum'); s.add_argument('--code', default='', help='주요판결의 법원코드(목록의 법원코드)')
    s.add_argument('--refresh', action='store_true'); s.add_argument('--out')
    s = subs.add_parser('get', help='게시물의 첨부 판결문을 받아 글을 뽑는다')
    s.add_argument('board'); s.add_argument('seqnum', nargs='+'); s.add_argument('--out', required=True)
    s.add_argument('--code', default='', help='주요판결의 법원코드(목록에서 본 게시물은 기억해 둔 값을 쓴다)')
    s = subs.add_parser('공보', help='각급법원(제1,2심) 판결공보 요약본 색인을 만들거나 잇는다')
    s.add_argument('--limit', type=int, default=300, help='이번에 열 게시물 수'); s.add_argument('--from', dest='start', type=int, default=0, help='이 해 이후 게시물만')
    s = subs.add_parser('공보찾기', help='하급심 사건번호를 공보 색인에서 찾는다(확정·항소·상고 표시, 요청 없음)')
    s.add_argument('number', nargs='+')
    subs.add_parser('usage', help='오늘 보낸 요청 수와 멈춤 표시')
    a = p.parse_args(argv)
    _out_ok(p, getattr(a, 'out', None))
    try:
        if a.cmd == 'harvest':
            r = harvest(a.query, [x for x in a.boards.split(',') if x.strip()], court=a.court, limit=a.limit, views=a.views,
                        texts=a.texts, out=a.out)
            if not a.out:
                for b, v in r.get('목록', {}).items():
                    v['rows'] = v['rows'][:20]
            print(json.dumps(r, ensure_ascii=False, indent=1))
        elif a.cmd == 'search':
            r = search_lx(a.query, limit=a.limit) if board_of(a.board) == '법고을' else search(a.board, a.query, limit=a.limit, court=a.court)
            print(json.dumps(r, ensure_ascii=False, indent=1))
        elif a.cmd == 'show':
            d = view(a.board, a.seqnum, a.code, a.refresh)
            text = markdown(d)
            if a.out:
                write(Path(a.out) / f"법원_게시물_{d['게시판']}_{a.seqnum}.md", text)
                print('씀:', Path(a.out) / f"법원_게시물_{d['게시판']}_{a.seqnum}.md")
            else:
                print(text)
        elif a.cmd == 'get':
            folder = Path(a.out)
            parts = []
            for seq in a.seqnum:
                d = view(a.board, seq, a.code)
                t = judgment_text(d, folder)
                parts.append(markdown(d, t))
                print(f"{d['게시판']} {seq}: {d.get('기관')} {d.get('사건번호')} — {t['글출처'] or '글 없음'}"
                      + (f" / 받지 못함 {len(t['실패'])}" if t['실패'] else ''))
            b = board_of(a.board)
            path = folder / f'법원_본문_{b}.md'
            old = path.read_text(encoding='utf-8') if path.is_file() else f'# 법원 누리집 {BOARDS[b]["name"]} 판결문\n\n'
            write(path, old + '\n'.join(x for x in parts if x.split('\n', 1)[0] not in old))
            print('씀:', path)
        elif a.cmd == '공보':
            print(json.dumps(build_gongbo(a.limit, a.start), ensure_ascii=False, indent=1))
        elif a.cmd == '공보찾기':
            got = gongbo_lookup(a.number)
            print(json.dumps({'찾음': got, '없음': [n for n in a.number if re.sub(r'\s', '', n) not in {g['사건번호'] for g in got}],
                              '안내': '색인은 공보에 실린 하급심만 갖는다. 없다고 확정 여부를 단정하지 않는다'}, ensure_ascii=False, indent=1))
        elif a.cmd == 'usage':
            u = usage()
            print(json.dumps({'날짜': u['date'], '오늘 요청': u['count'], '하루 상한': DAILY_MAX,
                              '멈춤 표시': stop_marker().read_text(encoding='utf-8', errors='replace').strip() if stop_marker().is_file() else '없음'},
                             ensure_ascii=False, indent=1))
    except ScourtError as e:
        print(str(e), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
