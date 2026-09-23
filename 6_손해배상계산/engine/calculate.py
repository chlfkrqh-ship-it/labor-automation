"""사건 하나를 끝까지 계산한다. 엑셀표 생성의 입력이 되는 결과 묶음.

여명단축(부상): 여명 종료일이 가동종료일보다 앞서면 여명 종료 다음 날부터 가동종료일까지
상실률을 SHORTENED_LIFE_LOSS_RATE(66.66666666)로 둔다. 생계비 1/3 을 상실률로 공제하는 방식이다
(income.py·constants.py, 설명서 16쪽). 이 분기는 대법원 프로그램 출력과 대조하지 않았으므로
결과에 경고를 남긴다. 여명 종료일이 입원치료 종료일 이전이면 어느 상실률을 쓰는지 확인되지
않아 계산하지 않는다.

향후 개호비 단가: 원본은 개호비 화면에서 직종(jikCd)을 따로 골라 그 단가를 쓴다
(caregiving.py 의 GetWageFromSalaryDayTable(jikCd, ...)). 피해자의 일실수입 노임과 별개의 입력이므로
피해자 노임으로 대신 계산하지 않는다. 호출자가 caregiving_price_of 를 넘기거나 사건 파일에
caregiving_wages(개호 노임단가 표)를 적어야 하며, 둘 다 없으면 멈춘다.

장례비(사망): 재산적 손해·과실상계·합계에 넣지 않는다. 골든 케이스 2(구 프로그램) 출력도
장례비 5,000,000원을 적고 재산상 손해를 일실수입과 같게 두었다. 장례비를 지출한 사람의
청구액은 엔진이 계산하지 않으므로 결과에 경고를 남긴다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from .caregiving import CaregivingRow, build_caregiving_rows, past_caregiving, total_caregiving
from .case import Case
from .constants import (
    HOSPITALIZED_LOSS_RATE,
    LIVING_COST_DEATH,
    LIVING_COST_INJURY,
    SHORTENED_LIFE_LOSS_RATE,
)
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
    wage_basis: str = ""                  # 일실수입 노임 기준 (계산표 표시용)
    caregiving_basis: str = ""            # 향후 개호비 단가 기준 (계산표 표시용)
    warnings: list[str] = field(default_factory=list)   # 사람이 확인할 점 ('경고' 시트)


def _fmt(d: date) -> str:
    return f"{d:%Y. %m. %d.}".replace(" 0", " ")


def _default_wage_basis(case: Case) -> str:
    """호출자가 노임 기준을 알려 주지 않을 때 사건 입력에서 만든 표시 문구."""
    if case.wages:
        return "노임단가 직접입력"
    if case.rural:
        return f"농촌 일용노임({'여' if case.sex == 'F' else '남'})"
    return f"직종별 노임 — {case.occupation}"


def _caregiving_table(case: Case):
    """사건 파일의 caregiving_wages(개호 노임단가 표) -> (단가 조회기, has_wage).

    키는 '연도-번호'. 번호는 반기(1·2), caregiving_rural 이면 분기(1~4)다.
    표의 마지막 구간 뒤는 마지막 단가를 쓴다(원본 GetWageFromSalaryDayTableNext — 마지막 공표 단가).
    표의 첫 구간 앞이나 표 중간에 빈 구간이 있으면 멈춘다.
    """
    top = 4 if case.caregiving_rural else 2
    kind = "분기" if case.caregiving_rural else "반기"
    table: dict[tuple[int, int], Decimal] = {}
    for key, value in case.caregiving_wages.items():
        try:
            y, i = (int(x) for x in str(key).split("-"))
        except ValueError:
            raise ValueError(
                f"개호 노임단가 표의 '{key}' 는 '연도-{kind}'(예: 2024-1) 형식이 아닙니다."
            ) from None
        if not 1 <= i <= top:
            hint = " 분기 단가라면 caregiving_rural 을 true 로 두십시오." if not case.caregiving_rural else ""
            raise ValueError(f"개호 노임단가 표의 '{key}': {kind} 번호는 1~{top} 이어야 합니다.{hint}")
        table[(y, i)] = Decimal(str(value))
    first, last = min(table), max(table)
    cur, missing = first, []
    while cur < last:
        cur = (cur[0], cur[1] + 1) if cur[1] < top else (cur[0] + 1, 1)
        if cur not in table:
            missing.append(f"{cur[0]}-{cur[1]}")
    if missing:
        raise ValueError(f"개호 노임단가 표에 빠진 {kind}가 있습니다: {', '.join(missing)}")

    def price_of(p):
        key = (p.year, p.index)
        if key in table:
            return table[key]
        if key > last:
            return table[last]
        raise ValueError(
            f"개호 노임단가 표에 {p.year}년 {p.index}{kind} 단가가 없습니다"
            f"(표: {first[0]}-{first[1]} ~ {last[0]}-{last[1]}). 개호 시작 구간부터 적으십시오."
        )

    return price_of, (lambda y, i: (y, i) in table)


def calculate(
    case: Case,
    wage_of,
    has_wage=None,
    caregiving_price_of=None,
    caregiving_has_wage=None,
    wage_basis: str | None = None,
    caregiving_basis: str | None = None,
) -> Result:
    """wage_of(period) -> 일 노임단가.  has_wage(year, index) -> bool.

    caregiving_price_of / caregiving_has_wage  향후 개호비 단가 조회기(개호 기준 직종·농촌 여부는
        caregiving_rural). 넘기지 않으면 case.caregiving_wages 표를 쓴다. 피해자 노임(wage_of)으로
        대신하지 않는다.
    wage_basis / caregiving_basis  계산표에 적을 노임·개호 단가 기준 문구(예: 고른 직종명과 코드).
        비우면 사건 입력에서 만든다.
    """
    warnings: list[str] = []
    work_end = case.resolved_work_end()
    items = [
        Impairment(i.rate, i.prior, i.years if i.years else None, i.dept)
        for i in case.impairments
    ]
    combined = truncate2(combined_with_prior(items)) if items else Decimal(0)
    prior = truncate2(prior_contribution(items)) if items else Decimal(0)

    death = case.injury_type == "사망"
    living_cost = LIVING_COST_DEATH if death else LIVING_COST_INJURY

    boundaries = []
    if case.cure_end and not death:
        boundaries.append(date.fromordinal(case.cure_end.toordinal() + 1))

    life_cut = None
    if not death and case.life_end and case.life_end < work_end:
        if case.life_end < case.accident:
            raise ValueError(
                f"여명 종료일({_fmt(case.life_end)})이 사고일자({_fmt(case.accident)})보다 앞섭니다. "
                "입력을 확인하십시오."
            )
        if case.cure_end and case.life_end <= case.cure_end:
            raise ValueError(
                f"여명 종료일({_fmt(case.life_end)})이 입원치료 종료일({_fmt(case.cure_end)}) 이전입니다. "
                "입원기간 상실률 100%와 여명단축 상실률 66.66666666% 가운데 무엇을 쓰는지 확인되지 않아 "
                "엔진이 계산하지 않습니다. 대법원 프로그램으로 계산하십시오."
            )
        life_cut = case.life_end
        boundaries.append(date.fromordinal(life_cut.toordinal() + 1))
        warnings.append(
            f"여명단축: 여명 종료일({_fmt(life_cut)})이 가동종료일({_fmt(work_end)})보다 앞서 "
            f"{_fmt(date.fromordinal(life_cut.toordinal() + 1))}부터 가동종료일까지 상실률 "
            f"{SHORTENED_LIFE_LOSS_RATE}%(생계비 1/3 공제)를 적용했습니다. 이 분기는 대법원 프로그램 "
            "출력과 대조하지 않았으니 제출 전 프로그램으로 확인하십시오."
        )

    def loss_rate_of(p):
        if death:
            return Decimal(100)
        if life_cut and p.start > life_cut:
            return SHORTENED_LIFE_LOSS_RATE
        if case.cure_end and p.end <= case.cure_end:
            return HOSPITALIZED_LOSS_RATE
        return combined

    rows = build_income_rows(
        accident_date=case.accident,
        start=case.accident,
        end=work_end,
        wage_of=wage_of,
        loss_rate_of=loss_rate_of,
        rural=case.rural,
        living_cost=living_cost,
        ratio=float(case.legal_rate) / 100,
        has_wage=has_wage,
        boundaries=boundaries,
    )

    care_rows = []
    care_basis = ""
    if case.caregiving_start and case.caregiving_end:
        if caregiving_price_of is not None:
            price_of, care_has = caregiving_price_of, caregiving_has_wage
            care_basis = caregiving_basis or "호출자가 지정한 개호 단가"
        elif case.caregiving_wages:
            price_of, care_has = _caregiving_table(case)
            care_basis = caregiving_basis or (
                f"개호 노임단가 직접입력({'분기' if case.caregiving_rural else '반기'})"
            )
        else:
            raise ValueError(
                "향후 개호비 단가가 없습니다. 개호 단가는 피해자의 일실수입 노임과 따로 정하는 입력입니다"
                "(원본은 개호비 화면에서 직종을 따로 고릅니다). 사건 파일에 caregiving_wages"
                "(개호 노임단가 표, 예: {\"2024-1\": 165545})를 적거나, 노임표의 직종 노임을 쓰려면 "
                "caregiving_occupation(예: 보통인부)을 적으십시오. 분기 단가(농촌)라면 표에 적고 "
                "caregiving_rural 도 true 로 두십시오. 피해자 노임으로 대신 계산하지 않습니다."
            )
        care_rows = build_caregiving_rows(
            accident_date=case.accident,
            start=case.caregiving_start,
            end=case.caregiving_end,
            unit_price_of=price_of,
            headcount=case.caregiving_headcount,
            prior_ratio=prior,
            rural=case.caregiving_rural,
            ratio=float(case.legal_rate) / 100,
            has_wage=care_has,
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

    if death and case.funeral_cost:
        warnings.append(
            f"장례비 {int(case.funeral_cost):,}원은 재산적 손해·과실상계·합계에 넣지 않았습니다. "
            "장례비를 지출한 사람의 청구액(과실상계 후 금액)은 엔진이 계산하지 않으니 "
            "대법원 프로그램으로 확인하십시오."
        )
    zero_steps = [str(r.step) for r in rows if r.wage == 0]
    if zero_steps:
        warnings.append(
            f"노임단가가 0원인 일실수입 순번이 있습니다(순번 {', '.join(zero_steps)}). 노임표에 그 구간 "
            "단가가 비어 있는 것으로 보이니 노임단가를 직접 입력하십시오."
        )
    zero_care = [str(r.step) for r in care_rows if r.unit_price == 0]
    if zero_care:
        warnings.append(
            f"개호비 단가가 0원인 향후 개호비 순번이 있습니다(순번 {', '.join(zero_care)}). 개호 단가를 확인하십시오."
        )

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
        wage_basis=wage_basis or _default_wage_basis(case),
        caregiving_basis=care_basis,
        warnings=warnings,
    )
