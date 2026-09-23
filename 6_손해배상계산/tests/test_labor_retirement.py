"""법정 퇴직금·차액 (engine/labor/retirement.py) 검증.

골든 예시는 조사 문서 average_wage_severance.md 3절과 검증 메모의 판결 원문 숫자다.
판결문에 없는 사실(입사일 등)을 테스트용으로 정한 경우 그 사실을 주석에 적었다.
금액 기대값은 판결 숫자이거나, assert 옆에 Decimal 식을 그대로 적은 값이다.
"""

import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.labor.common import LaborError, resolve_options, round_to  # noqa: E402
from engine.labor.retirement import (  # noqa: E402
    OPTIONS,
    RULES,
    calculate_retirement,
    load_retirement,
    one_year_expiry,
    years_and_days,
)

D = Decimal


def run(raw, worker=None, avg=None, monthly=None, **opt):
    inp = load_retirement(raw, worker)
    opts, _ = resolve_options(opt, OPTIONS)
    deps = {}
    if avg is not None:
        deps["average_daily_wage"] = avg if callable(avg) else D(avg)
    if monthly is not None:
        deps["monthly_wage_base"] = monthly
    return calculate_retirement(inp, opts, **deps)


def floor(x):
    return round_to(x, 0, "floor")


# ================================================================ 모듈 규약
def test_옵션_키_접두어와_기본값():
    assert all(k.startswith("rs_") for k in OPTIONS)
    values, _ = resolve_options({}, OPTIONS)
    assert values["rs_service_ratio_mode"] == "total_days"
    assert values["rs_round_severance"] == "won_floor"
    assert values["rs_round_ratio"] == "none"
    assert values["rs_due_date"] == "statutory_14"
    assert values["rs_part_rounding"] == "per_part"


def test_규칙_상태_어휘():
    allowed = {"판례확립", "법령", "행정해석", "하급심", "실무관행", "불명확"}
    for rid, (summary, status) in RULES.items():
        assert summary
        assert set(status.split("·")) <= allowed, rid
    assert RULES["RS-07"][1] == "판례확립·행정해석"
    for m in ("MR-1", "MR-2", "MR-3"):
        assert m in RULES


# ================================================================ 골든 G3 부산지방법원 2020나52559
def test_G3_주15시간_미만_구간_제외_1064일_퇴직일_다음날_기산():
    raw = {"hire_date": "2016-02-15", "last_working_day": "2019-09-10",
           "excluded_periods": [{"reason": "short_hours", "start": "2019-01-14", "end": "2019-09-10"}]}
    res = run(raw, avg=34666, rs_due_date="day_after_retirement")
    part = [r for r in res.rows if r.kind == "part"][0]
    assert part.counted_days == 1064                       # "2016. 2. 15.부터 2019. 1. 13.까지 총 1,064일"
    assert res.final_severance == 3031612                  # "34,666원 × 30일 × 1,064일/365일, 원 미만 버림"
    [claim] = res.claims
    assert claim.amount == 3031612 and claim.settlement
    assert claim.due_date + timedelta(days=1) == date(2019, 9, 11)   # "퇴직일 다음 날인 2019. 9. 11.부터"
    assert any("2003도5169" in w for w in res.warnings)


def test_주15시간_whole_if_last():
    raw = {"hire_date": "2016-02-15", "last_working_day": "2019-09-10",
           "excluded_periods": [{"reason": "short_hours", "start": "2019-01-14", "end": "2019-09-10"}]}
    res = run(raw, avg=34666, rs_hours15_basis="whole_if_last")
    assert not res.eligible and res.total == 0 and res.claims == []


# ================================================================ 골든 G4 수원지방법원 2018가소24967
G4 = {"hire_date": "2002-01-02",       # 입사일은 판결에 없어 정함
      "last_working_day": "2015-06-30", "paid_severance": 19776480,
      "interim_settlements": [{"date": "2012-07-18", "valid": True}]}


