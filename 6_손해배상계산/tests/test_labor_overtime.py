"""연장·야간·휴일근로수당 재산정 차액 (engine/labor/overtime.py) 검증.

골든 예시는 조사 문서 overtime.md 3절과 검증 메모의 판결 원문 숫자다(G1~G3 서울중앙지방법원 2021. 9. 2.
선고 2020나38982, G4 대법원 2023. 12. 7. 선고 2020도15393). 판결문에 없는 사실(시각, 기산 요일, 지급일 등)을
테스트용으로 정한 경우 주석에 적었다. 금액 기대값은 판결 숫자이거나 assert 옆에 Decimal 식을 적은 값이다.
G5(창원 2014가합932)는 숫자가 없어 배수 구조 테스트로만, G6(의정부고양 2014가합53189)은 표기 516,517원과
식의 곱 516,516원이 달라 기대값으로 쓰지 않는다.
"""

import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.labor.common import LaborError, resolve_options  # noqa: E402
from engine.labor.overtime import (  # noqa: E402
    OPTIONS,
    RULES,
    calculate_overtime,
    load_overtime,
)

D = Decimal
W = D(8328)                               # 2020나38982 시간급 통상임금
WORKER = {"pay_day": 25}                  # 정기지급일은 판결에 없어 테스트용으로 정함


def run(raw, worker=WORKER, hourly=W, small=None, **opt):
    inp = load_overtime(raw, worker)
    opts, _ = resolve_options(opt, OPTIONS)
    deps = {}
    if hourly is not None:
        deps["hourly_of"] = hourly if callable(hourly) else (lambda d, v=D(hourly): v)
    if small is not None:
        deps["small_business"] = small if callable(small) else (lambda d, v=small: v)
    return calculate_overtime(inp, opts, **deps)


def lines(row, **match):
    return [ln for ln in row.lines if all(getattr(ln, k) == v for k, v in match.items())]


def amt(row, **match):
    return sum((ln.amount for ln in lines(row, **match)), D(0))


# ================================================================ 모듈 규약
def test_옵션_키_접두어와_기본값():
    assert all(k.startswith("ot_") for k in OPTIONS)
    values, _ = resolve_options({}, OPTIONS)
    assert values["ot_night_premium_under5"] is False           # OT-01 검증 교정
    assert values["ot_holiday_in_weekly_40"] == "unset"         # OT-05 기본값 삭제
    assert values["ot_weekly_allocation"] == "unset"
    assert values["ot_pre2018_holiday_over8_add_ot"] is True    # OT-10 교정
    assert values["ot_part_time_premium"] == "off"              # OT-08 확인불가
    assert values["ot_overpayment_character"] == "unset"        # OT-18 불명확
    assert values["ot_compare_unit"] == "unset"
    assert values["ot_claim_basis"] == "legal"
    assert values["ot_amount_rounding"] == "floor"
    assert values["ot_hours_rounding"] == "none"


def test_규칙_상태_어휘():
    allowed = {"판례확립", "법령", "행정해석", "하급심", "실무관행", "불명확"}
    for rid, (summary, status) in RULES.items():
        assert summary
        assert set(status.split("·")) <= allowed, rid
    assert RULES["OT-10"][1] == "판례확립·실무관행"
    assert RULES["OT-18"][1] == "불명확"
    assert all(f"OT-{i:02d}" in RULES for i in range(1, 23))
    assert all(f"M{i}" in RULES for i in range(1, 12))


# ================================================================ 골든 G1·G2 서울중앙 2020나38982
# 시각은 판결에 없음: G1 은 12시간 중 휴게 1시간이라 09:00~21:00(야간 없음)으로 정함. 두 날 모두 비번일(소정 0시간).
G1 = {"date": "2018-02-17", "start": "09:00", "end": "21:00", "break_minutes": 60, "scheduled_hours": 0}
G2 = {"date": "2018-02-19", "start": "20:00", "end": "08:00", "scheduled_hours": 0}


def test_G1_비휴일_추가근로_104100원():
    res = run({"week_start": "monday", "days": [G1]})
    [row] = res.rows
    assert amt(row, kind="base") == D(91608)                       # "기본임금 91,608원{= 11시간 … × 8,328원}"
    assert amt(row, category="overtime", kind="premium") == D(12492)  # "3시간 × 8,328원 × 50/100"
    assert row.legal_amount == D(104100)                           # 판결 원문
    assert row.overtime_hours == 3 and row.in_law_hours == 8


def test_G2_야간근무_연장_야간_중복_149904원():
    res = run({"week_start": "monday", "days": [G2]})
    [row] = res.rows
    assert amt(row, kind="base") == D(99936)                        # "8,328원 × 12시간"
    assert amt(row, category="overtime", kind="premium") == D(16656)  # "8,328원 × 4시간 × 50/100"
    assert amt(row, category="night") == D(33312)                   # "8,328원 × 8시간 × 50/100"
    assert row.legal_amount == D(149904)                            # 판결 원문
    assert row.night_hours == 8 and row.overtime_night_hours == 2   # 04:00~06:00 연장·야간 중복(표시)
    assert row.period_start == date(2018, 2, 1)                     # 시업일(2. 19.) 귀속(OT-13)


def test_G1_G2_합산_기지급_256020원이면_차액_없음():
    # 기지급 210,840원 + 시정명령 지급 45,180원. 명목 구분이 판결에 없어 정액(lump)으로 넣음.
    res = run({"week_start": "monday", "days": [G1, G2],
               "paid": [{"period": "2018-02", "lump": D(210840) + D(45180)}]})
    [row] = res.rows
    assert row.legal_amount == D(254004)                            # 판결 원문 합계
    assert row.diff == D(254004) - D(256020)
    assert res.total == 0 and res.claims == [] and res.extra_wages == {}


