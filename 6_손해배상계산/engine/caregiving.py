"""개호비 — 기왕 개호비와 향후 개호비.

원본: SUT.SBGCalc.Model.SBGCalc.ToBeCaregivingCost

향후 개호비는 치료비가 아니라 **일실수입과 같은 구조**다. 필요일마다 단일 계수를
더하는 방식이 아니라, 기간을 나누고 구간마다 H(m1) - H(m2) 를 쓴다.

    _hoffmanLeibniz2 = HoffmanLeibnizUtil.GetFactor(_type, (int)_m2, _statutoryRateRatio, sumMode: true);
    AdjustHoffmanLeibniz = Math.Round(_hoffmanLeibniz1 - _hoffmanLeibniz2, 4).ToString();
    ...
    double presentHoff = Math.Round(_hoffmanLeibniz1 - _hoffmanLeibniz2, 4);
    if (FractionUtil.RemoveFraction(value, 4) + presentHoff >= 240.0)

엑셀표저장의 '개호비' 시트 컬럼도 일실수입과 같다.

    순번 기간초일 기간말일 개호비단가 인원 기왕증(%) 월비용 M1 호프만1 M2 호프만2 M1-M2 적용호프만 기간개호비

설명서 23쪽: "일실수입과 마찬가지로 노임단가 변동시점에 따라 기간을 나누고,
각 기간별 개호비를 자동 계산하여 준다", "일실수입과 마찬가지로 과잉배상 방지를
위해 적용호프만이 240으로 제한된다".

월비용은 ToBeCaregivingCost 안에서 만들어진다. 팝업은 단가와 인원만 넘긴다.

    public decimal DeciSalary => decimal.Truncate(_wage * (decimal)_personCnt * 365m / 12m);

    월비용 = 절사(개호비 단가 x 인원 x 365 / 12)

일수가 30일이 아니라 **365/12 = 30.4166...** 이다. 개호는 매일 필요하므로 1년치를
12로 나눈 값을 한 달로 본다. `decimal.Truncate` 는 0 방향 절단이다.

기간분할은 **일실수입과 다르고, 화면의 `chkMonth` 체크박스로 두 방식이 갈린다.**

  월 단위 (chkMonth 체크)  — 개호 시작일의 '일' 에 맞춰 끊는다
      농촌   <=3.31. -> 4월 D일 전날 (D=31이면 4.30.) / <=6.30. -> 7월 D일 전날
             <=9.30. -> 10월 D일 전날 / <=12.31. -> 익년 1월 D일 전날
             그 밖   -> 익년 4월 D일 전날 (D=31이면 익년 4.30.)
      직종별 <=4.30. -> 5월 D일 전날 / <=8.31. -> 9월 D일 전날 (D=31이면 9.30.)

  분기·반기 단위 (체크 해제) — 달력 경계로 끊는다
      농촌   3.31. / 6.30. / 9.30. / 12.31. / 익년 3.31.
      직종별 4.30. / 8.31. (추정)

노임 조회는 구간의 **기간말일 연도**를 쓴다. 분기·반기만 분기 판정에서 정해진다.

    year = endDate.Year;
    wage = DBHelper.GetWageFromSalaryDayTable(jikCd, endDate.Year, quarter);

다음 구간의 단가가 없으면 가동종료일까지 확장하는 것은 일실수입과 같다.

    nextWage = GetWageFromSalaryDayTable(jikCd, nextYear, nextQuarter);
    if (wage == -1m)     { wage = GetWageFromSalaryDayTableNext(jikCd); endDate = totalEndDate; }
    if (nextWage == -1m) { endDate = totalEndDate; }

직종별 월 단위의 한 가지 함정: `<=4.30.` 분기만 **totalStartDate.Day**(개호 전체
시작일)를 쓰고, `9.1.~12.31.` 분기는 **startDate.Day**(현재 구간 시작일)를 쓴다.

    endDate = new DateTime(startDate.Year, 5, totalStartDate.Day).AddDays(-1.0);   // <=4.30.
    endDate = new DateTime(startDate.Year + 1, 5, startDate.Day).AddDays(-1.0);    // 그 밖

보통은 두 값이 같지만, 시작일이 31일이라 말일 보정(9.30.)이 걸리면 다음 구간의
시작일이 10월 1일이 되어 갈라진다. 그때부터는 1일 기준으로 끊긴다.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Callable

from datetime import timedelta

from .dateutil import months_from
from .fraction import remove_fraction
from .hoffman import HOFFMAN, LEGAL_RATE, MONTHLY_CAP, adjust_factor
from .wage_period import WagePeriod

# 월비용 = 절사(단가 x 인원 x 365/12).  ToBeCaregivingCost.DeciSalary 그대로.
MONTHLY_DAYS = Decimal(365) / Decimal(12)


def _day_or_month_end(year: int, month: int, day: int) -> date:
    """new DateTime(year, month, day) 에 해당. 그 달에 없는 날이면 말일로."""
    last = [31, 29 if (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)) else 28,
            31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1]
    return date(year, month, min(day, last))


def caregiving_segment_end(start: date, rural: bool, month_mode: bool, total_start: date):
    """구간의 (기간말일, 노임조회 연도, 분기/반기 번호). CaregivingCostPopup 그대로.

    돌려주는 기간말일은 **개호 종료일로 자르기 전** 값이다. 연도도 그 시점에
    정해지므로, 잘라낸 뒤의 말일 연도와 달라질 수 있다.
    """
    y, d = start.year, start.day
    prev = lambda dt: dt - timedelta(days=1)

    if rural:
        if month_mode:
            if start <= date(y, 3, 31):
                end = date(y, 4, 30) if d == 31 else prev(_day_or_month_end(y, 4, d))
                return end, y, 1
            if start <= date(y, 6, 30):
                return prev(_day_or_month_end(y, 7, d)), y, 2
            if start <= date(y, 9, 30):
                return prev(_day_or_month_end(y, 10, d)), y, 3
            if start <= date(y, 12, 31):
                return prev(_day_or_month_end(y + 1, 1, d)), y, 4
            end = date(y + 1, 4, 30) if d == 31 else prev(_day_or_month_end(y + 1, 4, d))
            return end, y + 1, 1
        for boundary, q in ((date(y, 3, 31), 1), (date(y, 6, 30), 2),
                            (date(y, 9, 30), 3), (date(y, 12, 31), 4)):
            if start <= boundary:
                return boundary, boundary.year, q
        return date(y + 1, 3, 31), y + 1, 1

    if month_mode:
        if start <= date(y, 4, 30):
            # 이 분기만 totalStartDate.Day 를 쓴다. 나머지는 startDate.Day 다.
            return prev(_day_or_month_end(y, 5, total_start.day)), y, 1
        if start <= date(y, 8, 31):
            end = date(y, 9, 30) if d == 31 else prev(_day_or_month_end(y, 9, d))
            return end, y, 2
        return prev(_day_or_month_end(y + 1, 5, d)), y + 1, 1
    if start <= date(y, 4, 30):
        return date(y, 4, 30), y, 1
    if start <= date(y, 8, 31):
        return date(y, 8, 31), y, 2
    return date(y + 1, 4, 30), y + 1, 1


def split_caregiving_periods(
    start: date, end: date, rural: bool = False, month_mode: bool = True, has_wage=None
) -> list[WagePeriod]:
    """개호 기간을 노임 변경 시점으로 쪼갠다.

    원본은 `while (startDate < totalEndDate)` 이고, 구간이 종료일을 넘으면 잘라낸다.

    노임 조회 연도가 농촌과 직종별에서 다르다.

        농촌   자른 뒤에 다시 `year = endDate.Year;` 로 덮어쓴다  -> 잘린 말일의 연도
        직종별 그 덮어쓰기가 없다                                  -> 자르기 전 연도

    개호 종료일이 구간 경계보다 앞이면 이 차이가 드러난다.

    현재 구간의 단가도 없으면(원본의 `wage == -1m`) 그 키를 그대로 담아 종료일까지 한 순번으로
    묶는다. 키가 노임표의 마지막 공표 키보다 뒤이면 조회기(cli._wage_lookup)가 마지막 단가
    (원본의 GetWageFromSalaryDayTableNext)를 돌려주고, 앞인데 빠진 키면 알아볼 수 있는 오류로 멈춘다.
    """
    out: list[WagePeriod] = []
    cur = start
    while cur < end:
        seg_end, branch_year, index = caregiving_segment_end(cur, rural, month_mode, start)
        if seg_end > end:
            seg_end = end
        year = seg_end.year if rural else branch_year
        if has_wage is not None:
            # 농촌   nextQuarter = (quarter == 4) ? 1 : quarter + 1
            #        nextYear    = (quarter == 4) ? tmpEnd.AddYears(1).Year : tmpEnd.Year
            # 직종별 nextHalf    = (half == 1) ? 2 : 1
            #        nextYear    = (half == 1) ? tmpEnd.Year : tmpEnd.AddYears(1).Year
            nxt = seg_end + timedelta(days=1)
            rolls = (index == 4) if rural else (index != 1)
            n_year = nxt.year + 1 if rolls else nxt.year
            n_index = 1 if rolls else index + 1
            if not has_wage(year, index) or not has_wage(n_year, n_index):
                out.append(WagePeriod(cur, end, year, index, rural))
                break
        out.append(WagePeriod(cur, seg_end, year, index, rural))
        cur = seg_end + timedelta(days=1)
    return out


def past_caregiving(unit_price, total_days, prior_ratio=0, actual_spent=None) -> Decimal:
    """기왕 개호비.

    설명서 22~23쪽: 직종을 선택하고 총 일수를 입력하면 사고일 기준 단가로 계산된다.
    계산된 개호비보다 실제지출 개호비가 더 적으면 그 금액이 적용 개호비가 된다.
    기왕증이 있으면 반영한다.
    """
    calculated = remove_fraction(
        Decimal(str(unit_price)) * Decimal(str(total_days)) * (1 - Decimal(str(prior_ratio)) / 100),
        0,
    )
    if actual_spent is None:
        return calculated
    return min(calculated, Decimal(str(actual_spent)))


@dataclass
class CaregivingRow:
    """향후 개호비 한 순번. 개호비 시트의 한 행."""

    step: int
    start: date
    end: date
    unit_price: Decimal
    headcount: Decimal
    prior_ratio: Decimal
    monthly_cost: Decimal
    m1: int
    m2: int
    raw_factor: Decimal
    factor: Decimal
    amount: Decimal

    @property
    def capped(self) -> bool:
        return self.factor != self.raw_factor


def build_caregiving_rows(
    accident_date: date,
    start: date,
    end: date,
    unit_price_of: Callable[[WagePeriod], Decimal],
    headcount: Decimal | float | str = 1,
    prior_ratio: Decimal | float | str = 0,
    rural: bool = False,
    ratio: float = LEGAL_RATE,
    kind: str = HOFFMAN,
    has_wage=None,
    monthly_days=MONTHLY_DAYS,
    month_mode: bool = True,
) -> list[CaregivingRow]:
    """향후 개호비 순번을 만든다. 일실수입과 같은 방식으로 240 상한을 건다.

    설명서 24쪽처럼 기간별로 인원을 달리하려면 구간을 나눠 여러 번 호출하고
    이어 붙이면 된다. 그때는 saved 를 이어받아야 하므로 chain_caregiving 을 쓴다.
    """
    head = Decimal(str(headcount))
    prior = Decimal(str(prior_ratio))
    rows: list[CaregivingRow] = []
    saved = Decimal(0)

    for step, p in enumerate(
        split_caregiving_periods(start, end, rural, month_mode, has_wage), 1
    ):
        m2 = months_from(accident_date, p.start)
        m1 = months_from(accident_date, p.end)
        raw = adjust_factor(m1, m2, ratio, kind)

        factor = raw
        if saved >= MONTHLY_CAP:
            factor = Decimal(0)
        elif saved + factor >= MONTHLY_CAP:
            factor = MONTHLY_CAP - saved
        saved += factor

        unit = Decimal(str(unit_price_of(p)))
        # DeciSalary = decimal.Truncate(_wage * _personCnt * 365m / 12m)
        monthly = remove_fraction(unit * head * Decimal(str(monthly_days)), 0)
        amount = remove_fraction(factor * monthly * (1 - prior / 100), 0)
        rows.append(
            CaregivingRow(
                step=step,
                start=p.start,
                end=p.end,
                unit_price=unit,
                headcount=head,
                prior_ratio=prior,
                monthly_cost=monthly,
                m1=m1,
                m2=m2,
                raw_factor=raw,
                factor=factor,
                amount=amount,
            )
        )
    return rows


def total_caregiving(rows: list[CaregivingRow]) -> Decimal:
    return sum((r.amount for r in rows), Decimal(0))
