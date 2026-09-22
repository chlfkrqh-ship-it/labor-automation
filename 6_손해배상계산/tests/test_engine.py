"""대법원 프로그램 설명서 수치 + 디컴파일 소스 대조로 엔진을 검증한다.

여기 쓰인 값은 모두 공개 설명서의 예시이며 실제 사건 자료가 아니다.
"""

import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.disability import (
    Impairment,
    combined_with_prior,
    prior_contribution,
    truncate2,
)
from engine.fraction import remove_fraction, round_half_even
from engine.hoffman import LEIBNIZ, adjust_factor, apply_cap, cumulative, get_factor
from engine.income import period_income


# ---------------------------------------------------------------- 노동능력상실률
# 설명서(손해배상) 2쪽 / 예시 2쪽
EXAMPLE = [
    Impairment(58.0, prior=50.0, dept="신장내과"),
    Impairment(13.0, dept="안과"),
    Impairment(1.06, dept="치과"),
]


def test_중복장해율():
    assert truncate2(combined_with_prior(EXAMPLE)) == Decimal("38.88")


def test_기왕증기여도():
    assert truncate2(prior_contribution(EXAMPLE)) == Decimal("39.09")


def test_한시장해_영구환산():
    # 설명서 15쪽: 13% x 2년/10년 = 2.6%
    assert Impairment(13.0, years=2).as_permanent_rate() == 2.6


# ---------------------------------------------------------------- 호프만
def test_240_초과시점():
    # 설명서 17쪽: 414개월을 초과하여 단리연금현가율이 240을 넘게 된다
    assert cumulative(413) == Decimal("239.9092")
    assert cumulative(414) == Decimal("240.2762")


def test_설명서_18쪽_순번3():
    assert cumulative(144) == Decimal("112.6135")   # 12년
    assert cumulative(720) == Decimal("332.3359")   # 60년
    assert adjust_factor(720, 144) == Decimal("219.7224")


def test_240_상한_적용():
    # 설명서 18쪽: 8.1249 + 15.4684 = 23.5933, 240 - 23.5933 = 216.4067
    got = apply_cap(["8.1249", "15.4684", "219.7224"])
    assert got[2] == Decimal("216.4067")
    assert sum(got) == Decimal("240")


def test_get_factor_단일월():
    # sumMode=false 면 해당 월의 계수 1개만 (startIdx = month)
    single = get_factor(month=12, sum_mode=False)
    assert single == remove_fraction(1.0 / (1.0 + 12 * (0.05 / 12.0)), 4)


def test_get_factor_useLimit():
    # useLimit 은 GetFactor 안에서 누적값 자체를 240 으로 자른다
    assert get_factor(month=720, sum_mode=True, use_limit=True) == Decimal("240")
    assert get_factor(month=720, sum_mode=True, use_limit=False) == Decimal("332.3359")


def test_라이프니츠는_월복리():
    # 1 / (1 + ratio/12)^n. 같은 기간이면 호프만보다 작다.
    assert cumulative(720, kind=LEIBNIZ) < cumulative(720)


# ---------------------------------------------------------------- 일실수입
def test_기간일실수입():
    # 적용호프만 x 월소득 x 상실률 x (1-생계비), 원 미만 절사
    got = period_income("12.3456", 3_000_000, 38.88, 0)
    # 12.3456 * 3,000,000 * 0.3888 = 14,399,907.0720 -> 원 미만 절사
    assert got == Decimal("14399907")
    assert got == remove_fraction(Decimal("12.3456") * 3_000_000 * Decimal("0.3888"), 0)


def test_사망_생계비_3분의1():
    full = period_income("10", 3_000_000, 100, 0)
    death = period_income("10", 3_000_000, 100, Decimal(1) / Decimal(3))
    assert full == Decimal("30000000")
    assert death == remove_fraction(Decimal("30000000") * (1 - Decimal(1) / Decimal(3)), 0)