def test_G4_지급률_2_950_10원_버림_차액_1509790():
    res = run(G4, avg="240522.85", rs_service_ratio_mode="years_plus_days", rs_round_ratio="3dp_floor",
              rs_round_severance="ten_won_floor")
    part = [r for r in res.rows if r.kind == "part" and r.segment_no == 2][0]
    assert (part.start, part.calendar_days, part.years, part.remaining_days) == (date(2012, 7, 19), 1077, 2, 347)
    assert part.ratio == D("2.950")                        # "2년 + 347일/365일, 소수점 셋째자리 미만 버림"
    assert res.final_severance == 21286270                 # "240,522.85원 × 2.950 × 30일, 10원 미만 버림"
    assert res.final_diff == 1509790 and res.total == 1509790
    [claim] = res.claims
    assert claim.category == "퇴직금 차액" and claim.due_date == date(2015, 7, 14) and claim.settlement
    # 중간정산 구간은 정산 시점 평균임금이 없어 재산정하지 않음
    seg1 = [r for r in res.rows if r.kind == "segment" and r.segment_no == 1][0]
    assert seg1.amount is None and seg1.end == date(2012, 7, 18)


def test_G4_total_days_방식_차이는_지급률_버림_때문():
    res = run(G4, avg="240522.85")
    assert res.final_severance == 21291214                 # 검증 메모: total_days 방식 21,291,214원
    assert res.final_severance == floor(D("240522.85") * 30 * 1077 / 365)
    same = run(G4, avg="240522.85", rs_service_ratio_mode="years_plus_days")
    assert same.final_severance == res.final_severance     # 2년+347일 = 1,077일, 윤년이 연수 구간에 없어 같음


# ================================================================ 골든 G5 대구지방법원 2024나318050 (원고 주장 계산)
def test_G5_monthly_avg_원고_계산_비교용():
    # 재직 1년 59일. 입사일은 판결에 없어 2023. 1. 1.로, 마지막 근무일 2024. 2. 28.로 정함.
    raw = {"hire_date": "2023-01-01", "last_working_day": "2024-02-28"}
    avg_base = (D(2139000) + 2219000 + 2152630) / 3
    res = run(raw, monthly=avg_base, rs_service_ratio_mode="monthly_avg", rs_round_monthly_base="won_floor")
    part = [r for r in res.rows if r.kind == "part"][0]
    assert (part.years, part.remaining_days) == (1, 59)
    assert res.final_severance == 2521011                  # 원고 각주 "2,521,011원"
    ord_base = (D(2039000) + 100000) / 209 * 8 * 30
    res2 = run(raw, monthly=ord_base, rs_service_ratio_mode="monthly_avg", rs_round_monthly_base="won_floor")
    assert res2.final_severance == 2853307                 # 원고 각주 "2,853,307원"(월 기준액 2,456,267원 먼저 버림)
    assert any("원고 주장" in w for w in res2.warnings)
    res3 = run(raw, monthly=ord_base, rs_service_ratio_mode="monthly_avg")
    assert res3.final_severance == floor(ord_base * (365 + 59) / 365)    # 전체 정밀도면 2,853,308


def test_G5_monthly_avg_월기준액은_사건yaml에서도_적는다():
    # 사건.yaml·cli 경로에는 deps 가 없으므로 retirement.monthly_wage_base 로 받는다(원고 계산 월 기준액 2,456,267원)
    raw = {"hire_date": "2023-01-01", "last_working_day": "2024-02-28", "monthly_wage_base": 2456267}
    assert run(raw, rs_service_ratio_mode="monthly_avg").final_severance == 2853307
    assert run(raw, monthly=D(3000000), rs_service_ratio_mode="monthly_avg").final_severance == \
        floor(D(3000000) * (365 + 59) / 365)               # deps 가 있으면 deps 우선
    with pytest.raises(LaborError, match="retirement.monthly_wage_base"):
        run({"hire_date": "2023-01-01", "last_working_day": "2024-02-28"}, avg=1, rs_service_ratio_mode="monthly_avg")
    with pytest.raises(LaborError, match="음수"):
        load_retirement({**raw, "monthly_wage_base": -1})


