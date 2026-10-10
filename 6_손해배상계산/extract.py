#!/usr/bin/env python3
"""사건 폴더의 자료에서 텍스트를 뽑아 한 파일에 모은다.

    python extract.py 사건/삼양식품

PDF·docx·xlsx·csv·txt·md 를 읽어 `<폴더>/_추출.txt` 로 쓴다.
한글(.hwp)은 지원하지 않는다. PDF 나 docx 로 저장해서 넣어야 한다.

엔진이 만든 계산 결과물(계산 폴더 `계산/` 아래 파일, `*_노동금액계산표*.xlsx`)과 자체 검토 자료
(`자체검토/` 아래 파일, 공통/자체검토.md 2절)는 자료가 아니므로 읽지 않고 머리에 이름만 적는다.
다시 계산할 때 이전 계산값과 검토 기록이 자료로 섞이지 않게 한다. 사건상태 기록(`사건상태.md`·`자료목록.json`)과
추출 캐시(`추출캐시/`)도 읽지 않는다.
계산 폴더가 자료 폴더와 같은 사건(`사건/{사건명}/`)에서는 `/손배계산`·`/손배검산` 이 만든 파일이 자료 옆에 놓이므로,
사건 폴더 바로 아래에 있고 이름이 `{폴더 이름}_계산표`·`{폴더 이름}_검산표` 와 같거나 `{폴더 이름}_대안계산표` 로 시작하는 xlsx·xlsm
(옵션을 여럿 바꾸어 돌린 `{폴더 이름}_대안계산표2.xlsx` 등)도 같이 거른다. 검산용 입력·스크립트(`검산_*.yaml`·`검산_*.yml`·`검산_*.py`)는
사건 폴더 바로 아래든 하위 폴더든 거른다.
상대방·법원의 별지 계산표는 자료이므로 이름에 '계산표'나 '검산표'가 있다는 것만으로 거르지 않는다.
그 밖의 계산표·검산표(이름이 위와 다르거나 다른 하위 폴더에 든 것)는 자료로 읽는다.
받은 계산표가 사건 폴더 바로 아래에 이 세 가지 이름(계산표·검산표·대안계산표)으로 놓여 있으면 우리 결과물로 보아 읽지 않는다.
`_추출.txt` 머리의 '읽지 않음' 목록(화면의 '제외' 줄)에 받은 계산표가 있으면 이름을 바꾸거나 `계산/`·`자체검토/` 가 아닌 하위 폴더로 옮긴 뒤 다시 돌린다.

추출 결과는 사건 자료이므로 저장소에 커밋하지 않는다(.gitignore 로 막혀 있다).
"""

from __future__ import annotations

import sys
from pathlib import Path

SUPPORTED = {".pdf", ".docx", ".xlsx", ".xlsm", ".csv", ".txt", ".md"}
SKIP_NAMES = {"_추출.txt", "사건.yaml", "사건상태.md", "자료목록.json"}   # 뒤의 둘은 공통/사건상태.md 의 작성 메모와 기준 목록
SKIP_DIRS = {"추출캐시"}               # 공통/scripts/system.py extract 가 남기는 캐시
OUTPUT_DIRS = {"계산", "자체검토"}      # 손배계산.md 0절의 계산 폴더, 자체 검토 자료(공통/자체검토.md 2절)
OUTPUT_MARK = "_노동금액계산표"         # cli.py·watch.py 의 노동 금액 계산표 이름
# 명령어 지침이 -o 로 주게 한 이름의 꼬리. 앞은 사건명(계산 폴더가 자료 폴더와 같은 사건에서는 그 폴더 이름)이다
OUTPUT_TAILS = ("_계산표", "_검산표")   # 손배계산.md 5절(신체손해 계산표), 손배검산.md(검산표)
OUTPUT_ALT = "_대안계산표"             # 손배검산.md 의 대안계산표. 옵션을 여럿 바꾸어 돌리면 뒤에 번호가 붙으므로 이 이름으로 시작하는 것을 거른다
CHECK_PREFIX = "검산_"                 # 손배검산.md 의 검산용 입력(검산_사건.yaml·검산_사건_대안.yaml)과 남겨 둔 스크립트(검산_{항목}.py)


def is_engine_output(rel: Path, case: str = "") -> bool:
    """엔진이 만든 계산 결과물이나 검산용 입력·스크립트, 자체 검토 자료인지. rel 은 사건 폴더 기준 상대경로, case 는 사건 폴더 이름."""
    if any(part in OUTPUT_DIRS for part in rel.parts[:-1]):
        return True
    suffix = rel.suffix.lower()
    if rel.name.startswith(CHECK_PREFIX) and suffix in (".yaml", ".yml", ".py"):
        return True
    if suffix not in (".xlsx", ".xlsm"):
        return False
    if OUTPUT_MARK in rel.stem:
        return True
    # 상대방·법원의 계산표가 걸리지 않게, 사건 폴더 바로 아래에 지침이 정한 이름으로 있는 것만 거른다
    if not case or len(rel.parts) != 1:
        return False
    return rel.stem in {case + tail for tail in OUTPUT_TAILS} or rel.stem.startswith(case + OUTPUT_ALT)


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

    parts, skipped, outputs = [], [], []
    case = root.resolve().name
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name in SKIP_NAMES or path.name.startswith("~$"):
            continue
        if SKIP_DIRS & set(path.relative_to(root).parts[:-1]):
            continue
        if is_engine_output(path.relative_to(root), case):
            outputs.append(path.relative_to(root))
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
    if outputs:
        header += "\n\n[계산 결과물·검산용 입력·자체 검토 자료 — 자료가 아니므로 읽지 않음]\n"
        header += "\n".join(f"  {s}" for s in outputs)
        for s in outputs:
            print(f"  제외   {s}")
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
    # Windows 파이프(cp949)에서 파일 이름·안내 출력이 UnicodeEncodeError 로 멈추지 않게 한다.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    if len(sys.argv) > 1 and sys.argv[1] in ('-h', '--help'):
        print(__doc__); sys.exit(0)
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
