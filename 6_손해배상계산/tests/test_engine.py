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
    assert Impairment(13.0, years=2).as_permanent_rate() == Decimal("2.6")


def test_단일_장해는_부동소수점_오차로_깎이지_않는다():
    # float 로 1 - (1 - 0.10) 을 구하면 9.999999999999998 -> 절사 9.99 가 된다
    for rate in (8, 10, 20, 45, 58):
        assert truncate2(combined_with_prior([Impairment(float(rate))])) == Decimal(rate)
    wrong = [r for r in range(1, 101) if truncate2(combined_with_prior([Impairment(r)])) != r]
    assert wrong == []


def test_중복장해율과_기왕증_기여도는_10진수로_계산한다():
    # 1 - 0.99 x 0.92 = 0.0892 -> 8.92 (float 로는 8.91)
    assert truncate2(combined_with_prior([Impairment(1), Impairment(8)])) == Decimal("8.92")
    # 10% 중 기왕증 30% -> 기여도 30 (float 로는 29.99)
    assert truncate2(prior_contribution([Impairment(10, prior=30)])) == Decimal("30.00")
    assert truncate2(combined_with_prior([Impairment(1, prior=5)])) == Decimal("0.95")


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


# ================================================================ 사건 전체 계산 (감사 수정 회귀)
# 아래는 골든 케이스 3(검증 목적으로 만든 가상 사건)의 입력과 data/ 의 공개 노임표·생명표를 쓴다.
from datetime import date

import openpyxl
import pytest

from tests.golden import case_fault_deduction as F


def _case(**kw):
    """골든 케이스 3 입력으로 만든 사건. kw 로 항목을 바꾼다."""
    from engine.case import Case, ImpairmentInput

    base = dict(
        case_no="2024가단1", name="홍길동", birth=F.BIRTH, accident=F.ACCIDENT,
        cure_end=F.CURE_END, life_expectancy=F.LIFE_EXPECTANCY, life_end=F.LIFE_END,
        impairments=[ImpairmentInput(d, Decimal(r), Decimal(p or 0)) for d, r, p, *_ in F.IMPAIRMENTS],
        wages={f"{y}-{i}": v for (y, i), v in F.WAGES.items()},
        fault_rate=F.FAULT_RATE, paid_cure=F.PAID_CURE, advance=F.ADVANCE,
        solatium=F.SOLATIUM_APPLIED,
    )
    base.update(kw)
    return Case(**base)


def _lookup(case):
    """노임 직접입력 표의 조회기. cli·watch 의 직접입력 경로와 같은 모양이다."""
    table = {tuple(int(x) for x in k.split("-")): v for k, v in case.wages.items()}
    last = table[max(table)]
    return (lambda p: table.get((p.year, p.index), last)), (lambda y, i: (y, i) in table)


def _calc(case, **kw):
    from engine.calculate import calculate

    return calculate(case, *_lookup(case), **kw)


def _book(result, tmp_path):
    from engine.excel import write_workbook

    return openpyxl.load_workbook(write_workbook(result, tmp_path / "계산표.xlsx"))


def _first_row(ws, text, col=2):
    return next(r for r in range(1, ws.max_row + 1) if ws.cell(r, col).value == text)


def test_계산은_장해율을_10진수로_넘긴다():
    from engine.case import ImpairmentInput

    r = _calc(_case(impairments=[ImpairmentInput("정형외과", Decimal(10))]))
    assert r.combined_rate == Decimal("10.00")
    assert [x.loss_rate for x in r.income_rows][2:] == [Decimal("10.00")] * 4


# ---------------------------------------------------------------- 노임표 조회 (data/)
def _wage_table():
    from engine.tables import WageTable

    return WageTable.load()


def test_직종은_이름이_같은_것을_고른다():
    wt = _wage_table()
    # 부분일치의 첫 항목을 쓰면 원자력배관공·원자력특별인부·특고압케이블전공 등이 뽑혔다
    for name, oid in [("배관공", "7204"), ("특별인부", "6736"), ("고압케이블전공", "7698"),
                      ("비계공", "6775"), ("용접공", "6853"), ("타일공", "7061"), ("석공", "7126")]:
        assert [o["id"] for o in wt.find_occupation(name)] == [oid], name


def test_노임표의_모든_직종이_자기_이름으로_풀린다():
    wt = _wage_table()
    for o in wt.occupations:
        found = wt.find_occupation(o["name"])
        assert o in found and all(f["name"] == o["name"] for f in found), o["name"]


