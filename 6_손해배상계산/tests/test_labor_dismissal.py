"""해고기간 임금 상당액·중간수입 공제 (engine/labor/dismissal.py) 검증.

골든 예시는 조사 문서 dismissal_wage.md·interim_income.md 3절과 검증 메모·검증 판정의 판결 원문 숫자다.
판결문에 없는 사실(정기지급일, 청구 기간의 정확한 시작일, 별지에만 있는 월별 수입 등)을 테스트용으로 정한 경우
그 사실을 주석에 적었다. 금액 기대값은 판결 숫자이거나, assert 옆에 Decimal 식을 그대로 적은 값이다.
"""

import sys
from datetime import date
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.labor.common import LaborError, resolve_options  # noqa: E402
from engine.labor.dismissal import (  # noqa: E402
    OPTIONS,
    RULES,
    allocate_payment,
    calculate_dismissal,
    labor_commission_award_amount,
    load_dismissal,
)

D = Decimal
W25 = {"pay_day": 25}


def fl(x):
    return D(x).quantize(D(1), rounding=ROUND_DOWN)


def hu(x):
    return D(x).quantize(D(1), rounding=ROUND_HALF_UP)


def run(raw, worker=None, deps=None, **opt):
    inp = load_dismissal(raw, W25 if worker is None else worker)
    opts, _ = resolve_options(opt, OPTIONS)
    return calculate_dismissal(inp, opts, **(deps or {}))


def row(res, key, kind="dismissal"):
    return next(r for r in res.rows if r.key == key and r.kind == kind)


def by_year(res, year):
    return sum((r.pay_amount for r in res.rows if r.kind == "dismissal" and r.period_start.year == year), D(0))


def base(**kw):
    raw = {"claim_basis": "wage_538_invalid_dismissal", "invalidity_basis": "lsa_23"}
    raw.update(kw)
    return raw


# ================================================================ 모듈 규약
def test_옵션_키_접두어와_기본값():
    assert all(k.startswith(("dw_", "ii_")) for k in OPTIONS)
    values, _ = resolve_options({}, OPTIONS)
    assert values["ii_cap_base"] is None                 # II-04 기본값 없음(검증)
    assert values["ii_income_allocation"] is None        # 사용자가 정함
    assert values["ii_business_income_basis"] is None    # II-10c 확인불가
    assert values["ii_post_deemed_employment_cap"] is None
    assert values["dw_start_rule"] == "effective_date"   # DW-09 paid_through+1 기본값 폐기
    assert values["dw_expense_test"] == "requirement_linked"   # DW-04 검증
    assert values["dw_bonus_allocation"] == "annual_div_12"    # DW-14 지급월 배분은 확인불가
    assert values["ii_c_rounding_target"] == "limit"
    assert values["ii_apply_ordinary_wage_cap"] is False
    assert values["ii_exclude_non_avg_items_from_cap"] is False
    assert "관찰 빈도" in OPTIONS["ii_cap_base"].choices["C_contract_wage_ratio"]


def test_규칙_상태_어휘():
    allowed = {"판례확립", "법령", "행정해석", "하급심", "실무관행", "불명확"}
    for rid, (summary, status) in RULES.items():
        assert summary
        assert set(status.split("·")) <= allowed, rid
    for i in range(1, 22):
        assert f"DW-{i:02d}" in RULES
    for i in range(1, 16):
        assert f"II-{i:02d}" in RULES
    assert RULES["DW-08"][1] == "불명확" and RULES["II-04"][1] == "불명확"


# ================================================================ 중간수입 G-01 부산고법 2020나54503
def g01(**opt):
    return run(base(
        dismissal_date="2018-07-10", past_until="2019-08-31", future_start_date="2019-09-01",
        wage_items=[{"name": "월급", "category": "base", "monthly": 3520000}],
        interim_income=[
            # F 2019. 7. 8.~8. 5. 근무분을 7월분에, G 8. 12.~9. 1.을 8월분에 대응(판결)
            {"start": "2019-07-08", "end": "2019-08-05", "amount": 1702496, "type": "employment", "assigned_period": "2019-07"},
            {"start": "2019-08-12", "end": "2019-09-01", "amount": 1389233, "type": "employment", "assigned_period": "2019-08"},
            {"start": "2019-09-01", "monthly_amount": 2774340, "type": "employment"},
        ],
        interim_cap={"avg_daily_wage": 107491},
    ), deps={"small_business": lambda d: d >= date(2019, 6, 30)},
        dw_start_rule="next_day", ii_cap_base="A_daily_avg", **opt)


def test_G01_월별_한도_휴업수당_보장_4인이하_전환():
    res = g01()
    assert res.start_date == date(2018, 7, 11)
    assert row(res, "2018-07").pay == 2384516           # 3,520,000 × 21/31 버림
    assert sum(row(res, f"2018-{m:02d}").pay for m in range(8, 13)) + \
        sum(row(res, f"2019-{m:02d}").pay for m in range(1, 7)) == 38720000
    jul = row(res, "2019-07")
    assert jul.allowance == 2288662                      # 107,491 × 0.7 × 365/12 버림
    assert jul.pay == 2288662                            # 3,520,000 − 1,702,496 < 휴업수당 → 휴업수당액
    assert jul.small_business is None                    # 7월분까지 한도(시행령 제7조의2 전 1개월 판정)
    aug = row(res, "2019-08")
    assert aug.pay == 2130767 and aug.small_business     # 전액 공제
    assert res.total == 45523945
    assert sum(r.pay for r in res.rows if r.period_start <= date(2019, 4, 1)) == 34064516
    assert res.future_monthly_amount == 745660           # 2019. 9.부터 월 745,660원(전액 공제)


def test_G01_기준일_당일_판정이면_7월분도_전액공제():
    res = g01(ii_headcount_basis="reference_day")
    assert row(res, "2019-07").pay == D(3520000) - D(1702496)


# ================================================================ G-02 대전고법 2017나14978
def test_G02_해고전_3개월_월평균임금_70퍼센트():
    # 청구 45개월은 2013. 9.~2017. 5.로 정함. 2014. 8.·9. 중간수입은 별지에만 있어 검증 메모의 역산 합계 1,277,409원을
    # 638,704원·638,705원으로 나눠 넣고(각 월 한도 이하), 2014. 10.~2017. 5.는 한도를 넘는 월 1,000,000원으로 정함.
    res = run(base(
        start_date="2013-09-01", past_until="2017-05-31",
        wage_items=[{"name": "월급", "category": "base", "monthly": 2556000}],
        interim_income=[
            {"start": "2014-08-01", "end": "2014-08-31", "amount": 638704, "type": "employment"},
            {"start": "2014-09-01", "end": "2014-09-30", "amount": 638705, "type": "employment"},
            {"start": "2014-10-01", "end": "2017-05-31", "monthly_amount": 1000000, "type": "employment"},
        ],
        interim_cap={"avg_monthly_wage": 2413733},
    ), ii_cap_base="B_monthly_avg")
    oct14 = row(res, "2014-10")
    assert oct14.allowance == 1689613                    # 2,413,733 × 70% 버림
    assert oct14.deduction == 866387                     # 2,556,000 − 1,689,613
    assert res.interim_deduction_total == 29001793
    assert res.total == 86018207                         # 2,556,000 × 45 − 29,001,793


