#!/usr/bin/env python3
"""사건 YAML 을 읽어 손해배상액 계산표 엑셀을 만든다.

    python cli.py cases/sample.yaml -o out/계산표.xlsx

사건 파일은 저장소에 커밋하지 않는다(.gitignore 의 cases/).
"""

from __future__ import annotations

import argparse
from decimal import Decimal
from pathlib import Path

from engine.calculate import calculate
from engine.case import load
from engine.excel import write_workbook


def _wage_lookup(case):
    """노임단가 조회기. 사건 파일에 wages 가 있으면 그것을, 없으면 data/ 를 쓴다."""
    if case.wages:
        table = {tuple(int(x) for x in k.split("-")): v for k, v in case.wages.items()}
        last = table[max(table)]
        return (lambda p: table.get((p.year, p.index), last)), (lambda y, i: (y, i) in table)

    from engine.tables import WageTable

    wt = WageTable.load()
    matches = wt.find_occupation(case.occupation)
    if not matches:
        raise SystemExit(f"직종 '{case.occupation}' 을 찾지 못했습니다.")
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


def is_labor_yaml(path) -> bool:
    """사건 파일 맨 위 `kind: labor` 이면 노동 금액 사건."""
    import yaml

    p = Path(path)
    if p.suffix.lower() not in (".yaml", ".yml"):
        return False
    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return isinstance(raw, dict) and raw.get("kind") == "labor"


def run_labor(case_path, out=None) -> Path:
    from engine.labor.calculate import calculate_labor, load_labor_case, summary_lines
    from engine.labor.excel import write_labor_workbook

    case = load_labor_case(case_path)
    result = calculate_labor(case)
    out = Path(out or Path(case_path).with_name(f"{case.case_no or 'case'}({case.name})_노동금액계산표.xlsx"))
    write_labor_workbook(result, out)
    for line in summary_lines(result):
        print(line)
    for w in result.warnings:
        print(f"  확인: {w}")
    print(f"\n저장: {out}")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="손해배상액·노동 금액 계산표 생성")
    ap.add_argument("case", help="사건 YAML 경로")
    ap.add_argument("-o", "--out", default=None, help="출력 xlsx 경로")
    args = ap.parse_args()

    if is_labor_yaml(args.case):
        from engine.labor.common import LaborError

        try:
            run_labor(args.case, args.out)
        except LaborError as exc:
            raise SystemExit(f"입력 오류: {exc}")
        return

    case = load(args.case)
    wage_of, has_wage = _wage_lookup(case)
    result = calculate(case, wage_of, has_wage)

    out = Path(args.out or f"out/{case.case_no or 'case'}({case.name}).xlsx")
    write_workbook(result, out)

    st = result.settlement
    print(f"사건            {case.case_no} {case.name} / {case.case_type} / {case.injury_type}")
    print(f"사고당시연령    {result.age[0]}세 {result.age[1]}개월 {result.age[2]}일")
    if result.combined_rate:
        print(f"중복장해율      {result.combined_rate}%  (기왕증 기여도 {result.prior_contribution}%)")
    print(f"일실수입        {int(result.income_total):>15,} 원  ({len(result.income_rows)}개 순번)")
    if result.active_total:
        print(f"적극손해        {int(result.active_total):>15,} 원")
    print(f"재산적 손해     {int(result.property_damage):>15,} 원")
    print(f"과실비율액      {int(st['원고측_과실비율액']):>15,} 원  ({case.fault_rate}%)")
    print(f"공제액          {int(st['공제액_합계']):>15,} 원")
    print(f"재산상손해      {int(st['재산상손해_합계']):>15,} 원")
    print(f"위자료          {int(case.solatium):>15,} 원  (자동계산 {int(result.solatium_auto):,})")
    print(f"합계            {int(st['합계']):>15,} 원")
    print(f"\n저장: {out}")


if __name__ == "__main__":
    main()