def test_이름이_같은_계열은_최근_계열부터_이어서_찾는다():
    wt = _wage_table()
    assert [o["id"] for o in wt.find_occupation("제철축로공")] == ["7555", "3922"]
    assert wt.find_occupation("전기공사기사")[0]["id"] == "8257"
    # 원본은 직종 이름으로 단가를 찾는다 — 최근 계열 id 로도 2009년 단가가 나온다
    assert wt.occupation_wage("7555", 2009, 2) == wt.occupation_wage("3922", 2009, 2)


def test_부분일치로는_직종을_고르지_않는다():
    from engine.tables import OccupationNotFound

    wt = _wage_table()
    assert wt.find_occupation("용접") == []
    assert wt.find_occupation("") == []
    with pytest.raises(OccupationNotFound, match="용접공"):
        wt.resolve_occupation("용접")
    assert wt.resolve_occupation("배관공")[0]["id"] == "7204"


def test_노임표에_없는_반기는_이유를_적고_멈춘다():
    wt = _wage_table()
    # 원자력배관공은 2024-2 까지만 단가가 있고 플랜트배관공으로 통합됐다
    with pytest.raises(KeyError, match="플랜트배관공"):
        wt.occupation_wage("4773", 2025, 1)


def test_노임표_단가():
    wt = _wage_table()
    assert wt.occupation_wage("6736", 2026, 1) == 226122      # 특별인부
    assert wt.occupation_wage("7698", 2026, 1) == 373640      # 고압케이블전공
    assert (wt.rural_wage(2026, 1, "M"), wt.rural_wage(2026, 1, "F")) == (153783, 122176)
    # 도시일용(TB_SUT001)은 보통인부(TB_SUT004) 반기 단가와 같다. 1·2분기가 상반기, 3·4분기가 하반기
    common = wt.find_occupation("보통인부")[0]["id"]
    assert wt.city_wage(2025, 2) == wt.occupation_wage(common, 2025, 1) == 169804
    assert wt.city_wage(2025, 3) == wt.occupation_wage(common, 2025, 2) == 171037


def test_생명표_기대여명():
    from engine.tables import LifeTable

    lt = LifeTable.load()
    assert lt.expectancy(2024, 34, "M") == float(F.LIFE_EXPECTANCY)   # 2024년 생명표 34세 남
    assert lt.expectancy(2024, 34, "F") > lt.expectancy(2024, 34, "M")


def test_직종만_적은_사건은_그_직종_노임으로_계산한다():
    # 노임을 직접 넣지 않은 기본 경로: 직종명 -> find_occupation -> occupation_wage
    from engine.calculate import calculate

    wt = _wage_table()
    case = _case(occupation="배관공", wages={})
    oid = wt.find_occupation(case.occupation)[0]["id"]

    def wage_of(p):
        return wt.occupation_wage(oid, p.year, p.index)

    def has_wage(y, i):
        try:
            wt.occupation_wage(oid, y, i)
            return True
        except KeyError:
            return False

    r = calculate(case, wage_of, has_wage)
    assert [int(x.wage) for x in r.income_rows[:6]] == [229482, 229664, 229664, 238145, 239439, 247897]
    assert r.wage_basis == "직종별 노임 — 배관공"


# ---------------------------------------------------------------- 향후 개호비 단가
CARE = dict(caregiving_start=date(2026, 1, 1), caregiving_end=date(2045, 12, 31))


def test_향후_개호비는_피해자_노임으로_대신하지_않는다():
    with pytest.raises(ValueError, match="caregiving_wages"):
        _calc(_case(occupation="철근공", **CARE))


def test_향후_개호비는_개호_노임단가_표로_계산한다():
    victim = {k: v * 2 for k, v in _case().wages.items()}     # 피해자 직종 노임(개호 단가와 다름)
    r = _calc(_case(wages=victim, caregiving_wages={"2025-2": 171037, "2026-1": 172068}, **CARE))
    assert [(x.start, x.end, x.unit_price) for x in r.caregiving_rows] == [
        (date(2026, 1, 1), date(2045, 12, 31), Decimal(172068))
    ]
    assert r.caregiving_basis == "개호 노임단가 직접입력(반기)"


def test_개호_단가가_농촌_분기면_분기로_나눈다():
    # 피해자는 직종별(반기)이어도 개호 표가 분기면 분기 경계와 개호 표의 단가 유무로 나눈다
    r = _calc(_case(caregiving_rural=True, caregiving_wages={
        "2025-4": 122880, "2026-1": 122176, "2026-2": 124927}, **CARE))
    assert [(x.start, x.end, x.unit_price) for x in r.caregiving_rows] == [
        (date(2026, 1, 1), date(2026, 3, 31), Decimal(122176)),
        (date(2026, 4, 1), date(2045, 12, 31), Decimal(124927)),
    ]