# ---------------------------------------------------------------- 끝수처리
def test_끝수처리_두_종류():
    # 누적합은 절사, 적용호프만 차이는 반올림
    assert remove_fraction("112.61359", 4) == Decimal("112.6135")
    assert round_half_even("112.61359", 4) == Decimal("112.6136")


def test_removeFraction_음수는_0방향_절단():
    # C# (int) 캐스트는 floor 가 아니라 0 방향 절단이다
    assert remove_fraction("-123.45", 0) == Decimal("-123")
    assert remove_fraction("123.45", 0) == Decimal("123")
    assert remove_fraction("-0.9999", 2) == Decimal("-0.99")


def test_생계비_분수파싱():
    from engine.fraction import fraction_to_decimal

    assert fraction_to_decimal("1/3") == Decimal(1) / Decimal(3)
    assert fraction_to_decimal("0.5") == Decimal("0.5")
    assert fraction_to_decimal("1 2/3") == Decimal(1) + Decimal(2) / Decimal(3)


# ---------------------------------------------------------------- 노임 기간분할
def test_직종별_반기는_달력반기가_아니다():
    from datetime import date

    from engine.wage_period import occupation_key

    # IncomeCostPopup: <= 4/30 -> half 1, <= 8/31 -> half 2, 그 뒤는 다음해 half 1
    assert occupation_key(date(2025, 4, 30)) == (2025, 1)
    assert occupation_key(date(2025, 5, 1)) == (2025, 2)
    assert occupation_key(date(2025, 8, 31)) == (2025, 2)
    assert occupation_key(date(2025, 9, 1)) == (2026, 1)
    assert occupation_key(date(2025, 12, 31)) == (2026, 1)


def test_농촌은_달력분기():
    from datetime import date

    from engine.wage_period import rural_key

    assert rural_key(date(2025, 3, 31)) == (2025, 1)
    assert rural_key(date(2025, 4, 1)) == (2025, 2)
    assert rural_key(date(2025, 9, 30)) == (2025, 3)
    assert rural_key(date(2025, 10, 1)) == (2025, 4)


def test_기간분할_경계():
    from datetime import date

    from engine.wage_period import split_periods

    got = split_periods(date(2025, 3, 15), date(2026, 1, 31))
    assert [(p.start, p.end) for p in got] == [
        (date(2025, 3, 15), date(2025, 4, 30)),
        (date(2025, 5, 1), date(2025, 8, 31)),
        (date(2025, 9, 1), date(2026, 1, 31)),
    ]
    assert got[0].days == 20                      # normalDayCnt
    assert split_periods(date(2025, 1, 1), date(2025, 1, 1), rural=True)[0].days == 25


# ---------------------------------------------------------------- 반복지출 상한
def test_수치합계_상한은_240_나누기_수명():
    from datetime import date

    from engine.cost import RecurringCost

    acc = date(2014, 10, 26)
    long_run = dict(accident_date=acc, start_date=date(2016, 8, 20), end_date=date(2063, 12, 30))

    # 설명서의 "20" 은 수명 12개월일 때의 값일 뿐이다
    assert RecurringCost(**long_run, cost=Decimal(1), duration_month=12).cap == 20
    assert RecurringCost(**long_run, cost=Decimal(1), duration_month=1).cap == 240
    assert RecurringCost(**long_run, cost=Decimal(1), duration_month=60).cap == 4

    c = RecurringCost(**long_run, cost=Decimal("800000"), duration_month=60)
    assert c.is_capped
    assert c.factor_sum() == Decimal("4.0000")
    assert c.total() == Decimal("3200000")


def test_1회성_지출은_상한에_안_걸린다():
    from datetime import date

    from engine.cost import RecurringCost

    c = RecurringCost(
        accident_date=date(2014, 10, 26),
        start_date=date(2016, 8, 20),
        end_date=date(2016, 8, 20),
        cost=Decimal("5000000"),
        duration_month=12,
    )
    assert not c.is_capped
    assert c.total() == Decimal("4597500")


