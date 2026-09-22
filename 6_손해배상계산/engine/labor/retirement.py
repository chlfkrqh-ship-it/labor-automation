"""법정 퇴직금과 기지급 퇴직금 대비 차액 (lane: average_wage_severance, 규칙 RS-01~RS-07, MR-1~MR-3).

사람이 사건.yaml `retirement:` 절에 적은 입사일·마지막 근무일·중간정산·기지급 퇴직금과, 평균임금 모듈이
정한 1일 평균임금(deps `average_daily_wage`: Decimal 또는 구간 말일을 받는 콜러블)으로 법정 퇴직금을 다시
계산하고 기지급액을 뺀 차액을 청구 원금(Claim)으로 넘긴다. 신체손해용 일실퇴직금(engine/severance.py)과 무관하다.
법적 판단(중간정산 사유의 적법성, 사업장 규모, 초단시간 여부 등)은 하지 않는다. 사람이 판정해 입력한 값으로 계산만 한다.
기대값은 판결 원문 숫자로 검증했다(tests/test_labor_retirement.py).

---------------------------------------------------------------- 발생 요건
RS-01 [법령] 근로자퇴직급여 보장법 제4조 제1항 단서 "계속근로기간이 1년 미만인 근로자, 4주간을 평균하여 1주간의
      소정근로시간이 15시간 미만인 근로자에 대하여는 그러하지 아니하다".
      1년 판정 `rs_one_year_basis`: calendar(기본) = 입사일(초일 산입)부터 1년의 만료일(민법 제160조, 대응일 없으면
      그 월 말일 — `rs_missing_anniversary`)까지 근무했는지(윤년이 끼면 366일). days_365 = 양끝 포함 일수 >= 365.
      원문 근거는 확인되지 않았다(조사 문서 미해결 9).
      15시간 미만: 전 기간 `weekly_hours` < 15 이면 퇴직금 없음. 구간별 초단시간은 `excluded_periods`
      (reason: short_hours)로 받고 판단기간 `rs_hours15_basis`: exclude_periods(기본) = 그 구간을 계속근로일수에서 뺀다
      (부산지방법원 2020나52559 — 2019. 1. 14. 이후 주 15시간 미만 구간 제외) | whole_if_last = 마지막 근무일이 그
      구간 안이면 퇴직금 전체 불인정. 검증 판정: 대법원 2005. 5. 13. 선고 2003도5169 는 어느 4주를 기준으로 할지
      판시하지 않았으므로 어느 쪽도 판례 근거로 삼지 않고 warning.
MR-1 [법령·하급심] 상시 4명 이하 사업 경과규정: 구 근로자퇴직급여 보장법(2011. 7. 25. 법률 제10967호로 전부개정되기
      전의 것) 부칙 제8조 — 2010. 12. 1. 전 기간은 퇴직금 없음, 2010. 12. 1.~2012. 12. 31. 기간은 100분의 50,
      2013. 1. 1.부터 같은 기준. 부칙 원문은 열람하지 못했고 부산지방법원 서부지원 2024. 9. 26. 선고 2023가단118024
      (확정)의 인용으로만 확인했다. 규모 구간(`small_business_periods`, 비우면 worker)별로 일수를 나누고 구간마다
      끝수처리한 뒤 합산한다(같은 판결: 762일분 × 1/2 = 3,880,344원 + 3,580일분 36,460,975원).

---------------------------------------------------------------- 산식·계속근로일수
RS-02 [법령·실무관행] 제8조 제1항 "계속근로기간 1년에 대하여 30일분 이상의 평균임금을 퇴직금으로". 일수 환산
      `rs_service_ratio_mode`:
        total_days(기본)  1일 평균임금 × 30 × 계속근로일수 ÷ 365 — 퇴직연금복지과-526 "평균임금×30일×재직일수÷365",
                          하급심 다수(부산지방법원 2020나52559, 전주지방법원 군산지원 2023가단56185, 서울중앙지방법원
                          2017가단5098186, 부산지방법원 서부지원 2023가단118024), 대구지방법원 2024나318050 법원 산식
                          "(퇴직 전 3개월 지급된 임금 총액/퇴직 전 3개월간의 총일수)×30일×(총계속근로일수/365)"
        years_plus_days   1일 평균임금 × 30 × (만 근속연수 + 잔여일수 ÷ 365) — 수원지방법원 2018가소24967 "지급률은
                          2.950(= 2년 + 347일/365일, 소수점 셋째자리 미만 버림)". 2월 29일이 '연수' 구간에 들어갈 때만
                          total_days 보다 작다. 이 판결의 21,286,270원과 total_days 방식 21,291,214원의 차이는 윤년이
                          아니라 지급률 셋째자리 버림(`rs_round_ratio`)과 10원 미만 버림에서 생긴다(검증 판정).
        monthly_avg       월 기준액(deps `monthly_wage_base`) × (만 근속연수 + 잔여일수 ÷ 365) — 대구지방법원
                          2024나318050 의 '당사자의 주장 가. 원고' 각주 계산이다. 법원 산식이 아니며 비교용(warning).
RS-03 [법령·실무관행] 계속근로일수 = 입사일부터 마지막 근무일까지 양끝 포함((L − H).days + 1; 부산지방법원 2020나52559
      "2016. 2. 15.부터 2019. 1. 13.까지 총 1,064일"). 중간정산 뒤에는 정산시점부터 새로 계산(제8조 제2항 후문
      "미리 정산하여 지급한 후의 퇴직금 산정을 위한 계속근로기간은 정산시점부터 새로 계산한다"), 판결은 정산기준일
      다음 날부터 셈(수원지방법원 2018가소24967 "퇴직금중간정산일 다음 날인 2012. 7. 19.부터").
MR-2 [하급심] 법정 사유 없는 중간정산·퇴직금 분할약정은 퇴직금 지급의 효력이 없어 계속근로기간을 끊지 않는다
      (부산지방법원 서부지원 2023가단118024, 대법원 2010다95147 인용 — 대법원 원문 미열람). 중간정산 `valid: false`
      이면 입사일부터 이어 계산하고 그 지급액은 최종 기지급액에 더해 공제한다. 부당이득 상계 한도는 다른 모듈(warning).
MR-3 [법령] 육아휴직기간은 근속기간에 포함(남녀고용평등법 제19조 제4항 "또한 제2항의 육아휴직 기간은 근속기간에
      포함한다"). 평균임금 산정기간 제외(시행령 제2조)와 별개이므로 `excluded_periods` 에 육아휴직·출산휴가·업무상
      요양 등을 넣으면 오류로 막는다.

---------------------------------------------------------------- 끝수·차액·지급기한
RS-04 [불명확] 끝수: 법령 규정 없음. 지급률 `rs_round_ratio`(none 기본 | 3dp_floor — 2018가소24967), 퇴직금
      `rs_round_severance`(won_floor 기본 — 2020나52559 "원 미만 버림", 2023가단56185, 2017가단5098186 | ten_won_floor —
      2018가소24967 "10원 미만 버림" | none). 규모 구간이 여러 개면 `rs_part_rounding`(per_part 기본 — 2023가단118024).
      1일 평균임금 끝수는 평균임금 모듈(aw_round_avg_daily)이 정해 넘긴다.
RS-05 [하급심] 차액 = 재산정 퇴직금 − 기지급 퇴직금. 중간정산분은 정산시점마다 따로 — 수원지방법원 2018가소24967(확정)
      "미지급 퇴직금 차액을 계산하면, 1,509,790원[= 21,286,270원(= 240,522.85원 × 2.950 × 30일, 10원 미만 버림) -
      19,776,480원]". 중간정산 구간은 그 구간의 1일 평균임금(입력 `average_daily_wage` 또는 콜러블에 정산기준일)이 있을
      때만 재산정하고, 없으면 재산정하지 않는다. 중간정산 차액 청구권은 정산 시점에 발생·시효 기산(같은 판결이 인용한
      대법원 2006다20542 — 원문 미열람) → 별도 Claim(settlement=False, due_date = 지급일 또는 정산기준일) + warning.
RS-06 [법령·하급심] 제9조 제1항 "그 지급사유가 발생한 날부터 14일 이내에 퇴직금을 지급하여야 한다". 지급사유 발생일 =
      마지막 근무일 L 다음 날, 그날부터 14일이 되는 날 L + 14일을 Claim.due_date 로 둔다(지연손해금 L + 15일부터 —
      전주지방법원 군산지원 2023가단56185 "퇴직일로부터 14일이 경과한 다음 날(… 2023. 3. 15. …)", 부산지방법원 서부지원
      2023가단118024 2022. 11. 4.). `rs_due_date=day_after_retirement` 이면 due_date = L(지연손해금 L + 1일부터 —
      부산지방법원 2020나52559 "원고의 퇴직일 다음 날인 2019. 9. 11.부터"). 이율 구간은 지연손해금 모듈.
RS-07 [판례확립(청구 형태)·행정해석(산식)] DC형은 부담금 차액을 계정에 납입하라는 이행청구(대법원 2023. 4. 13. 선고
      2018다283926 "정당한 부담금과 이미 납입된 부담금의 차액을 퇴직연금제도 계정에 납입할 것을 청구하는 이행의 소"),
      소급분 산식은 행정해석(퇴직연금복지과-526·926). 이 모듈은 법정 퇴직금만 계산하고 `dc_plan: true` 면 warning 만.

---------------------------------------------------------------- 사건.yaml `retirement:` 절
    retirement:
      hire_date: 2002-01-02          # 비우면 worker.hire_date
      last_working_day: 2015-06-30   # 비우면 worker.last_working_day(필수)
      paid_severance: 19776480       # 최종 퇴직 시 기지급 퇴직금
      interim_settlements:           # 중간정산(정산기준일까지의 근로분)
        - {date: 2012-07-18, paid: 30000000, valid: true, average_daily_wage: null, paid_date: 2012-07-25}
      weekly_hours: 40               # 전 기간 4주 평균 1주 소정근로시간(비우면 판단 안 함)
      excluded_periods:              # 계속근로일수에서 뺄 구간(육아휴직 등 근속 포함 기간은 넣지 않음)
        - {reason: short_hours, start: 2019-01-14, end: 2019-09-10}
      small_business_periods: []     # 상시 4명 이하 기간 [[시작, 끝], ...]. 비우면 worker.small_business_periods
      dc_plan: false                 # 확정기여형 퇴직연금 가입(참고 경고만)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from .common import (
    Claim,
    LaborError,
    OptionSpec,
    Trace,
    add_months,
    days_inclusive,
    dec,
    is_within,
    parse_date,
    round_to,
)

__all__ = [
    "NON_EXCLUDABLE_REASONS", "OPTIONS", "RULES",
    "InterimSettlement", "RetirementInput", "RetirementResult", "RetirementRow", "ServiceExclusion",
    "calculate_retirement", "load_retirement", "one_year_expiry", "years_and_days",
]

ZERO = Decimal(0)
ONE = Decimal(1)
HALF = Decimal("0.5")
DAYS_365 = Decimal(365)
DATE_SMALL_BIZ_START = date(2010, 12, 1)    # 상시 4명 이하 퇴직급여제도 적용
DATE_SMALL_BIZ_FULL = date(2013, 1, 1)      # 100분의 50 경과기간 종료 다음 날

EXCLUDABLE_REASONS = {
    "short_hours": "4주 평균 1주 소정근로시간 15시간 미만 구간(제4조 제1항 단서)",
    "other": "기타 계속근로기간에서 빼는 구간(근거를 note 에 적을 것)",
}
NON_EXCLUDABLE_REASONS = {
    "parental_leave": "육아휴직기간은 근속기간에 포함(남녀고용평등법 제19조 제4항)",
    "maternity": "출산전후휴가기간은 계속근로기간에 포함(평균임금 산정기간 제외와 별개)",
    "industrial_accident": "업무상 요양 휴업기간은 계속근로기간에 포함(평균임금 산정기간 제외와 별개)",
    "childcare_reduced_hours": "육아기 근로시간 단축기간은 근속기간에 포함",
    "unfair_dismissal": "부당해고기간은 근로관계가 계속된 기간",
}

OPTIONS: dict[str, OptionSpec] = {s.key: s for s in [
    OptionSpec("rs_service_ratio_mode", "total_days", "계속근로기간 환산", "RS-02", {
        "total_days": "30 × 계속근로일수 ÷ 365(퇴직연금복지과-526, 하급심 다수)",
        "years_plus_days": "30 × (만 근속연수 + 잔여일수 ÷ 365)(수원지방법원 2018가소24967)",
        "monthly_avg": "월 기준액 × (만 근속연수 + 잔여일수 ÷ 365) — 대구지방법원 2024나318050 원고 주장 계산(비교용)",
    }),
    OptionSpec("rs_round_ratio", "none", "지급률(근속연수 환산값) 끝수", "RS-04", {
        "none": "끝수처리 안 함",
        "3dp_floor": "소수점 셋째자리 미만 버림(수원지방법원 2018가소24967)",
    }),
    OptionSpec("rs_round_severance", "won_floor", "퇴직금 끝수", "RS-04", {
        "won_floor": "원 미만 버림(부산지방법원 2020나52559 등)",
        "ten_won_floor": "10원 미만 버림(수원지방법원 2018가소24967)",
        "none": "끝수처리 안 함",
    }),
    OptionSpec("rs_part_rounding", "per_part", "규모 구간이 나뉠 때 끝수처리 단위", "MR-1", {
        "per_part": "구간마다 끝수처리한 뒤 합산(부산지방법원 서부지원 2023가단118024)",
        "sum_then_round": "구간 합계를 한 번 끝수처리",
    }),
    OptionSpec("rs_round_monthly_base", "none", "monthly_avg 월 기준액 끝수", "RS-02", {
        "none": "끝수처리 안 함",
        "won_floor": "원 미만 버림 후 곱함(대구지방법원 2024나318050 원고 계산 2,456,267원 재현)",
    }),
    OptionSpec("rs_one_year_basis", "calendar", "계속근로 1년 판정", "RS-01", {
        "calendar": "입사일부터 역에 의한 1년 만료일까지 근무(민법 제160조)",
        "days_365": "양끝 포함 일수 365일 이상",
    }),
    OptionSpec("rs_missing_anniversary", "civil_code", "1년 만료일의 대응일이 없을 때(2. 29. 입사 등)", "RS-01", {
        "civil_code": "민법 제160조 제3항 — 그 월 말일로 만료",
        "clamp": "그 월 말일을 대응일로 보아 전날 만료",
    }),
    OptionSpec("rs_hours15_basis", "exclude_periods", "주 15시간 미만 구간 처리", "RS-01", {
        "exclude_periods": "입력 구간을 계속근로일수에서 뺌(부산지방법원 2020나52559) — 판단기간 판례 미확인",
        "whole_if_last": "마지막 근무일이 15시간 미만 구간이면 퇴직금 전체 불인정 — 판단기간 판례 미확인",
    }),
    OptionSpec("rs_due_date", "statutory_14", "퇴직금 차액 지급기일(Claim.due_date)", "RS-06", {
        "statutory_14": "마지막 근무일 + 14일(지연손해금 + 15일부터, 전주지방법원 군산지원 2023가단56185)",
        "day_after_retirement": "마지막 근무일(지연손해금 다음 날부터, 부산지방법원 2020나52559)",
    }),
]}

RULES: dict[str, tuple[str, str]] = {
    "RS-01": ("계속근로 1년 미만·4주 평균 주 15시간 미만이면 퇴직금 없음(판단기간은 옵션)", "법령"),
    "RS-02": ("1일 평균임금 × 30 × 계속근로일수 ÷ 365(환산 방식 옵션)", "법령·실무관행"),
    "RS-03": ("계속근로일수 양끝 포함, 적법한 중간정산 뒤 정산기준일 다음 날부터", "법령·실무관행"),
    "RS-04": ("지급률·퇴직금 끝수", "불명확"),
    "RS-05": ("재산정 퇴직금 − 기지급 퇴직금, 중간정산은 정산시점별", "하급심"),
    "RS-06": ("지급사유 발생일부터 14일 기한, 지연손해금 기산일은 판결마다 다름", "법령·하급심"),
    "RS-07": ("DC형 부담금 차액 이행청구 — 참고 경고만", "판례확립·행정해석"),
    "MR-1": ("상시 4명 이하 사업 2010. 12. 1. 전 0, 2012. 12. 31.까지 1/2", "법령·하급심"),
    "MR-2": ("무효 중간정산·분할약정은 계속근로기간을 끊지 않음", "하급심"),
    "MR-3": ("육아휴직기간은 계속근로기간에 포함", "법령"),
}


# ================================================================ 입력
@dataclass
class InterimSettlement:
    date: date                        # 정산기준일(이 날까지의 근로분을 정산)
    paid: Decimal = ZERO
    valid: bool = True
    average_daily_wage: Decimal | None = None
    paid_date: date | None = None
    note: str = ""


@dataclass
class ServiceExclusion:
    reason: str
    start: date
    end: date
    note: str = ""


@dataclass
class RetirementInput:
    hire_date: date
    last_working_day: date
    paid_severance: Decimal = ZERO
    interim_settlements: list = field(default_factory=list)
    weekly_hours: Decimal | None = None
    excluded_periods: list = field(default_factory=list)
    small_business_periods: list = field(default_factory=list)
    dc_plan: bool = False


# ================================================================ 결과
@dataclass
class RetirementRow:
    """계산표 한 줄. kind: eligibility | part(규모·비율 구간) | segment(중간정산 구간 합계)."""

    segment_no: int
    kind: str
    start: date | None
    end: date | None
    rate: Decimal | None = None             # 1, 1/2, 0 (MR-1)
    calendar_days: int | None = None
    excluded_days: int | None = None
    counted_days: int | None = None
    years: int | None = None
    remaining_days: int | None = None
    ratio: Decimal | None = None            # 근속연수 환산값(끝수처리 후)
    average_daily_wage: Decimal | None = None
    amount_raw: Decimal | None = None
    amount: Decimal | None = None
    paid: Decimal | None = None
    diff: Decimal | None = None
    note: str = ""


@dataclass
class RetirementResult:
    rows: list
    total: Decimal
    claims: list
    trace: list
    warnings: list
    eligible: bool = True
    final_severance: Decimal | None = None
    final_paid: Decimal = ZERO
    final_diff: Decimal = ZERO


# ================================================================ 읽기
_KEYS = {"hire_date", "last_working_day", "paid_severance", "interim_settlements", "weekly_hours",
         "excluded_periods", "small_business_periods", "dc_plan"}


def _num(v, label: str, default=None) -> Decimal | None:
    if v is None or v == "":
        return default
    if isinstance(v, bool):
        raise LaborError(f"퇴직금: {label} 은(는) 숫자여야 합니다: {v!r}")
    try:
        return dec(v)
    except (InvalidOperation, ValueError, TypeError):
        raise LaborError(f"퇴직금: {label} 은(는) 숫자여야 합니다: {v!r}") from None


def _date(v, label: str, required: bool = False) -> date | None:
    if v is None or v == "":
        if required:
            raise LaborError(f"퇴직금: {label} 이(가) 없습니다")
        return None
    try:
        return parse_date(v)
    except (ValueError, TypeError):
        raise LaborError(f"퇴직금: {label} 날짜 형식이 올바르지 않습니다: {v!r}") from None


def _bool(v, label: str, default=None):
    if v is None or v == "":
        return default
    if isinstance(v, bool):
        return v
    raise LaborError(f"퇴직금: {label} 은(는) true/false 여야 합니다: {v!r}")


def _periods(raw, label: str) -> list:
    out = []
    for i, pr in enumerate(raw or [], 1):
        if not isinstance(pr, (list, tuple)) or len(pr) != 2:
            raise LaborError(f"퇴직금: {label}[{i}] 는 [시작, 끝] 이어야 합니다")
        s = _date(pr[0], f"{label}[{i}] 시작", required=True)
        e = _date(pr[1], f"{label}[{i}] 끝", required=True)
        if e < s:
            raise LaborError(f"퇴직금: {label}[{i}] 의 끝 {e} 이 시작 {s} 보다 앞섭니다")
        out.append((s, e))
    return out


def load_retirement(raw: dict, worker: dict | None = None) -> RetirementInput:
    """사건.yaml `retirement:` 절(dict)과 `worker:` 절을 읽는다."""
    raw = dict(raw or {})
    worker = dict(worker or {})
    unknown = set(raw) - _KEYS
    if unknown:
        raise LaborError(f"퇴직금: retirement 절에 알 수 없는 키: {', '.join(sorted(unknown))}")
    hire = _date(raw.get("hire_date"), "hire_date") or _date(worker.get("hire_date"), "worker.hire_date")
    if hire is None:
        raise LaborError("퇴직금: 입사일(retirement.hire_date 또는 worker.hire_date)이 없습니다")
    last = _date(raw.get("last_working_day"), "last_working_day") or _date(worker.get("last_working_day"),
                                                                           "worker.last_working_day")
    if last is None:
        raise LaborError("퇴직금: 마지막 근무일(retirement.last_working_day 또는 worker.last_working_day)이 없습니다 — "
                         "재직 중이면 퇴직금을 계산하지 않습니다")
    if last < hire:
        raise LaborError(f"퇴직금: 마지막 근무일 {last} 이 입사일 {hire} 보다 앞섭니다")

    interims = []
    for i, s in enumerate(raw.get("interim_settlements") or [], 1):
        lab = f"interim_settlements[{i}]"
        if not isinstance(s, dict):
            raise LaborError(f"퇴직금: {lab} 은(는) 사전이어야 합니다")
        bad = set(s) - {"date", "paid", "valid", "average_daily_wage", "paid_date", "note"}
        if bad:
            raise LaborError(f"퇴직금: {lab} 에 알 수 없는 키: {', '.join(sorted(bad))}")
        d = _date(s.get("date"), f"{lab}.date", required=True)
        if not hire <= d < last:
            raise LaborError(f"퇴직금: {lab} 정산기준일 {d} 은 입사일 {hire} 이후, 마지막 근무일 {last} 전이어야 합니다")
        valid = _bool(s.get("valid"), f"{lab}.valid")
        if valid is None:
            raise LaborError(f"퇴직금: {lab} 중간정산의 유효 여부(valid: true/false)를 사람이 정해 적어야 합니다(RS-03, MR-2)")
        interims.append(InterimSettlement(d, _num(s.get("paid"), f"{lab}.paid", ZERO), valid,
                                          _num(s.get("average_daily_wage"), f"{lab}.average_daily_wage"),
                                          _date(s.get("paid_date"), f"{lab}.paid_date"), str(s.get("note") or "")))
    interims.sort(key=lambda x: x.date)
    dates = [x.date for x in interims]
    if len(set(dates)) != len(dates):
        raise LaborError("퇴직금: 같은 정산기준일의 중간정산이 두 번 있습니다")

    excluded = []
    for i, e in enumerate(raw.get("excluded_periods") or [], 1):
        lab = f"excluded_periods[{i}]"
        if not isinstance(e, dict):
            raise LaborError(f"퇴직금: {lab} 은(는) 사전이어야 합니다")
        reason = e.get("reason")
        if reason in NON_EXCLUDABLE_REASONS:
            raise LaborError(f"퇴직금: {lab} 사유 {reason!r} 는 계속근로기간에서 뺄 수 없습니다 — {NON_EXCLUDABLE_REASONS[reason]} (MR-3)")
        if reason not in EXCLUDABLE_REASONS:
            raise LaborError(f"퇴직금: {lab} 의 사유 {reason!r} 를 알 수 없습니다. 가능: {', '.join(EXCLUDABLE_REASONS)}")
        s = _date(e.get("start"), f"{lab}.start", required=True)
        en = _date(e.get("end"), f"{lab}.end", required=True)
        if en < s:
            raise LaborError(f"퇴직금: {lab} 의 끝 {en} 이 시작 {s} 보다 앞섭니다")
        excluded.append(ServiceExclusion(reason, s, en, str(e.get("note") or "")))

    sbp_raw = raw.get("small_business_periods")
    sbp = _periods(sbp_raw if sbp_raw else worker.get("small_business_periods"), "small_business_periods")
    paid = _num(raw.get("paid_severance"), "paid_severance", ZERO)
    wh = _num(raw.get("weekly_hours"), "weekly_hours")
    for v, lab in ((paid, "paid_severance"), (wh, "weekly_hours")):
        if v is not None and v < 0:
            raise LaborError(f"퇴직금: {lab} 는 음수일 수 없습니다")
    return RetirementInput(hire, last, paid, interims, wh, excluded, sbp,
                           bool(_bool(raw.get("dc_plan"), "dc_plan", False)))


# ================================================================ 날짜 헬퍼
def _fmt(d: date | None) -> str:
    return "" if d is None else f"{d.year}. {d.month}. {d.day}."


def one_year_expiry(start: date, months: int = 12, mode: str = "civil_code") -> date:
    """start(초일 산입)부터 months 개월의 만료일. 민법 제160조 제2·3항(mode=civil_code), clamp 는 말일을 대응일로."""
    target = add_months(start, months)
    if target.day != start.day and mode == "civil_code":
        return target
    return target - timedelta(days=1)


def years_and_days(start: date, end: date, mode: str = "civil_code") -> tuple[int, int]:
    """[start, end] 의 (만 연수, 잔여 일수). 잔여 일수는 마지막 만료일 다음 날부터 end 까지 양끝 포함."""
    years = 0
    while one_year_expiry(start, 12 * (years + 1), mode) <= end:
        years += 1
    anniv = start if years == 0 else one_year_expiry(start, 12 * years, mode) + timedelta(days=1)
    return years, days_inclusive(anniv, end)


def _settle(x: Decimal) -> Decimal:
    """Decimal 나눗셈의 순환소수 오차 보정(소수 10자리 반올림). 끝수처리 직전에만 쓴다."""
    return x.quantize(Decimal("1e-10"), rounding=ROUND_HALF_UP)


def _round_severance(v: Decimal, mode: str) -> Decimal:
    if mode == "none":
        return v
    return round_to(_settle(v), 0, "floor10" if mode == "ten_won_floor" else "floor")


# ================================================================ 계산 내부
@dataclass
class _Ctx:
    o: dict
    trace: list
    warnings: list

    def warn(self, msg: str) -> None:
        if msg not in self.warnings:
            self.warnings.append(msg)


def _read_options(opts: dict | None) -> dict:
    opts = opts or {}
    out = {}
    for key, spec in OPTIONS.items():
        v = opts.get(key, spec.default)
        if spec.choices and v not in spec.choices:
            raise LaborError(f"옵션 {key} 의 값 {v!r} 은 허용되지 않습니다. 가능: {', '.join(map(str, spec.choices))}")
        out[key] = v
    return out


def _rate_on(d: date, inp: RetirementInput) -> Decimal:
    if not is_within(d, inp.small_business_periods):
        return ONE
    if d < DATE_SMALL_BIZ_START:
        return ZERO
    if d < DATE_SMALL_BIZ_FULL:
        return HALF
    return ONE


def _parts(inp: RetirementInput, start: date, end: date) -> list[tuple[date, date, Decimal]]:
    """[start, end] 를 MR-1 비율이 같은 구간으로 나눈다."""
    cuts = {DATE_SMALL_BIZ_START, DATE_SMALL_BIZ_FULL}
    for s, e in inp.small_business_periods:
        cuts.add(s)
        cuts.add(e + timedelta(days=1))
    edges = sorted(c for c in cuts if start < c <= end)
    out = []
    s = start
    for c in edges + [end + timedelta(days=1)]:
        e = c - timedelta(days=1)
        if s <= e:
            r = _rate_on(s, inp)
            if out and out[-1][2] == r and out[-1][1] + timedelta(days=1) == s:
                out[-1] = (out[-1][0], e, r)
            else:
                out.append((s, e, r))
        s = c
    return out


def _excluded_days(inp: RetirementInput, start: date, end: date) -> int:
    days: set = set()
    for x in inp.excluded_periods:
        s, e = max(x.start, start), min(x.end, end)
        d = s
        while d <= e:
            days.add(d)
            d += timedelta(days=1)
    return len(days)


def _resolve(dep, when: date):
    if dep is None:
        return None
    return dec(dep(when)) if callable(dep) else dec(dep)


def _segment(no: int, kind: str, start: date, end: date, avg: Decimal | None, monthly: Decimal | None,
             inp: RetirementInput, ctx: _Ctx, rows: list) -> Decimal | None:
    """구간 퇴직금(끝수처리 후). 1일 평균임금(또는 월 기준액)이 없으면 None."""
    o = ctx.o
    mode = o["rs_service_ratio_mode"]
    base = monthly if mode == "monthly_avg" else avg
    parts = _parts(inp, start, end)
    raw_sum = ZERO
    rounded_sum = ZERO
    for ps, pe, rate in parts:
        cal = days_inclusive(ps, pe)
        exd = _excluded_days(inp, ps, pe)
        counted = cal - exd
        years = rem = None
        if mode == "total_days":
            num = Decimal(counted)                      # ratio = num / 365
        else:
            if exd:
                raise LaborError(f"퇴직금: {_fmt(ps)}~{_fmt(pe)} 에 계속근로일수 제외 구간이 있어 rs_service_ratio_mode={mode} "
                                 "(만 연수 + 잔여일수)로 셀 수 없습니다 — total_days 를 쓰십시오")
            years, rem = years_and_days(ps, pe, o["rs_missing_anniversary"])
            num = Decimal(years * 365 + rem)
        ratio_exact = num / DAYS_365
        ratio = ratio_exact
        if o["rs_round_ratio"] == "3dp_floor":
            ratio = round_to(_settle(ratio_exact), 3, "floor")
        note = []
        if rate != ONE:
            note.append("상시 4명 이하 2010. 12. 1. 전 — 퇴직금 없음" if rate == 0 else
                        "상시 4명 이하 2010. 12. 1.~2012. 12. 31. — 100분의 50(구 퇴직급여법 부칙 제8조)")
        if exd:
            note.append(f"계속근로일수 제외 {exd}일")
        if base is None:
            rows.append(RetirementRow(no, "part", ps, pe, rate, cal, exd, counted, years, rem, ratio, avg,
                                      note="; ".join(note + ["1일 평균임금 없음 — 재산정 안 함"])))
            continue
        mult = base if mode == "monthly_avg" else base * 30
        if o["rs_round_ratio"] == "none":
            amount_raw = mult * rate * num / DAYS_365
            formula = f"{mult} × {rate} × {num}/365"
        else:
            amount_raw = mult * rate * ratio
            formula = f"{mult} × {rate} × {ratio}"
        amount = _round_severance(amount_raw, o["rs_round_severance"])
        raw_sum += amount_raw
        rounded_sum += amount
        rows.append(RetirementRow(no, "part", ps, pe, rate, cal, exd, counted, years, rem, ratio, avg,
                                  amount_raw, amount, note="; ".join(note + [formula])))
    if base is None:
        return None
    if o["rs_part_rounding"] == "sum_then_round" and len(parts) > 1:
        return _round_severance(raw_sum, o["rs_round_severance"])
    return rounded_sum


def calculate_retirement(inp: RetirementInput, opts: dict, **deps) -> RetirementResult:
    o = _read_options(opts)
    trace: list[Trace] = []
    warnings: list[str] = []
    rows: list[RetirementRow] = []
    ctx = _Ctx(o, trace, warnings)
    for key, spec in OPTIONS.items():
        v = o[key]
        trace.append(Trace(spec.rule, f"옵션 {key}", str(v), spec.choices.get(v, spec.description)))
    H, L = inp.hire_date, inp.last_working_day
    mode = o["rs_service_ratio_mode"]
    avg_dep = deps.get("average_daily_wage")
    monthly_dep = deps.get("monthly_wage_base")
    if mode == "monthly_avg":
        if monthly_dep is None:
            raise LaborError("퇴직금: rs_service_ratio_mode=monthly_avg 이면 월 기준액(deps monthly_wage_base)이 필요합니다")
        ctx.warn("monthly_avg 는 대구지방법원 2024나318050 의 원고 주장 계산으로 법정 산식이 아닙니다 — 비교용으로만 쓰십시오(RS-02)")
    elif avg_dep is None:
        raise LaborError("퇴직금: 1일 평균임금(deps average_daily_wage)이 필요합니다 — 평균임금 모듈 결과를 넘기십시오")
    if inp.dc_plan:
        ctx.warn("확정기여형(DC) 퇴직연금 가입자는 법정 퇴직금이 아니라 부담금 차액의 계정 납입 이행청구(대법원 2018다283926) 대상이며, "
                 "소급분 산식은 행정해석(퇴직연금복지과-526·926)입니다 — 이 계산은 참고용(RS-07)")

    # ---- RS-01 발생 요건
    total_days = days_inclusive(H, L)
    expiry = one_year_expiry(H, 12, o["rs_missing_anniversary"])
    if o["rs_one_year_basis"] == "calendar":
        one_year = L >= expiry
        why = f"1년 만료일 {_fmt(expiry)}, 마지막 근무일 {_fmt(L)}"
    else:
        one_year = total_days >= 365
        why = f"계속근로 {total_days}일"
    reason = None
    if not one_year:
        reason = f"계속근로기간 1년 미만({why}) — 퇴직금 없음(제4조 제1항 단서)"
    elif inp.weekly_hours is not None and inp.weekly_hours < 15:
        reason = f"4주 평균 1주 소정근로시간 {inp.weekly_hours}시간 < 15시간 — 퇴직금 없음(제4조 제1항 단서)"
    short = [x for x in inp.excluded_periods if x.reason == "short_hours"]
    if short:
        ctx.warn(f"주 15시간 미만 구간 처리(rs_hours15_basis={o['rs_hours15_basis']})의 판단기간은 판례로 확인되지 않았습니다"
                 "(대법원 2003도5169 는 어느 4주를 기준으로 할지 판시하지 않음)")
        if reason is None and o["rs_hours15_basis"] == "whole_if_last" and any(x.start <= L <= x.end for x in short):
            reason = "마지막 근무일이 주 15시간 미만 구간 — 퇴직금 전체 불인정(rs_hours15_basis=whole_if_last)"
    if any(x.reason == "other" for x in inp.excluded_periods):
        ctx.warn("계속근로일수에서 기타(other) 구간을 뺐습니다 — 근거 확인 필요")
    trace.append(Trace("RS-01", "퇴직금 발생 요건", "충족" if reason is None else "불충족", reason or why))
    if reason is not None:
        rows.append(RetirementRow(0, "eligibility", H, L, calendar_days=total_days, note=reason))
        paid = inp.paid_severance + sum((s.paid for s in inp.interim_settlements), ZERO)
        return RetirementResult(rows, ZERO, [], trace, warnings, eligible=False, final_severance=ZERO,
                                final_paid=paid, final_diff=ZERO)
    if inp.small_business_periods:
        ctx.warn("상시 4명 이하 경과규정(MR-1: 2010. 12. 1. 전 0, 2012. 12. 31.까지 1/2)은 구 퇴직급여법 부칙 제8조를 "
                 "하급심(부산지방법원 서부지원 2023가단118024) 인용으로만 확인했습니다")

    # ---- 구간(RS-03, MR-2)
    valid = [s for s in inp.interim_settlements if s.valid]
    invalid = [s for s in inp.interim_settlements if not s.valid]
    final_paid = inp.paid_severance + sum((s.paid for s in invalid), ZERO)
    for s in invalid:
        ctx.warn(f"중간정산 {_fmt(s.date)} 은 무효로 입력되어 계속근로기간을 끊지 않고, 지급액 {s.paid}원은 최종 기지급액에 더해 "
                 "공제했습니다(MR-2) — 부당이득 상계 한도는 따로 확인해야 합니다")
        trace.append(Trace("MR-2", f"무효 중간정산 {_fmt(s.date)}", f"공제 {s.paid}", "입사일부터 계속근로 이어 계산"))

    claims: list[Claim] = []
    total = ZERO
    start = H
    no = 0
    for s in valid:
        no += 1
        avg = s.average_daily_wage
        if avg is None and callable(avg_dep):
            avg = _resolve(avg_dep, s.date)
        monthly = _resolve(monthly_dep, s.date) if (mode == "monthly_avg" and callable(monthly_dep)) else None
        if mode == "monthly_avg" and monthly is not None and o["rs_round_monthly_base"] == "won_floor":
            monthly = round_to(_settle(monthly), 0, "floor")
        sev = _segment(no, "interim", start, s.date, avg, monthly, inp, ctx, rows)
        if sev is None:
            rows.append(RetirementRow(no, "segment", start, s.date, paid=s.paid,
                                      note=f"중간정산 구간 — 정산 시점 1일 평균임금이 없어 재산정하지 않음(정산기준일 {_fmt(s.date)})"))
            trace.append(Trace("RS-03", f"중간정산 {_fmt(s.date)}", "재산정 안 함", f"다음 구간은 {_fmt(s.date + timedelta(days=1))}부터"))
        else:
            diff = max(ZERO, sev - s.paid)
            rows.append(RetirementRow(no, "segment", start, s.date, average_daily_wage=avg, amount=sev, paid=s.paid, diff=diff,
                                      note=f"중간정산 구간 재산정(RS-05)" + ("; 기지급액이 재산정액 이상 — 차액 0" if sev < s.paid else "")))
            if diff > 0:
                due = s.paid_date or s.date
                claims.append(Claim("중간정산 퇴직금 차액", f"중간정산 퇴직금 차액({_fmt(start)}~{_fmt(s.date)})", diff, due, False,
                                    note=f"정산기준일 {_fmt(s.date)}; 청구권은 중간정산 시점에 발생·시효 기산(수원지방법원 2018가소24967)"))
                total += diff
                ctx.warn(f"중간정산 퇴직금 차액 {diff}원({_fmt(start)}~{_fmt(s.date)})은 중간정산 시점부터 소멸시효가 진행합니다"
                         "(대법원 2006다20542 인용 하급심) — 소 제기일과 대조 필요")
        start = s.date + timedelta(days=1)

    # ---- 최종 구간
    no += 1
    avg = _resolve(avg_dep, L) if avg_dep is not None else None
    monthly = None
    if mode == "monthly_avg":
        monthly = _resolve(monthly_dep, L)
        if o["rs_round_monthly_base"] == "won_floor":
            monthly = round_to(_settle(monthly), 0, "floor")
    sev = _segment(no, "final", start, L, avg, monthly, inp, ctx, rows)
    diff = max(ZERO, sev - final_paid)
    rows.append(RetirementRow(no, "segment", start, L, average_daily_wage=avg, amount=sev, paid=final_paid, diff=diff,
                              note="최종 퇴직 구간" + ("; 기지급액이 재산정액 이상 — 차액 0" if sev < final_paid else "")))
    trace.append(Trace("RS-03", "최종 구간 계속근로", f"{_fmt(start)}~{_fmt(L)}",
                       f"양끝 포함 {days_inclusive(start, L)}일" + (" (중간정산 다음 날부터)" if valid else "")))
    trace.append(Trace("RS-05", "퇴직금 차액", f"{sev} − {final_paid} = {diff}"))
    if o["rs_due_date"] == "statutory_14":
        due = L + timedelta(days=14)
        due_note = f"지급사유 발생일 {_fmt(L + timedelta(days=1))}부터 14일이 되는 {_fmt(due)}(제9조 제1항); 지연손해금 {_fmt(due + timedelta(days=1))}부터"
    else:
        due = L
        due_note = f"퇴직일 다음 날 {_fmt(L + timedelta(days=1))}부터 지연손해금(부산지방법원 2020나52559)"
    trace.append(Trace("RS-06", "지급기일", _fmt(due), due_note + " — 이율 구간은 지연손해금 모듈"))
    if diff > 0:
        claims.append(Claim("퇴직금 차액", f"퇴직금 차액({_fmt(start)}~{_fmt(L)})", diff, due, True, note=due_note))
        total += diff
    return RetirementResult(rows, total, claims, trace, warnings, eligible=True, final_severance=sev,
                            final_paid=final_paid, final_diff=diff)
