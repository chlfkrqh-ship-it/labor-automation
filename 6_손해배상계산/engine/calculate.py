"""사건 하나를 끝까지 계산한다. 엑셀표 생성의 입력이 되는 결과 묶음."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from .caregiving import CaregivingRow, build_caregiving_rows, past_caregiving, total_caregiving
from .case import Case
from .constants import LIVING_COST_DEATH, LIVING_COST_INJURY
from .cost import RecurringCost
from .dateutil import age_at
from .disability import Impairment, combined_with_prior, prior_contribution, truncate2
from .fraction import remove_fraction
from .schedule import IncomeRow, build_income_rows, total_income
from .settlement import settle, solatium_auto


@dataclass
class Result:
    case: Case
    age: tuple
    combined_rate: Decimal
    prior_contribution: Decimal
    income_rows: list[IncomeRow] = field(default_factory=list)
    income_total: Decimal = Decimal(0)
    caregiving_rows: list[CaregivingRow] = field(default_factory=list)
    past_caregiving_total: Decimal = Decimal(0)
    future_caregiving_total: Decimal = Decimal(0)
    treatment_rows: list = field(default_factory=list)
    treatment_total: Decimal = Decimal(0)
    orthosis_rows: list = field(default_factory=list)
    orthosis_total: Decimal = Decimal(0)
    passive_total: Decimal = Decimal(0)   # 소극손해
    active_total: Decimal = Decimal(0)    # 적극손해
    property_damage: Decimal = Decimal(0)
    settlement: dict = field(default_factory=dict)
    solatium_auto: Decimal = Decimal(0)


def calculate(case: Case, wage_of, has_wage=None, caregiving_price_of=None) -> Result:
    """wage_of(period) -> 일 노임단가.  has_wage(year, index) -> bool."""
    work_end = case.resolved_work_end()
    items = [
        Impairment(float(i.rate), float(i.prior), float(i.years) if i.years else None, i.dept)
        for i in case.impairments
    ]
    combined = truncate2(combined_with_prior(items)) if items else Decimal(0)
    prior = truncate2(prior_contribution(items)) if items else Decimal(0)

    death = case.injury_type == "사망"
    living_cost = LIVING_COST_DEATH if death else LIVING_COST_INJURY

    boundaries = []
    if case.cure_end and not death:
        boundaries.append(date.fromordinal(case.cure_end.toordinal() + 1))

    rows = build_income_rows(
        accident_date=case.accident,
        start=case.accident,
        end=work_end,
        wage_of=wage_of,
        loss_rate_of=(
            (lambda p: Decimal(100))
            if death
            else (lambda p: Decimal(100) if case.cure_end and p.end <= case.cure_end else combined)
        ),
        rural=case.rural,
        living_cost=living_cost,
        ratio=float(case.legal_rate) / 100,
        has_wage=has_wage,
        boundaries=boundaries,
    )

    care_rows = []
    if case.caregiving_start and case.caregiving_end:
        care_rows = build_caregiving_rows(
            accident_date=case.accident,
            start=case.caregiving_start,
            end=case.caregiving_end,
            unit_price_of=caregiving_price_of or wage_of,
            headcount=case.caregiving_headcount,
            prior_ratio=prior,
            rural=case.rural,
            ratio=float(case.legal_rate) / 100,
            has_wage=has_wage,
            month_mode=case.caregiving_month_mode,
        )
    past_care = (
        past_caregiving(
            case.past_caregiving_price,
            case.past_caregiving_days,
            prior,
            case.past_caregiving_actual,
        )
        if case.past_caregiving_days
        else Decimal(0)
    )

    def _costs(inputs):
        out = []
        for t in inputs:
            out.append(
                RecurringCost(
                    accident_date=case.accident,
                    start_date=t.first,
                    end_date=t.last,
                    cost=t.cost,
                    duration_month=t.duration_month,
                    prior_ratio=t.prior,
                    ratio=float(case.legal_rate) / 100,
                )
            )
        return out

    treatments = _costs(case.treatments)
    orthoses = _costs(case.orthoses)
    treatment_total = sum((c.total() for c in treatments), Decimal(0))
    orthosis_total = sum((c.total() for c in orthoses), Decimal(0))
    future_care = total_caregiving(care_rows)

    income_total = total_income(rows)
    passive = income_total + case.severance
    active = case.past_treatment + treatment_total + past_care + future_care + orthosis_total
    property_damage = passive + active

    st = settle(
        property_damage,
        case.fault_rate,
        pre_offset_deduction=case.pre_offset_deduction,
        paid_cure=case.paid_cure,
        prior_ratio=prior,
        advance=case.advance,
        ratio_deduction=case.ratio_deduction,
        full_deduction=case.full_deduction,
        solatium=case.solatium,
    )

    y = age_at(case.birth, case.accident)
    return Result(
        case=case,
        age=(y.year, y.month, y.day),
        combined_rate=combined,
        prior_contribution=prior,
        income_rows=rows,
        income_total=income_total,
        caregiving_rows=care_rows,
        past_caregiving_total=past_care,
        future_caregiving_total=future_care,
        treatment_rows=treatments,
        treatment_total=treatment_total,
        orthosis_rows=orthoses,
        orthosis_total=orthosis_total,
        passive_total=passive,
        active_total=active,
        property_damage=property_damage,
        settlement=st,
        solatium_auto=solatium_auto(combined, case.fault_rate),
    )
