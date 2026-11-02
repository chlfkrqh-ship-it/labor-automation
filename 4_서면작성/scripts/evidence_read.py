"""호증(자료)을 모든 면 읽었는지 기록하고 기계로 확인한다 — 증거 '파악'의 관문(`.claude/commands/증거정리.md` 3단계).

    python -B 4_서면작성/scripts/evidence_read.py make  "<사건 폴더>" [--호증 사6 노 ...] [--no-ocr] [--no-text]
    python -B 4_서면작성/scripts/evidence_read.py make  "<사건 폴더>" --다시 사6        # 파일이 바뀐 호증의 기록을 새로 짠다
    python -B 4_서면작성/scripts/evidence_read.py check "<사건 폴더>" [--호증 ...]
    python -B 4_서면작성/scripts/evidence_read.py 그림  "<사건 폴더>" --호증 을105-8 [--면 3 7] [--전부]   # 그림으로 볼 면을 확인표와 함께 연다
    python -B 4_서면작성/scripts/evidence_read.py 실측  "<사건 폴더>" [--호증 ...] [--보기]   # 세션 기록으로 실제 읽은 줄을 재어 기록에 적는다
    python -B 4_서면작성/scripts/evidence_read.py make  "<사건 폴더>" --글다시 [사6 ...]    # 면별 글만 지금 판으로 다시 낸다(기록의 면별 내용은 그대로)
    python -B 4_서면작성/scripts/evidence_read.py make  "1_검토의견/사건/{의뢰인}_{검토내용}" --자료 "<첨부 폴더>"   # 호증 번호 없는 자료

make  서면 사건은 호증마다(우리·상대, PDF 가 아닌 원자료 포함) `증거관리/호증읽기/{호증키}.md` 틀을 만든다. 틀에는 파일·해시·단위 수와
      단위마다 빈 줄(PDF·그림은 '- 3면:', 압축파일은 '- [파일] 이름:', 엑셀은 '- [시트] 이름:', 그 밖은 '- 전체:')이 있다.
      PDF 는 면별 글(글자층, 없거나 깨지면 Windows 문자인식)을 `증거관리/호증글자/{호증키}.txt` 에 낸다.
      `--자료` 를 주면 그 폴더의 파일마다 `작업/자료읽기/{파일 이름}.md` 와 `작업/자료글자/{파일 이름}.txt` 를 만든다.
      호증 번호를 다시 매겨 기록의 호증키와 파일이 어긋나면, 해시가 같은 파일의 호증키로 기록을 옮긴다.
check 모든 호증(자료)에 기록이 있는지, 기록한 뒤 파일이 바뀌지 않았는지(해시), 모든 단위가 채워졌는지, '읽은 방식'과
      '쟁점에 닿는 문구'가 적혔는지, 면마다 확인표가 맞는지, 다 읽지 않았다는 표현(모음 그림, '…중심으로 읽음')이 없는지,
      PDF·그림에 '실측:' 줄이 있고 그 뒤 면별 글이 바뀌지 않았는지 본다. 하나라도 어긋나면 종료 코드 1 이다.
그림  그림으로 볼 면(스캔한 표, 사진, 문자인식이 깨진 면)과 그림 호증을 원본에 가까운 크기로 그려 아래 띠에 확인표를 적어
      시스템 임시 폴더에 둔다(OneDrive 에 쌓지 않는다). 작성 세션은 그 그림을 한 장씩 열어 읽는다.
실측  이 PC 세션 기록에서 면별 글을 찍은 도구 결과의 줄과 한 장씩 연 그림을 모아 호증마다 잰다. 줄의 98%, 면마다 90% 이상이 화면에 나왔고
      그림으로 볼 면을 모두 열었으면 기록에 '실측:' 줄을 적는다. 거른 줄과 확인표만 찍으면 모자라게 나오고, 모음 그림과 하위 작업의 기록은 세지 않는다.
      세션 기록은 PC 마다 따로이고 열흘이 지나면 지워지므로 읽은 그 PC 에서 바로 돌린다.

확인표: 면별 글의 면마다 끝에 '[3면 끝 · 확인표 K7QF]'가 있고, 그림으로 볼 면은 `그림` 이 그린 그림 아래 띠에 있다. 그 면을 끝까지 열어
본 세션만 알 수 있으므로 기록의 그 면 줄('- 3면: … 확인표 K7QF')에 옮겨 적는다. 묶은 줄('- 5~9면:')에는 그 면들의 확인표를 모두 적는다.
확인표는 사건 폴더 이름·파일 해시·면 번호로 정해지므로 다른 사건의 기록을 옮겨 와도 맞지 않는다. 스크립트로 확인표만 뽑거나 줄을 걸러 읽지 않는다.
모음 그림(여러 면을 줄여 한 장에 모은 그림)은 글자를 읽을 수 없으므로 읽은 것으로 치지 않는다.

작성 세션은 면별 글과 그림으로 모든 면을 읽고 면마다 그 면에 무엇이 있는지 적는다. 같은 꼴의 면(일자별 문자, 월별 대장)은
'- 5~9면:' 처럼 묶을 수 있으나 면마다 다른 것(날짜·대상·문구)을 함께 적는다. '같음', '반복', '…' 만 적은 줄은 빈 줄로 센다.
이 도구는 칸이 채워졌는지와 글이 실제로 화면에 나왔는지만 본다. 읽은 내용이 맞는지는 판정하지 않는다.

2026. 11. 2. GGM 정직 3월: 사 제6호증(38면, 글자층 없음)을 첫 면만 읽고 '반복 기재'로 요약하여 3면의 쟁점 문구를 답변서(1)·(2)와
그 뒤의 자체 재검토에서 모두 놓친 일로 만들었다. 담당 노무사 "노동사건자동화는 결국 문체, 증거, 판례 세 가지에 어떠한 하자도
없어야", "증거(편철, 파악, 이해 등 모든 걸 포함)".
2026. 11. 3. 한전 태양광 22명(노정일): 스캔 계좌내역 5건 95면(기록이 찬 25건 글자의 72.6%)을 문자인식 줄을 임시 스크립트로 걸러 금액이 큰 줄과
이름 줄 중심으로 읽고 나머지를 모음 그림으로 보았는데 '그림 전 면(모음 그림)'이라는 자기 신고로 check 를 지났다. 그 범위에서 원고 문답서와
부딪히는 거래가 나왔다. 확인표와 스캔 표 줄 복원을 넣었다. 담당 노무사 "법률자료작성이므로 완결성 100%에 수렴해야 한다고 대충 읽고 쓰면 그게 되겠니".
확인표는 거른 줄과 함께 찍으면 옮겨 적을 수 있으므로 같은 날 세션 기록으로 재는 실측을 더했다. 담당 노무사 "뭔가 여전히 증거는 대충 읽는 느낌이 있네".
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import os
import math
import re
import statistics
import sys
import tempfile
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
확인_글자 = 'ACDEFGHJKLMNPQRTUVWXY3479'      # 헷갈리는 글자(0·O, 1·I, 2·Z, 5·S, 6·G, 8·B)는 쓰지 않는다
# 다 읽지 않았다는 표현. 내용 설명('안전 수칙을 중심으로 진행')에 걸리지 않게 읽는 말과 붙은 것만 본다
거른말 = re.compile(r'모음\s*그림|썸네일|축소\s*그림'
                 r'|(?:중심으로|위주로)\s*(?:만\s*)?(?:읽|보|봄|확인)'
                 r'|(?:일부|몇\s*줄)\s*(?:만\s*)?(?:줄\s*(?:만\s*)?)?(?:읽|보고|보았|봄)'
                 r'|(?:걸러|골라|추려|훑어|대강|대충)\s*(?:서\s*)?(?:읽|보|봄|확인)'
                 r'|나머지(?:는|도|\s*면은|\s*줄은)?\s*(?:모음|그림으로만|생략|훑|보지|읽지)'
                 r'|(?:면|줄|쪽)(?:은|을|는)?\s*건너')
줄_통과, 면_통과 = 0.98, 0.9      # 실측: 호증의 줄, 면마다의 줄 가운데 화면에 나온 몫


def 확인표(사건: Path, 해: str, no, 갈래: str) -> str:
    """면마다 끝에 붙는 확인표. 갈래는 '글'(면별 글) 또는 '그림'·'그림2'…(그림으로 본 면·조각). 그 면을 끝까지 열어 본 세션만 안다."""
    h = hashlib.sha1(f'{nfc(Path(사건).resolve().name)}|{해}|{no}|{갈래}'.encode('utf-8')).digest()
    return ''.join(확인_글자[b % len(확인_글자)] for b in h[:4])


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


산출물_이름 = re.compile(r'(-회신초안|-간이안)\.md$|관련 검토[_.]|_수정\(|_최종|_Rev_\d|_초안\.(?:docx|pdf)$|_간이안\.(?:docx|pdf)$'
                    r'|_노동금액계산표|^검산_|^_추출\.txt$')
우리_폴더 = re.compile(r'^(?:작업|백업|계산|전환작업|빌드)$|^별첨_|^법제처')


def 자료_목록(사건: Path, 폴더들: list) -> dict:
    """자료 이름 → 파일. 이름은 파일 이름(확장자 포함)이고, 같은 이름이 여럿이면 폴더 이름을 앞에 붙인다.
    우리가 만든 산출물(검토의견서·회신초안·수정본, `1_검토의견/CLAUDE.md` 6절의 이름, 엔진이 만든 계산표)과
    작업·계산·백업·전환작업(Word 변환 부품)·별첨(붙이려고 받은 판결·회시)·법제처 수확 폴더는 뺀다. 상대방의 별지 계산표는 자료이다."""
    out = {}
    for d in 폴더들:
        d = Path(d)
        for p in sorted(d.rglob('*')):
            if not p.is_file() or p.name.startswith('~$') or not p.name.lower().endswith(DOCS) or 산출물_이름.search(p.name):
                continue
            if any(우리_폴더.search(x) for x in p.relative_to(d).parts[:-1]):
                continue
            if p.stem in (f'{d.name}_계산표', f'{d.name}_검산표') or p.stem.startswith(f'{d.name}_대안계산표'):
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
    rel = nfc(p.relative_to(자.사건).as_posix()) if 자.사건 in p.parents else nfc(str(p))   # 두 PC가 함께 보는 기록이라 / 로 적는다
    수 = f'{len(units)}면' if units and isinstance(units[0], int) else f'{len(units)}개'
    줄 = [f'# {자.제목(k)} 읽기 기록', '',
          f'파일: {rel}', f'해시: {해시(p)} · {수}', f'만든 날: {dt.date.today().isoformat()}',
          '읽은 방식: ', '',
          '<!-- 모든 면을 읽고 면마다 그 면에 무엇이 있는지 적는다. 같은 꼴의 면은 "- 5~9면:" 으로 묶되 면마다 다른 것(날짜·대상·문구)을 함께 적는다. '
          '"읽은 방식"에는 글자층·문자인식·그림 가운데 실제로 본 방식과 그림으로 본 면을 적는다. '
          '면별 글의 면 끝 확인표(그림으로 볼 면은 `그림` 이 그린 그림 아래 띠의 확인표)를 그 면 줄에 옮긴다. 줄을 걸러 읽거나 모음 그림으로 갈음하지 않는다. -->', '',
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
    rel = nfc(p.relative_to(자.사건).as_posix()) if 자.사건 in p.parents else nfc(str(p))
    try:
        출처 = nfc(원본.resolve().relative_to(뿌리().resolve()).as_posix())
    except ValueError:
        출처 = nfc(str(원본))
    수 = f'{len(units)}면' if units and isinstance(units[0], int) else f'{len(units)}개'
    면별 = [re.sub(r'\s*확인표\s*[A-Z0-9]{4}', '', re.sub(r'^(\s*-\s*[^:]+?:\s*)', r'\1(옮김) ', l)) if re.match(r'^\s*-', l) else l
           for l in 절(t, '면별 내용') if l.strip()]
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


def 단위_줄들(text: str) -> list:
    """'면별 내용'의 줄마다 (그 줄이 덮는 단위, 내용)."""
    out = []
    for line in 절(text, '면별 내용'):
        line = line.strip()
        m = 면_줄.match(line)
        if m:
            out.append((set(range(int(m.group(1)), int(m.group(2) or m.group(1)) + 1)), m.group(3)))
            continue
        m = 단위_줄.match(line)
        if m:
            out.append(({f'[{m.group(1)}] {nfc(m.group(2))}'}, m.group(3)))
            continue
        m = 전체_줄.match(line)
        if m:
            out.append(({'전체'}, m.group(1)))
    return out


def 그림_면들(자: 자리, k: str) -> tuple:
    """면별 글에서 (그림으로 볼 면, 확인표가 있는 판인지). 면별 글이 없으면 (None, False)."""
    f = 자.글_파일(k)
    if not f.is_file():
        return None, False
    t = f.read_text(encoding='utf-8', errors='replace')
    return {int(x) for x in re.findall(r'^=== (\d+)면 .*? — 그림으로 볼 면\(', t, re.M)}, '면 끝 · ' in t


def 그림_조각수(p: Path) -> int:
    """그림 호증을 몇 조각으로 여는지. 긴 화면 갈무리는 한 장으로 줄이면 글자를 못 읽으므로 폭의 1.4배 높이로 자른다. 못 열면 0."""
    try:
        d = _ecr.pymupdf.open(p)
    except Exception:
        return 0
    try:
        r = d[0].rect
        return max(1, math.ceil(r.height / (r.width * 1.4))) if r.width > 0 else 0
    except Exception:
        return 0
    finally:
        d.close()


def 기대_확인표(자: 자리, k: str, p: Path) -> dict | None:
    """단위 → 그 단위 줄에 있어야 할 확인표들. PDF 와 그림 호증만 보고, 그 밖(압축·엑셀·문서·소리)은 None 이다(읽은 방식의 신고로 본다)."""
    suf = p.suffix.lower()
    if suf == '.pdf':
        그림, _ = 그림_면들(자, k)
        if 그림 is None:
            return None
        해 = 해시(p)
        return {no: [확인표(자.사건, 해, no, '그림' if no in 그림 else '글')] for no in 단위들(p)}
    if suf in IMAGE:
        n = 그림_조각수(p)
        if not n:
            return None
        해 = 해시(p)
        return {1: [확인표(자.사건, 해, 1, '그림' if i == 1 else f'그림{i}') for i in range(1, n + 1)]}
    return None


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
    text = f.read_text(encoding='utf-8')
    if p.suffix.lower() == '.pdf':
        그림, 새판 = 그림_면들(자, k)
        if 그림 is None:
            out.append('면별 글이 없다 — `make` 로 만들고 면마다 끝까지 읽는다(면 끝의 확인표를 기록에 옮긴다)')
        elif not 새판:
            out.append('면별 글이 확인표가 없는 옛 판이다 — `make` 를 다시 돌려 새로 쓰고 면마다 다시 읽어 확인표를 옮긴다')
    기대 = 기대_확인표(자, k, p)
    if 기대:
        줄들 = 단위_줄들(text)
        틀린 = [u for u, toks in 기대.items()      # 띄어 옮겨도('F Q U G') 맞게 본다
              if not all(x in re.sub(r'\s', '', ' '.join(c for us, c in 줄들 if u in us)).upper() for x in toks)]
        if 틀린:
            out.append(f"확인표가 없거나 맞지 않는 면 {len(틀린)}/{len(기대)}: {면_표시(틀린)}면 — 면별 글은 그 면 끝까지 읽고, 그림으로 볼 면과 그림 호증은 "
                       f"`evidence_read.py 그림` 이 그린 그림을 한 장씩 열어 끝의 확인표를 그 면 줄에 옮긴다(줄을 걸러 읽거나 모음 그림으로 갈음하지 않는다)")
    거른 = [m.group(0) for 줄 in [r['방식']] + [c for _, c in 단위_줄들(text)] for m in [거른말.search(줄)] if m]
    if 거른:
        말들 = "', '".join(dict.fromkeys(거른))
        out.append(f"다 읽지 않았다는 표현이 있다('{말들}') — 그 면을 처음부터 끝까지 읽고 기록을 고친다. "
                   '모음 그림은 글자를 읽을 수 없어 읽은 것으로 치지 않는다')
    return out + 실측_문제(자, k, p, text)


def 잴_수_있나(p: Path) -> bool:
    """세션 기록으로 잴 수 있는 호증인가. 면별 글이 있는 PDF 와 열리는 그림이고, 압축·엑셀·문서·소리는 재지 않는다."""
    return p.suffix.lower() == '.pdf' or (p.suffix.lower() in IMAGE and 그림_조각수(p) > 0)


def 실측_문제(자: 자리, k: str, p: Path, 기록: str) -> list:
    """기록에 '실측:' 줄이 있고 그 뒤 면별 글이 바뀌지 않았는지. 재는 일은 `실측` 이 한다."""
    if not 잴_수_있나(p):
        return []
    m = re.search(r'^실측:(.*)$', 기록, re.M)
    if not m:
        return ['실제로 읽은 기록(실측)이 없다 — 면별 글을 읽기 도구로 끝까지 읽고(줄을 거르지 않는다) 그림으로 볼 면을 한 장씩 연 뒤 `실측` 을 돌린다']
    글 = 자.글_파일(k)
    if p.suffix.lower() == '.pdf' and 글.is_file() and f'글 {해시(글)}' not in m.group(1):
        return ['실측한 뒤 면별 글이 바뀌었다 — 지금 면별 글을 읽고 `실측` 을 다시 돌린다']
    return []


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


def 줄_복원(units: list) -> list:
    """문자인식 면의 조각을 높이가 같은 것끼리 왼쪽부터 한 줄로 잇는다. 스캔한 표(계좌내역·대장)는 칸이 조각으로 따로 읽혀
    거래 한 건이 여러 줄로 흩어지므로 칸을 '|'로 이어 줄로 돌린다. 스캔이 기울면 한 줄의 끝이 다음 줄 높이까지 내려가므로 옆 칸과의
    높이 차이로 기울기를 재어 바로잡는다. 글자는 하나도 빼지 않는다(2026. 11. 3. 한전 계좌내역)."""
    조각 = [(줄_꼴(t), b) for t, b in units if 줄_꼴(t)]
    if not 조각:
        return []
    높이 = sorted(max(1.0, b[3] - b[1]) for _, b in 조각)
    h = 높이[len(높이) // 2]
    자리들 = sorted(((b[0] + b[2]) / 2, (b[1] + b[3]) / 2) for _, b in 조각)
    기울기들 = []
    for i, (x, y) in enumerate(자리들):
        for x2, y2 in 자리들[i + 1:i + 200]:
            if 30 < x2 - x <= 400 and abs(y2 - y) < h * 0.6:
                기울기들.append((y2 - y) / (x2 - x))
                break
    기울기 = statistics.median(기울기들) if 기울기들 else 0.0
    줄들 = []
    for yc, x0, 글 in sorted(((b[1] + b[3]) / 2 - 기울기 * (b[0] + b[2]) / 2, b[0], 글) for 글, b in 조각):
        if 줄들 and yc - 줄들[-1][0] <= h * 0.55:
            줄들[-1][1].append((x0, 글))
            n = len(줄들[-1][1])
            줄들[-1][0] = (줄들[-1][0] * (n - 1) + yc) / n
        else:
            줄들.append([yc, [(x0, 글)]])
    return ['| ' + ' | '.join(g for _, g in sorted(c)) + ' |' if len(c) > 1 else c[0][1] for _, c in 줄들]


def 표_모양(행들: list) -> bool:
    """이은 줄이 표로 보이는가. 칸이 셋 이상인 줄이 다섯 줄 넘고 조각의 절반 이상이 그런 줄에 있으면 칸이 조각으로 따로 읽힌 스캔 표이다."""
    칸들 = [줄.count(' | ') + 1 if 줄.startswith('| ') else 1 for 줄 in 행들]
    많은 = [c for c in 칸들 if c >= 3]
    return len(많은) >= 5 and sum(많은) * 2 >= sum(칸들)


def 숫자표_같나(줄들: list) -> bool:
    """문자인식 면이 숫자 표(대장·명세)로 보이는가. 칸이 섞여 읽히므로 그림으로 본다."""
    숫자줄 = 0
    for t in 줄들:
        toks = t.replace('|', ' ').split()
        if len(toks) >= 3 and sum(bool(re.fullmatch(r'[\d,.\-:/()%원]+', x)) for x in toks) / len(toks) >= 0.6:
            숫자줄 += 1
    return 숫자줄 >= 8 or (줄들 and 숫자줄 / len(줄들) >= 0.4 and 숫자줄 >= 3)


def 글_쓰기(자: 자리, k: str, p: Path, use_ocr: bool) -> tuple:
    """면별 글을 쓴다. 돌려주는 것: (알림, {그림으로 볼 면: 까닭}).

    읽는 비용을 줄이되 글은 하나도 빼지 않는다. ① 여러 면에 되풀이되는 줄(문자 모음의 머리·꼬리, 대장의 칸 이름)은 머리에
    번호를 붙여 한 번 적고, 면마다 그 면에 든 되풀이 줄의 번호를 적는다(어느 면에 어느 줄이 있는지 그대로 남는다).
    ② 글자층 면의 표는 칸을 살려 옮기고, 칸이 조각으로 따로 읽힌 스캔 표는 줄로 돌린다. ③ 글로 읽기 어려운 면(글자가 거의 없음, 문자인식 품질 낮음, 숫자 표로 보이는 스캔 면,
    사진·도표가 큰 면)만 '그림으로 볼 면'으로 표시한다. 그 면은 반드시 그림으로 열고, 기록의 '읽은 방식'에 면 번호를 적는다."""
    if p.suffix.lower() != '.pdf':
        return '', {}
    해 = 해시(p)
    캐시 = 자.글
    ocr_dirs = [str(x) for x in 자.사건.glob('라운드*/작업/증거인용검토*/ocr')] + [str(캐시 / 'ocr')]
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
                행들 = 줄_복원(e['units'])
                if 표_모양(행들):      # 칸마다 따로 읽혀 숫자 표로 잡히지 않는 면(을 제105호증의10)도 줄로 돌린다
                    줄들 = 행들
            글 = ' '.join(줄들 + 표).replace('|', ' ')
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
            if 그림.get(no) == '숫자 표(칸 맞춤)':      # 칸을 줄로 돌려 읽게 하고, 숫자는 그림으로 맞댄다
                줄들 = 줄_복원(e['units'])
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
            f'{n}면. 그림으로 볼 면: ' + (', '.join(f'{no}면({why})' for no, why in sorted(그림.items())) if 그림 else '없음'),
            '면마다 끝까지 읽고 끝의 확인표를 기록의 그 면 줄에 옮긴다. 그림으로 볼 면은 '
            f'`python -B 4_서면작성/scripts/evidence_read.py 그림 "<사건 폴더>" --호증 {k}` 이 그린 그림을 한 장씩 열어 읽고 그림 아래 띠의 확인표를 옮긴다. '
            '줄을 걸러 읽거나 모음 그림으로 갈음하지 않는다.']
    if 번호:
        머리 += ['', f'## 여러 면에 되풀이되는 줄 {len(번호)}개 — 면마다 [되풀이 줄: 번호]로 적는다(그 면에 그 줄이 있다는 뜻)', '']
        머리 += [f'- R{i}: {t}' for t, i in sorted(번호.items(), key=lambda x: x[1])]
    본문 = []
    for no, src, 줄들, 표 in 면들:
        if 번호:
            든 = sorted({번호[t] for t in 줄들 if t in 번호})
            줄들 = [t for t in 줄들 if t not in 번호] + ([f'[되풀이 줄: {", ".join(f"R{i}" for i in 든)}]'] if 든 else [])
        표시 = f' — 그림으로 볼 면({그림[no]})' if no in 그림 else ''
        끝 = (f'[{no}면 끝 · 그림으로 볼 면 — 확인표는 `그림` 이 그린 그림 아래 띠에 있다]' if no in 그림
             else f'[{no}면 끝 · 확인표 {확인표(자.사건, 해, no, "글")}]')
        본문.append(f'=== {no}면 ({src}){표시} ===\n' + '\n'.join(줄들 + 표 + [끝]) + '\n')
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


# ---------------------------------------------------------------- 실측: 세션 기록으로 실제 읽은 줄을 잰다
def 정규(t: str) -> str:
    return re.sub(r'\s+', '', nfc(t))


def 면_범위(글: str) -> set:
    """'3 7-9', '1~3, 5' → 면 번호들."""
    out = set()
    for a, b in re.findall(r'(\d+)\s*(?:[~\-]\s*(\d+))?', 글):
        out.update(range(int(a), int(b or a) + 1))
    return out


def 글_읽기(text: str) -> tuple:
    """면별 글에서 ({면: [읽을 줄]}, {그림으로 볼 면}, {돌린 면: 각도}). 되풀이 줄은 머리에 적힌 그 줄을, 표는 줄마다, 면 끝 줄까지 센다."""
    R = dict(re.findall(r'^- R(\d+): (.*)$', text, re.M))
    면들, 볼, 돌림, 지금 = {}, set(), {}, None
    for line in text.splitlines():
        m = re.match(r'^=== (\d+)면 \((.*?)\)( — 그림으로 볼 면\(.*\))? ===$', line)
        if m:
            지금 = int(m.group(1))
            면들[지금] = []
            if m.group(3):
                볼.add(지금)
            r = re.search(r'(\d+)도 돌림', m.group(2))
            if r:
                돌림[지금] = int(r.group(1))
            continue
        s = line.strip()
        if 지금 is None or not s or re.fullmatch(r'\[표 \d+\]', s):
            continue
        m = re.fullmatch(r'\[되풀이 줄: (.*)\]', s)
        if m:
            면들[지금] += [f'- R{x}: {R[x]}' for x in re.findall(r'R(\d+)', m.group(1)) if x in R]
        else:
            면들[지금].append(s)
    return 면들, 볼, 돌림


def 기록_폴더() -> Path:
    return Path.home() / '.claude' / 'projects' / re.sub(r'[^A-Za-z0-9]', '-', str(뿌리()))


def 도구_뜻(b: dict, 자: 자리, 파일이름: dict):
    """도구 호출이 면별 글을 찍는 것이면 '글', 호증의 면을 그림으로 여는 것이면 (기록 이름, 면들. 면을 안 정했으면 None)."""
    i = b.get('input') or {}
    경로 = nfc(str(i.get('file_path') or '')).replace('\\', '/')
    if b.get('name') == 'Read' and 경로:
        m = re.search(r'/([^/]+)/(\d+)(면|조각)\.png$', 경로)      # `그림` 이 낸 낱장
        if m and nfc(m.group(1)) in 파일이름.values():
            return nfc(m.group(1)), {int(m.group(2)) if m.group(3) == '면' else f'조각{int(m.group(2))}'}
        이름 = 파일이름.get(경로.rsplit('/', 1)[-1])
        if 이름:
            return 이름, (면_범위(str(i['pages'])) if i.get('pages') else None)
    return '글' if 자.글.name in json.dumps(i, ensure_ascii=False) else None


def 본_기록(폴더: Path, 자: 자리, 파일이름: dict) -> dict:
    """이 PC 세션 기록에서 면별 글을 찍은 도구 결과의 줄(세션별)과 그림으로 연 면(기록 이름별)을 모은다. 파일이름: 호증 파일 이름 → 기록 이름.
    세션 기록 폴더 바로 아래만 보므로 하위 작업(`{세션}/subagents/`)은 세지 않는다. 호증은 작성 세션이 직접 읽는다(루트 CLAUDE.md)."""
    줄들, 그림 = {}, {}
    for f in sorted(폴더.glob('*.jsonl')):
        도구 = {}
        with open(f, encoding='utf-8', errors='replace') as 기록:
            for line in 기록:
                if '"tool_use"' in line:
                    if 자.글.name not in line and '"Read"' not in line:
                        continue
                elif '"tool_result"' not in line or not any(x in 도구 for x in re.findall(r'"tool_use_id":\s*"([^"]+)"', line)):
                    continue
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                내용 = r['message'].get('content') if isinstance(r.get('message'), dict) else None
                for b in 내용 if isinstance(내용, list) else ():
                    if not isinstance(b, dict):
                        continue
                    if b.get('type') == 'tool_use':
                        뜻 = 도구_뜻(b, 자, 파일이름)
                        if 뜻:
                            도구[b.get('id')] = 뜻
                    elif b.get('type') == 'tool_result' and b.get('tool_use_id') in 도구 and not b.get('is_error'):
                        뜻, c = 도구[b['tool_use_id']], b.get('content')
                        if 뜻 == '글':
                            글 = c if isinstance(c, str) else '\n'.join(x.get('text', '') for x in c or [] if isinstance(x, dict))
                            남을 = 줄들.setdefault(f.stem, set())
                            for l in 글.splitlines():
                                남을.add(정규(l))
                                남을.add(정규(re.sub(r'^\s*\d+(?:\t|→|:|-)', '', l)))      # 읽기 도구·grep 의 줄 번호
                        elif isinstance(c, list) and any(isinstance(x, dict) and x.get('type') in ('image', 'document') for x in c):
                            for no in 뜻[1] or {'전체'}:
                                그림.setdefault(뜻[0], {})[no] = f.stem
    return {'줄': 줄들, '모두': set().union(*줄들.values()) if 줄들 else set(), '그림': 그림}


def 재기(자: 자리, k: str, p: Path, 본: dict) -> dict:
    """호증 하나를 잰다. 줄(화면에 나온 수, 모두), 덜 읽은 면, 열지 않은 면·조각, 통과 여부, 세션."""
    연 = 본['그림'].get(자.이름(k), {})
    if p.suffix.lower() != '.pdf':
        n = 그림_조각수(p)
        면들, 볼 = {}, {f'조각{i}' for i in range(1, n + 1)}
        if '전체' in 연 and n == 1:      # 조각이 하나인 그림은 파일을 바로 열어도 같다
            연 = {'조각1': 연['전체']}
    else:
        면들, 볼, _ = 글_읽기(자.글_파일(k).read_text(encoding='utf-8', errors='replace'))
        if '전체' in 연 and len(면들) <= 10:      # 면을 정하지 않고 PDF 를 읽기 도구로 열면 10면까지 그림으로 온다
            연 = {**{no: 연['전체'] for no in 면들}, **{a: b for a, b in 연.items() if a != '전체'}}
    합, 든, 덜, 필요 = 0, 0, [], set()
    for no, 줄 in sorted(면들.items()):
        n = sum(정규(x) in 본['모두'] for x in 줄)
        합, 든 = 합 + len(줄), 든 + n
        필요.update(정규(x) for x in 줄)
        if n < 면_통과 * len(줄):
            덜.append(no)
    못본 = sorted(볼 - set(연))
    세션 = sorted({s[:8] for s, ls in 본['줄'].items() if 필요 & ls} | {s[:8] for s in 연.values()})
    return {'합': 합, '든': 든, '덜': 덜, '볼': sorted(볼), '못본': 못본, '세션': 세션,
            '통과': not 덜 and 든 >= 줄_통과 * 합 and not 못본}


def 실측_적기(f: Path, 줄: str):
    t = f.read_text(encoding='utf-8')
    if re.search(r'^실측:.*$', t, re.M):
        t = re.sub(r'^실측:.*$', lambda _: 줄, t, count=1, flags=re.M)
    else:
        t = re.sub(r'^(읽은 방식:.*)$', lambda m: m.group(1) + '\n' + 줄, t, count=1, flags=re.M)
    f.write_text(t, encoding='utf-8')


def 면말(들: list) -> str:
    """연 것·못 연 것의 표시. 면이면 '2, 5면', 그림 조각이면 '3조각'."""
    return f'{면_표시(들)}면' if isinstance(들[0], int) else f'{len(들)}조각'


def cmd_실측(a) -> int:
    자, 목록, _ = 대상(a)
    잴 = {k: p for k, p in 목록.items() if 잴_수_있나(p)}
    if not 잴:
        print('잴 호증(자료)이 없습니다:', a.case)
        return 2
    폴더 = Path(a.기록폴더) if a.기록폴더 else 기록_폴더()
    본 = 본_기록(폴더, 자, {nfc(p.name): 자.이름(k) for k, p in 잴.items()})
    통과, 덜, 안읽음, 없음 = [], [], [], []
    for k in sorted(잴, key=호증_정렬):
        p = 잴[k]
        if not 자.기록_파일(k).is_file() or (p.suffix.lower() == '.pdf' and not 자.글_파일(k).is_file()):
            없음.append(k)
            continue
        x = 재기(자, k, p, 본)
        if x['통과']:
            통과.append(k)
            if not a.보기:
                글 = 자.글_파일(k)
                실측_적기(자.기록_파일(k), f"실측: {dt.date.today().isoformat()} · 줄 {x['든']}/{x['합']} · 그림 {면말(x['볼']) if x['볼'] else '없음'}"
                                          f" · 글 {해시(글) if 글.is_file() else '없음'} · 세션 {'·'.join(x['세션']) or '없음'}")
        elif not x['든'] and len(x['못본']) == len(x['볼']):
            안읽음.append(k)
        else:
            말 = [f"줄 {x['든']}/{x['합']}({x['든'] * 100 / max(1, x['합']):.0f}%)"]
            if x['덜']:
                말.append(f"덜 읽은 면 {면_표시(x['덜'])}")
            if x['못본']:
                말.append(f"한 장씩 열지 않은 그림 {면말(x['못본'])}")
            덜.append(f"- {자.제목(k)}: " + ', '.join(말))
    print(f"실측(세션 기록 {len(본['줄'])}개, {폴더.name}): 호증(자료) {len(잴)}건 가운데 통과 {len(통과)}건, 덜 읽음 {len(덜)}건, 읽은 기록 없음 {len(안읽음)}건"
          + (f', 기록·면별 글 없음 {len(없음)}건' if 없음 else '') + (' (보기만, 적지 않음)' if a.보기 else ''))
    for s in 덜:
        print(s)
    if 안읽음:
        print('읽은 기록 없음: ' + ', '.join(자.제목(k) for k in 안읽음[:20]) + (f' 외 {len(안읽음) - 20}건' if len(안읽음) > 20 else ''))
    if 없음:
        print('먼저 make: ' + ', '.join(자.제목(k) for k in 없음[:20]) + (f' 외 {len(없음) - 20}건' if len(없음) > 20 else ''))
    return 0 if len(통과) == len(잴) else 1


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
            새경로 = nfc(전체[새[0]].relative_to(자.사건).as_posix())
            t = re.sub(r'^파일:.*$', lambda _: f'파일: {새경로}', t, count=1, flags=re.M)
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
        옛글 = p.suffix.lower() == '.pdf' and 자.글_파일(k).is_file() and not 그림_면들(자, k)[1]      # 확인표가 없는 옛 판
        글다시 = a.글다시 == [] or k in (a.글다시 or [])
        if not a.no_text and (k in 새로 or k in 옮겨옴 or not 자.글_파일(k).is_file() or 옛글 or 글다시):
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
    print('다음: 면별 글(' + str(자.글) + ')을 면마다 끝까지 읽고, 그림으로 볼 면과 그림 호증은 `그림 --호증 {호증}` 이 그린 그림을 한 장씩 열어 '
          '읽은 뒤 면마다 끝의 확인표를 그 면 줄에 옮겨 기록을 채우고 `실측`, `check` 를 돌린다.')
    return 0


def 띠_붙여_저장(pix, 글: str, 표: str, out: Path):
    """그림 아래에 띠를 붙여 왼쪽에 호증·면을, 오른쪽 끝에 확인표를 적어 저장한다. 그림 위는 덮지 않는다.
    띠의 글자는 한 장씩 열면 읽히고 여러 장을 줄여 모으면 읽히지 않는다. 확인표는 글자 사이가 벌어지지 않게 영문 글꼴로 적는다."""
    띠 = 40
    크기 = max(14, pix.width / 75)      # 본문 작은 글자만 하게: 한 장으로 열면 읽히고, 넉 장 넘게 줄여 모으면 읽히지 않는다
    d = _ecr.pymupdf.open()
    try:
        pg = d.new_page(width=pix.width, height=pix.height + 띠)
        pg.insert_image(_ecr.pymupdf.Rect(0, 0, pix.width, pix.height), pixmap=pix)
        try:
            pg.insert_text((14, pix.height + 26), 글 + ' · 확인표', fontsize=크기, fontname='korea')
        except Exception:
            pg.insert_text((14, pix.height + 26), 'check code', fontsize=크기)
        x = pix.width - _ecr.pymupdf.get_text_length(표, fontname='hebo', fontsize=크기) - 14
        pg.insert_text((x, pix.height + 26), 표, fontsize=크기, fontname='hebo')
        pg.get_pixmap(dpi=72).save(str(out))
    finally:
        d.close()


def cmd_그림(a) -> int:
    """그림으로 볼 면(PDF)과 그림 호증을 원본에 가까운 크기로 그려 아래 띠에 확인표를 적는다. 시스템 임시 폴더에 둔다."""
    자, 목록, _ = 대상(a)
    if not 목록:
        print('읽을 호증(자료)이 없습니다:', a.case)
        return 2
    뿌리_폴더 = Path(a.out) if a.out else Path(tempfile.gettempdir()) / '증거그림' / nfc(자.사건.resolve().name)
    for k in sorted(목록, key=호증_정렬):
        p = 목록[k]
        suf = p.suffix.lower()
        if suf not in ('.pdf',) + IMAGE:
            continue
        폴더 = 뿌리_폴더 / 자.이름(k)
        폴더.mkdir(parents=True, exist_ok=True)
        for old in 폴더.glob('*.png'):
            old.unlink()
        해, 만든 = 해시(p), []
        if suf == '.pdf':
            그림, _ = 그림_면들(자, k)
            if 그림 is None:
                print(f'{자.제목(k)}: 면별 글이 없다 — 먼저 `make` 를 돌린다')
                continue
            돌림 = 글_읽기(자.글_파일(k).read_text(encoding='utf-8', errors='replace'))[2]      # 누운 스캔은 문자인식할 때 돌린 대로 세워 그린다
            d = _ecr.pymupdf.open(p)
            try:
                면 = list(range(1, len(d) + 1)) if a.전부 else sorted(a.면 or 그림)
                for no in 면:
                    if not 1 <= no <= len(d):
                        continue
                    pg = d[no - 1]
                    z = min(150 / 72, 2200 / max(pg.rect.width, pg.rect.height))
                    pix = pg.get_pixmap(matrix=_ecr.pymupdf.Matrix(z, z).prerotate(돌림.get(no, 0)))
                    out = 폴더 / f'{no:03d}면.png'
                    띠_붙여_저장(pix, f'{자.제목(k)} {no}면', 확인표(자.사건, 해, no, '그림' if no in 그림 else '글'), out)
                    만든.append(out)
            finally:
                d.close()
        else:
            n = 그림_조각수(p)
            if not n:
                print(f'{자.제목(k)}: 그림을 열지 못했다({nfc(p.name)}) — 원본을 직접 열어 읽고 \'읽은 방식\'에 적는다')
                continue
            d = _ecr.pymupdf.open(p)
            try:
                pg = d[0]
                r = pg.rect
                try:
                    폭 = _ecr.pymupdf.Pixmap(str(p)).width
                except Exception:
                    폭 = r.width
                z = min(폭, 1600) / r.width
                단 = r.width * 1.4
                for i in range(n):
                    clip = _ecr.pymupdf.Rect(0, i * 단, r.width, min(r.height, (i + 1) * 단 + 단 * 0.04))
                    pix = pg.get_pixmap(matrix=_ecr.pymupdf.Matrix(z, z), clip=clip)
                    out = 폴더 / f'{i + 1:02d}조각.png'
                    띠_붙여_저장(pix, f'{자.제목(k)} {i + 1}/{n}조각', 확인표(자.사건, 해, 1, '그림' if i == 0 else f'그림{i + 1}'), out)
                    만든.append(out)
            finally:
                d.close()
        print(f'{자.제목(k)}: {len(만든)}장 → {폴더}')
        for f in 만든:
            print(f'  {f}')
    print('다음: 그림을 한 장씩 원본 크기로 열어 읽고 그림 아래 띠의 확인표를 기록의 그 면 줄에 옮긴다. 여러 장을 줄여 모은 그림으로 보지 않는다.')
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
    print(f'전 면 읽기 기록: 호증(자료) {len(목록)}건 모두 채워졌고 실측을 마쳤다 → {자.기록}')
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='호증(자료)을 모든 면 읽었는지 기록하고 확인한다')
    sub = ap.add_subparsers(dest='cmd', required=True)
    for name in ('make', 'check', '그림', '실측'):
        s = sub.add_parser(name)
        s.add_argument('case')
        s.add_argument('--자료', nargs='+', help='호증 번호 없는 자료 폴더(검토의견의 첨부 등)')
        s.add_argument('--호증', nargs='+', help='이 호증키(사6)나 머리글자(사 노)만')
        if name == 'make':
            s.add_argument('--다시', nargs='+', help='파일이 바뀐 이 호증키의 기록을 새로 짠다(앞선 기록은 끝에 옮겨 둔다)')
            s.add_argument('--글다시', nargs='*', help='면별 글만 지금 판으로 다시 낸다(호증키를 안 주면 모두). 읽은 뒤에 다시 내면 실측을 다시 해야 한다')
            s.add_argument('--no-ocr', action='store_true')
            s.add_argument('--no-text', action='store_true', help='면별 글을 만들지 않는다')
        if name == '그림':
            s.add_argument('--면', nargs='+', type=int, help='이 면만(PDF). 주지 않으면 그림으로 볼 면')
            s.add_argument('--전부', action='store_true', help='PDF 의 모든 면을 그린다(글 면도 그림으로 읽을 때)')
            s.add_argument('--out', help='그림을 둘 폴더(주지 않으면 시스템 임시 폴더. OneDrive 에 쌓지 않는다)')
        if name == '실측':
            s.add_argument('--보기', action='store_true', help='재기만 하고 기록에 적지 않는다')
            s.add_argument('--기록폴더', help='세션 기록 폴더(시험용)')
    a = ap.parse_args(argv)
    return {'make': cmd_make, 'check': cmd_check, '그림': cmd_그림, '실측': cmd_실측}[a.cmd](a)


if __name__ == '__main__':
    raise SystemExit(main())
