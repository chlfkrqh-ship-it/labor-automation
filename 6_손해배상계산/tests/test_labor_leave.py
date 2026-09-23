"""연차휴가 발생일수·미사용 연차휴가수당 (engine/labor/leave.py) 검증.

골든 예시는 조사 문서 annual_leave.md 3절과 검증 메모의 판결 원문 숫자다.
판결문에 없는 사실(입사일, 산정기간 시작일 등)을 테스트용으로 정한 경우 그 사실을 주석에 적었다.
금액 기대값은 판결 숫자이거나, assert 옆에 Decimal 식을 그대로 적은 값이다.
"""

import sys
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.labor.common import LaborError, resolve_options  # noqa: E402
from engine.labor.leave import (  # noqa: E402
    OPTIONS,
    RULES,
    _first_payday_on_or_after,
    calculate_leave,
    load_leave,
    period_span,
    promotion_first_notice_window,
)

D = Decimal


def run(raw, worker=None, daily=None, deps=None, **opt):
    inp = load_leave(raw, worker)
    opts, _ = resolve_options(opt, OPTIONS)
    deps = dict(deps or {})
    if daily is not None:
        deps["daily_ordinary_of"] = daily if callable(daily) else (lambda d, v=D(daily): v)
    return calculate_leave(inp, opts, **deps)


def mains(res):
    return [r for r in res.rows if r.kind == "main"]


def monthly_days(res, period_no=1):
    return sum((r.accrued_days for r in res.rows if r.kind == "monthly" and r.period_no == period_no), D(0))


# ================================================================ 모듈 규약
def test_옵션_키_접두어와_기본값():
    assert all(k.startswith("al_") for k in OPTIONS)
    values, used = resolve_options({}, OPTIONS)
    assert values["al_final_rounding"] == "floor"
    assert values["al_round_after_full_product"] is True
    assert values["al_promotion_window"] == "after"
    assert "before" not in OPTIONS["al_promotion_window"].choices     # AL-16: 2019다279283 과 모순
    assert values["al_below80_interplay"] == "prorate_only"
    assert values["al_accrual_rule_override"] == "none"
    assert values["al_first_year_below80"] == "no_double"
    assert values["al_mixed_reduced_hours"] == "none"


def test_규칙_상태_어휘():
    allowed = {"판례확립", "법령", "행정해석", "하급심", "실무관행", "불명확"}
    for rid, (summary, status) in RULES.items():
        assert summary
        assert set(status.split("·")) <= allowed, rid
    assert RULES["AL-02"][1] == "법령·하급심"
    assert RULES["AL-05"][1] == "법령·행정해석"
    assert RULES["AL-06"][1] == "판례확립·행정해석"
    for m in ("M1", "M2", "M3", "M4", "M5", "M6"):
        assert m in RULES


# ================================================================ 골든 G1 대법원 2021다227100
def test_G1_1년_기간제_최대_11일_추가수당_없음():
    # 근로기간 2017. 8. 1.~2018. 7. 31., 사용 15일. 출근 자료는 판결에 없어 결근 없음으로 가정.
    res = run({"hire_date": "2017-08-01", "last_working_day": "2018-07-31", "assume_full_attendance": True,
               "periods": [{"used_monthly_days": 15}]}, daily=1)
    assert monthly_days(res) == 11
    main = mains(res)[0]
    assert main.accrual_date == date(2018, 8, 1) and main.accrued_days == 0   # "그다음 날인 2018. 8. 1." 미발생
    assert res.total == 0
    assert any("사용" in w and "많습니다" in w for w in res.warnings)


# ================================================================ 골든 G2 대법원 2022다245419
def test_G2a_1년_3개월_근로자_26일():
    # 2018. 9. 18.부터 약 1년 3개월 근로. 마지막 근로일은 판결에 없어 2019. 12. 17.로 정함(2019. 9. 18.~2020. 9. 17. 어느 날이어도 같음).
    res = run({"hire_date": "2018-09-18", "last_working_day": "2019-12-17", "assume_full_attendance": True,
               "periods": [{}]}, worker={"pay_day": 25}, daily=1)
    main = mains(res)[0]
    assert main.accrual_date == date(2019, 9, 18)     # "1년간의 근로를 마친 다음 날인 2019. 9. 18."
    assert monthly_days(res) + main.accrued_days == 26


def test_G2b_2년_근로_12월31일_퇴직_2년차분_미발생():
    res = run({"hire_date": "2018-01-01", "last_working_day": "2019-12-31", "assume_full_attendance": True,
               "periods": [{}, {}]}, worker={"pay_day": 25}, daily=1)
    second = [r for r in mains(res) if r.period_no == 2][0]
    assert second.accrual_date == date(2020, 1, 1)
    assert second.accrued_days == 0 and "미발생" in second.source


def test_G2c_1일분_73776원():
    # 1년 기간제, 11일 중 10일 사용, 1일분 73,776원(원심 인정). 입사일은 판결에 없어 2019. 1. 1.로 정함.
    res = run({"hire_date": "2019-01-01", "last_working_day": "2019-12-31", "assume_full_attendance": True,
               "periods": [{"used_monthly_days": 10}]}, daily=73776)
    assert monthly_days(res) == 11
    assert res.total == D(73776) * 1
    [claim] = res.claims
    assert claim.settlement and claim.due_date == date(2020, 1, 14)


# ================================================================ 골든 G3 대법원 2022다231403 → 서울중앙지법 2023나72464
def test_G3_시효_기산점과_완성일():
    # 근무기간 2014. 7. 21.~2015. 7. 20.분, 휴가권 취득 2015. 7. 21., 소 제기 2019. 3. 15.
    res = run({"hire_date": "2014-07-21", "last_working_day": "2018-02-21",
               "periods": [{"granted_days": 8}, {"granted_days": 8}, {"granted_days": 9}]},
              worker={"pay_day": 25}, daily=lambda d: D(12381) * 8)
    first = mains(res)[0]
    assert first.accrual_date == date(2015, 7, 21)
    assert first.claim_arises == date(2016, 7, 21)          # 원심의 2015. 7. 21. 기산은 파기됨
    assert first.prescription_date == date(2019, 7, 20)
    assert date(2019, 3, 15) <= first.prescription_date      # 소 제기일 기준 시효 미완성
    assert any("소 제기일과 대조 필요" in w for w in res.warnings)


