"""호증(자료)의 글을 형식마다 뽑는다. `evidence_read.py` 가 면별 글과 확인표를 만들 때 부른다. 모델을 쓰지 않는다.

PDF 가 아닌 호증도 단위(압축 안 파일, 엑셀 시트, 문서 전체)마다 글을 뽑아 덩이로 나누고 덩이마다 확인표를 붙이게 한다.
글이 아닌 것(그림 파일, 문서 안에 든 그림)은 그림으로 열어 보게 하고, 뽑을 수 없는 형식은 그 까닭을 돌려준다.

- 워드(.docx·.docm): 본문(표는 칸을 '|'로), 머리글·바닥글, 각주·미주, 메모(쓴 사람·날짜), 변경 내용 추적의 지운 글('[지움: …]'),
  글상자, 체크 상자 같은 기호(☑·☐). 안에 든 그림(word/media)은 그림으로 볼 것으로 돌려준다.
- 엑셀(.xlsx·.xlsm): 시트마다 값이 있는 칸을 행마다 '3행 | A: 값 | C: 값'으로. 숫자는 엑셀이 보여 주는 꼴로(날짜, 출퇴근 시각,
  '[h]:mm' 합계 시간, 백분율, 일반 숫자는 유효 숫자 15자리), 값 없이 식만 있으면 식을, 메모, 숨긴 시트·행·열, 시트 위 도형·차트의
  글을 적는다.
- 파워포인트(.pptx): 슬라이드마다 글(표·스마트아트·차트 글 포함)과 발표자 메모, 숨긴 슬라이드. 한글(.hwpx): 문단마다.
  메일(.eml): 머리(보낸 사람·받는 사람·날짜·제목)와 본문(글 본문이 안내 문구뿐이면 HTML 본문도), 첨부(본문에 넣은 그림 포함)는
  형식대로 다시 뽑는다. 텍스트(.txt·.csv): UTF-16 머리표가 있으면 UTF-16, 그 밖은 utf-8, 안 되면 cp949.
- 문서 안의 그림은 아주 작은 것(아이콘·글머리표, 64×64 화소 미만)만 빼고 모두 그림으로 볼 것이 된다. 바로 열 수 없는 그림
  (워드에 붙인 .emf·.wmf 등)은 Pillow(윈도)나 LibreOffice 로 PNG 로 바꾸고, 바꾸지 못하면 그 까닭을 돌려준다.
- 옛 형식 .doc·.xls 는 이 PC의 워드·엑셀(없으면 LibreOffice)로 .docx·.xlsx 로 바꾸어 위와 같이 읽는다(`새형식`. PDF 로 바꾸면
  숨긴 시트·행·열과 메모가 빠진다). .hwp 는 이 PC의 한글로 PDF 로 바꾸어 면마다 읽게 한다(`PDF로`). 그림이 든 면도 그림으로 볼 면이
  되어 빠지지 않는다. .msg 는 extract_msg 로 읽는다. 바꿀 길이 없으면 그 까닭을 돌려준다.
  한글 파일(.hwp)은 한글 자동화가 있는 PC에서만 읽힌다(LibreOffice 는 한글 97 이하 형식만 읽는다). 그런 호증은 제출용 PDF 를 만들어
  두면 그 PDF 로 읽는다. 머리 서명이 한글 문서가 아닌 .hwp 는 바꾸지 않는다(`한글_판`).
  .doc·.xls 도 머리 서명이 워드·엑셀 문서(또는 RTF·HTML·XML 로 저장한 문서)가 아니면 바꾸지 않고, 글자로만 된 파일(쉼표·탭으로 나눈
  글을 .xls 로 저장한 것 등)은 바꾸지 않고 바로 읽는다(`오피스_판`). .txt·.csv 도 글자로 풀리지 않으면 읽은 것으로 치지 않는다(`글자_풀기`).

2026. 11. 3. 담당 노무사 "압축·엑셀·문서 호증도 확인표 넣어줘".
"""
from __future__ import annotations

import contextlib
import datetime as dt
import email
import email.policy
import html
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

덩이_크기 = 3000      # 덩이 하나의 글자 수(줄을 자르지 않고 맞춘다). 덩이마다 끝에 확인표가 붙는다
줄_폭 = 1000         # 면별 글 한 줄의 글자 수 상한. 읽기 도구(Read)는 2,000자 넘는 줄을 잘라 보여 주므로(잘린 줄은 실측에서 읽지 않은 줄이 된다)
                     # 그보다 짧게 나눈다
그림_꼴 = ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tif', '.tiff', '.webp')
바꿀_그림_꼴 = ('.emf', '.wmf', '.emz', '.wmz', '.heic', '.heif', '.svg', '.jfif', '.pict', '.wdp', '.jxr')
작은_그림 = 64 * 64      # 이보다 작은 그림(아이콘·글머리표)만 따로 열게 하지 않는다. 직인·서명 그림은 이보다 크다
MC = '{http://schemas.openxmlformats.org/markup-compatibility/2006}'

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
S = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
A = '{http://schemas.openxmlformats.org/drawingml/2006/main}'
R = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
PR = '{http://schemas.openxmlformats.org/package/2006/relationships}'


@contextlib.contextmanager
def 임시_폴더():
    """지울 때 잠긴 파일(윈도에서 한글·LibreOffice 가 늦게 놓는 파일)이 있어도 멈추지 않는 임시 폴더."""
    d = tempfile.mkdtemp(prefix='etext_')
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


def nfc(s: str) -> str:
    return unicodedata.normalize('NFC', s)


def zip_이름(info) -> str:
    """압축 안 파일 이름. UTF-8 표시가 없는 이름(윈도에서 만든 압축)은 cp949 로 다시 푼다."""
    n = info.filename
    if not info.flag_bits & 0x800:
        try:
            n = n.encode('cp437').decode('cp949')
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
    return nfc(n)