# ================================================================ G-03 서울중앙지법 2019나79130
def test_G03_입사일_기준_월단위_잔여일_일할_사용자_주장범위():
    # 청구 12개월은 2018. 10.~2019. 9.로 정함. 실제 수입은 9. 30.까지로 두고 사용자 주장 범위(1. 14.~9. 2.)만 공제되는지 본다.
    res = run(base(
        start_date="2018-10-01", past_until="2019-09-30",
        wage_items=[{"name": "월급", "category": "base", "monthly": 1600000}],
        interim_income=[{"start": "2019-01-14", "end": "2019-09-30", "monthly_amount": 1725860, "type": "employment"}],
        employer_claim_periods=[["2019-01-14", "2019-09-02"]],
    ), ii_cap_base="C_contract_wage_ratio", ii_period_anchor="income_start")
    assert row(res, "2019-02").deduction == 480000       # 1,600,000 × 30%
    assert row(res, "2019-09").deduction == 309677       # 480,000 × 20/31 버림
    assert res.interim_deduction_total == 3669677
    assert res.total == 15530323                         # 19,200,000 − 3,669,677
    assert any("사용자 주장 범위 밖" in w for w in res.warnings)


# ================================================================ G-04 서울고법 2021나2030052
def test_G04_30퍼센트_한도_수입액_자인에도_한도_적용():
    # 월별 수입은 1,500,000~2,000,000원(자인)이라 모두 한도(900,000원) 초과 — 1,500,000원으로 정함.
    res = run(base(
        dismissal_date="2018-06-05", past_until="2020-05-31",
        wage_items=[{"name": "월급", "category": "base", "monthly": 3000000}],
        interim_income=[{"start": "2019-03-01", "end": "2020-05-31", "monthly_amount": 1500000, "type": "employment",
                         "raised_by": "worker_admitted"}],
    ), dw_start_rule="next_day", ii_cap_base="C_contract_wage_ratio")
    assert row(res, "2019-03").limit == 900000
    assert sum(r.pay for r in res.rows if r.period_start < date(2019, 3, 1)) == 26500000   # 3,000,000 × 25/30 + × 8
    assert sum(r.pay for r in res.rows if r.period_start >= date(2019, 3, 1)) == 31500000  # 2,100,000 × 15
    assert res.total == 58000000
    assert res.future_start_date == date(2020, 6, 1) and res.future_monthly_amount == 3000000


# ================================================================ G-05 대전지법 2023가합203713
def g05(**opt):
    return run(base(
        start_date="2023-04-16", past_until="2024-04-15",
        wage_items=[{"name": "월급", "category": "base", "monthly": 2719539}],
        interim_income=[{"start": "2023-11-13", "end": "2023-12-31", "amount": 4449250, "type": "employment"}],
    ), ii_cap_base="C_contract_wage_ratio", ii_income_allocation="calendar_days", **opt)


def test_G05_중간수입_일수안분_한도창_끝수순서():
    res = g05()
    nov, dec_ = row(res, "2023-11"), row(res, "2023-12")
    assert nov.income == 1634418                         # 4,449,250 × 18/49 버림
    assert dec_.income == 2814831                        # 4,449,250 × 31/49 버림
    assert nov.limit == 489516                           # floor(floor(2,719,539 × 18/30) × 0.3)
    assert dec_.limit == 815861                          # floor(2,719,539 × 30%)
    assert nov.pay == 2230023 and dec_.pay == 1903678
    assert row(res, "2023-04").pay == 1359769            # 2,719,539 × 15/30 버림
    assert res.total == 31329090


def test_G05_임금기간_전체_한도창이면_판결과_불일치():
    res = g05(ii_cap_window="whole_wage_period")
    assert row(res, "2023-11").pay == 1903678            # 검증 메모: 조사자 산식 문자 적용 시 2,230,023원과 다름


def test_G05_안분_옵션_없으면_오류():
    with pytest.raises(LaborError, match="ii_income_allocation"):
        run(base(start_date="2023-04-16", past_until="2024-04-15",
                 wage_items=[{"name": "월급", "category": "base", "monthly": 2719539}],
                 interim_income=[{"start": "2023-11-13", "end": "2023-12-31", "amount": 4449250, "type": "employment"}]),
            ii_cap_base="C_contract_wage_ratio")


# ================================================================ G-06 광주지법 2017나58303
def test_G06_매월_평균임금_재산정_부당이득_청구액_제한():
    res = run(base(
        mode="refund", start_date="2013-01-01", reinstatement_date="2013-11-01", refund_claimed_amount=20847000,
        wage_items=[{"name": "월급", "category": "base", "monthly": 6949000}],
        interim_income=[{"start": "2013-01-01", "end": "2013-10-31", "amount": 32166660, "type": "employment"}],
        interim_cap={"pre_dismissal_wages": {"2012-10": 6711061, "2012-11": 6711061, "2012-12": 6711061}},  # 80,532,740 ÷ 12
    ), ii_cap_base="D_rolling_avg", ii_income_allocation="annual_equal_monthly")
    assert row(res, "2013-01").income == 2680555         # 32,166,660 ÷ 12 버림
    assert row(res, "2013-02").allowance == fl(D(6790374) * D("0.7"))   # 기초 (6,711,061 × 2 + 6,949,000) ÷ 3
    assert row(res, "2013-03").allowance == fl(D(6869687) * D("0.7"))   # 기초 (6,711,061 + 6,949,000 × 2) ÷ 3
    assert row(res, "2013-04").allowance == fl(D(6949000) * D("0.7"))
    assert res.refund_amount == 21180117
    assert res.refund_awardable == 20847000 and res.total == 20847000 and res.claims == []


def annual_case(incomes, **opt):
    return run(base(dismissal_date="2023-01-01", reinstatement_date="2024-07-01",
                    wage_items=[{"name": "기본급", "category": "base", "monthly": 3000000}], interim_income=incomes),
               ii_cap_base="C_contract_wage_ratio", ii_income_allocation="annual_equal_monthly", **opt)


def test_연간총액_12등분은_여러_기간에_걸친_총액에만():
    annual = {"start": "2023-01-01", "end": "2023-12-31", "amount": 12000000, "type": "employment"}
    res = annual_case([annual, {"start": "2024-03-01", "end": "2024-03-31", "amount": 600000, "type": "employment"}])
    assert row(res, "2023-05").income == 1000000 and row(res, "2023-05").deduction == 900000   # 한도 3,000,000 × 30%
    assert row(res, "2024-03").income == 600000 and row(res, "2024-03").deduction == 600000   # 한 달 수입은 ÷ 12 하지 않음
    assert not any("1년이 아닌데" in w for w in res.warnings)
    # 1년이 아닌 기간의 총액에 ÷ 12 를 쓰면 경고(연간 총액이 아니면 monthly_amount 로)
    res = annual_case([annual, {"start": "2024-03-01", "end": "2024-05-31", "amount": 1500000, "type": "employment"}])
    assert row(res, "2024-04").income == 125000
    assert any("중간수입[2]" in w and "1년이 아닌데" in w for w in res.warnings)
    assert not any("중간수입[1]" in w and "1년이 아닌데" in w for w in res.warnings)


