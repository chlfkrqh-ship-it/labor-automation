"""호증(자료)을 모든 면 읽었는지 기록하고 기계로 확인한다 — 증거 '파악'의 관문(`.claude/commands/증거정리.md` 3단계).

    python -B 4_서면작성/scripts/evidence_read.py make  "<사건 폴더>" [--호증 사6 노 ...] [--no-ocr] [--no-text]
    python -B 4_서면작성/scripts/evidence_read.py make  "<사건 폴더>" --다시 사6        # 파일이 바뀐 호증의 기록을 새로 짠다
    python -B 4_서면작성/scripts/evidence_read.py check "<사건 폴더>" [--호증 ...]
    python -B 4_서면작성/scripts/evidence_read.py 그림  "<사건 폴더>" --호증 을105-8 [--면 3 7] [--전부]   # 그림으로 볼 면을 확인표와 함께 연다
    python -B 4_서면작성/scripts/evidence_read.py 실측  "<사건 폴더>" [--호증 ...] [--보기]   # 세션 기록으로 실제 읽은 줄을 재어 기록에 적는다
    python -B 4_서면작성/scripts/evidence_read.py 계획  "<사건 폴더>" [--창 200000]        # 아직 읽지 않은 호증의 양을 어림해 창을 나눈다
    python -B 4_서면작성/scripts/evidence_read.py make  "<사건 폴더>" --글다시 [사6 ...]    # 면별 글만 지금 판으로 다시 낸다(기록의 면별 내용은 그대로)
    python -B 4_서면작성/scripts/evidence_read.py make  "1_검토의견/사건/{의뢰인}_{검토내용}" --자료 "<첨부 폴더>"   # 호증 번호 없는 자료

make  서면 사건은 호증마다(우리·상대, PDF 가 아닌 원자료 포함) `증거관리/호증읽기/{호증키}.md` 틀을 만든다. 호증 번호가 없는 상대방 서면,
      참고자료(인용판결_PDF 의 판결문 포함), 노동위원회_기록의 서면도 '라운드2 상대 {파일 이름}' 같은 키로 같이 만든다. 틀에는 파일·해시·단위 수와
      단위마다 빈 줄(PDF·그림은 '- 3면:', 압축파일은 '- [파일] 이름:', 엑셀은 '- [시트] 이름:', 그 밖은 '- 전체:')이 있다.
      PDF 는 면별 글(글자층, 없거나 깨지면 Windows 문자인식)을 `증거관리/호증글자/{호증키}.txt` 에 낸다.
      압축·엑셀·워드·한글·파워포인트·메일·텍스트도 단위마다 글을 뽑아 같은 자리에 낸다(`evidence_text.py`). 글은 3,000자 안팎의
      덩이로 나누어 덩이 끝에, 압축·첨부 안의 PDF 는 면 끝에 확인표를 붙이고, 그림(압축 안 그림 파일, 문서·시트·메일에 든 그림)은
      `그림` 으로 열게 한다. 옛 형식 .doc·.xls 는 워드·엑셀(없으면 LibreOffice)로 .docx·.xlsx 로 바꾸어 읽고, .hwp 는 한글이 있는
      PC에서 PDF 로 바꾸어 면마다 읽는다.
      `--자료` 를 주면 그 폴더의 파일마다 `작업/자료읽기/{파일 이름}.md` 와 `작업/자료글자/{파일 이름}.txt` 를 만든다.
      호증 번호를 다시 매겨 기록의 호증키와 파일이 어긋나면, 해시가 같은 파일의 호증키로 기록을 옮긴다.
check 모든 호증(자료)에 기록이 있는지, 기록한 뒤 파일이 바뀌지 않았는지(해시), 모든 단위가 채워졌는지, '읽은 방식'과
      '쟁점에 닿는 문구'가 적혔는지, 그림으로 볼 면(끼운 그림이 있는 면 포함)을 그림으로 읽었는지, 면마다 확인표가 맞는지,
      다 읽지 않았다는 표현(모음 그림, '…중심으로 읽음')이 없는지, '실측:' 줄이 있고 그 뒤 면별 글이 바뀌지 않았는지(소리·영상과
      열리지 않는 그림 말고 모두) 본다. 하나라도 어긋나면 종료 코드 1 이다.
그림  그림으로 볼 면(스캔한 표, 사진, 문자인식이 깨진 면, 글자층 면에 끼운 표·발췌 그림)과 그림 호증, 압축·문서·메일 안의 그림을
      원본에 가까운 크기로 그려 아래 띠에 확인표를 적어 시스템 임시 폴더에 둔다(OneDrive 에 쌓지 않는다). 작성 세션은 그 그림을 한 장씩 열어 읽는다.
실측  이 PC 세션 기록에서 면별 글을 찍은 도구 결과의 줄과 한 장씩 연 그림을 모아 호증마다 잰다. 줄의 98%, 면(압축·엑셀·문서는 단위)마다 90%
      이상이 화면에 나왔고 그림으로 볼 면과 압축·문서 안의 그림을 모두 열었으면 기록에 '실측:' 줄을 적는다. 거른 줄과 확인표만 찍으면 모자라게
      나오고, 모음 그림과 하위 작업의 기록은 세지 않는다.
      세션 기록은 PC 마다 따로이고 열흘이 지나면 지워지므로 읽은 그 PC 에서 바로 돌린다.
계획  아직 실측을 마치지 않은 호증의 읽을 양(면별 글의 글자·줄, 한 장씩 열 그림)을 토큰으로 어림해 한 창에 상한만큼씩 나눈다. 실측은 세션
      기록을 모두 합쳐 재므로 창을 나누어 읽어도 된다. 한 창의 문맥이 커질수록 턴마다 같은 글을 다시 읽어 사용량이 커진다
      (2026. 11. 3. 노정일 호증을 한 창에서 다시 읽다가 문맥이 약 82만 토큰까지 찼다).

확인표: 면별 글의 면마다 끝에 '[3면 끝 · 확인표 K7QF]'가 있고, 그림으로 볼 면은 `그림` 이 그린 그림 아래 띠에 있다. 그 면을 끝까지 열어
본 세션만 알 수 있으므로 기록의 그 면 줄('- 3면: … 확인표 K7QF')에 옮겨 적는다. 묶은 줄('- 5~9면:')에는 그 면들의 확인표를 모두 적는다.
PDF 가 아닌 호증은 단위 줄('- [파일] 이름:', '- [시트] 이름:', '- 전체:')에 그 단위의 덩이·면·그림 확인표를 모두 적는다. 면별 글 머리의
'확인표 단위:' 목록이 단위마다 몇 개가 있어야 하는지 보여 준다. 뽑지 못한 문서(한글이 없는 PC의 .hwp, 머리 서명이 한글 문서가 아닌 .hwp,
머리 서명이 워드·엑셀 문서가 아닌 .doc·.xls, 글자로 풀리지 않는 .txt·.csv, 그리지 못한 문서 안 그림)는 막히고, 같은 폴더에 같은 이름의
PDF 를 두면 그 PDF 를 면마다 읽는 것으로 갈음한다. 소리·영상과 열리지 않는 그림 파일만 '읽은 방식'의 신고로 본다.
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
같은 날 SR노조 통상임금 리서치: 글자층 면에 끼운 그림(판결의 단체협약·노사합의 표와 별지 표, 서면의 판결 발췌 박스)은 그림이 면의 25% 를
넘지 않으면 그림으로 볼 면이 되지 않아, 그 그림 속 글이 면별 글에 없는데도 check·실측이 지났다(판결 9건, 초안 11면, 피고 서면 1면).
끼운 그림을 따로 세어 표시하고, 그 전에 낸 면별 글은 PDF 에서 바로 재어 그 면을 그림으로 읽었는지와 실측이 그 면을 쟀는지 본다.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import os
import io
import math
import re
import shutil
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
_spec = importlib.util.spec_from_file_location('evidence_text', Path(__file__).resolve().parent / 'evidence_text.py')
_et = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_et)

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


def PDF_면수(p: Path) -> int:
    """PDF 의 면 수. 비었거나 깨져 열리지 않으면 0."""
    try:
        d = _ecr.pymupdf.open(p)
    except Exception:
        return 0
    try:
        return len(d)
    finally:
        d.close()


def 단위들(p: Path) -> list:
    """읽을 단위. PDF 는 면 번호(int), 그림은 [1], 압축파일은 '[파일] 이름', 엑셀은 '[시트] 이름', 그 밖은 ['전체']."""
    suf = p.suffix.lower()
    if suf == '.pdf':
        n = PDF_면수(p)
        return list(range(1, n + 1)) if n else ['전체']      # 열리지 않는 PDF 는 한 단위로 두고 check 가 막는다
    if suf in IMAGE:
        return [1]
    if suf == '.zip':
        try:
            with zipfile.ZipFile(p) as z:
                return [f'[파일] {n}' for n, _ in _et.zip_목록(z)] or ['전체']
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


def 서면류_파일(p: Path, 뿌리_: Path) -> bool:
    """읽을 문서인가. 임시 파일과 작업·백업·원고별 정리 폴더의 것은 뺀다(노동위원회_기록의 우리 서면도 읽는다)."""
    return (p.is_file() and not p.name.startswith('~$') and p.name.lower().endswith(DOCS)
            and not any(x in ('작업', '백업', '원고별 정리') for x in p.relative_to(뿌리_).parts[:-1]))


def 서면_자료(사건: Path, 호증: dict) -> dict:
    """호증 번호가 없는 서면과 참고자료. 키 → 파일. `/서면` 1단계에서 모두 읽는다고 한 것 가운데 호증이 아닌 것이다.
    라운드마다 상대증거/ 의 상대방 서면(판정서·결정문 포함), 참고자료/ 전체(인용판결_PDF 의 판결문, 타 사건 자료), 노동위원회_기록/ 의
    우리·상대 서면. 호증과 같은 파일(해시)은 두 번 읽지 않게 뺀다. 키는 '라운드2 상대 {파일 이름}', '라운드2 참고 {파일 이름}',
    '노동위 {파일 이름}' 꼴이다(같은 이름이 또 있으면 폴더 이름을 붙인다).
    2026. 11. 3. 담당 노무사 "위와 같은 완결성 원칙은 시스템 전반에 적용되는거지?" — 그때까지 확인표·실측은 호증에만 걸려 있었다."""
    호증해시 = {해시(p) for p in 호증.values()}
    out = {}

    def 넣기(앞: str, p: Path):
        k = nfc(f'{앞} {p.name}')
        if k in out:
            k = nfc(f'{앞} {p.parent.name}_{p.name}')
        out[k] = p

    for 라운드 in sorted((x for x in 사건.glob('라운드*') if x.is_dir()), key=lambda x: int(re.sub(r'\D', '', x.name) or 0)):
        n = re.sub(r'\D', '', 라운드.name) or '0'
        for 폴더, 말 in (('상대증거', '상대'), ('참고자료', '참고')):
            d = 라운드 / 폴더
            if not d.is_dir():
                continue
            for p in sorted(d.rglob('*')):
                if 서면류_파일(p, d) and not (폴더 == '상대증거' and _ecr.file_key(p.name)) and 해시(p) not in 호증해시:
                    넣기(f'라운드{n} {말}', p)
    d = 사건 / '노동위원회_기록'
    if d.is_dir():
        for p in sorted(d.rglob('*')):
            if 서면류_파일(p, d) and not _ecr.file_key(p.name) and 해시(p) not in 호증해시:
                넣기('노동위', p)
    return out


# 판 이름(관련 검토, _수정(…), _최종, _Rev_N, _초안, _간이안)은 우리 산출물의 이름 꼴 '(약칭) …'(앞에 송부일 '261013_' 이 붙기도 한다)에만
# 건다. 2026. 11. 5. 삼양인터내셔날 후속 검토에서 의뢰인이 보낸 '답변서_최종.docx' 가 자료 목록에서 빠져 찾았다. 건보공단 임금협약서_최종 4건,
# HPS 관리운영계약서_최종, SR노조 영업양수도계약서_초안 도 같은 까닭으로 빠져 있었다. '(주)' 같은 법인 표시는 약칭이 아니다.
우리_이름꼴 = r'^(?:\d{6}_)?\((?!(?:주|유|사|재|합)\))[^()]+\) '
산출물_이름 = re.compile(r'(-회신초안|-간이안)\.md$'
                    rf'|{우리_이름꼴}.*(?:관련 검토[_.]|_수정\(|_최종|_Rev_\d|_초안\.(?:docx|pdf)$|_간이안\.(?:docx|pdf)$)'
                    r'|_노동금액계산표|^검산_|^_추출\.txt$'
                    r'|^\(리서치\)')      # 우리 리서치 문서(`2_판례검색/양식/(리서치) …`). 2026. 11. 5. 이케아 견적에서 의뢰인 자료로 셌다
우리_폴더 = re.compile(r'^(?:작업|백업|계산|전환작업|빌드)$|^별첨_|^법제처')


def 자료_목록(사건: Path, 폴더들: list) -> dict:
    """자료 이름 → 파일. 이름은 파일 이름(확장자 포함)이고, 같은 이름이 여럿이면 폴더 이름을 앞에 붙인다.
    우리가 만든 산출물(검토의견서·회신초안·수정본, `1_검토의견/CLAUDE.md` 6절의 이름, 엔진이 만든 계산표)과
    작업·계산·백업·전환작업(Word 변환 부품)·별첨(붙이려고 받은 판결·회시)·법제처 수확 폴더는 뺀다. 상대방의 별지 계산표는 자료이다.
    다만 인용한 판결문(작업/인용판결_PDF)은 인정사실까지 전문을 읽어야 하므로 넣는다(루트 CLAUDE.md '판례 인용과 증거 인용')."""
    out = {}
    for d in 폴더들:
        d = Path(d)
        for p in sorted(d.rglob('*')):
            if not p.is_file() or p.name.startswith('~$') or not p.name.lower().endswith(DOCS) or 산출물_이름.search(p.name):
                continue
            if any(우리_폴더.search(x) for x in p.relative_to(d).parts[:-1]) and p.relative_to(d).parts[:-1] != ('작업', '인용판결_PDF'):
                continue      # 우리 작업 폴더는 빼되, 검토의견에 인용한 판결문(작업/인용판결_PDF)은 전문을 읽는다
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
    """단위 → 그 단위 줄에 있어야 할 확인표들. PDF·그림 호증·압축·엑셀·문서·메일을 본다. 소리·영상과 열지 못한 그림 호증,
    면별 글이 없는 것은 None 이다(소리·영상과 열지 못한 그림은 읽은 방식의 신고로 보고, 면별 글이 없으면 따로 막는다)."""
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
    if suf in 기타_꼴 and 기타_새판(자, k, p):
        해, 기대 = 해시(p), {}
        for it in 목록_읽기(자.글_파일(k).read_text(encoding='utf-8', errors='replace')):
            u, 경로 = it['단위'], it['경로']
            if it['갈래'] == '글':
                기대.setdefault(u, []).extend(확인표(자.사건, 해, 키(u, 경로, f'덩이{i}'), '글') for i in range(1, it['수'] + 1))
            elif it['갈래'] == '그림':
                기대.setdefault(u, []).extend(확인표(자.사건, 해, 키(u, 경로, f'그림{i}'), '그림') for i in range(1, it['수'] + 1))
            elif it['갈래'] == '면':
                기대.setdefault(u, []).extend(확인표(자.사건, 해, 키(u, 경로, f'{j}면'), 종) for j, 종 in enumerate(it['종류'], 1))
        return 기대
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
        본 = 그림_본_면(r['방식'], len(units))
        못본 = sorted(볼 - 본)
        if 못본:
            out.append(f"그림으로 볼 면 {면_표시(못본)}면을 그림으로 본 기록이 없다('읽은 방식'에 '그림 {'·'.join(map(str, 못본[:5]))}면'처럼 적는다)")
        끼운 = sorted(끼운_면(자, k, p) - 볼 - 본)      # 끼운 그림을 표시하기 전에 낸 면별 글의 그 면
        if 끼운:
            out.append(f"끼운 그림(글자층 면에 든 표·발췌 그림)이 있는 면 {면_표시(끼운)}면을 그림으로 본 기록이 없다 — 그 그림 속 글은 면별 글에 없다. "
                       f"`evidence_read.py 그림 --호증 \"{k}\"` 이 그린 낱장을 한 장씩 열어 읽고 그 면 줄에 그림 속 글을 적은 뒤 "
                       f"'읽은 방식'에 '그림 {'·'.join(map(str, 끼운[:5]))}면'처럼 적는다")
    if not r['문구']:
        out.append("'쟁점에 닿는 문구'가 비었다(원문 그대로와 면. 없으면 '없음')")
    text = f.read_text(encoding='utf-8')
    if p.suffix.lower() == '.pdf' and not PDF_면수(p):
        out.append('PDF 가 비었거나 깨져 열리지 않는다 — 원본을 다시 받아 같은 이름으로 두고 `make --다시` 로 새로 짠다')
        return out
    if p.suffix.lower() == '.pdf':
        그림, 새판 = 그림_면들(자, k)
        if 그림 is None:
            out.append('면별 글이 없다 — `make` 로 만들고 면마다 끝까지 읽는다(면 끝의 확인표를 기록에 옮긴다)')
        elif not 새판:
            out.append('면별 글이 확인표가 없는 옛 판이다 — `make` 를 다시 돌려 새로 쓰고 면마다 다시 읽어 확인표를 옮긴다')
    elif p.suffix.lower() in 기타_꼴:
        if not 자.글_파일(k).is_file():
            out.append('면별 글이 없다 — `make` 로 만들고 단위마다 끝까지 읽는다(덩이·면 끝의 확인표를 기록에 옮긴다)')
        elif not 기타_새판(자, k, p):
            out.append('면별 글이 확인표가 없는 옛 판이거나 바뀌기 전 파일의 것이다 — `make` 를 다시 돌려 새로 쓰고 다시 읽는다')
        else:
            못 = [it['단위'] + (' › ' + '›'.join(it['경로']) if it['경로'] else '') + f"({it['까닭']})"
                 for it in 목록_읽기(자.글_파일(k).read_text(encoding='utf-8', errors='replace')) if it['갈래'] == '모름' and it['문서']]
            대신 = next((q for q in p.parent.glob('*.pdf') if nfc(q.stem) == nfc(p.stem)), None) if p.suffix.lower() != '.zip' else None
            if 못 and 대신 is None:      # 같은 이름의 PDF 가 있으면 그 PDF 를 면마다 읽는다(자료 모드. 서면 사건은 PDF 가 그 호증이 된다)
                out.append('글을 뽑지 못한 곳: ' + '; '.join(못) + ' — ' + (
                    '압축을 풀어(암호는 받아서) 안의 파일을 따로 두거나 한글·LibreOffice 가 있는 PC에서 `make` 를 다시 돌린다'
                    if p.suffix.lower() == '.zip' else
                    '한글·LibreOffice 가 있는 PC에서 `make` 를 다시 돌리거나, 같은 폴더에 같은 이름의 PDF 로 저장해 두고 그 PDF 를 읽는다'
                    '(서면 사건은 PDF 가 그 호증으로 읽힌다)'))
    기대 = 기대_확인표(자, k, p)
    if 기대:
        줄들 = 단위_줄들(text)
        틀린 = [u for u, toks in 기대.items()      # 띄어 옮겨도('F Q U G') 맞게 본다
              if not all(x in re.sub(r'\s', '', ' '.join(c for us, c in 줄들 if u in us)).upper() for x in toks)]
        if 틀린:
            표시 = f'면 {len(틀린)}/{len(기대)}: {면_표시(틀린)}면' if all(isinstance(u, int) for u in 틀린) else \
                f"단위 {len(틀린)}/{len(기대)}: {', '.join(map(str, 틀린))}"
            out.append(f"확인표가 없거나 맞지 않는 {표시} — 면별 글은 그 면·덩이 끝까지 읽고, 그림으로 볼 면과 그림은 "
                       f"`evidence_read.py 그림` 이 그린 그림을 한 장씩 열어 끝의 확인표를 그 단위 줄에 모두 옮긴다(줄을 걸러 읽거나 모음 그림으로 갈음하지 않는다)")
    거른 = [m.group(0) for 줄 in [r['방식']] + [c for _, c in 단위_줄들(text)] for m in [거른말.search(줄)] if m]
    if 거른:
        말들 = "', '".join(dict.fromkeys(거른))
        out.append(f"다 읽지 않았다는 표현이 있다('{말들}') — 그 면을 처음부터 끝까지 읽고 기록을 고친다. "
                   '모음 그림은 글자를 읽을 수 없어 읽은 것으로 치지 않는다')
    return out + 실측_문제(자, k, p, text)


def 잴_수_있나(p: Path) -> bool:
    """세션 기록으로 잴 수 있는 호증인가. 면별 글이 있는 PDF·압축·엑셀·문서·메일과 열리는 그림이고, 소리·영상은 재지 않는다(녹취록으로 읽는다)."""
    return p.suffix.lower() in ('.pdf',) + 기타_꼴 or (p.suffix.lower() in IMAGE and 그림_조각수(p) > 0)


def 실측_문제(자: 자리, k: str, p: Path, 기록: str) -> list:
    """기록에 '실측:' 줄이 있고 그 뒤 면별 글이 바뀌지 않았는지, 실측이 그림으로 볼 면(끼운 그림이 있는 면 포함)을 모두 쟀는지.
    재는 일은 `실측` 이 한다."""
    if not 잴_수_있나(p):
        return []
    m = re.search(r'^실측:(.*)$', 기록, re.M)
    if not m:
        return ['실제로 읽은 기록(실측)이 없다 — 면별 글을 읽기 도구로 끝까지 읽고(줄을 거르지 않는다) 그림으로 볼 면을 한 장씩 연 뒤 `실측` 을 돌린다']
    글 = 자.글_파일(k)
    if p.suffix.lower() in ('.pdf',) + 기타_꼴 and 글.is_file() and f'글 {해시(글)}' not in m.group(1):
        return ['실측한 뒤 면별 글이 바뀌었다 — 지금 면별 글을 읽고 `실측` 을 다시 돌린다']
    if p.suffix.lower() == '.pdf':      # 면별 글에 표시된 그림 면은 그 글을 잰 실측이 쟀다(글 해시). 표시 전에 낸 면별 글의 끼운 그림 면만 본다
        잰 = re.search(r'· 그림 (.*?) · 글 ', m.group(1))
        잰 = 면_범위(잰.group(1)) if 잰 and 잰.group(1) != '없음' else set()
        덜 = sorted(끼운_면(자, k, p) - (그림_면들(자, k)[0] or set()) - 잰)
        if 덜:
            return [f'실측이 끼운 그림이 있는 면 {면_표시(덜)}면을 재지 않았다(끼운 그림을 표시하기 전의 실측) — 그 면을 `그림` 이 그린 '
                    '낱장으로 한 장씩 열어 읽고 `실측` 을 다시 돌린다']
    return []


# ---------------------------------------------------------------- 면별 글
끼운_문턱 = 0.003     # 글자층 면에 끼운 그림으로 볼 넓이(면의 0.3% 초과). 서명·관인·작은 로고·아이콘은 거른다
선_폭 = 8             # 짧은 변이 8pt 가 안 되는 그림은 선·음영 띠로 보고 뺀다(피고 서면 제목 아래 띠 467×6pt)


def 면_상자(page):
    """그림·낱말 좌표와 같은(돌리기 전) 면 상자. 돌린 면의 page.rect 는 가로세로가 바뀌어 있다."""
    return page.rect * page.derotation_matrix


def 그림_비율(page) -> float:
    """글자층 면에서 그림(사진·도표)이 차지하는 넓이 비율."""
    try:
        상자 = 면_상자(page)
        area = abs(상자)
        return min(1.0, sum(abs(_ecr.pymupdf.Rect(i['bbox']) & 상자) for i in page.get_image_info()) / area) if area else 0.0
    except Exception:
        return 0.0


def 끼운_그림(doc, 면들=None) -> dict:
    """글자층 면(면들, 주지 않으면 모든 면)마다 끼운 그림 {면: 가장 큰 그림이 면에서 차지하는 비율}. 글자층 면에 끼운 표·발췌·캡처
    그림은 그 속 글이 글자층에 없다. 빼는 것: 되풀이되는 같은 그림(같은 그림이 본 면 가운데 2면 이상이고 그 절반 이상: LBOX 워터마크,
    머리글·바닥글 로고. 같은 그림은 파일 안 그림 스트림이 같은 것이고, 가리지 못하면 화소 크기와 자리가 같은 것), 글자층 낱말이 위에 놓인
    투명 그림(한 면짜리 문서의 워터마크), 면 바닥 가운데의 작은 표시(전자소송 서증 표시·쪽 번호), 선·음영 띠(짧은 변 8pt 미만),
    작은 그림(면의 0.3% 이하: 서명·관인·아이콘). 그림 정보는 xref 없이 읽는다(xref 를 붙이면 그림마다 풀어 117면 스캔본이 53초 걸린다)."""
    면들 = sorted(no for no in (면들 if 면들 is not None else range(1, len(doc) + 1)) if 1 <= no <= len(doc))
    후보, 놓인, 지문 = {}, {}, {}
    for no in 면들:
        pg = doc[no - 1]
        상자 = 면_상자(pg)
        넓이 = abs(상자)
        try:
            inf = pg.get_image_info() if 넓이 else []
            든 = pg.get_images(full=True) if inf else []
        except Exception:
            continue
        낱말 = None
        for i in inf:
            r = _ecr.pymupdf.Rect(i['bbox']) & 상자
            비율 = abs(r) / 넓이
            if r.is_empty or min(r.width, r.height) < 선_폭 or 비율 <= 끼운_문턱:
                continue
            같은 = [x for x in 든 if x[2] == i['width'] and x[3] == i['height']]
            xref, 투명 = (같은[0][0], bool(같은[0][1])) if len(같은) == 1 else (0, False)
            if xref and 비율 < 0.25 and xref not in 지문:      # 면의 25% 넘는 그림은 '사진·도표 있음'으로 이미 그림으로 볼 면이다
                try:
                    지문[xref] = hashlib.sha1(doc.xref_stream_raw(xref)).hexdigest()
                except Exception:
                    지문[xref] = f'xref {xref}'
            b = i['bbox']
            열쇠 = 지문.get(xref) or (i['width'], i['height'], *(round(v / 4) for v in b))
            놓인.setdefault(열쇠, set()).add(no)      # 되풀이는 아래에서 빼는 것까지 모두 센다(글자와 겹친 면의 워터마크도)
            보임, 면 = r * pg.rotation_matrix, pg.rect      # 보이는 방향(가로 면·돌린 면도 바닥은 보이는 바닥이다)
            if 보임.height <= 30 and 보임.y0 >= 면.y1 - 72 and abs((보임.x0 + 보임.x1) - (면.x0 + 면.x1)) <= 면.width * 0.2:
                continue      # 면 바닥 가운데의 작은 표시(전자소송 서증 표시 '갑 제3호증' 115×20pt 는 바닥에서 50pt 위, 쪽 번호)
            if 투명:
                낱말 = pg.get_text('words') if 낱말 is None else 낱말
                if any(r.contains(_ecr.pymupdf.Point((w[0] + w[2]) / 2, (w[1] + w[3]) / 2)) for w in 낱말):
                    continue
            후보.setdefault(no, []).append((열쇠, 비율))
    되풀이 = {k for k, s in 놓인.items() if len(s) >= 2 and len(s) * 2 >= len(면들)}
    out = {}
    for no, xs in 후보.items():
        크기 = [a for k, a in xs if k not in 되풀이]
        if 크기:
            out[no] = max(크기)
    return out


def 글자층_면(글: str) -> set:
    """면별 글에서 글자층으로 읽은 면."""
    return {int(x) for x in re.findall(r'^=== (\d+)면 \(글자층', 글, re.M)}


_끼운_캐시 = {}


def 끼운_면(자: 자리, k: str, p: Path) -> set:
    """PDF 호증에서 끼운 그림이 있어 그림으로 볼 면(글자층으로 읽은 면만). 끼운 그림을 표시하기 전(2026. 11. 3.)에 낸 면별 글에는
    그 표시가 없으므로 면별 글의 표시와 따로 PDF 에서 바로 잰다. 확인표는 면별 글의 표시를 따른다(옛 면별 글의 그 면은 '글' 확인표).
    면별 글이 없거나 PDF 가 아니면 빈 집합."""
    f = 자.글_파일(k)
    if p.suffix.lower() != '.pdf' or not f.is_file():
        return set()
    층 = 글자층_면(f.read_text(encoding='utf-8', errors='replace'))
    if not 층:
        return set()
    열쇠 = (str(p.resolve()), p.stat().st_mtime_ns, p.stat().st_size, frozenset(층))
    if 열쇠 not in _끼운_캐시:
        try:
            d = _ecr.pymupdf.open(p)
        except Exception:
            return set()
        try:
            _끼운_캐시[열쇠] = set(끼운_그림(d, 층))
        finally:
            d.close()
    return set(_끼운_캐시[열쇠])


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


# ---------------------------------------------------------------- PDF 가 아닌 호증(압축·엑셀·문서·메일)
기타_꼴 = ('.zip', '.xlsx', '.xlsm', '.xls', '.docx', '.docm', '.doc', '.hwp', '.hwpx', '.pptx', '.txt', '.csv', '.eml', '.msg')
소리_꼴 = ('.mp3', '.m4a', '.wav', '.mp4', '.mov')
목록_머리 = '확인표 단위: '
가름 = ' ⟶ '
글판 = 3      # 글을 뽑는 방식(evidence_text.py, 아래 파일_항목)이 바뀌어 면별 글의 내용이 달라지면 올린다.
              # 2: 옛 형식 .doc·.xls 를 PDF 대신 .docx·.xlsx 로 바꾸어 읽는다(숨긴 시트·행·메모가 빠지지 않게)
              # 3: 1,000자 넘는 줄을 나눈다(읽기 도구가 2,000자 넘는 줄을 잘라 보여 주어 실측이 지나가지 못한다)
              # 옛 면별 글은 make 가 새로 쓰고, 옛 확인표는 맞지 않게 되어 그 호증을 다시 읽게 된다


def 키(u: str, 경로: list, 조각: str) -> str:
    """단위 안 항목의 확인표 열쇠. 경로는 호증 파일에서 그 항목까지(압축 안 파일, 문서 안 그림, 메일 첨부)."""
    return f'{글판}|{u}|{"›".join(경로)}|{조각}'


def 파일_항목(자: 자리, k: str, 이름: str, data: bytes, 경로: list, use_ocr: bool, 깊이: int = 0) -> list:
    """파일 하나에서 읽을 항목들. 글은 덩이로, 그림은 조각 수로, PDF 는 면마다(그림으로 볼 면 표시), 뽑지 못하면 그 까닭."""
    ext = Path(이름).suffix.lower()
    out = []

    def 글(x: str, 빈: str, 그림=()):
        작음 = sum(1 for g in 그림 if g['갈래'] == '작음')
        if 작음:      # 빼고 여는 그림이 있다는 것도 읽는 사람이 알게 글에 적는다
            x += f'\n[작은 그림 {작음}개(64×64 화소 미만: 아이콘·글머리표)는 따로 열지 않는다]'
        out.append({'갈래': '글', '경로': 경로, '덩이': _et.덩이로(x) or [빈]})
        그림들(그림)

    def 그림들(gs):
        for g in gs:
            if g['갈래'] == '그림':
                out.append({'갈래': '그림', '경로': 경로 + [g['이름']], '조각': g['조각']})
            elif g['갈래'] == '못 엶':
                out.append({'갈래': '모름', '경로': 경로 + [g['이름']], '문서': True,
                            '까닭': f'문서 안의 {g["ext"]} 그림을 그리지 못했다(문서를 PDF 로 저장해 그 PDF 로 읽는다)'})

    def 모름(까닭: str, 문서: bool = True):
        out.append({'갈래': '모름', '경로': 경로, '까닭': 까닭, '문서': 문서})

    try:
        if ext in ('.doc', '.xls'):      # 새 형식으로 바꾸어 같은 방식으로 읽는다(숨긴 시트·메모·지운 글까지)
            판 = _et.오피스_판(data, ext)
            if 판 == '글':      # 쉼표·탭으로 나눈 글을 .xls 로 저장한 것 등. 변환기를 거치면 cp949·UTF-8 이 깨지므로 바로 읽는다
                글(_et.글자_풀기(data), '(빈 파일)')
                return out
            if not 판:      # 변환기가 맞지 않는 바이트를 글 문서로 열어 만든 엉터리 글을 읽은 것으로 치던 것(2026. 11. 3.)
                모름(f'{ext} 이름이지만 머리 서명이 {"워드" if ext == ".doc" else "엑셀"} 문서가 아니다(깨졌거나 암호가 걸렸거나 다른 형식의 '
                    '파일이다. 원본을 열어 보고 PDF 로 저장해 둔다)')
                return out
            b = _et.새형식(이름, data)
            if not b:
                모름(f'{ext} 를 바꾸지 못했다(워드·엑셀이나 LibreOffice 가 있는 PC에서 make 를 다시 돌리거나 PDF 로 저장해 둔다)')
                return out
            data, ext = b, '.docx' if ext == '.doc' else '.xlsx'
        if ext == '.pdf':
            with _et.임시_폴더() as d:
                f = Path(d) / 'a.pdf'
                f.write_bytes(data)
                열쇠 = f'{자.이름(k)}_{hashlib.sha1("›".join(경로).encode("utf-8")).hexdigest()[:8]}'
                면들, 그림 = 면_분석(자, 열쇠, f, use_ocr)
            out.append({'갈래': '면', '경로': 경로, '면': [('그림' if no in 그림 else '글', src, 그림.get(no, ''),
                                                         '\n'.join(x for t in 줄들 + 표 for x in _et.긴줄_나누기(t)))
                                                        for no, src, 줄들, 표 in 면들]})
        elif ext in IMAGE + _et.바꿀_그림_꼴:
            열 = _et.열_그림(data, ext)
            if 열:
                out.append({'갈래': '그림', '경로': 경로, '조각': _et.조각수(*_et.그림_크기(*열))})
            else:      # 그림 호증을 열지 못한 것과 같이 다룬다(원본을 그림 보기로 열어 읽고 그 줄에 적는다)
                모름(f'{ext} 그림을 열지 못했다(원본을 그림 보기로 열어 읽고 그 줄에 적는다)', 문서=False)
        elif ext in ('.docx', '.docm'):
            r = _et.docx_글(data)
            글(r['글'], '(글 없음)', r['그림'])
        elif ext in ('.xlsx', '.xlsm'):
            r = _et.xlsx_시트들(data)
            글('\n'.join(f'[시트] {n}' + (' (숨긴 시트)' if h else '') + '\n' + x for n, x, h, _ in r['시트']), '(빈 통합 문서)', r['그림'])
        elif ext == '.pptx':
            r = _et.pptx_슬라이드(data)
            글('\n'.join(f'[슬라이드 {i}]\n{x}' for i, x in enumerate(r['슬라이드'], 1)), '(빈 발표 자료)', r['그림'])
        elif ext == '.hwpx':
            r = _et.hwpx_글(data)
            글(r['글'], '(글 없음)', r['그림'])
        elif ext in ('.txt', '.csv'):
            t = _et.글자_풀기(data)
            if t is None:      # 끝내 latin-1 로 풀어 깨진 파일도 읽은 것으로 치던 것(2026. 11. 3.)
                모름(f'{ext} 이름이지만 글자로 된 파일이 아니다(깨졌거나 다른 형식의 파일이다. 원본을 열어 보고 PDF 로 저장해 둔다)')
            else:
                글(t, '(빈 파일)')
        elif ext == '.eml':
            r = _et.eml_글(data)
            글(r['글'], '(빈 메일)')
            for n, b in r['첨부']:
                out.extend(파일_항목(자, k, n, b, 경로 + [n], use_ocr, 깊이 + 1) if 깊이 < 3 else
                           [{'갈래': '모름', '경로': 경로 + [n], '까닭': '첨부가 너무 깊이 들어 있다(풀어서 따로 둔다)', '문서': True}])
        elif ext == '.zip':
            if 깊이 >= 3:
                모름('압축이 너무 깊이 들어 있다(풀어서 따로 둔다)')
            else:
                with zipfile.ZipFile(io.BytesIO(data)) as z:
                    for n, info in _et.zip_목록(z):
                        out.extend(파일_항목(자, k, n, b, 경로 + [n], use_ocr, 깊이 + 1) if (b := 압축_풀기(z, info)) is not None else
                                   [{'갈래': '모름', '경로': 경로 + [n], '까닭': '압축을 풀지 못했다(암호가 걸렸거나 깨졌다)', '문서': True}])
        elif ext == '.hwp':      # PDF 로 바꾸어 면마다 읽는다(그림이 든 면은 그림으로 볼 면이 된다)
            b = _et.PDF로(이름, data)
            if b:
                out.extend(파일_항목(자, k, '바꾼.pdf', b, 경로, use_ocr, 깊이))
            elif not _et.한글_판(data):      # LibreOffice 가 글 문서로 열어 만든 PDF 를 읽은 것으로 치던 것(2026. 11. 3.)
                모름('.hwp 이름이지만 머리 서명이 한글 문서가 아니다(깨졌거나 다른 형식의 파일이다. 원본을 열어 보고 PDF 로 저장해 둔다)')
            else:
                모름('한글 자동화로 .hwp 를 PDF 로 바꾸지 못했다(이 PC에 한글 자동화가 없거나 암호가 걸렸거나 깨진 파일이다. '
                    '한글이 있는 PC에서 make 를 다시 돌리거나 PDF 로 저장해 둔다)')
        elif ext == '.msg':
            r = _et.msg_글(data)
            if '모름' in r:
                모름(r['모름'])
            else:
                글(r.get('글') or '', '(빈 메일)')
                for n, b in r.get('첨부', []):
                    out.extend(파일_항목(자, k, n, b, 경로 + [n], use_ocr, 깊이 + 1))
        elif ext in 소리_꼴:
            모름('소리·영상은 녹취록으로 읽는다', 문서=False)
        else:
            모름(f'{ext or "확장자 없는"} 형식은 글을 뽑지 못한다', 문서=False)
    except Exception as e:      # 깨진 파일 등. 읽은 것으로 치지 않는다
        모름(f'읽다가 오류({type(e).__name__})')
    return out


def 단위_항목(자: 자리, k: str, p: Path, use_ocr: bool) -> dict:
    """단위 → 항목들. 압축은 안의 파일마다, 엑셀은 시트마다(그 시트에 든 그림 포함), 그 밖은 '전체' 하나."""
    ext = p.suffix.lower()
    data = p.read_bytes()
    if ext == '.zip':
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                return {f'[파일] {n}': 파일_항목(자, k, n, b, [n], use_ocr, 1) if (b := 압축_풀기(z, info)) is not None else
                        [{'갈래': '모름', '경로': [n], '까닭': '압축을 풀지 못했다(암호가 걸렸거나 깨졌다)', '문서': True}]
                        for n, info in _et.zip_목록(z)}
        except zipfile.BadZipFile:
            return {'전체': [{'갈래': '모름', '경로': [], '까닭': '압축을 풀지 못했다', '문서': True}]}
    if ext in ('.xlsx', '.xlsm'):
        try:
            r = _et.xlsx_시트들(data)
        except Exception as e:
            return {u: [{'갈래': '모름', '경로': [], '까닭': f'엑셀을 읽다가 오류({type(e).__name__})', '문서': True}] for u in 단위들(p)}
        그림 = {g['이름']: g for g in r['그림']}

        def 그림_항(m):
            g = 그림[m]
            if g['갈래'] == '그림':
                return [{'갈래': '그림', '경로': [m], '조각': g['조각']}]
            if g['갈래'] == '못 엶':
                return [{'갈래': '모름', '경로': [m], '문서': True, '까닭': f'시트 위의 {g["ext"]} 그림을 그리지 못했다(통합 문서를 PDF 로 저장해 그 PDF 로 읽는다)'}]
            return []
        out, 쓴 = {}, set()
        for 이름, 글, 숨김, 든 in r['시트']:
            작음 = sum(1 for m in set(든) if m in 그림 and 그림[m]['갈래'] == '작음')
            글 = ('(숨긴 시트)\n' if 숨김 else '') + 글 + (f'\n[작은 그림 {작음}개(64×64 화소 미만)는 따로 열지 않는다]' if 작음 else '')
            items = [{'갈래': '글', '경로': [], '덩이': _et.덩이로(글) or ['(빈 시트)']}]
            for m in 든:
                if m in 그림 and m not in 쓴:
                    items += 그림_항(m)
                    쓴.add(m)
            out[f'[시트] {이름}'] = items
        if out:
            첫 = next(iter(out))
            out[첫] += [x for n in 그림 if n not in 쓴 for x in 그림_항(n)]
        return out
    return {'전체': 파일_항목(자, k, p.name, data, [], use_ocr, 0)}


def 압축_풀기(z, info) -> bytes | None:
    try:
        return z.read(info)
    except (RuntimeError, zipfile.BadZipFile, OSError, EOFError, NotImplementedError, ValueError):     # 암호, 깨진 압축, 못 푸는 압축 방식
        return None


def 바이트_찾기(p: Path, 경로: list) -> bytes:
    """호증 파일에서 경로(압축 안 파일, 문서 안 그림, 메일 첨부)를 따라 그 항목의 바이트를 찾는다."""
    data, 이름 = p.read_bytes(), p.name
    for e in 경로:
        ext = Path(이름).suffix.lower()
        if ext in ('.doc', '.xls'):      # make 처럼 새 형식으로 바꾼 뒤 그 안에서 찾는다
            data, ext = _et.새형식(이름, data), '.docx' if ext == '.doc' else '.xlsx'
        if ext == '.eml':
            data = next(b for n, b in _et.eml_글(data)['첨부'] if n == e)
        elif ext == '.msg':
            data = next(b for n, b in _et.msg_글(data).get('첨부', []) if n == e)
        else:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                data = z.read(next(i for n, i in _et.zip_목록(z) if n == e) if ext == '.zip' else e)
        이름 = e
    return data


def 기타_글_쓰기(자: 자리, k: str, p: Path, use_ocr: bool) -> str:
    """PDF 가 아닌 호증의 면별 글. 단위마다 글 덩이와 그 끝의 확인표, 그림·그림으로 볼 면은 `그림` 으로 열 것, 머리에 확인표 목록."""
    해 = 해시(p)
    항목 = 단위_항목(자, k, p, use_ocr)
    목록, 몸, 못 = [], [], []
    for u in 단위들(p):
        몸.append(f'=== {u} ===')
        for it in 항목.get(u) or [{'갈래': '모름', '경로': [], '까닭': '그 단위의 글을 찾지 못했다', '문서': True}]:
            경 = '›'.join(it['경로'])
            보일 = it['경로'][1:] if u.startswith('[파일] ') and it['경로'][:1] == [u[5:]] else it['경로']      # 압축 안 파일 이름을 두 번 쓰지 않는다
            보기 = u + (f' › {"›".join(보일)}' if 보일 else '')
            if it['갈래'] == '글':
                n = len(it['덩이'])
                목록.append(목록_머리 + 가름.join([u, f'글 {n}', 경]))
                for i, d in enumerate(it['덩이'], 1):
                    몸 += [d, f'[{보기} · 덩이 {i}/{n} 끝 · 확인표 {확인표(자.사건, 해, 키(u, it["경로"], f"덩이{i}"), "글")}]']
            elif it['갈래'] == '그림':
                목록.append(목록_머리 + 가름.join([u, f'그림 {it["조각"]}', 경]))
                몸.append(f'[{보기} · 그림 {it["조각"]}조각 — 그림으로 본다. 확인표는 `그림` 이 그린 그림 아래 띠에 있다]')
            elif it['갈래'] == '면':
                목록.append(목록_머리 + 가름.join([u, '면 ' + ','.join(x[0] for x in it['면']), 경]))
                for j, (종, src, 까닭, 글) in enumerate(it['면'], 1):
                    몸.append(f'--- {보기} {j}면 ({src})' + (f' — 그림으로 볼 면({까닭})' if 종 == '그림' else '') + ' ---')
                    if 글:
                        몸.append(글)
                    몸.append(f'[{보기} · {j}면 끝 · ' + ('그림으로 볼 면 — 확인표는 `그림` 이 그린 그림 아래 띠에 있다]' if 종 == '그림' else
                                                    f'확인표 {확인표(자.사건, 해, 키(u, it["경로"], f"{j}면"), "글")}]'))
            else:
                목록.append(목록_머리 + 가름.join([u, '모름', 경, it['까닭'], '문서' if it['문서'] else '그 밖']))
                몸.append(f'[{보기} — 글을 뽑지 못했다: {it["까닭"]}]')
                못.append(f'{보기}: {it["까닭"]}')
        몸.append('')
    머리 = [f'# {자.제목(k)} 면별 글 — {nfc(p.name)}', '', f'해시: {해}', f'글판: {글판}',
            '단위마다 글을 끝까지 읽고 덩이·면 끝의 확인표를 기록의 그 단위 줄에 모두 옮긴다. 그림과 그림으로 볼 면은 '
            f'`python -B 4_서면작성/scripts/evidence_read.py 그림 "<사건 폴더>" --호증 {k}` 이 그린 그림을 한 장씩 열어 읽고 띠의 확인표를 옮긴다. '
            '줄을 걸러 읽거나 모음 그림으로 갈음하지 않는다.', ''] + 목록 + ['']
    자.글_파일(k).parent.mkdir(parents=True, exist_ok=True)
    자.글_파일(k).write_text('\n'.join(머리 + 몸), encoding='utf-8')
    return ('글을 뽑지 못한 곳 ' + '; '.join(못)) if 못 else ''


def 목록_읽기(글: str) -> list:
    """면별 글 머리의 확인표 목록."""
    out = []
    for line in 글.splitlines():
        if not line.startswith(목록_머리):
            continue
        parts = line[len(목록_머리):].split(가름)
        u, 무엇 = parts[0], parts[1] if len(parts) > 1 else ''
        경로 = parts[2].split('›') if len(parts) > 2 and parts[2] else []
        if 무엇.startswith('글 ') or 무엇.startswith('그림 '):
            out.append({'단위': u, '갈래': 무엇.split()[0], '수': int(무엇.split()[1]), '경로': 경로})
        elif 무엇.startswith('면 '):
            out.append({'단위': u, '갈래': '면', '종류': 무엇[2:].split(','), '경로': 경로})
        elif 무엇 == '모름':
            out.append({'단위': u, '갈래': '모름', '경로': 경로, '까닭': parts[3] if len(parts) > 3 else '',
                        '문서': (parts[4] if len(parts) > 4 else '') == '문서'})
    return out


def 기타_새판(자: 자리, k: str, p: Path) -> bool:
    """면별 글이 지금 파일의 것이고 확인표 목록이 있는가. 머리 서명이 한글 문서가 아닌 .hwp 를 면으로 낸 글(2026. 11. 3. 고치기 전에
    LibreOffice 가 글 문서로 열어 바꾼 것)은 옛 판으로 본다. make 가 다시 써서 뽑지 못한 곳이 된다."""
    f = 자.글_파일(k)
    if not f.is_file():
        return False
    t = f.read_text(encoding='utf-8', errors='replace')
    if not (f'해시: {해시(p)}' in t and f'글판: {글판}\n' in t and 목록_머리 in t):
        return False
    for it in 목록_읽기(t):
        if it['갈래'] == '면' and (it['경로'][-1] if it['경로'] else p.name).lower().endswith('.hwp'):
            try:
                if not _et.한글_판(바이트_찾기(p, it['경로'])):
                    return False
            except Exception:      # 목록의 경로가 파일에 없다
                return False
    return 옛형식_글_맞음(p, t)


def 옛형식_글_맞음(p: Path, t: str) -> bool:
    """.doc·.xls·.txt·.csv 를 지금의 읽기로 읽은 면별 글인가. 고치기 전(2026. 11. 3.)에는 변환기가 머리 서명이 맞지 않는 .doc·.xls 를
    글 문서로 열어 엉터리 글을 만들었고, .txt·.csv 는 latin-1 로 끝내 풀었으며, 글자로만 된 .doc·.xls 는 변환기를 거쳐 cp949·UTF-8 이
    깨졌다. 그렇게 읽은 글(읽지 못한 곳이 아닌 단위)은 옛 판으로 보아 make 가 다시 쓰게 한다."""
    본, 정리 = set(), (lambda s: re.sub(r'\s+', '', nfc(s)))
    for it in 목록_읽기(t):
        if it['갈래'] == '모름':
            continue
        for i in range(len(it['경로']) + 1):
            앞 = tuple(it['경로'][:i])
            e = Path(it['경로'][i - 1] if i else p.name).suffix.lower()
            if e not in ('.doc', '.xls', '.txt', '.csv') or 앞 in 본:
                continue
            본.add(앞)
            try:
                data = 바이트_찾기(p, list(앞))
            except Exception:      # 목록의 경로가 파일에 없다
                return False
            if e in ('.txt', '.csv'):
                if _et.글자_풀기(data) is None:
                    return False
                continue
            판 = _et.오피스_판(data, e)
            if 판 is None:
                return False
            if 판 == '글':
                첫 = next((x.strip() for x in _et.글자_풀기(data).splitlines() if x.strip()), '')
                if 첫 and 정리(첫[:60]) not in 정리(t):
                    return False
    return True


def 글_쓰기(자: 자리, k: str, p: Path, use_ocr: bool) -> tuple:
    """면별 글을 쓴다. 돌려주는 것: (알림, {그림으로 볼 면: 까닭}).

    읽는 비용을 줄이되 글은 하나도 빼지 않는다. ① 여러 면에 되풀이되는 줄(문자 모음의 머리·꼬리, 대장의 칸 이름)은 머리에
    번호를 붙여 한 번 적고, 면마다 그 면에 든 되풀이 줄의 번호를 적는다(어느 면에 어느 줄이 있는지 그대로 남는다).
    ② 글자층 면의 표는 칸을 살려 옮기고, 칸이 조각으로 따로 읽힌 스캔 표는 줄로 돌린다. ③ 글로 읽기 어려운 면(글자가 거의 없음, 문자인식 품질 낮음, 숫자 표로 보이는 스캔 면,
    사진·도표가 큰 면, 표·발췌 그림을 끼운 글자층 면)만 '그림으로 볼 면'으로 표시한다. 그 면은 반드시 그림으로 열고, 기록의 '읽은 방식'에 면 번호를 적는다."""
    if p.suffix.lower() in 기타_꼴:
        return 기타_글_쓰기(자, k, p, use_ocr), {}
    if p.suffix.lower() != '.pdf':
        return '', {}
    if not PDF_면수(p):
        return 'PDF 가 비었거나 깨져 열리지 않는다(원본을 다시 받는다)', {}
    해 = 해시(p)
    면들, 그림 = 면_분석(자, 자.이름(k), p, use_ocr)
    return PDF_글_쓰기(자, k, p, 해, 면들, 그림)


def 면_분석(자: 자리, key: str, p: Path, use_ocr: bool) -> tuple:
    """PDF 의 면마다 (면, 글 출처, 줄들, 표)와 그림으로 볼 면 {면: 까닭}."""
    캐시 = 자.글
    표지 = 캐시 / 'ocr' / key / '파일해시.txt'      # 같은 호증 번호에 다른 파일을 넣으면 앞 파일의 문자인식을 버린다
    if 표지.is_file() and 표지.read_text(encoding='utf-8').strip() != 해시(p):      # 표지가 없는 옛 캐시는 make 가 파일이 바뀐 호증만 버린다
        shutil.rmtree(표지.parent, ignore_errors=True)
    ocr_dirs = [str(x) for x in 자.사건.glob('라운드*/작업/증거인용검토*/ocr')] + [str(캐시 / 'ocr')]
    ex = _ecr.Exhibit(key, p, 캐시, ocr_dirs=ocr_dirs, use_ocr=use_ocr)
    면들, 그림 = [], {}
    try:
        ex.prepare(range(1, len(ex) + 1))
        끼운 = 끼운_그림(ex.doc, [no for no in range(1, len(ex) + 1) if (ex.pages.get(no) or {}).get('src', '').startswith('글자층')])
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
            elif src.startswith('글자층') and no in 끼운:      # 표·발췌·캡처 그림 속 글은 글자층에 없다
                그림[no] = '끼운 그림'
            if 그림.get(no) == '숫자 표(칸 맞춤)':      # 칸을 줄로 돌려 읽게 하고, 숫자는 그림으로 맞댄다
                줄들 = 줄_복원(e['units'])
            면들.append((no, src, 줄들, 표))
    finally:
        ex.close()
    for png in 캐시.glob('ocr/*/*.png'):      # 글만 쌓고 그림은 남기지 않는다
        png.unlink()
    if 표지.parent.is_dir():
        표지.write_text(해시(p), encoding='utf-8')
    return 면들, 그림


def PDF_글_쓰기(자: 자리, k: str, p: Path, 해: str, 면들: list, 그림: dict) -> tuple:
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
    if '끼운 그림' in 그림.values():
        머리.append('끼운 그림: 글자층 면에 든 표·발췌·캡처 그림이다. 그 그림 속 글은 아래 면별 글에 없으므로 그림으로 열어 읽고 그 면 줄에 적는다.')
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
        줄 = [x for t in 줄들 + 표 for x in _et.긴줄_나누기(t)]      # 읽기 도구가 긴 줄을 잘라 보여 주지 않게
        본문.append(f'=== {no}면 ({src}){표시} ===\n' + '\n'.join(줄 + [끝]) + '\n')
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
        m = re.search(r'/([^/]+)/(?:(\d+)_)?(\d+)(면|조각)\.png$', 경로)      # `그림` 이 낸 낱장(압축·문서 안의 것은 '차례_' 가 붙는다)
        if m and nfc(m.group(1)) in 파일이름.values():
            if m.group(2):
                return nfc(m.group(1)), {f'{int(m.group(2))}:{int(m.group(3))}{m.group(4)}'}
            return nfc(m.group(1)), {int(m.group(3)) if m.group(4) == '면' else f'조각{int(m.group(3))}'}
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
    if p.suffix.lower() in 기타_꼴:
        면들, 볼 = 기타_글_읽기(자.글_파일(k).read_text(encoding='utf-8', errors='replace'))
    elif p.suffix.lower() != '.pdf':
        n = 그림_조각수(p)
        면들, 볼 = {}, {f'조각{i}' for i in range(1, n + 1)}
        if '전체' in 연 and n == 1:      # 조각이 하나인 그림은 파일을 바로 열어도 같다
            연 = {'조각1': 연['전체']}
    else:
        면들, 볼, _ = 글_읽기(자.글_파일(k).read_text(encoding='utf-8', errors='replace'))
        볼 |= 끼운_면(자, k, p)      # 끼운 그림을 표시하기 전에 낸 면별 글이어도 그 면은 그림으로 열었는지 잰다
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
    긴 = [no for no in 덜 if any(len(x) > 2000 and 정규(x) not in 본['모두'] for x in 면들[no])]
    return {'합': 합, '든': 든, '덜': 덜, '볼': sorted(볼), '못본': 못본, '세션': 세션, '긴줄': 긴,
            '통과': not 덜 and 든 >= 줄_통과 * 합 and not 못본}


def 실측_적기(f: Path, 줄: str):
    t = f.read_text(encoding='utf-8')
    if re.search(r'^실측:.*$', t, re.M):
        t = re.sub(r'^실측:.*$', lambda _: 줄, t, count=1, flags=re.M)
    else:
        t = re.sub(r'^(읽은 방식:.*)$', lambda m: m.group(1) + '\n' + 줄, t, count=1, flags=re.M)
    f.write_text(t, encoding='utf-8')


def 면말(들: list) -> str:
    """연 것·못 연 것의 표시. 면이면 '2, 5면', 그림 조각이면 '3조각', 압축·문서 안의 그림이면 '3장'."""
    if isinstance(들[0], int):
        return f'{면_표시(들)}면'
    return f'{len(들)}장' if ':' in str(들[0]) else f'{len(들)}조각'


def 단위말(들: list) -> str:
    """덜 읽은 단위의 표시. PDF 면이면 '1~3', 압축·엑셀·문서의 단위면 이름을 잇는다."""
    return 면_표시(들) if all(isinstance(x, int) for x in 들) else ', '.join(map(str, 들))


def 기타_글_읽기(text: str) -> tuple:
    """PDF 가 아닌 호증의 면별 글에서 ({단위: [읽을 줄]}, {열어 볼 그림}). 줄은 단위 머리('=== …')와 면 머리('--- … ---')를 뺀
    모든 줄(덩이·면 끝 줄 포함)이고, 그림은 `그림` 이 낸 낱장 이름대로 '차례:i조각'·'차례:j면'이다(차례는 머리 목록의 그림·면 항목 차례)."""
    단위, 지금 = {}, None
    for line in text.splitlines():
        m = re.match(r'^=== (.+) ===$', line)
        if m:
            지금 = m.group(1)
            단위.setdefault(지금, [])
            continue
        s = line.strip()
        if 지금 is None or not s or (s.startswith('--- ') and s.endswith(' ---')):
            continue
        단위[지금].append(s)
    볼, 차례 = set(), 0
    for it in 목록_읽기(text):
        if it['갈래'] == '그림':
            차례 += 1
            볼.update(f'{차례}:{i}조각' for i in range(1, it['수'] + 1))
        elif it['갈래'] == '면':
            차례 += 1
            볼.update(f'{차례}:{j}면' for j, 종 in enumerate(it['종류'], 1) if 종 == '그림')
    return 단위, 볼


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
        if (not 자.기록_파일(k).is_file() or (p.suffix.lower() == '.pdf' and not 자.글_파일(k).is_file())
                or (p.suffix.lower() in 기타_꼴 and not 기타_새판(자, k, p))):
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
                말.append(f"덜 읽은 {'면' if all(isinstance(u, int) for u in x['덜']) else '단위'} {단위말(x['덜'])}")
            if x['못본']:
                말.append(f"한 장씩 열지 않은 그림 {면말(x['못본'])}")
            if x['긴줄']:      # 읽기 도구는 2,000자 넘는 줄을 잘라 보여 준다. 지금 판의 make 는 줄을 나누어 쓴다
                말.append(f"2,000자 넘는 줄이 있는 {단위말(x['긴줄'])} — `make --글다시 {k}` 로 면별 글을 다시 내고 다시 읽는다")
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


# ---------------------------------------------------------------- 계획: 읽을 양을 어림해 창을 나눈다
글_토큰 = 1.5        # 면별 글의 글자 수를 토큰으로 어림할 때 나누는 수(한글이 많은 글 기준의 어림)
줄_토큰 = 2          # 읽기 도구가 줄마다 붙이는 줄 번호의 몫
그림_토큰 = 1600     # 그림 한 장의 어림(긴 변을 줄여 보내므로 장마다 비슷하다)
창_기본 = 200_000    # 한 창에서 읽을 양의 기본 상한(토큰). 문맥이 커질수록 턴마다 같은 글을 다시 읽어 사용량이 커진다


def 읽을_양(자: 자리, k: str, p: Path) -> dict | None:
    """그 호증을 읽는 데 드는 양. 면별 글(머리 포함 파일 전체)의 줄·글자와 한 장씩 열 그림. 면별 글이 없으면 None."""
    suf = p.suffix.lower()
    if suf in IMAGE:
        n = 그림_조각수(p)
        return {'줄': 0, '글자': 0, '그림': n, '토큰': n * 그림_토큰} if n else None
    f = 자.글_파일(k)
    if not f.is_file() or (suf in 기타_꼴 and not 기타_새판(자, k, p)):
        return None
    t = f.read_text(encoding='utf-8', errors='replace')
    볼 = 기타_글_읽기(t)[1] if suf in 기타_꼴 else 글_읽기(t)[1] | 끼운_면(자, k, p)
    줄 = t.count('\n') + 1
    return {'줄': 줄, '글자': len(t), '그림': len(볼), '토큰': round(len(t) / 글_토큰 + 줄 * 줄_토큰 + len(볼) * 그림_토큰)}


def 만(n: float) -> str:
    return f'{n / 10000:.1f}만' if n >= 10000 else f'{n:,.0f}'


def cmd_계획(a) -> int:
    """아직 실측을 마치지 않은 호증의 읽을 양을 어림하고, 한 창에 상한만큼씩 차례대로 나눈다. 실측은 이 PC 의 세션 기록을 모두 합쳐 재므로
    창을 나누어 읽어도 된다. 한 호증이 상한을 넘으면 그 호증만 한 창에 두고 면 순서대로 읽다가 문맥이 차면 새 창에서 이어 읽는다."""
    자, 목록, _ = 대상(a)
    if not 목록:
        print('읽을 호증(자료)이 없습니다:', a.case)
        return 2
    상한 = a.창 or 창_기본
    남은, 없음, 다 = [], [], 0
    for k in sorted(목록, key=호증_정렬):
        p = 목록[k]
        if not 잴_수_있나(p):
            continue
        f = 자.기록_파일(k)
        if f.is_file() and not 실측_문제(자, k, p, f.read_text(encoding='utf-8')):
            다 += 1
            continue
        양 = 읽을_양(자, k, p)
        if 양 is None:
            없음.append(k)
            continue
        남은.append((k, 양))
    if 없음:
        print('먼저 make(면별 글이 없거나 옛 판): ' + ', '.join(자.제목(k) for k in 없음))
    if not 남은:
        print(f'실측을 마치지 않은 호증이 없습니다(실측을 마친 것 {다}건).')
        return 0
    창들, 지금, 합 = [], [], 0
    for k, 양 in 남은:
        if 지금 and 합 + 양['토큰'] > 상한:
            창들.append(지금)
            지금, 합 = [], 0
        지금.append((k, 양))
        합 += 양['토큰']
    창들.append(지금)
    전체 = sum(양['토큰'] for _, 양 in 남은)
    print(f"실측을 마치지 않은 호증 {len(남은)}건(마친 것 {다}건), 읽을 양 어림 {만(전체)} 토큰"
          f"(글 {만(sum(양['글자'] / 글_토큰 + 양['줄'] * 줄_토큰 for _, 양 in 남은))}, 그림 {sum(양['그림'] for _, 양 in 남은):,}장) "
          f"→ 창 {len(창들)}개(한 창 {만(상한)} 토큰 안팎)")
    for i, 창 in enumerate(창들, 1):
        합 = sum(양['토큰'] for _, 양 in 창)
        말 = f"{i}창: " + ', '.join(자.제목(k) for k, _ in 창) + \
            f" (줄 {sum(양['줄'] for _, 양 in 창):,}, 그림 {sum(양['그림'] for _, 양 in 창):,}장, 약 {만(합)} 토큰)"
        if len(창) == 1 and 합 > 상한:
            말 += ' — 한 창을 넘는다. 면 순서대로 읽어 기록을 채우다가 문맥이 차면 새 창에서 이어 읽는다'
        print(말)
    print('창마다 그 창의 호증을 끝까지 읽고 기록을 채운 뒤 `실측` 을 돌리고, 다음 창은 새로 연다. 실측은 이 PC 의 세션 기록을 모두 합쳐 잰다.')
    return 0


# ---------------------------------------------------------------- 명령
def 대상(a) -> tuple:
    사건 = Path(a.case)
    자 = 자리(사건, bool(a.자료))
    if a.자료:
        전체 = 자료_목록(사건, a.자료)
    else:
        전체 = 서면_호증(사건)
        전체.update(서면_자료(사건, 전체))      # 상대방 서면·참고자료(인용 판결문)·노동위원회 기록도 같은 관문으로 읽는다
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
    바뀐_파일 = set()
    for k in sorted(목록, key=호증_정렬):
        p, f = 목록[k], 자.기록_파일(k)
        if f.is_file():
            r = 기록_읽기(f.read_text(encoding='utf-8'))
            if r['해시'] != 현재해시[k]:
                바뀐_파일.add(k)
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
        옛글 = ((p.suffix.lower() == '.pdf' and 자.글_파일(k).is_file() and not 그림_면들(자, k)[1])      # 확인표가 없는 옛 판
               or (p.suffix.lower() in 기타_꼴 and 자.글_파일(k).is_file() and not 기타_새판(자, k, p)))
        글다시 = a.글다시 == [] or k in (a.글다시 or [])
        if not a.no_text and (k in 새로 or k in 옮겨옴 or not 자.글_파일(k).is_file() or 옛글 or 글다시):
            if k in 바뀐_파일:      # 기록한 뒤 파일이 바뀌었으면 앞 파일의 문자인식을 쓰지 않는다
                shutil.rmtree(자.글 / 'ocr' / 자.이름(k), ignore_errors=True)
                # 증거 인용 대조가 쌓은 같은 호증의 캐시도 함께 읽으므로, 표지가 없거나 지금 파일과 다르면 지운다(2026. 11. 5. `/하자보완`)
                for d in 자.사건.glob('라운드*/작업/증거인용검토*/ocr'):
                    c = d / 자.이름(k)
                    m = c / _ecr.MARK
                    if c.is_dir() and not (m.is_file() and m.read_text(encoding='utf-8').strip() == 현재해시[k]):
                        shutil.rmtree(c, ignore_errors=True)
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
          '읽은 뒤 면마다 끝의 확인표를 그 면 줄에 옮겨 기록을 채우고 `실측`, `check` 를 돌린다. 호증이 많으면 `계획` 이 나눈 대로 창을 나누어 읽는다.')
    return 0


def 띠_붙여_저장(pix, 글: str, 표: str, out: Path):
    """그림 아래에 띠를 붙여 왼쪽에 호증·면을, 오른쪽 끝에 확인표를 적어 저장한다. 그림 위는 덮지 않는다.
    띠의 글자는 한 장씩 열면 읽히고 여러 장을 줄여 모으면 읽히지 않는다. 확인표는 글자 사이가 벌어지지 않게 영문 글꼴로 적는다."""
    크기 = max(14, pix.width / 75)      # 본문 작은 글자만 하게: 한 장으로 열면 읽히고, 넉 장 넘게 줄여 모으면 읽히지 않는다
    띠 = 크기 * 2.6 + 12                  # 두 줄: 호증·면, 그 아래 확인표(좁은 그림에서도 겹치지 않게)
    d = _ecr.pymupdf.open()
    try:
        pg = d.new_page(width=pix.width, height=pix.height + 띠)
        pg.insert_image(_ecr.pymupdf.Rect(0, 0, pix.width, pix.height), pixmap=pix)
        try:      # 이름표가 그림 폭을 넘으면 글자를 줄여 다 보이게 한다(확인표는 그대로)
            길이 = _ecr.pymupdf.get_text_length(글 + ' · 확인표', fontname='korea', fontsize=크기)
            작게 = max(7, 크기 * min(1, (pix.width - 20) / 길이)) if 길이 else 크기
            pg.insert_text((10, pix.height + 크기 + 4), 글 + ' · 확인표', fontsize=작게, fontname='korea')
        except Exception:
            pg.insert_text((10, pix.height + 크기 + 4), 'check code', fontsize=크기)
        pg.insert_text((10, pix.height + 크기 * 2.3 + 6), 표, fontsize=크기, fontname='hebo')
        pg.get_pixmap(dpi=72).save(str(out))
    finally:
        d.close()


def 조각_그리기(doc, n: int, 폭: float, 이름: str, 표들: list, 폴더: Path, 앞: str) -> list:
    """그림(문서로 연 것)을 n 조각으로 나누어 조각마다 띠에 확인표를 붙여 저장한다. 조각 높이는 같게 나누고 조금 겹친다."""
    pg = doc[0]
    r = pg.rect
    z = min(폭, 1600) / r.width
    단 = r.height / n
    만든 = []
    for i in range(n):
        clip = _ecr.pymupdf.Rect(0, i * 단, r.width, min(r.height, (i + 1) * 단 + 단 * 0.04))
        pix = pg.get_pixmap(matrix=_ecr.pymupdf.Matrix(z, z), clip=clip)
        out = 폴더 / f'{앞}{i + 1:02d}조각.png'
        띠_붙여_저장(pix, f'{이름} {i + 1}/{n}조각', 표들[i], out)
        만든.append(out)
    return 만든


def 면_그리기(doc, 면: list, 이름: str, 표들: dict, 폴더: Path, 앞: str, 돌림: dict | None = None) -> list:
    """PDF 의 면들을 그려 띠에 확인표를 붙인다. 돌림: 누운 스캔을 문자인식할 때 돌린 각도 {면: 도}(그대로 세워 그린다)."""
    만든 = []
    for no in 면:
        if not 1 <= no <= len(doc):
            continue
        pg = doc[no - 1]
        z = min(150 / 72, 2200 / max(pg.rect.width, pg.rect.height))
        pix = pg.get_pixmap(matrix=_ecr.pymupdf.Matrix(z, z).prerotate((돌림 or {}).get(no, 0)))
        out = 폴더 / f'{앞}{no:03d}면.png'
        띠_붙여_저장(pix, f'{이름} {no}면', 표들[no], out)
        만든.append(out)
    return 만든


def cmd_그림(a) -> int:
    """그림으로 볼 면(PDF)과 그림 호증, 압축·문서 안의 그림과 그림으로 볼 면을 원본에 가까운 크기로 그려 아래 띠에 확인표를 적는다.
    시스템 임시 폴더에 둔다."""
    자, 목록, _ = 대상(a)
    if not 목록:
        print('읽을 호증(자료)이 없습니다:', a.case)
        return 2
    뿌리_폴더 = Path(a.out) if a.out else Path(tempfile.gettempdir()) / '증거그림' / nfc(자.사건.resolve().name)
    for k in sorted(목록, key=호증_정렬):
        p = 목록[k]
        suf = p.suffix.lower()
        if suf not in ('.pdf',) + IMAGE + 기타_꼴:
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
            try:      # 끼운 그림을 표시하기 전의 면별 글이면 그 면도 그린다(띠의 확인표는 면별 글의 표시대로 '글' 확인표)
                면 = list(range(1, len(d) + 1)) if a.전부 else sorted(a.면 or 그림 | 끼운_면(자, k, p))
                만든 += 면_그리기(d, 면, 자.제목(k), {no: 확인표(자.사건, 해, no, '그림' if no in 그림 else '글') for no in range(1, len(d) + 1)},
                                  폴더, '', 돌림)
            finally:
                d.close()
        elif suf in IMAGE:
            n = 그림_조각수(p)
            if not n:
                print(f'{자.제목(k)}: 그림을 열지 못했다({nfc(p.name)}) — 원본을 직접 열어 읽고 \'읽은 방식\'에 적는다')
                continue
            d = _ecr.pymupdf.open(p)
            try:
                try:
                    폭 = _ecr.pymupdf.Pixmap(str(p)).width
                except Exception:
                    폭 = d[0].rect.width
                만든 += 조각_그리기(d, n, 폭, 자.제목(k), [확인표(자.사건, 해, 1, '그림' if i == 1 else f'그림{i}') for i in range(1, n + 1)], 폴더, '')
            finally:
                d.close()
        else:
            if not 기타_새판(자, k, p):
                print(f'{자.제목(k)}: 면별 글이 없거나 옛 판이다 — 먼저 `make` 를 돌린다')
                continue
            차례 = 0
            글자 = 자.글_파일(k).read_text(encoding='utf-8', errors='replace')
            for it in 목록_읽기(글자):
                u, 경로 = it['단위'], it['경로']
                if it['갈래'] not in ('그림', '면'):
                    continue
                차례 += 1
                보일 = 경로[1:] if u.startswith('[파일] ') and 경로[:1] == [u[5:]] else 경로
                이름 = f'{자.제목(k)} {u}' + (f' › {"›".join(보일)}' if 보일 else '')
                try:
                    data = 바이트_찾기(p, 경로)
                    끝 = 경로[-1] if 경로 else p.name
                    ext = Path(끝).suffix.lower().lstrip('.')
                    if it['갈래'] == '면' and ext == 'hwp':
                        data = _et.PDF로(끝, data)
                        if not data:      # 빈 PDF 로 열려 아무것도 그리지 않고 지나가지 않게
                            print(f'  {이름}: 한글 자동화로 .hwp 를 PDF 로 바꾸지 못했다 — 한글이 있는 PC에서 `그림` 을 다시 돌린다')
                            continue
                    elif it['갈래'] == '그림':
                        data, ext = _et.열_그림(data, '.' + ext)
                        ext = ext.lstrip('.')
                    d = _ecr.pymupdf.open(stream=data, filetype='pdf' if it['갈래'] == '면' else ext)
                except Exception as e:
                    print(f'  {이름}: 열지 못했다({type(e).__name__}) — 원본을 직접 열어 본다')
                    continue
                try:
                    if it['갈래'] == '그림':
                        try:
                            폭 = _ecr.pymupdf.Pixmap(data).width
                        except Exception:
                            폭 = d[0].rect.width
                        표들 = [확인표(자.사건, 해, 키(u, 경로, f'그림{i}'), '그림') for i in range(1, it['수'] + 1)]
                        만든 += 조각_그리기(d, it['수'], 폭, 이름, 표들, 폴더, f'{차례:03d}_')
                    else:
                        면 = (list(range(1, len(it['종류']) + 1)) if a.전부 else [j for j, 종 in enumerate(it['종류'], 1) if 종 == '그림'])
                        표들 = {j: 확인표(자.사건, 해, 키(u, 경로, f'{j}면'), 종) for j, 종 in enumerate(it['종류'], 1)}
                        보기 = u + (f' › {"›".join(보일)}' if 보일 else '')
                        돌림 = {int(m.group(1)): int(m.group(2)) for m in re.finditer(      # 누운 스캔은 문자인식할 때 돌린 대로 세워 그린다
                            r'^--- ' + re.escape(보기) + r' (\d+)면 \([^)]*?(\d+)도 돌림[^)]*\)', 글자, re.M)}
                        만든 += 면_그리기(d, 면, 이름, 표들, 폴더, f'{차례:03d}_', 돌림)
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
    for name in ('make', 'check', '그림', '실측', '계획'):
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
        if name == '계획':
            s.add_argument('--창', type=int, help=f'한 창에서 읽을 양의 상한(토큰, 기본 {창_기본:,})')
    a = ap.parse_args(argv)
    _끼운_캐시.clear()      # 한 번 돌 때만 쓴다(같은 프로세스에서 파일을 바꾸어 다시 돌리는 시험)
    return {'make': cmd_make, 'check': cmd_check, '그림': cmd_그림, '실측': cmd_실측, '계획': cmd_계획}[a.cmd](a)


if __name__ == '__main__':
    raise SystemExit(main())