def test_G3_금액_2476200원과_퇴직_14일():
    # 시간급 12,381원 × 8시간 × 미사용 25일(8+8+9). 연도별 배분은 판결 표기(8일+8일+9일) 순서대로 둠.
    res = run({"hire_date": "2014-07-21", "last_working_day": "2018-02-21",
               "periods": [{"granted_days": 8}, {"granted_days": 8}, {"granted_days": 9}]},
              worker={"pay_day": 25}, daily=lambda d: D(12381) * 8)
    assert res.total == D("2476200")                          # 판결 원문
    last = [r for r in mains(res) if r.period_no == 3][0]
    assert last.settlement and last.pay_due_date == date(2018, 3, 7)   # 지연손해금 "2018. 3. 8."부터
    # 판결은 25일 전부를 퇴직일로부터 14일 경과 다음날부터 기산 → all_settlement 옵션으로 재현
    res2 = run({"hire_date": "2014-07-21", "last_working_day": "2018-02-21",
                "periods": [{"granted_days": 8}, {"granted_days": 8}, {"granted_days": 9}]},
               worker={"pay_day": 25}, daily=lambda d: D(12381) * 8, al_due_when_retired="all_settlement")
    assert {c.due_date for c in res2.claims} == {date(2018, 3, 7)}
    assert res2.total == D("2476200")


# ================================================================ 골든 G4 서울서부지법 2020가단278289
def _g4_daily(d):
    monthly = D(6389170) if d <= date(2016, 12, 31) else D(6527250) if d <= date(2017, 12, 31) else D(7942250)
    hourly = (monthly / 209).quantize(D(1), rounding=ROUND_HALF_UP)   # 사규 '통상임금/209', 31,230.86 → 31,231
    return hourly * 8


def test_G4_연도별_차액_합계_731256원():
    # 산정기간 시작일(12. 4.)은 '2017. 12. 4.~2018. 12. 3. 분' 표기에서, 입사연도는 테스트용으로 2010년으로 정함.
    raw = {"hire_date": "2010-12-04", "last_working_day": "2018-12-10", "periods": [
        {"start": "2014-12-04", "granted_days": 17, "paid_amount": 4073200},
        {"start": "2015-12-04", "granted_days": 17, "paid_amount": 4162960},
        {"start": "2016-12-04", "granted_days": 10, "paid_amount": 2477600},
        {"start": "2017-12-04", "granted_days": 10, "paid_amount": 3716100},
    ]}
    res = run(raw, worker={"pay_day": 25}, daily=_g4_daily, al_due_when_retired="all_settlement")
    rows = mains(res)
    assert [r.amount for r in rows] == [D(4157520), D(4247416), D(3040080), D(3040080)]   # 판결 원문
    assert [r.claim_amount for r in rows] == [D(84320), D(84456), D(562480), D(0)]         # 판결 원문
    assert res.total == D(731256)                                                          # 판결 원문
    assert {c.due_date for c in res.claims} == {date(2018, 12, 24)}   # "14일이 경과한 2018. 12. 25.부터"


# ================================================================ 골든 G5 서울서부지법 2022나48711
G5_RAW = {"hire_date": "2000-03-02", "last_working_day": "2017-06-30",     # 입사일은 테스트용
          "periods": [{"start": "2016-03-02", "granted_days": "25.5", "paid_amount": 3656240}]}


def test_G5_10원_미만_버림_5014660원과_차액():
    res = run(G5_RAW, daily=lambda d: D(5137570) * 8 / 209, al_final_rounding="floor10")
    [row] = [r for r in mains(res) if r.unused]
    assert row.amount == D(5014660)                  # 판결 원문 "5,014,660원{… 10원 미만 버림}"
    assert row.claim_amount == D(1358420)            # 판결 원문 인용액(기지급 3,656,240원 기준)
    assert row.pay_due_date == date(2017, 7, 14)     # 지연손해금 "2017. 7. 15.부터"
    assert row.settlement


def test_G5_기지급액_3656240원_재현():
    raw = dict(G5_RAW, periods=[{"start": "2016-03-02", "granted_days": "25.5"}])
    res = run(raw, daily=lambda d: D(3745860) * 8 / 209, al_final_rounding="floor10")
    assert res.total == D(3656240)


