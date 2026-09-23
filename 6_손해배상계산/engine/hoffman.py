"""중간이자 공제 — 호프만식 / 라이프니츠식.

원본: SUT.SBGCalc.Helpers.HoffmanLeibnizUtil.GetFactor
      SUT.SBGCalc.Model.SBGCalc.Income (적용호프만과 240 상한)

    public static double GetFactor(HoffmanLeibnizType type, int month, double ratio,
                                   bool sumMode = false, bool useLimit = false)
    {
        int startIdx = sumMode ? 1 : month;
        for (int i = startIdx; i <= month; i++)
            sum += (decimal)(type == Hoffman
                ? 1.0 / (1.0 + (double)i * (ratio / 12.0))
                : 1.0 / Math.Pow(1.0 + ratio / 12.0, i));
        sum = (decimal)FractionUtil.RemoveFraction((double)sum, 4);
        if (useLimit && sum > 240m) sum = 240m;
        return (double)sum;
    }

검증 (설명서 17~18쪽 수치를 그대로 재현):
    H(413) = 239.9092,  H(414) = 240.2762   "414개월을 초과하여 240을 넘게"
    H(144) = 112.6135,  H(720) = 332.3359   18쪽 순번3의 두 끝점
    240 상한 적용 -> 216.4067
"""

from __future__ import annotations

from decimal import Decimal

from .fraction import remove_fraction, round_half_even, to_decimal15

HOFFMAN = "H"
LEIBNIZ = "L"

MONTHLY_CAP = Decimal("240")   # 설명서 17쪽: 월단위 단리연금현가율 누적 240 초과 방지
# 치료비·보조구 수치합계 상한은 설명서 25~26쪽의 '20' 이 아니라 240 / 수명(월)이다(cost.py).
LEGAL_RATE = 0.05              # 법정이율. 기초사항에서 사용자가 입력한다(_statutoryRateRatio).


def get_factor(
    kind: str = HOFFMAN,
    month: int = 0,
    ratio: float = LEGAL_RATE,
    sum_mode: bool = False,
    use_limit: bool = False,
) -> Decimal:
    """GetFactor 그대로.

    sum_mode=False 면 해당 월 1개의 계수만, True 면 1개월부터 누적합.
    호프만은 단리, 라이프니츠는 월복리다.
    """
    start = 1 if sum_mode else month
    total = Decimal(0)
    for i in range(start, month + 1):
        if kind == HOFFMAN:
            f = 1.0 / (1.0 + i * (ratio / 12.0))
        else:
            f = 1.0 / (1.0 + ratio / 12.0) ** i
        total += to_decimal15(f)          # C# 의 (decimal)double 변환
    total = remove_fraction(total, 4)     # 누적합을 4자리 절사
    if use_limit and total > MONTHLY_CAP:
        total = MONTHLY_CAP
    return total


def cumulative(months: int, ratio: float = LEGAL_RATE, kind: str = HOFFMAN) -> Decimal:
    """1개월부터 n개월까지의 단리연금현가율. get_factor(sum_mode=True) 축약."""
    return get_factor(kind, months, ratio, sum_mode=True)


def adjust_factor(
    m1: int, m2: int, ratio: float = LEGAL_RATE, kind: str = HOFFMAN
) -> Decimal:
    """적용호프만 = H(m1) - H(m2).

    원본 Income.cs:
        _hoffmanLeibniz1 = GetFactor(type, m1, ratio, sumMode: true);
        _hoffmanLeibniz2 = GetFactor(type, m2, ratio, sumMode: true);
        AdjustHoffmanLeibniz = Math.Round(_hoffmanLeibniz1 - _hoffmanLeibniz2, 4);

    useLimit 은 넘기지 않는다. 240 상한은 여기가 아니라 순번 누적 단계에서 건다.
    차이에는 절사가 아니라 Math.Round(반올림)를 쓴다.
    """
    h1 = get_factor(kind, m1, ratio, sum_mode=True)
    h2 = get_factor(kind, m2, ratio, sum_mode=True)
    return round_half_even(h1 - h2, 4)


def apply_cap(factors, cap: Decimal = MONTHLY_CAP) -> list[Decimal]:
    """순번별 적용호프만에 누적 240 상한을 건다.

    원본 Income.cs:
        double presentHoff = Math.Round(_hoffmanLeibniz1 - _hoffmanLeibniz2, 4);
        if (value + presentHoff >= 240.0)     // value = 직전 순번까지의 누적
            ...

    설명서 18쪽: 직전 순번까지의 합계 + 현재 순번 > 240 이면
    현재 순번에 (240 - 직전까지의 합계)를 넣는다. 이후 순번은 0.
    """
    cap = Decimal(str(cap))
    out: list[Decimal] = []
    total = Decimal(0)
    for f in factors:
        f = Decimal(str(f))
        if total >= cap:
            out.append(Decimal(0))
            continue
        if total + f >= cap:
            f = cap - total
        out.append(f)
        total += f
    return out
