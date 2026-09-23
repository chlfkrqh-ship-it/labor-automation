"""노동능력상실률 — 중복장해율 및 기왕증 기여도.

검증 상태: 확정.
'손해배상 계산 사용자설명서' 2쪽/15쪽 예시를 소수점 4자리까지 재현함.
  신장내과 58%(기왕증 50%), 안과 13%, 치과 1.06%
    -> 중복장해율 38.8848% (프로그램 표시 38.88%)
    -> 기왕증 기여도 39.0973% (프로그램 표시 39.09%)
골든 케이스 3(신 프로그램) 장해 표의 행별 표시값도 재현한다.
  정형외과 40%(기왕증 20%)          -> 중복장해 32,   단순중복장해 40, 기왕증 기여도 20
  + 안과 20%                        -> 중복장해 45.6, 단순중복장해 52, 기왕증 기여도 12.3

계산은 float 가 아니라 Decimal 10진 계산으로 한다. float 로 1 - PI(1 - r/100) 을 구하면
단일 장해 10% 가 9.999999999999998 이 되고, 소수 셋째자리 이하를 절사하면 9.99% 로 떨어진다
(1~100% 정수 단일 장해 중 16개, 골든 케이스 3의 기왕증 기여도 20 -> 19.99). 프로그램 표시값은
10.00 / 20 이므로 사람이 적은 10진수를 그대로 계산한다. float 로 들어온 값은 str() 을 거쳐
Decimal 로 바꾼다(58.0 -> 58.0, 1.06 -> 1.06).
"""

from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN, localcontext

# 나눗셈(기왕증 기여도)과 여러 장해의 곱에서 절사 경계가 반올림으로 흔들리지 않도록 넉넉히 둔다.
_PRECISION = 60


def _dec(value) -> Decimal:
    """Decimal 은 그대로, float·int·str 은 사람이 적은 10진수 그대로 Decimal 로."""
    return value if isinstance(value, Decimal) else Decimal(str(value))


@dataclass(frozen=True)
class Impairment:
    """진료과별 장해 1건.

    rate:  개별수치 (%, 예: 58.0)
    prior: 기왕증 기여도 (%, 예: 50.0). 해당 장해 안에서 기왕증이 차지하는 비율.
    years: 한시장해인 경우 존속 년수. None이면 영구장해.
    dept:  진료과 (표시용)

    수치는 Decimal·int·float 어느 것이든 받는다. 계산은 Decimal 로 한다.
    """

    rate: Decimal | float
    prior: Decimal | float = 0
    years: Decimal | float | None = None
    dept: str = ""

    @property
    def is_temporary(self) -> bool:
        return self.years is not None

    def as_permanent_rate(self) -> Decimal:
        """한시장해를 영구장해로 환산한 개별수치.

        설명서 15쪽: 환산 방식 = 개별수치 x (년수 / 10년)
        영구장해는 그대로 반환한다.
        """
        with localcontext() as ctx:
            ctx.prec = _PRECISION
            if not self.is_temporary:
                return _dec(self.rate)
            return _dec(self.rate) * _dec(self.years) / Decimal(10)

    def net_rate(self) -> Decimal:
        """기왕증을 공제한 뒤의 개별수치."""
        with localcontext() as ctx:
            ctx.prec = _PRECISION
            return self.as_permanent_rate() * (1 - _dec(self.prior) / 100)


def combined_rate(rates) -> Decimal:
    """중복장해율 (%). 복합장해 공식 1 - PI(1 - r_i)."""
    with localcontext() as ctx:
        ctx.prec = _PRECISION
        remaining = Decimal(1)
        for r in rates:
            remaining *= 1 - _dec(r) / 100
        return (1 - remaining) * 100


def combined_with_prior(items: list[Impairment]) -> Decimal:
    """기왕증 공제 후 중복장해율 (%). 프로그램의 '중복장해율' 표시값."""
    return combined_rate([i.net_rate() for i in items])


def combined_without_prior(items: list[Impairment]) -> Decimal:
    """기왕증 공제 전 전체 후유장해율 (%). 프로그램의 '단순중복장해' 표시값."""
    return combined_rate([i.as_permanent_rate() for i in items])


def prior_contribution(items: list[Impairment]) -> Decimal:
    """전체 후유장해 100% 기준 기왕증 기여도 (%).

    (기왕증 공제 전 - 공제 후) / 공제 전
    """
    gross = combined_without_prior(items)
    if gross == 0:
        return Decimal(0)
    net = combined_with_prior(items)
    with localcontext() as ctx:
        ctx.prec = _PRECISION
        return (gross - net) / gross * 100


def truncate2(value) -> Decimal:
    """소수점 셋째자리 이하 절사.

    프로그램 표시값과 대조한 결과 절사로 보인다.
      38.8848 -> 38.88,  39.0973 -> 39.09
    끝수처리 옵션(올림/내림/반올림)이 항목별로 다를 수 있으므로
    디컴파일 소스로 최종 확인이 필요하다.

    값은 위 함수들이 돌려준 Decimal 을 그대로 절사한다. float 를 받으면 str() 을 거친
    10진수로 절사하므로, float 오차가 남은 값(9.999999999999998)은 그대로 9.99 가 된다.
    합성 계산을 float 로 하지 않는 이유다.
    """
    return _dec(value).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
