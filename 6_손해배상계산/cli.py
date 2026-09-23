#!/usr/bin/env python3
"""사건 YAML 을 읽어 손해배상액 계산표 엑셀을 만든다.

    python cli.py cases/sample.yaml -o out/계산표.xlsx

사건 파일은 저장소에 커밋하지 않는다(.gitignore 의 cases/).
신체손해 계산 흐름(run_injury)과 노임 조회기는 watch.py 도 이것을 쓴다.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path

from engine.calculate import calculate
from engine.case import Case, load
from engine.excel import write_workbook
from engine.inputform import REQUIRED_LABELS, WAGE_TABLE, parse_wage_key
from engine.wage_period import wage_key


class InputError(ValueError):
    """사건 파일·입력서 값 문제. cli 는 '입력 오류:' 로 끝내고, watch 는 99_오류 에 사유를 남긴다."""


def utf8_console() -> None:
    """출력을 UTF-8 로 맞춘다.

    Windows 파이썬은 출력이 콘솔이 아니라 파이프(Claude Code 가 명령을 돌리는 방식)이면
    cp949 로 쓰고, 요약의 '—' 같은 문자에서 UnicodeEncodeError 로 멈춘다.
    """
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


def _key_text(key, rural: bool) -> str:
    y, i = key
    return f"{y}년 {i}분기" if rural else f"{y}년 {'상' if i == 1 else '하'}반기"


def _next_key(key, rural: bool):
    y, i = key
    return (y, i + 1) if i < (4 if rural else 2) else (y + 1, 1)


def _wage_lookup(case: Case):
    """노임단가 조회기 (wage_of, has_wage, notes).

    사건 파일·입력서에 wages 가 있으면 그것을, 없으면 data/ 의 노임표를 쓴다.

    - 마지막 단가 뒤의 반기(분기)는 마지막으로 공표된(적은) 단가를 쓴다. 원본이 다음 단가가
      없으면 GetWage...Next(마지막 단가)로 종료일까지 잇는 것과 같다(engine/wage_period.py
      split_periods, engine/caregiving.py 머리말). 사고일·개호 시작일이 이미 표의 마지막 단가
      뒤이면 notes 에 그 사실을 적는다.
    - 마지막 단가보다 앞인데 빠진 반기(분기)는 추측하지 않고 InputError 로 멈춘다.
      직접입력에서 빠진 반기를 마지막 단가로 채우거나 앞 반기 단가를 끝까지 이으면
      중간에 적은 단가가 버려진다.
    """
    rural = case.rural
    notes: list[str] = []

    if case.wages:
        try:
            table = {parse_wage_key(k, rural): int(v) for k, v in case.wages.items()}
        except ValueError as exc:
            raise InputError(f"{WAGE_TABLE}: {exc}") from None
        keys = set(table)
        last = max(keys)
        fallback_note = (
            f"{WAGE_TABLE}에 {'-'.join(map(str, _next_key(last, rural)))}부터 단가가 없어 "
            f"마지막으로 적은 {last[0]}-{last[1]} 단가({table[last]:,}원)를 그 기간에 썼습니다."
        )

        def missing(key):
            start = min(key, wage_key(case.accident, rural))
            gaps, k = [], start
            while k <= last:
                if k not in keys:
                    gaps.append(f"{k[0]}-{k[1]}")
                k = _next_key(k, rural)
            acc = wage_key(case.accident, rural)
            unit = "분기" if rural else "반기"
            return InputError(
                f"{WAGE_TABLE}에 {', '.join(gaps)} 이(가) 없습니다. 사고일이 속한 {acc[0]}-{acc[1]}부터 "
                f"마지막으로 적은 {last[0]}-{last[1]}까지 {unit}마다 빠짐없이 적으십시오"
                f"(한 단가를 전 기간에 쓰려면 {acc[0]}-{acc[1]} 한 줄만 적습니다)."
            )

        def raw_wage(key):
            if key not in keys:
                raise missing(key)
            return table[key]

        def has_wage(y, i):
            if (y, i) in keys:
                return True
            if (y, i) > last:
                return False
            raise missing((y, i))
    else:
        from engine.tables import WageTable

        wt = WageTable.load()
        if rural:                                         # 농촌 일용노임은 직종과 무관하다
            what = "농촌 일용노임"
            basis = f"농촌 일용노임({'남' if case.sex == 'M' else '여'}, 분기)"
            keys = {(int(r["year"]), int(r["quarter"])) for r in wt.quarterly}
            newest = max(keys, default=None)

            def get(key):
                return wt.rural_wage(key[0], key[1], case.sex)
        else:
            from engine.tables import OccupationNotFound

            try:
                matches = wt.resolve_occupation(case.occupation)
            except OccupationNotFound as exc:
                raise InputError(f"{exc} (입력서는 [{WAGE_TABLE}] 표, 사건 파일은 wages)") from None
            oid = matches[0]["id"]
            what = f"직종 '{matches[0]['name']}' 노임"
            basis = wt.occupation_label(matches[0])
            keys = {(y, h) for (o, y, h) in wt.by_half if o == oid}
            newest = max(((y, h) for (_, y, h) in wt.by_half), default=None)

            def get(key):
                return wt.occupation_wage(oid, key[0], key[1])

        if not keys:
            raise InputError(f"{what} 단가가 노임표에 하나도 없습니다. [{WAGE_TABLE}] 표(사건 파일이면 wages)에 넣으십시오.")
        last = max(keys)
        fallback_note = (
            f"노임표에 {_key_text(_next_key(last, rural), rural)}부터 {what} 단가가 없어 "
            f"마지막 공표 단가({_key_text(last, rural)} {get(last):,}원)를 그 기간에 썼습니다. "
            + (f"이 직종은 {_key_text(last, rural)} 뒤로 공표되지 않았습니다(노임표 최신 {_key_text(newest, rural)}). "
               f"직종명이나 [{WAGE_TABLE}] 을 확인하십시오." if last < newest else
               "새 노임이 공표되면 노임표추출.bat 으로 표를 갱신한 뒤 다시 계산하십시오.")
        )

        def raw_wage(key):
            if key not in keys:
                raise InputError(
                    f"{what} {_key_text(key, rural)} 단가가 노임표에 없습니다. 노임표추출.bat 을 다시 돌리거나 "
                    f"[{WAGE_TABLE}] 표(사건 파일이면 wages)에 넣으십시오."
                )
            return get(key)

        def has_wage(y, i):
            return (y, i) in keys

    def wage_of(p):
        key = (p.year, p.index)
        if key > last:
            if fallback_note not in notes:
                notes.append(fallback_note)
            return raw_wage(last)
        return raw_wage(key)

    wage_of.basis = None if case.wages else basis         # 계산표 [일실수입] 옆에 적을 노임 기준
    return wage_of, has_wage, notes


def _caregiving_lookup(case: Case):
    """향후 개호비 단가 조회기 (calculate 에 넘길 인자, notes).

    caregiving_occupation(예: 보통인부)을 적으면 노임표에서 그 직종 노임을 개호 단가로 쓴다. 마지막 공표
    반기 뒤는 피해자 노임과 같이 마지막 단가를 쓰고 notes 에 적는다. caregiving_wages 표가 있으면 엔진이
    그 표를 쓰므로 넘기지 않는다. 둘 다 없으면 엔진이 이유를 적고 멈춘다(피해자 노임으로 대신하지 않는다).
    """
    if not (case.caregiving_start and case.caregiving_end) or case.caregiving_wages or not case.caregiving_occupation:
        return {}, []
    if case.caregiving_rural:
        raise InputError("농촌 노임(분기)을 개호 단가로 쓰려면 caregiving_wages 표에 적으십시오. "
                         "caregiving_occupation 은 직종별 노임(반기)만 찾습니다.")
    price_of, has, notes = _wage_lookup(replace(case, occupation=case.caregiving_occupation, wages={}, rural=False))
    kwargs = {"caregiving_price_of": price_of, "caregiving_has_wage": has,
              "caregiving_basis": f"노임표 직종 '{case.caregiving_occupation}' 노임"}
    return kwargs, notes


def load_injury(path) -> Case:
    """신체손해 사건 파일(YAML)을 읽는다. 생년월일·사고일자가 비어 있으면 멈춘다.

    Case 에는 기본값(생년월일 1990. 1. 1., 사고일자 2024. 1. 1.)이 있어 읽은 뒤에는 빈 값을
    알 수 없다. 그래서 입력서의 _check_required 처럼 파일에 실제로 적힌 값을 본다.
    """
    import yaml

    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise InputError("사건 파일은 '키: 값' 형식이어야 합니다. cases/sample.yaml 을 참조하십시오.")
    missing = [f"{label}({key})" for label, key in REQUIRED_LABELS if not raw.get(key)]
    if missing:
        raise InputError("사건 파일에 필수값이 비어 있습니다: " + ", ".join(missing))
    return load(path)


def run_injury(case: Case, out) -> Path:
    """신체손해 계산표를 만들고 요약을 출력한다."""
    wage_of, has_wage, notes = _wage_lookup(case)
    care, care_notes = _caregiving_lookup(case)
    result = calculate(case, wage_of, has_wage, wage_basis=wage_of.basis, **care)
    notes = notes + [f"개호 단가 — {n}" for n in care_notes] + list(result.warnings)
    out = write_workbook(result, out)

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
    auto = "" if case.injury_type == "사망" else f"  (자동계산 {int(result.solatium_auto):,})"
    print(f"위자료          {int(case.solatium):>15,} 원{auto}")
    print(f"합계            {int(st['합계']):>15,} 원")
    for n in notes:
        print(f"  확인: {n}")
    print(f"\n저장: {out}")
    return out


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
    utf8_console()
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

    try:
        case = load_injury(args.case)
        run_injury(case, Path(args.out or f"out/{case.case_no or 'case'}({case.name}).xlsx"))
    except InputError as exc:
        raise SystemExit(f"입력 오류: {exc}")


if __name__ == "__main__":
    main()