# ================================================================ G-07 수원고법 2025나11545(반올림)
def test_G07_반올림_한도와_수입안분():
    # 11. 21.~12. 31. 수입은 판결 표가 이미지라 한도를 넘는 월 3,000,000원으로 정함.
    res = run({"claim_basis": "tort_suspension_pay_cut", "start_date": "2019-11-21", "past_until": "2020-01-17",
               "wage_items": [{"name": "급여", "category": "base", "monthly": 5833333}],
               "interim_income": [
                   {"start": "2019-11-21", "end": "2019-12-31", "monthly_amount": 3000000, "type": "employment"},
                   {"start": "2020-01-01", "end": "2020-01-31", "monthly_amount": 4554839, "type": "employment"}]},
              ii_cap_base="C_contract_wage_ratio", ii_rounding="half_up")
    assert row(res, "2019-12").limit == 1750000          # 5,833,333 × 0.3 반올림(버림이면 1,749,999)
    assert row(res, "2019-11").limit + row(res, "2019-12").limit == 2333333
    assert row(res, "2020-01").limit == 959677
    assert row(res, "2020-01").income == 2497815         # 4,554,839 × 17/31 반올림


# ================================================================ G-08·안산 2023가단88293
def test_G08_평균임금_30퍼센트_고정한도():
    # 월 임금 3,000,000원·수입 2,000,000원은 테스트용. 한도는 W 와 무관하게 883,213원.
    res = run(base(start_date="2020-01-01", past_until="2020-01-31",
                   wage_items=[{"name": "월급", "category": "base", "monthly": 3000000}],
                   interim_income=[{"start": "2020-01-01", "end": "2020-01-31", "amount": 2000000, "type": "employment"}],
                   interim_cap={"avg_monthly_wage": 2944045}),
              ii_cap_base="E_avg_wage_fixed_ratio")
    assert row(res, "2020-01").limit == 883213           # 2,944,045 × 30% 버림
    assert res.total == D(3000000) - D(883213)


def test_안산_2023가단88293_옵션C_4개월():
    res = run(base(start_date="2022-01-01", past_until="2022-04-30",
                   wage_items=[{"name": "월급", "category": "base", "monthly": 3500000}],
                   interim_income=[{"start": "2022-01-01", "end": "2022-04-30", "monthly_amount": 2000000, "type": "employment"}]),
              ii_cap_base="C_contract_wage_ratio")
    assert res.interim_deduction_total == 4200000        # 1,050,000 × 4


# ================================================================ 해고기간 G1 서울고법 2014나16809
def g1_raw(**kw):
    raw = base(
        dismissal_date="2009-12-21", reinstatement_date="2012-08-19",
        exclusions=[{"start": "2009-12-21", "end": "2010-03-20", "reason": "valid_suspension"}],
        wage_items=[{"name": "기본급", "category": "base", "history": {"total": 3560832, "months": 5}},
                    {"name": "제수당", "category": "fixed_allowance", "history": {"total": 3697218, "months": 5}}],
        payments=[{"date": "2013-01-14", "amount": 86671453}],
    )
    raw.update(kw)
    return raw


def test_G1_정상근무기간_월평균_소급정직_제외_급여기간_일할():
    res = run(g1_raw(), worker={"pay_day": 25, "pay_period_start_day": 19})
    first = res.rows[0]
    assert first.items == {"기본급": 712166, "제수당": 739443}    # 3,560,832 ÷ 5 버림, 3,697,218 ÷ 5 버림(반올림이면 739,444)
    assert first.label == "2010. 4.분" and first.start == date(2010, 3, 21) and first.end == date(2010, 4, 18)
    assert (first.covered_days, first.period_days) == (29, 31)
    assert first.wage == fl(D(1451609) * 29 / 31)
    assert first.pay_date == date(2010, 4, 25)
    assert res.rows[-1].end == date(2012, 8, 18)          # "복직일 전날인 2012. 8. 18.까지"
    assert res.deemed_attendance_periods == [(date(2010, 3, 21), date(2012, 8, 18))]
    assert res.continuous_service_periods == [(date(2009, 12, 21), date(2012, 8, 18))]
    # 원금 80,698,273 + 지연손해금 7,061,729 − 기지급 86,671,453, 지연손해금 먼저 충당
    assert allocate_payment(80698273, 7061729, 86671453)["remaining_principal"] == 1088549
    assert any("법정충당" in w for w in res.warnings)


def test_G1_지급월_상여_지급대상기간_일할():
    # 옵션 payment_month 의 산식 확인(지급률 100%로 단순화): 4월 상여 대상 2. 19.~4. 18. 59일 중 29일.
    raw = g1_raw(wage_items=[{"name": "기본급", "category": "base", "monthly": 712166},
                             {"name": "상여", "category": "regular_bonus", "monthly": 1607978,
                              "schedule": [{"month": 4, "rate": 1, "target_months": 2}]}])
    res = run(raw, worker={"pay_day": 25, "pay_period_start_day": 19}, dw_bonus_allocation="payment_month")
    assert res.rows[0].items["상여"] == fl(D(1607978) * 29 / 59)
    res2 = run(raw, worker={"pay_day": 25, "pay_period_start_day": 19})
    assert res2.rows[0].items["상여"] == fl(D(1607978) / 12)   # 기본 annual_div_12


# ================================================================ G2 창원지법 2018가합52160
def test_G2_원천징수후_금액_기준_원금과_충당():
    res = run(base(
        dismissal_date="2018-01-01", reinstatement_date="2018-04-24", withholding_rate="0.033",
        wage_items=[{"name": "약정 월급", "category": "base", "monthly": 7000000, "to": "2018-02-28"},
                    {"name": "약정 월급(3월~)", "category": "base", "monthly": 4000000, "from": "2018-03-01"}],
        payments=[{"date": "2018-07-02", "amount": 14350000, "basis": "net"}],
    ), worker={"pay_day": 10, "pay_month_offset": 1}, dw_amount_basis="net_of_withholding")
    assert row(res, "2018-04").wage == 3066666            # 4,000,000 × 23/30 버림
    assert res.total == 20371466
    assert [c.due_date for c in res.claims] == [date(2018, 2, 10), date(2018, 3, 10), date(2018, 4, 10), date(2018, 5, 10)]
    interest = fl(sum(c.amount * D("0.06") * (date(2018, 7, 2) - c.due_date).days / 365 for c in res.claims))
    assert interest == 363464                             # 판결 지연손해금(상사 6%) — 원금 항목과 지급기일 검증
    assert allocate_payment(res.total, interest, 14350000)["remaining_principal"] == 6384930


