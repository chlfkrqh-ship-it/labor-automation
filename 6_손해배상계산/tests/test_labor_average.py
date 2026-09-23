"""1일 평균임금 (engine/labor/average.py) 검증.

골든 예시는 조사 문서 average_wage_severance.md 3절과 검증 메모의 판결 원문 숫자다.
판결문에 없는 사실(입사일, 상여금 지급일 등)을 테스트용으로 정한 경우 그 사실을 주석에 적었다.
금액 기대값은 판결 숫자이거나, assert 옆에 Decimal 식을 그대로 적은 값이다.
"""

import sys
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.labor.common import LaborError, resolve_options, round_to  # noqa: E402
from engine.labor.average import (  # noqa: E402
    OPTIONS,
    RULES,
    annual_leave_items_from_rows,
    calculate_average_wage,
    load_average_wage,
    window_bounds,
)

D = Decimal


def run(raw, worker=None, ordinary=0, extra=None, **opt):
    inp = load_average_wage(raw, worker)
    opts, _ = resolve_options(opt, OPTIONS)
    deps = {"daily_ordinary_of": ordinary if callable(ordinary) else (lambda d, v=D(ordinary): v)}
    if extra is not None:
        deps["extra_wages"] = extra
    return calculate_average_wage(inp, opts, **deps)


def close(a, b):
    return abs(D(a) - D(b)) < D("1e-15")


def flat(start, end, amount, hire="2000-01-01", **more):
    """[start, end] 전체에 한 항목 금액을 넣은 최소 입력."""
    raw = {"hire_date": hire, "wages": [{"start": start, "end": end, "items": {"임금": amount}}]}
    raw.update(more)
    return raw


# ================================================================ 모듈 규약
def test_옵션_키_접두어와_기본값():
    assert all(k.startswith("aw_") for k in OPTIONS)
    values, _ = resolve_options({}, OPTIONS)
    assert values["aw_annual_leave_mode"] == "case_prorata"          # 검증 판정: moel_3_12 를 기본값으로 두지 않음
    assert values["aw_ordinary_compare_mode"] == "daily"
    assert values["aw_round_avg_daily"] == "jeon2_floor"
    assert values["aw_dismissal_period_exclude"] is True
    assert values["aw_long_exclusion_trigger"] == "window_fully_excluded"
    assert values["aw_partial_period"] == "calendar_days"


def test_규칙_상태_어휘():
    allowed = {"판례확립", "법령", "행정해석", "하급심", "실무관행", "불명확"}
    for rid, (summary, status) in RULES.items():
        assert summary
        assert set(status.split("·")) <= allowed, rid
    assert RULES["AW-02"][1] == "판례확립·실무관행"
    assert RULES["AW-06"][1] == "불명확"
    assert RULES["AW-11"][1] == "행정해석·하급심"
    assert RULES["AW-14"][1] == "불명확"
    assert "MR-4" in RULES


def test_결과_형태():
    res = run(flat("2024-04-01", "2024-06-30", 9100000, last_working_day="2024-06-30"))
    assert res.total == 0 and res.claims == []
    assert isinstance(res.average_daily_wage, Decimal) and isinstance(res.average_daily_wage_raw, Decimal)


# ================================================================ 골든 G1 대법원 87다카2901
def test_G1_산정기간_일할_상여금_가산_원미만_버림():
    # 사고일 1985. 8. 23. 입사일·상여금 지급일(1984. 12. 20., 1985. 6. 20.)은 판결에 없어 정함("매년 6월·12월").
    raw = {"occurrence_date": "1985-08-23", "hire_date": "1980-01-01",
           "wages": [{"month": "1985-05", "items": {"급여": 308760}}, {"month": "1985-06", "items": {"급여": 243410}},
                     {"month": "1985-07", "items": {"급여": 244440}}, {"month": "1985-08", "items": {"급여": 259590}}],
           "bonuses": [{"paid_date": "1984-12-20", "amount": 220500}, {"paid_date": "1985-06-20", "amount": 220500}]}
    res = run(raw, aw_round_avg_daily="won_floor")
    assert (res.window_start, res.window_end, res.window_days) == (date(1985, 5, 23), date(1985, 8, 22), 92)
    # 원문 "［(308,760×9/31+243,410+244,440+259,590×22/31)+(220,500×2×3/12)］÷92×365/12"
    expected_total = D(308760) * 9 / 31 + 243410 + 244440 + D(259590) * 22 / 31 + D(220500) * 2 * 3 / 12
    assert close(res.wage_total, expected_total)
    assert res.average_daily_wage == 9477
    assert round_to(res.average_daily_wage * 365 / 12, 0, "floor") == 288258     # 원문 "금288,258원"