def test_기왕증_반영():
    from datetime import date

    from engine.cost import RecurringCost

    base = dict(
        accident_date=date(2014, 10, 26),
        start_date=date(2022, 5, 9),
        end_date=date(2063, 12, 30),
        cost=Decimal("4200000"),
        duration_month=120,
    )
    full = RecurringCost(**base).total()
    with_prior = RecurringCost(**base, prior_ratio=Decimal(25)).total()
    assert with_prior == remove_fraction(full * Decimal("0.75"), 0)


# ---------------------------------------------------------------- 기간 계산
def test_초일산입이_기본값():
    from datetime import date

    from engine.dateutil import diff_ymd, months_from

    # isNeedPlus1DayToEndDate 기본 true -> 기간말일에 하루를 더한다
    assert diff_ymd(date(2014, 10, 26), date(2015, 10, 25)).total_months == 12
    y = diff_ymd(date(2014, 10, 26), date(2014, 10, 26))
    assert (y.year, y.month, y.day) == (0, 0, 1)

    # 향후치료비는 명시적으로 끈다
    assert months_from(date(2014, 10, 26), date(2063, 12, 30), plus_one_day=False) == 590


# ---------------------------------------------------------------- 일실수입 순번
def _rows(end, loss="38.88"):
    from datetime import date

    from engine.schedule import build_income_rows

    return build_income_rows(
        date(2025, 3, 15),
        date(2025, 3, 15),
        end,
        lambda p: Decimal("170000"),
        lambda p: Decimal(loss),
    )


def test_순번은_노임변경일마다_끊긴다():
    from datetime import date

    rows = _rows(date(2026, 1, 31))
    assert [(r.start, r.end) for r in rows] == [
        (date(2025, 3, 15), date(2025, 4, 30)),
        (date(2025, 5, 1), date(2025, 8, 31)),
        (date(2025, 9, 1), date(2026, 1, 31)),
    ]
    # 월소득 = 노임단가 x 일수(20)
    assert rows[0].salary == Decimal("3400000")


def test_적용호프만은_구간차이():
    from engine.hoffman import adjust_factor

    rows = _rows(__import__("datetime").date(2026, 1, 31))
    for r in rows:
        assert r.raw_factor == adjust_factor(r.m1, r.m2)


def test_240_누적상한이_순번에_걸린다():
    from datetime import date

    rows = _rows(date(2085, 12, 31))   # 60년 이상 -> 누적이 240 을 넘는다
    assert sum(r.factor for r in rows) == Decimal("240")
    capped = [r for r in rows if r.capped]
    assert capped, "240 상한에 걸린 순번이 있어야 한다"
    # 상한 이후 순번은 0
    after = rows[rows.index(capped[0]) + 1:]
    assert all(r.factor == 0 for r in after)


def test_사망은_생계비_3분의1_공제():
    from datetime import date

    from engine.constants import LIVING_COST_DEATH
    from engine.schedule import build_income_rows, total_income

    args = (date(2025, 3, 15), date(2025, 3, 15), date(2030, 3, 14))
    injury = build_income_rows(*args, lambda p: Decimal("170000"))
    death = build_income_rows(*args, lambda p: Decimal("170000"), living_cost=LIVING_COST_DEATH)
    assert total_income(death) < total_income(injury)


# ---------------------------------------------------------------- 개호비
def test_개호_월비용은_365를_12로_나눈다():
    from datetime import date

    from engine.caregiving import build_caregiving_rows

    # ToBeCaregivingCost.DeciSalary
    #   = decimal.Truncate(_wage * _personCnt * 365m / 12m)
    rows = build_caregiving_rows(
        date(2024, 1, 1), date(2024, 1, 1), date(2024, 12, 31),
        lambda p: 172068, headcount="0.5",
        has_wage=lambda y, i: True,
    )
    assert rows[0].monthly_cost == remove_fraction(
        Decimal(172068) * Decimal("0.5") * Decimal(365) / 12, 0
    )
    assert rows[0].monthly_cost == Decimal("2616867")   # 30일이면 2,581,020


