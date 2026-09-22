"""지연손해금 — 근로기준법 제37조 연 20%, 상사 6%·민사 5%, 소송촉진법 이율, 소멸시효 표시
(lane: delay_interest, 규칙 DI-01~DI-17 / 해고기간 임금 20% 쟁점: dismissal_interest_20).

다른 모듈이 만든 원금 항목(`Claim`)마다 날짜별 이율을 정해 구간표를 만들고,
(1) 청구취지·주문형 문구(기산일·이율 구간, 끝은 '다 갚는 날까지'), (2) 기준일까지의 금액,
(3) 소멸시효 완성일 표시를 낸다. 해고 무효·다툼의 적절성 같은 법적 판단은 하지 않는다.
사람이 사건.yaml `interest:` 절에 적은 날짜(송달일, 사실심 선고일 등)로 계산만 한다.

---------------------------------------------------------------- 이율
DI-01 [법령] 민사 연 5%(민법 제379조), 상사 연 6%(상법 제54조), 근로기준법 지연이자 연 20%
      (시행령 제17조 "연 100분의 20"). 20%는 **지급사유 발생일이 2005. 7. 1. 이후**인 금품에만
      (법률 제7465호 부칙 "시행 후 최초로 지급사유가 발생하는 경우부터") — 날짜 구간으로 구현하지 않는다.
      소송촉진법 법정이율: 1981. 3. 1. 25% → 2003. 6. 1. 20% → 2015. 10. 1. 15% → 2019. 6. 1. 12%.
      2015·2019 개정 부칙: 시행 당시 1심 변론이 종결된 사건은 종전 이율(`first_instance_close_date`).
      2003 부칙은 원문 재대조 안 됨 → 1심 변론종결일이 2003. 6. 1. 전이면 경과조치를 적용하지 않고 warning.
DI-02 [법령·판례확립] 퇴직·사망 청산 금품(Claim.settlement=True)은 지급사유 발생일부터 14일이 되는 날
      (= 마지막 근무일 + 14일, Claim.due_date)까지 미지급이면 그 다음 날부터 20%. 14일째가 일요일이어도
      다음 날부터(민법 제161조 미적용, 판결 확인).
DI-03 [법령/판례확립/불명확] 재직 중 정기임금(Claim.settlement=False)
      - 개정 제37조 제1항 제2호(법률 제20520호, 2025. 10. 23. 시행): 제43조 제2항 정기지급일까지
        미지급이면 다음 날부터 20%. 부칙 제2조 "시행 이후 … 지연이자 지급사유가 발생하는 경우부터".
        경계 정기지급일 2025. 10. 22.(고용노동부 Q&A '10. 23. 0시부터 지급 지연') — 판결 확인 없음,
        `di_new_law_cutoff`. 퇴직 후에도 정기지급일 기준 유지(제37조 제2항).
      - 구법 적용분: 재직(복직) 중이면 20% 없음 — 대법원 2014. 8. 26. 선고 2014다28305(원심 판단
        수긍) "해고가 무효로 되어 갑이 복직한 이상 이에 해당한다고 보기 어렵고 … 상법이 정한 연 6%".
        근로관계가 끝났으면(정년·계약만료·사직·재해고) 마지막 근무일 + 15일부터 20%(하급심 다수:
        서울고법 2017나28919 확정, 대전고법 2019나13573 심리불속행). 재해고로 끝난 경우는 확정 고법
        판결이 갈린다(대전고법 2019나13573 적용 / 서울고법 2021나2031970 부정) → `di_redismissal_20`.
      - 개정법 도래분을 해고기간 임금에 적용하는 1심은 세 갈래(서울북부 2026가합20004 지급일 다음날부터
        20%·배제 없음 / 서울중앙 2025가합10452 선고일까지 배제 / 창원 2025구합1375 선고 후 12%).
        기본 계산에 20%를 쓰고 '대안: 개정법 미적용' 결과를 함께 낸다.
DI-04 [법령] 20% 적용 제외(제37조 제3항, 시행령 제18조): 회생·파산 등, 자금 확보 곤란, 존부를 법원·
      노동위원회에서 다투는 것이 적절, 이에 준하는 사유 — "그 사유가 존속하는 기간"만. `exclusions[]`.
DI-05 [판례확립] 제18조 제3호 기준은 "사용자 주장에 상당한 근거"(대법원 2026. 4. 30. 선고 2026다200272,
      2022. 3. 31. 선고 2020다294486). 종기는 사실심 판결 선고일 — 당일까지 저율, 다음 날부터 20%.
      1심 일부 인용 후 항소심 유지도 원심 선고 시까지(2020다294486). 판결 확정일까지 배제한 판결은 없고
      서울고법 2019나2050152(확정) "판결 확정 이후에 이르러서야 … 적용된다고 볼 수는 없다" → `finality`
      선택 시 warning. 해고무효가 이미 확정되었으면 배제 없음(`dismissal_validity_settled`).
DI-06 [판례확립] 20% 미적용 구간: 사용자가 상인이면 6%, 비상인(의료법인·학교법인·비영리법인 등) 5%.
      `employer_merchant` 필수.
DI-07 [법령·판례확립] 소송촉진법 이율: 소장 부본 송달 다음 날부터. 다투는 것이 타당한 범위에서 사실심
      선고일까지 배제(제3조 제2항). 장래이행 부분 제외(이 모듈은 과거분만 받는다).
DI-08 [판례확립/하급심] 같은 날 이율을 겹치지 않는다. 우선순위 20% → 소송촉진법 → 6%/5%.
      회생 등 제18조 제1호 제외기간에 소송촉진법 이율을 붙인 사례는 약해서(서울서부 2019가단214470)
      기본 미적용, `di_sokchok_in_exclusion`.
DI-09 [판례확립·법령] 재직 중 임금 기본형: 정기지급일 다음 날부터 6%/5%, 송달 다음 날부터 소송촉진법 이율.
DI-10 확정 지연손해금의 원금화: 구현하지 않음(원본이 상사채권일 때 이율 미확인) → 필요하면 수동 항목.
---------------------------------------------------------------- 일할·끝수·충당
DI-11 [불명확] `원금 × 연이율 × 기간`, 기산일·종기 모두 산입. 1년 이상이면 기산일부터 만 N년 + 잔여일수/분모.
      분모: 잔여기간에 2. 29.이 들면 366(`anniv_feb29`, 기본) / 잔여기간 종료연도가 윤년이면 366
      (`anniv_endyear_leap`) — 판결 골든 4건은 둘 다와 일치하고 2024. 3. 1.~12. 31.처럼 갈리는 경우는 판결
      미확인. 그 밖에 `calendar_split`(역년별 분모), `actual_365`.
DI-12 [실무관행] 구간별 산출 후 원 미만 버림, 합산(`floor_per_segment`) / 합계 후 버림(`floor_total`).
DI-13 [판례확립] 원금은 세전. 원천징수세액은 실제 납부한 경우 그 납부일에 원금에서 뺀다(대법원 2013다36347,
      다툼으로 소송에 이른 경우 달리 볼 여지 유보) → `payments[].kind = withholding` 은 원금 직접 감액 + warning.
DI-14 [법령] 변제충당: 이자(지연손해금) → 원본(민법 제479조). `payments[].kind = payment`.
DI-15 [법령·판례확립] 소멸시효 3년(근로기준법 제49조, 퇴직급여법 제10조). 임금은 정기지급일부터,
      청산 금품은 지급사유 발생일(마지막 근무일 다음 날)부터. 초일 불산입 → 만료일 = 기산일의 3년 뒤 해당일.
      말일이 토·일요일이면 다음 날(민법 제161조, 판례 미확인, `di_limitation_weekend_shift`; 공휴일은 모름).
      소 제기일(`suit_filed_date`)이 만료일 뒤면 '시효 완성 의심' 표시(재판 외 최고·일부청구는 사람이 판단).
DI-16 DC형 부담금 지연이자(연 10%→20%): 범위 밖, 구현하지 않음.
DI-18 [법령] 근로기준법 적용 제외 사업(동거 친족만 사용하는 사업·가사 사용인, 제11조 제1항 단서)은 제37조 20% 없음
      → `lsa_not_applicable`. 상시 4명 이하 사업장은 시행령 별표 1이 제36조~제37조를 적용하므로 20% 적용.
      해고예고수당의 20% 대상 여부는 하급심이 갈려 warning 만(settlement 값은 사람이 정함).
검증: 반박 검증 메모(delay_interest_검증메모.md) 판정 반영. 검색 보강(결정례·유권해석 탭, 3페이지)은 하지 않았다.
DI-17 [법령] 청구 범위 제한: `di_claimed_rate_cap`(연 %) — 원고가 구한 이율보다 높게 계산하지 않는다.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from .common import (
    Claim, LaborError, OptionSpec, Trace, add_months, dec, parse_date, round_money,
)

# ---------------------------------------------------------------- 옵션·규칙
OPTIONS: dict[str, OptionSpec] = {s.key: s for s in [
    OptionSpec("di_new_law_cutoff", "2025-10-22",
               "개정 제37조 제1항 제2호를 적용하는 첫 정기지급일", "DI-03"),
    OptionSpec("di_regime", "auto", "재직 중 정기임금의 20% 적용 방식", "DI-03", {
        "auto": "개정법 도래분(정기지급일 ≥ 경계일)은 지급일 다음 날부터 20%, 대안 결과를 함께 출력",
        "new_2ho_off": "개정법 도래분에도 20% 미적용(보수적)",
        "old_only": "구법 규칙만 적용(개정법 무시)",
    }),
    OptionSpec("di_ended_old_law_20", True,
               "구법 도래분이 퇴직(근로관계 종료) 때까지 미지급이면 마지막 근무일 + 15일부터 20%", "DI-03"),
    OptionSpec("di_redismissal_20", True,
               "재해고로 근로관계가 끝난 경우에도 위 20% 적용(대전고법 2019나13573 / 반대 서울고법 2021나2031970)",
               "DI-03"),
    OptionSpec("di_exclusion_end", "final_fact_instance", "제18조 제3호·소송촉진법 제3조 제2항 배제 종기", "DI-05", {
        "final_fact_instance": "사실심 최종 선고일(항소심 선고일이 있으면 그날, 없으면 1심 선고일)",
        "first_instance": "1심 선고일",
        "none": "배제 없음(사용자가 다투지 않았거나 해고무효가 이미 확정)",
        "finality": "판결 확정일(근거 판결 없음 — 서울고법 2019나2050152 반대)",
    }),
    OptionSpec("di_sokchok_in_exclusion", False,
               "회생 등 20% 제외기간에 소송촉진법 이율 적용(근거 약함)", "DI-08"),
    OptionSpec("di_day_count", "anniv_feb29", "일할 계산 분모", "DI-11", {
        "anniv_feb29": "만 N년 + 잔여일수/(잔여기간에 2. 29. 포함 시 366, 아니면 365)",
        "anniv_endyear_leap": "만 N년 + 잔여일수/(잔여기간 종료연도 윤년이면 366)",
        "calendar_split": "역년별 일수/그해 일수 합",
        "actual_365": "총일수/365",
    }),
    OptionSpec("di_rounding", "floor_per_segment", "지연손해금 끝수", "DI-12", {
        "floor_per_segment": "구간별 원 미만 버림 후 합산",
        "floor_total": "원금 항목별 합계 후 원 미만 버림",
    }),
    OptionSpec("di_claimed_rate_cap", None, "원고가 구한 최고 이율(연 %). 비우면 제한 없음", "DI-17"),
    OptionSpec("di_limitation_weekend_shift", True,
               "시효 만료일이 토·일요일이면 다음 날로(민법 제161조, 판례 미확인)", "DI-15"),
]}

RULES: dict[str, tuple[str, str]] = {
    "DI-01": ("이율표(5%/6%/20%/소송촉진법 25→20→15→12%), 20%는 지급사유 발생일 2005. 7. 1. 이후분", "법령"),
    "DI-02": ("퇴직 청산 금품은 마지막 근무일 + 15일부터 20%", "법령·판례확립"),
    "DI-03": ("재직 중 임금: 개정법 도래분 지급일 다음 날부터 20%, 구법분은 복직이면 없음·종료면 종료일+15일부터", "법령/판례확립/불명확"),
    "DI-04": ("20% 적용 제외 사유는 존속기간만", "법령"),
    "DI-05": ("다툼 적절 시 사실심 선고일까지 20% 배제", "판례확립"),
    "DI-06": ("20% 미적용 구간: 상인 6%, 비상인 5%", "판례확립"),
    "DI-07": ("소송촉진법 이율은 송달 다음 날부터, 다툼 타당 범위는 선고일까지 배제", "법령·판례확립"),
    "DI-08": ("같은 날 이율 중첩 없음: 20% → 소송촉진법 → 6%/5%", "판례확립"),
    "DI-09": ("재직 중 임금 기본형: 지급일 다음 날부터 6%/5%", "판례확립"),
    "DI-11": ("일할: 만 N년 + 잔여일수/분모(분모 규칙 옵션)", "불명확"),
    "DI-12": ("구간별 원 미만 버림", "실무관행"),
    "DI-13": ("원금은 세전, 실제 납부한 원천세만 납부일에 감액", "판례확립"),
    "DI-14": ("변제충당: 이자 → 원본", "법령"),
    "DI-15": ("소멸시효 3년 만료일 표시", "법령·판례확립"),
    "DI-17": ("원고가 구한 이율 상한", "법령"),
    "DI-18": ("근로기준법 적용 제외 사업은 20% 없음, 해고예고수당 20% 여부는 경고", "법령/하급심"),
}

LSA20_EFFECTIVE = date(2005, 7, 1)
LSA20 = Decimal("20")
SOKCHOK_TABLE = [   # (시행일, 연 %)
    (date(1981, 3, 1), Decimal("25")),
    (date(2003, 6, 1), Decimal("20")),
    (date(2015, 10, 1), Decimal("15")),
    (date(2019, 6, 1), Decimal("12")),
]
SOKCHOK_TRANSITIONS = (date(2015, 10, 1), date(2019, 6, 1))
END_CAUSES = {"retirement": "정년", "contract_end": "계약기간 만료", "resignation": "사직",
              "redismissal": "재해고", "death": "사망", "other": "기타"}


# ---------------------------------------------------------------- 입력
@dataclass
class Exclusion:
    start: date
    end: date
    reason: str = ""


@dataclass
class Payment:
    date: date
    amount: Decimal
    claim: str = ""          # 원금 항목 label. 비우면 적용하지 않고 warning
    kind: str = "payment"    # payment(이자 → 원본 충당) | withholding(원금 직접 감액)


@dataclass
class InterestInput:
    employer_merchant: bool
    calc_until: date | None = None
    service_date: date | None = None
    first_instance_judgment_date: date | None = None
    appellate_judgment_date: date | None = None
    finality_date: date | None = None
    first_instance_close_date: date | None = None
    suit_filed_date: date | None = None
    last_working_day: date | None = None      # 근로관계 종료 시 마지막 근무일(재직이면 None)
    end_cause: str = ""
    dismissal_validity_settled: bool = False
    lsa_not_applicable: bool = False          # 동거 친족만 사용하는 사업·가사 사용인(제11조 제1항 단서)
    exclusions: list[Exclusion] = field(default_factory=list)
    payments: list[Payment] = field(default_factory=list)
    items: list[Claim] = field(default_factory=list)   # 다른 모듈 밖에서 직접 넣는 원금


def _d(v, label):
    if v in (None, ""):
        return None
    try:
        return parse_date(v)
    except Exception as exc:
        raise LaborError(f"interest.{label}: 날짜 형식이 아닙니다: {v!r}") from exc


def load_interest(raw: dict | None, worker: dict | None = None) -> InterestInput:
    """사건.yaml `interest:` 절.

    interest:
      employer_merchant: true           # 필수(없으면 worker.employer_merchant). 회사=상인 6%, 비상인 5%
      calc_until: 2026-10-01            # 금액 계산 기준일. 비우면 구간표·문구만
      service_date: 2025-08-20          # 소장 부본 송달일
      first_instance_judgment_date: 2026-10-01   # 선고(예정)일
      appellate_judgment_date: null
      finality_date: null
      first_instance_close_date: null   # 소송촉진법 경과조치용 1심 변론종결일
      suit_filed_date: 2025-08-01       # 시효 표시
      end_cause: retirement             # 근로관계 종료 사유: retirement|contract_end|resignation|redismissal|death|other
      dismissal_validity_settled: false # 해고무효(구제명령)가 이미 확정·다툼 없음이면 true → 배제 없음
      exclusions: [{start: 2024-01-10, end: 2024-06-30, reason: 회생절차}]   # 제18조 제1·2·4호
      payments: [{date: 2026-01-05, amount: 1000000, claim: "2024. 3.분", kind: payment}]
      items: [{category: 해고예고수당, label: 해고예고수당, amount: 3000000, due_date: 2024-03-15, settlement: true}]
    마지막 근무일은 worker.last_working_day 를 쓴다.
    """
    raw = dict(raw or {})
    worker = dict(worker or {})
    merchant = raw.get("employer_merchant", worker.get("employer_merchant"))
    if merchant is None:
        raise LaborError("interest.employer_merchant(사용자가 상인인지 여부)가 없습니다. "
                         "회사면 true(연 6%), 의료법인·학교법인·비영리법인·개인 비상인이면 false(연 5%).")
    end_cause = str(raw.get("end_cause") or "")
    if end_cause and end_cause not in END_CAUSES:
        raise LaborError(f"interest.end_cause 값 {end_cause!r} 은 허용되지 않습니다. 가능: {', '.join(END_CAUSES)}")
    items = []
    for i, it in enumerate(raw.get("items") or []):
        for k in ("label", "amount", "due_date"):
            if it.get(k) in (None, ""):
                raise LaborError(f"interest.items[{i}].{k} 가 없습니다.")
        items.append(Claim(str(it.get("category") or "기타"), str(it["label"]), dec(it["amount"]),
                           _d(it["due_date"], f"items[{i}].due_date"), bool(it.get("settlement", False)),
                           str(it.get("note") or "")))
    pays = []
    for i, p in enumerate(raw.get("payments") or []):
        kind = str(p.get("kind") or "payment")
        if kind not in ("payment", "withholding"):
            raise LaborError(f"interest.payments[{i}].kind 는 payment 또는 withholding 입니다.")
        if p.get("date") in (None, "") or p.get("amount") in (None, ""):
            raise LaborError(f"interest.payments[{i}] 에 date·amount 가 필요합니다.")
        pays.append(Payment(_d(p["date"], f"payments[{i}].date"), dec(p["amount"]), str(p.get("claim") or ""), kind))
    excl = []
    for i, e in enumerate(raw.get("exclusions") or []):
        s, t = _d(e.get("start"), f"exclusions[{i}].start"), _d(e.get("end"), f"exclusions[{i}].end")
        if not s or not t or t < s:
            raise LaborError(f"interest.exclusions[{i}] 의 start·end 가 없거나 순서가 맞지 않습니다.")
        excl.append(Exclusion(s, t, str(e.get("reason") or "")))
    return InterestInput(
        employer_merchant=bool(merchant),
        calc_until=_d(raw.get("calc_until"), "calc_until"),
        service_date=_d(raw.get("service_date"), "service_date"),
        first_instance_judgment_date=_d(raw.get("first_instance_judgment_date"), "first_instance_judgment_date"),
        appellate_judgment_date=_d(raw.get("appellate_judgment_date"), "appellate_judgment_date"),
        finality_date=_d(raw.get("finality_date"), "finality_date"),
        first_instance_close_date=_d(raw.get("first_instance_close_date"), "first_instance_close_date"),
        suit_filed_date=_d(raw.get("suit_filed_date"), "suit_filed_date"),
        last_working_day=_d(raw.get("last_working_day", worker.get("last_working_day")), "last_working_day"),
        end_cause=end_cause,
        dismissal_validity_settled=bool(raw.get("dismissal_validity_settled", False)),
        lsa_not_applicable=bool(raw.get("lsa_not_applicable", False)),
        exclusions=excl, payments=pays, items=items,
    )


# ---------------------------------------------------------------- 결과
@dataclass
class Segment:
    start: date
    end: date | None          # None = 다 갚는 날까지
    rate: Decimal
    rule: str                 # DI-xx
    basis: str                # '상사 6%', '근로기준법 20%', '소송촉진법 12%' 등


@dataclass
class InterestRow:
    claim: str
    category: str
    principal: Decimal
    start: date
    end: date
    days: int
    fraction: str             # '1년 + 45/366' 등
    rate: Decimal
    basis: str
    rule: str
    interest: Decimal


@dataclass
class LimitationRow:
    claim: str
    category: str
    start: date
    expiry: date
    suspect: bool | None      # 소 제기일이 없으면 None


@dataclass
class ClaimSchedule:
    claim: Claim
    segments: list[Segment]
    interest_total: Decimal = Decimal(0)
    order_text: str = ""


@dataclass
class InterestResult:
    rows: list[InterestRow]
    total: Decimal
    claims: list[Claim]
    trace: list[Trace]
    warnings: list[str]
    schedules: list[ClaimSchedule] = field(default_factory=list)
    limitation: list[LimitationRow] = field(default_factory=list)
    alternatives: dict = field(default_factory=dict)   # 이름 -> (합계, schedules) — 대안 계산
    order_text: str = ""


# ---------------------------------------------------------------- 날짜·이율
def _add_years(d: date, n: int) -> date:
    return add_months(d, 12 * n)


def year_fraction(start: date, end: date, mode: str) -> tuple[Decimal, str]:
    """[start, end] 양끝 포함 기간의 연 환산값과 설명(DI-11)."""
    days = (end - start).days + 1
    if mode == "actual_365":
        return Decimal(days) / 365, f"{days}/365"
    if mode == "calendar_split":
        total, parts = Decimal(0), []
        for y in range(start.year, end.year + 1):
            a, b = max(start, date(y, 1, 1)), min(end, date(y, 12, 31))
            n, den = (b - a).days + 1, 366 if calendar.isleap(y) else 365
            total += Decimal(n) / den
            parts.append(f"{n}/{den}")
        return total, " + ".join(parts)
    n = 0
    while _add_years(start, n + 1) - timedelta(days=1) <= end:
        n += 1
    rest_start = _add_years(start, n)
    if rest_start > end:
        return Decimal(n), f"{n}년"
    rem = (end - rest_start).days + 1
    if mode == "anniv_feb29":
        den = 366 if any(calendar.isleap(y) and rest_start <= date(y, 2, 29) <= end
                         for y in range(rest_start.year, end.year + 1)) else 365
    elif mode == "anniv_endyear_leap":
        den = 366 if calendar.isleap(end.year) else 365
    else:
        raise LaborError(f"일할 방식을 알 수 없습니다: {mode}")
    return Decimal(n) + Decimal(rem) / den, (f"{n}년 + " if n else "") + f"{rem}/{den}"


def sokchok_rate(d: date, close: date | None = None) -> Decimal | None:
    """소송촉진법 법정이율(DI-01). close = 1심 변론종결일(2015·2019 경과조치)."""
    def table(x: date) -> Decimal | None:
        rate = None
        for since, r in SOKCHOK_TABLE:
            if x >= since:
                rate = r
        return rate

    if close is not None and close < d and any(close < c <= d for c in SOKCHOK_TRANSITIONS):
        return table(close)
    return table(d)


# ---------------------------------------------------------------- 계산
def _exclusion_end(inp: InterestInput, o: dict, warnings: list) -> date | None:
    mode = o["di_exclusion_end"]
    if inp.dismissal_validity_settled or mode == "none":
        return None
    if mode == "first_instance":
        return inp.first_instance_judgment_date
    if mode == "finality":
        warnings.append("배제 종기를 판결 확정일로 두었습니다. 확정일까지 배제한 판결은 확인되지 않았고 "
                        "서울고법 2019나2050152(확정)는 '판결 확정 이후에 이르러서야 … 적용된다고 볼 수는 없다'고 했습니다.")
        return inp.finality_date
    return inp.appellate_judgment_date or inp.first_instance_judgment_date


def _lsa20_start(c: Claim, inp: InterestInput, o: dict, regime: str, trace: list, warnings: list) -> tuple[date | None, str]:
    """20% 기산일과 근거 문구. 적용 없으면 (None, 사유)."""
    if inp.lsa_not_applicable:
        return None, "근로기준법 적용 제외 사업(제11조 제1항 단서) — 제37조 없음"
    if c.settlement:
        trigger = c.due_date - timedelta(days=13)      # 지급사유 발생일(= 마지막 근무일 다음 날)
        if trigger < LSA20_EFFECTIVE:
            return None, "지급사유 발생일이 2005. 7. 1. 전(DI-01)"
        return c.due_date + timedelta(days=1), "퇴직 청산 금품 14일 경과(DI-02)"

    cutoff = parse_date(o["di_new_law_cutoff"])
    if regime == "auto" and c.due_date >= cutoff:
        return c.due_date + timedelta(days=1), "개정 제37조 제1항 제2호 정기지급일 경과(DI-03, 불명확)"

    end = inp.last_working_day
    if end is None or not o["di_ended_old_law_20"]:
        return None, "재직(복직) 중 구법 적용분(DI-03, 2014다28305)"
    if inp.end_cause == "redismissal" and not o["di_redismissal_20"]:
        return None, "재해고로 종료 — 20% 미적용 옵션(서울고법 2021나2031970)"
    start = max(end + timedelta(days=15), c.due_date + timedelta(days=1))
    if end + timedelta(days=15) < LSA20_EFFECTIVE:
        return None, "퇴직일이 2005. 7. 1. 전(DI-01)"
    return start, "근로관계 종료 후 14일 경과(DI-03, 하급심 다수)"


def _schedule(c: Claim, inp: InterestInput, o: dict, regime: str, trace: list, warnings: list) -> list[Segment]:
    base_rate = Decimal("6") if inp.employer_merchant else Decimal("5")
    base_label = "상사 6%" if inp.employer_merchant else "민사 5%"
    start = c.due_date + timedelta(days=1)
    lsa_start, lsa_why = _lsa20_start(c, inp, o, regime, trace, warnings)
    excl_end = _exclusion_end(inp, o, warnings)
    sok_start = inp.service_date + timedelta(days=1) if inp.service_date else None
    cap = dec(o.get("di_claimed_rate_cap"))

    # 이율이 바뀔 수 있는 날을 모두 모은다.
    points = {start}
    for p in (lsa_start, sok_start, excl_end and excl_end + timedelta(days=1)):
        if p and p > start:
            points.add(p)
    for e in inp.exclusions:
        for p in (e.start, e.end + timedelta(days=1)):
            if p > start:
                points.add(p)
    for since, _ in SOKCHOK_TABLE:
        if since > start:
            points.add(since)
    ordered = sorted(points)

    def rate_on(d: date) -> tuple[Decimal, str, str]:
        in_dispute = excl_end is not None and d <= excl_end
        in_other_excl = any(e.start <= d <= e.end for e in inp.exclusions)
        if lsa_start and d >= lsa_start and not in_dispute and not in_other_excl:
            return LSA20, "근로기준법 20%", "DI-02" if c.settlement else "DI-03"
        if sok_start and d >= sok_start and not in_dispute and (not in_other_excl or o["di_sokchok_in_exclusion"]):
            r = sokchok_rate(d, inp.first_instance_close_date)
            if r is not None:
                return r, f"소송촉진법 {r}%", "DI-07"
        return base_rate, base_label, "DI-06" if lsa_start else "DI-09"

    segs: list[Segment] = []
    for i, s in enumerate(ordered):
        e = ordered[i + 1] - timedelta(days=1) if i + 1 < len(ordered) else None
        r, label, rule = rate_on(s)
        if cap is not None and r > cap:
            r, label = cap, f"{label} → 청구 상한 {cap}%"
        if segs and segs[-1].rate == r and segs[-1].basis == label:
            segs[-1].end = e
        else:
            segs.append(Segment(s, e, r, rule, label))
    trace.append(Trace("DI-03" if not c.settlement else "DI-02", f"{c.label} 20% 판단", lsa_why))
    return segs


def _fmt(d: date) -> str:
    return f"{d.year}. {d.month}. {d.day}."


def _order_text(c: Claim, segs: list[Segment]) -> str:
    parts = []
    for s in segs:
        if s.end is None:
            parts.append(f"{_fmt(s.start)}부터 다 갚는 날까지 연 {s.rate}%" if not parts
                         else f"그 다음 날부터 다 갚는 날까지 연 {s.rate}%")
        else:
            parts.append(f"{_fmt(s.start)}부터 {_fmt(s.end)}까지 연 {s.rate}%" if not parts
                         else f"그 다음 날부터 {_fmt(s.end)}까지 연 {s.rate}%")
    return f"{int(c.amount):,}원에 대하여 " + ", ".join(parts)


def _accrue(c: Claim, segs: list[Segment], until: date, pays: list[Payment], o: dict,
            rows: list[InterestRow], warnings: list) -> Decimal:
    """기준일까지 금액. 변제·원천세가 있으면 그 날짜로 구간을 더 나눈다."""
    principal = c.amount
    unpaid_interest = Decimal(0)
    events = sorted(pays, key=lambda p: p.date)
    cuts = []
    for s in segs:
        if s.start > until:
            break
        cuts.append((s.start, min(s.end or until, until), s))
    total = Decimal(0)
    for s_start, s_end, seg in cuts:
        cur = s_start
        for p in [p for p in events if s_start <= p.date <= s_end] + [None]:
            stop = s_end if p is None else p.date - timedelta(days=1)
            if stop >= cur and principal > 0:
                frac, desc = year_fraction(cur, stop, o["di_day_count"])
                raw = principal * seg.rate / 100 * frac
                amt = round_money(raw) if o["di_rounding"] == "floor_per_segment" else raw
                rows.append(InterestRow(c.label, c.category, principal, cur, stop, (stop - cur).days + 1,
                                        desc, seg.rate, seg.basis, seg.rule, amt))
                unpaid_interest += amt
                total += amt
            if p is not None:
                if p.kind == "withholding":
                    principal = max(principal - p.amount, Decimal(0))
                else:
                    to_interest = min(p.amount, unpaid_interest)
                    unpaid_interest -= to_interest
                    principal = max(principal - (p.amount - to_interest), Decimal(0))
                cur = p.date
    if o["di_rounding"] == "floor_total":
        total = round_money(total)
    return total


def _limitation(c: Claim, inp: InterestInput, o: dict) -> LimitationRow:
    start = c.due_date - timedelta(days=13) if c.settlement else c.due_date
    expiry = _add_years(start, 3)
    if o["di_limitation_weekend_shift"]:
        while expiry.weekday() >= 5:
            expiry += timedelta(days=1)
    suspect = None if inp.suit_filed_date is None else inp.suit_filed_date > expiry
    return LimitationRow(c.label, c.category, start, expiry, suspect)


def _run(claims: list[Claim], inp: InterestInput, o: dict, regime: str, trace, warnings, rows) -> tuple[Decimal, list[ClaimSchedule]]:
    total = Decimal(0)
    schedules = []
    for c in claims:
        if c.amount <= 0:
            continue
        segs = _schedule(c, inp, o, regime, trace, warnings)
        sch = ClaimSchedule(c, segs, order_text=_order_text(c, segs))
        if inp.calc_until and inp.calc_until > c.due_date:
            pays = [p for p in inp.payments if p.claim == c.label]
            sch.interest_total = _accrue(c, segs, inp.calc_until, pays, o, rows, warnings)
            total += sch.interest_total
        schedules.append(sch)
    return total, schedules


def calculate_interest(inp: InterestInput, opts: dict, claims: list[Claim] | None = None) -> InterestResult:
    o = {k: (opts or {}).get(k, s.default) for k, s in OPTIONS.items()}
    trace: list[Trace] = []
    warnings: list[str] = []
    all_claims = list(claims or []) + list(inp.items)
    if not all_claims:
        return InterestResult([], Decimal(0), [], trace, ["지연손해금을 계산할 원금 항목이 없습니다."])

    labels = {c.label for c in all_claims}
    for p in inp.payments:
        if p.claim not in labels:
            warnings.append(f"변제 {_fmt(p.date)} {int(p.amount):,}원은 claim 이름이 원금 항목과 맞지 않아 반영하지 않았습니다.")
        if p.kind == "withholding":
            warnings.append(f"{p.claim}: 원천세 {int(p.amount):,}원을 {_fmt(p.date)}에 원금에서 뺐습니다. "
                            "실제 납부한 경우에만 뺄 수 있고(대법원 2013다36347), 다툼으로 소송에 이른 경우 달리 볼 여지가 있습니다.")
    if inp.first_instance_close_date and inp.first_instance_close_date < date(2003, 6, 1):
        warnings.append("1심 변론종결일이 2003. 6. 1. 전입니다. 2003년 소송촉진법 이율 개정 부칙은 확인되지 않아 경과조치를 적용하지 않았습니다.")
    for c in all_claims:
        if "해고예고" in c.category or "해고예고" in c.label:
            warnings.append(f"{c.label}: 해고예고수당이 연 20% 대상인지는 판결이 갈립니다"
                            "(원금에 넣어 20% — 대전지법 2018가합107477 / 12% — 성남지원 2023가단208164). "
                            "settlement 값으로 계산 방식을 정했는지 확인하세요.")
    if inp.end_cause == "redismissal" and inp.last_working_day:
        warnings.append("재해고로 근로관계가 끝난 경우 구법 도래분 20% 적용은 확정 고법 판결이 갈립니다"
                        "(적용: 대전고법 2019나13573 / 부정: 서울고법 2021나2031970).")
    if o["di_exclusion_end"] == "final_fact_instance" and not inp.dismissal_validity_settled \
            and not (inp.first_instance_judgment_date or inp.appellate_judgment_date):
        warnings.append("선고(예정)일이 없어 20%·소송촉진법 배제기간을 두지 않았습니다. 사용자 주장에 상당한 근거가 있으면 "
                        "사실심 선고일까지 배제됩니다(대법원 2026다200272). 선고 예정일을 넣어 다시 계산하세요.")

    regime = o["di_regime"]
    rows: list[InterestRow] = []
    total, schedules = _run(all_claims, inp, o, regime, trace, warnings, rows)

    alternatives = {}
    cutoff = parse_date(o["di_new_law_cutoff"])
    if regime == "auto" and any(not c.settlement and c.due_date >= cutoff for c in all_claims):
        warnings.append("개정 근로기준법 제37조 제1항 제2호(2025. 10. 23. 시행)를 해고기간 등 다툼이 있는 임금에 적용하는 방식은 "
                        "1심 판결이 갈리고(서울북부 2026가합20004 / 서울중앙 2025가합10452 / 창원 2025구합1375) "
                        "고법·대법원 판단이 없습니다. '대안: 개정법 미적용' 결과를 함께 확인하세요.")
        alt_total, alt_sched = _run(all_claims, inp, o, "new_2ho_off", [], [], [])
        alternatives["개정법 미적용"] = (alt_total, alt_sched)
    if not inp.dismissal_validity_settled and o["di_exclusion_end"] != "none":
        max_o = dict(o, di_exclusion_end="none")
        cm_total, cm_sched = _run(all_claims, inp, max_o, regime, [], [], [])
        alternatives["청구 최대(배제 없음)"] = (cm_total, cm_sched)

    limitation = [_limitation(c, inp, o) for c in all_claims if c.amount > 0]
    for lr in limitation:
        if lr.suspect:
            warnings.append(f"{lr.claim}: 시효 만료일 {_fmt(lr.expiry)}이 소 제기일보다 앞섭니다. 최고·승인 등 중단 사유를 확인하세요.")
    if inp.suit_filed_date is None:
        warnings.append("소 제기일이 없어 시효 완성 여부는 표시하지 않고 만료일만 적었습니다.")

    trace.append(Trace("DI-06", "20% 미적용 구간 이율", "상사 6%" if inp.employer_merchant else "민사 5%"))
    trace.append(Trace("DI-11", "일할 분모", o["di_day_count"], "판결로 갈리지 않는 분모 규칙 — 옵션"))
    if inp.calc_until:
        trace.append(Trace("DI-12", "금액 계산 기준일", _fmt(inp.calc_until), o["di_rounding"]))

    order = "\n".join(s.order_text for s in schedules)
    return InterestResult(rows, total, [], trace, warnings, schedules, limitation, alternatives, order)