# ================================================================ 골든 G2 대법원 96누5469
def test_G2_초일_불산입_기간():
    # 사망일 1995. 4. 20. — 정당한 산정기간 1995. 1. 20.~4. 19.(90일). 임금총액은 원문에 없어 기간만 검증.
    s, e, missing, short = window_bounds(date(1995, 4, 20), date(1990, 1, 1))
    assert (s, e, missing, short) == (date(1995, 1, 20), date(1995, 4, 19), False, False)
    assert (e - s).days + 1 == 90
    # 원심처럼 사망일을 넣으면 1. 21.~4. 20. — 일수는 같아 경계만 다르다(검증 메모)
    assert window_bounds(date(1995, 4, 21), date(1990, 1, 1))[:2] == (date(1995, 1, 21), date(1995, 4, 20))


def test_G2_둘째자리_버림_형태():
    # 임금총액 2,760,000원은 원문 미기재 — 판결값 30,666.66원에서 역산한 값(검증 메모)
    res = run(flat("1995-01-20", "1995-04-19", 2760000, hire="1990-01-01", occurrence_date="1995-04-20"))
    assert res.average_daily_wage == D("30666.66")


# ================================================================ 골든 G3 부산지방법원 2020나52559
def test_G3_해고일_기준_산정기간_91일():
    res = run(flat("2019-04-01", "2019-06-30", 3154606, hire="2016-02-15", occurrence_date="2019-07-01"))
    assert (res.window_start, res.window_end, res.window_days) == (date(2019, 4, 1), date(2019, 6, 30), 91)


def test_AW11_부당해고기간_72일_제외_3개월_미만이면_발생일_유지():
    # 부당해고 2019. 7. 1.~9. 10.(72일), 퇴직(합의해지 간주) 9. 10. — 산정기간 6. 11.~9. 10. 92일 중 72일 제외
    raw = flat("2019-06-01", "2019-09-30", 0, hire="2016-02-15", last_working_day="2019-09-10",
               excluded_periods=[{"reason": "unfair_dismissal", "start": "2019-07-01", "end": "2019-09-10"}])
    raw["wages"] = [{"month": "2019-06", "items": {"임금": 3000000}}]
    for trigger in ("window_fully_excluded", "continuous_3_months"):
        res = run(raw, aw_long_exclusion_trigger=trigger)
        assert (res.window_start, res.window_end) == (date(2019, 6, 11), date(2019, 9, 10))
        assert (res.window_days, res.excluded_days, res.counted_days) == (92, 72, 20)
        assert close(res.principle_daily, D(3000000) * 20 / 30 / 20)
    assert any("AW-11" in w for w in res.warnings)
    off = run(raw, aw_dismissal_period_exclude=False)
    assert off.excluded_days == 0 and off.counted_days == 92


# ================================================================ 골든 G4 수원지방법원 2018가소24967
def test_G4_임금총액_21887580_평균임금_240522_85():
    # 퇴직 2015. 6. 30. 경영평가성과급 지급일은 판결에 없어 2015. 3. 31.로 정함(발생일 이전 12개월 안).
    raw = {"hire_date": "2002-01-02", "last_working_day": "2015-06-30",
           "wages": [{"start": "2015-04-01", "end": "2015-06-30", "items": {"기본연봉급·성과연봉급": 20335140}}]
           + [{"month": m, "items": {"직급보조비": 280000, "가족수당": 60000}} for m in ("2015-04", "2015-05", "2015-06")],
           "bonuses": [{"paid_date": "2015-03-31", "amount": 2129760}]}
    res = run(raw)      # 판결에 통상임금 비교 수치 없음 — 비교가 발동하지 않도록 0
    assert (res.window_start, res.window_end, res.window_days) == (date(2015, 4, 1), date(2015, 6, 30), 91)
    assert res.wage_total == 21887580                      # "20,335,140원 ＋ 280,000원 × 3개월 ＋ 60,000월 × 3개월 ＋ 2,129,760원/4"
    assert res.average_daily_wage == D("240522.85")        # "소수점 둘째자리 미만 버림"
    assert close(res.average_daily_wage_raw, D(21887580) / 91)


# ================================================================ 골든 G7 서울중앙지방법원 2017가단5098186
def test_G7_반올림_163180_23():
    # 3개월 임금 15,012,581원, 92일. 마지막 근무일은 판결에 없어 92일이 되는 2017. 8. 31.로 정함.
    res = run(flat("2017-06-01", "2017-08-31", 15012581, last_working_day="2017-08-31"), aw_round_avg_daily="jeon2_half_up")
    assert res.window_days == 92
    assert res.average_daily_wage == D("163180.23")