def test_개호_노임단가_표를_검사한다():
    for wages, text in [({"2026-3": 1}, "caregiving_rural"),
                        ({"2024-1": 1, "2025-1": 1}, "2024-2"),
                        ({"2026-2": 1}, "2026년 1반기"),
                        ({"2026/1": 1}, "형식")]:
        with pytest.raises(ValueError, match=text):
            _calc(_case(caregiving_wages=wages, **CARE))


def test_호출자가_넘긴_개호_단가_조회기를_쓴다():
    r = _calc(_case(**CARE), caregiving_price_of=lambda p: 150000,
              caregiving_has_wage=lambda y, i: True, caregiving_basis="도시일용(보통인부)")
    assert r.caregiving_rows and all(x.unit_price == 150000 for x in r.caregiving_rows)
    assert r.caregiving_basis == "도시일용(보통인부)"


# ---------------------------------------------------------------- 여명단축
def test_여명단축_구간은_상실률_66_66666666():
    from engine.constants import SHORTENED_LIFE_LOSS_RATE

    r = _calc(_case(life_end=date(2035, 12, 31)))
    before = [x for x in r.income_rows if x.end <= date(2035, 12, 31)]
    after = [x for x in r.income_rows if x.start > date(2035, 12, 31)]
    assert before[-1].end == date(2035, 12, 31) and after[0].start == date(2036, 1, 1)
    assert [x.loss_rate for x in after] == [SHORTENED_LIFE_LOSS_RATE]
    # 여명 종료 전 순번은 골든 케이스 3과 같다(6순번만 여명 종료일에서 끊긴다)
    for x, g in zip(before[:5], F.INCOME_ROWS[:5]):
        assert x.amount == g[12]
    assert before[5].loss_rate == F.COMBINED_RATE
    assert sum(x.factor for x in r.income_rows) <= 240
    assert any("여명단축" in w for w in r.warnings)


def test_여명_종료일이_가동종료일_뒤면_그대로다():
    r = _calc(_case())
    assert r.income_total == F.INCOME_TOTAL and r.warnings == []


def test_여명_종료일이_입원치료_종료일_이전이면_멈춘다():
    with pytest.raises(ValueError, match="대법원 프로그램"):
        _calc(_case(life_end=date(2024, 5, 31)))


def test_사망_사건은_여명_종료일로_나누지_않는다():
    r = _calc(_case(injury_type="사망", cure_end=None, impairments=[], life_end=date(2035, 12, 31)))
    assert all(x.loss_rate == 100 for x in r.income_rows)
    assert not any("여명단축" in w for w in r.warnings)


# ---------------------------------------------------------------- 2월 29일생
def test_2월29일생_가동종료일은_정하지_않고_멈춘다():
    from engine.case import Case

    with pytest.raises(ValueError, match="work_end") as err:
        Case(birth=date(1996, 2, 29), accident=date(2024, 1, 1)).resolved_work_end()
    assert "2061. 2. 28." in str(err.value) and "2061. 2. 27." in str(err.value)
    # 가동종료일을 적으면 그 값을 쓴다. 가동연한이 끝나는 해가 윤년이면 대응일이 있다
    assert Case(birth=date(1996, 2, 29), work_end=date(2061, 2, 28)).resolved_work_end() == date(2061, 2, 28)
    assert Case(birth=date(1996, 2, 29), work_limit_years=64).resolved_work_end() == date(2060, 2, 28)
    r = _calc(_case(birth=date(1996, 2, 29), work_end=date(2061, 2, 28)))
    assert r.income_rows[-1].end == date(2061, 2, 28)


# ---------------------------------------------------------------- 사건 파일 -> 계산 -> 계산표
EXTRA = """
past_treatment: 3000000
treatments:
  - {name: 물리치료, cost: 300000, first: 2025-01-01, last: 2034-12-31, duration_month: 12}
  - {name: 반흔교정술, cost: 2000000, first: 2025-10-30}
  - {name: 약제, cost: 10000, first: 2025-01-01, last: 2025-12-31, repeating: false}
orthoses:
  - {name: 의족, cost: 3000000, first: 2025-01-01, last: 2054-12-31, duration_month: 60}
past_caregiving_days: 30
past_caregiving_price: 150000
past_caregiving_actual: 4000000
caregiving_start: 2024-07-01
caregiving_end: 2054-12-31
caregiving_headcount: 0.5
caregiving_wages:
  "2024-2": 167081
  "2025-1": 169804
  "2025-2": 171037
  "2026-1": 172068
"""


def _loaded(tmp_path):
    from engine.case import load

    root = Path(__file__).resolve().parent.parent
    path = tmp_path / "사건.yaml"
    path.write_text((root / "cases" / "sample.yaml").read_text(encoding="utf-8") + EXTRA,
                    encoding="utf-8")
    return load(path)