def test_G1_combined_구조도_합계_같음():
    res = run({"week_start": "monday", "days": [G1]}, ot_multiplier_structure="combined")
    [row] = res.rows
    assert row.legal_amount == D(104100)
    assert {(ln.category, ln.multiplier) for ln in row.lines} == {("in_law", D(1)), ("overtime", D("1.5"))}


# ================================================================ 골든 G3 근로자의 날 2018. 5. 1.
G3 = {"date": "2018-05-01", "start": "20:00", "end": "08:00", "holiday": True, "holiday_kind": "labor_day",
      "base_paid": True, "night_proven": False}   # 판결은 야간 가산을 따로 산정하지 않음 → 야간 미증명으로 둠


def test_G3_휴일_8시간_초과_가산분만_차액_2494원():
    res = run({"week_start": "monday", "days": [G3], "paid": [{"period": "2018-05", "holiday": 64130}]})
    [row] = res.rows
    assert amt(row, category="holiday_le8") == D(33312)             # "8시간 × 8,328원 × 50/100"
    assert amt(row, category="holiday_gt8") == D(33312)             # "4시간 × 8,328원 × 1"
    assert row.legal_amount == D(66624)                             # 판결 원문
    assert res.total == D(2494)                                     # "그 차액인 2,494원(= 66,624원 – 64,130원)"
    assert not lines(row, kind="base")                              # 기본분 별도 지급(가산분만)
    assert row.unproven_hours == 8
    [claim] = res.claims
    assert claim.due_date == date(2018, 5, 25) and claim.amount == D(2494)
    assert res.extra_wages == {"2018-05": D(2494)}


def test_G3_야간을_증명하면_33312원_추가():
    g3 = dict(G3, night_proven=True)
    res = run({"week_start": "monday", "days": [g3]})
    assert res.rows[0].legal_amount == D(66624) + W * 8 * D("0.5")


def test_G3_휴일_경계_calendar_day_옵션():
    # 5. 2. 00:00~08:00 을 평일 근로로 나눔: 휴일 4시간(가산 0.5), 평일 4시간(소정 8시간 이내·기본분 지급)
    res = run({"week_start": "monday", "days": [G3]}, ot_holiday_boundary="calendar_day")
    row = res.rows[0]
    assert row.holiday_le8_hours == 4 and row.holiday_gt8_hours == 0
    assert row.legal_amount == W * 4 * D("0.5")
    assert any("OT-13" in w for w in res.warnings)


# ================================================================ 골든 G4 대법원 2020도15393 — 한도 판정
G4_DAYS = [{"date": "2014-04-15", "hours": 12}, {"date": "2014-04-16", "hours": "11.5"},
           {"date": "2014-04-17", "hours": "14.5"}, {"date": "2014-04-20", "hours": "11.5"}]


def test_G4_1주_한도_9시간30분과_가산시간_17시간30분():
    res = run({"week_start": "monday", "days": G4_DAYS}, hourly=10000)
    [wk] = res.weeks
    assert wk.week_start == date(2014, 4, 14)
    assert wk.limit_basis_hours == D("49.5")          # "49시간 30분"
    assert wk.limit_overtime_hours == D("9.5")        # "총 연장근로시간은 9시간 30분"
    assert not wk.violation
    assert wk.premium_overtime_hours == D("17.5")     # OT-05 가산 대상(판결 계산값 아님): 4+3.5+6.5+3.5
    assert not wk.holiday_included


def test_G4_연장_휴게_자동공제_48시간30분():
    res = run({"week_start": "monday", "days": G4_DAYS}, hourly=10000, ot_assume_ot_break=True)
    [wk] = res.weeks
    assert wk.limit_basis_hours == D("48.5")          # "1주간의 총 실근로시간은 48시간 30분"
    assert wk.limit_overtime_hours == D("8.5")        # "총 연장근로시간은 8시간 30분"


def test_한도_초과_경고():
    days = [{"date": f"2019-03-{d:02d}", "hours": 11} for d in range(4, 9)]   # 월~금 11시간 → 55 − 40 = 15
    res = run({"week_start": "monday", "size_band": "300+", "days": days}, hourly=10000)
    assert res.weeks[0].violation and res.weeks[0].limit_overtime_hours == 15
    assert any("한도" in w for w in res.warnings)
    assert res.rows[0].overtime_hours == 15            # 가산액은 한도와 무관


# ================================================================ G5 배수 구조(창원 2014가합932 → 항소심 2017나24321)
def test_G5_야간_가산분만_50퍼센트():
    res = run({"week_start": "monday", "days": [{"date": "2019-03-04", "start": "22:00", "end": "06:00",
                                                 "breaks": [{"start": "02:00", "end": "03:00"}]}]}, hourly=10000)
    row = res.rows[0]
    assert row.night_hours == 7 and row.overtime_hours == 0 and row.in_law_hours == 0
    assert row.legal_amount == D(10000) * 7 * D("0.5")   # (시급 × 야간시간 × 150%) − (× 100%)


# ================================================================ OT-03 개정일 경계
def _holiday10(d):
    return {"week_start": "monday", "days": [{"date": d, "start": "08:00", "end": "18:00", "holiday": True,
                                              "holiday_kind": "weekly"}]}


