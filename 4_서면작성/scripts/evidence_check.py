"""편철한 호증 파일이 표제와 맞는지, 호증 경계가 밀리지 않았는지 대조한다.

합본 PDF를 호증별로 나눌 때 도장이 찍힌 첫 장이 앞 호증 파일 끝에 붙는 경계
어긋남이 잘 생긴다. 한 번 밀리면 그 뒤 호증이 줄줄이 밀리고, 표제와 내용이 다른
채로 제출된다(2026. 9. 16. 이케아 사건에서 갑 제21·22·35·43호증 4건 발생).
사람이 눈으로 볼 자리를 좁혀 주는 것이 이 스크립트의 일이고, 맞다 틀리다는
판단하지 않는다.

    # 1) 도장 위치 — 1면에 도장이 없는 파일을 찾는다
    python 4_서면작성/scripts/evidence_check.py stamp "{사건}/라운드N/우리증거"

    # 2) 출처 대조 — 편철본의 각 면이 원본 어느 파일 몇 면에서 왔는지
    python 4_서면작성/scripts/evidence_check.py trace "{원본폴더}" "{편철폴더}"

    # 3) 첫 면 모음 — 표제와 내용을 눈으로 대조할 이미지를 만든다
    python 4_서면작성/scripts/evidence_check.py sheet "{편철폴더}" --out "{사건}/증거관리/증거확인.png"

sheet 는 --out 이 없으면 편철폴더가 속한 사건 폴더(…/사건/{사건명}/)의
증거관리/증거확인.png 에 쓴다. 현재 폴더(저장소 루트)에 쓰지 않는다. 의뢰인 증거의 첫 면을
모은 이미지이므로 git 이 무시하는 사건/ 아래에 두어야 한다. 사건 폴더 아래가 아니면
--out 을 달라고 하고 멈춘다.

도장은 두 가지로 찾는다. ① 오른쪽 여백(가로 78% 오른쪽)의 붉은 계열 픽셀, ② 면 위쪽 20%·
오른쪽 절반 자리에 호증번호만 적힌 줄(표지 라벨, 예: '갑 제1호증'). 본문 문장 속
'사 제3호증에 의하면' 같은 인용이나 왼쪽·아래의 목록 칸은 도장으로 치지 않는다.
그래도 완전하지 않다. 표지가 붉은 문서에서는 없는 도장을 있다고 하고(오탐), 검은 도장과
다른 자리의 표지는 놓친다(누락). 그래서 stamp 결과만으로 끝내지 말고 sheet 로 만든
이미지를 반드시 눈으로 본다.

stamp 는 찾은 표지 라벨을 함께 적는다. 1면 표지가 파일명과 같은 기호(갑·을·사 …)인데
번호가 다르거나, 2면 이후에 1면과 다른 표지 라벨이 있으면 경계가 밀렸을 수 있다고
표시한다. 사→갑처럼 번호를 새로 매긴 호증은 옛 표지가 남는 것이 정상이므로 기호가
다르면 번호를 견주지 않는다. 2면 이후의 붉은 도장은 직인·인감과 구별되지 않아
도장면 목록에만 싣는다.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import os
import re
import sys
from pathlib import Path

try:
    import pymupdf
except ImportError:  # pymupdf 1.x 이전
    import fitz as pymupdf

ROOT = Path(__file__).resolve().parents[2]
# 호증번호 정규식은 공통/scripts/system.py 의 것을 그대로 쓴다(citation_check.py 와 같다).
_spec = importlib.util.spec_from_file_location('workflow_system', ROOT / '공통/scripts/system.py')
_system = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_system)

HOJEUNG = re.compile(r'제\s*(\d+)\s*호증(?:\s*의\s*(\d+))?')
EVIDENCE = re.compile(_system.EVIDENCE_NUMBER)
# 표지 라벨('갑 제1호증')을 찾는 자리. 면 높이의 위쪽 20%, 너비의 오른쪽 절반(줄의 왼쪽 끝 기준).
STAMP_TOP = 0.2
STAMP_LEFT = 0.5


def _sort_key(path: Path):
    m = HOJEUNG.search(path.name)
    if not m:
        return (10**6, 0, path.name)
    return (int(m.group(1)), int(m.group(2) or 0), path.name)


def _pdfs(folder: Path) -> list[Path]:
    return sorted((p for p in folder.glob('*.pdf')), key=_sort_key)


def _require_pdfs(folder: Path) -> list[Path]:
    """PDF 목록. 폴더가 없거나 PDF 가 없으면 그 사실을 적고 빈 목록을 돌려준다."""
    files = _pdfs(folder)
    if not files:
        print(f'{"PDF 없음" if folder.is_dir() else "폴더 없음"}: {folder}')
    return files


def _page_hash(page, dpi: int = 36) -> str:
    """면 지문. **렌더한 픽셀만 쓴다.**

    PDF 내부 참조번호(xref)나 `page.get_images()` 결과를 지문에 섞지 않는다.
    면을 새 파일로 떼어내면 그 번호가 다시 매겨져 같은 면이 다른 것으로 나온다
    (2026. 9. 22. GGM 정직 3월 증거 검증에서 83면 전부를 불일치로 잘못 보고했다).
    """
    pix = page.get_pixmap(dpi=dpi)
    return hashlib.md5(pix.samples).hexdigest()


def _stamp_score(page) -> int:
    """오른쪽 여백의 붉은 도장 픽셀 수."""
    import numpy as np
    pix = page.get_pixmap(dpi=60)
    a = np.frombuffer(pix.samples, dtype=np.uint8)
    a = a.reshape(pix.height, pix.width, pix.n)[:, :, :3].astype(int)
    reg = a[:, int(a.shape[1] * 0.78):]
    r, g, b = reg[:, :, 0], reg[:, :, 1], reg[:, :, 2]
    return int(((r > 110) & (r - g > 55) & (r - b > 45)).sum())


def _text_labels(page) -> list[str]:
    """면 오른쪽 위에서 호증번호만 적힌 줄이나 글자 묶음을 찾아 공백을 지운 번호로 돌려준다.

    줄 전체가 호증번호 하나여야 한다. 본문 문장 속 '사 제3호증에 의하면' 은 걸리지 않는다.
    좌표는 회전을 반영해 화면에 보이는 면 기준으로 본다.
    """
    w, h = page.rect.width, page.rect.height
    found = []
    for block in page.get_text('dict')['blocks']:
        for line in block.get('lines', []):
            spans = line['spans']
            pieces = [(line['bbox'], ''.join(s['text'] for s in spans))]
            pieces += [(s['bbox'], s['text']) for s in spans] if len(spans) > 1 else []
            for bbox, text in pieces:
                box = pymupdf.Rect(bbox) * page.rotation_matrix
                if box.x0 < w * STAMP_LEFT or box.y1 > h * STAMP_TOP:
                    continue
                compact = re.sub(r'\s+', '', text)
                if compact and EVIDENCE.fullmatch(compact):
                    found.append(compact)
                    break
    return found


def _label_key(text: str):
    """'갑제3호증의1' → ('갑', 3). 호증번호가 없으면 None."""
    m = EVIDENCE.search(re.sub(r'\s+', '', text))
    if not m:
        return None
    head, _, tail = m.group(0).partition('제')
    return head, int(re.match(r'\d+', tail).group(0))


def _conflicts(name: str, label: str) -> bool:
    """파일명과 1면 표지의 기호가 같은데 번호가 다르면 참. 기호가 다르면 새로 매긴 번호로 보고 견주지 않는다."""
    mine, theirs = _label_key(name), _label_key(label)
    return bool(mine and theirs and mine[0] == theirs[0] and mine[1] != theirs[1])


def cmd_stamp(args) -> int:
    folder = Path(args.folder)
    files = _require_pdfs(folder)
    if not files:
        return 1
    bad, mismatch, later = [], [], []
    for f in files:
        doc = pymupdf.open(f)
        marks, first, extra = [], None, []
        for i, page in enumerate(doc):
            labels = _text_labels(page)
            if _stamp_score(page) > 25 or labels:
                marks.append(i + 1)
            if i == 0:
                first = labels[0] if labels else None
                continue
            # 면마다 같은 표지를 찍은 파일도 있으므로 1면 표지와 다른 것만 짚는다
            others = [label for label in labels if label != first]
            if others:
                extra.append(f'{i + 1}면 {others[0]}')
        notes = f'  표지={first}' if first else ''
        if 1 not in marks:
            bad.append(f.name)
            notes += '   <<< 1면에 도장 없음'
        if first and _conflicts(f.name, first):
            mismatch.append(f'{f.name} — 1면 표지 {first}')
            notes += '   <<< 표지 번호가 파일명과 다름'
        if extra:
            later.append(f'{f.name} — {", ".join(extra)}')
            notes += f'   <<< 1면과 다른 표지: {", ".join(extra)}'
        print(f'{f.name[:52]:54s} {doc.page_count:3d}면  도장면={marks}{notes}')
        doc.close()
    print()
    if bad:
        print(f'⚠️ 1면에 도장이 없는 파일 {len(bad)}건. 앞 호증 파일의 끝과 이어 붙는지 확인한다.')
        for n in bad:
            print(f'   - {n}')
        print('   한 건이라도 나오면 그 구간 앞뒤 호증을 함께 다시 본다. 해당 파일만 고치지 않는다.')
    if mismatch:
        print(f'⚠️ 1면 표지 번호가 파일명과 다른 파일 {len(mismatch)}건. 다른 호증의 첫 장으로 시작하는지 본다.')
        for n in mismatch:
            print(f'   - {n}')
    if later:
        print(f'⚠️ 2면 이후에 1면과 다른 호증 표지가 있는 파일 {len(later)}건. 다음 호증 첫 장이 붙었거나 '
              '두 호증이 섞였을 수 있다. sheet --all-pages 로 확인한다.')
        for n in later:
            print(f'   - {n}')
    if not (bad or mismatch or later):
        print('모든 파일의 1면에 도장이 있다. 다만 오탐이 있을 수 있으므로 sheet 로 눈으로 확인한다.')
    return 0


def cmd_trace(args) -> int:
    src_dir, dst_dir = Path(args.source), Path(args.target)
    # 한쪽이라도 비면 대조한 것이 없는데 세 수치가 모두 0으로 나와 이상 없음처럼 보인다.
    sources, targets = _require_pdfs(src_dir), _require_pdfs(dst_dir)
    if not (sources and targets):
        print('대조하지 않았다. 두 경로를 확인한다. 경로는 저장소 루트 기준이다'
              '(예: 4_서면작성/사건/{사건명}/라운드N/우리증거).')
        return 1
    index: dict[str, list[str]] = {}
    for f in sources:
        doc = pymupdf.open(f)
        for i, page in enumerate(doc):
            index.setdefault(_page_hash(page), []).append(f'{f.stem}#p{i + 1}')
        doc.close()
    print(f'원본 {src_dir} — {sum(len(v) for v in index.values())}면 색인')
    print()
    used: dict[str, list[str]] = {}     # 원본 면 지문 -> 그 면을 쓴 편철 위치
    missing = 0
    for f in targets:
        doc = pymupdf.open(f)
        prov = []
        for i, p in enumerate(doc):
            h = _page_hash(p)
            if h in index:
                used.setdefault(h, []).append(f'{f.stem}#p{i + 1}')
            else:
                missing += 1
            prov.append('/'.join(index.get(h, ['(원본없음)'])))
        uniq = {p.split('#')[0] for p in prov if p != '(원본없음)'}
        warn = ''
        if len(uniq) > 1:
            warn = '   <<< 두 개 이상의 원본 파일이 섞였다'
        print(f'{f.name[:52]:54s} {doc.page_count:3d}면  <- {" | ".join(prov)}{warn}')
        doc.close()

    # 원본 쪽에서 본다: 두 번 쓰인 면과 한 번도 안 쓰인 면
    dup = {h: v for h, v in used.items() if len(v) > 1}
    unused = [index[h] for h in index if h not in used]
    total = sum(len(v) for v in index.values())
    print()
    print(f'원본 {total}면 중 {total - len(unused)}면 사용, {len(unused)}면 미사용'
          f' · 중복 사용 {len(dup)}건 · 원본에 없는 편철 면 {missing}면')
    if dup:
        print('⚠️ 같은 원본 면이 두 곳에 들어갔다. 의도한 것이 아니면 한쪽을 뺀다.')
        for h, where in dup.items():
            print(f'   {index[h][0]} → {", ".join(where)}')
    if unused:
        print('미사용 원본 면 — 뺀 이유를 호증목록 비고에 적는다. 빠뜨린 것이면 호증을 더 만든다.')
        for names in sorted(unused):
            print(f'   {"/".join(names)}')
    print()
    print('편철본이 원본 한 파일에서 p1부터 연속으로 왔는지 본다. 중간이 끊기거나')
    print('두 파일이 섞였으면 경계가 밀렸을 수 있다. (원본없음)은 신규 서증이다.')
    return 0


# sheet 표제 글꼴. 앞에서부터 찾는다. PIL 기본 글꼴에는 한글이 없어 표제가 네모로 깨진다.
LABEL_FONTS = ('malgun.ttf', 'gulim.ttc', 'batang.ttc')
LABEL_MIN_SIZE = 10


def _label_font_path() -> Path | None:
    """Windows 글꼴 폴더에서 한글 TrueType 글꼴을 찾는다. 폴더는 환경변수로 정한다."""
    from PIL import ImageFont
    dirs = [Path(os.environ[v]) / 'Fonts' for v in ('WINDIR', 'SystemRoot') if os.environ.get(v)]
    for name in LABEL_FONTS:
        for d in dirs:
            path = d / name
            if not path.is_file():
                continue
            try:
                ImageFont.truetype(str(path), LABEL_MIN_SIZE)
            except OSError:
                continue
            return path
    return None


def _label_font(labels: list[str], limit: int):
    """가장 긴 표제가 limit 픽셀에 들어가는 가장 큰 크기로 연다. 모든 칸에 같은 크기를 쓴다."""
    from PIL import ImageFont
    path = _label_font_path()
    if path is None:
        print(f'⚠️ 한글 글꼴({"·".join(LABEL_FONTS)})을 찾지 못해 기본 글꼴로 표제를 그린다. '
              '표제의 한글이 깨지므로 칸 순서(호증번호 정렬)와 내용으로 대조한다.', file=sys.stderr)
    size = max(LABEL_MIN_SIZE, limit // 15)
    while True:
        if path is not None:
            font = ImageFont.truetype(str(path), size)
        else:
            try:
                font = ImageFont.load_default(size)
            except TypeError:  # Pillow 10.1 이전은 크기를 받지 않는다
                return ImageFont.load_default(), None
        if size <= LABEL_MIN_SIZE or max(font.getlength(t) for t in labels) <= limit:
            return font, path
        size -= 1


def _clip_label(text: str, font, limit: int) -> str:
    """가장 작은 크기로도 칸을 넘는 표제는 뒤를 줄이고 '…'를 붙인다."""
    if font.getlength(text) <= limit:
        return text
    while text and font.getlength(text + '…') > limit:
        text = text[:-1]
    return text + '…'


def _case_dir(folder: Path) -> Path | None:
    """편철폴더가 속한 사건 폴더(가장 안쪽 '사건' 폴더의 바로 아래). 없으면 None.

    저장소를 품은 바깥 폴더의 이름이 우연히 '사건' 이어도 그 아래를 사건 폴더로 보지 않는다.
    """
    parts = folder.resolve().parts
    for k in range(len(parts) - 2, -1, -1):
        if parts[k] == '사건':
            case = Path(*parts[:k + 2])
            return None if ROOT.is_relative_to(case) else case
    return None


def _sheet_out(args, folder: Path) -> Path | None:
    """sheet 의 저장 경로. --out 이 없으면 사건 폴더의 증거관리/증거확인.png 이다.

    현재 폴더(저장소 루트)에 쓰면 의뢰인 증거 첫 면 모음이 git 추적 대상이 되므로 그리로 쓰지 않는다.
    """
    if args.out:
        return Path(args.out)
    case = _case_dir(folder)
    if case is None:
        print(f'저장할 곳을 정하지 못했다. 편철폴더가 사건 폴더(…/사건/{{사건명}}/) 아래에 있지 않다: {folder}')
        print('   --out 으로 사건 폴더 안 경로를 준다(예: --out "{사건}/증거관리/증거확인.png").')
        return None
    return case / '증거관리' / '증거확인.png'


def cmd_sheet(args) -> int:
    from PIL import Image, ImageDraw
    folder = Path(args.folder)
    files = _require_pdfs(folder)
    if not files:
        return 1
    base_out = _sheet_out(args, folder)
    if base_out is None:
        return 1
    base_out.parent.mkdir(parents=True, exist_ok=True)
    tiles = []
    for f in files:
        doc = pymupdf.open(f)
        pages = range(doc.page_count) if args.all_pages else [0]
        for i in pages:
            pix = doc[i].get_pixmap(dpi=args.dpi)
            img = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
            label = f.stem[:28] + (f' p{i + 1}' if args.all_pages else '')
            tiles.append((label, img))
        doc.close()
    cols = args.cols
    w = max(i.width for _, i in tiles)
    h = max(i.height for _, i in tiles)
    # 표제는 칸 맨 위 흰 띠에 쓰고 문서는 그 아래에 붙인다. 문서 위에 겹쳐 쓰면
    # 1면 위쪽에 찍힌 호증 도장과 문서 제목이 가려진다.
    border, pad = 4, max(4, w // 80)
    limit = w - 2 * (border + pad)
    font, font_path = _label_font([label for label, _ in tiles], limit)
    _, top, _, bottom = font.getbbox('증제0호증Ag')
    band = border + pad + (bottom - top) + pad
    out_paths = []
    per = cols * args.rows
    for start in range(0, len(tiles), per):
        chunk = tiles[start:start + per]
        rows = (len(chunk) + cols - 1) // cols
        sheet = Image.new('RGB', (cols * w, rows * (band + h)), 'white')
        draw = ImageDraw.Draw(sheet)
        for k, (label, img) in enumerate(chunk):
            x, y = (k % cols) * w, (k // cols) * (band + h)
            sheet.paste(img, (x, y + band))
            draw.line([x, y + band - 1, x + w - 1, y + band - 1], fill='darkgray')
            draw.rectangle([x, y, x + w - 1, y + band + h - 1], outline='red', width=border)
            draw.text((x + border + pad, y + border + pad - top), _clip_label(label, font, limit),
                      font=font, fill='red')
        out = base_out
        if len(tiles) > per:
            out = out.with_name(f'{out.stem}_{start // per + 1}{out.suffix}')
        sheet.save(out)
        out_paths.append(out)
    for p in out_paths:
        print(f'만들었다: {p}')
    if font_path:
        print(f'표제 글꼴: {font_path.name}, {font.size}px')
    print()
    print('각 칸의 표제(파일명)와 그 아래 내용이 같은 문서인지 본다.')
    print('첫 면이 문서 중간부터 시작하거나 앞 호증의 꼬리로 보이면 경계가 밀린 것이다.')
    return 0


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)

    p1 = sub.add_parser('stamp', help='1면에 호증 도장이 있는지 본다')
    p1.add_argument('folder')
    p1.set_defaults(func=cmd_stamp)

    p2 = sub.add_parser('trace', help='편철본의 각 면이 원본 어디에서 왔는지 대조한다')
    p2.add_argument('source')
    p2.add_argument('target')
    p2.set_defaults(func=cmd_trace)

    p3 = sub.add_parser('sheet', help='첫 면을 모아 육안 확인용 이미지를 만든다')
    p3.add_argument('folder')
    p3.add_argument('--out', help='저장 경로. 없으면 사건 폴더의 증거관리/증거확인.png. '
                                  '한 장(--cols × --rows 칸)을 넘으면 _1, _2 … 를 붙여 여러 장으로 쓴다')
    p3.add_argument('--cols', type=int, default=5)
    p3.add_argument('--rows', type=int, default=3)
    p3.add_argument('--dpi', type=int, default=52)
    p3.add_argument('--all-pages', action='store_true', help='첫 면만이 아니라 모든 면')
    p3.set_defaults(func=cmd_sheet)

    args = ap.parse_args()
    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
