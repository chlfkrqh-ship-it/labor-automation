"""일실수입 — 기간별 금액 계산.

원본: SUT.SBGCalc.Model.SBGCalc.Income

    return (decimal)FractionUtil.RemoveFraction(
        (double)((decimal)_adjustHoffmanLeibniz
                 * decimal.Parse(Salary.Replace(",", ""))
                 * (decimal)(_lossRate / 100.0)
                 * (decimal)CommonCalc.Calc("1-" + LivingCost, 10, Math.Round, 1)), 0);

    기간일실수입 = 적용호프만 x 월소득 x (상실률/100) x (1 - 생계비),  원 미만 절사
"""

from __future__ import annotations

from decimal import Decimal

from .fraction import remove_fraction


def period_income(
    adjust_hoffman,
    salary,
    loss_rate,
    living_cost=0,
) -> Decimal:
    """한 순번(기간)의 일실수입.

    adjust_hoffman: 적용호프만 (hoffman.adjust_factor 결과, 240 상한 적용 후)
    salary:         월소득 (원)
    loss_rate:      노동능력상실률 (%, 예: 38.88). 입원기간은 100.
    living_cost:    생계비 공제율 (사망사건은 1/3). 부상은 0.

    사망사건에서 상실률 항목이 생계비 항목으로 바뀌고 1/3을 공제한다(설명서 32쪽).
    여명이 가동기간 내로 단축된 경우에는 그 기간의 상실률을 66.6%로 설정하는
    방식으로 생계비 1/3을 공제한다(설명서 16쪽).
    """
    value = (
        Decimal(str(adjust_hoffman))
        * Decimal(str(salary))
        * (Decimal(str(loss_rate)) / Decimal(100))
        * (Decimal(1) - Decimal(str(living_cost)))
    )
    return remove_fraction(value, 0)