def test_2018_3_19_구법_휴일_10시간():
    res = run(_holiday10("2018-03-18"), hourly=10000)          # 일요일
    row = res.rows[0]
    assert amt(row, kind="base") == D(10000) * 10
    assert amt(row, category="holiday_le8") == D(10000) * 8 * D("0.5")
    assert amt(row, category="holiday_gt8") == D(10000) * 2 * D("0.5")
    assert amt(row, category="holiday_gt8_ot") == D(10000) * 2 * D("0.5")    # OT-10 옵션 기본 true
    res2 = run(_holiday10("2018-03-18"), hourly=10000, ot_pre2018_holiday_over8_add_ot=False)
    assert res2.rows[0].legal_amount == D(10000) * (10 + D(10) * D("0.5"))


def test_2018_3_19_과_20_경계():
    old = run({"week_start": "monday", "days": [{"date": "2018-03-19", "start": "08:00", "end": "18:00",
                                                 "holiday": True, "holiday_kind": "agreed"}]}, hourly=10000)
    new = run({"week_start": "monday", "days": [{"date": "2018-03-20", "start": "08:00", "end": "18:00",
                                                 "holiday": True, "holiday_kind": "agreed"}]}, hourly=10000)
    assert old.rows[0].legal_amount == D(10000) * (10 + 10 * D("0.5") + 2 * D("0.5"))
    assert new.rows[0].legal_amount == D(10000) * (10 + 8 * D("0.5") + 2 * D(1))
    assert not lines(new.rows[0], category="holiday_gt8_ot")


def test_야간근무가_자정을_넘어도_시업일_기준():
    # 2018. 3. 19. 22:00 시작 → 구법 기간 근로(OT-03 근로일 = 시업일)
    res = run({"week_start": "monday", "days": [{"date": "2018-03-19", "start": "22:00", "end": "08:00",
                                                 "holiday": True, "holiday_kind": "agreed"}]}, hourly=10000)
    row = res.rows[0]
    assert lines(row, category="holiday_gt8_ot")
    assert amt(row, category="holiday_gt8") == D(10000) * 2 * D("0.5")


# ================================================================ OT-01 5인 미만
def test_5인_미만은_가산_0_야간_옵션():
    raw = {"week_start": "monday", "days": [dict(G2, date="2019-03-04")]}
    res = run(raw, hourly=10000, small=True)
    row = res.rows[0]
    assert row.legal_amount == D(10000) * 12                   # 기본분만
    assert any("OT-01" in w for w in res.warnings)
    res2 = run(raw, hourly=10000, small=True, ot_night_premium_under5=True)
    assert res2.rows[0].legal_amount == D(10000) * 12 + D(10000) * 8 * D("0.5")


def test_상시근로자수_입력이_deps_보다_우선():
    raw = {"week_start": "monday", "headcount": [{"from": "2019-01-01", "to": "2019-12-31",
                                                  "person_days": 88, "operating_days": 22}],   # 88 ÷ 22 = 4명
           "days": [{"date": "2019-03-04", "hours": 10}]}
    res = run(raw, hourly=10000, small=False)
    assert res.rows[0].overtime_hours == 2
    assert res.rows[0].legal_amount == D(10000) * 2      # 초과 2시간 기본분 100%만, 가산 0(4명 이하)
    big = run(dict(raw, headcount=[]), hourly=10000, small=False)
    assert big.rows[0].legal_amount == D(10000) * 2 * D("1.5")


# ================================================================ OT-07 법내 초과, OT-08 단시간
def test_법내_초과근로는_기본분만():
    # 1일 소정 6시간·1주 30시간, 월요일 9시간 근로: 법내 2시간(100%) + 연장 1시간(150%)
    raw = {"week_start": "monday", "scheduled_daily_hours": 6, "scheduled_weekly_hours": 30,
           "days": [{"date": "2019-03-04", "hours": 9}]}
    res = run(raw, hourly=10000)
    row = res.rows[0]
    assert row.in_law_hours == 2 and row.overtime_hours == 1
    assert row.legal_amount == D(10000) * (2 + 1 + 1 * D("0.5"))


def test_단시간_가산_옵션():
    raw = {"week_start": "monday", "part_time": True, "scheduled_daily_hours": 4, "scheduled_weekly_hours": 20,
           "days": [{"date": "2019-03-04", "hours": 6}]}
    off = run(raw, hourly=10000)
    on = run(raw, hourly=10000, ot_part_time_premium="daily")
    assert off.rows[0].legal_amount == D(10000) * 2
    assert on.rows[0].legal_amount == D(10000) * 2 * D("1.5")
    assert any("OT-08" in w for w in off.warnings)


def test_단시간_가산_시행일_전은_0():
    raw = {"week_start": "monday", "part_time": True, "scheduled_daily_hours": 4, "scheduled_weekly_hours": 20,
           "days": [{"date": "2014-09-18", "hours": 6}]}
    assert run(raw, hourly=10000, ot_part_time_premium="daily").rows[0].legal_amount == D(10000) * 2


# ================================================================ OT-05 1일·1주 중복 제거
def test_1일_1주_중복_제거():
    # 월~금 10시간 + 토 8시간: 일 초과 10 + 주 (40 + 8 − 40) = 18 (단순 합산 10 + 18 = 28 아님)
    days = [{"date": f"2019-03-{d:02d}", "hours": 10} for d in range(4, 9)] + [{"date": "2019-03-09", "hours": 8}]
    res = run({"week_start": "monday", "days": days}, hourly=10000)
    row = res.rows[0]
    assert row.overtime_hours == 18
    assert row.legal_amount == D(10000) * 18 * D("1.5")


