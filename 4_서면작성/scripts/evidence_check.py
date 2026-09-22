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
    python 4_서면작성/scripts/evidence_check.py sheet "{편철폴더}" --out 확인용.png

도장 검출은 오른쪽 여백의 붉은 계열 픽셀을 세는 방식이라 완전하지 않다. 표지가
붉은 문서에서는 없는 도장을 있다고 하고(오탐), 검은 도장은 놓친다(누락). 그래서
stamp 결과만으로 끝내지 말고 sheet 로 만든 이미지를 반드시 눈으로 본다.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
from pathlib import Path

try:
    import pymupdf
except ImportError:  # pymupdf 1.x 이전
    import fitz as pymupdf

HOJEUNG = re.compile(r'제\s*(\d+)\s*호증(?:\s*의\s*(\d+))?')


def _sort_key(path: Path):
    m = HOJEUNG.search(path.name)
    if not m:
        return (10**6, 0, path.name)
    return (int(m.group(1)), int(m.group(2) or 0), path.name)


def _pdfs(folder: Path) -> list[Path]:
    return sorted((p for p in folder.glob('*.pdf')), key=_sort_key)


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


def cmd_stamp(args) -> int:
    folder = Path(args.folder)
    files = _pdfs(folder)
    if not files:
        print(f'PDF 없음: {folder}')
        return 1
    bad = []
    for f in files:
        doc = pymupdf.open(f)
        marks = []
        for i, page in enumerate(doc):
            text = page.get_text()
            has_text_stamp = '호증' in text and '제' in text
            if _stamp_score(page) > 25 or has_text_stamp:
                marks.append(i + 1)
        flag = '' if 1 in marks else '   <<< 1면에 도장 없음'
        if not (1 in marks):
            bad.append(f.name)
        print(f'{f.name[:52]:54s} {doc.page_count:3d}면  도장면={marks}{flag}')
        doc.close()
    print()
    if bad:
        print(f'⚠️ 1면에 도장이 없는 파일 {len(bad)}건. 앞 호증 파일의 끝과 이어 붙는지 확인한다.')
        for n in bad:
            print(f'   - {n}')
        print('   한 건이라도 나오면 그 구간 앞뒤 호증을 함께 다시 본다. 해당 파일만 고치지 않는다.')
    else:
        print('모든 파일의 1면에 도장이 있다. 다만 오탐이 있을 수 있으므로 sheet 로 눈으로 확인한다.')
    return 0


def cmd_trace(args) -> int:
    src_dir, dst_dir = Path(args.source), Path(args.target)
    index: dict[str, list[str]] = {}
    for f in _pdfs(src_dir):
        doc = pymupdf.open(f)
        for i, page in enumerate(doc):
            index.setdefault(_page_hash(page), []).append(f'{f.stem}#p{i + 1}')
        doc.close()
    print(f'원본 {src_dir} — {sum(len(v) for v in index.values())}면 색인')
    print()
    used: dict[str, list[str]] = {}     # 원본 면 지문 -> 그 면을 쓴 편철 위치
    missing = 0
    for f in _pdfs(dst_dir):
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


def cmd_sheet(args) -> int:
    from PIL import Image, ImageDraw
    folder = Path(args.folder)
    files = _pdfs(folder)
    if not files:
        print(f'PDF 없음: {folder}')
        return 1
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
        out = Path(args.out)
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
    p3.add_argument('--out', default='증거확인.png')
    p3.add_argument('--cols', type=int, default=5)
    p3.add_argument('--rows', type=int, default=3)
    p3.add_argument('--dpi', type=int, default=52)
    p3.add_argument('--all-pages', action='store_true', help='첫 면만이 아니라 모든 면')
    p3.set_defaults(func=cmd_sheet)

    args = ap.parse_args()
    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