# ================================================================ G3 서울중앙지법 2023나15560
def test_G3_평균임금_일액과_복직포기일_종기():
    res = run(base(
        dismissal_date="2021-01-01", termination={"date": "2021-04-29", "cause": "waiver"},
        base_wage={"three_month_total": 10500000, "three_month_days": 92},
    ), dw_base_wage_method="avg_daily_3m")
    assert res.rows[0].items == {"평균임금 일액": 114130}   # 10,500,000 ÷ 92 버림
    assert sum(r.covered_days for r in res.rows) == 119
    assert res.total == 13581470                          # 114,130 × 119
    info = res.claim_info
    assert info.employment_status == "terminated" and info.termination_cause == "waiver"
    assert info.settlement_deadline == date(2021, 5, 13) and info.interest_end_cause == "other"
    assert not any(c.settlement for c in res.claims)      # 정기지급일 원금 — 종료 정보는 claim_info(interest DI-02 오독 방지)
    assert all(c.due_date.day == 25 for c in res.claims)
    assert res.future_monthly_amount is None


# ================================================================ G4 춘천지법 속초지원 2024가합30450
def g4(**opt):
    opt = {"ii_cap_base": "C_contract_wage_ratio", "ii_c_rounding_target": "pay",
           "ii_leave_allowance": "include_as_claimed", **opt}
    return run(base(
        dismissal_date="2020-02-01", closing_date="2024-09-12", past_until="2024-08-31", future_start_date="2024-09-01",
        wage_items=[
            {"name": "기본급", "category": "base", "monthly": 3115950},
            {"name": "고정수당", "category": "fixed_allowance", "monthly": 770600},
            {"name": "상여금", "category": "regular_bonus", "annual_rate": "1.5", "base_items": ["기본급"]},
            {"name": "연차수당18", "category": "leave_allowance", "monthly": 245520, "from": "2020-02-01", "to": "2021-12-31"},
            {"name": "연차수당19", "category": "leave_allowance", "monthly": 259160, "from": "2022-01-01", "to": "2023-12-31"},
            {"name": "연차수당20", "category": "leave_allowance", "monthly": 272800, "from": "2024-01-01"},
        ],
        interim_income=[{"start": "2020-12-01", "monthly_amount": 2600000, "type": "employment"}],
    ), **opt)


def test_G4_월평균_급여_공제후_월액_연도합_장래분():
    res = g4()
    feb = row(res, "2020-02")
    assert feb.items["상여금"] == 389493                  # 3,115,950 × 150% ÷ 12 버림(판결 문언은 반올림)
    assert feb.wage - feb.items["연차수당18"] == 4276043
    assert by_year(res, 2020) == 48380724
    assert by_year(res, 2021) == 37981128
    assert by_year(res, 2022) == 38095704 and by_year(res, 2023) == 38095704
    assert by_year(res, 2024) == 23945840                 # 2,993,230 × 8 — 끝나지 않은 2024년 연차 배척
    assert res.total == 186499100
    assert res.future_start_date == date(2024, 9, 1) and res.future_monthly_amount == 2993230
    assert res.claim_info.future_monthly_amount == 2993230


def test_G4_상여_반올림이면_1원_차이():
    res = g4(dw_bonus_monthly_rounding="half_up")
    feb = row(res, "2020-02")
    assert feb.wage - feb.items["연차수당18"] == 4276044


def test_G4_기본값이면_연차수당은_공제대상_아님():
    res = g4(ii_leave_allowance="exclude_from_deduction", ii_c_rounding_target="limit")
    dec20 = row(res, "2020-12")
    assert dec20.deduction == fl(D(4276043) * D("0.3"))
    assert dec20.pay == D(4276043) - fl(D(4276043) * D("0.3")) + 245520


# ================================================================ G5 대구지법 2020가합210338
def g5(**opt):
    return run(base(dismissal_date="2019-07-24", paid_through_date="2019-07-19", reinstatement_date="2020-11-25",
                    wage_items=[{"name": "약정 월급", "category": "base", "monthly": 5000000}]),
               dw_start_rule="next_day", **opt)


def test_G5_해고전_미지급_임금_구분():
    res = g5()
    pre = [r for r in res.rows if r.kind == "pre_dismissal"]
    assert len(pre) == 1 and pre[0].start == date(2019, 7, 20) and pre[0].end == date(2019, 7, 24)
    assert res.pre_dismissal_total == 806451              # 5,000,000 ÷ 31일 × 5일 버림
    assert res.start_date == date(2019, 7, 25) and res.end_date == date(2020, 11, 24)
    assert res.deemed_attendance_periods == [(date(2019, 7, 25), date(2020, 11, 24))]


def test_G5_해고기간_원단위_올림():
    res = g5(dw_proration_rounding="ceil10")
    assert res.dismissal_total == 80129040                # 1,129,040 + 5,000,000 × 15 + 4,000,000
    assert row(res, "2019-07").pay == 1129040


# ================================================================ 끝수·한도 기준 옵션 고정(판결 숫자가 없는 분기 — 산식으로)
def test_원단위_반올림_일할과_일액_소수_둘째자리():
    res = g5(dw_proration_rounding="round10_half_up")
    assert row(res, "2019-07").pay == 1129030            # 5,000,000 × 7/31 = 1,129,032.2… → 원 단위에서 반올림
    assert res.dismissal_total == 1129030 + 5000000 * 15 + 4000000
    res = run(base(dismissal_date="2021-01-01", termination={"date": "2021-04-29", "cause": "waiver"},
                   base_wage={"three_month_total": 10500000, "three_month_days": 92}),
              dw_base_wage_method="avg_daily_3m", dw_daily_rate_rounding="keep_2dp")
    assert res.rows[0].items == {"평균임금 일액": D("114130.43")}   # 10,500,000 ÷ 92 소수점 둘째 자리
    assert res.total == sum(fl(D("114130.43") * n) for n in (31, 28, 31, 29))


def test_월한도_먼저_끊고_일할_월중_일부():
    res = run(base(start_date="2024-07-01", past_until="2024-07-31",
                   wage_items=[{"name": "월급", "category": "base", "monthly": 2719539}],
                   interim_income=[{"start": "2024-07-13", "end": "2024-07-31", "amount": 2000000, "type": "employment"}]),
              ii_cap_base="C_contract_wage_ratio", ii_rounding_order="rate_first")
    jul = row(res, "2024-07")
    assert jul.limit == fl(fl(D(2719539) * D("0.3")) * 19 / 31)   # 월 한도 → 버림 → 19/31 일할 → 버림
    assert jul.deduction == jul.limit


def test_한도_W를_원천징수후_금액으로():
    res = run(base(start_date="2024-01-01", past_until="2024-01-31", withholding_rate="0.033",
                   wage_items=[{"name": "월급", "category": "base", "monthly": 3000000}],
                   interim_income=[{"start": "2024-01-01", "end": "2024-01-31", "amount": 2000000, "type": "employment"}]),
              ii_cap_base="C_contract_wage_ratio", ii_wage_basis_for_cap="net_of_withholding")
    limit = fl(fl(D(3000000) * (1 - D("0.033"))) * D("0.3"))      # floor(2,901,000 × 30%) = 870,300
    assert row(res, "2024-01").limit == limit and res.total == 3000000 - limit