def test_주_초과분_배정_옵션은_결과가_달라질_때만_요구():
    # 주가 2019. 3. 25.(월)~31.(일)이고 임금산정기간이 21일 시작이면 같은 기간 → 선택 없이 계산
    days = [{"date": f"2019-03-{d:02d}", "hours": 8} for d in range(25, 31)]    # 48시간 → 주 초과 8
    res = run({"week_start": "monday", "days": days}, worker={"pay_day": 25, "pay_period_start_day": 21}, hourly=10000)
    assert res.rows[0].overtime_hours == 8
    # 달력 월이면 3월(25~31)과 4월로 나뉘지 않음(모두 3월) — 시급이 4월 1일에 바뀌는 주로 바꿔 차이를 만든다
    days2 = [{"date": f"2019-03-{d:02d}", "hours": 8} for d in (27, 28, 29, 30, 31)] + [{"date": "2019-04-01", "hours": 8}]
    raw2 = {"week_start": "wednesday", "days": days2}
    with pytest.raises(LaborError, match="ot_weekly_allocation"):
        run(raw2, hourly=10000)
    last = run(raw2, hourly=10000, ot_weekly_allocation="last_days_first")
    chrono = run(raw2, hourly=10000, ot_weekly_allocation="chronological")
    assert [r.overtime_hours for r in last.rows] == [0, 8]
    assert [r.overtime_hours for r in chrono.rows] == [8, 0]


def test_휴일_주40시간_합산_선택_강제():
    # 1주 정의 시행(300+ 2018. 7. 1.) 후: 월~금 8시간 + 일요일(주휴) 8시간
    days = [{"date": f"2019-03-{d:02d}", "hours": 8} for d in range(4, 9)]
    days.append({"date": "2019-03-10", "hours": 8, "holiday": True, "holiday_kind": "weekly"})
    raw = {"week_start": "monday", "size_band": "300+", "days": days}
    with pytest.raises(LaborError, match="ot_holiday_in_weekly_40"):
        run(raw, hourly=10000)
    ex = run(raw, hourly=10000, ot_holiday_in_weekly_40="exclude")
    inc = run(raw, hourly=10000, ot_holiday_in_weekly_40="include", ot_weekly_allocation="last_days_first")
    assert ex.rows[0].legal_amount == D(10000) * 8 * D("1.5")
    assert inc.rows[0].legal_amount == D(10000) * 8 * D("1.5") + D(10000) * 8 * D("1.5")
    assert inc.weeks[0].holiday_included and inc.weeks[0].limit_basis_hours == 48


def test_구_1주_정의_기간은_휴일_합산_선택_불필요():
    days = [{"date": f"2019-03-{d:02d}", "hours": 8} for d in range(4, 9)]
    days.append({"date": "2019-03-10", "hours": 8, "holiday": True, "holiday_kind": "weekly"})
    res = run({"week_start": "monday", "size_band": "5-29", "days": days}, hourly=10000)   # 5-29 는 2021. 7. 1. 시행
    assert res.rows[0].overtime_hours == 0 and res.weeks[0].limit_basis_hours == 40


# ================================================================ OT-11 휴일 판정
def test_공휴일_규모별_시행_전은_휴일_아님():
    rec = {"date": "2021-03-01", "hours": 8, "holiday": True, "holiday_kind": "public"}
    before = run({"week_start": "monday", "size_band": "5-29", "days": [rec]}, hourly=10000)
    after = run({"week_start": "monday", "size_band": "30-49", "days": [rec]}, hourly=10000,
                ot_holiday_in_weekly_40="exclude")
    assert before.rows[0].holiday_le8_hours == 0
    assert after.rows[0].legal_amount == D(10000) * 8 * D("1.5")


def test_휴일대체_요건():
    base = {"date": "2019-03-10", "hours": 8, "holiday": True, "holiday_kind": "weekly"}
    ok = dict(base, substitution={"basis": True, "notice_at": "2019-03-08 18:00"})
    late = dict(base, substitution={"basis": True, "notice_at": "2019-03-09 12:00"})
    r_ok = run({"week_start": "monday", "size_band": "5-29", "days": [ok]}, hourly=10000)
    r_late = run({"week_start": "monday", "size_band": "5-29", "days": [late]}, hourly=10000)
    r_late2 = run({"week_start": "monday", "size_band": "5-29", "days": [late]}, hourly=10000,
                  ot_substitution_notice_24h=False)
    assert r_ok.rows[0].holiday_le8_hours == 0
    assert r_late.rows[0].holiday_le8_hours == 8 and any("24시간" in w for w in r_late.warnings)
    assert r_late2.rows[0].holiday_le8_hours == 0
    pub = {"date": "2022-03-01", "hours": 8, "holiday": True, "holiday_kind": "public",
           "substitution": {"basis": True, "notice_at": "2022-02-20 09:00"}}   # 서면합의 없음
    r_pub = run({"week_start": "monday", "size_band": "5-29", "days": [pub]}, hourly=10000,
                ot_holiday_in_weekly_40="exclude")
    assert r_pub.rows[0].holiday_le8_hours == 8 and any("서면합의" in w for w in r_pub.warnings)


# ================================================================ OT-02 적용제외
def test_제63조_적용제외_야간만_가산():
    raw = {"week_start": "monday", "exempt_63": [{"from": "2019-01-01", "category": 3, "approved_on": "2019-03-01"}],
           "days": [dict(G2, date="2019-03-04")]}
    res = run(raw, hourly=10000)
    assert res.rows[0].legal_amount == D(10000) * 12 + D(10000) * 8 * D("0.5")
    before = run(dict(raw, days=[dict(G2, date="2019-02-25")]), hourly=10000)   # 승인 전
    assert before.rows[0].legal_amount == D(10000) * 12 + D(10000) * 4 * D("0.5") + D(10000) * 8 * D("0.5")