# ================================================================ 골든 G8 부산지방법원 서부지원 2023가단118024
def test_G8_92일_원미만_버림_123913():
    res = run(flat("2022-07-21", "2022-10-20", 11400000, last_working_day="2022-10-20"), aw_round_avg_daily="won_floor")
    assert (res.window_start, res.window_end, res.window_days) == (date(2022, 7, 21), date(2022, 10, 20), 92)
    assert res.average_daily_wage == 123913


# ================================================================ AW-02·03 경계
@pytest.mark.parametrize("mode,start,days", [("next_day", date(2023, 3, 1), 91), ("month_end", date(2023, 2, 28), 92)])
def test_월말_대응일_없음(mode, start, days):
    # 마지막 근무일 2023. 5. 30. → 발생일 5. 31. → 2. 31. 없음
    res = run(flat("2023-02-01", "2023-05-31", 1000000, last_working_day="2023-05-30"), aw_window_month_end=mode)
    assert (res.window_start, res.window_end, res.window_days) == (start, date(2023, 5, 30), days)
    assert any("AW-02" in w for w in res.warnings)


def test_윤년_2월29일():
    assert window_bounds(date(2024, 5, 29), date(2000, 1, 1))[:2] == (date(2024, 2, 29), date(2024, 5, 28))
    assert window_bounds(date(2024, 5, 31), date(2000, 1, 1), "month_end")[:2] == (date(2024, 2, 29), date(2024, 5, 30))
    s, e, missing, _ = window_bounds(date(2024, 5, 31), date(2000, 1, 1), "next_day")
    assert (s, e, missing) == (date(2024, 3, 1), date(2024, 5, 30), True)


def test_재직_3개월_미만():
    res = run(flat("2024-05-15", "2024-06-30", 4700000, hire="2024-05-15", last_working_day="2024-06-30"))
    assert (res.window_start, res.window_days) == (date(2024, 5, 15), 47)
    assert res.average_daily_wage == D(4700000) / 47


def test_근로_첫날_발생():
    res = run({"hire_date": "2024-05-15", "occurrence_date": "2024-05-15", "first_day_daily_wage": 100000})
    assert res.average_daily_wage == 100000
    with pytest.raises(LaborError, match="first_day_daily_wage"):
        run({"hire_date": "2024-05-15", "occurrence_date": "2024-05-15"})


def test_월_중도_일할과_as_entered():
    # 발생일 2024. 7. 16. → 4. 16.~7. 15.(91일). 4월 30일 중 15일, 7월 31일 중 15일
    raw = {"hire_date": "2020-01-01", "occurrence_date": "2024-07-16",
           "wages": [{"month": m, "items": {"임금": 3000000}} for m in ("2024-04", "2024-05", "2024-06", "2024-07")]}
    res = run(raw)
    assert res.window_days == 91
    assert close(res.wage_total, D(3000000) * 15 / 30 + 3000000 + 3000000 + D(3000000) * 15 / 31)
    raw2 = {**raw, "wages": [{"month": "2024-04", "items": {"임금": 1500000}}, {"month": "2024-05", "items": {"임금": 3000000}},
                             {"month": "2024-06", "items": {"임금": 3000000}}, {"month": "2024-07", "items": {"임금": 1400000}}]}
    res2 = run(raw2, aw_partial_period="as_entered")
    assert res2.wage_total == D(1500000) + 3000000 + 3000000 + 1400000
    assert any("as_entered" in w for w in res2.warnings)


def test_항목별_불산입과_extra_wages():
    raw = {"hire_date": "2020-01-01", "last_working_day": "2024-06-30",
           "wages": [{"month": m, "items": {"기본급": 3000000, "경조금": {"amount": 500000, "include": False}}}
                     for m in ("2024-04", "2024-05", "2024-06")]}
    res = run(raw, extra={"2024-03": D(999999), "2024-05": D(210000), "2024-06": D(90000)})
    assert res.wage_total == D(3000000) * 3 + 210000 + 90000     # 3월분은 산정기간 밖
    assert res.counted_days == 91


def test_임금_입력_없는_날_경고():
    res = run({"hire_date": "2020-01-01", "last_working_day": "2024-06-30",
               "wages": [{"month": "2024-06", "items": {"임금": 3000000}}]})
    assert any("임금 입력이 없는 날이 61일" in w for w in res.warnings)