군더더기 = ('.ds_store', 'thumbs.db', 'desktop.ini')      # 운영체제가 남기는 파일. 내용이 없다


def zip_목록(z) -> list:
    """[(이름, ZipInfo)]. 폴더와 __MACOSX·운영체제가 남기는 파일은 뺀다. 이름 차례."""
    return sorted(((zip_이름(i), i) for i in z.infolist() if not i.is_dir() and not i.filename.startswith('__MACOSX')
                   and i.filename.rsplit('/', 1)[-1].lower() not in 군더더기), key=lambda x: x[0])


def 긴줄_나누기(줄: str, 폭: int = 줄_폭) -> list:
    """폭보다 긴 줄을 여러 줄로 나눈다. 표의 칸 경계(' | ')나 빈칸에서 끊을 수 있으면 거기서, 아니면 글자로 끊는다.
    끊은 자리의 빈칸 말고는 글자를 하나도 빼지 않는다."""
    out = []
    while len(줄) > 폭:
        끊 = 줄.rfind(' | ', 폭 // 2, 폭)
        if 끊 < 0:
            끊 = 줄.rfind(' ', 폭 // 2, 폭)
        if 끊 <= 0:
            끊 = 폭
        out.append(줄[:끊].rstrip())
        줄 = 줄[끊:].lstrip()
    out.append(줄)
    return out


def 덩이로(글: str) -> list:
    """글을 줄을 자르지 않고 덩이_크기 안팎으로 나눈다. 줄_폭보다 긴 줄은 먼저 여러 줄로 나눈다. 빈 글이면 []."""
    out, 지금 = [], []
    크기 = 0
    for 줄 in (x for 원 in 글.replace('\r\n', '\n').split('\n') for x in 긴줄_나누기(원)):
        if 크기 + len(줄) > 덩이_크기 and 지금:
            out.append('\n'.join(지금))
            지금, 크기 = [], 0
        지금.append(줄)
        크기 += len(줄) + 1
    if 지금 and '\n'.join(지금).strip():
        out.append('\n'.join(지금))
    return [x.strip('\n') for x in out if x.strip()]


def 그림_크기(data: bytes, ext: str):
    """(폭, 높이). 열지 못하면 None."""
    try:
        import pymupdf
    except ImportError:
        return None
    try:
        pix = pymupdf.Pixmap(data)
        return (pix.width, pix.height)
    except Exception:
        pass
    try:
        d = pymupdf.open(stream=data, filetype=ext.lstrip('.').lower())
        try:
            r = d[0].rect
            return (r.width, r.height)
        finally:
            d.close()
    except Exception:
        return None


def 조각수(폭, 높이) -> int:
    """긴 그림(화면 갈무리)은 한 장으로 줄이면 글자를 못 읽으므로 폭의 1.4배 높이로 자른다."""
    import math
    return max(1, math.ceil(높이 / (폭 * 1.4))) if 폭 else 1


def _벡터_그림(data: bytes, ext: str) -> bool:
    """LibreOffice 로 그릴 벡터 그림인지 머리 바이트로 본다. 아니면 LibreOffice 가 글 문서로 열어 바이트를 글자로 그려 버린다."""
    if ext == '.emf':
        return data[40:44] == b' EMF'
    if ext == '.wmf':
        return data[:4] == b'\xd7\xcd\xc6\x9a' or (data[:2] in (b'\x01\x00', b'\x02\x00') and data[2:4] == b'\x09\x00')
    if ext == '.svg':
        return b'<svg' in data[:4096].lower()
    return False


def 그림_PNG(data: bytes, ext: str) -> bytes | None:
    """바로 열 수 없는 그림(.emf·.wmf·.heic 등)을 PNG 로. Pillow(윈도에서는 .emf·.wmf 를 그린다), 벡터 그림은 LibreOffice. 못 하면 None."""
    import io
    ext = ext.lower()
    if ext in ('.emz', '.wmz'):      # gzip 으로 줄인 .emf·.wmf
        try:
            import gzip
            data, ext = gzip.decompress(data), '.emf' if ext == '.emz' else '.wmf'
        except (OSError, EOFError):
            return None
    try:
        from PIL import Image
        with Image.open(io.BytesIO(data)) as im:
            if ext in ('.wmf', '.emf'):
                im.load(dpi=150)
            b = io.BytesIO()
            im.convert('RGB').save(b, 'PNG')
            return b.getvalue()
    except Exception:
        pass
    if not _벡터_그림(data, ext):
        return None
    b = _libre(data, ext, 'png')
    if not b or b[:8] != b'\x89PNG\r\n\x1a\n':
        return None
    try:      # LibreOffice 는 쪽 크기로 그리므로 그림이 있는 곳만 남긴다(빈 곳까지 조각으로 나누어 열지 않게)
        from PIL import Image, ImageOps
        with Image.open(io.BytesIO(b)) as im:
            box = ImageOps.invert(im.convert('L')).point(lambda v: 255 if v > 8 else 0).getbbox()
            if box:
                out = io.BytesIO()
                im.crop((max(0, box[0] - 10), max(0, box[1] - 10), min(im.width, box[2] + 10), min(im.height, box[3] + 10))).save(out, 'PNG')
                b = out.getvalue()
    except Exception:
        pass
    return b


def 열_그림(data: bytes, ext: str):
    """(바로 열 수 있는 바이트, 확장자). 바로 열리면 그대로, 아니면 PNG 로 바꾼 것. 못 열면 None."""
    if 그림_크기(data, ext):
        return data, ext
    b = 그림_PNG(data, ext)
    return (b, '.png') if b and 그림_크기(b, '.png') else None


def 그림_항목(이름: str, data: bytes):
    """문서 안의 그림 하나. {'갈래': '그림', …} 이나, 아주 작으면 {'갈래': '작음'}, 열지 못하면 {'갈래': '못 엶'}."""
    ext = Path(이름).suffix.lower()
    열 = 열_그림(data, ext)
    if not 열:
        return {'갈래': '못 엶', '이름': nfc(이름), 'ext': ext}
    크기 = 그림_크기(*열)
    if 크기[0] * 크기[1] < 작은_그림:
        return {'갈래': '작음', '이름': nfc(이름)}
    return {'갈래': '그림', '이름': nfc(이름), '조각': 조각수(*크기), 'ext': 열[1]}


def 그림_모음(z, 앞: str) -> list:
    """압축꼴 문서(워드·엑셀·파워포인트·hwpx)의 그림 폴더에 든 그림 항목들. 그림이 아닌 것(.bin 등 개체)은 뺀다."""
    out = []
    for n in sorted(z.namelist()):
        if n.startswith(앞) and not n.endswith('/') and Path(n).suffix.lower() in 그림_꼴 + 바꿀_그림_꼴:
            out.append(그림_항목(n, z.read(n)))
    return out


# ---------------------------------------------------------------- 워드
_기호 = {'A8': '☐', 'FE': '☑', 'FD': '☒', '78': '☒', 'FC': '✓', 'FB': '✗', '6F': '□', '6E': '■', 'A1': '○', '6C': '●', 'A4': '◉'}     # Wingdings


def _w_글(el) -> str:
    """문단 하나의 글(글상자 안 글 포함). 지운 글은 '[지움: …]'으로 남긴다(이어진 지운 조각은 하나로). 옛 판 대체본(mc:Fallback)은
    같은 글이라 건너뛴다."""
    out = []      # 글 조각. 지운 글은 ('지움', 글)

    def 걷기(x):
        for c in x:
            if c.tag == MC + 'Fallback':
                continue
            if c.tag == W + 't':
                out.append(c.text or '')
            elif c.tag == W + 'delText':
                if out and isinstance(out[-1], tuple):
                    out[-1] = ('지움', out[-1][1] + (c.text or ''))
                else:
                    out.append(('지움', c.text or ''))
            elif c.tag == W + 'tab':
                out.append('\t')
            elif c.tag in (W + 'br', W + 'cr'):
                out.append('\n')
            elif c.tag == W + 'sym':      # 기호 글꼴의 글자(체크 상자 등). 아는 것은 그 모양으로, 모르는 것은 있다는 것만
                ch = (c.get(W + 'char') or '').upper()
                out.append(_기호.get(ch[-2:], '[기호]') if ch[:2] in ('F0', '00') else '[기호]')
            걷기(c)
    걷기(el)
    return ''.join(f'[지움: {x[1]}]' if isinstance(x, tuple) else x for x in out)


def _w_몸(몸) -> list:
    """본문의 문단과 표를 차례대로 줄로. 표는 행마다 칸을 '|'로 잇는다."""
    줄 = []
    for el in list(몸):
        if el.tag == W + 'p':
            t = _w_글(el).strip()
            if t:
                줄.append(t)
        elif el.tag == W + 'tbl':
            for tr in el.iter(W + 'tr'):
                칸 = [' / '.join(x for x in (_w_글(p).strip() for p in tc.iter(W + 'p')) if x) for tc in tr.findall(W + 'tc')]
                if any(칸):
                    줄.append('| ' + ' | '.join(칸) + ' |')
        elif el.tag == W + 'sdt':
            c = el.find(W + 'sdtContent')
            if c is not None:
                줄 += _w_몸(c)
    return 줄


def docx_글(data: bytes) -> dict:
    """{'글': 글, '그림': [그림 항목]}"""
    with zipfile.ZipFile(_바이트(data)) as z:
        names = z.namelist()
        줄 = []
        몸 = ET.fromstring(z.read('word/document.xml')).find(W + 'body')
        if 몸 is not None:
            줄 += _w_몸(몸)
        for 머리, pat in (('머리글', r'word/header\d*\.xml'), ('바닥글', r'word/footer\d*\.xml')):
            for n in sorted(x for x in names if re.fullmatch(pat, x)):
                t = [x for x in _w_몸(ET.fromstring(z.read(n))) if x]
                if t:
                    줄 += [f'[{머리}] ' + ' / '.join(t)]
        for 머리, n, tag in (('각주', 'word/footnotes.xml', 'footnote'), ('미주', 'word/endnotes.xml', 'endnote')):
            if n in names:
                for fn in ET.fromstring(z.read(n)).findall(W + tag):
                    t = ' '.join(x for x in _w_몸(fn) if x)
                    if t and fn.get(W + 'type') not in ('separator', 'continuationSeparator', 'continuationNotice'):
                        줄.append(f'[{머리} {fn.get(W + "id")}] {t}')
        if 'word/comments.xml' in names:
            for c in ET.fromstring(z.read('word/comments.xml')).findall(W + 'comment'):
                t = ' '.join(x for x in _w_몸(c) if x)
                if t:
                    줄.append(f'[메모 {c.get(W + "author", "")} {c.get(W + "date", "")[:10]}] {t}')
        그림 = 그림_모음(z, 'word/media/')
    return {'글': '\n'.join(줄), '그림': 그림}


# ---------------------------------------------------------------- 엑셀
def _열(ref: str) -> str:
    return re.match(r'[A-Z]+', ref).group(0) if ref and re.match(r'[A-Z]+', ref) else ''


def _rels(z, 경로: str) -> dict:
    d, n = os.path.split(경로)
    rel = f'{d}/_rels/{n}.rels' if d else f'_rels/{n}.rels'
    if rel not in z.namelist():
        return {}
    out = {}
    for r in ET.fromstring(z.read(rel)).findall(PR + 'Relationship'):
        t = r.get('Target', '')
        out[r.get('Id')] = t.lstrip('/') if t.startswith('/') else os.path.normpath(os.path.join(d, t)).replace('\\', '/')
    return out


def _엑셀_날짜(v: float, d1904: bool) -> str:
    base = dt.datetime(1904, 1, 1) if d1904 else dt.datetime(1899, 12, 30)
    x = base + dt.timedelta(seconds=round(v * 86400))      # 엑셀처럼 초 단위로 반올림해 보인다(8:53:59.99997 → 8:54)
    return x.strftime('%Y-%m-%d') if x.time() == dt.time(0) else x.strftime('%Y-%m-%d %H:%M' if x.second == 0 else '%Y-%m-%d %H:%M:%S')


def _서식_갈래(fid: int, code: str) -> str | None:
    """표시 형식이 날짜·시각·경과 시간·백분율인지. 근태 자료의 출퇴근 시각과 '[h]:mm' 합계 시간을 숫자로 두면 잘못 읽는다."""
    raw = code.lower()
    if re.search(r'\[(h+|m+|s+)\]', raw):
        return '경과'
    c = re.sub(r'"[^"]*"|\[[^\]]*\]|\\.', '', raw)
    if fid in (9, 10) or '%' in c:
        return '백분율'
    if fid in (18, 19, 20, 21, 45, 46, 47) or (fid >= 164 and re.search(r'[hs]', c) and not re.search(r'[yd]', c)):
        return '시각'
    if fid in (14, 15, 16, 17, 22) or (fid >= 164 and re.search(r'[ymd]', c)):
        return '날짜'
    return None


def _엑셀_값(글: str, 갈래: str | None, d1904: bool) -> str:
    """숫자 칸을 엑셀이 보여 주는 꼴로(일반 숫자는 엑셀처럼 유효 숫자 15자리)."""
    try:
        v = float(글)
    except ValueError:
        return 글
    try:
        if 갈래 == '날짜':
            return _엑셀_날짜(v, d1904)
        if 갈래 == '시각':
            if 0 <= v < 1:
                x = dt.datetime(2000, 1, 1) + dt.timedelta(seconds=round(v * 86400))
                return x.strftime('%H:%M' if x.second == 0 else '%H:%M:%S')
            return _엑셀_날짜(v, d1904)
        if 갈래 == '경과':
            분 = round(v * 24 * 60)
            return f'{"-" if 분 < 0 else ""}{abs(분) // 60}:{abs(분) % 60:02d}'
        if 갈래 == '백분율':
            return f'{v * 100:.15g}%'
    except (OverflowError, ValueError):
        return 글
    return f'{v:.15g}' if abs(v) < 1e15 else 글


def xlsx_시트들(data: bytes) -> dict:
    """{'시트': [(이름, 글, 숨김, [그 시트에 든 그림 이름])], '그림': [그림 항목]}"""
    with zipfile.ZipFile(_바이트(data)) as z:
        names = z.namelist()
        wb = ET.fromstring(z.read('xl/workbook.xml'))
        pr = wb.find(S + 'workbookPr')
        d1904 = pr is not None and pr.get('date1904') in ('1', 'true')
        rels = _rels(z, 'xl/workbook.xml')
        공유 = []
        if 'xl/sharedStrings.xml' in names:
            for si in ET.fromstring(z.read('xl/sharedStrings.xml')).findall(S + 'si'):
                공유.append(''.join(t.text or '' for t in si.iter(S + 't')))
        칸서식 = {}      # 칸 서식 번호 → '날짜'·'시각'·'경과'·'백분율'
        if 'xl/styles.xml' in names:
            st = ET.fromstring(z.read('xl/styles.xml'))
            서식 = {int(n.get('numFmtId')): n.get('formatCode', '') for n in st.iter(S + 'numFmt')}
            xfs = st.find(S + 'cellXfs')
            for i, xf in enumerate(xfs.findall(S + 'xf') if xfs is not None else []):
                fid = int(xf.get('numFmtId', '0'))
                g = _서식_갈래(fid, 서식.get(fid, ''))
                if g:
                    칸서식[i] = g
        시트 = []
        sheets = wb.find(S + 'sheets')
        for sh in (sheets.findall(S + 'sheet') if sheets is not None else []):
            이름 = nfc(sh.get('name', ''))
            경로 = rels.get(sh.get(R + 'id'))
            if not 경로 or 경로 not in names:
                시트.append((이름, '', sh.get('state') in ('hidden', 'veryHidden'), []))
                continue
            x = ET.fromstring(z.read(경로))
            숨긴열 = set()
            for c in x.iter(S + 'col'):
                if c.get('hidden') in ('1', 'true'):
                    숨긴열.update(range(int(c.get('min', '0')), int(c.get('max', '0')) + 1))
            줄 = []
            for row in x.iter(S + 'row'):
                칸 = []
                for c in row.findall(S + 'c'):
                    t, v, f = c.get('t'), c.find(S + 'v'), c.find(S + 'f')
                    if t == 'inlineStr':
                        val = ''.join(e.text or '' for e in c.iter(S + 't'))
                    elif v is None or v.text is None:
                        val = ''
                    elif t == 's':
                        val = 공유[int(v.text)] if int(v.text) < len(공유) else v.text
                    elif t == 'b':
                        val = 'TRUE' if v.text == '1' else 'FALSE'
                    elif t in ('str', 'e'):
                        val = v.text
                    else:
                        val = _엑셀_값(v.text, 칸서식.get(int(c.get('s') or 0)), d1904)
                    if not val and f is not None and (f.text or '').strip():
                        val = '=' + f.text
                    val = re.sub(r'\s+', ' ', val).strip()
                    if val:
                        칸.append(f'{_열(c.get("r", ""))}: {val}')
                if 칸:
                    줄.append(f'{row.get("r", "")}행' + (' (숨긴 행)' if row.get('hidden') in ('1', 'true') else '') + ' | ' + ' | '.join(칸))
            if 숨긴열:
                줄.append(f'(숨긴 열 {len(숨긴열)}개: 위 값에 들어 있다)')
            든그림 = []
            for rid, tgt in _rels(z, 경로).items():
                if 'drawing' in tgt and tgt in names:
                    든그림 += [m for m in _rels(z, tgt).values() if m.startswith('xl/media/')]
                    도형 = _a_글(z.read(tgt))
                    if 도형:
                        줄.append('[도형 글] ' + ' / '.join(도형))
                    for m in _rels(z, tgt).values():
                        if 'charts/chart' in m and m in names:
                            줄.append('[차트] ' + (' / '.join(_차트_글(z.read(m))) or '(글 없음, 값은 위 칸)'))
                if 'comments' in tgt and tgt in names:
                    cm = ET.fromstring(z.read(tgt))
                    authors = [a.text or '' for a in cm.iter(S + 'author')]
                    for c in cm.iter(S + 'comment'):
                        t = ''.join(e.text or '' for e in c.iter(S + 't')).strip()
                        a = authors[int(c.get('authorId', '0'))] if c.get('authorId', '0').isdigit() and int(c.get('authorId', '0')) < len(authors) else ''
                        if t:
                            줄.append(f'[메모 {c.get("ref", "")} {a}] ' + re.sub(r'\s+', ' ', t))
            시트.append((이름, '\n'.join(줄), sh.get('state') in ('hidden', 'veryHidden'), 든그림))
        그림 = 그림_모음(z, 'xl/media/')
    return {'시트': 시트, '그림': 그림}


def _a_글(xml: bytes) -> list:
    """도형·글상자의 문단 글(a:p)."""
    return [t for p in ET.fromstring(xml).iter(A + 'p') for t in [''.join(x.text or '' for x in p.iter(A + 't')).strip()] if t]


def _차트_글(xml: bytes) -> list:
    """차트의 제목·축 이름(a:t)과 계열 이름·항목 이름(c:v 가운데 숫자가 아닌 것)."""
    C = '{http://schemas.openxmlformats.org/drawingml/2006/chart}'
    x = ET.fromstring(xml)
    글 = _a_글(xml)
    for v in x.iter(C + 'v'):
        s = (v.text or '').strip()
        if s and not re.fullmatch(r'-?[\d.,E+-]+', s) and s not in 글:
            글.append(s)
    return 글


# ---------------------------------------------------------------- 파워포인트·한글(hwpx)
def pptx_슬라이드(data: bytes) -> dict:
    """{'슬라이드': [글], '그림': [그림 항목]}"""
    with zipfile.ZipFile(_바이트(data)) as z:
        names = z.namelist()
        pres = ET.fromstring(z.read('ppt/presentation.xml'))
        rels = _rels(z, 'ppt/presentation.xml')
        P = '{http://schemas.openxmlformats.org/presentationml/2006/main}'
        순서 = [rels.get(s.get(R + 'id')) for s in pres.iter(P + 'sldId')]
        out = []
        for 경로 in 순서:
            if not 경로 or 경로 not in names:
                out.append('')
                continue
            sl = ET.fromstring(z.read(경로))
            줄 = (['(숨긴 슬라이드)'] if sl.get('show') in ('0', 'false') else []) + _a_글(z.read(경로))
            for tgt in _rels(z, 경로).values():
                if tgt in names and ('diagrams/data' in tgt):
                    줄 += ['[스마트아트] ' + ' / '.join(_a_글(z.read(tgt)))] if _a_글(z.read(tgt)) else []
                if tgt in names and 'charts/chart' in tgt:
                    줄.append('[차트] ' + (' / '.join(_차트_글(z.read(tgt))) or '(글 없음)'))
                if 'notesSlide' in tgt and tgt in names:
                    메모 = [''.join(t.text or '' for t in p.iter(A + 't')).strip() for p in ET.fromstring(z.read(tgt)).iter(A + 'p')]
                    메모 = [x for x in 메모 if x and not x.isdigit()]
                    if 메모:
                        줄.append('[발표자 메모] ' + ' / '.join(메모))
            out.append('\n'.join(x for x in 줄 if x))
        그림 = 그림_모음(z, 'ppt/media/')
    return {'슬라이드': out, '그림': 그림}


def hwpx_글(data: bytes) -> dict:
    """{'글': 글, '그림': [그림 항목]}. 문단마다 한 줄(표 칸의 문단도 차례대로)."""
    with zipfile.ZipFile(_바이트(data)) as z:
        names = z.namelist()
        구역 = sorted((n for n in names if re.fullmatch(r'Contents/section\d+\.xml', n)), key=lambda n: int(re.sub(r'\D', '', n) or 0))
        줄 = []
        for n in 구역:
            for p in ET.fromstring(z.read(n)).iter():
                if p.tag.endswith('}p'):
                    t = ''.join(''.join(x.itertext()) for r in p if r.tag.endswith('}run') for x in r if x.tag.endswith('}t')).strip()
                    if t:
                        줄.append(t)
        그림 = 그림_모음(z, 'BinData/')
    return {'글': '\n'.join(줄), '그림': 그림}


# ---------------------------------------------------------------- 메일·텍스트
def 고유(이름: str, 쓴: list) -> str:
    """같은 이름의 첨부가 또 있으면 '이름 (2).확장자'로. 첨부를 이름으로 다시 찾으므로 겹치면 안 된다."""
    if 이름 not in 쓴:
        return 이름
    s, e = os.path.splitext(이름)
    i = 2
    while f'{s} ({i}){e}' in 쓴:
        i += 1
    return f'{s} ({i}){e}'


def 글자_풀기(data: bytes) -> str | None:
    """글자로만 된 파일이면 그 글(UTF-16 머리표, UTF-8, cp949 순으로 푼다), 아니면 None. 머리표 없이 NUL 이 있거나, 어느 글자 판으로도
    풀리지 않거나, 제어 문자(탭·줄바꿈·쪽 나눔 말고)가 글자의 1% 를 넘으면 글자로 된 파일이 아니다. 2026. 11. 3. `텍스트_글` 은 끝내 latin-1
    로 풀어, 이름만 .txt·.csv 인 깨진 파일도 엉터리 글로 읽혀 check 를 지났다."""
    if data[:2] in (b'\xff\xfe', b'\xfe\xff'):
        try:
            t = data.decode('utf-16')
        except UnicodeDecodeError:
            return None
    elif b'\x00' in data:
        return None
    else:
        for enc in ('utf-8-sig', 'cp949'):
            try:
                t = data.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        else:
            return None
    t = t.rstrip('\x1a')      # 옛 DOS 글 파일 끝의 Ctrl-Z
    제어 = sum(1 for c in t if (ord(c) < 32 and c not in '\t\n\r\f\v') or 0x7f <= ord(c) < 0xa0)
    return t if 제어 * 100 <= len(t) else None


def 텍스트_글(data: bytes) -> str:
    if data[:2] in (b'\xff\xfe', b'\xfe\xff'):      # UTF-16 은 머리표로 먼저 가린다(cp949 로도 풀려 글이 깨진다)
        try:
            return data.decode('utf-16')
        except UnicodeDecodeError:
            pass
    for enc in ('utf-8-sig', 'cp949'):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode('latin-1')


def html_글(data: bytes) -> dict | None:
    """HTML 문서(그룹웨어 품의서, 저장한 웹 화면, 메일 본문)의 {'글': 글, '넣은 그림': 파일에 든 그림 수, '바깥 그림': 바깥 주소 그림 수}.
    글자로 된 파일이 아니면 None 이다(`글자_풀기`). 스크립트·스타일·주석을 빼고, 줄을 나누는 꼬리표(br·p·div·tr·li·h·table·title)는 줄로,
    표 칸(td·th)은 ' | ' 로 바꾼 뒤 꼬리표를 걷는다(`eml_글` 의 HTML 본문과 같은 방식에 표 칸을 살린 것). 2026. 11. 12. `/하자보완`:
    그룹웨어에서 내려받은 구매품의서 .html 이 읽을 대상에 들지 않았다."""
    t = 글자_풀기(data)
    if t is None:
        return None
    t = re.sub(r'(?is)<!--.*?-->', '', re.sub(r'(?is)<(script|style)\b.*?</\1\s*>', '', t))
    그림 = re.findall(r'(?is)<img\b[^>]*>', t)
    넣은 = sum(1 for g in 그림 if re.search(r'''(?is)\bsrc\s*=\s*["']?\s*data:''', g))
    t = re.sub(r'(?i)<br\s*/?>|</(?:p|div|tr|li|h\d|table|title)\s*>', '\n', t)
    t = re.sub(r'(?i)</t[dh]\s*>', ' | ', t)
    t = html.unescape(re.sub(r'<[^>]+>', ' ', t))
    줄 = [re.sub(r'[ \t\u00a0\u3000]+', ' ', x).strip() for x in t.splitlines()]
    줄 = [re.sub(r'^(?:\|\s*)+|(?:\s*\|)+$', '', x).strip() for x in 줄]
    return {'글': '\n'.join(x for x in 줄 if x), '넣은 그림': 넣은, '바깥 그림': len(그림) - 넣은}


def eml_글(data: bytes) -> dict:
    """{'글': 머리와 본문, '첨부': [(이름, 바이트)]}"""
    m = email.message_from_bytes(data, policy=email.policy.default)
    줄 = [f'{h}: {m.get(h)}' for h in ('From', 'To', 'Cc', 'Date', 'Subject') if m.get(h)]
    본문, 웹, 첨부 = [], [], []
    for part in m.walk():
        if part.is_multipart():
            continue
        이름 = part.get_filename()
        if 이름 or part.get_content_disposition() == 'attachment' or part.get_content_maintype() not in ('text', 'multipart', 'message'):
            if not 이름:      # 본문에 넣은 그림(cid) 등 이름 없는 부분
                이름 = f'이름 없는 첨부{len(첨부) + 1}' + (mimetypes.guess_extension(part.get_content_type()) or '')
            첨부.append((고유(nfc(이름), [n for n, _ in 첨부]), part.get_payload(decode=True) or b''))
        elif part.get_content_type() in ('text/plain', 'text/html'):
            try:
                글 = part.get_content()
            except (LookupError, UnicodeDecodeError):
                글 = 텍스트_글(part.get_payload(decode=True) or b'')
            if part.get_content_type() == 'text/plain':
                본문.append(글)
            else:
                글 = re.sub(r'(?i)<br\s*/?>|</(?:p|div|tr|li|h\d|table)\s*>', '\n', re.sub(r'(?is)<(script|style).*?</\1>', '', 글))
                웹.append(html.unescape(re.sub(r'<[^>]+>', ' ', 글)))
    글자 = lambda xs: len(re.sub(r'\s', '', ''.join(xs)))
    if 웹 and 글자(본문) < 글자(웹) * 0.7:      # 글 본문이 없거나 HTML 본문보다 훨씬 짧으면(안내 문구만 있는 메일) HTML 본문도 읽는다
        본문 += (['[HTML 본문]'] if 본문 else []) + 웹
    줄.append('')
    줄 += [re.sub(r'[ \t]+', ' ', x) for x in '\n'.join(본문).splitlines()]
    if 첨부:
        줄.append('[첨부] ' + ', '.join(f'{n}({len(b):,}바이트)' for n, b in 첨부))
    return {'글': '\n'.join(줄), '첨부': 첨부}


# ---------------------------------------------------------------- 옛 형식 바꾸기
def soffice() -> str | None:
    후보 = [shutil.which('soffice'), shutil.which('libreoffice')]
    for env in ('ProgramFiles', 'ProgramFiles(x86)', 'ProgramW6432'):      # 윈도의 설치 자리(PC마다 같은 환경 변수)
        if os.environ.get(env):
            후보.append(str(Path(os.environ[env]) / 'LibreOffice' / 'program' / 'soffice.exe'))
    for c in 후보:
        if c and Path(c).is_file():
            return c
    return None


def _libre(data: bytes, ext: str, 바꿀: str) -> bytes | None:
    exe = soffice()
    if not exe:
        return None
    with 임시_폴더() as d:
        src = Path(d) / f'원본{ext}'
        src.write_bytes(data)
        try:
            subprocess.run([exe, '--headless', '--norestore', f'-env:UserInstallation=file:///{Path(d, "lo").as_posix().lstrip("/")}',
                            '--convert-to', 바꿀, '--outdir', str(Path(d) / 'out'), str(src)],
                           capture_output=True, timeout=180)
        except (OSError, subprocess.TimeoutExpired):
            return None
        out = list((Path(d) / 'out').glob('*'))
        return out[0].read_bytes() if out else None


def _한글_PDF(data: bytes, ext: str) -> bytes | None:
    """한글 자동화로 PDF 로 저장한다(윈도의 한글). 없으면 None.
    보안 모듈이 등록되지 않으면 파일 접근 창이 떠 멈추므로 쓰지 않고, 새 한글 창이 아니면 열려 있는 문서를 건드릴 수 있어 쓰지 않는다
    (`nlrc_forms.py`·`print_docs.py` 와 같은 조건). 암호가 걸린 파일은 암호 창을 띄우지 않고 못 연 것으로 친다."""
    if sys.platform != 'win32':
        return None
    try:
        import win32com.client as win32
        hwp = win32.DispatchEx('HWPFrame.HwpObject')
    except Exception:
        return None
    try:
        새창 = hwp.XHwpDocuments.Count == 1
        if not 새창 or not hwp.RegisterModule('FilePathCheckDLL', 'FilePathCheckerModuleExample'):
            if 새창:
                hwp.Quit()
            return None
    except Exception:
        return None
    with 임시_폴더() as d:
        src, out = Path(d) / f'원본{ext}', Path(d) / '바꿈.pdf'
        src.write_bytes(data)
        try:
            if not hwp.Open(str(src), 'HWPX' if ext == '.hwpx' else 'HWP', 'forceopen:true;suspendpassword:true'):
                return None
            hwp.SaveAs(str(out), 'PDF', '')
            return out.read_bytes() if out.is_file() else None
        except Exception:
            return None
        finally:
            try:
                hwp.Clear(1)
                hwp.Quit()
            except Exception:
                pass


OLE_서명 = b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'      # 복합 문서(MS-CFB)의 머리 8바이트. HWP 5 와 .doc·.xls·.msg 가 이 꼴이다


def 한글_판(data: bytes) -> int | None:
    """.hwp 바이트의 머리 서명으로 본 한글 문서의 판. 5(한글 2002 이후), 3(한글 97 이하), 한글 문서가 아니면 None.
    HWP 5 는 복합 문서이고 그 안의 FileHeader 스트림이 'HWP Document File'로 시작한다(스트림 이름은 복합 문서의 목록에 UTF-16 으로
    적힌다). HWP 3 이하는 파일 첫 30바이트가 'HWP Document File V3.00 '(2.x 는 V2.00·V2.10)에 1A 01 02 03 04 05 를 붙인 것이다.
    이름만 .hwp 인 hwpx(zip), 한글이 아닌 복합 문서(.doc 등), 깨진 파일은 None 이다."""
    if data[:8] == OLE_서명:
        return 5 if 'FileHeader'.encode('utf-16-le') in data and b'HWP Document File' in data else None
    return 3 if data[:19] == b'HWP Document File V' else None


def PDF로(이름: str, data: bytes) -> bytes | None:
    """한글 파일(.hwp)을 PDF 로. 이 PC의 한글로 바꾸고, 한글이 못 하면 한글 97 이하(HWP 3) 형식만 LibreOffice 로 바꾼다. 못 하면 None.
    머리 서명이 한글 문서가 아니면 바꾸지 않는다. LibreOffice 는 한글 거르개가 맞지 않는 바이트를 글 문서로 열어 PDF 를 만들고(가짜 .hwp 가
    1면짜리 글이 되었다), HWP 5 는 읽지 못해 그 바이트를 글자로 그린다(1면짜리 서식이 902면의 깨진 글이 되었다. 2026. 11. 3. LibreOffice 26.8).
    그렇게 만든 PDF 를 면마다 읽게 하면 문서를 읽지 않고도 check 를 지난다."""
    판 = 한글_판(data)
    if not 판:
        return None
    return _한글_PDF(data, '.hwp') or (_libre(data, '.hwp', 'pdf') if 판 == 3 else None)


_표시_머리 = re.compile(rb'\s*(?:<(?:!--|(?:!doctype|\?xml|html|head|body|table|meta|style|xml)\b)|mime-version\s*:)', re.I)


def 오피스_판(data: bytes, ext: str) -> str | None:
    """.doc·.xls 바이트의 머리 서명으로 본 꼴. 워드·엑셀·LibreOffice 는 맞지 않는 바이트도 글 문서로 열어 엉터리 글의 docx·xlsx 를 만들므로
    (2026. 11. 3. 깨진 .doc·.xls 가 그렇게 바뀌어 읽힌 것이 되었다. 같은 날 .hwp 의 `한글_판`) 바꾸기 전에 가린다.
    'ole'(워드·엑셀 97~2003 의 복합 문서. 그 안에 WordDocument·Workbook(엑셀 5·95 는 Book) 스트림이 있다), 'zip'(이름만 .doc·.xls 인
    docx·xlsx), 'rtf'(.doc), '표시'(HTML·MHT·XML 로 저장한 문서. 은행·급여 사이트의 '엑셀 내려받기'가 흔히 이렇다), 'biff'(엑셀 2~4),
    'word2'(워드 2 이하), '글'(쉼표·탭으로 나눈 글처럼 글자로만 된 파일. 바꾸지 않고 `글자_풀기` 로 읽는다. 변환기를 거치면 cp949·UTF-8 이
    깨진다). 어느 것도 아니면 None(깨졌거나, 암호가 걸린 새 형식이거나, 다른 형식의 파일이다)."""
    if data[:8] == OLE_서명:
        이름들 = ('WordDocument',) if ext == '.doc' else ('Workbook', 'Book')
        return 'ole' if any(n.encode('utf-16-le') in data for n in 이름들) else None
    if data[:4] == b'PK\x03\x04':
        return 'zip'
    머리 = data[:4096]
    if 머리[:2] in (b'\xff\xfe', b'\xfe\xff'):
        머리 = 머리.decode('utf-16', 'ignore').encode('utf-8')
    머리 = 머리[3:] if 머리[:3] == b'\xef\xbb\xbf' else 머리
    if ext == '.doc' and 머리.lstrip()[:5] == b'{\\rtf':
        return 'rtf'
    if _표시_머리.match(머리) or re.search(rb'(?im)^mime-version\s*:', 머리[:1024]):
        return '표시'
    if ext == '.xls' and data[:4] in (b'\x09\x00\x04\x00', b'\x09\x02\x06\x00', b'\x09\x04\x06\x00'):
        return 'biff'
    if ext == '.doc' and data[:2] in (b'\xdb\xa5', b'\x31\xbe'):
        return 'word2'
    return '글' if 글자_풀기(data) is not None else None


def _오피스_바꾸기(data: bytes, ext: str) -> bytes | None:
    """윈도의 워드·엑셀로 .doc → .docx, .xls → .xlsx(`evidence_cite_review.py` 의 워드 자동화와 같은 꼴). 없으면 None.
    암호가 걸린 파일은 암호 창을 띄우지 않게 빈 암호를 주어 못 연 것으로 친다."""
    if sys.platform != 'win32':
        return None
    try:
        import win32com.client as win32
    except ImportError:
        return None
    with 임시_폴더() as d:
        src, out = Path(d) / f'원본{ext}', Path(d) / ('바꿈.docx' if ext == '.doc' else '바꿈.xlsx')
        src.write_bytes(data)
        try:
            if ext == '.doc':
                app = win32.DispatchEx('Word.Application')
                app.Visible, app.DisplayAlerts = False, 0
                try:
                    doc = app.Documents.Open(str(src), ConfirmConversions=False, ReadOnly=True, AddToRecentFiles=False, PasswordDocument='')
                    doc.SaveAs2(str(out), FileFormat=16)      # wdFormatXMLDocument
                    doc.Close(False)
                finally:
                    if app.Documents.Count == 0:
                        app.Quit()
            else:
                app = win32.DispatchEx('Excel.Application')
                app.Visible, app.DisplayAlerts = False, False
                try:
                    wb = app.Workbooks.Open(str(src), UpdateLinks=0, ReadOnly=True, Password='')
                    wb.SaveAs(str(out), FileFormat=51)      # xlOpenXMLWorkbook
                    wb.Close(False)
                finally:
                    if app.Workbooks.Count == 0:
                        app.Quit()
            return out.read_bytes() if out.is_file() else None
        except Exception:
            return None


def 새형식(이름: str, data: bytes) -> bytes | None:
    """옛 형식 .doc → .docx, .xls → .xlsx. 윈도의 워드·엑셀, 없으면 LibreOffice. 못 하면 None.
    PDF 로 바꾸면 숨긴 시트·행·열과 메모가 빠지므로 새 형식으로 바꾸어 같은 방식(docx_글·xlsx_시트들)으로 읽는다.
    머리 서명이 워드·엑셀 문서가 아니거나 글자로만 된 파일이면 바꾸지 않는다(`오피스_판`)."""
    ext = Path(이름).suffix.lower()
    if 오피스_판(data, ext) in (None, '글'):
        return None
    b = _오피스_바꾸기(data, ext) or _libre(data, ext, 'docx' if ext == '.doc' else 'xlsx')
    return b if b and b[:2] == b'PK' else None


def msg_글(data: bytes) -> dict:
    """아웃룩 .msg. {'글': 머리와 본문, '첨부': [(이름, 바이트)]} 나 {'모름': 까닭}."""
    try:
        import extract_msg
    except ImportError:
        return {'모름': 'extract_msg 가 없어 .msg 를 읽지 못했다(아웃룩에서 .eml 이나 PDF 로 저장해 둔다)'}
    with 임시_폴더() as d:
        (Path(d) / 'a.msg').write_bytes(data)
        m = extract_msg.Message(str(Path(d) / 'a.msg'))
        try:
            머리 = [f'From: {m.sender}', f'To: {m.to}', f'Cc: {m.cc}', f'Date: {m.date}', f'Subject: {m.subject}', '', m.body or '']
            첨부 = []
            for a in m.attachments:
                첨부.append((고유(nfc(a.longFilename or a.shortFilename or '첨부'), [n for n, _ in 첨부]), a.data or b''))
        finally:
            m.close()
    return {'글': '\n'.join(x for x in 머리 if x is not None) + ('\n[첨부] ' + ', '.join(n for n, _ in 첨부) if 첨부 else ''), '첨부': 첨부}


def _바이트(data: bytes):
    import io
    return io.BytesIO(data)