# ================================================================ OT-14 휴게
def test_자유이용_미보장_휴게는_공제하지_않음():
    rec = {"date": "2019-03-04", "start": "09:00", "end": "19:00",
           "breaks": [{"start": "12:00", "end": "13:00", "free": False}]}
    res = run({"week_start": "monday", "days": [rec]}, hourly=10000)
    assert res.rows[0].overtime_hours == 2
    assert any("M8" in w for w in res.warnings)


# ================================================================ 집계 방식(a)
def test_월별_집계_입력():
    raw = {"months": [{"period": "2019-03", "overtime_hours": 20, "night_hours": 10, "holiday_le8_hours": 8,
                       "holiday_gt8_hours": 2, "paid": {"overtime": 250000, "night": 40000, "holiday": 100000}}]}
    res = run(raw, hourly=10000)
    row = res.rows[0]
    legal = D(10000) * (20 * D("1.5") + 10 * D("0.5") + 8 * D("1.5") + 2 * D(2))
    assert row.legal_amount == legal
    assert res.total == legal - D(390000)
    assert res.claims[0].due_date == date(2019, 3, 25)


def test_집계_기간_중_시급_바뀌면_나눠_입력():
    raw = {"months": [{"period": "2018-03", "overtime_hours": 10}]}
    with pytest.raises(LaborError, match="나눠"):
        run(raw, hourly=lambda d: D(9000) if d.day < 20 else D(9500))
    ok = run({"months": [{"period": "2018-03", "to": "2018-03-19", "holiday_le8_hours": 8, "holiday_gt8_hours": 2},
                         {"period": "2018-03", "from": "2018-03-20", "holiday_le8_hours": 8, "holiday_gt8_hours": 2}]},
             hourly=10000)
    assert ok.rows[0].legal_amount == D(10000) * ((8 + 2) * D("1.5") + 2 * D("0.5")) + D(10000) * (8 * D("1.5") + 2 * D(2))


def test_집계_가산율_시행일은_영향받는_시간이_있을_때만_나눔():
    # 2018. 3. 20. 개정은 휴일 8시간 초과분만, 2014. 9. 19. 단시간 가산은 옵션을 켠 단시간근로자의 소정 초과분만 바꾼다
    for per in ("2018-03", "2014-09"):
        res = run({"months": [{"period": per, "overtime_hours": 10}]}, hourly=10000)
        assert res.total == D(10000) * 10 * D("1.5")
    with pytest.raises(LaborError, match="가산율 체계"):
        run({"months": [{"period": "2018-03", "holiday_le8_hours": 8, "holiday_gt8_hours": 2}]}, hourly=10000)
    pt = {"part_time": True, "scheduled_daily_hours": 4, "scheduled_weekly_hours": 20,
          "months": [{"period": "2014-09", "in_law_hours": 2}]}
    assert run(pt, hourly=10000).total == D(10000) * 2                     # 옵션 off: 기본분만, 나눌 필요 없음
    with pytest.raises(LaborError, match="단시간 가산 시행"):
        run(pt, hourly=10000, ot_part_time_premium="daily")


def test_지급월_오프셋():
    res = run({"months": [{"period": "2019-03", "overtime_hours": 1}]}, worker={"pay_day": 10, "pay_month_offset": 1},
              hourly=10000)
    assert res.claims[0].due_date == date(2019, 4, 10)


def test_지급일_설정을_빈칸으로_두면_worker_값():
    # docstring '비우면 worker 값' — YAML 에서 키만 적고 값을 비우면 None 으로 읽힌다
    raw = yaml.safe_load("pay_day:\npay_month_offset:\npay_period_start_day:\n"
                         "months:\n  - {period: \"2024-03\", overtime_hours: 10}\n")
    worker = {"pay_day": 10, "pay_month_offset": 1, "pay_period_start_day": 21}
    inp = load_overtime(raw, worker)
    assert (inp.pay_day, inp.pay_month_offset, inp.pay_period_start_day) == (10, 1, 21)
    [row] = run(raw, worker=worker, hourly=10000).rows
    assert (row.period_start, row.period_end, row.due_date) == (date(2024, 3, 21), date(2024, 4, 20), date(2024, 5, 10))
    explicit = load_overtime({"pay_month_offset": 0, "pay_period_start_day": 1}, worker)   # 명시한 값은 그대로
    assert (explicit.pay_day, explicit.pay_month_offset, explicit.pay_period_start_day) == (10, 0, 1)


# ================================================================ OT-16·17
def test_간주합의_시간_하한():
    raw = {"agreed_hours": [{"from": "2019-01-01", "to": "2019-12-31", "overtime": 20}],
           "months": [{"period": "2019-03", "overtime_hours": 12}]}
    res = run(raw, hourly=10000)
    assert res.rows[0].overtime_hours == 20
    assert res.rows[0].legal_amount == D(10000) * 20 * D("1.5")
    no = run({"months": [{"period": "2019-03", "overtime_hours": 12}]}, hourly=10000)
    assert no.rows[0].legal_amount == D(10000) * 12 * D("1.5")


def test_미증명_시간은_제외():
    res = run({"months": [{"period": "2019-03", "overtime_hours": 12, "proven": False}]}, hourly=10000)
    assert res.rows[0].legal_amount == 0 and res.rows[0].unproven_hours == 12
    assert any("2022다291153" in w for w in res.warnings)