# ================================================================ AW-05 상여금
def test_상여금_12개월_경계일():
    # 발생일 2024. 7. 1. → 12개월 범위 2023. 7. 1.~2024. 6. 30.
    raw = flat("2024-04-01", "2024-06-30", 9100000, last_working_day="2024-06-30",
               bonuses=[{"paid_date": "2023-06-30", "amount": 1000000}, {"paid_date": "2023-07-01", "amount": 2000000},
                        {"paid_date": "2024-06-30", "amount": 4000000}, {"paid_date": "2024-07-01", "amount": 8000000},
                        {"paid_date": "2024-01-10", "amount": 16000000, "include": False}])
    res = run(raw)
    assert res.principle.bonus_total == D(2000000) + 4000000
    assert res.wage_total == D(9100000) + (D(2000000) + 4000000) * 3 / 12


def test_퇴직_후_지급_성과급_옵션():
    raw = flat("2024-04-01", "2024-06-30", 9100000, last_working_day="2024-06-30",
               bonuses=[{"paid_date": "2024-09-15", "amount": 1200000, "evaluation_start": "2023-07-01",
                         "evaluation_end": "2024-06-30"}])
    assert run(raw).principle.bonus_total == 0
    on = run(raw, aw_bonus_after_retirement=True)
    assert on.principle.bonus_total == 1200000
    assert on.wage_total == D(9100000) + D(1200000) * 3 / 12


# ================================================================ AW-06 연차휴가수당
def leave_raw(**item):
    return flat("2024-04-01", "2024-06-30", 9100000, last_working_day="2024-06-30", annual_leave_pay=[item])


def test_퇴직으로_발생한_연차수당_불산입_moel():
    # 2023. 7. 1.~2024. 6. 30. 근로분, 퇴직 다음 날 2024. 7. 1. 청구권 발생
    item = {"amount": 1500000, "claim_arises": "2024-07-01", "period_start": "2023-07-01", "period_end": "2024-06-30"}
    moel = run(leave_raw(**item), aw_annual_leave_mode="moel_3_12")
    assert moel.principle.annual_leave_addition == 0
    assert moel.wage_total == 9100000
    # 귀속 기준(2009다86246 적용례)은 기초 1년과 산정기간이 겹친 91일분을 산입 — 두 값 병기와 경고
    case = run(leave_raw(**item))
    assert close(case.principle.annual_leave_addition, D(1500000) * 91 / 366)
    assert case.annual_leave_alternatives["moel_3_12"] == 0
    assert any("AW-06" in w for w in case.warnings)
    months = run(leave_raw(**item), aw_annual_leave_prorata_unit="months")
    assert close(months.principle.annual_leave_addition, D(1500000) * 3 / 12 * 91 / 91)


def test_전년도_미사용수당_moel_3_12_산입_case_불산입():
    # 2022. 7. 1.~2023. 6. 30. 근로분, 청구권 2024. 7. 1. 전(2024. 1. 1.) 발생 — 산정기간과 기초 1년은 겹치지 않음
    item = {"amount": 1200000, "claim_arises": "2024-01-01", "period_start": "2022-07-01", "period_end": "2023-06-30"}
    moel = run(leave_raw(**item), aw_annual_leave_mode="moel_3_12")
    assert moel.principle.annual_leave_addition == D(1200000) * 3 / 12
    assert run(leave_raw(**item)).principle.annual_leave_addition == 0
    assert run(leave_raw(**item), aw_annual_leave_mode="exclude").principle.annual_leave_addition == 0


def test_연차_행에서_변환():
    rows = [SimpleNamespace(period_start=date(2023, 7, 1), period_end=date(2024, 6, 30), amount=D(1500000),
                            claim_arises=date(2024, 7, 1), pay_due_date=date(2024, 7, 14), source="15일"),
            SimpleNamespace(period_start=date(2022, 7, 1), period_end=date(2023, 6, 30), amount=D(0),
                            claim_arises=date(2023, 7, 1), pay_due_date=None, source="")]
    items = annual_leave_items_from_rows(rows)
    assert len(items) == 1 and items[0].cause is None and items[0].claim_arises == date(2024, 7, 1)


def test_연차수당_필요값_누락():
    with pytest.raises(LaborError, match="period_start"):
        run(leave_raw(amount=100000, claim_arises="2024-01-01"))
    with pytest.raises(LaborError, match="claim_arises"):
        run(leave_raw(amount=100000, period_start="2023-07-01", period_end="2024-06-30"), aw_annual_leave_mode="moel_3_12")


