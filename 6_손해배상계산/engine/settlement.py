"""과실상계 · 공제 · 위자료 · 최종 합계.

골든 케이스 3(손해배상(자)/부상/과실 30%)의 엑셀표저장 결과에서 역산해 확정했다.
소스 대조는 아직 하지 않았으므로, 다른 조합에서 어긋날 여지가 있다.

    재산적 손해                      362,157,144
    원고측 과실비율 30%
    원고측 과실비율액                108,647,143   = 절사(362,157,144 x 0.30)
    지급치료비 1,000,000 중 기왕증 과실분  386,100
    손해배상 선급                      2,000,000
    공제액 합계                        2,386,100
    재산상손해 합계                  251,123,901
    적용 위자료                       20,000,000
    합계                             271,123,901
"""

from __future__ import annotations

from decimal import Decimal

from .fraction import remove_fraction

SOLATIUM_BASE = Decimal("100000000")   # 위자료 자동계산 기준액 (골든 케이스 3에서 역산)
SOLATIUM_FAULT_WEIGHT = Decimal("0.8") # 과실비율에 곱하는 가중치


def fault_share(property_damage, fault_rate) -> Decimal:
    """원고측 과실비율액 = 절사(재산적 손해 x 과실비율).

    골든: 절사(362,157,144 x 0.30) = 108,647,143
    """
    return remove_fraction(Decimal(str(property_damage)) * Decimal(str(fault_rate)) / 100, 0)


def after_fault_offset(property_damage, fault_rate) -> Decimal:
    """화면에 표시되는 '과실상계 후 재산적 손해' = 절사(재산적 손해 x (1 - 과실비율)).

    *** 최종 계산에는 이 값을 쓰지 않는다. ***

    프로그램은 표시용으로 이 값을 쓰지만 최종 재산상손해는
    `재산적 손해 - 과실비율액 - 공제액` 으로 구한다. 두 경로가 절사 때문에
    1원 어긋난다.

        절사(362,157,144 x 0.7) = 253,510,000  ->  - 2,386,100 = 251,123,900
        362,157,144 - 108,647,143 - 2,386,100  =              251,123,901  <- 프로그램의 최종값
    """
    return remove_fraction(
        Decimal(str(property_damage)) * (1 - Decimal(str(fault_rate)) / 100), 0
    )


def paid_cure_deduction(paid_cure, prior_ratio, fault_rate) -> Decimal:
    """지급치료비 중 '기왕증 과실분' — 원고가 부담해야 할 몫만 공제한다.

        지급치료비 x [1 - (1 - 기왕증기여도) x (1 - 과실비율)]

    골든: 1,000,000 x [1 - 0.877 x 0.70] = 1,000,000 x 0.3861 = 386,100
    """
    p = Decimal(str(prior_ratio)) / 100
    f = Decimal(str(fault_rate)) / 100
    return remove_fraction(Decimal(str(paid_cure)) * (1 - (1 - p) * (1 - f)), 0)


def solatium_auto(loss_rate, fault_rate, base=SOLATIUM_BASE) -> Decimal:
    """위자료 자동계산 = 기준액 x 노동능력상실률 x (1 - 과실비율 x 0.8).

    골든: 1억 x 45.6% x (1 - 0.30 x 0.8) = 34,656,000

    화면의 '적용 위자료'에 직접 입력한 값이 최종 위자료가 되고(설명서 30쪽),
    이 자동계산값은 참고치다.
    """
    return remove_fraction(
        Decimal(str(base))
        * Decimal(str(loss_rate))
        / 100
        * (1 - Decimal(str(fault_rate)) / 100 * SOLATIUM_FAULT_WEIGHT),
        0,
    )


def settle(
    property_damage,
    fault_rate,
    *,
    pre_offset_deduction=0,
    paid_cure=0,
    prior_ratio=0,
    advance=0,
    ratio_deduction=0,
    full_deduction=0,
    solatium=0,
) -> dict:
    """과실상계부터 최종합계까지.

    pre_offset_deduction  과실상계 전 공제액 (산재 휴업급여·장해급여 등)
    paid_cure             지급 치료비
    prior_ratio           기왕증 기여도 (%)
    advance               손해배상 선급금 (전액 공제)
    ratio_deduction       기타공제 중 비율공제액
    full_deduction        기타공제 중 전액공제액
    solatium              적용 위자료
    """
    P = Decimal(str(property_damage)) - Decimal(str(pre_offset_deduction))
    share = fault_share(P, fault_rate)
    cure = paid_cure_deduction(paid_cure, prior_ratio, fault_rate)
    deduction = (
        cure + Decimal(str(advance)) + Decimal(str(ratio_deduction)) + Decimal(str(full_deduction))
    )
    property_final = P - share - deduction
    return {
        "선공제_후_재산적손해": P,
        "원고측_과실비율액": share,
        "과실상계_후_표시값": after_fault_offset(P, fault_rate),
        "기왕증_과실분": cure,
        "공제액_합계": deduction,
        "재산상손해_합계": property_final,
        "위자료_합계": Decimal(str(solatium)),
        "합계": property_final + Decimal(str(solatium)),
    }
