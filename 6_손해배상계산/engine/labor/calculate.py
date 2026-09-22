"""노동 금액 사건 하나를 끝까지 계산한다 — 모듈 조립 순서와 값 전달.

    통상임금(ordinary) ─┬─ 시간외수당(overtime) ── 월별 증가 임금 ─┐
                        ├─ 연차휴가수당(leave)                        │
                        └─ 1일 통상임금 ─────── 평균임금(average_wage) ┴─ 퇴직금(retirement)
                                                     └──────────────── 해고기간 임금(dismissal)
    각 모듈의 원금 항목(Claim) ──────────────────────────────────────── 지연손해금(interest)

사건.yaml 에 있는 절만 계산한다. 앞 모듈이 필요한데 절이 없으면 무엇을 넣어야 하는지 오류로 알린다.
옵션은 모든 모듈 것을 한 번에 검사한다(모르는 키·허용되지 않는 값은 오류).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

from . import average, dismissal, interest, leave, ordinary, overtime, retirement
from .common import Claim, LaborError, Trace, is_within, parse_date, resolve_options

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
    periods = []
    for i, p in enumerate(worker.get("small_business_periods") or []):
        if not isinstance(p, (list, tuple)) or len(p) != 2:
            raise LaborError(f"worker.small_business_periods[{i}] 는 [시작, 끝] 형식이어야 합니다.")
        periods.append((parse_date(p[0]), parse_date(p[1]) if p[1] else None))
    return lambda d: is_within(parse_date(d), periods)


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

    def run(section, label, mod, **deps):
        stem = mod.__name__.rsplit(".", 1)[-1]
        stem = "average_wage" if stem == "average" else stem
        loader, calc = getattr(mod, f"load_{stem}"), getattr(mod, f"calculate_{stem}")
        try:
            inp = loader(case.raw[section], w)
            out = calc(inp, o, **deps)
        except LaborError as exc:
            raise LaborError(f"[{label}] {exc}") from exc
        res.parts[section] = out
        res.warnings += [f"[{label}] {x}" for x in out.warnings]
        res.trace += [(label, t) for t in out.trace]
        return out

    if case.has("ordinary"):
        run("ordinary", "통상임금", ordinary)

    def daily_ordinary_of(allowance):
        part = res.parts.get("ordinary")
        return (lambda d: part.daily_ordinary_of(d, allowance=allowance)) if part else None

    if case.has("overtime"):
        ow = _need(res, "ordinary", "시간외수당")
        run("overtime", "시간외수당", overtime,
            hourly_of=lambda d: ow.hourly_of(d, allowance="overtime"), small_business=small)
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

    for section, _, _ in MODULES[:-1]:
        part = res.parts.get(section)
        if part is not None:
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
        out.append(f"{names[section]:<12}  {int(part.total):>15,} 원")
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