# ================================================================ AW-07·08·09 제외기간
def test_제외기간_일부_일수와_임금_차감():
    # 2024. 5. 1.~5. 31. 육아휴직(그 기간 임금 0), 6. 3.~6. 5. 적법 파업(임금 0)
    raw = {"hire_date": "2020-01-01", "last_working_day": "2024-06-30",
           "wages": [{"month": "2024-04", "items": {"임금": 3000000}}, {"month": "2024-05", "items": {"임금": 0}},
                     {"month": "2024-06", "items": {"임금": 2700000}}],
           "excluded_periods": [{"reason": "parental_leave", "start": "2024-05-01", "end": "2024-05-31"},
                                {"reason": "strike", "start": "2024-06-03", "end": "2024-06-05", "lawful": True}]}
    res = run(raw)
    assert (res.excluded_days, res.counted_days) == (34, 91 - 34)
    assert close(res.principle_daily, (D(3000000) + 2700000) / (91 - 34))


def test_제외기간_임금_차감():
    raw = flat("2024-04-01", "2024-06-30", 9100000, last_working_day="2024-06-30",
               excluded_periods=[{"reason": "employer_shutdown", "start": "2024-06-01", "end": "2024-06-30", "wages": 2100000}])
    res = run(raw)
    assert res.wage_total == D(9100000) - 2100000 and res.counted_days == 61


def test_위법_쟁의와_위법_직장폐쇄는_제외_안_함():
    base = flat("2024-04-01", "2024-06-30", 9100000, last_working_day="2024-06-30")
    unlawful = run({**base, "excluded_periods": [{"reason": "strike", "start": "2024-06-01", "end": "2024-06-10", "lawful": False}]})
    assert unlawful.excluded_days == 0
    lockout = run({**base, "excluded_periods": [{"reason": "lockout", "start": "2024-06-01", "end": "2024-06-10",
                                                  "lawful": False, "employer_wage_obligation": True}]})
    assert lockout.excluded_days == 0
    lawful = run({**base, "excluded_periods": [{"reason": "lockout", "start": "2024-06-01", "end": "2024-06-10", "lawful": True}]})
    assert lawful.excluded_days == 10
    overlap = run({**base, "excluded_periods": [{"reason": "lockout", "start": "2024-06-01", "end": "2024-06-10",
                                                  "lawful": True, "worker_unlawful_strike": True}]})
    assert overlap.excluded_days == 0
    military_paid = run({**base, "excluded_periods": [{"reason": "military", "start": "2024-06-01", "end": "2024-06-03", "wages": 300000}]})
    assert military_paid.excluded_days == 0


def test_제외기간_3개월_이상이면_최초일_기준():
    # 부당해고 2019. 4. 1.~9. 10., 퇴직 9. 10. → 6. 11.~9. 10. 전부 제외 → 발생일 4. 1. → 1. 1.~3. 31.(90일)
    raw = {"hire_date": "2016-02-15", "last_working_day": "2019-09-10",
           "wages": [{"start": "2019-01-01", "end": "2019-03-31", "items": {"임금": 9000000}}],
           "excluded_periods": [{"reason": "unfair_dismissal", "start": "2019-04-01", "end": "2019-09-10"}]}
    res = run(raw)
    assert res.original_occurrence_date == date(2019, 9, 11)
    assert res.occurrence_date == date(2019, 4, 1)
    assert (res.window_start, res.window_end, res.window_days) == (date(2019, 1, 1), date(2019, 3, 31), 90)
    assert res.average_daily_wage_raw == D(9000000) / 90
    assert any(r.kind == "shift" for r in res.rows)
    assert any(t.rule == "AW-09" for t in res.trace)


def test_AW09_판정방식_차이():
    # 제외기간 2024. 3. 1.~6. 10.(3개월 이상)이 산정기간 4. 1.~6. 30. 일부만 덮음
    raw = {"hire_date": "2020-01-01", "last_working_day": "2024-06-30",
           "wages": [{"start": "2023-12-01", "end": "2024-06-30", "items": {"임금": 7000000}}],
           "excluded_periods": [{"reason": "approved_leave", "start": "2024-03-01", "end": "2024-06-10"}]}
    full = run(raw)
    assert full.occurrence_date == date(2024, 7, 1) and full.counted_days == 20
    cont = run(raw, aw_long_exclusion_trigger="continuous_3_months")
    assert cont.occurrence_date == date(2024, 3, 1)
    assert (cont.window_start, cont.window_end) == (date(2023, 12, 1), date(2024, 2, 29))