# ================================================================ G6 수원지법 여주지원 2023가합11391
def test_G6_3개월평균_통상임금_하한과_중간수입_2개월14일():
    res = run(base(
        dismissal_date="2023-07-31", closing_date="2024-11-27", past_until="2024-08-31", future_start_date="2024-09-01",
        base_wage={"three_month_total": D(5060800) + D(3870990) + D(744213), "ordinary_monthly_wage": 4400000},
        interim_income=[{"start": "2024-04-15", "end": "2024-06-28", "amount": 11795000, "type": "employment"}],
    ), dw_start_rule="next_day", dw_base_wage_method="avg_monthly_3m_ordinary_floor", dw_proration="fixed_30",
        ii_cap_base="C_contract_wage_ratio", ii_period_anchor="income_start", ii_rounding_order="rate_first",
        ii_income_allocation="calendar_days")
    assert res.rows[0].items == {"기준 월임금": 4400000}   # 3,225,334 < 4,400,000
    assert res.wage_total == 57200000
    assert res.interim_deduction_total == 3256000        # 1,320,000 × (2 + 14/30)
    assert res.total == 53944000
    assert res.total - 31163149 == 22780851              # 판결은 기지급액을 원금에서 뺌
    assert res.future_monthly_amount == 4400000


# ================================================================ G7 창원지법 통영지원 2014가단5110
def test_G7_30일_고정_일할():
    # 해고기간은 판결에 날짜가 없어 31일 달에 27일이 걸리도록 2014. 2. 1.~5. 27.로 정함.
    res = run(base(start_date="2014-02-01", past_until="2014-05-27",
                   wage_items=[{"name": "월평균 추가수입", "category": "base", "monthly": 946500}]),
              dw_proration="fixed_30")
    assert res.total == 3691350                           # 946,500 × (3 + 27/30)
    res2 = run(base(start_date="2014-03-01", past_until="2014-03-28",
                    wage_items=[{"name": "월평균 추가수입", "category": "base", "monthly": 946500}]),
               dw_proration="fixed_30")
    assert res2.total == 883400                           # 946,500 × 28/30


# ================================================================ G8 행정심판 2022-09280
def test_G8_노동위원회_금전보상():
    assert labor_commission_award_amount(D(3000000), date(2020, 11, 1), date(2020, 12, 17)) == (98630, 77, 7594510)
    res = run({"mode": "labor_commission_award", "start_date": "2020-11-01",
               "labor_commission": {"monthly_wage": 3000000, "decision_date": "2020-12-17", "service_days": 30}})
    assert res.total == 7594510 and res.labor_commission_amount == 7594510
    with pytest.raises(LaborError, match="구제신청"):
        run({"mode": "labor_commission_award", "start_date": "2020-11-01", "small_business": True,
             "labor_commission": {"monthly_wage": 3000000, "decision_date": "2020-12-17"}})


def test_송달일수_빈칸은_30일_형식이_틀리면_입력_오류():
    lc = {"monthly_wage": 3000000, "decision_date": "2020-12-17"}
    res = run({"mode": "labor_commission_award", "start_date": "2020-11-01", "labor_commission": {**lc, "service_days": None}})
    assert res.total == 7594510                            # 비우면 30일(G8 과 같음)
    for bad in ("30일", -1, 1.5, True):
        with pytest.raises(LaborError, match="service_days"):
            load_dismissal({"mode": "labor_commission_award", "start_date": "2020-11-01",
                            "labor_commission": {**lc, "service_days": bad}}, W25)


# ================================================================ G9 대법원 93다21736 원심(파기)
def test_G9_직전1개월_고정과_인상_미반영_경고():
    res = run(base(dismissal_date="1990-03-01", past_until="1990-03-31",
                   wage_items=[{"name": "기본급", "category": "base", "monthly": 224600},
                               {"name": "상여금", "category": "regular_bonus", "annual_rate": 5, "base_items": ["기본급"]},
                               {"name": "활동비", "category": "fixed_allowance", "monthly": 80000},
                               {"name": "징수수당", "category": "fixed_allowance", "monthly": 80780}],
                   raises=[{"applies_from": "1990-01-01", "amount": 30000, "items": ["기본급"]}]),
              dw_base_wage_method="last_month")
    assert res.rows[0].items["상여금"] == 93583           # 224,600 × 500% ÷ 12 버림
    assert res.total == 478963
    assert any("93다21736" in w for w in res.warnings)
    res2 = run(base(dismissal_date="1990-03-01", past_until="1990-03-31",
                    wage_items=[{"name": "기본급", "category": "base", "monthly": 224600}],
                    raises=[{"applies_from": "1990-01-01", "amount": 30000, "items": ["기본급"]}]))
    assert res2.total == 254600                            # items 방식은 소급 인상 반영: 224,600 + 30,000


# ================================================================ G11 수원지법 2019나58100(누적 인상 반올림)
def test_G11_평가연동_누적_인상_반올림():
    # 연봉을 월 항목 금액으로 넣어 누적 방식만 확인한다.
    res = run(base(start_date="2013-01-01", past_until="2016-01-31",
                   wage_items=[{"name": "연봉", "category": "base", "monthly": 27788260}],
                   raises=[{"applies_from": "2013-01-01", "rate": "-0.005", "kind": "evaluation"},
                           {"applies_from": "2014-01-01", "rate": "0.024", "kind": "evaluation"},
                           {"applies_from": "2015-01-01", "rate": "0.024", "kind": "evaluation"},
                           {"applies_from": "2016-01-01", "rate": "0.024", "kind": "evaluation"}]))
    vals = [row(res, f"{y}-01").items["연봉"] for y in (2013, 2014, 2015, 2016)]
    assert vals == [27649319, 28312903, 28992413, 29688231]
    assert sum(v - vals[0] for v in vals[1:]) == 4045590
    assert any("적정한 등급" in w for w in res.warnings)


# ================================================================ 경계
def test_1989년_3월_29일_60퍼센트에서_70퍼센트로_일단위_분할():
    res = run(base(start_date="1989-03-01", past_until="1989-03-31",
                   wage_items=[{"name": "월급", "category": "base", "monthly": 310000}],
                   interim_income=[{"start": "1989-03-01", "end": "1989-03-31", "monthly_amount": 300000, "type": "employment"}]),
              ii_cap_base="C_contract_wage_ratio")
    # floor(floor(310,000 × 28/31) × 0.4) + floor(floor(310,000 × 3/31) × 0.3)
    assert row(res, "1989-03").deduction == fl(fl(D(310000) * 28 / 31) * D("0.4")) + fl(fl(D(310000) * 3 / 31) * D("0.3"))


def test_월중도_해고와_복직_일할():
    res = run(base(dismissal_date="2024-01-10", reinstatement_date="2024-03-16",
                   wage_items=[{"name": "월급", "category": "base", "monthly": 3100000}]))
    assert row(res, "2024-01").covered_days == 22 and row(res, "2024-01").pay == fl(D(3100000) * 22 / 31)
    assert row(res, "2024-02").pay == 3100000
    assert row(res, "2024-03").covered_days == 15 and row(res, "2024-03").pay == fl(D(3100000) * 15 / 31)
    assert res.claim_info.employment_status == "reinstated" and res.future_monthly_amount is None
    assert [c.due_date for c in res.claims] == [date(2024, 1, 25), date(2024, 2, 25), date(2024, 3, 25)]