def test_사건파일의_치료비_구분과_개호_단가표를_읽는다(tmp_path):
    case = _loaded(tmp_path)
    # repeating 을 적지 않으면 최종 필요일이 최초 필요일과 다른지로 정한다(입력서와 같다)
    assert [t.repeating for t in case.treatments] == [True, False, False]
    assert case.caregiving_wages["2026-1"] == 172068 and case.caregiving_rural is False


def test_적극손해를_사건파일부터_계산표까지_잇는다(tmp_path):
    case = _loaded(tmp_path)
    r = _calc(case)
    assert r.treatment_total == sum(c.total() for c in r.treatment_rows) > 0
    assert r.orthosis_total == sum(c.total() for c in r.orthosis_rows) > 0
    assert r.future_caregiving_total == sum(x.amount for x in r.caregiving_rows) > 0
    assert r.past_caregiving_total == Decimal(3946500)      # min(150,000 x 30 x (1 - 12.3%), 4,000,000)
    assert r.active_total == (case.past_treatment + r.treatment_total + r.past_caregiving_total
                              + r.future_caregiving_total + r.orthosis_total)
    assert r.property_damage == r.income_total + r.active_total

    wb = _book(r, tmp_path)

    def total(sheet, label):
        ws = wb[sheet]
        return ws.cell(_first_row(ws, label), 11).value

    assert total("치료비", "향후 치료비 합계 : ") == int(r.treatment_total)
    assert total("보조구", "향후 보조구 합계 : ") == int(r.orthosis_total)
    assert total("개호비", "향후 개호비 합계 : ") == int(r.future_caregiving_total)
    assert total("개호비", "기왕 개호비 합계 : ") == int(r.past_caregiving_total)
    ws = wb["치료비"]
    assert [ws.cell(_first_row(ws, t.name), 3).value for t in case.treatments] == ["반복", "1회", "1회"]
    ws = wb["개호비"]
    assert ws.cell(_first_row(ws, "[향후 개호비]"), 4).value == "개호비 단가 기준 : 개호 노임단가 직접입력(반기)"

    ws = wb["종합"]
    start, end = _first_row(ws, "[적극손해]"), _first_row(ws, "적극손해 합계 : ")
    assert sum(ws.cell(row, 5).value or 0 for row in range(start + 1, end)) == ws.cell(end, 14).value
    assert ws.cell(end, 14).value == int(r.active_total)


# ---------------------------------------------------------------- 계산표 표시
def test_위자료_표는_과실상계_공제_뒤_금액을_쓴다(tmp_path):
    wb = _book(_calc(_case()), tmp_path)
    ws = wb["종합"]
    row = next(rr for rr in range(1, ws.max_row + 1)
               if ws.cell(rr, 2).value == 1 and ws.cell(rr, 3).value == "홍길동")
    assert ws.cell(row, 4).value == int(F.SOLATIUM_AUTO)
    assert ws.cell(row, 8).value == int(F.PROPERTY_FINAL)      # 과실상계 전 362,157,144 가 아니다
    assert ws.cell(row, 10).value == int(F.GRAND_TOTAL)
    # 확인할 점이 없으면 '경고' 시트를 두지 않는다
    assert "경고" not in wb.sheetnames and ws["B3"].value is None
    assert ws.cell(_first_row(ws, "[일실수입]"), 4).value == "노임 기준 : 노임단가 직접입력"


def test_한시장해만_있으면_머리글을_덮어쓰지_않는다(tmp_path):
    from engine.case import ImpairmentInput

    r = _calc(_case(impairments=[ImpairmentInput("정형외과", Decimal(30), years=Decimal(3))]))
    ws = _book(r, tmp_path)["종합"]
    head = _first_row(ws, "진료과")
    assert ws.cell(head, 7).value == "중복장해(%)" and ws.cell(head, 11).value == "기왕증 기여도(%)"
    assert ws.cell(head + 1, 7).value == 9                     # 30% x 3년/10년


def test_경고는_계산표_경고_시트에_남긴다(tmp_path):
    wb = _book(_calc(_case(life_end=date(2035, 12, 31))), tmp_path)
    assert wb.sheetnames[-1] == "경고"
    assert "여명단축" in wb["경고"]["A3"].value
    assert "1건" in wb["종합"]["B3"].value


def test_노임단가_0원_순번은_경고한다():
    from engine.calculate import calculate

    case = _case()
    wage_of, has_wage = _lookup(case)
    r = calculate(case, lambda p: 0 if (p.year, p.index) == (2025, 1) else wage_of(p), has_wage)
    assert any("노임단가가 0원" in w and "순번 4" in w for w in r.warnings)
