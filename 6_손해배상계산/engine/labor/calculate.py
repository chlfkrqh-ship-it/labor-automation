"""노동 금액 사건 하나를 끝까지 계산한다 — 모듈 조립 순서와 값 전달.

    통상임금(ordinary) ─┬─ 시간외수당(overtime) ── 월별 증가 임금 ─┐
                        ├─ 연차휴가수당(leave)                        │
                        └─ 1일 통상임금 ─────── 평균임금(average_wage) ┴─ 퇴직금(retirement)
                                                     └──────────────── 해고기간 임금(dismissal)
    각 모듈의 원금 항목(Claim) ──────────────────────────────────────── 지연손해금(interest)

사건.yaml 에 있는 절만 계산한다. 앞 모듈이 필요한데 절이 없으면 무엇을 넣어야 하는지 오류로 알린다.
옵션은 모든 모듈 것을 한 번에 검사한다(모르는 키·허용되지 않는 값은 오류).

값 전달 규약
- 통상임금 콜러블에는 수당 종류(allowance)만 넘기고 청구묶음(bundle)은 넘기지 않는다. 다른 모듈 절에 묶음을 적을
  키가 없기 때문이다. 그래서 이 경로가 쓰는 수당(연장·야간·휴일근로수당, 연차휴가수당, 퇴직금, 해고기간 임금)에
  이름 붙은 청구묶음이 parallel_claims 에 있으면 멈춘다(OW-03a).
- 시간외수당 모듈은 연장·야간·휴일 줄에 모두 연장근로수당(overtime) 통상시급을 쓴다(deps hourly_of 가 날짜만 받는다).
  야간(night)·휴일(holiday_work)의 병행 판정으로 통상시급이 달라지는 기간에 야간·휴일 줄이 있으면 멈춘다(OW-03a).
- 사업장 규모 deps small_business 는 worker.small_business_periods 가 있을 때만 넘긴다. 없으면 각 모듈이
  자기 절 입력(leave.small_business 등)으로 정한다.
- 통상임금 모듈은 다른 모듈이 콜러블을 부를 때 경고(OW-M5 등)를 더한다. 그래서 경고는 모든 모듈을 돈 뒤
  (지연손해금 전에) 한 번에 모은다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from . import average, dismissal, interest, leave, ordinary, overtime, retirement
from .common import Claim, LaborError, Trace, dec, is_within, parse_date, resolve_options

MODULES = [  # (절 이름, 한글 이름, 모듈)
    ("ordinary", "통상임금", ordinary),
    ("overtime", "시간외수당", overtime),
    ("leave", "연차휴가수당", leave),
    ("average_wage", "평균임금", average),
    ("retirement", "퇴직금", retirement),
    ("dismissal", "해고기간 임금", dismissal),
    ("interest", "지연손해금", interest),
]
TOP_KEYS = {"kind", "case_no", "name", "employer", "worker", "options", "note"} | {m[0] for m in MODULES}

# 절별로 이 조립 경로가 통상임금 콜러블에 넘기는 수당 종류(ordinary.ALLOWANCES)
ALLOWANCES_BY_SECTION = {
    "overtime": ("overtime", "night", "holiday_work"),
    "leave": ("annual_leave",),
    "average_wage": ("severance",),
    "dismissal": ("dismissal_wage",),
}
# 시간외수당 줄 종류(OvertimeLine.item) 중 연장근로수당 시급을 빌려 쓰는 것 -> 통상임금 수당 종류
OVERTIME_ITEM_ALLOWANCE = {"night": "night", "holiday": "holiday_work"}


@dataclass
class LaborCase:
    raw: dict
    worker: dict
    options: dict
    option_rows: list      # [(OptionSpec, 값, 기본값 여부)]
    case_no: str = ""
    name: str = ""
    employer: str = ""

    def has(self, section: str) -> bool:
        return self.raw.get(section) is not None


@dataclass
class LaborResult:
    case: LaborCase
    parts: dict = field(default_factory=dict)          # 절 이름 -> 모듈 결과
    claims: list = field(default_factory=list)         # 지연손해금에 넘긴 원금 항목
    warnings: list = field(default_factory=list)       # '[모듈] 내용'
    trace: list = field(default_factory=list)          # (모듈, Trace)

    @property
    def principal_total(self) -> Decimal:
        return sum((c.amount for c in self.claims), Decimal(0))


def load_labor_case(source) -> LaborCase:
    """경로(yaml) 또는 이미 읽은 dict."""
    if isinstance(source, (str, Path)):
        import yaml
        raw = yaml.safe_load(Path(source).read_text(encoding="utf-8")) or {}
    else:
        raw = dict(source)
    if raw.get("kind") != "labor":
        raise LaborError("노동 금액 사건 파일은 맨 위에 `kind: labor` 가 있어야 합니다.")
    unknown = set(raw) - TOP_KEYS
    if unknown:
        raise LaborError("사건.yaml 에 알 수 없는 절: " + ", ".join(sorted(unknown))
                         + f" (가능: {', '.join(sorted(TOP_KEYS))})")
    worker = dict(raw.get("worker") or {})
    values, rows = resolve_options(raw.get("options"), *[m.OPTIONS for _, _, m in MODULES])
    return LaborCase(raw, worker, values, rows, str(raw.get("case_no") or ""), str(raw.get("name") or ""),
                     str(raw.get("employer") or ""))


def _small_business(worker: dict):
    """worker.small_business_periods 로 deps small_business(d) 를 만든다.

    기간이 없으면 None 을 돌려준다. 항상 False 인 함수를 넘기면 모듈이 자기 절 입력(leave.small_business: true 등)보다
    deps 를 먼저 보아 그 입력이 무시된다.
    """
    periods = []
    for i, p in enumerate(worker.get("small_business_periods") or []):
        if not isinstance(p, (list, tuple)) or len(p) != 2:
            raise LaborError(f"worker.small_business_periods[{i}] 는 [시작, 끝] 형식이어야 합니다.")
        periods.append((parse_date(p[0]), parse_date(p[1]) if p[1] else None))
    if not periods:
        return None
    return lambda d: is_within(parse_date(d), periods)


def _fmt(d) -> str:
    return "" if d is None else f"{d.year}. {d.month}. {d.day}."


def _won(v) -> str:
    """원 단위 금액 표시. 끝수가 있으면 버리지 않고 그대로 보인다."""
    v = Decimal(v)
    return f"{int(v):,}" if v == v.to_integral_value() else f"{v:,}"


def _check_bundles(case: LaborCase, ord_inp) -> None:
    """이름 붙은 청구묶음은 이 경로에서 적용할 수 없으므로 모듈 깊은 곳의 오류 대신 여기서 방법을 알린다(OW-03a)."""
    used = {a for section, names in ALLOWANCES_BY_SECTION.items() if case.has(section) for a in names}
    named = [p for p in ord_inp.parallel_claims if p.bundle and p.allowance in used]
    if named:
        listed = ", ".join(f"({p.allowance}, {p.bundle!r})" for p in named)
        raise LaborError(
            f"[통상임금] parallel_claims 의 청구묶음 {listed}: 조립 계산(cli·감시 폴더)은 청구묶음을 모듈에 넘기지 않아 "
            "묶음별 병행 여부를 적용할 수 없습니다. 수당마다 bundle 을 비운 한 줄로 적거나, 청구묶음별로 기간을 나눈 "
            "사건.yaml 로 따로 계산하십시오(OW-03a)")


def _check_overtime_allowances(ow, ot, o: dict) -> None:
    """야간·휴일 줄에 쓴 연장근로수당 시급이 야간·휴일근로수당 병행 판정의 시급과 다르면 멈춘다(OW-03a).

    2024. 12. 19. 이후 제공분은 수당과 관계없이 신 법리라 같으므로 그 전날까지만 본다. 줄에는 날짜가 없어
    그 줄이 있는 임금산정기간의 날마다 비교한다. 법정 줄을 쓰지 않는 경우(유효한 포괄임금으로 차액 0,
    약정 기준만 청구)는 보지 않는다.
    """
    if ot.method == "inclusive_valid" or o.get("ot_claim_basis") == "contract":
        return
    last = ordinary.BOUNDARY - timedelta(days=1)
    found = []
    for r in ot.rows:
        items = sorted({ln.item for ln in r.lines} & set(OVERTIME_ITEM_ALLOWANCE))
        d = max(r.period_start, ow.period_start)
        end = min(r.period_end, ow.period_end, last)
        while items and d <= end:
            base = ow.hourly_of(d, allowance="overtime")
            for item in list(items):
                allowance = OVERTIME_ITEM_ALLOWANCE[item]
                other = ow.hourly_of(d, allowance=allowance)
                if other != base:
                    found.append(f"{r.key} {allowance}({_fmt(d)} 연장 {base:,.2f} / {allowance} {other:,.2f})")
                    items.remove(item)
            d += timedelta(days=1)
    if found:
        raise LaborError(
            "[시간외수당] 시간외수당 모듈은 야간·휴일 가산도 연장근로수당(overtime)의 병행 여부로 정한 통상시급으로 "
            "계산합니다. 그런데 parallel_claims 로 정한 야간(night)·휴일(holiday_work) 병행 여부로는 통상시급이 다릅니다: "
            + ", ".join(found[:5]) + (" 외" if len(found) > 5 else "")
            + ". 수당별 시급 적용은 아직 지원하지 않습니다. 야간·휴일도 연장과 같게 보아야 하면 parallel_claims 에 "
            "night·holiday_work 줄을 overtime 과 같은 parallel 값으로 적으십시오. 다르게 보아야 하면 연장분과 "
            "야간·휴일분을 나눈 사건.yaml 로 따로 계산하고 사람이 검산하십시오(OW-03a)")


def _need(result: LaborResult, section: str, for_label: str):
    part = result.parts.get(section)
    if part is None:
        label = dict((m[0], m[1]) for m in MODULES)[section]
        raise LaborError(f"{for_label} 계산에는 `{section}:` 절({label})이 먼저 필요합니다.")
    return part


def calculate_labor(case: LaborCase) -> LaborResult:
    res = LaborResult(case)
    o, w = case.options, case.worker
    small = _small_business(w)
    inputs = {}

    def run(section, label, mod, **deps):
        stem = mod.__name__.rsplit(".", 1)[-1]
        stem = "average_wage" if stem == "average" else stem
        loader, calc = getattr(mod, f"load_{stem}"), getattr(mod, f"calculate_{stem}")
        try:
            inp = loader(case.raw[section], w)
            out = calc(inp, o, **deps)
        except LaborError as exc:
            raise LaborError(f"[{label}] {exc}") from exc
        inputs[section] = inp
        res.parts[section] = out
        res.trace += [(label, t) for t in out.trace]
        return out

    if case.has("ordinary"):
        run("ordinary", "통상임금", ordinary)
        _check_bundles(case, inputs["ordinary"])

    def daily_ordinary_of(allowance):
        part = res.parts.get("ordinary")
        return (lambda d: part.daily_ordinary_of(d, allowance=allowance)) if part else None

    if case.has("overtime"):
        ow = _need(res, "ordinary", "시간외수당")
        run("overtime", "시간외수당", overtime,
            hourly_of=lambda d: ow.hourly_of(d, allowance="overtime"), small_business=small)
        _check_overtime_allowances(ow, res.parts["overtime"], o)
    if case.has("leave"):
        _need(res, "ordinary", "연차휴가수당")
        run("leave", "연차휴가수당", leave, daily_ordinary_of=daily_ordinary_of("annual_leave"), small_business=small)
    if case.has("average_wage"):
        extra = getattr(res.parts.get("overtime"), "extra_wages", None) or {}
        run("average_wage", "평균임금", average, daily_ordinary_of=daily_ordinary_of("severance"), extra_wages=extra)
    if case.has("retirement"):
        avg = _need(res, "average_wage", "퇴직금")
        run("retirement", "퇴직금", retirement, average_daily_wage=avg.average_daily_wage)
    if case.has("dismissal"):
        avg = res.parts.get("average_wage")
        run("dismissal", "해고기간 임금", dismissal,
            average_daily_wage=avg.average_daily_wage if avg else None,
            daily_ordinary_of=daily_ordinary_of("dismissal_wage"), small_business=small)

    # 경고는 모든 모듈을 돈 뒤에 모은다 — 통상임금 모듈은 다른 모듈이 콜러블을 부를 때 경고(OW-M5 등)를 더한다.
    for section, label, _ in MODULES[:-1]:
        part = res.parts.get(section)
        if part is not None:
            res.warnings += [f"[{label}] {x}" for x in part.warnings]
            res.claims += list(part.claims or [])

    if case.has("interest") or res.claims:
        raw_int = case.raw.get("interest")
        if raw_int is None:
            res.warnings.append("[지연손해금] `interest:` 절이 없어 지연손해금을 계산하지 않았습니다. "
                                "employer_merchant·송달일·선고(예정)일을 넣으면 구간과 금액이 나옵니다.")
        else:
            raw_int = _interest_defaults_from_dismissal(dict(raw_int), res)
            try:
                inp = interest.load_interest(raw_int, w)
                out = interest.calculate_interest(inp, o, claims=res.claims)
            except LaborError as exc:
                raise LaborError(f"[지연손해금] {exc}") from exc
            res.parts["interest"] = out
            res.warnings += [f"[지연손해금] {x}" for x in out.warnings]
            res.trace += [("지연손해금", t) for t in out.trace]
            cap = o.get("di_claimed_rate_cap")
            if cap not in (None, "") and 0 < dec(cap) < 1:
                res.warnings.append(f"[지연손해금] 옵션 di_claimed_rate_cap 은 연 % 단위입니다 — {cap} 을(를) 연 {cap}% 로 "
                                    "계산했습니다. 연 12% 로 제한하려면 12 로 적습니다(DI-17)")
    return res


def _interest_defaults_from_dismissal(raw_int: dict, res: LaborResult) -> dict:
    """해고기간 임금 모듈이 정리한 사실(claim_info)을 interest 절의 빈 칸에만 채운다. 사람이 적은 값이 우선."""
    part = res.parts.get("dismissal")
    info = getattr(part, "claim_info", None)
    if info is None:
        return raw_int
    filled = []

    def fill(key, value):
        if value is not None and raw_int.get(key) in (None, ""):
            raw_int[key] = value
            filled.append(f"{key}={value}")

    if info.employment_status == "terminated" and not res.case.worker.get("last_working_day"):
        fill("last_working_day", info.termination_date)
    fill("end_cause", info.interest_end_cause)
    if info.dismissal_invalid_final or info.remedy_order_final:
        fill("dismissal_validity_settled", True)
    fill("employer_merchant", info.employer_merchant)
    fill("first_instance_close_date", info.first_instance_closing_date)
    if filled:
        res.trace.append(("지연손해금", Trace("DI-03", "해고기간 임금 모듈에서 가져온 사실", ", ".join(map(str, filled)))))
    return raw_int


def summary_lines(res: LaborResult) -> list[str]:
    """CLI·감시 폴더 출력용 요약."""
    c = res.case
    out = [f"사건            {c.case_no} {c.name} / {c.employer}"]
    names = dict((m[0], m[1]) for m in MODULES)
    for section, part in res.parts.items():
        if section == "interest":
            continue
        if section == "ordinary":
            out.append(f"{names[section]:<12}  기간 {len(part.rows)}개 구간")
            continue
        if section == "average_wage":
            out.append(f"{names[section]:<12}  1일 {part.average_daily_wage:,} 원")
            continue
        if section == "dismissal":
            out += _dismissal_lines(part)
            continue
        out.append(f"{names[section]:<12}  {_won(part.total):>15} 원")
        if section == "overtime":
            out += _overtime_alternative_lines(part)
    out.append(f"원금 합계        {int(res.principal_total):>15,} 원")
    it = res.parts.get("interest")
    if it is not None:
        if it.rows:
            out.append(f"지연손해금       {int(it.total):>15,} 원  (기준일까지)")
        for name, (total, _) in it.alternatives.items():
            if it.rows:
                out.append(f"  대안: {name:<14} {int(total):>12,} 원")
    if res.warnings:
        out.append(f"확인할 점 {len(res.warnings)}건 — 계산표 '경고' 시트")
    return out


def _dismissal_lines(part) -> list[str]:
    """해고기간 임금 절의 요약. 모드마다 금액의 성격이 달라 이름을 바꾸고, 원금 합계에 들지 않는 금액은 그렇게 적는다."""
    if part.labor_commission_amount is not None:
        return [f"{'금전보상 임금상당액':<12}  {_won(part.labor_commission_amount):>15} 원  "
                "(노동위원회 금전보상 DW-21 — 원금 합계·지연손해금 제외)"]
    if part.refund_amount is not None:
        return [f"{'부당이득 반환액':<12}  {_won(part.refund_awardable):>15} 원  "
                f"(사용자가 돌려받을 금액 II-14, 공제 가능액 {_won(part.refund_amount)} 원 — 원금 합계·지연손해금 제외)"]
    out = [f"{'해고기간 임금':<12}  {_won(part.total):>15} 원"]
    if part.future_monthly_amount is not None:
        until = "복직시까지" if part.end_date is None else f"{_fmt(part.end_date)}까지"
        out.append(f"  장래분: {_fmt(part.future_start_date)}부터 {until} 월 {_won(part.future_monthly_amount)} 원  "
                   "(DW-19 — 원금 합계·지연손해금 제외)")
    return out


def _overtime_alternative_lines(part) -> list[str]:
    """초과 지급분 충당·비교 단위(OT-18) 방식별로 이미 계산한 시간외수당 합계 중 고른 방식과 다른 것."""
    alts = getattr(part, "alternatives", None) or {}
    chosen = alts.get(part.method)
    other = {m: v for m, v in alts.items() if m != part.method and v != chosen}
    if not other:
        return []
    body = " / ".join(f"{m} {_won(v)} 원" for m, v in other.items())
    return [f"  대안(OT-18 충당·비교 단위, 고른 방식 {part.method}): {body}",
            "    시간외수당 원금만 — 평균임금·퇴직금·지연손해금까지 바뀐 금액은 options 를 바꾼 사본으로 다시 계산"]
