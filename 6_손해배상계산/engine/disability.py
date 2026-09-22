"""노동능력상실률 — 중복장해율 및 기왕증 기여도.

검증 상태: 확정.
'손해배상 계산 사용자설명서' 2쪽/15쪽 예시를 소수점 4자리까지 재현함.
  신장내과 58%(기왕증 50%), 안과 13%, 치과 1.06%
    -> 중복장해율 38.8848% (프로그램 표시 38.88%)
    -> 기왕증 기여도 39.0973% (프로그램 표시 39.09%)
"""

from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN


@dataclass(frozen=True)
class Impairment:
    """진료과별 장해 1건.

    rate:  개별수치 (%, 예: 58.0)
    prior: 기왕증 기여도 (%, 예: 50.0). 해당 장해 안에서 기왕증이 차지하는 비율.
    years: 한시장해인 경우 존속 년수. None이면 영구장해.
    dept:  진료과 (표시용)
    """

    rate: float
    prior: float = 0.0
    years: float | None = None
    dept: str = ""

    @property
    def is_temporary(self) -> bool:
        return self.years is not None

    def as_permanent_rate(self) -> float:
        """한시장해를 영구장해로 환산한 개별수치.

        설명서 15쪽: 환산 방식 = 개별수치 x (년수 / 10년)
        영구장해는 그대로 반환한다.
        """
        if not self.is_temporary:
            return self.rate
        return self.rate * (self.years / 10.0)

    def net_rate(self) -> float:
        """기왕증을 공제한 뒤의 개별수치."""
        return self.as_permanent_rate() * (1.0 - self.prior / 100.0)


def combined_rate(rates: list[float]) -> float:
    """중복장해율 (%). 복합장해 공식 1 - PI(1 - r_i)."""
    remaining = 1.0
    for r in rates:
        remaining *= 1.0 - r / 100.0
    return (1.0 - remaining) * 100.0


def combined_with_prior(items: list[Impairment]) -> float:
    """기왕증 공제 후 중복장해율 (%). 프로그램의 '중복장해율' 표시값."""
    return combined_rate([i.net_rate() for i in items])


def combined_without_prior(items: list[Impairment]) -> float:
    """기왕증 공제 전 전체 후유장해율 (%)."""
    return combined_rate([i.as_permanent_rate() for i in items])


def prior_contribution(items: list[Impairment]) -> float:
    """전체 후유장해 100% 기준 기왕증 기여도 (%).

    (기왕증 공제 전 - 공제 후) / 공제 전
    """
    gross = combined_without_prior(items)
    if gross == 0.0:
        return 0.0
    net = combined_with_prior(items)
    return (gross - net) / gross * 100.0


def truncate2(value: float) -> Decimal:
    """소수점 셋째자리 이하 절사.

    프로그램 표시값과 대조한 결과 절사로 보인다.
      38.8848 -> 38.88,  39.0973 -> 39.09
    끝수처리 옵션(올림/내림/반올림)이 항목별로 다를 수 있으므로
    디컴파일 소스로 최종 확인이 필요하다.
    """
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
