"""호증(자료)을 모든 면 읽었는지 기록하고 기계로 확인한다 — 증거 '파악'의 관문(`.claude/commands/증거정리.md` 3단계).

    python -B 4_서면작성/scripts/evidence_read.py make  "<사건 폴더>" [--호증 사6 노 ...] [--no-ocr] [--no-text]
    python -B 4_서면작성/scripts/evidence_read.py make  "<사건 폴더>" --다시 사6        # 파일이 바뀐 호증의 기록을 새로 짠다
    python -B 4_서면작성/scripts/evidence_read.py check "<사건 폴더>" [--호증 ...]
    python -B 4_서면작성/scripts/evidence_read.py make  "1_검토의견/사건/{의뢰인}_{검토내용}" --자료 "<첨부 폴더>"   # 호증 번호 없는 자료

make  서면 사건은 호증마다(우리·상대, PDF 가 아닌 원자료 포함) `증거관리/호증읽기/{호증키}.md` 틀을 만든다. 틀에는 파일·해시·단위 수와
      단위마다 빈 줄(PDF·그림은 '- 3면:', 압축파일은 '- [파일] 이름:', 엑셀은 '- [시트] 이름:', 그 밖은 '- 전체:')이 있다.
      PDF 는 면별 글(글자층, 없거나 깨지면 Windows 문자인식)을 `증거관리/호증글자/{호증키}.txt` 에 낸다.
      `--자료` 를 주면 그 폴더의 파일마다 `작업/자료읽기/{파일 이름}.md` 와 `작업/자료글자/{파일 이름}.txt` 를 만든다.
      호증 번호를 다시 매겨 기록의 호증키와 파일이 어긋나면, 해시가 같은 파일의 호증키로 기록을 옮긴다.
check 모든 호증(자료)에 기록이 있는지, 기록한 뒤 파일이 바뀌지 않았는지(해시), 모든 단위가 채워졌는지, '읽은 방식'과
      '쟁점에 닿는 문구'가 적혔는지 본다. 하나라도 어긋나면 종료 코드 1 이다.

작성 세션은 면별 글과 그림으로 모든 면을 읽고 면마다 그 면에 무엇이 있는지 적는다. 같은 꼴의 면(일자별 문자, 월별 대장)은
'- 5~9면:' 처럼 묶을 수 있으나 면마다 다른 것(날짜·대상·문구)을 함께 적는다. '같음', '반복', '…' 만 적은 줄은 빈 줄로 센다.
이 도구는 칸이 채워졌는지만 본다. 읽은 내용이 맞는지는 판정하지 않는다.

2026. 11. 2. GGM 정직 3월: 사 제6호증(38면, 글자층 없음)을 첫 면만 읽고 '반복 기재'로 요약하여 3면의 쟁점 문구를 답변서(1)·(2)와
그 뒤의 자체 재검토에서 모두 놓친 일로 만들었다. 담당 노무사 "노동사건자동화는 결국 문체, 증거, 판례 세 가지에 어떠한 하자도
없어야", "증거(편철, 파악, 이해 등 모든 걸 포함)".
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import os
import re
import sys
import unicodedata
import zipfile
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

_spec = importlib.util.spec_from_file_location('evidence_cite_review', Path(__file__).resolve().parent / 'evidence_cite_review.py')
_ecr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_ecr)

IMAGE = ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tif', '.tiff', '.heic', '.webp')
DOCS = IMAGE + ('.pdf', '.zip', '.xlsx', '.xlsm', '.xls', '.docx', '.doc', '.hwp', '.hwpx', '.pptx', '.txt', '.csv',
                '.msg', '.eml', '.mp3', '.m4a', '.wav', '.mp4', '.mov')
빈말 = {'', '-', '…', '...', '같음', '동일', '위와 같음', '위와같음', '반복', '반복 기재', '생략', '확인', '확인 필요', '내용 확인 필요'}
면_줄 = re.compile(r'^-\s*(\d+)\s*(?:~\s*(\d+)\s*)?면\s*:\s*(.*)$')
단위_줄 = re.compile(r'^-\s*\[(파일|시트)\]\s*(.+?)\s*:\s*(.*)$')
전체_줄 = re.compile(r'^-\s*전체\s*:\s*(.*)$')


def nfc(s: str) -> str:
    return unicodedata.normalize('NFC', s)


def 해시(p: Path) -> str:
    h = hashlib.sha1()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()[:12]


def 호증_정렬(k: str):
    m = re.match(r'(\D+)(\d+)(?:-(\d+))?$', k)
    return (m.group(1), int(m.group(2)), int(m.group(3) or 0)) if m else (k, 0, 0)


def 호증_표시(k: str) -> str:
    m = re.match(r'(\D+)(\d+)(?:-(\d+))?$', k)
    return f'{m.group(1)} 제{m.group(2)}호증' + (f'의{m.group(3)}' if m.group(3) else '') if m else k


def 단위들(p: Path) -> list:
    """읽을 단위. PDF 는 면 번호(int), 그림은 [1], 압축파일은 '[파일] 이름', 엑셀은 '[시트] 이름', 그 밖은 ['전체']."""
    suf = p.suffix.lower()
    if suf == '.pdf':
        d = _ecr.pymupdf.open(p)
        try:
            return list(range(1, len(d) + 1))
        finally:
            d.close()
    if suf in IMAGE:
        return [1]
    if suf == '.zip':
        try:
            with zipfile.ZipFile(p) as z:
                names = [nfc(i.filename) for i in z.infolist() if not i.is_dir() and not i.filename.startswith('__MACOSX')]
            return [f'[파일] {n}' for n in sorted(names)] or ['전체']
        except zipfile.BadZipFile:
            return ['전체']
    if suf in ('.xlsx', '.xlsm'):
        try:
            with zipfile.ZipFile(p) as z:
                xml = z.read('xl/workbook.xml').decode('utf-8', 'replace')
            names = re.findall(r'<sheet\b[^>]*\bname="([^"]+)"', xml)
            return [f'[시트] {nfc(n)}' for n in names] or ['전체']
        except (KeyError, zipfile.BadZipFile):
            return ['전체']
    return ['전체']


def 면_표시(units: list) -> str:
    """[1,2,3,5,7,8] → '1~3, 5, 7~8'."""
    out, i = [], 0
    while i < len(units):
        j = i
        while j + 1 < len(units) and units[j + 1] == units[j] + 1:
            j += 1
        out.append(f'{units[i]}~{units[j]}' if j > i else f'{units[i]}')
        i = j + 1
    return ', '.join(out)


# ---------------------------------------------------------------- 대상 찾기
def 최근_라운드(사건: Path):
    rs = sorted((p for p in 사건.glob('라운드*') if p.is_dir()), key=lambda p: int(re.sub(r'\D', '', p.name) or 0))
    return rs[-1] if rs else 사건


def 서면_호증(사건: Path) -> dict:
    """호증키 → 읽을 파일. PDF(같은 라운드 원본 먼저, 제출 사본은 뒤)를 쓰고, PDF 가 없는 호증은 원자료를 쓴다."""
    라운드 = 최근_라운드(사건)
    out = {}
    for k, ps in _ecr.find_exhibits(사건, 라운드).items():
        ps = [p for p in ps if '작업' not in p.relative_to(사건).parts]
        if ps:
            out[k] = ps[0]
    for dp, dn, fn in sorted(os.walk(사건)):
        parts = Path(dp).relative_to(사건).parts
        if '백업' in parts or '작업' in parts or '원고별 정리' in parts or not any(x in _ecr.EVIDENCE_DIRS for x in parts):
            continue
        for f in sorted(fn):
            if f.startswith('~$') or not f.lower().endswith(DOCS):
                continue
            k = _ecr.file_key(f)
            if k and k not in out:
                out[k] = Path(dp) / f
    return out


산출물_이름 = re.compile(r'(-회신초안|-간이안)\.md$|관련 검토_|_수정\(|_최종|_Rev_\d|_초안\.(?:docx|pdf)$|_간이안\.(?:docx|pdf)$')


def 자료_목록(사건: Path, 폴더들: list) -> dict:
    """자료 이름 → 파일. 이름은 파일 이름(확장자 포함)이고, 같은 이름이 여럿이면 폴더 이름을 앞에 붙인다.
    우리가 만든 산출물(검토의견서·회신초안·수정본, `1_검토의견/CLAUDE.md` 6절의 이름)과 작업·계산·백업 폴더는 뺀다."""
    out = {}
    for d in 폴더들:
        d = Path(d)
        for p in sorted(d.rglob('*')):
            if not p.is_file() or p.name.startswith('~$') or not p.name.lower().endswith(DOCS) or 산출물_이름.search(p.name):
                continue
            if any(x in ('작업', '백업', '계산') for x in p.relative_to(d).parts[:-1]):
                continue
            k = nfc(p.name)
            if k in out:
                k = nfc(f'{p.parent.name}_{p.name}')
            out[k] = p
    return out


class 자리:
    """기록과 글을 두는 자리. 서면 사건은 증거관리/, 자료는 작업/ 아래이다."""

    def __init__(self, 사건: Path, 자료: bool):
        self.사건, self.자료 = 사건, 자료
        self.기록 = 사건 / ('작업/자료읽기' if 자료 else '증거관리/호증읽기')
        self.글 = 사건 / ('작업/자료글자' if 자료 else '증거관리/호증글자')

    def 이름(self, k: str) -> str:
        return re.sub(r'[\\/:*?"<>|]', '_', k)

    def 기록_파일(self, k: str) -> Path:
        return self.기록 / f'{self.이름(k)}.md'

    def 글_파일(self, k: str) -> Path:
        return self.글 / f'{self.이름(k)}.txt'

    def 제목(self, k: str) -> str:
        return k if self.자료 else 호증_표시(k)


# ---------------------------------------------------------------- 기록 읽고 쓰기
def 틀(자: 자리, k: str, p: Path, units: list, 앞선: str = '') -> str:
    rel = nfc(str(p.relative_to(자.사건))) if 자.사건 in p.parents else nfc(str(p))
    수 = f'{len(units)}면' if units and isinstance(units[0], int) else f'{len(units)}개'
    줄 = [f'# {자.제목(k)} 읽기 기록', '',
          f'파일: {rel}', f'해시: {해시(p)} · {수}', f'만든 날: {dt.date.today().isoformat()}',
          '읽은 방식: ', '',
          '<!-- 모든 면을 읽고 면마다 그 면에 무엇이 있는지 적는다. 같은 꼴의 면은 "- 5~9면:" 으로 묶되 면마다 다른 것(날짜·대상·문구)을 함께 적는다. '
          '"읽은 방식"에는 글자층·문자인식·그림 가운데 실제로 본 방식과 그림으로 본 면을 적는다. -->', '',
          '## 면별 내용', '']
    for u in units:
        줄.append(f'- {u}면: ' if isinstance(u, int) else f'- {u}: ')
    줄 += ['', '## 쟁점에 닿는 문구(원문 그대로, 면)', '', '- ', '']
    if 앞선:
        줄 += [f'## 앞선 기록(파일이 바뀌기 전, {dt.date.today().isoformat()}에 옮김)', '', 앞선.strip(), '']
    return '\n'.join(줄) + '\n'


def 뿌리() -> Path:
    """다른 사건의 기록을 찾을 저장소 뿌리(시험에서는 EVIDENCE_READ_ROOT 로 바꾼다)."""
    return Path(os.environ.get('EVIDENCE_READ_ROOT') or Path(__file__).resolve().parents[2])


def 다른_기록(자: '자리') -> dict:
    """저장소 안 다른 사건·자료의 읽기 기록. 해시 → [기록 파일]. 같은 파일을 두 번 읽지 않으려는 것이다."""
    out = {}
    for pat in ('*/사건/*/증거관리/호증읽기/*.md', '1_검토의견/사건/*/작업/자료읽기/*.md'):
        for f in sorted(뿌리().glob(pat)):
            if f.parent.resolve() == 자.기록.resolve():
                continue
            try:
                h = 기록_읽기(f.read_text(encoding='utf-8'))['해시']
            except OSError:
                continue
            if h:
                out.setdefault(h, []).append(f)
    return out


def 옮겨_오기(자: '자리', k: str, p: Path, units: list, 원본: Path) -> str | None:
    """같은 파일(해시)을 다른 사건에서 모든 면 읽어 둔 기록이 있으면 면별 내용과 읽은 방식을 옮긴 기록을 만든다.
    쟁점에 닿는 문구는 사건마다 다르므로 비워 두고, 옮겨 온 기록의 문구는 참고로 아래에 둔다."""
    t = 원본.read_text(encoding='utf-8')
    r = 기록_읽기(t)
    if not set(units) <= r['채운'] or not r['방식']:
        return None
    rel = nfc(str(p.relative_to(자.사건))) if 자.사건 in p.parents else nfc(str(p))
    try:
        출처 = nfc(str(원본.resolve().relative_to(뿌리().resolve())))
    except ValueError:
        출처 = nfc(str(원본))
    수 = f'{len(units)}면' if units and isinstance(units[0], int) else f'{len(units)}개'
    면별 = [re.sub(r'^(\s*-\s*[^:]+?:\s*)', r'\1(옮김) ', l) if re.match(r'^\s*-', l) else l for l in 절(t, '면별 내용') if l.strip()]
    줄 = [f'# {자.제목(k)} 읽기 기록', '',
          f'파일: {rel}', f'해시: {r["해시"]} · {수}', f'만든 날: {dt.date.today().isoformat()}',
          f'옮겨 온 기록: {출처} (같은 파일이다. 그 사건에서 읽은 면별 내용을 참고로 옮겼다. 그 사건이 읽은 방식: {r["방식"]})',
          '읽은 방식: ', '',
          '<!-- 다른 사건에서 같은 파일을 읽은 기록이다. 그 사건의 쟁점을 놓고 쓴 것이므로 이 사건 쟁점을 놓고 면마다 다시 읽고, '
          '맞으면 "(옮김)"만 지우고 모자라면 고친다. 읽은 방식과 쟁점에 닿는 문구는 이 사건에서 새로 적는다. -->', '',
          '## 면별 내용', ''] + 면별 + ['', '## 쟁점에 닿는 문구(원문 그대로, 면)', '', '- ', '',
          '## 옮겨 온 기록의 쟁점 문구(그 사건의 것. 이 사건 쟁점으로 다시 고른다)', ''] + [f'- {x}' for x in r['문구']] + ['']
    return '\n'.join(줄) + '\n'


def 그림면_적기(f: Path, 그림: dict):
    """기록 머리의 '그림으로 볼 면:' 줄을 지금 면별 글의 표시로 맞춘다."""
    t = f.read_text(encoding='utf-8')
    줄 = '그림으로 볼 면: ' + (', '.join(f'{no}면({why})' for no, why in sorted(그림.items())) if 그림 else '없음')
    if re.search(r'^그림으로 볼 면:.*$', t, re.M):
        t = re.sub(r'^그림으로 볼 면:.*$', 줄, t, count=1, flags=re.M)
    else:
        t = re.sub(r'^(만든 날:.*)$', lambda m: m.group(1) + '\n' + 줄, t, count=1, flags=re.M)
    f.write_text(t, encoding='utf-8')


def 절(text: str, 머리: str) -> list:
    """'## 머리' 로 시작하는 절의 줄."""
    out, 안 = [], False
    for line in text.splitlines():
        if line.startswith('## '):
            안 = line[3:].strip().startswith(머리)
            continue
        if 안:
            out.append(line.rstrip())
    return out


def 기록_읽기(text: str) -> dict:
    파일 = re.search(r'^파일:[ \t]*(.+)$', text, re.M)          # 줄을 넘어 다음 줄을 값으로 읽지 않는다
    해 = re.search(r'^해시:[ \t]*([0-9a-f]{6,40})', text, re.M)
    방식 = re.search(r'^읽은 방식:[ \t]*(.*)$', text, re.M)
    채운, 빈칸, 옮김 = set(), set(), set()

    def 셈(내용: str, 단위: set):
        내용 = 내용.strip()
        if 내용.startswith('(옮김)'):          # 다른 사건 기록에서 옮긴 줄은 이 사건에서 다시 읽기 전까지 빈 줄이다
            옮김.update(단위)
            빈칸.update(단위)
        else:
            (채운 if 내용 not in 빈말 else 빈칸).update(단위)

    for line in 절(text, '면별 내용'):
        line = line.strip()
        m = 면_줄.match(line)
        if m:
            셈(m.group(3), set(range(int(m.group(1)), int(m.group(2) or m.group(1)) + 1)))
            continue
        m = 단위_줄.match(line)
        if m:
            셈(m.group(3), {f'[{m.group(1)}] {nfc(m.group(2))}'})
            continue
        m = 전체_줄.match(line)
        if m:
            셈(m.group(1), {'전체'})
    문구 = [l.strip()[1:].strip() for l in 절(text, '쟁점에 닿는 문구') if l.strip().startswith('-')]
    return {'파일': 파일.group(1).strip() if 파일 else '', '해시': 해.group(1) if 해 else '',
            '방식': (방식.group(1).strip() if 방식 else ''), '채운': 채운, '빈칸': 빈칸 - 채운, '옮김': 옮김 - 채운,
            '문구': [x for x in 문구 if x]}


def 문제들(자: 자리, k: str, p: Path) -> list:
    f = 자.기록_파일(k)
    if not f.is_file():
        return ['기록 없음(make 로 틀을 만들고 모든 면을 읽어 채운다)']
    r = 기록_읽기(f.read_text(encoding='utf-8'))
    out = []
    if r['해시'] != 해시(p):
        out.append(f"기록한 뒤 파일이 바뀜(기록 {r['해시'] or '없음'}) — `make --다시 {k}` 로 새로 짜고 다시 읽는다")
    units = 단위들(p)
    빈 = [u for u in units if u not in r['채운']]
    if r['옮김']:
        out.append(f"다른 사건 기록에서 옮긴 줄 {len(r['옮김'])}개 — 이 사건 쟁점을 놓고 그 면을 다시 읽어 고치거나 확인한 뒤 '(옮김)'을 지운다")
    if 빈:
        면 = [u for u in 빈 if isinstance(u, int)]
        그밖 = [u for u in 빈 if not isinstance(u, int)]
        말 = (f'{면_표시(면)}면' if 면 else '') + (', ' if 면 and 그밖 else '') + ', '.join(그밖)
        out.append(f'읽지 않았거나 비운 단위 {len(빈)}/{len(units)}: {말}')
    if not r['방식'] or r['방식'] in 빈말:
        out.append("'읽은 방식'이 비었다(글자층·문자인식·그림 가운데 실제로 본 방식과 그림으로 본 면)")
    else:
        m = re.search(r'^그림으로 볼 면:[ \t]*(.*)$', f.read_text(encoding='utf-8'), re.M)
        볼 = {int(x) for x in re.findall(r'(\d+)면', m.group(1))} if m else set()
        못본 = sorted(볼 - 그림_본_면(r['방식'], len(units)))
        if 못본:
            out.append(f"그림으로 볼 면 {면_표시(못본)}면을 그림으로 본 기록이 없다('읽은 방식'에 '그림 {'·'.join(map(str, 못본[:5]))}면'처럼 적는다)")
    if not r['문구']:
        out.append("'쟁점에 닿는 문구'가 비었다(원문 그대로와 면. 없으면 '없음')")
    return out


# ---------------------------------------------------------------- 면별 글
def 그림_비율(page) -> float:
    """글자층 면에서 그림(사진·도표)이 차지하는 넓이 비율."""
    try:
        area = abs(page.rect)
        return min(1.0, sum(abs(_ecr.pymupdf.Rect(i['bbox']) & page.rect) for i in page.get_image_info()) / area) if area else 0.0
    except Exception:
        return 0.0


def 줄_꼴(t: str) -> str:
    return re.sub(r'\s+', ' ', t).strip()


def 표_줄(page, units: list) -> tuple:
    """글자층 면의 표를 칸을 살려 옮긴다. (표 밖의 줄, [표 줄]). 표를 찾지 못하면 줄을 그대로 둔다."""
    try:
        tabs = [t for t in page.find_tables().tables if t.row_count >= 2 and t.col_count >= 2]
    except Exception:
        return [줄_꼴(t) for t, _ in units if 줄_꼴(t)], []
    if not tabs:
        return [줄_꼴(t) for t, _ in units if 줄_꼴(t)], []
    boxes = [_ecr.pymupdf.Rect(t.bbox) for t in tabs]
    밖 = [줄_꼴(t) for t, b in units if 줄_꼴(t)
          and not any(r.contains(_ecr.pymupdf.Point((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)) for r in boxes)]
    표 = []
    for i, t in enumerate(tabs, 1):
        표.append(f'[표 {i}]')
        for row in t.extract():
            표.append('| ' + ' | '.join(줄_꼴(c or '').replace('|', '｜') for c in row) + ' |')
    return 밖, 표


def 숫자표_같나(줄들: list) -> bool:
    """문자인식 면이 숫자 표(대장·명세)로 보이는가. 칸이 섞여 읽히므로 그림으로 본다."""
    숫자줄 = 0
    for t in 줄들:
        toks = t.split()
        if len(toks) >= 3 and sum(bool(re.fullmatch(r'[\d,.\-:/()%원]+', x)) for x in toks) / len(toks) >= 0.6:
            숫자줄 += 1
    return 숫자줄 >= 8 or (줄들 and 숫자줄 / len(줄들) >= 0.4 and 숫자줄 >= 3)


def 글_쓰기(자: 자리, k: str, p: Path, use_ocr: bool) -> tuple:
    """면별 글을 쓴다. 돌려주는 것: (알림, {그림으로 볼 면: 까닭}).

    읽는 비용을 줄이되 글은 하나도 빼지 않는다. ① 여러 면에 되풀이되는 줄(문자 모음의 머리·꼬리, 대장의 칸 이름)은 머리에
    번호를 붙여 한 번 적고, 면마다 그 면에 든 되풀이 줄의 번호를 적는다(어느 면에 어느 줄이 있는지 그대로 남는다).
    ② 글자층 면의 표는 칸을 살려 옮긴다. ③ 글로 읽기 어려운 면(글자가 거의 없음, 문자인식 품질 낮음, 숫자 표로 보이는 스캔 면,
    사진·도표가 큰 면)만 '그림으로 볼 면'으로 표시한다. 그 면은 반드시 그림으로 열고, 기록의 '읽은 방식'에 면 번호를 적는다."""
    if p.suffix.lower() != '.pdf':
        return '', {}
    캐시 = 자.글
    ocr_dirs = [str(x) for x in 자.사건.glob('라운드*/작업/증거인용검토/ocr')] + [str(캐시 / 'ocr')]
    ex = _ecr.Exhibit(자.이름(k), p, 캐시, ocr_dirs=ocr_dirs, use_ocr=use_ocr)
    면들, 그림 = [], {}
    try:
        ex.prepare(range(1, len(ex) + 1))
        for no in range(1, len(ex) + 1):
            e = ex.pages.get(no) or {'src': '글자 없음', 'units': []}
            src = e['src']
            if src.startswith('글자층'):
                줄들, 표 = 표_줄(ex.doc[no - 1], e['units'])
            else:
                줄들, 표 = [줄_꼴(t) for t, _ in e['units'] if 줄_꼴(t)], []
            글 = ' '.join(줄들 + 표)
            if len(re.sub(r'\s', '', 글)) < 20:
                그림[no] = '글자 거의 없음'
            elif src.startswith('문자인식') and _ecr.quality(글) < 0.55:
                그림[no] = '문자인식 품질 낮음'
            elif src.startswith('문자인식') and 숫자표_같나(줄들):
                그림[no] = '숫자 표(칸 맞춤)'
            elif src.startswith('글자층(적음)'):
                그림[no] = '글자 적음'
            elif src.startswith('글자층') and 그림_비율(ex.doc[no - 1]) >= 0.25:
                그림[no] = '사진·도표 있음'
            면들.append((no, src, 줄들, 표))
    finally:
        ex.close()
    for png in 캐시.glob('ocr/*/*.png'):      # 글만 쌓고 그림은 남기지 않는다
        png.unlink()
    n = len(면들)
    번호 = {}
    if n >= 4:
        셈 = {}
        for _, _, 줄들, _ in 면들:
            for t in set(줄들):
                셈[t] = 셈.get(t, 0) + 1
        기준 = max(3, -(-n // 2))
        for t in sorted((t for t, c in 셈.items() if c >= 기준 and len(t) >= 4), key=lambda t: -셈[t]):
            번호[t] = len(번호) + 1
    머리 = [f'# {자.제목(k)} 면별 글 — {nfc(p.name)}', '',
            f'{n}면. 그림으로 볼 면: ' + (', '.join(f'{no}면({why})' for no, why in sorted(그림.items())) if 그림 else '없음')]
    if 번호:
        머리 += ['', f'## 여러 면에 되풀이되는 줄 {len(번호)}개 — 면마다 [되풀이 줄: 번호]로 적는다(그 면에 그 줄이 있다는 뜻)', '']
        머리 += [f'- R{i}: {t}' for t, i in sorted(번호.items(), key=lambda x: x[1])]
    본문 = []
    for no, src, 줄들, 표 in 면들:
        if 번호:
            든 = sorted({번호[t] for t in 줄들 if t in 번호})
            줄들 = [t for t in 줄들 if t not in 번호] + ([f'[되풀이 줄: {", ".join(f"R{i}" for i in 든)}]'] if 든 else [])
        표시 = f' — 그림으로 볼 면({그림[no]})' if no in 그림 else ''
        본문.append(f'=== {no}면 ({src}){표시} ===\n' + '\n'.join(줄들 + 표) + '\n')
    자.글_파일(k).parent.mkdir(parents=True, exist_ok=True)
    자.글_파일(k).write_text('\n'.join(머리) + '\n\n' + '\n'.join(본문), encoding='utf-8')
    return (f'그림으로 볼 면 {면_표시(sorted(그림))}' if 그림 else ''), 그림


def 그림_본_면(방식: str, 전체: int) -> set:
    """'읽은 방식'에서 그림으로 본 면. '그림 3·7면', '그림 3, 7~9면', '그림 전 면'."""
    본 = set()
    for m in re.finditer(r'그림(?:으로)?\s*(?:본\s*면)?\s*:?\s*(전\s*면|모든\s*면|[\d\s,·ㆍ~\-]+)', 방식):
        g = m.group(1)
        if re.match(r'(전|모든)\s*면', g):
            return set(range(1, 전체 + 1))
        for a, b in re.findall(r'(\d+)\s*(?:[~\-]\s*(\d+))?', g):
            본.update(range(int(a), int(b or a) + 1))
    return 본


# ---------------------------------------------------------------- 명령
def 대상(a) -> tuple:
    사건 = Path(a.case)
    자 = 자리(사건, bool(a.자료))
    전체 = 자료_목록(사건, a.자료) if a.자료 else 서면_호증(사건)
    목록 = dict(전체)
    if a.호증:
        목록 = {k: v for k, v in 전체.items()
                if any(k == x or (not re.search(r'\d', x) and k.startswith(x)) for x in a.호증)}
    return 자, 목록, 전체


def cmd_make(a) -> int:
    자, 목록, 전체 = 대상(a)
    if not 목록:
        print('읽을 호증(자료)이 없습니다:', a.case)
        return 2
    자.기록.mkdir(parents=True, exist_ok=True)
    현재해시 = {k: 해시(p) for k, p in 전체.items()}
    # 번호를 다시 매겨 기록이 옛 호증키에 남은 것은 해시가 같은 새 호증키로 옮긴다
    옮김, 이름들 = [], {자.이름(k) for k in 전체}
    for f in sorted(자.기록.glob('*.md')):
        k_old = f.stem
        if k_old in 이름들:
            continue
        h = 기록_읽기(f.read_text(encoding='utf-8'))['해시']
        새 = [k for k, v in 현재해시.items() if v == h and not 자.기록_파일(k).is_file()]
        if len(새) == 1:
            t = f.read_text(encoding='utf-8')
            t = re.sub(r'^# .+? 읽기 기록', f'# {자.제목(새[0])} 읽기 기록', t, count=1, flags=re.M)
            t = re.sub(r'^파일:.*$', f'파일: {nfc(str(전체[새[0]].relative_to(자.사건)))}', t, count=1, flags=re.M)
            자.기록_파일(새[0]).write_text(t, encoding='utf-8')
            f.unlink()
            옛글 = 자.글 / f'{k_old}.txt'
            if 옛글.is_file() and not 자.글_파일(새[0]).is_file():
                옛글.rename(자.글_파일(새[0]))
            옮김.append(f'{k_old} → {새[0]}')
    다시 = set(a.다시 or [])
    새로, 바뀜, 알림, 옮겨옴 = [], [], [], []
    색인 = 다른_기록(자)
    for k in sorted(목록, key=호증_정렬):
        p, f = 목록[k], 자.기록_파일(k)
        if f.is_file():
            r = 기록_읽기(f.read_text(encoding='utf-8'))
            if r['해시'] != 현재해시[k]:
                if k in 다시:
                    앞선 = '\n'.join(절(f.read_text(encoding='utf-8'), '면별 내용'))
                    f.write_text(틀(자, k, p, 단위들(p), 앞선), encoding='utf-8')
                    새로.append(k)
                else:
                    바뀜.append(k)
        else:
            units = 단위들(p)
            t = next((x for x in (옮겨_오기(자, k, p, units, g) for g in 색인.get(현재해시[k], [])) if x), None)
            f.write_text(t or 틀(자, k, p, units), encoding='utf-8')
            (옮겨옴 if t else 새로).append(k)
        if not a.no_text and (k in 새로 or k in 옮겨옴 or not 자.글_파일(k).is_file()):
            msg, 그림 = 글_쓰기(자, k, p, not a.no_ocr)
            if p.suffix.lower() == '.pdf':
                그림면_적기(f, 그림)
            if msg:
                알림.append(f'{자.제목(k)}: {msg}')
        print(f'{자.제목(k)} — {nfc(p.name)}', flush=True)
    print(f'기록 틀 새로 {len(새로)}건, 다른 사건 기록에서 옮겨 옴 {len(옮겨옴)}건(쟁점 문구만 채운다), 번호 따라 옮김 {len(옮김)}건, '
          f'파일이 바뀐 기록 {len(바뀜)}건 → {자.기록}')
    for s in 옮김:
        print('  옮김: ' + s)
    for k in 옮겨옴:
        print(f'  옮겨 옴: {자.제목(k)} — 같은 파일을 다른 사건에서 읽은 기록')
    for k in 바뀜:
        print(f'  바뀜: {자.제목(k)} — `make --다시 {k}` 로 새로 짠다')
    for s in 알림:
        print('  ' + s)
    print('다음: 면별 글(' + str(자.글) + ')과 그림으로 모든 면을 읽고 기록을 채운 뒤 `check` 를 돌린다.')
    return 0


def cmd_check(a) -> int:
    자, 목록, 전체 = 대상(a)
    if not 목록:
        print('읽을 호증(자료)이 없습니다:', a.case)
        return 2
    나쁨 = {}
    for k in sorted(목록, key=호증_정렬):
        ps = 문제들(자, k, 목록[k])
        if ps:
            나쁨[k] = ps
    옛것 = sorted(f.stem for f in 자.기록.glob('*.md') if f.stem not in {자.이름(k) for k in 전체}) if 자.기록.is_dir() else []
    if 나쁨:
        print(f'전 면 읽기 기록: 호증(자료) {len(목록)}건 가운데 {len(나쁨)}건이 덜 되었다 → {자.기록}')
        for k, ps in 나쁨.items():
            print(f'- {자.제목(k)} ({nfc(목록[k].name)})')
            for s in ps:
                print(f'    {s}')
    for s in 옛것:
        print(f'참고: 지금 호증에 없는 기록 {s}.md (번호를 다시 매겼으면 make 가 옮긴다)')
    if 나쁨:
        return 1
    print(f'전 면 읽기 기록: 호증(자료) {len(목록)}건 모두 채워졌다 → {자.기록}')
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='호증(자료)을 모든 면 읽었는지 기록하고 확인한다')
    sub = ap.add_subparsers(dest='cmd', required=True)
    for name in ('make', 'check'):
        s = sub.add_parser(name)
        s.add_argument('case')
        s.add_argument('--자료', nargs='+', help='호증 번호 없는 자료 폴더(검토의견의 첨부 등)')
        s.add_argument('--호증', nargs='+', help='이 호증키(사6)나 머리글자(사 노)만')
        if name == 'make':
            s.add_argument('--다시', nargs='+', help='파일이 바뀐 이 호증키의 기록을 새로 짠다(앞선 기록은 끝에 옮겨 둔다)')
            s.add_argument('--no-ocr', action='store_true')
            s.add_argument('--no-text', action='store_true', help='면별 글을 만들지 않는다')
    a = ap.parse_args(argv)
    return cmd_make(a) if a.cmd == 'make' else cmd_check(a)


if __name__ == '__main__':
    raise SystemExit(main())
