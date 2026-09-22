#!/usr/bin/env python3
"""추출한 accdb CSV를 엔진이 쓰는 형태로 정규화한다.

입력 : tools/02_dump_accdb.ps1 (또는 노임표추출.ps1) 이 만든 TB_SUT001~004.csv
출력 : data/{life_table,wage_quarterly,occupation,wage_occupation}.csv

감사 컬럼(FRST_INPT_USER_ID, LAST_CHG_USER_ID, *_PGM_ID, *_DT)은 제거한다.
법원 담당자 ID와 내부 프로그램 ID가 들어 있어 저장소에 남기면 안 된다.
노임단가·생명표 수치 자체는 공공통계다.

사용:
    python scripts/normalize.py                          <- C:\\sut_extract\\db 아래에서 자동 탐색
    python scripts/normalize.py C:/sut_extract/db/CortCalc
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data"
NEED = ["TB_SUT001", "TB_SUT002", "TB_SUT003", "TB_SUT004"]
SEARCH_ROOTS = [Path(r"C:\sut_extract\db"), Path(r"D:\sut_extract\db"), ROOT / "sut_extract" / "db"]


def find_source() -> Path | None:
    for root in SEARCH_ROOTS:
        if not root.is_dir():
            continue
        for d in sorted(root.iterdir()):
            if d.is_dir() and all((d / f"{t}.csv").exists() for t in NEED):
                return d
    return None


def read(src: Path, name: str) -> list[dict[str, str]]:
    with (src / f"{name}.csv").open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def num(value) -> int | None:
    """빈 칸·NULL·공백이 섞여 있어도 죽지 않게 정수로 바꾼다."""
    if value is None:
        return None
    s = str(value).strip().replace(",", "")
    if not s or s.upper() in {"NULL", "NONE", "NAN"}:
        return None
    try:
        return int(float(s))
    except ValueError:
        return None


def build(table: str, src: Path, fields: list[str], mapper, key_fields: list[str]):
    """행을 만들고, 정렬키가 숫자가 아닌 행은 건너뛰며 몇 건인지 알린다."""
    good, bad = [], []
    for r in read(src, table):
        try:
            row = mapper(r)
        except KeyError as e:
            raise SystemExit(
                f"\n[중단] {table}.csv 에 {e} 컬럼이 없습니다.\n"
                f"       실제 컬럼: {', '.join(list(r.keys())[:12])} ...\n"
                f"       프로그램 버전이 달라 컬럼명이 바뀌었을 수 있습니다."
            )
        if all(num(row[k]) is not None for k in key_fields):
            good.append(row)
        else:
            bad.append(row)
    good.sort(key=lambda r: tuple(num(r[k]) for k in key_fields))
    return good, bad


def write(name: str, fields: list[str], rows: list[dict], skipped: list[dict]) -> None:
    OUT.mkdir(exist_ok=True)
    with (OUT / name).open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    note = f"  (값이 비어 건너뛴 행 {len(skipped)}건)" if skipped else ""
    print(f"  {name:<26} {len(rows):>7,}행{note}")


def main(src_dir: str | None) -> None:
    if src_dir:
        src = Path(src_dir)
        if not src.is_dir():
            raise SystemExit(f"[중단] 폴더가 없습니다: {src}")
    else:
        found = find_source()
        if not found:
            raise SystemExit(
                "[중단] TB_SUT001~004 가 모두 있는 폴더를 찾지 못했습니다.\n"
                "       노임표추출.bat 을 먼저 실행하거나, 폴더를 직접 지정하십시오:\n"
                "         python scripts\\normalize.py C:\\sut_extract\\db\\CortCalc"
            )
        src = found
    missing = [t for t in NEED if not (src / f"{t}.csv").exists()]
    if missing:
        raise SystemExit(f"[중단] {src} 에 없는 파일: {', '.join(m + '.csv' for m in missing)}")

    print(f"입력: {src}")

    rows, bad = build("TB_SUT002", src,
        ["year", "age", "male", "female"],
        lambda r: {"year": r["LFEXP_CRTR_YR"], "age": r["LFEXP_CRTR_AGE"],
                   "male": r["MLE_LFEXP_AGE"], "female": r["FMLE_LFEXP_AGE"]},
        ["year", "age"])
    write("life_table.csv", ["year", "age", "male", "female"], rows, bad)

    rows, bad = build("TB_SUT001", src,
        ["year", "quarter", "rural_male", "rural_female", "city_daily"],
        lambda r: {"year": r["LABR_WG_CRTR_YR"], "quarter": r["QRT_DVS_CD"],
                   "rural_male": r["RRL_MLE_WG_UPRC"], "rural_female": r["RRL_FMLE_WG_UPRC"],
                   "city_daily": r["CITY_DLYLBR_WG_UPRC"]},
        ["year", "quarter"])
    write("wage_quarterly.csv",
          ["year", "quarter", "rural_male", "rural_female", "city_daily"], rows, bad)

    rows, bad = build("TB_SUT003", src,
        ["id", "division", "name", "merged_name"],
        lambda r: {"id": r["OCPN_TBLT_SRNO"], "division": r["OCPN_DVS_NM"],
                   "name": r["OCPN_NM"], "merged_name": r["INTG_OCPN_NM"]},
        ["id"])
    write("occupation.csv", ["id", "division", "name", "merged_name"], rows, bad)

    rows, bad = build("TB_SUT004", src,
        ["occupation_id", "year", "half", "wage"],
        lambda r: {"occupation_id": r["OCPN_TBLT_SRNO"], "year": r["OCPN_UPRC_CRTR_YR"],
                   "half": r["HYR_DVS_CD"], "wage": r["OCPN_WG_UPRC"]},
        ["occupation_id", "year", "half", "wage"])
    write("wage_occupation.csv", ["occupation_id", "year", "half", "wage"], rows, bad)

    print("\n감사 컬럼(담당자 ID/프로그램 ID/변경일시)은 제거했습니다.")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