def test_G5_일당_먼저_끊으면_불일치():
    res = run(G5_RAW, daily=lambda d: D(5137570) * 8 / 209, al_final_rounding="floor10",
              al_round_after_full_product=False)
    # 196,653 × 25.5 = 5,014,651.5 → 10원 미만 버림 5,014,650 (판결 5,014,660원과 다름)
    assert [r.amount for r in mains(res) if r.unused] == [D(196653) * D("25.5") // 10 * 10]


def test_G5_퇴직시_시효_기산점_옵션():
    a = run(G5_RAW, daily=lambda d: D(5137570) * 8 / 209)
    b = run(G5_RAW, daily=lambda d: D(5137570) * 8 / 209, al_retire_prescription_start="end_of_use_period")
    ra = [r for r in mains(a) if r.unused][0]
    rb = [r for r in mains(b) if r.unused][0]
    assert ra.prescription_date == date(2020, 6, 30)     # 2017. 7. 1. + 3년 − 1일
    assert rb.prescription_date == date(2021, 3, 1)      # 사용기간 말일 2018. 3. 1. 다음 날 + 3년 − 1일


# ================================================================ 골든 G6 근로기준과-5802 (회계연도 퇴직 정산)
def _g6_raw(last):
    return {"hire_date": "2004-08-01", "last_working_day": last, "period_basis": "fiscal_year",
            "fy_clause_scope": "grant_date_only",
            "periods": [{"granted_days": 7, "used_days": 7}, {"granted_days": 15, "used_days": 15},
                        {"granted_days": 15, "used_days": 15}, {"granted_days": 16, "used_days": 16},
                        {"granted_days": 16, "used_days": 16}]}


def test_G6_입사일기준_79일_회계연도_69일_정산_10일():
    res = run(_g6_raw("2009-09-30"), daily=100000)
    assert res.hire_basis_days == 79 and res.fiscal_basis_days == 69    # 회시 원문 수치
    [settle] = [r for r in res.rows if r.kind == "settlement"]
    assert settle.accrued_days == 10
    assert settle.amount == D(100000) * 10
    assert settle.settlement and settle.pay_due_date == date(2009, 10, 14)
    assert any("확인불가" in w for w in res.warnings)


def test_G6_퇴직_2009_7_30이면_회계연도_기준_유지():
    res = run(_g6_raw("2009-07-30"), daily=100000)
    assert res.hire_basis_days == 62 and res.fiscal_basis_days == 69    # "입사일기준 총 62일, 회계연도기준 총 69일"
    assert not [r for r in res.rows if r.kind == "settlement"]
    assert res.total == 0


# ================================================================ 골든 G7 대법원 2019다279283 (사용촉진)
def test_G7_촉구_창():
    assert promotion_first_notice_window(date(2016, 12, 31), "art61_1", "after") == (date(2016, 7, 1), date(2016, 7, 10))
    lo, hi = promotion_first_notice_window(date(2016, 12, 31), "art61_1", "both")
    assert lo <= date(2016, 7, 6) <= hi
    with pytest.raises(LaborError):
        promotion_first_notice_window(date(2016, 12, 31), "art61_1", "before")


def _g7_raw(**promotion):
    # 사용기간 말일 2016. 12. 31.이 되도록 회계연도 2015년분으로 둠(입사일은 테스트용).
    return {"hire_date": "2015-01-01", "period_basis": "fiscal_year", "fy_clause_scope": "accrual_period",
            "periods": [{"granted_days": 21, "promotion": promotion}]}


def test_G7_2차_통보_없고_일부만_지정_보상의무_존속():
    res = run(_g7_raw(first_notice="2016-07-06"), worker={"pay_day": 25}, daily=100000)
    row = mains(res)[0]
    assert row.use_end == date(2016, 12, 31)
    assert row.promotion_lawful is False
    assert row.extinguished == 0 and row.unused == 21


def test_G7_2차_통보_기한_경계와_지정일_근로():
    ok = run(_g7_raw(first_notice="2016-07-06", second_notice="2016-10-31", worked_designated_days=20),
             worker={"pay_day": 25}, daily=100000)
    row = mains(ok)[0]
    assert row.promotion_lawful is True
    assert row.extinguished == 1 and row.unused == 20     # 지정일에 근로한 20일은 보상의무 존속
    late = run(_g7_raw(first_notice="2016-07-06", second_notice="2016-11-01"), worker={"pay_day": 25}, daily=100000)
    assert mains(late)[0].promotion_lawful is False


def test_사용기간_중_퇴직이면_촉진_효과_없음():
    raw = _g7_raw(lawful=True)
    raw["last_working_day"] = "2016-09-30"
    res = run(raw, daily=100000)
    row = mains(res)[0]
    assert row.extinguished == 0 and row.unused == 21 and row.settlement


# ================================================================ 골든 G8 부산지법 2021가단304232 (구 제3항)
def _g8(hire, last, **opt):
    return run({"hire_date": hire, "last_working_day": last, "assume_full_attendance": True, "periods": []},
               worker={"pay_day": 25}, daily=100000, **opt)


def test_G8_원고B_2017_5_29_이전_입사_11일_4일():
    res = _g8("2017-03-01", "2019-12-31")
    assert monthly_days(res) == 11
    p1 = [r for r in mains(res) if r.period_no == 1][0]
    assert p1.accrued_days == 4                               # "2년차 연차휴가일수 4일"
    p2 = [r for r in mains(res) if r.period_no == 2][0]
    assert p2.pay_due_date == date(2020, 1, 14)               # 지연손해금 "2020. 1. 15.부터"


@pytest.mark.parametrize("hire", ["2017-07-13", "2017-10-02", "2018-01-08"])
def test_G8_원고DEF_2017_5_30_이후_입사_11일_15일(hire):
    res = _g8(hire, "2020-02-29")
    assert monthly_days(res) == 11
    assert [r for r in mains(res) if r.period_no == 1][0].accrued_days == 15
    settled = [r for r in res.rows if r.settlement]
    assert settled and {r.pay_due_date for r in settled} == {date(2020, 3, 14)}   # "2020. 3. 15.부터"


def test_구_제3항_기준일_경계_옵션():
    le = _g8("2017-05-29", "2019-12-31")
    lt = _g8("2017-05-29", "2019-12-31", al_old_art60_3_compare="lt")
    after = _g8("2017-05-30", "2019-12-31")
    assert mains(le)[0].accrued_days == 4
    assert mains(lt)[0].accrued_days == 15
    assert mains(after)[0].accrued_days == 15


def test_구_제3항_사용일수_공제_방식():
    res = run({"hire_date": "2017-03-01", "last_working_day": "2019-12-31", "assume_full_attendance": True,
               "periods": [{"used_monthly_days": 3}]}, worker={"pay_day": 25}, daily=100000,
              al_old_art60_3_deduct="used")
    assert mains(res)[0].accrued_days == 15 - 3
    assert all(r.unused == 0 for r in res.rows if r.kind == "monthly")   # 미사용 월 휴가는 15일에 흡수


# ================================================================ 골든 G9 대전고법 2019나41 (재직 중 지급기일)
def _g9_raw():
    # 회계연도 2011년분(2011. 1. 25. 입사자 소정근로일수 220일), 부당해고 52일 출근 간주.
    # 부여일수 15일과 1일 통상임금은 판결 별지에 없어 테스트용으로 정함.
    return {"hire_date": "2011-01-25", "period_basis": "fiscal_year", "fy_clause_scope": "accrual_period",
            "periods": [{"scheduled_days": 220, "attended_days": 168, "deemed": {"unfair_dismissal": 52},
                         "granted_days": 15}]}


def test_G9_휴가권_2012_1_1_지급의무_2013_1_25():
    res = run(_g9_raw(), worker={"pay_day": 25}, daily=100000)
    row = mains(res)[0]
    assert row.attendance_rate == 1                    # 해고기간 출근 간주
    assert row.accrual_date == date(2012, 1, 1)
    assert row.claim_arises == date(2013, 1, 1)
    assert row.pay_due_date == date(2013, 1, 25)       # "2013. 1. 25.에 비로소 발생", 지연 2013. 1. 26.부터
    assert not row.settlement
    other = run(_g9_raw(), worker={"pay_day": 25}, daily=100000, al_in_service_due="claim_arises")
    assert mains(other)[0].pay_due_date == date(2013, 1, 1)


def test_G9_단협_1_5배_산식과_법정_산식_전체_비교():
    raw = _g9_raw()
    raw["agreed_formula"] = {"multiplier": "1.5", "wage_basis": "statutory"}
    res = run(raw, worker={"pay_day": 25}, daily=100000)
    assert res.basis == "agreed"
    assert res.total == D(100000) * 15 * D("1.5")
    assert res.statutory_total == D(100000) * 15


# ================================================================ 골든 G10 대법원 2014다232296
def test_G10_1년_전체_업무상_재해_휴업도_출근율_충족():
    # 입사일은 판결에 없어 1990. 1. 1.로 정함 → 2008년 산정기간은 19년차.
    raw = {"hire_date": "1990-01-01", "periods": [
        {"start": "2008-01-01", "scheduled_days": 250, "attended_days": 0, "deemed": {"industrial_accident": 250}}]}
    res = run(raw, worker={"pay_day": 25}, daily=100000)
    row = mains(res)[0]
    n = 19
    assert row.attendance_rate == 1
    assert row.accrued_days == 15 + (n - 1) // 2
    assert res.total == D(100000) * (15 + (n - 1) // 2)   # 사용연도 출근 없어도 수당 청구(AL-21)


# ================================================================ 추가 골든 G12 의정부지법 2024나226635
def test_G12_회계연도_부여_26일_미사용_16_75일_7504000원():
    # 입사일은 판결에 없어 1990. 3. 2.로 정함. 법정 1일 통상임금은 월 6,832,000원 × 8 / 183 으로 둠.
    raw = {"hire_date": "1990-03-02", "last_working_day": "2021-04-21", "period_basis": "fiscal_year",
           "fy_clause_scope": "accrual_period",
           "agreed_formula": {"multiplier": "1.5", "wage_basis": "agreed", "monthly_divisor": 183, "daily_hours": 8},
           "agreed_ordinary_wage": [{"from": "2021-01-01", "monthly": 6832000}],
           "periods": [{"start": "2020-01-01", "granted_days": 26, "used_days": "9.25"}]}
    res = run(raw, daily=lambda d: D(6832000) * 8 / 183)
    row = [r for r in mains(res) if r.unused][0]
    assert row.unused == D("16.75")
    assert res.basis == "agreed"
    assert res.total == D(7504000)                     # 판결 원문 "7,504,000원"
    assert row.settlement and row.pay_due_date == date(2021, 5, 5)


# ================================================================ AL-03 날짜 연산
def test_윤년_1년은_366일_날짜로_판단():
    before = run({"hire_date": "2019-03-01", "last_working_day": "2020-02-29", "assume_full_attendance": True,
                  "periods": [{}]}, daily=1)
    after = run({"hire_date": "2019-03-01", "last_working_day": "2020-03-01", "assume_full_attendance": True,
                 "periods": [{}]}, daily=1)
    assert mains(before)[0].accrual_date == date(2020, 3, 1)
    assert mains(before)[0].accrued_days == 0
    assert mains(after)[0].accrued_days == 15


def test_2월29일_입사_대응일_옵션():
    assert period_span(date(2020, 2, 29), 12, "civil_code") == (date(2021, 2, 28), date(2021, 3, 1))
    assert period_span(date(2020, 2, 29), 12, "clamp") == (date(2021, 2, 27), date(2021, 2, 28))
    assert period_span(date(2019, 1, 31), 1) == (date(2019, 2, 28), date(2019, 3, 1))
    assert period_span(date(2019, 1, 31), 2) == (date(2019, 3, 30), date(2019, 3, 31))


def test_시효_완성일은_대응일_옵션과_무관하게_민법_제160조():
    # 마지막 근로일 2024. 2. 28. → 시효 기산일 2024. 2. 29. → 3년 뒤 2월에 29일이 없어 그 월 말일 2027. 2. 28. 만료
    for mode in ("civil_code", "clamp"):
        res = run({"hire_date": "2021-06-01", "last_working_day": "2024-02-28", "assume_full_attendance": True,
                   "periods": []}, worker={"pay_day": 25}, daily=100000, al_missing_anniversary=mode)
        rows = [r for r in res.rows if r.claim_arises == date(2024, 2, 29)]
        assert rows and {r.prescription_date for r in rows} == {date(2027, 2, 28)}, mode


def test_재직_중_기준일_뒤_산정기간은_근로관계_종료로_적지_않음():
    res = run({"hire_date": "2023-03-02", "calc_until": "2026-09-15", "assume_full_attendance": True, "periods": []},
              worker={"pay_day": 25}, daily=100000)
    row = [r for r in mains(res) if r.accrual_date == date(2027, 3, 2)][0]
    assert row.accrued_days == 0
    assert "근로관계 종료" not in row.source and "기준일" in row.source
    assert "2016다48297" not in row.note and "재직 중" in row.note


def test_기준일_뒤_청구권은_합계_제외():
    res = run({"hire_date": "2020-02-29", "calc_until": "2021-03-01", "assume_full_attendance": True,
               "periods": [{"used_monthly_days": 11}]}, worker={"pay_day": 25}, daily=100000)
    main = [r for r in mains(res) if r.period_no == 1][0]
    assert main.accrual_date == date(2021, 3, 1)
    assert main.claim_pending and res.total == 0 and not res.claims


def test_발생시기_특약_M1():
    raw = {"hire_date": "2015-07-01", "last_working_day": "2020-06-30", "assume_full_attendance": True,
           "periods": [{"start": "2019-07-01", "accrual_date": "2020-06-30"}]}
    plain = run(raw, daily=100000)
    assert mains(plain)[0].accrued_days == 0
    assert any("al_accrual_rule_override=none" in w for w in plain.warnings)
    special = run(raw, daily=100000, al_accrual_rule_override="per_input")
    row = mains(special)[0]
    n = 5
    assert row.accrued_days == 15 + (n - 1) // 2
    assert row.claim_arises == date(2020, 7, 1) and row.pay_due_date == date(2020, 7, 14)


# ================================================================ AL-01 적용 범위
def test_5인_미만_사업장_미적용():
    res = run({"hire_date": "2019-01-01", "last_working_day": "2021-06-30", "assume_full_attendance": True,
               "small_business": True, "periods": []}, daily=100000)
    assert res.total == 0
    assert all(r.accrued_days == 0 for r in res.rows)
    assert any("4명 이하" in r.source for r in res.rows)


def test_5인_미만_플래그는_조립_모듈_deps_가_있어도_산다():
    # 조립 모듈(calculate.py)은 worker.small_business_periods 로 만든 deps(기간이 없으면 늘 거짓)를 넘긴다.
    # 그 deps 가 leave.small_business: true 를 덮으면 제60조 미적용 사업장에 수당이 생긴다.
    raw = {"hire_date": "2019-01-01", "last_working_day": "2021-06-30", "assume_full_attendance": True,
           "small_business": True, "periods": []}
    res = run(raw, worker={"pay_day": 25}, daily=100000, deps={"small_business": lambda d: False})
    assert res.total == 0
    assert all(r.accrued_days == 0 for r in res.rows)
    assert any("4명 이하" in r.source for r in res.rows)
    # 산정기간에 적은 small_business 는 그대로 우선한다
    per = run(dict(raw, periods=[{}, {"small_business": False}]), worker={"pay_day": 25}, daily=100000,
              deps={"small_business": lambda d: False})
    assert {r.period_no: r.accrued_days for r in mains(per)} == {1: 0, 2: 15, 3: 0}   # 3기간은 발생일 전 퇴직


def test_5인_미만_기간만_worker_에서():
    res = run({"hire_date": "2019-01-01", "last_working_day": "2021-06-30", "assume_full_attendance": True,
               "periods": []}, worker={"small_business_periods": [["2020-01-01", "2020-12-31"]], "pay_day": 25},
              daily=100000)
    p1 = [r for r in mains(res) if r.period_no == 1][0]      # 발생일 2020. 1. 1. 소규모
    p2 = [r for r in mains(res) if r.period_no == 2][0]      # 발생일 2021. 1. 1.
    assert p1.accrued_days == 0 and p2.accrued_days == 15


@pytest.mark.parametrize("weekly,expected_hours", [("14.99", None), ("15", D(15) * 15 * 8 / 40)])
def test_주_15시간_경계(weekly, expected_hours):
    res = run({"hire_date": "2019-01-01", "assume_full_attendance": True, "weekly_hours": weekly,
               "periods": [{"start": "2020-01-01"}]}, worker={"pay_day": 25}, daily=100000)
    row = mains(res)[0]
    if expected_hours is None:
        assert row.accrued_days == 0 and "15시간 미만" in row.source
    else:
        assert row.accrued_hours == expected_hours


# ================================================================ AL-04·05 일수
@pytest.mark.parametrize("k", [2, 3, 4, 19, 20, 22])
def test_가산휴가_표(k):
    start = f"{2000 + k}-01-01"
    res = run({"hire_date": "2000-01-01", "assume_full_attendance": True, "periods": [{"start": start}]},
              worker={"pay_day": 25}, daily=1)
    n = k + 1
    assert mains(res)[0].accrued_days == min(25, 15 + (n - 1) // 2)


def test_출근율_80퍼센트_경계():
    ok = run({"hire_date": "2015-01-01", "periods": [{"start": "2016-01-01", "scheduled_days": 250, "attended_days": 200}]},
             worker={"pay_day": 25}, daily=1)
    assert mains(ok)[0].accrued_days == 15
    below = run({"hire_date": "2015-01-01", "periods": [
        {"start": "2016-01-01", "scheduled_days": 250, "attended_days": 199,
         "monthly_perfect": [True] * 5 + [False] * 7}]}, worker={"pay_day": 25}, daily=1)
    row = mains(below)[0]
    assert row.accrued_days == 5 and "제2항(b)" in row.source


def test_80퍼센트_미만_가산_옵션():
    raw = {"hire_date": "2010-01-01", "periods": [
        {"start": "2016-01-01", "scheduled_days": 250, "attended_days": 100, "monthly_perfect": [True] * 2 + [False] * 10}]}
    n = 7
    assert mains(run(raw, worker={"pay_day": 25}, daily=1))[0].accrued_days == 2
    loose = run(raw, worker={"pay_day": 25}, daily=1, al_bonus_requires_80pct=False)
    assert mains(loose)[0].accrued_days == 2 + (n - 1) // 2


def test_80퍼센트_미만자_월개근은_2012_8_2_이후_산정기간부터():
    res = run({"hire_date": "2009-01-01", "periods": [
        {"start": "2010-01-01", "scheduled_days": 250, "attended_days": 100, "monthly_perfect": [True] * 12}]},
        worker={"pay_day": 25}, daily=1)
    assert mains(res)[0].accrued_days == 0


def test_80퍼센트_미만_다음_연도_가산은_경고():
    raw = {"hire_date": "2013-01-01", "periods": [
        {"start": "2015-01-01", "scheduled_days": 250, "attended_days": 100, "monthly_perfect": [False] * 12},
        {"start": "2016-01-01", "scheduled_days": 250, "attended_days": 250}]}
    res = run(raw, worker={"pay_day": 25}, daily=1)
    assert [r.accrued_days for r in mains(res)] == [0, 16]
    assert any("계속근로연수" in w for w in res.warnings)


# ================================================================ AL-06 최초 1년
def test_최초_1년_80퍼센트_미만_비중복_기본():
    raw = {"hire_date": "2019-01-01", "periods": [
        {"scheduled_days": 250, "attended_days": 150, "monthly_perfect": [True] * 5 + [False] * 7}]}
    res = run(raw, worker={"pay_day": 25}, daily=1)
    assert monthly_days(res) == 5
    assert mains(res)[0].accrued_days == 0
    assert any("중복" in w for w in res.warnings)
    dbl = run(raw, worker={"pay_day": 25}, daily=1, al_first_year_below80="add_art60_2b")
    assert mains(dbl)[0].accrued_days == 5


def test_12번째_달_개근은_1년_미만_휴가_아님():
    res = run({"hire_date": "2021-01-01", "periods": [
        {"scheduled_days": 250, "attended_days": 250, "monthly_perfect": [True] * 12}]},
        worker={"pay_day": 25}, daily=1)
    assert monthly_days(res) == 11


def test_2020_3_31_개정_전후_사용기간():
    # 입사 2019. 5. 31. → 10번째 월 휴가 발생일 2020. 3. 31.(신법), 9번째 2020. 3. 1.(구법)
    res = run({"hire_date": "2019-05-31", "assume_full_attendance": True, "periods": [{}]},
              worker={"pay_day": 25}, daily=100000)
    monthly = [r for r in res.rows if r.kind == "monthly"]
    new = [r for r in monthly if r.accrual_date == date(2020, 3, 31)]
    assert len(new) == 1 and new[0].accrued_days == 2
    assert new[0].use_end == date(2020, 5, 30)                 # 최초 1년 근로가 끝날 때까지
    assert new[0].claim_arises == date(2020, 5, 31)
    old = [r for r in monthly if r.accrual_date < date(2020, 3, 31)]
    assert sum(r.accrued_days for r in old) == 9
    first = [r for r in old if r.accrual_date == date(2019, 7, 1)][0]
    assert first.use_end == date(2020, 6, 30)                   # 발생일부터 1년


def test_월_실질소정근로일_비례_입력():
    res = run({"hire_date": "2021-01-01", "last_working_day": "2021-06-30", "periods": [
        {"monthly_perfect": [True, "0.5", True, True, True, False, True, True, True, True, True]}]}, daily=100000)
    assert monthly_days(res) == 1 + D("0.5") + 1 + 1 + 1       # 발생일 2. 1.~6. 1. 다섯 번(6. 30. 퇴직), 6번째 달은 7. 1. 발생
    assert res.total == D(100000) * (1 + D("0.5") + 1 + 1 + 1)


# ================================================================ AL-10 비례
def _prorate(scheduled, attended, excluded, monthly=None, **opt):
    period = {"start": "2016-01-01", "scheduled_days": scheduled, "attended_days": attended,
              "excluded": {"agreed_leave": excluded}}
    if monthly is not None:
        period["monthly_perfect"] = monthly
    return mains(run({"hire_date": "2015-01-01", "periods": [period]}, worker={"pay_day": 25}, daily=1, **opt))[0]


def test_비례_2015다66052_8할_미달에_한정():
    assert _prorate(240, 40, 200).accrued_days == D(15) * 40 / 240          # 법제처-24-0778 검산 예 2.5일
    assert _prorate(250, 230, 10).accrued_days == 15                          # 230 ≥ 250 × 0.8 → 비례 안 함
    assert _prorate(250, 230, 10, al_proration_mode="moel_always").accrued_days == D(15) * 240 / 250
    assert _prorate(250, 230, 10, al_proration_mode="supreme_2013").accrued_days == D(15) * 240 / 250


def test_비례_소수_일수_옵션():
    assert _prorate(250, 230, 10, al_proration_mode="moel_always", al_day_fraction="ceil_day").accrued_days == 15
    assert _prorate(250, 230, 10, al_proration_mode="moel_always", al_day_fraction="floor_day").accrued_days == 14
    to_hours = _prorate(250, 230, 10, al_proration_mode="moel_always", al_day_fraction="to_hours").accrued_days
    assert to_hours == D(116) / 8                                             # 14.4일 × 8 = 115.2시간 → 116시간


def test_비례와_제2항b_큰_값_옵션():
    monthly = [True] * 3 + [False] * 9
    assert _prorate(240, 40, 200, monthly).accrued_days == D(15) * 40 / 240
    assert _prorate(240, 40, 200, monthly, al_below80_interplay="max_with_art60_2").accrued_days == 3


def test_제외기간이_소정근로일수_전부면_미발생():
    row = mains(run({"hire_date": "2015-01-01", "periods": [
        {"start": "2016-01-01", "scheduled_days": 240, "attended_days": 0, "excluded": {"union_full_time": 240}}]},
        daily=1))[0]
    assert row.accrued_days == 0 and "전부 제외" in row.source


def test_정당한_정직_옵션():
    raw = {"hire_date": "2015-01-01", "periods": [
        {"start": "2016-01-01", "scheduled_days": 250, "attended_days": 190, "suspension_days": 50,
         "monthly_perfect": [False] * 12}]}
    assert mains(run(raw, worker={"pay_day": 25}, daily=1))[0].accrued_days == 0
    ex = run(raw, worker={"pay_day": 25}, daily=1, al_lawful_suspension="excluded")
    assert mains(ex)[0].accrued_days == D(15) * 200 / 250
    assert any("정직" in w for w in ex.warnings)


# ================================================================ AL-18·19 단시간·혼재
def test_단시간근로자_시간_비례와_시간급_수당():
    raw = {"hire_date": "2019-01-01", "weekly_hours": 20, "daily_hours": 4, "assume_full_attendance": True,
           "periods": [{"start": "2020-01-01"}]}
    res = run(raw, worker={"pay_day": 25}, daily=40000)
    row = mains(res)[0]
    assert row.unit == "시간" and row.accrued_hours == D(15) * 20 / 40 * 8
    assert res.total == D(40000) / 4 * 60


def test_단시간_수당은_통상시급_deps_로_계산하고_1일_시간_불일치를_경고():
    # 통상임금 절은 1일 4시간(시급 10,000원 → 1일 40,000원)인데 leave.daily_hours 를 비워 기본 8시간이 된 경우
    raw = {"hire_date": "2019-01-01", "weekly_hours": 20, "assume_full_attendance": True,
           "periods": [{"start": "2020-01-01"}]}
    hourly = {"hourly_of": lambda d: D(10000)}
    fallback = run(raw, worker={"pay_day": 25}, daily=40000)
    assert fallback.total == D(40000) / 8 * 60                 # deps 없으면 1일 통상임금 ÷ leave.daily_hours — 경고로 알림
    assert any("AL-18" in w and "leave.daily_hours 8" in w for w in fallback.warnings)
    res = run(raw, worker={"pay_day": 25}, daily=40000, deps=hourly)
    assert mains(res)[0].accrued_hours == 60 and res.total == D(10000) * 60
    assert any("AL-18" in w and "(4시간" in w for w in res.warnings)
    same = run(dict(raw, daily_hours=4), worker={"pay_day": 25}, daily=40000, deps=hourly)
    assert same.total == D(10000) * 60 and not any("AL-18" in w for w in same.warnings)
    # 약정 산식(법정 통상임금 × 1.5)도 같은 통상시급을 쓴다
    agreed = run(dict(raw, agreed_formula={"multiplier": "1.5", "wage_basis": "statutory"}), worker={"pay_day": 25},
                 daily=40000, deps=hourly)
    assert agreed.basis == "agreed" and agreed.total == D(10000) * D("1.5") * 60


def test_단시간_1시간_미만_올림():
    raw = {"hire_date": "2019-01-01", "weekly_hours": 21, "assume_full_attendance": True,
           "periods": [{"start": "2021-01-01"}]}
    up = mains(run(raw, worker={"pay_day": 25}, daily=1))[0]
    assert up.accrued_hours == 68                                             # 16 × 21 ÷ 40 × 8 = 67.2
    exact = mains(run(raw, worker={"pay_day": 25}, daily=1, al_pt_hour_rounding="none"))[0]
    assert exact.accrued_hours == D(16) * 21 * 8 / 40


def test_통상_단축_혼재_옵션():
    raw = {"hire_date": "2019-01-01", "assume_full_attendance": True,
           "periods": [{"start": "2020-01-01", "reduced_hours": {"months": 4, "weekly_hours": 20}}]}
    plain = run(raw, worker={"pay_day": 25}, daily=1)
    assert mains(plain)[0].accrued_hours is None and mains(plain)[0].accrued_days == 15
    assert any("AL-19" in w for w in plain.warnings)
    mixed = run(raw, worker={"pay_day": 25}, daily=1, al_mixed_reduced_hours="moel_2013_prorate")
    assert mains(mixed)[0].accrued_hours == D(15) * 8 * ((12 - 4) * 40 + 20 * 4) / (12 * 40)


# ================================================================ AL-12·M4 약정 비교
def test_약정_산식은_전체_비교_항목별_혼합_없음():
    # 1기간은 약정 일급이 높고, 2기간은 법정이 높다. 합계가 큰 쪽 하나로만 계산한다.
    raw = {"hire_date": "2014-01-01", "periods": [
        {"start": "2016-01-01", "granted_days": 10}, {"start": "2017-01-01", "granted_days": 10}],
        "agreed_formula": {"multiplier": 1, "wage_basis": "agreed"},
        "agreed_ordinary_wage": [{"from": "2010-01-01", "daily": 150000}, {"from": "2018-01-01", "daily": 60000}]}
    res = run(raw, worker={"pay_day": 25}, daily=100000)
    assert res.statutory_total == D(100000) * 10 * 2
    assert res.agreed_total == D(150000) * 10 + D(60000) * 10
    assert res.basis == "agreed"
    assert [r.amount for r in mains(res)] == [D(150000) * 10, D(60000) * 10]


def test_약정_통상임금이_낮으면_법정():
    raw = {"hire_date": "2014-01-01", "periods": [{"start": "2016-01-01", "granted_days": 10}],
           "agreed_formula": {"multiplier": "1.5", "wage_basis": "agreed", "monthly_divisor": 209, "daily_hours": 8},
           "agreed_ordinary_wage": [{"from": "2010-01-01", "monthly": 1000000}]}
    res = run(raw, worker={"pay_day": 25}, daily=100000)
    assert res.basis == "statutory" and res.total == D(100000) * 10


def _agreed_days_raw(used, **period):
    # 법정 15일(2년차), 단체협약 휴가 20일, 약정 산식 = 법정 1일 통상임금 × 1. 퇴직 2022. 6. 30.(사용기간 중)
    return {"hire_date": "2020-01-01", "last_working_day": "2022-06-30",
            "agreed_formula": {"multiplier": 1, "wage_basis": "statutory"},
            "periods": [dict({"start": "2021-01-01", "scheduled_days": 248, "attended_days": 248, "agreed_days": 20,
                              "used_days": used}, **period)]}


@pytest.mark.parametrize("used,agreed_left", [(14, 6), (15, 5), (17, 3), (21, 0)])
def test_약정_휴가일수는_법정_일수를_다_써도_남는다(used, agreed_left):
    # 사용 14일이면 약정 6일분인데 사용 15일에서 0이 되던 불연속 — 약정 미사용 = 20 − 사용일수
    res = run(_agreed_days_raw(used), worker={"pay_day": 25}, daily=100000)
    row = mains(res)[0]
    assert row.unused == max(0, 15 - used)
    assert (row.agreed_amount or 0) == D(100000) * agreed_left
    assert res.total == D(100000) * agreed_left
    assert res.basis == ("agreed" if agreed_left else "statutory")
    over = [w for w in res.warnings if "많습니다" in w]
    assert bool(over) == (used > 20)          # 약정 일수 이내 사용은 경고 대신 비고
    if over:
        assert "약정 20일" in over[0]


def test_사용촉진으로_법정_미사용이_소멸해도_약정_초과분은_남는다():
    # 재직 중, 법정 미사용 5일은 적법한 촉진으로 소멸 — 약정 미사용 = 20 − 사용 10 − 소멸 5 = 5일
    raw = _agreed_days_raw(10, promotion={"lawful": True})
    del raw["last_working_day"]
    res = run(raw, worker={"pay_day": 25}, daily=100000)
    row = mains(res)[0]
    assert row.extinguished == 5 and row.unused == 0
    assert row.agreed_amount == D(100000) * 5 and res.basis == "agreed" and res.total == D(100000) * 5
    assert row.claim_arises == date(2023, 1, 1) and row.pay_due_date == date(2023, 1, 25)
    with pytest.raises(LaborError, match="pay_day"):          # 약정분만 남아도 재직 중 지급기일에는 정기지급일이 필요
        run(raw, daily=100000)


# ================================================================ AL-14·22 지급기일·끝수
def test_첫_정기지급일():
    assert _first_payday_on_or_after(date(2013, 1, 1), 25) == date(2013, 1, 25)
    assert _first_payday_on_or_after(date(2013, 1, 25), 25) == date(2013, 1, 25)
    assert _first_payday_on_or_after(date(2013, 1, 26), 25) == date(2013, 2, 25)
    assert _first_payday_on_or_after(date(2013, 2, 1), 31) == date(2013, 2, 28)


def test_재직_중_지급기일_전_퇴직이면_14일_기한():
    # 사용기간 말일 2016. 12. 31., 청구권 2017. 1. 1., 정기지급일 1. 25. 전인 1. 10. 퇴직
    raw = {"hire_date": "2015-01-01", "last_working_day": "2017-01-10", "period_basis": "fiscal_year",
           "fy_clause_scope": "accrual_period", "periods": [{"granted_days": 15}, {"granted_days": 15, "used_days": 15}]}
    res = run(raw, worker={"pay_day": 25}, daily=100000)
    row = mains(res)[0]
    assert row.claim_arises == date(2017, 1, 1)
    assert row.pay_due_date == date(2017, 1, 24) and row.settlement


@pytest.mark.parametrize("mode,expected", [("floor", D(10000)), ("half_up", D(10001)), ("floor10", D(10000))])
def test_최종_끝수_옵션(mode, expected):
    res = run({"hire_date": "2014-01-01", "periods": [{"start": "2016-01-01", "granted_days": 1}]},
              worker={"pay_day": 25}, daily="10000.5", al_final_rounding=mode)
    assert res.total == expected


def test_claims_와_경고():
    res = run({"hire_date": "2014-07-21", "last_working_day": "2018-02-21", "periods": [
        {"granted_days": 8}, {"granted_days": 8}, {"granted_days": 9}]},
        worker={"pay_day": 25}, daily=lambda d: D(12381) * 8)
    assert len(res.claims) == 3
    assert all(c.category == "연차휴가수당" for c in res.claims)
    assert sum(c.amount for c in res.claims) == res.total
    assert [c.settlement for c in res.claims] == [False, False, True]
    assert any(t.rule == "AL-22" for t in res.trace)


def test_출근율_100퍼센트면_최초_1년_모든_달_개근으로_봄():
    # 월별 개근 입력 없이 출근율 100%이면 11개월 개근 → 구 제3항 15 − 11 = 4일
    res = run({"hire_date": "2014-07-21", "last_working_day": "2016-02-21", "periods": [
        {"scheduled_days": 250, "attended_days": 250}]}, worker={"pay_day": 25}, daily=1)
    assert monthly_days(res) == 11
    assert mains(res)[0].accrued_days == 15 - 11


def test_부당해고_간주와_M6_경고():
    res = run({"hire_date": "2015-01-01", "periods": [
        {"start": "2016-01-01", "scheduled_days": 250, "attended_days": 0, "deemed": {"unfair_dismissal": 250}}]},
        worker={"pay_day": 25}, daily=100000)
    assert mains(res)[0].accrued_days == 15
    assert any("M6" in w for w in res.warnings)
    assert any("M2" in w for w in res.warnings)     # 공휴일 유급휴일 반영 확인


def test_기지급액이_많으면_0():
    res = run({"hire_date": "2014-01-01", "periods": [{"start": "2016-01-01", "granted_days": 1, "paid_amount": 200000}]},
              worker={"pay_day": 25}, daily=100000)
    assert res.total == 0 and not res.claims


# ================================================================ 입력 오류
def test_입사일_누락():
    with pytest.raises(LaborError, match="입사일"):
        load_leave({"periods": []})


def test_worker_입사일_사용():
    inp = load_leave({"periods": []}, {"hire_date": "2020-01-01", "last_working_day": "2021-01-31", "pay_day": 25})
    assert inp.hire_date == date(2020, 1, 1) and inp.last_working_day == date(2021, 1, 31) and inp.pay_day == 25


def test_빈칸_마지막_근로일과_지급일은_worker_값():
    worker = {"hire_date": "2018-01-01", "last_working_day": "2019-12-31", "pay_day": 25}
    for blank in (None, ""):
        inp = load_leave({"last_working_day": blank, "pay_day": blank, "periods": []}, worker)
        assert inp.last_working_day == date(2019, 12, 31) and inp.pay_day == 25


def test_템플릿대로_last_working_day_를_비우면_키를_뺀_것과_같다():
    # docstring 템플릿을 복사해 `last_working_day:` 를 비운 YAML. 재직자로 계산하면 2020. 1. 1. 발생분이 생긴다(2016다48297 위반).
    import yaml

    worker = {"hire_date": "2018-01-01", "last_working_day": "2019-12-31", "pay_day": 25}
    blank = yaml.safe_load("last_working_day:\npay_day:\nassume_full_attendance: true\nperiods: [{}, {}]\n")
    assert blank["last_working_day"] is None and blank["pay_day"] is None
    res = run(blank, worker=worker, daily=100000)
    omitted = run({"assume_full_attendance": True, "periods": [{}, {}]}, worker=worker, daily=100000)
    second = [r for r in mains(res) if r.period_no == 2][0]
    assert second.accrual_date == date(2020, 1, 1) and second.accrued_days == 0 and "근로관계 종료" in second.source
    assert res.total == omitted.total == D(100000) * (11 + 15)
    assert ([(c.amount, c.due_date, c.settlement) for c in res.claims]
            == [(c.amount, c.due_date, c.settlement) for c in omitted.claims])


def test_출근자료_누락():
    with pytest.raises(LaborError, match="scheduled_days"):
        run({"hire_date": "2019-01-01", "periods": [{"start": "2020-01-01"}]}, daily=1)


def test_최초_1년_월개근_누락():
    with pytest.raises(LaborError, match="monthly_perfect"):
        run({"hire_date": "2019-01-01", "periods": [{"scheduled_days": 250, "attended_days": 240}]}, daily=1)


def test_80퍼센트_미만_월개근_누락():
    with pytest.raises(LaborError, match="monthly_perfect"):
        run({"hire_date": "2015-01-01", "periods": [{"start": "2016-01-01", "scheduled_days": 250, "attended_days": 100}]},
            daily=1)


def test_회계연도_해석범위_누락():
    with pytest.raises(LaborError, match="fy_clause_scope"):
        load_leave({"hire_date": "2019-01-01", "period_basis": "fiscal_year", "periods": []})


def test_회계연도_부여일수_누락():
    with pytest.raises(LaborError, match="granted_days"):
        run({"hire_date": "2019-01-01", "period_basis": "fiscal_year", "fy_clause_scope": "accrual_period",
             "periods": [{"scheduled_days": 250, "attended_days": 250}]}, daily=1)


def test_알수없는_사유와_키():
    with pytest.raises(LaborError, match="사유"):
        load_leave({"hire_date": "2019-01-01", "periods": [{"deemed": {"sick": 3}}]})
    with pytest.raises(LaborError, match="알 수 없는 키"):
        load_leave({"hire_date": "2019-01-01", "periods": [{"used": 3}]})


def test_산정기간_시작일_불일치():
    with pytest.raises(LaborError, match="맞지 않습니다"):
        run({"hire_date": "2019-01-01", "periods": [{"start": "2020-02-01", "granted_days": 15}]}, daily=1)


def test_출근일수_초과():
    with pytest.raises(LaborError, match="실질 소정근로일수"):
        run({"hire_date": "2015-01-01", "periods": [
            {"start": "2016-01-01", "scheduled_days": 250, "attended_days": 240, "deemed": {"maternity": 20}}]}, daily=1)


def test_통상임금_deps_누락():
    with pytest.raises(LaborError, match="daily_ordinary_of"):
        run({"hire_date": "2014-01-01", "periods": [{"start": "2016-01-01", "granted_days": 1}]}, worker={"pay_day": 25})


def test_정기지급일_누락():
    with pytest.raises(LaborError, match="pay_day"):
        run({"hire_date": "2014-01-01", "periods": [{"start": "2016-01-01", "granted_days": 1}]}, daily=1)


def test_잘못된_옵션():
    with pytest.raises(LaborError):
        resolve_options({"al_promotion_window": "before"}, OPTIONS)
    with pytest.raises(LaborError):
        calculate_leave(load_leave({"hire_date": "2019-01-01"}), {"al_final_rounding": "ceil"})


def test_약정_월액에_제수_누락():
    with pytest.raises(LaborError, match="monthly_divisor"):
        load_leave({"hire_date": "2019-01-01", "agreed_ordinary_wage": [{"from": "2019-01-01", "monthly": 3000000}]})