def test_유효한_포괄임금이면_차액_0():
    raw = {"inclusive_wage": "valid_hard_to_measure",
           "months": [{"period": "2019-03", "overtime_hours": 50, "paid": {"lump": 100000}}]}
    res = run(raw, hourly=10000)
    assert res.rows[0].legal_amount == D(10000) * 50 * D("1.5")
    assert res.total == 0 and not res.claims


def test_포괄임금_불성립_정액_공제():
    raw = {"inclusive_wage": "not_formed",
           "months": [{"period": "2019-03", "overtime_hours": 50, "paid": {"lump": 600000}}]}
    assert run(raw, hourly=10000).total == D(10000) * 50 * D("1.5") - D(600000)


# ================================================================ OT-15 약정 전체 비교
AGREED = {"valid": True, "hourly": [{"from": "2019-01-01", "amount": 9000}],
          "rates": {"overtime": 1.0, "night": 0.5, "holiday_le8": 0.5, "holiday_gt8": 1.0}}


def test_약정_전체와_법정_전체_비교():
    raw = {"agreed": AGREED, "months": [{"period": "2019-03", "overtime_hours": 10}]}
    legal = run(raw, hourly=10000)
    assert legal.basis == "legal" and legal.total == D(10000) * 10 * D("1.5")
    assert legal.contract_total == D(9000) * 10 * 2
    greater = run(raw, hourly=10000, ot_claim_basis="greater")
    assert greater.basis == "contract" and greater.total == D(9000) * 10 * 2
    # 취사선택(법정 시급 10,000원 × 약정 배수 2.0 = 200,000원)은 어떤 옵션으로도 나오지 않는다
    assert D(10000) * 10 * 2 not in {legal.total, greater.total}


def test_약정_무효면_약정_기준_불가():
    raw = {"agreed": dict(AGREED, valid=False), "months": [{"period": "2019-03", "overtime_hours": 10}]}
    with pytest.raises(LaborError, match="97다14200"):
        run(raw, hourly=10000, ot_claim_basis="contract")
    res = run(raw, hourly=10000, ot_claim_basis="greater")
    assert res.basis == "legal"


# ================================================================ OT-18 비교 단위·충당
def _two_months(paid3, paid4):
    return {"compare_units": [["2019-03-01", "2019-04-30"]],
            "months": [{"period": "2019-03", "overtime_hours": 10, "night_hours": 10, "paid": paid3},
                       {"period": "2019-04", "overtime_hours": 10, "paid": paid4}]}


def test_초과지급_없으면_선택_불필요():
    res = run(_two_months({"overtime": 0}, {"overtime": 0}), hourly=10000)
    assert res.total == D(10000) * (10 * D("1.5") + 10 * D("0.5") + 10 * D("1.5"))


def test_비교_단위_옵션별_차이():
    # 3월: 연장 150,000원 대비 200,000원 지급(50,000 초과), 야간 50,000원 미지급. 4월: 연장 150,000원 미지급.
    raw = _two_months({"overtime": 200000}, {"overtime": 0})
    with pytest.raises(LaborError, match="ot_overpayment_character"):
        run(raw, hourly=10000)
    err = run(raw, hourly=10000, ot_overpayment_character="erroneous")
    assert err.total == D(150000) + D(50000) + D(150000) - D(200000)        # 다른 항목·다른 달 충당
    assert [r.claim_amount for r in err.rows] == [D(0), D(150000)]          # 3월 순액 0, 4월 그대로
    with pytest.raises(LaborError, match="ot_compare_unit"):
        run(raw, hourly=10000, ot_overpayment_character="contractual")
    month = run(raw, hourly=10000, ot_overpayment_character="contractual", ot_compare_unit="month")
    whole = run(raw, hourly=10000, ot_overpayment_character="contractual", ot_compare_unit="whole_period")
    unit = run(raw, hourly=10000, ot_overpayment_character="contractual", ot_compare_unit="pay_unit")
    assert month.total == D(50000) + D(150000)                                # 다른 항목 공제 불허
    assert whole.total == D(50000) + (D(150000) - D(50000))                   # 같은 항목(연장) 안에서만 충당
    assert [r.claim_amount for r in whole.rows] == [D(50000), D(100000)]
    assert unit.total == whole.total
    assert month.alternatives == {"erroneous": D(150000), "contractual/month": D(200000),
                                  "contractual/pay_unit": D(150000), "contractual/whole_period": D(150000)}


def test_pay_unit_인데_단위기간_없음():
    raw = {"months": [{"period": "2019-03", "overtime_hours": 1}]}
    with pytest.raises(LaborError, match="compare_units"):
        run(raw, hourly=10000, ot_compare_unit="pay_unit")


# ================================================================ OT-21 끝수
def test_끝수_옵션_원고_계산_방식():
    # 2020나38982 원고 주장: 8,328.6원 × 12시간 × 1.5배, 일의 자리에서 올림(법원 판단 아님)
    raw = {"months": [{"period": "2018-02", "overtime_hours": 12}]}
    ceil10 = run(raw, hourly=D("8328.6"), ot_multiplier_structure="combined", ot_amount_rounding="ceil10")
    assert ceil10.total == ((D("8328.6") * 12 * D("1.5")) / 10).to_integral_value(rounding="ROUND_CEILING") * 10
    floor_h = run(raw, hourly=D("8328.6"), ot_hourly_rounding="floor")
    assert floor_h.total == D(8328) * 12 * D("1.5")                         # 법원: 원 미만 없는 8,328원 사용
    plain = run(raw, hourly=D("8328.6"))
    # split: 기본분 8,328.6 × 12 = 99,943.2 → 99,943, 가산 8,328.6 × 12 × 0.5 = 49,971.6 → 49,971
    assert plain.total == D(99943) + D(49971)
    item = run(raw, hourly=D("8328.6"), ot_rounding_stage="item")
    assert item.total == (D("8328.6") * 12 * D("1.5")).to_integral_value(rounding="ROUND_DOWN")   # 149,914.8 → 149,914


