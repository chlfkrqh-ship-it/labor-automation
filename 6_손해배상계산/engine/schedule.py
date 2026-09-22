"""일실수입 순번 조립.

원본: SUT.SBGCalc.View.Popup.IncomeCostPopup 의 자동입력 흐름

    노임단가 변경일마다 순번을 나누고, 순번마다
        m2 = 사고일자 ~ 기간초일 개월수
        m1 = 사고일자 ~ 기간말일 개월수
        적용호프만 = Math.Round(H(m1) - H(m2), 4)
        월소득 = 노임단가 x 일수
        기간일실수입 = 적용호프만 x 월소득 x (상실률/100) x (1 - 생계비)
    를 계산하고, 직전 순번까지의 누적(savehoff)에 240 상한을 건다.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Callable

from .constants import LIVING_COST_DEATH, LIVING_COST_INJURY
from .dateutil import months_from
from .fraction import fraction_to_decimal, remove_fraction
from .hoffman import HOFFMAN, LEGAL_RATE, MONTHLY_CAP, adjust_factor
from .income import period_income
from .wage_period import WagePeriod, split_periods


@dataclass
class IncomeRow:
    """일실수입 한 순번. 엑셀표의 한 행에 대응한다."""

    step: int
    start: date
    end: date
    days: int
    wage: Decimal          # 노임단가 (일)
    salary: Decimal        # 월소득 = 노임단가 x 일수
    loss_rate: Decimal     # 상실률 (%)
    living_cost: Decimal   # 생계비 공제율 (0 또는 1/3)
    m1: int
    m2: int
    raw_factor: Decimal    # 240 상한 적용 전 적용호프만
    factor: Decimal        # 240 상한 적용 후
    amount: Decimal        # 기간일실수입
    prorated_days: int = 0                  # 안분일수
    prorated_amount: Decimal = Decimal(0)   # 안분액(30일 기준)

    @property
    def capped(self) -> bool:
        return self.factor != self.raw_factor

    @property
    def subtotal(self) -> Decimal:
        return self.amount + self.prorated_amount


def build_income_rows(
    accident_date: date,
    start: date,
    end: date,
    wage_of: Callable[[WagePeriod], Decimal],
    loss_rate_of: Callable[[WagePeriod], Decimal] = lambda p: Decimal(100),
    rural: bool = False,
    living_cost: Decimal | str = LIVING_COST_INJURY,
    ratio: float = LEGAL_RATE,
    kind: str = HOFFMAN,
    has_wage=None,
    boundaries: list[date] | None = None,
) -> list[IncomeRow]:
    """노임단가 변경일 기준으로 일실수입 순번을 만든다.

    wage_of      구간을 받아 그 구간의 일 노임단가를 돌려준다 (TB_SUT001/TB_SUT004 조회)
    loss_rate_of 구간을 받아 상실률(%)을 돌려준다.
                 입원기간은 100, 여명단축 구간은 66.66666666 을 쓴다.
    living_cost  부상이면 "0", 사망이면 "1/3" (IncomeCostPopup 원본)
    has_wage     (year, index) -> bool. 다음 구간 단가가 없으면 끝까지 한 순번으로 묶는다.
    boundaries   노임변경일 외에 추가로 순번을 끊을 날짜. 입원치료 종료일 다음날처럼
                 상실률이 바뀌는 지점이 여기 들어간다.
    """
    lc = fraction_to_decimal(str(living_cost))
    rows: list[IncomeRow] = []
    saved = Decimal(0)

    periods = split_periods(start, end, rural, has_wage)
    if boundaries:
        periods = _apply_boundaries(periods, boundaries)

    for step, p in enumerate(periods, 1):
        m2 = months_from(accident_date, p.start)
        m1 = months_from(accident_date, p.end)
        raw = adjust_factor(m1, m2, ratio, kind)

        factor = raw
        if saved >= MONTHLY_CAP:
            factor = Decimal(0)
        elif saved + factor >= MONTHLY_CAP:
            factor = MONTHLY_CAP - saved
        saved += factor

        wage = Decimal(str(wage_of(p)))
        salary = wage * p.days
        loss = Decimal(str(loss_rate_of(p)))

        # 적용호프만이 0인 순번은 월 단위로 잡히지 않으므로 일할 안분한다.
        # 골든 케이스 순번1: 2025.08.18.~08.31. 안분일수 14, 3,420,740 x 14/30 = 1,596,345
        pro_days = 0
        pro_amount = Decimal(0)
        if factor == 0:
            pro_days = (p.end - p.start).days + 1
            pro_amount = remove_fraction(
                salary * pro_days / 30 * (loss / 100) * (1 - lc), 0
            )

        rows.append(
            IncomeRow(
                step=step,
                start=p.start,
                end=p.end,
                days=p.days,
                wage=wage,
                salary=salary,
                loss_rate=loss,
                living_cost=lc,
                m1=m1,
                m2=m2,
                raw_factor=raw,
                factor=factor,
                amount=period_income(factor, salary, loss, lc),
                prorated_days=pro_days,
                prorated_amount=pro_amount,
            )
        )
    return rows


def _apply_boundaries(periods: list[WagePeriod], boundaries: list[date]) -> list[WagePeriod]:
    """노임변경일 외의 지점에서 순번을 더 쪼갠다 (입원치료 종료일 등)."""
    from dataclasses import replace

    out: list[WagePeriod] = []
    for p in periods:
        cuts = sorted(d for d in boundaries if p.start < d <= p.end)
        cur = p.start
        for d in cuts:
            out.append(replace(p, start=cur, end=date.fromordinal(d.toordinal() - 1)))
            cur = d
        out.append(replace(p, start=cur, end=p.end))
    return out


def total_income(rows: list[IncomeRow]) -> Decimal:
    """일실수입 전체합계 = 기간 일실수입 합 + 안분액 합."""
    return sum((r.subtotal for r in rows), Decimal(0))
