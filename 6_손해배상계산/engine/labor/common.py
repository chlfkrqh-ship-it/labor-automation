"""노동 금액 모듈이 함께 쓰는 기간·끝수·옵션·근거 기록.

기간 계산은 모두 **양끝 포함(초일산입)** 이다. `days_inclusive(2024-01-01, 2024-01-31) == 31`.
평균임금 산정기간처럼 초일을 넣지 않는 계산은 호출하는 모듈이 시작일을 하루 옮겨서 넘긴다.

끝수처리는 법령에 정함이 없고 판결마다 달라(조사 문서 OW-14, OT-21, RS-04, AL-22, DW-13)
옵션으로 둔다. 기본값은 판결에서 가장 많이 관찰된 '원 미만 버림'이다. 중간값(통상시급,
1일 평균임금 등)은 옵션이 따로 정하지 않는 한 Decimal 정밀도를 그대로 유지하고,
금액으로 확정하는 마지막 단계에서만 끊는다.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_CEILING, ROUND_DOWN, ROUND_HALF_UP, Decimal

from ..case import _d as parse_date

__all__ = [
    "Claim", "LaborError", "OptionSpec", "PaySlice", "Trace",
    "add_months", "days_inclusive", "dec", "is_within", "month_end", "parse_date",
    "pay_date_for", "pay_periods", "resolve_options", "round_money", "round_to",
]


class LaborError(ValueError):
    """입력이 계산을 할 수 없는 상태일 때. 메시지는 사용자에게 그대로 보여 준다."""


def dec(v, default=None) -> Decimal | None:
    if v is None or v == "":
        return default
    if isinstance(v, Decimal):
        return v
    return Decimal(str(v).replace(",", ""))


# ---------------------------------------------------------------- 날짜
def days_inclusive(start: date, end: date) -> int:
    """양끝 포함 일수. end < start 이면 0."""
    return max((end - start).days + 1, 0)


def month_end(d: date) -> date:
    return date(d.year, d.month, calendar.monthrange(d.year, d.month)[1])


def add_months(d: date, n: int) -> date:
    """n개월 뒤 같은 날. 대응일이 없으면 그 달 말일(1. 31. + 1개월 = 2. 28./29.)."""
    y, m = divmod(d.month - 1 + n, 12)
    y += d.year
    m += 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def is_within(d: date, periods) -> bool:
    """periods = [(시작, 끝), ...] 양끝 포함. 끝이 None 이면 열린 기간."""
    for s, e in periods or []:
        if s <= d and (e is None or d <= e):
            return True
    return False


@dataclass(frozen=True)
class PaySlice:
    """임금산정기간 하나와 그중 계산 대상 구간.

    key        'YYYY-MM' — 임금산정기간이 시작하는 달
    period_*   임금산정기간 전체 (예: 1일~말일, 21일~다음달 20일)
    start/end  계산 대상 [start, end] 와 겹치는 부분
    """

    key: str
    period_start: date
    period_end: date
    start: date
    end: date

    @property
    def period_days(self) -> int:
        return days_inclusive(self.period_start, self.period_end)

    @property
    def covered_days(self) -> int:
        return days_inclusive(self.start, self.end)

    @property
    def is_full(self) -> bool:
        return self.start == self.period_start and self.end == self.period_end


def pay_periods(start: date, end: date, start_day: int = 1) -> list[PaySlice]:
    """[start, end] 를 임금산정기간 단위로 자른다.

    start_day=1 이면 달력 월, 21 이면 21일~다음달 20일. 29일 이후 시작은 달마다 기간이
    어긋나므로 받지 않는다.
    """
    if end < start:
        return []
    if not 1 <= start_day <= 28:
        raise LaborError(f"임금산정기간 시작일은 1~28 이어야 합니다: {start_day}")

    def anchor(y: int, m: int) -> date:
        return date(y, m, min(start_day, calendar.monthrange(y, m)[1]))

    ps = anchor(start.year, start.month)
    if start < ps:
        ps = anchor(*((start.year - 1, 12) if start.month == 1 else (start.year, start.month - 1)))
    out = []
    while ps <= end:
        nxt = anchor(*((ps.year + 1, 1) if ps.month == 12 else (ps.year, ps.month + 1)))
        pe = nxt - timedelta(days=1)
        out.append(PaySlice(f"{ps.year:04d}-{ps.month:02d}", ps, pe, max(ps, start), min(pe, end)))
        ps = nxt
    return out


def pay_date_for(period_end: date, pay_day: int, month_offset: int = 0) -> date:
    """임금산정기간 말일이 속한 달 + month_offset 개월의 pay_day 일(말일 초과 시 말일)."""
    y, m = divmod(period_end.month - 1 + month_offset, 12)
    y += period_end.year
    m += 1
    return date(y, m, min(pay_day, calendar.monthrange(y, m)[1]))


# ---------------------------------------------------------------- 끝수
ROUNDING_MODES = {
    "floor": "원 미만 버림",
    "half_up": "원 미만 반올림",
    "ceil": "원 미만 올림",
    "floor10": "10원 미만 버림",
    "none": "끝수처리 안 함",
}


def round_to(value, digits: int = 0, mode: str = "floor") -> Decimal:
    """digits 자리 아래를 mode 로 처리. 음수는 0 방향(버림)·절댓값 기준(반올림)."""
    v = Decimal(str(value))
    if mode == "none":
        return v
    if mode == "floor10":
        return (v / 10).quantize(Decimal(1), rounding=ROUND_DOWN) * 10
    q = Decimal(1).scaleb(-digits)
    rounding = {"floor": ROUND_DOWN, "half_up": ROUND_HALF_UP, "ceil": ROUND_CEILING}.get(mode)
    if rounding is None:
        raise LaborError(f"끝수처리 방식을 알 수 없습니다: {mode} (가능: {', '.join(ROUNDING_MODES)})")
    return v.quantize(q, rounding=rounding)


def round_money(value, mode: str = "floor") -> Decimal:
    return round_to(value, 0, mode)


# ---------------------------------------------------------------- 옵션
@dataclass(frozen=True)
class OptionSpec:
    """판례가 갈리거나 불명확해 사건마다 고르는 계산 방식.

    key      사건.yaml `options:` 아래 키
    default  기본값 (근거가 가장 무거운 쪽)
    choices  허용값과 설명. 비어 있으면 자유값(숫자 등)
    rule     근거 규칙 ID (노동금액-계산기준.md)
    """

    key: str
    default: object
    description: str
    rule: str
    choices: dict = field(default_factory=dict)


def resolve_options(raw: dict | None, *spec_groups) -> tuple[dict, list[tuple[OptionSpec, object, bool]]]:
    """(값 사전, [(spec, 값, 기본값 여부)]) 를 돌려준다. 모르는 키·허용되지 않는 값은 오류."""
    raw = dict(raw or {})
    specs: dict[str, OptionSpec] = {}
    for group in spec_groups:
        for spec in (group.values() if isinstance(group, dict) else group):
            specs[spec.key] = spec
    unknown = sorted(set(raw) - set(specs))
    if unknown:
        raise LaborError("알 수 없는 옵션: " + ", ".join(unknown))
    values, used = {}, []
    for key, spec in specs.items():
        is_default = key not in raw
        value = spec.default if is_default else raw[key]
        if spec.choices and value not in spec.choices:
            raise LaborError(
                f"옵션 {key} 의 값 {value!r} 은 허용되지 않습니다. 가능: {', '.join(map(str, spec.choices))}")
        values[key] = value
        used.append((spec, value, is_default))
    return values, used


# ---------------------------------------------------------------- 근거 기록과 원금 항목
@dataclass
class Trace:
    """계산표 '근거' 시트에 남기는 한 줄. 무엇을 어떤 규칙으로 정했는지."""

    rule: str
    label: str
    value: str = ""
    note: str = ""


@dataclass
class Claim:
    """지연손해금·소멸시효 계산의 입력이 되는 원금 한 건.

    category   '시간외수당 차액' / '연차휴가수당' / '퇴직금 차액' / '해고기간 임금' 등
    label      '2024. 3.분' 처럼 사람이 읽는 이름
    due_date   본래 지급기일(정기지급일, 수당청구권 발생일 등). 지연손해금은 그 다음날부터
    settlement 퇴직·사망으로 청산할 금품이면 True — 근로기준법 제36조 14일 기한 적용 대상
    """

    category: str
    label: str
    amount: Decimal
    due_date: date
    settlement: bool = False
    note: str = ""
