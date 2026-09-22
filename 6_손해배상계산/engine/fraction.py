"""FractionUtil 대응 — 끝수 절사와 분수 파싱.

원본: SBCalcLib.Util.FractionUtil.removeFraction
  (신 손해배상이 부르는 SUT.Common.Helpers.Utils.FractionUtil.RemoveFraction 은
   아직 대조하지 못했다. 아래는 SBCalc 판을 옮긴 것이다.)

    public static double removeFraction(double value, int jari)
    {
        double num = 0.0; string text = value.ToString();
        double result = value;
        if (jari >= 0) {
            int num3 = text.IndexOf(".");
            if (num3 > -1) {                                   // 소수점이 있을 때만
                num  = double.Parse(text.Substring(0, num3));  // 정수부
                int num2 = (int)Math.Pow(10.0, jari);
                result  = (double)((decimal)value - (decimal)num);   // 소수부
                result *= num2;
                result  = (int)result;                          // 0 방향 절단
                result /= num2;
                result += num;
            }
        }
        return result;
    }

핵심은 `(int)result` 다. C# 의 int 캐스트는 내림(floor)이 아니라 **0 방향 절단**이라,
음수에서는 올림처럼 동작한다.  -123.45 를 jari=0 으로 넘기면 -123 이 된다.

프로그램 전반의 끝수처리 구분:

    RemoveFraction(누적합, 4)     절사    HoffmanLeibnizUtil.GetFactor
    RemoveFraction(금액, 0)       절사    모든 원 단위 금액
    Math.Round(적용호프만, 4)      반올림   Income.cs (C# 기본 = 은행가 반올림)

절사로 판정한 실증 근거: 설명서 18쪽의 H(144)=112.6135, H(720)=332.3359 는
반올림하면 112.6136 / 332.3360 이 되어 어긋난다.
"""

from decimal import Decimal, ROUND_DOWN, ROUND_HALF_EVEN


def to_decimal15(x: float) -> Decimal:
    """C# 의 (decimal)someDouble — double 을 유효숫자 15자리로 반올림해 변환."""
    return Decimal(f"{x:.15g}")


def remove_fraction(value, digits: int = 0) -> Decimal:
    """FractionUtil.removeFraction — digits 자리 아래를 0 방향으로 절단.

    Python decimal 의 ROUND_DOWN 이 곧 0 방향 절단이라 C# (int) 캐스트와 같다.
    원본은 jari < 0 이면 값을 그대로 돌려준다.
    """
    if digits < 0:
        return Decimal(str(value))
    q = Decimal(1).scaleb(-digits)
    return Decimal(str(value)).quantize(q, rounding=ROUND_DOWN)


def round_half_even(value, digits: int = 0) -> Decimal:
    """C# Math.Round(double, int) — 기본이 MidpointRounding.ToEven."""
    q = Decimal(1).scaleb(-digits)
    return Decimal(str(value)).quantize(q, rounding=ROUND_HALF_EVEN)


def fraction_to_decimal(fraction: str) -> Decimal:
    """FractionUtil.fractionToDecimal — "1/3", "1 2/3" 같은 분수 문자열을 수로.

    생계비(LivingCost)가 이 형식으로 저장된다. Income 의 금액식에 있는
    CommonCalc.Calc("1-" + LivingCost, ...) 가 이 값을 쓴다.
    """
    text = fraction.strip()
    try:
        return Decimal(text)
    except Exception:
        pass
    parts = [p for p in text.replace("/", " ").split() if p]
    if len(parts) == 2:
        return Decimal(parts[0]) / Decimal(parts[1])
    if len(parts) == 3:
        return Decimal(parts[0]) + Decimal(parts[1]) / Decimal(parts[2])
    raise ValueError(f"분수 형식이 아닙니다: {fraction!r}")


def drop_10_unit(value) -> Decimal:
    """FractionUtil.drop10Unit — 인지액의 100원 미만 절사(Math.Floor)."""
    return (Decimal(str(value)) / 100).to_integral_value(rounding=ROUND_DOWN) * 100