def test_monthly_avg_는_사건yaml_경로로_계산된다():
    import yaml
    from engine.labor.calculate import calculate_labor, load_labor_case

    sample = Path(__file__).resolve().parent.parent / "cases" / "labor_sample.yaml"
    case = yaml.safe_load(sample.read_text(encoding="utf-8"))
    case["options"]["rs_service_ratio_mode"] = "monthly_avg"
    case["retirement"] = dict(case.get("retirement") or {}, monthly_wage_base=3000000)
    res = calculate_labor(load_labor_case(case))
    ret = res.parts["retirement"]
    hire, last = date(2021, 3, 2), date(2025, 6, 30)            # labor_sample worker
    years, rem = years_and_days(hire, last)
    assert ret.final_severance == floor(D(3000000) * (years * 365 + rem) / 365)
    assert any("원고 주장" in w for w in res.warnings)


# ================================================================ RS-06 지급기일과 지연손해금
@pytest.mark.parametrize("due_opt,due", [("statutory_14", date(2023, 7, 14)), ("day_after_retirement", date(2023, 6, 30))])
def test_퇴직금_차액은_지급사유_발생일을_지연손해금에_넘긴다(due_opt, due):
    from engine.labor.interest import OPTIONS as DI_OPTIONS, calculate_interest, load_interest

    res = run({"hire_date": "2019-03-04", "last_working_day": "2023-06-30"}, avg=100000, rs_due_date=due_opt)
    [claim] = res.claims
    assert claim.due_date == due and claim.trigger_date == date(2023, 7, 1)
    # worker.last_working_day 가 없어도 due_date 에서 역산하지 않는다: 20%는 마지막 근무일 + 15일부터, 시효 기산은 7. 1.
    di_opts = {k: s.default for k, s in DI_OPTIONS.items()} | {"di_exclusion_end": "none"}
    r = calculate_interest(load_interest({"employer_merchant": True, "suit_filed_date": "2026-06-25"}), di_opts, [claim])
    segs = r.schedules[0].segments
    assert (segs[-1].start, segs[-1].rate) == (date(2023, 7, 15), Decimal(20))
    assert segs[0].start == due + timedelta(days=1)
    lr = r.limitation[0]
    assert lr.start == date(2023, 7, 1) and lr.suspect is False
    assert not any("지급기일 − 13일" in w for w in r.warnings)


# ================================================================ 골든 G6 전주지방법원 군산지원 2023가단56185
@pytest.mark.parametrize("avg,days,last,expected,interest_from", [
    (76666, 8541, date(2023, 2, 28), 53819532, date(2023, 3, 15)),
    (73333, 7421, date(2023, 2, 28), 44729111, date(2023, 3, 15)),
    (69230, 8155, date(2022, 6, 30), 46403067, date(2022, 7, 15)),
])
def test_G6_원미만_버림_14일_경과_다음날(avg, days, last, expected, interest_from):
    # 재직일수만 판결에 있어 입사일 = 마지막 근무일 − (재직일수 − 1)일로 정함. 퇴직일은 판결 기산일에서 역산.
    hire = last - timedelta(days=days - 1)
    res = run({"hire_date": hire.isoformat(), "last_working_day": last.isoformat()}, avg=avg)
    assert res.final_severance == expected
    [claim] = res.claims
    assert claim.due_date + timedelta(days=1) == interest_from      # "퇴직일로부터 14일이 경과한 다음 날"


# ================================================================ 골든 G7 서울중앙지방법원 2017가단5098186
def test_G7_53138635():
    last = date(2017, 8, 31)       # 판결에 없어 정함
    hire = last - timedelta(days=3962 - 1)
    res = run({"hire_date": hire.isoformat(), "last_working_day": last.isoformat()}, avg="163180.23")
    assert res.final_severance == 53138635                 # "163,180.23원×30×3962/365"


