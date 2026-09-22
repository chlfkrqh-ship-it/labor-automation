#!/usr/bin/env python3
"""노동사건 자동화 — 입력 폴더를 지켜보다가 계산표를 만든다.

    python watch.py                     한 번 훑고 끝 (기본)
    python watch.py --loop              10초마다 계속 지켜봄
    python watch.py --root D:\\다른폴더

폴더 구조 (없으면 만든다. 기본 위치는 6_손해배상계산 폴더 자신)

    6_손해배상계산/
      00_양식/     입력서.xlsx  <- 이걸 복사해서 채운다
      01_입력/     채운 입력서(.xlsx)나 사건 파일(.yaml)을 여기 넣는다
      02_결과/     계산표가 여기 나온다
      03_보관/     처리한 입력 파일이 여기로 옮겨진다
      99_오류/     처리 실패한 파일과 사유

전부 로컬에서 돈다. 사건 자료가 밖으로 나가지 않는다.
"""

from __future__ import annotations

import argparse
import shutil
import time
import traceback
from datetime import datetime
from pathlib import Path

from engine.calculate import calculate
from engine.case import Case, load
from engine.excel import write_workbook
from engine.inputform import make_template, read_form

SUB = ["00_양식", "01_입력", "02_결과", "03_보관", "99_오류"]
SUFFIXES = {".xlsx", ".xlsm", ".yaml", ".yml"}


def ensure_root(root: Path) -> Path:
    for name in SUB:
        (root / name).mkdir(parents=True, exist_ok=True)
    form = root / "00_양식" / "입력서.xlsx"
    if not form.exists():
        make_template(form)
        print(f"  입력서 양식 생성: {form}")
    return root


def _wage_lookup(case: Case):
    if case.wages:
        table = {tuple(int(x) for x in k.split("-")): v for k, v in case.wages.items()}
        last = table[max(table)]
        return (lambda p: table.get((p.year, p.index), last)), (lambda y, i: (y, i) in table)

    from engine.tables import WageTable

    wt = WageTable.load()
    matches = wt.find_occupation(case.occupation)
    if not matches:
        raise ValueError(
            f"직종 '{case.occupation}' 을 노임표에서 찾지 못했습니다. "
            f"입력서의 [노임단가 직접입력] 표에 단가를 넣거나 직종명을 확인하세요."
        )
    oid = matches[0]["id"]

    def wage_of(p):
        if case.rural:
            return wt.rural_wage(p.year, p.index, case.sex)
        return wt.occupation_wage(oid, p.year, p.index)

    def has_wage(y, i):
        try:
            wage_of(type("P", (), {"year": y, "index": i})())
            return True
        except KeyError:
            return False

    return wage_of, has_wage


def process(path: Path, root: Path) -> Path:
    """입력 파일 하나를 계산표로 바꾼다."""
    from cli import is_labor_yaml, run_labor

    if is_labor_yaml(path):
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return run_labor(path, root / "02_결과" / f"{path.stem}_노동금액계산표_{stamp}.xlsx")
    case = load(path) if path.suffix.lower() in (".yaml", ".yml") else read_form(path, strict=True)
    if not case.accident or not case.birth:
        raise ValueError("생년월일과 사고일자는 반드시 있어야 합니다.")

    wage_of, has_wage = _wage_lookup(case)
    result = calculate(case, wage_of, has_wage)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    label = f"{case.case_no or path.stem}({case.name})" if case.name else (case.case_no or path.stem)
    out = root / "02_결과" / f"{label}_계산표_{stamp}.xlsx"
    write_workbook(result, out)

    st = result.settlement
    print(f"  {label}")
    print(f"    사고당시연령  {result.age[0]}세 {result.age[1]}개월 {result.age[2]}일")
    if result.combined_rate:
        print(f"    중복장해율    {result.combined_rate}%  (기왕증 기여도 {result.prior_contribution}%)")
    print(f"    일실수입      {int(result.income_total):>15,} 원  ({len(result.income_rows)}개 순번)")
    if result.active_total:
        print(f"    적극손해      {int(result.active_total):>15,} 원")
    print(f"    재산상손해    {int(st['재산상손해_합계']):>15,} 원")
    print(f"    합계          {int(st['합계']):>15,} 원")
    print(f"    -> {out.name}")
    return out


def scan_once(root: Path) -> int:
    inbox = root / "01_입력"
    done = 0
    for path in sorted(inbox.iterdir()):
        if not path.is_file() or path.suffix.lower() not in SUFFIXES:
            continue
        if path.name.startswith("~$"):        # 엑셀 임시파일
            continue
        try:
            process(path, root)
            shutil.move(str(path), root / "03_보관" / path.name)
            done += 1
        except Exception as exc:
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            err = root / "99_오류" / f"{path.stem}_{stamp}.txt"
            err.write_text(
                f"파일: {path.name}\n시각: {datetime.now():%Y-%m-%d %H:%M:%S}\n\n"
                f"{exc}\n\n---\n{traceback.format_exc()}",
                encoding="utf-8",
            )
            shutil.move(str(path), root / "99_오류" / path.name)
            print(f"  [오류] {path.name}: {exc}")
            print(f"    -> {err.name}")
    return done


def main() -> None:
    ap = argparse.ArgumentParser(description="노동사건 손해배상 계산 자동화")
    ap.add_argument("--root", default=str(Path(__file__).resolve().parent), help="작업 폴더 (기본: 6_손해배상계산 폴더 자신)")
    ap.add_argument("--loop", action="store_true", help="계속 지켜보기")
    ap.add_argument("--interval", type=int, default=10, help="확인 간격(초), 기본 10")
    args = ap.parse_args()

    root = ensure_root(Path(args.root).expanduser().resolve())
    print(f"작업 폴더: {root}")
    print(f"입력 폴더: {root / '01_입력'}\n")

    if not args.loop:
        n = scan_once(root)
        print(f"\n{n}건 처리했습니다." if n else "\n처리할 파일이 없습니다.")
        return

    print("지켜보는 중입니다. Ctrl+C 로 종료합니다.\n")
    try:
        while True:
            scan_once(root)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\n종료합니다.")


if __name__ == "__main__":
    main()
