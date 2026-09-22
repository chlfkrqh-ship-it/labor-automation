"""일실퇴직금 (일반) — 산출방식 A~D.

원본 화면의 정의(엑셀표저장 '퇴직금(일반)' 시트) 그대로다.

    A  (정년시퇴직금현가 - 기수령퇴직금)              x 상실률
    B  (정년시퇴직금현가 - 사고시의 계산상퇴직금)      x 상실률
    C  (정년시퇴직금현가 - 실제퇴직시계산상퇴직금의 현가) x 상실률
    D  (정년시퇴직금현가 - 실제퇴직시받은 퇴직금의 현가)  x 상실률

각 방식마다 월할/일할 두 계산이 나오고, 사용자가 하나를 골라 종합화면에 반영한다.
재직기간은 DateUtil.GetDiffDaysString 의 MonthCalc(월할) / DayCalc(일할)를 쓴다.

    MonthCalc = years + months / 12
    DayCalc   = totalDays / 365          (초일산입이므로 하루가 더해진 총일수)

    퇴직금 = 월급여 x 재직기간계수,  원 미만 절사
    현가   = 퇴직금 x GetFactor(호프만, 사고일~해당일 개월수),  원 미만 절사

골든 케이스 2로 확인한 값 (월급여 2,334,000원, 상실률 100%):

    재직기간 0년 1월 22일 -> 월할 0.0833333333333333, 일할 0.142465753424658
    사고시 퇴직금  월할 194,499 / 일할 332,515
    정년시 퇴직금현가 2,240,640
    방식 B  월할 2,046,141 = 2,240,640 - 194,499
            일할 1,908,125 = 2,240,640 - 332,515

방식 A 와 D 는 기수령퇴직금이 0 이면 0 이 나온다(골든 케이스 2에서 확인).
"""

from __future__ import annotations

from decimal import Decimal

from .fraction import remove_fraction


def severance_amount(monthly_salary, service_factor) -> Decimal:
    """퇴직금 = 월급여 x 재직기간계수, 원 미만 절사."""
    return remove_fraction(Decimal(str(monthly_salary)) * Decimal(str(service_factor)), 0)


def present_value(amount, factor) -> Decimal:
    """사고시 현가 = 금액 x 호프만계수, 원 미만 절사."""
    return remove_fraction(Decimal(str(amount)) * Decimal(str(factor)), 0)


def method_a(retirement_pv, received, loss_rate=100) -> Decimal:
    """A — 기수령퇴직금을 그대로 공제."""
    return remove_fraction(
        (Decimal(str(retirement_pv)) - Decimal(str(received))) * Decimal(str(loss_rate)) / 100, 0
    )


def method_b(retirement_pv, at_accident, loss_rate=100) -> Decimal:
    """B — 사고시의 계산상 퇴직금을 공제."""
    return remove_fraction(
        (Decimal(str(retirement_pv)) - Decimal(str(at_accident))) * Decimal(str(loss_rate)) / 100, 0
    )


def method_c(retirement_pv, at_leave_pv, loss_rate=100) -> Decimal:
    """C — 실제퇴직시 계산상 퇴직금의 사고시 현가를 공제."""
    return remove_fraction(
        (Decimal(str(retirement_pv)) - Decimal(str(at_leave_pv))) * Decimal(str(loss_rate)) / 100, 0
    )


def method_d(retirement_pv, received_pv, loss_rate=100) -> Decimal:
    """D — 실제퇴직시 받은 퇴직금의 사고시 현가를 공제."""
    return remove_fraction(
        (Decimal(str(retirement_pv)) - Decimal(str(received_pv))) * Decimal(str(loss_rate)) / 100, 0
    )