def test_개호_기간분할은_두_방식():
    from datetime import date

    from engine.caregiving import split_caregiving_periods

    # 월 단위 — 개호 시작일의 '일' 에 맞춰 끊는다
    month = split_caregiving_periods(date(2024, 3, 15), date(2025, 6, 30))
    assert (month[0].start, month[0].end) == (date(2024, 3, 15), date(2024, 5, 14))
    assert (month[1].start, month[1].end) == (date(2024, 5, 15), date(2024, 9, 14))

    # 분기·반기 단위 — 달력 경계. 일실수입과 같아진다
    cal = split_caregiving_periods(date(2024, 3, 15), date(2025, 6, 30), month_mode=False)
    assert (cal[0].start, cal[0].end) == (date(2024, 3, 15), date(2024, 4, 30))
    assert (cal[1].start, cal[1].end) == (date(2024, 5, 1), date(2024, 8, 31))
    assert cal[1].index == 2


def test_개호_말일보정():
    from datetime import date

    from engine.caregiving import caregiving_segment_end

    # startDate.Day == 31 이면 4월 30일 / 9월 30일로 보정한다
    end, year, q = caregiving_segment_end(date(2024, 3, 31), rural=True, month_mode=True,
                                          total_start=date(2024, 3, 31))
    assert end == date(2024, 4, 30) and q == 1 and year == 2024
    end, year, h = caregiving_segment_end(date(2024, 7, 31), rural=False, month_mode=True,
                                          total_start=date(2024, 7, 31))
    assert end == date(2024, 9, 30) and h == 2 and year == 2024


def test_개호_직종별_말일보정후_기준일이_바뀐다():
    from datetime import date

    from engine.caregiving import split_caregiving_periods

    # <=4.30. 분기만 totalStartDate.Day 를 쓰고 9.1.~12.31. 분기는 startDate.Day 를 쓴다.
    # 시작일이 31일이면 말일 보정(9.30.)으로 다음 구간이 10.1. 이 되고,
    # 그때부터 1일 기준으로 끊긴다.
    got = split_caregiving_periods(date(2024, 7, 31), date(2026, 12, 31))
    assert (got[0].start, got[0].end) == (date(2024, 7, 31), date(2024, 9, 30))
    assert (got[1].start, got[1].end) == (date(2024, 10, 1), date(2025, 4, 30))
    assert (got[2].start, got[2].end) == (date(2025, 5, 1), date(2025, 8, 31))


def test_개호_분기반기모드는_일실수입과_같다():
    from datetime import date

    from engine.caregiving import split_caregiving_periods
    from engine.wage_period import split_periods

    care = split_caregiving_periods(date(2024, 3, 15), date(2026, 12, 31), month_mode=False)
    income = split_periods(date(2024, 3, 15), date(2026, 12, 31))
    assert [(p.start, p.end, p.year, p.index) for p in care] == \
           [(p.start, p.end, p.year, p.index) for p in income]


def test_개호_노임연도는_자르기_전_기준_직종별만():
    from datetime import date

    from engine.caregiving import split_caregiving_periods

    # 개호 종료일(2026.12.31.)이 구간 경계(2027.4.30.)보다 앞이라 잘린다.
    # 직종별은 자르기 전 연도(2027)를 그대로 쓰고, 농촌은 자른 뒤 연도를 쓴다.
    job = split_caregiving_periods(date(2024, 3, 15), date(2026, 12, 31), month_mode=False)
    assert job[-1].end == date(2026, 12, 31) and job[-1].year == 2027

    rural = split_caregiving_periods(date(2024, 3, 15), date(2026, 12, 31),
                                     rural=True, month_mode=False)
    assert rural[-1].end == date(2026, 12, 31) and rural[-1].year == 2026