def test_산정기간_전부_제외인데_입사일_이전으로_옮겨지면_오류():
    raw = flat("2024-04-01", "2024-06-30", 0, hire="2024-04-01", last_working_day="2024-06-30",
               excluded_periods=[{"reason": "industrial_accident", "start": "2024-04-01", "end": "2024-06-30"}])
    with pytest.raises(LaborError, match="산정기간이 없습니다"):
        run(raw)


def test_AW09_로_발생일이_입사일로_옮겨지면_근로_첫날_규칙():
    # 입사일부터 업무상 요양하다 퇴직 — 산정기간 전부 제외 → 제외기간 최초일(입사일)로 발생일 이동 → 특례 고시 제2조
    raw = {"hire_date": "2024-01-02", "last_working_day": "2024-06-30", "first_day_daily_wage": 100000,
           "excluded_periods": [{"reason": "industrial_accident", "start": "2024-01-02", "end": "2024-06-30"}]}
    res = run(raw)
    assert res.original_occurrence_date == date(2024, 7, 1) and res.occurrence_date == date(2024, 1, 2)
    assert res.average_daily_wage == 100000
    assert any(r.kind == "shift" for r in res.rows) and any(t.rule == "AW-09" for t in res.trace)
    del raw["first_day_daily_wage"]
    with pytest.raises(LaborError, match="AW-09.*first_day_daily_wage"):
        run(raw)


@pytest.mark.parametrize("trigger", ["window_fully_excluded", "continuous_3_months"])
def test_입사일부터_수습_중_발생이면_첫날_규칙과_수습_경고(trigger):
    raw = {"hire_date": "2024-01-02", "occurrence_date": "2024-03-15", "first_day_daily_wage": 95000,
           "wages": [{"month": "2024-01", "items": {"임금": 2900000}}],
           "excluded_periods": [{"reason": "probation", "start": "2024-01-02", "end": "2024-04-01"}]}
    res = run(raw, aw_long_exclusion_trigger=trigger)
    assert res.occurrence_date == date(2024, 1, 2) and res.average_daily_wage == 95000
    assert any("수습" in w and "사람이 정하십시오" in w for w in res.warnings)
    del raw["first_day_daily_wage"]
    with pytest.raises(LaborError, match="first_day_daily_wage.*수습"):
        run(raw, aw_long_exclusion_trigger=trigger)


def test_제외기간이_입사일보다_앞서면_오류():
    raw = {"hire_date": "2024-01-02", "last_working_day": "2024-06-30",
           "excluded_periods": [{"reason": "industrial_accident", "start": "2023-12-01", "end": "2024-06-30"}]}
    with pytest.raises(LaborError, match="입사일.*앞섭니다"):
        run(raw)


def test_원칙_산정_불가_오류는_대체_산정기간을_권하지_않음():
    # 재직 3개월 미만이고 산정기간 전부가 3개월 미만 제외기간 — continuous_3_months 이면 발생일을 옮기지 않아 산입일수 0.
    # 원칙 산정이 멈추면 override_window 는 계산되지 않으므로 오류 문구가 그것을 권하면 안 된다.
    raw = flat("2024-05-15", "2024-06-30", 0, hire="2024-05-15", last_working_day="2024-06-30",
               excluded_periods=[{"reason": "approved_leave", "start": "2024-05-15", "end": "2024-06-30"}])
    with pytest.raises(LaborError, match="aw_long_exclusion_trigger") as exc:
        run(raw, aw_long_exclusion_trigger="continuous_3_months")
    assert "override_window" not in str(exc.value)


def test_수습을_3개월보다_길게_입력하면_임금은_입력기간으로_일할():
    # 수습 입력 2024. 1. 2.~4. 30.(120일, 임금 11,900,000원) → 제외는 3개월 이내 1. 2.~4. 1.만.
    # 산정기간 2. 1.~4. 30.(90일)과 겹친 61일분 = 11,900,000 × 61/120 을 뺀다(잘린 기간 91일로 나누지 않음).
    raw = {"hire_date": "2024-01-02", "last_working_day": "2024-04-30",
           "wages": [{"month": "2024-01", "items": {"임금": 2900000}}]
           + [{"month": m, "items": {"임금": 3000000}} for m in ("2024-02", "2024-03", "2024-04")],
           "excluded_periods": [{"reason": "probation", "start": "2024-01-02", "end": "2024-04-30", "wages": 11900000}]}
    res = run(raw)
    assert (res.window_start, res.window_end, res.window_days) == (date(2024, 2, 1), date(2024, 4, 30), 90)
    assert (res.excluded_days, res.counted_days) == (61, 29)
    assert res.principle.excluded_wages == D(11900000) * 61 / 120
    assert close(res.principle_daily, (D(9000000) - D(11900000) * 61 / 120) / 29)
    assert any("AW-07" in w and "입력 기간" in w for w in res.warnings)
    # 3개월 이내로 입력하면 그 기간(91일) 금액으로 일할 — 종전과 같다
    raw2 = dict(raw, excluded_periods=[{"reason": "probation", "start": "2024-01-02", "end": "2024-04-01", "wages": 8900000}])
    res2 = run(raw2)
    assert res2.principle.excluded_wages == D(8900000) * 61 / 91
    assert not any("AW-07" in w and "입력 기간" in w for w in res2.warnings)