# ================================================================ 골든 G8 부산지방법원 서부지원 2023가단118024 (MR-1)
def test_G8_4인이하_경과규정_구간별_버림_31842689():
    # 입사일은 판결에 없어 2008. 3. 1.로, 전 기간 상시 4명 이하로 정함.
    raw = {"hire_date": "2008-03-01", "last_working_day": "2022-10-20", "paid_severance": 8498630,
           "small_business_periods": [["2008-03-01", "2022-10-20"]]}
    res = run(raw, avg=123913)
    parts = [r for r in res.rows if r.kind == "part"]
    assert [(p.rate, p.counted_days, p.amount) for p in parts] == [
        (D(0), (date(2010, 11, 30) - date(2008, 3, 1)).days + 1, D(0)),
        (D("0.5"), 762, D(3880344)),                        # "762일 … × 1/2 = 3,880,344원"
        (D(1), 3580, D(36460975)),                          # "3,580일 → 36,460,975원"
    ]
    assert res.final_severance == 40341319
    assert res.final_diff == 31842689                       # 주문 인용액
    assert res.claims[0].due_date + timedelta(days=1) == date(2022, 11, 4)
    whole = run(raw, avg=123913, rs_part_rounding="sum_then_round")
    assert whole.final_severance == floor(D(123913) * 30 * D("0.5") * 762 / 365 + D(123913) * 30 * 3580 / 365)


# ================================================================ RS-01 1년·윤년
def test_1년_미만():
    res = run({"hire_date": "2024-01-02", "last_working_day": "2024-12-31", "paid_severance": 0}, avg=100000)
    assert not res.eligible and res.total == 0
    ok = run({"hire_date": "2024-01-02", "last_working_day": "2025-01-01"}, avg=100000)
    assert ok.eligible and ok.final_severance == floor(D(100000) * 30 * 366 / 365)


def test_2월29일_입사_1년_만료():
    assert one_year_expiry(date(2020, 2, 29)) == date(2021, 2, 28)
    assert one_year_expiry(date(2020, 2, 29), mode="clamp") == date(2021, 2, 27)
    short = run({"hire_date": "2020-02-29", "last_working_day": "2021-02-27"}, avg=100000)
    assert not short.eligible
    assert run({"hire_date": "2020-02-29", "last_working_day": "2021-02-28"}, avg=100000).eligible
    days365 = run({"hire_date": "2020-02-29", "last_working_day": "2021-02-27"}, avg=100000, rs_one_year_basis="days_365")
    assert days365.eligible                                 # 2020. 2. 29.~2021. 2. 27. = 365일


def test_윤년_포함_연수와_총일수_방식():
    # 2020. 1. 1.~2021. 3. 31.: 총 456일 = 1년(366일) + 90일
    assert years_and_days(date(2020, 1, 1), date(2021, 3, 31)) == (1, 90)
    total = run({"hire_date": "2020-01-01", "last_working_day": "2021-03-31"}, avg=100000)
    yd = run({"hire_date": "2020-01-01", "last_working_day": "2021-03-31"}, avg=100000, rs_service_ratio_mode="years_plus_days")
    assert total.final_severance == floor(D(100000) * 30 * 456 / 365)
    assert yd.final_severance == floor(D(100000) * 30 * (365 + 90) / 365)
    assert yd.final_severance < total.final_severance


def test_주15시간_미만_전기간():
    res = run({"hire_date": "2020-01-01", "last_working_day": "2023-12-31", "weekly_hours": 14}, avg=100000)
    assert not res.eligible


# ================================================================ RS-03·05 중간정산
def test_유효_중간정산_구간별_재산정과_청구():
    raw = {"hire_date": "2010-01-01", "last_working_day": "2020-12-31", "paid_severance": 10000000,
           "interim_settlements": [{"date": "2015-12-31", "paid": 15000000, "valid": True, "average_daily_wage": 90000,
                                    "paid_date": "2016-01-10"}]}
    res = run(raw, avg=120000)
    seg1_days = (date(2015, 12, 31) - date(2010, 1, 1)).days + 1
    seg2_days = (date(2020, 12, 31) - date(2016, 1, 1)).days + 1
    interim_sev = floor(D(90000) * 30 * seg1_days / 365)
    final_sev = floor(D(120000) * 30 * seg2_days / 365)
    assert res.final_severance == final_sev
    assert res.final_diff == final_sev - 10000000
    cats = {c.category: c for c in res.claims}
    assert cats["중간정산 퇴직금 차액"].amount == interim_sev - 15000000
    assert cats["중간정산 퇴직금 차액"].due_date == date(2016, 1, 10) and not cats["중간정산 퇴직금 차액"].settlement
    assert cats["퇴직금 차액"].due_date == date(2021, 1, 14) and cats["퇴직금 차액"].settlement
    assert res.total == (interim_sev - 15000000) + (final_sev - 10000000)
    assert any("소멸시효" in w for w in res.warnings)