def test_시간_끝수_옵션():
    raw = {"months": [{"period": "2019-03", "overtime_hours": "23.7808"}]}
    res = run(raw, hourly=10000, ot_hours_rounding="floor_2dp", ot_multiplier_structure="combined")
    assert res.rows[0].lines[0].hours == D("23.78")
    assert res.total == D("23.78") * 10000 * D("1.5")


# ================================================================ 연소자·청구기간·경고
def test_연소근로자_7시간_기준():
    res = run({"week_start": "monday", "minor": True, "days": [{"date": "2019-03-04", "hours": 8}]}, hourly=10000)
    assert res.rows[0].overtime_hours == 1


def test_청구기간_밖_기록은_주_판정에만():
    days = [{"date": f"2019-03-{d:02d}", "hours": 8} for d in range(25, 30)] + [{"date": "2019-03-30", "hours": 8}]
    res = run({"week_start": "monday", "claim_from": "2019-03-30", "days": days}, hourly=10000,
              ot_weekly_allocation="last_days_first")
    [row] = res.rows
    assert row.overtime_hours == 8                  # 토요일 8시간이 주 40시간 초과분


def test_집계_입력도_청구기간으로_거른다():
    raw = {"claim_from": "2019-03-01", "claim_to": "2019-03-31",
           "months": [{"period": p, "overtime_hours": 10} for p in ("2019-01", "2019-03", "2019-06")]}
    res = run(raw, hourly=10000)
    assert [r.key for r in res.rows] == ["2019-03"]
    assert res.total == D(10000) * 10 * D("1.5")                 # 일별 기록으로 넣은 것과 같이 3월분만
    assert any("청구기간" in w and "2019-01, 2019-06" in w for w in res.warnings)


def test_청구기간_경계에_걸친_집계_줄은_나눠_적어야():
    raw = {"claim_from": "2019-03-15", "months": [{"period": "2019-03", "overtime_hours": 10}]}
    with pytest.raises(LaborError, match="청구기간"):
        run(raw, hourly=10000)
    split = {"claim_from": "2019-03-15",
             "months": [{"period": "2019-03", "to": "2019-03-14", "overtime_hours": 4},
                        {"period": "2019-03", "from": "2019-03-15", "overtime_hours": 6}]}
    res = run(split, hourly=10000)
    assert res.total == D(10000) * 6 * D("1.5")
    assert any("2019-03(2019. 3. 1.~2019. 3. 14.)" in w for w in res.warnings)


def _paid_outside_claim():
    # 2월·3월 모두 월~금 10시간(1일 초과 2시간 × 5일), 청구는 3월부터. 2월 기지급액은 2월 재산정분과 같다
    days = [{"date": f"2019-02-{d:02d}", "hours": 10} for d in range(4, 9)]
    days += [{"date": f"2019-03-{d:02d}", "hours": 10} for d in range(4, 9)]
    return {"week_start": "monday", "claim_from": "2019-03-01", "days": days,
            "paid": [{"period": "2019-02", "overtime": 150000}, {"period": "2019-03", "overtime": 50000}]}


def test_청구기간_밖_기지급액은_비교_충당에서_뺀다():
    res = run(_paid_outside_claim(), hourly=10000, ot_overpayment_character="erroneous")
    assert [r.key for r in res.rows] == ["2019-03"]
    assert res.total == D(10000) * 10 * D("1.5") - D(50000)     # 3월 부족분 100,000원(2월분으로 상계하지 않음)
    assert any("밖 기지급액" in w and "2019-02" in w for w in res.warnings)
    assert run(_paid_outside_claim(), hourly=10000).total == res.total   # 초과지급 행이 없어 OT-18 선택 불필요


def test_청구기간_밖_기지급액_기간에는_간주합의_하한도_붙지_않는다():
    raw = {"claim_from": "2019-03-01", "agreed_hours": [{"from": "2019-01-01", "to": "2019-12-31", "overtime": 20}],
           "months": [{"period": "2019-03", "overtime_hours": 12}], "paid": [{"period": "2019-01", "overtime": 1000}]}
    res = run(raw, hourly=10000)
    assert [r.key for r in res.rows] == ["2019-03"]
    assert res.total == D(10000) * 20 * D("1.5")


def test_청구기간_경계가_임금산정기간_중간이면_기지급액_경고():
    days = [{"date": f"2019-03-{d:02d}", "hours": 8} for d in range(25, 31)]
    raw = {"week_start": "monday", "claim_from": "2019-03-30", "days": days, "paid": [{"period": "2019-03", "overtime": 1000}]}
    res = run(raw, hourly=10000, ot_weekly_allocation="last_days_first")
    assert any("경계에 걸칩니다" in w and "2019-03" in w for w in res.warnings)
    quiet = run(dict(raw, paid=[]), hourly=10000, ot_weekly_allocation="last_days_first")
    assert not any("경계에 걸칩니다" in w for w in quiet.warnings)


def test_청구기간_순서_오류():
    with pytest.raises(LaborError, match="claim_to"):
        load_overtime({"claim_from": "2019-03-01", "claim_to": "2019-02-28"}, WORKER)


