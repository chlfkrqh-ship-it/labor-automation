"""향후치료비·보조구 — 반복지출의 수치합계와 상한.

원본: SUT.SBGCalc.Model.SBGCalc.ToBeTreatmentCost.getTotalCost()

    if (_durationMonth != 0) {
        while (tmpDate <= _endDate) {
            DateUtil.GetDiffDaysString(_accidentDate, tmpDate, ref ymdClass, isNeedPlus1DayToEndDate: false);
            i = ymdClass.Year * 12 + ymdClass.Month;
            if (i < 0) i = 0;
            _adjustHoffmanLeibniz += HoffmanLeibnizUtil.GetFactor(_ratioType, i, _statutoryRateRatio);
            tmpDate = tmpDate.AddMonths(_durationMonth);
        }
        _adjustHoffmanLeibniz = (_adjustHoffmanLeibniz > 240.0 / _durationMonth)
                                ? (240.0 / _durationMonth) : _adjustHoffmanLeibniz;
        if (_adjustHoffmanLeibniz > 240.0) _adjustHoffmanLeibniz = 240.0;
    }
    _adjustHoffmanLeibniz = FractionUtil.RemoveFraction(_adjustHoffmanLeibniz, 4);
    return RemoveFraction(_cost * _adjustHoffmanLeibniz * (1 - _existingLossContributionRatio), 0);

*** 상한은 20 이 아니라 240 / 수명(월) 이다. ***

설명서 25쪽은 "수치합계가 20을 초과하면 20으로 제한된다"고만 적었는데, 그건
수명이 12개월(연 1회 지출)인 경우다.  240/12 = 20.  수명이 다르면 상한도 달라진다.

    수명  1개월  -> 상한 240
    수명 12개월  -> 상한  20     (설명서에 실린 값)
    수명 60개월  -> 상한   4

일실수입의 240 상한(월단위 누적)과 같은 취지를 지출 주기에 맞춰 환산한 것이다.

주의: 여기 쓰이는 GetFactor 는 sumMode 를 넘기지 않으므로 **누적합이 아니라 해당
월의 계수 1개**다. 필요일마다 그 시점의 현가계수를 하나씩 더한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from .dateutil import months_from
from .fraction import remove_fraction
from .hoffman import HOFFMAN, LEGAL_RATE, get_factor


def add_months(d: date, n: int) -> date:
    """DateTime.AddMonths — 말일 보정 포함."""
    total = (d.year * 12 + d.month - 1) + n
    year, month = divmod(total, 12)
    month += 1
    if month == 2:
        last = 29 if (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)) else 28
    elif month in (4, 6, 9, 11):
        last = 30
    else:
        last = 31
    return date(year, month, min(d.day, last))


@dataclass
class RecurringCost:
    """반복 또는 1회성 지출 1건 (치료비 항목, 보조구 종류).

    1회성이면 최초 필요일과 최종 필요일을 같게 두면 된다(설명서 25쪽).
    """

    accident_date: date
    start_date: date          # 최초 필요일
    end_date: date            # 최종 필요일
    cost: Decimal             # 1회 비용(단가)
    duration_month: int       # 수명(월)
    prior_ratio: Decimal = Decimal(0)   # 기왕증 기여도 (%, 0~100)
    kind: str = HOFFMAN
    ratio: float = LEGAL_RATE

    @property
    def cap(self) -> Decimal:
        """수치합계 상한 = 240 / 수명(월)."""
        if self.duration_month == 0:
            return Decimal(0)
        return Decimal(240) / Decimal(self.duration_month)

    def raw_factor_sum(self) -> Decimal:
        """상한 적용 전 수치합계."""
        if self.duration_month == 0:
            return Decimal(0)
        total = Decimal(0)
        cur = self.start_date
        while cur <= self.end_date:
            # 향후치료비는 isNeedPlus1DayToEndDate: false 로 부른다
            i = months_from(self.accident_date, cur, plus_one_day=False)
            total += get_factor(self.kind, i, self.ratio)   # sum_mode=False, 단일 계수
            cur = add_months(cur, self.duration_month)
        return total

    def factor_sum(self) -> Decimal:
        """수치합계. 상한 적용 후 4자리 절사."""
        total = self.raw_factor_sum()
        if self.duration_month == 0:
            return remove_fraction(0, 4)
        if total > self.cap:
            total = self.cap
        if total > 240:
            total = Decimal(240)
        return remove_fraction(total, 4)

    @property
    def is_capped(self) -> bool:
        """상한에 걸렸는지. 프로그램은 이때 수치합계를 빨간색으로 표시한다."""
        return self.raw_factor_sum() > self.cap

    def total(self) -> Decimal:
        """비용총액 = 1회비용 x 수치합계 x (1 - 기왕증기여도), 원 미만 절사."""
        return remove_fraction(
            self.cost * self.factor_sum() * (1 - self.prior_ratio / 100), 0
        )