def test_콜러블_평균임금은_구간_말일로_호출():
    seen = []

    def avg(d):
        seen.append(d)
        return D(100000)
    raw = {"hire_date": "2010-01-01", "last_working_day": "2020-12-31",
           "interim_settlements": [{"date": "2015-12-31", "paid": 0, "valid": True}]}
    run(raw, avg=avg)
    assert seen == [date(2015, 12, 31), date(2020, 12, 31)]


def test_무효_중간정산은_입사일부터_계속_기지급액_공제():
    raw = {"hire_date": "2010-01-01", "last_working_day": "2020-12-31", "paid_severance": 5000000,
           "interim_settlements": [{"date": "2015-12-31", "paid": 15000000, "valid": False}]}
    res = run(raw, avg=100000)
    days = (date(2020, 12, 31) - date(2010, 1, 1)).days + 1
    assert res.final_severance == floor(D(100000) * 30 * days / 365)
    assert res.final_paid == 20000000
    assert res.final_diff == res.final_severance - 20000000
    assert any("MR-2" in w for w in res.warnings)


def test_기지급이_많으면_차액_0():
    res = run({"hire_date": "2020-01-01", "last_working_day": "2022-12-31", "paid_severance": 99999999}, avg=100000)
    assert res.final_diff == 0 and res.claims == [] and res.total == 0


def test_DC형_경고():
    res = run({"hire_date": "2020-01-01", "last_working_day": "2022-12-31", "dc_plan": True}, avg=100000)
    assert any("RS-07" in w for w in res.warnings)


# ================================================================ 입력 오류
def test_육아휴직은_계속근로일수에서_뺄_수_없음():
    with pytest.raises(LaborError, match="MR-3"):
        load_retirement({"hire_date": "2020-01-01", "last_working_day": "2022-12-31",
                         "excluded_periods": [{"reason": "parental_leave", "start": "2021-01-01", "end": "2021-12-31"}]})


def test_입사일_마지막근무일_누락():
    with pytest.raises(LaborError, match="입사일"):
        load_retirement({"last_working_day": "2022-12-31"})
    with pytest.raises(LaborError, match="마지막 근무일"):
        load_retirement({"hire_date": "2020-01-01"})
    inp = load_retirement({}, {"hire_date": "2020-01-01", "last_working_day": "2022-12-31",
                               "small_business_periods": [["2020-01-01", "2020-12-31"]]})
    assert inp.small_business_periods == [(date(2020, 1, 1), date(2020, 12, 31))]


def test_평균임금_deps_누락():
    with pytest.raises(LaborError, match="average_daily_wage"):
        run({"hire_date": "2020-01-01", "last_working_day": "2022-12-31"})
    with pytest.raises(LaborError, match="monthly_wage_base"):
        run({"hire_date": "2020-01-01", "last_working_day": "2022-12-31"}, avg=1, rs_service_ratio_mode="monthly_avg")


def test_중간정산_입력_오류():
    base = {"hire_date": "2020-01-01", "last_working_day": "2022-12-31"}
    with pytest.raises(LaborError, match="valid"):
        load_retirement({**base, "interim_settlements": [{"date": "2021-06-30", "paid": 1}]})
    with pytest.raises(LaborError, match="정산기준일"):
        load_retirement({**base, "interim_settlements": [{"date": "2023-01-01", "valid": True}]})


def test_연수방식에_제외구간이면_오류():
    raw = {"hire_date": "2016-02-15", "last_working_day": "2019-09-10",
           "excluded_periods": [{"reason": "short_hours", "start": "2019-01-14", "end": "2019-09-10"}]}
    with pytest.raises(LaborError, match="total_days"):
        run(raw, avg=1, rs_service_ratio_mode="years_plus_days")


def test_잘못된_키와_옵션():
    with pytest.raises(LaborError, match="알 수 없는 키"):
        load_retirement({"hire_date": "2020-01-01", "last_working_day": "2022-12-31", "paid": 1})
    with pytest.raises(LaborError):
        resolve_options({"rs_round_severance": "half_up"}, OPTIONS)
