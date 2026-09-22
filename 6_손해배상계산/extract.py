#!/usr/bin/env python3
"""사건 폴더의 자료에서 텍스트를 뽑아 한 파일에 모은다.

    python extract.py 사건/삼양식품

PDF·docx·xlsx·csv·txt·md 를 읽어 `<폴더>/_추출.txt` 로 쓴다.
한글(.hwp)은 지원하지 않는다. PDF 나 docx 로 저장해서 넣어야 한다.

추출 결과는 사건 자료이므로 저장소에 커밋하지 않는다(.gitignore 로 막혀 있다).
"""

from __future__ import annotations

import sys
from pathlib import Path

SUPPORTED = {".pdf", ".docx", ".xlsx", ".xlsm", ".csv", ".txt", ".md"}
SKIP_NAMES = {"_추출.txt", "사건.yaml"}


def from_pdf(path: Path) -> str:
    from pypdf import PdfReader

    out = []
    for i, page in enumerate(PdfReader(str(path)).pages, 1):
        t = (page.extract_text() or "").strip()
        if t:
            out.append(f"--- p.{i} ---\n{t}")
    return "\n".join(out) or "(텍스트를 뽑지 못했다. 스캔 PDF 일 수 있다)"


def from_docx(path: Path) -> str:
    import docx

    d = docx.Document(str(path))
    out = [p.text.strip() for p in d.paragraphs if p.text.strip()]
    for ti, t in enumerate(d.tables, 1):
        out.append(f"[표 {ti}]")
        for row in t.rows:
            cells = [c.text.strip() for c in row.cells]
            if any(cells):
                out.append(" | ".join(cells))
    return "\n".join(out)


def from_xlsx(path: Path) -> str:
    import openpyxl

    wb = openpyxl.load_workbook(str(path), data_only=True)
    out = []
    for ws in wb.worksheets:
        out.append(f"[시트 {ws.title}]")
        for row in ws.iter_rows():
            cells = [f"{c.coordinate}={c.value}" for c in row if c.value is not None]
            if cells:
                out.append(" | ".join(cells))
    return "\n".join(out)


def from_text(path: Path) -> str:
    for enc in ("utf-8", "cp949", "utf-8-sig"):
        try:
            return path.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
    return "(인코딩을 읽지 못했다)"


READERS = {".pdf": from_pdf, ".docx": from_docx, ".xlsx": from_xlsx,
           ".xlsm": from_xlsx, ".csv": from_text, ".txt": from_text, ".md": from_text}


def main(folder: str) -> None:
    root = Path(folder)
    if not root.is_dir():
        sys.exit(f"폴더가 없습니다: {root}")

    parts, skipped = [], []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name in SKIP_NAMES or path.name.startswith("~$"):
            continue
        if path.suffix.lower() not in SUPPORTED:
            skipped.append(path.relative_to(root))
            continue
        try:
            body = READERS[path.suffix.lower()](path)
        except Exception as exc:
            body = f"(읽기 실패: {type(exc).__name__} {exc})"
        parts.append(f"\n{'='*70}\n■ {path.relative_to(root)}\n{'='*70}\n{body}")
        print(f"  읽음  {path.relative_to(root)}")

    out = root / "_추출.txt"
    header = f"사건 폴더: {root}\n파일 {len(parts)}건"
    if skipped:
        header += "\n\n[지원하지 않는 형식 — PDF 나 docx 로 저장해서 넣으세요]\n"
        header += "\n".join(f"  {s}" for s in skipped)
        for s in skipped:
            print(f"  건너뜀 {s}")
    out.write_text(header + "\n".join(parts), encoding="utf-8")
    print(f"\n-> {out}  ({out.stat().st_size:,} bytes)")
    if skipped:
        print("   .hwp 는 텍스트를 뽑지 못합니다. 한글에서 PDF 로 저장해 주세요.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ('-h', '--help'):
        print(__doc__); sys.exit(0)
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