def test_5인미만_사업장은_한도없이_전액공제():
    raw = {"claim_basis": "wage_538_invalid_dismissal", "invalidity_basis": "cba_rules", "small_business": True,
           "start_date": "2024-01-01", "past_until": "2024-01-31",
           "wage_items": [{"name": "월급", "category": "base", "monthly": 3000000}],
           "interim_income": [{"start": "2024-01-01", "end": "2024-01-31", "amount": 2500000, "type": "employment"}]}
    res = run(raw)                                          # ii_cap_base 없어도 한도 계산이 없으므로 오류 아님
    assert res.total == 500000 and row(res, "2024-01").small_business
    # 조립 모듈이 worker 기준 deps(항상 False)를 넘겨도 dismissal.small_business 가 살아 있어야 한다
    assert run(raw, deps={"small_business": lambda d: False}).total == 500000
    assert any("상시 4명 이하" in w for w in res.warnings)
    with pytest.raises(LaborError, match="제23조"):
        run(dict(raw, invalidity_basis="lsa_23"))


def test_중간수입이_한도_미달이면_전액_공제_초과면_한도():
    def base_raw(income):
        return base(start_date="2024-01-01", past_until="2024-01-31",
                    wage_items=[{"name": "월급", "category": "base", "monthly": 3000000}],
                    interim_cap={"avg_monthly_wage": 3000000},
                    interim_income=[{"start": "2024-01-01", "end": "2024-01-31", "amount": income, "type": "employment"}])
    small = run(base_raw(500000), ii_cap_base="B_monthly_avg")
    assert small.total == D(3000000) - D(500000)          # 수입 < 휴업수당이어도 공제 0 이 아님(2014다65397)
    big = run(base_raw(2000000), ii_cap_base="B_monthly_avg")
    assert big.total == fl(D(3000000) * D("0.7"))         # 한도 = 3,000,000 − floor(3,000,000 × 0.7)


def test_임금이_휴업수당_미달이면_공제_없음():
    res = run(base(start_date="2024-01-01", past_until="2024-01-31",
                   wage_items=[{"name": "월급", "category": "base", "monthly": 2000000}],
                   interim_cap={"avg_monthly_wage": 3000000},
                   interim_income=[{"start": "2024-01-01", "end": "2024-01-31", "amount": 2000000, "type": "employment"}]),
              ii_cap_base="B_monthly_avg")
    assert res.total == 2000000                            # 90다18999 — 공제 여지 없음, 휴업수당까지 끌어올리지 않음


def test_기간_대응_밖_수입과_공제대상_아닌_수입은_무시():
    res = run(base(start_date="2024-01-01", past_until="2024-02-29",
                   wage_items=[{"name": "월급", "category": "base", "monthly": 3000000}],
                   interim_income=[
                       {"start": "2023-11-01", "end": "2023-12-31", "amount": 9000000, "type": "employment"},
                       {"start": "2024-01-01", "end": "2024-02-29", "monthly_amount": 1500000, "type": "unemployment_benefit"},
                       {"start": "2024-01-01", "end": "2024-02-29", "monthly_amount": 1500000, "type": "union_fund"},
                       {"start": "2024-01-01", "end": "2024-02-29", "monthly_amount": 1500000, "type": "side_job"},
                       {"start": "2024-01-01", "end": "2024-02-29", "monthly_amount": 1500000, "type": "employment",
                        "raised_by": "none"}]),
              ii_cap_base="C_contract_wage_ratio", ii_income_allocation="calendar_days")
    assert res.total == 6000000 and res.interim_deduction_total == 0
    assert len(res.ignored_income) == 5


def test_한도없는_공제_자인과_한도없는_청구원인():
    raw = base(start_date="2024-01-01", past_until="2024-01-31",
               wage_items=[{"name": "월급", "category": "base", "monthly": 3000000}],
               interim_income=[{"start": "2024-01-01", "end": "2024-01-31", "amount": 2500000, "type": "employment",
                                "raised_by": "worker_admitted", "admitted_without_cap": True}])
    assert run(raw, ii_cap_base="C_contract_wage_ratio").total == 500000
    raw2 = dict(raw, interim_income=[{"start": "2024-01-01", "end": "2024-01-31", "amount": 2500000, "type": "employment"}])
    assert run(raw2, ii_cap_base="C_contract_wage_ratio").total == D(3000000) - fl(D(3000000) * D("0.3"))
    for basis in ("damages_after_relationship_terminated", "damages_direct_hire_duty", "wage_invalid_transfer"):
        assert run(dict(raw2, claim_basis=basis)).total == 500000, basis   # 91다44100, 2015다232859, 2013다45075


def test_고용_의사표시_확정일_전후_분할():
    raw = {"claim_basis": "damages_employment_succession_duty", "start_date": "2016-08-01", "past_until": "2016-08-31",
           "employment_deemed_date": "2016-08-23",
           "wage_items": [{"name": "월급", "category": "base", "monthly": 3100000}],
           "interim_income": [{"start": "2016-08-01", "end": "2016-08-31", "monthly_amount": 3100000, "type": "employment"}]}
    with pytest.raises(LaborError, match="ii_post_deemed_employment_cap"):
        run(raw, ii_cap_base="C_contract_wage_ratio")
    res = run(dict(raw, claim_basis="wage_538_invalid_dismissal"), ii_cap_base="C_contract_wage_ratio",
              ii_post_deemed_employment_cap="apply")
    # 8. 1.~22. 손해배상(전액) + 8. 23.~31. 임금(30% 한도)
    assert row(res, "2016-08").deduction == fl(D(3100000) * 22 / 31) + fl(fl(D(3100000) * 9 / 31) * D("0.3"))


def test_A옵션_평균임금_통상임금_하한():
    res = run(base(dismissal_date="2024-01-01", past_until="2024-01-31",
                   wage_items=[{"name": "월급", "category": "base", "monthly": 3000000}],
                   interim_cap={"avg_daily_wage": 80000},
                   interim_income=[{"start": "2024-01-01", "end": "2024-01-31", "amount": 3000000, "type": "employment"}]),
              deps={"daily_ordinary_of": lambda d: D(90000)}, ii_cap_base="A_daily_avg")
    assert row(res, "2024-01").allowance == fl(D(90000) * D("0.7") * 365 / 12)


def test_통상임금_단서는_1997년_3월_전_기간에_못씀():
    raw = base(start_date="1996-01-01", past_until="1996-01-31",
               wage_items=[{"name": "월급", "category": "base", "monthly": 1000000}],
               interim_cap={"avg_monthly_wage": 1000000, "ordinary_monthly_wage": 600000},
               interim_income=[{"start": "1996-01-01", "end": "1996-01-31", "amount": 900000, "type": "employment"}])
    with pytest.raises(LaborError, match="1997"):
        run(raw, ii_cap_base="B_monthly_avg", ii_apply_ordinary_wage_cap=True)
    raw2 = dict(raw, start_date="2024-01-01", past_until="2024-01-31",
                interim_income=[{"start": "2024-01-01", "end": "2024-01-31", "amount": 900000, "type": "employment"}])
    res = run(raw2, ii_cap_base="B_monthly_avg", ii_apply_ordinary_wage_cap=True)
    assert row(res, "2024-01").allowance == 600000         # min(1,000,000 × 0.7, 600,000)