def test_청구기간_밖_날짜로는_M6_경고를_내지_않음():
    raw = {"claim_from": "2025-01-01", "months": [{"period": "2024-12", "to": "2024-12-18", "overtime_hours": 1},
                                                  {"period": "2025-01", "overtime_hours": 1}]}
    res = run(raw, hourly=10000)
    assert not any("M6" in w for w in res.warnings)
    assert [r.key for r in res.rows] == ["2025-01"]


def test_2024_12_19_걸치면_경고():
    res = run({"months": [{"period": "2024-12", "to": "2024-12-18", "overtime_hours": 1},
                          {"period": "2025-01", "overtime_hours": 1}]}, hourly=10000)
    assert any("M6" in w for w in res.warnings)


def test_탄력적_근로시간제_일별기록_오류():
    with pytest.raises(LaborError, match="M1"):
        run({"week_start": "monday", "flexible_periods": [["2019-03-01", "2019-03-31"]],
             "days": [{"date": "2019-03-04", "hours": 10}]}, hourly=10000)


# ================================================================ 입력 누락·오류
def test_정기지급일_누락():
    with pytest.raises(LaborError, match="pay_day"):
        load_overtime({"months": []}, {})


def test_기산요일_누락():
    with pytest.raises(LaborError, match="week_start"):
        load_overtime({"days": [{"date": "2019-03-04", "hours": 8}]}, WORKER)


def test_통상시급_deps_누락():
    with pytest.raises(LaborError, match="hourly_of"):
        run({"months": [{"period": "2019-03", "overtime_hours": 1}]}, hourly=None)


def test_시각_또는_시간_누락():
    with pytest.raises(LaborError, match="hours"):
        load_overtime({"week_start": "monday", "days": [{"date": "2019-03-04", "start": "09:00"}]}, WORKER)


def test_휴일_종류_누락():
    with pytest.raises(LaborError, match="holiday_kind"):
        load_overtime({"week_start": "monday", "days": [{"date": "2019-03-10", "hours": 8, "holiday": True}]}, WORKER)


def test_공휴일인데_규모_누락():
    with pytest.raises(LaborError, match="size_band"):
        run({"week_start": "monday", "days": [{"date": "2022-03-01", "hours": 8, "holiday": True,
                                               "holiday_kind": "public"}]}, hourly=10000)


def test_시행일_이후_휴일근로인데_규모_누락():
    with pytest.raises(LaborError, match="size_band"):
        run({"week_start": "monday", "days": [{"date": "2019-03-10", "hours": 8, "holiday": True,
                                               "holiday_kind": "weekly"}]}, hourly=10000)


def test_단시간_소정시간_누락():
    with pytest.raises(LaborError, match="scheduled_daily_hours"):
        load_overtime({"part_time": True}, WORKER)


def test_기지급액_중복과_방식_혼용():
    with pytest.raises(LaborError, match="한 곳에만"):
        load_overtime({"months": [{"period": "2019-03", "paid": {"overtime": 1}}],
                       "paid": [{"period": "2019-03", "overtime": 1}]}, WORKER)
    with pytest.raises(LaborError, match="한 방식만"):
        run({"week_start": "monday", "days": [{"date": "2019-03-04", "hours": 9}],
             "months": [{"period": "2019-03", "overtime_hours": 1}]}, hourly=10000)


def test_알수없는_키와_옵션():
    with pytest.raises(LaborError, match="알 수 없는 키"):
        load_overtime({"months": [{"period": "2019-03", "ot_hours": 1}]}, WORKER)
    with pytest.raises(LaborError):
        resolve_options({"ot_compare_unit": "year"}, OPTIONS)
    with pytest.raises(LaborError, match="agreed"):
        run({"months": [{"period": "2019-03", "overtime_hours": 1}]}, hourly=10000, ot_claim_basis="greater")


def test_약정_가산율_일부_누락():
    with pytest.raises(LaborError, match="holiday_gt8"):
        load_overtime({"agreed": {"valid": True, "hourly": [{"from": "2019-01-01", "amount": 9000}],
                                  "rates": {"overtime": 0.5, "night": 0.5, "holiday_le8": 0.5}}}, WORKER)


def test_승인일_없는_감시단속적():
    with pytest.raises(LaborError, match="approved_on"):
        load_overtime({"exempt_63": [{"from": "2019-01-01", "category": 3}]}, WORKER)


def test_yaml_60진수_시각():
    # PyYAML 은 따옴표 없는 20:00 을 1200 으로 읽는다 → 분으로 해석
    inp = load_overtime({"week_start": 0, "days": [{"date": "2018-02-19", "start": 1200, "end": 480, "scheduled_hours": 0}]}, WORKER)
    assert inp.days[0].start == 20 * 60 and inp.days[0].end == 8 * 60


def test_따옴표_없는_점_표기_월은_오류():
    # PyYAML 은 따옴표 없는 2024.10 을 소수 2024.1 로 읽는다 → 1월과 구별할 수 없으므로 받지 않는다
    period = yaml.safe_load("period: 2024.10")["period"]
    assert period == 2024.1
    with pytest.raises(LaborError, match="따옴표"):
        load_overtime({"months": [{"period": period, "overtime_hours": 1}]}, WORKER)
    with pytest.raises(LaborError, match="따옴표"):
        load_overtime({"paid": [{"period": period, "overtime": 1}]}, WORKER)
    inp = load_overtime({"months": [{"period": "2024.10", "overtime_hours": 1}],
                         "paid": [{"period": "2024. 11.", "overtime": 1}]}, WORKER)
    assert [m.key for m in inp.months] == ["2024-10"] and list(inp.paid) == ["2024-11"]