# ================================================================ AW-10·12·13·14
def test_통상임금_하한_발동과_비교방식():
    # 3개월 임금 2,730,000원/91일 = 30,000원 < 1일 통상임금 80,000원
    raw = flat("2024-04-01", "2024-06-30", 2730000, last_working_day="2024-06-30", ordinary_wage_total=2000000)
    res = run(raw, ordinary=80000)
    assert res.principle_daily == D(2730000) / 91
    assert res.ordinary_applied and res.average_daily_wage == 80000
    assert res.compare_results == {"daily": True, "three_month_total": False, "exceptional_only": False}
    assert any("AW-14" in w for w in res.warnings)
    total = run(raw, ordinary=80000, aw_ordinary_compare_mode="three_month_total")
    assert not total.ordinary_applied and total.average_daily_wage == D("30000.00")
    exc = run(raw, ordinary=80000, aw_ordinary_compare_mode="exceptional_only")
    assert not exc.ordinary_applied
    exc2 = run({**raw, "ordinary_substitution_exceptional": True}, ordinary=80000, aw_ordinary_compare_mode="exceptional_only")
    assert exc2.ordinary_applied


def test_통상임금_기준일은_산정기간_말일():
    seen = []
    run(flat("2024-04-01", "2024-06-30", 9100000, last_working_day="2024-06-30"), ordinary=lambda d: seen.append(d) or D(0))
    assert seen == [date(2024, 6, 30)]


def test_비열거_기간은_제외_불가와_MR4_경고():
    with pytest.raises(LaborError, match="AW-10"):
        load_average_wage(flat("2024-04-01", "2024-06-30", 0, last_working_day="2024-06-30",
                               excluded_periods=[{"reason": "detention", "start": "2024-04-01", "end": "2024-06-30"}]))
    raw = flat("2024-04-01", "2024-06-30", 0, last_working_day="2024-06-30", pre_absence_average_daily=150000,
               unlisted_periods=[{"reason": "detention", "start": "2024-04-01", "end": "2024-06-30"}])
    res = run(raw, ordinary=60000)
    assert res.counted_days == 91 and res.ordinary_applied and res.average_daily_wage == 60000
    assert any("MR-4" in w and "150000" in w for w in res.warnings)


def test_대체_산정기간_병기와_적용():
    raw = flat("2024-04-01", "2024-06-30", 910000, last_working_day="2024-06-30",
               override_window={"start": "2023-10-01", "end": "2023-12-31", "reason": "휴직 전 3개월", "apply": False})
    raw["wages"].append({"start": "2023-10-01", "end": "2023-12-31", "items": {"임금": 9200000}})
    res = run(raw)
    assert not res.override_applied and res.average_daily_wage == D("10000.00")
    assert res.override.window_days == 92 and res.override.daily == D(9200000) / 92
    applied = run({**raw, "override_window": {**raw["override_window"], "apply": True}})
    assert applied.override_applied and applied.average_daily_wage == D("100000.00")
    assert any("AW-12" in w for w in applied.warnings)


@pytest.mark.parametrize("mode,expected", [("jeon2_floor", D("33333.32")), ("won_floor", D(33333)),
                                           ("jeon2_half_up", D("33333.33")), ("none", D(3033333) / 91)])
def test_끝수_옵션(mode, expected):
    # 3,033,333 ÷ 91 = 33,333.3296…
    res = run(flat("2024-04-01", "2024-06-30", 3033333, last_working_day="2024-06-30"), aw_round_avg_daily=mode)
    assert res.average_daily_wage == expected
    assert res.average_daily_wage_raw == D(3033333) / 91


# ================================================================ 입력 오류
def test_입사일_누락():
    with pytest.raises(LaborError, match="입사일"):
        load_average_wage({"last_working_day": "2024-06-30"})