def test_평균임금_비산입_임금은_한도없이_공제_옵션():
    raw = base(start_date="2024-01-01", past_until="2024-01-31",
               wage_items=[{"name": "월급", "category": "base", "monthly": 3000000},
                           {"name": "특별상여", "category": "regular_bonus", "monthly": 1000000, "in_average_wage": False}],
               interim_income=[{"start": "2024-01-01", "end": "2024-01-31", "amount": 5000000, "type": "employment"}])
    assert run(raw, ii_cap_base="C_contract_wage_ratio").rows[0].deduction == fl(D(4000000) * D("0.3"))
    assert run(raw, ii_cap_base="C_contract_wage_ratio", ii_exclude_non_avg_items_from_cap=True).rows[0].deduction == \
        fl(D(3000000) * D("0.3")) + 1000000


def test_제외기간_구속과_출근간주():
    res = run(base(dismissal_date="2024-01-01", reinstatement_date="2024-04-01",
                   exclusions=[{"start": "2024-02-01", "end": "2024-02-29", "reason": "detention"}],
                   wage_items=[{"name": "월급", "category": "base", "monthly": 3000000}]))
    assert [r.key for r in res.rows] == ["2024-01", "2024-03"] and res.total == 6000000
    assert res.deemed_attendance_periods == [(date(2024, 1, 1), date(2024, 1, 31)), (date(2024, 3, 1), date(2024, 3, 31))]
    assert res.continuous_service_periods == [(date(2024, 1, 1), date(2024, 3, 31))]
    assert any("94다40987" in w for w in res.warnings)


def test_복직명령_불응_종기와_갱신기대권():
    raw = base(dismissal_date="2024-01-01", closing_date="2024-12-31",
               return_order={"effective_date": "2024-03-01", "genuine": True, "refused": True},
               wage_items=[{"name": "월급", "category": "base", "monthly": 3000000}])
    res = run(raw)
    assert res.end_date == date(2024, 2, 29) and res.total == 6000000
    assert run(raw, dw_return_order_end="ignore").past_end == date(2024, 12, 31)
    res2 = run(base(dismissal_date="2024-01-01", termination={"date": "2024-02-29", "cause": "contract_end"},
                    renewal_expectation=True, renewed_term_end="2024-05-31",
                    wage_items=[{"name": "월급", "category": "base", "monthly": 3000000}]))
    assert res2.end_date == date(2024, 5, 31) and res2.total == 15000000


def renewal_case(**dismissal):
    raw = base(start_date="2023-01-01", termination={"date": "2022-12-31", "cause": "contract_end"},
               renewal_expectation=True, closing_date="2025-05-01",
               wage_items=[{"name": "기본급", "category": "base", "monthly": 3000000}])
    raw.update(dismissal)
    return raw


def test_갱신기대권이면_갱신간주_만료일이_근로관계_종료일():
    # 원래 계약만료일(2022. 12. 31.)이 아니라 갱신 간주된 계약기간 만료일에 근로관계가 끝난다(DW-10·DW-18, 2007두1729)
    res = run(renewal_case(renewed_term_end="2024-12-31"))
    info = res.claim_info
    assert res.end_date == date(2024, 12, 31) and len(res.claims) == 24
    assert (info.employment_status, info.termination_date, info.settlement_deadline, info.interest_end_cause) == \
        ("terminated", date(2024, 12, 31), date(2025, 1, 14), "contract_end")
    assert all(i.before_termination for i in info.installments)           # 정기지급일 2024. 12. 25.까지 모두 종료 전
    assert "원래 계약만료일 2022. 12. 31." in res.claims[0].note and "2025. 1. 14." in res.claims[0].note
    assert any("2007두1729" in n for n in info.notes)
    # 갱신 간주 만료일이 없으면 근로관계 계속 — 지연손해금 모듈에 종료일을 넘기지 않는다
    res = run(renewal_case())
    info = res.claim_info
    assert res.end_date is None and res.future_monthly_amount == 3000000
    assert (info.employment_status, info.termination_date, info.settlement_deadline, info.interest_end_cause) == \
        ("continuing", None, None, None)
    assert all(i.before_termination is None for i in info.installments)


def test_갱신기대권_해고기간_임금의_지연손해금_20_기산일():
    from engine.labor.calculate import calculate_labor, load_labor_case

    def interest_of(dismissal):
        case = {"kind": "labor", "worker": {"hire_date": "2021-01-01", "employer_merchant": True, "pay_day": 25},
                "dismissal": dismissal, "interest": {"calc_until": "2025-06-30"},
                "options": {"di_exclusion_end": "none"}}
        return calculate_labor(load_labor_case(case)).parts["interest"]

    it = interest_of(renewal_case(renewed_term_end="2024-12-31"))
    # 구법 도래분: 정기지급일 다음 날부터 6%, 근로관계 종료(2024. 12. 31.) + 15일부터 20%(DI-03)
    assert [(s.start, s.rate) for s in it.schedules[0].segments] == [(date(2023, 1, 26), D(6)), (date(2025, 1, 15), D(20))]
    assert [(s.start, s.rate) for s in it.schedules[-1].segments] == [(date(2024, 12, 26), D(6)), (date(2025, 1, 15), D(20))]
    assert it.total == 10967792                            # 원래 계약만료일을 종료일로 보면 21,185,748원(20% 과다)
    it = interest_of(renewal_case())
    assert {s.rate for sch in it.schedules for s in sch.segments} == {D(6)}   # 재직 중 구법분 — 20% 없음(2014다28305)


def test_worker_마지막근무일이_근로관계_종료일보다_앞서면_경고():
    res = run(renewal_case(renewed_term_end="2024-12-31"), worker={"pay_day": 25, "last_working_day": "2022-12-31"})
    assert any("worker.last_working_day 2022. 12. 31." in w and "2024. 12. 31. 보다 앞섭니다" in w and "DI-03" in w
               for w in res.warnings)
    res = run(renewal_case(), worker={"pay_day": 25, "last_working_day": "2022-12-31"})
    assert any("worker.last_working_day 2022. 12. 31." in w and "계속되는 것으로" in w for w in res.warnings)
    res = run(renewal_case(renewed_term_end="2024-12-31"), worker={"pay_day": 25, "last_working_day": "2024-12-31"})
    assert not any("worker.last_working_day" in w for w in res.warnings)


def test_실비변상_성과급_시간외수당_포함_판단():
    raw = base(start_date="2024-01-01", past_until="2024-01-31", small_business=False, wage_items=[
        {"name": "월급", "category": "base", "monthly": 3000000},
        {"name": "자가운전보조금", "category": "expense", "monthly": 200000},
        {"name": "식대", "category": "expense", "monthly": 100000, "requirement_linked": False},
        {"name": "특별보로금", "category": "discretionary", "monthly": 500000},
        {"name": "성과급", "category": "performance_bonus", "annual": 1200000, "rule_basis": True},
        {"name": "가끔 연장", "category": "overtime", "overtime": {"amount": 300000}},
        {"name": "상시 연장", "category": "overtime", "regular": True,
         "overtime": {"method": "peer_avg_hours", "hourly_wage": 10000, "hours": {"overtime": 10}}},
    ])
    res = run(raw)
    assert res.rows[0].items == {"월급": 3000000, "식대": 100000, "성과급": 100000, "상시 연장": 150000}  # 10 × 10,000 × 1.5
    assert any("94다25889" in w for w in res.warnings)
    res2 = run(raw, dw_expense_test="uniform_payment")
    assert "자가운전보조금" not in res2.rows[0].items and "식대" not in res2.rows[0].items


def test_재량_승진_제외_자동승급_반영():
    res = run(base(start_date="2024-01-01", past_until="2024-01-31",
                   wage_items=[{"name": "기본급", "category": "base", "monthly": 2000000}],
                   raises=[{"applies_from": "2024-01-01", "amount": 16500, "kind": "automatic_step"},
                           {"applies_from": "2024-01-01", "amount": 300000, "kind": "promotion"}]))
    assert res.total == 2016500
    assert any("94다446" in w for w in res.warnings)


def test_연차수당_5인미만과_출근간주():
    res = run({"claim_basis": "wage_538_invalid_dismissal", "invalidity_basis": "cba_rules", "small_business": True,
               "start_date": "2024-01-01", "past_until": "2024-01-31",
               "wage_items": [{"name": "월급", "category": "base", "monthly": 3000000},
                              {"name": "연차수당", "category": "leave_allowance", "monthly": 200000}]})
    assert res.total == 3000000
    assert any("제60조" in w for w in res.warnings)


def test_장래분_시작일과_끝나지않은_중간수입():
    res = run(base(dismissal_date="2024-01-01", closing_date="2024-03-20",
                   wage_items=[{"name": "월급", "category": "base", "monthly": 3000000}],
                   interim_income=[{"start": "2024-02-01", "monthly_amount": 2000000, "type": "employment"}]),
              ii_cap_base="C_contract_wage_ratio")
    assert res.past_end == date(2024, 3, 20)
    assert res.future_start_date == date(2024, 3, 21)
    assert res.future_monthly_amount == D(3000000) - fl(D(3000000) * D("0.3"))
    assert any("임금산정기간 시작일이 아닙니다" in w for w in res.warnings)
    assert res.claim_info.employment_status == "continuing"
    res2 = run(base(dismissal_date="2024-01-01", closing_date="2024-03-20",
                    wage_items=[{"name": "월급", "category": "base", "monthly": 3000000}],
                    interim_income=[{"start": "2024-02-01", "monthly_amount": 2000000, "type": "employment"}]),
               ii_cap_base="C_contract_wage_ratio", dw_future_interim="none")
    assert res2.future_monthly_amount == 3000000


def test_사업소득_기준은_사람이_정함():
    raw = base(start_date="2024-01-01", past_until="2024-01-31",
               wage_items=[{"name": "월급", "category": "base", "monthly": 3000000}],
               interim_income=[{"start": "2024-01-01", "end": "2024-01-31", "amount": 1000000, "type": "business",
                                "business_expenses": 700000}])
    with pytest.raises(LaborError, match="ii_business_income_basis"):
        run(raw, ii_cap_base="C_contract_wage_ratio")
    res = run(raw, ii_cap_base="C_contract_wage_ratio", ii_business_income_basis="net_of_expenses")
    assert res.interim_deduction_total == 300000


# ================================================================ 금지 산식·입력 누락
def test_금지_산식_입력_거부():
    with pytest.raises(LaborError, match="2021다279903"):
        load_dismissal(base(dismissal_date="2024-01-01", deduction_formula="income_minus_allowance"), W25)
    with pytest.raises(LaborError, match="2014다65397"):
        load_dismissal(base(dismissal_date="2024-01-01", deduction_formula="zero_if_income_below_allowance"), W25)


def test_입력_누락_오류():
    with pytest.raises(LaborError, match="claim_basis"):
        load_dismissal({"dismissal_date": "2024-01-01"}, W25)
    with pytest.raises(LaborError, match="dismissal_date"):
        load_dismissal({"claim_basis": "wage_538_invalid_dismissal"}, W25)
    with pytest.raises(LaborError, match="pay_day"):
        run(base(dismissal_date="2024-01-01", past_until="2024-01-31",
                 wage_items=[{"name": "월급", "monthly": 1}]), worker={})
    with pytest.raises(LaborError, match="past_until"):
        run(base(dismissal_date="2024-01-01", wage_items=[{"name": "월급", "monthly": 1}]))
    with pytest.raises(LaborError, match="wage_items"):
        run(base(dismissal_date="2024-01-01", past_until="2024-01-31"))
    with pytest.raises(LaborError, match="ii_cap_base"):
        run(base(dismissal_date="2024-01-01", past_until="2024-01-31", wage_items=[{"name": "월급", "monthly": 3000000}],
                 interim_income=[{"start": "2024-01-01", "end": "2024-01-31", "amount": 1, "type": "employment"}]))
    with pytest.raises(LaborError, match="include"):
        run(base(dismissal_date="2024-01-01", past_until="2024-01-31",
                 wage_items=[{"name": "학자금", "category": "child_education", "monthly": 100000}]))
    with pytest.raises(LaborError, match="applies_from"):
        load_dismissal(base(dismissal_date="2024-01-01", wage_items=[{"name": "월급", "monthly": 1}],
                            raises=[{"amount": 1000}]), W25)
    with pytest.raises(LaborError, match="알 수 없는 키"):
        load_dismissal(base(dismissal_date="2024-01-01", foo=1), W25)
    with pytest.raises(LaborError, match="type"):
        load_dismissal(base(dismissal_date="2024-01-01", interim_income=[{"start": "2024-01-01", "amount": 1, "end": "2024-01-31"}]), W25)
    with pytest.raises(LaborError, match="admitted_without_cap"):
        load_dismissal(base(dismissal_date="2024-01-01", interim_income=[
            {"start": "2024-01-01", "end": "2024-01-31", "amount": 1, "type": "employment", "admitted_without_cap": True}]), W25)
    with pytest.raises(LaborError, match="withholding_rate"):
        run(base(dismissal_date="2024-01-01", past_until="2024-01-31", wage_items=[{"name": "월급", "monthly": 1}]),
            dw_amount_basis="net_of_withholding")
    with pytest.raises(LaborError, match="하나만"):
        load_dismissal(base(dismissal_date="2024-01-01", wage_items=[{"name": "월급", "monthly": 1, "annual": 12}]), W25)
    with pytest.raises(LaborError, match="시작과 끝"):
        load_dismissal(base(dismissal_date="2024-01-01", employer_claim_periods=[["2024-09-01", None]]), W25)
    with pytest.raises(LaborError, match="앞섭니다"):
        load_dismissal(base(dismissal_date="2024-01-01", employer_claim_periods=[["2024-09-01", "2024-08-01"]]), W25)