def test_발생일_누락_worker_사용():
    with pytest.raises(LaborError, match="occurrence_date"):
        load_average_wage({"hire_date": "2020-01-01"})
    inp = load_average_wage({}, {"hire_date": "2020-01-01", "last_working_day": "2024-06-30", "pay_period_start_day": 21})
    assert inp.occurrence_date == date(2024, 7, 1) and inp.pay_period_start_day == 21


def test_빈칸_임금산정기간_시작일은_worker_값():
    worker = {"hire_date": "2019-01-01", "last_working_day": "2019-12-31", "pay_period_start_day": 21}
    for blank in (None, ""):
        assert load_average_wage({"pay_period_start_day": blank}, worker).pay_period_start_day == 21
    assert load_average_wage({"pay_period_start_day": None}, dict(worker, pay_period_start_day=None)).pay_period_start_day == 1
    for bad in (0, True, "스무하루"):
        with pytest.raises(LaborError, match="pay_period_start_day"):
            load_average_wage({"pay_period_start_day": bad}, worker)
    # 21일~20일 임금산정기간 사업장: 빈칸이면 키를 뺀 것과 같은 1일 평균임금
    wages = [{"month": m, "items": {"임금": a}}
             for m, a in (("2019-09", 3600000), ("2019-10", 3100000), ("2019-11", 3000000), ("2019-12", 4100000))]
    blank = run({"pay_period_start_day": None, "wages": wages}, worker)
    omitted = run({"wages": wages}, worker)
    assert blank.average_daily_wage == omitted.average_daily_wage == D("108204.76")


def test_따옴표_없는_점_표기_월은_오류():
    import yaml

    raw = yaml.safe_load("hire_date: 2010-01-01\nlast_working_day: 2015-12-31\n"
                         "wages:\n  - {month: 2015.10, items: {임금: 3000000}}\n")
    assert raw["wages"][0]["month"] == 2015.1              # YAML 이 10월을 숫자 2015.1(1월)로 읽는다
    with pytest.raises(LaborError, match="따옴표"):
        load_average_wage(raw)
    raw["wages"][0]["month"] = "2015.10"                   # 따옴표로 감싼 점 표기는 받는다
    assert load_average_wage(raw).wages[0].key == "2015-10"


def test_통상임금_deps_누락():
    with pytest.raises(LaborError, match="daily_ordinary_of"):
        calculate_average_wage(load_average_wage(flat("2024-04-01", "2024-06-30", 1, last_working_day="2024-06-30")), {})


def test_쟁의_적법여부_누락():
    with pytest.raises(LaborError, match="lawful"):
        load_average_wage(flat("2024-04-01", "2024-06-30", 1, last_working_day="2024-06-30",
                               excluded_periods=[{"reason": "strike", "start": "2024-06-01", "end": "2024-06-02"}]))


def test_3개월_총액_비교에_통상임금_총액_누락():
    with pytest.raises(LaborError, match="ordinary_wage_total"):
        run(flat("2024-04-01", "2024-06-30", 1, last_working_day="2024-06-30"), aw_ordinary_compare_mode="three_month_total")


def test_잘못된_키_금액_사유():
    with pytest.raises(LaborError, match="알 수 없는 키"):
        load_average_wage({"hire_date": "2020-01-01", "last_working_day": "2024-06-30", "wage": []})
    with pytest.raises(LaborError, match="숫자"):
        load_average_wage(flat("2024-04-01", "2024-06-30", "삼백만", last_working_day="2024-06-30"))
    with pytest.raises(LaborError, match="사유"):
        load_average_wage(flat("2024-04-01", "2024-06-30", 1, last_working_day="2024-06-30",
                               excluded_periods=[{"reason": "sick", "start": "2024-06-01", "end": "2024-06-02"}]))
    with pytest.raises(LaborError, match="YYYY-MM"):
        load_average_wage({"hire_date": "2020-01-01", "last_working_day": "2024-06-30", "wages": [{"month": "6월", "items": {"a": 1}}]})
    with pytest.raises(LaborError, match="items"):
        load_average_wage({"hire_date": "2020-01-01", "last_working_day": "2024-06-30", "wages": [{"month": "2024-06"}]})


def test_잘못된_옵션():
    with pytest.raises(LaborError):
        resolve_options({"aw_round_avg_daily": "ceil"}, OPTIONS)
    with pytest.raises(LaborError):
        run(flat("2024-04-01", "2024-06-30", 1, last_working_day="2024-06-30"), aw_annual_leave_mode="x")
