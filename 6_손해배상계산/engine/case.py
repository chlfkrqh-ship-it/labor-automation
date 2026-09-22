"""사건 입력 모델과 YAML 로더.

사건 자료는 저장소에 커밋하지 않는다(.gitignore 의 cases/). 이 모듈은 형식만 정의한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path


def _d(v) -> date:
    if isinstance(v, date):
        return v
    s = str(v).strip().replace(".", "-").replace("/", "-").rstrip("-")
    if s.isdigit() and len(s) == 8:
        return date(int(s[:4]), int(s[4:6]), int(s[6:]))
    y, m, dd = s.split("-")
    return date(int(y), int(m), int(dd))


@dataclass
class ImpairmentInput:
    dept: str
    rate: Decimal
    prior: Decimal = Decimal(0)
    years: Decimal | None = None      # 한시장해면 년수


@dataclass
class TreatmentInput:
    name: str
    cost: Decimal
    first: date
    last: date
    duration_month: int
    prior: Decimal = Decimal(0)
    repeating: bool = False


@dataclass
class OrthosisInput(TreatmentInput):
    pass


@dataclass
class Case:
    # 기초사항
    case_no: str = ""
    name: str = ""
    sex: str = "M"                      # M / F
    case_type: str = "손해배상(자)"      # 손해배상(자) / 손해배상(산)
    injury_type: str = "부상"            # 부상 / 사망
    judgment_type: str = "판결"          # 판결 / 조정
    birth: date = date(1990, 1, 1)
    accident: date = date(2024, 1, 1)
    cure_end: date | None = None         # 입원치료 종료일
    work_limit_years: int = 65           # 가동연한
    work_end: date | None = None         # 비우면 생년월일 + 가동연한 - 1일
    argument_end: date | None = None     # 변론 종결일
    legal_rate: Decimal = Decimal("5")   # 법정이율 %
    life_expectancy: Decimal | None = None
    life_end: date | None = None

    # 노동능력상실률
    impairments: list[ImpairmentInput] = field(default_factory=list)

    # 일실수입
    occupation: str = "보통인부"
    rural: bool = False
    # 노임단가를 직접 지정할 때 쓴다. {"2024-1": 165545, ...}
    # 비우면 data/ 의 정규화된 노임표(engine.tables)를 쓴다.
    wages: dict = field(default_factory=dict)

    # 기타손해
    treatments: list[TreatmentInput] = field(default_factory=list)
    orthoses: list[OrthosisInput] = field(default_factory=list)
    past_treatment: Decimal = Decimal(0)
    past_caregiving_days: Decimal = Decimal(0)
    past_caregiving_price: Decimal = Decimal(0)   # 기왕 개호비 단가 (사고일 기준)
    past_caregiving_actual: Decimal | None = None
    caregiving_start: date | None = None
    caregiving_end: date | None = None
    caregiving_headcount: Decimal = Decimal(1)
    caregiving_month_mode: bool = True   # 화면의 chkMonth. 월 단위 / 분기·반기 단위
    severance: Decimal = Decimal(0)
    funeral_cost: Decimal = Decimal(0)   # 사망이면 기본 500만

    # 과실상계·공제
    fault_rate: Decimal = Decimal(0)
    pre_offset_deduction: Decimal = Decimal(0)
    paid_cure: Decimal = Decimal(0)
    advance: Decimal = Decimal(0)
    ratio_deduction: Decimal = Decimal(0)
    full_deduction: Decimal = Decimal(0)

    # 위자료
    solatium: Decimal = Decimal(0)

    def resolved_work_end(self) -> date:
        """가동종료일. 생년월일 + 가동연한 - 1일.

        골든 케이스 3: 1990.01.01. 생 + 65년 -> 2054.12.31.
        """
        if self.work_end:
            return self.work_end
        anniversary = date(
            self.birth.year + self.work_limit_years, self.birth.month, self.birth.day
        )
        return date.fromordinal(anniversary.toordinal() - 1)


def load(path: str | Path) -> Case:
    """YAML 사건 파일을 읽는다."""
    import yaml

    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    kw = dict(raw)
    for k in ("birth", "accident", "cure_end", "work_end", "argument_end", "life_end",
              "caregiving_start", "caregiving_end"):
        if kw.get(k):
            kw[k] = _d(kw[k])
    if "caregiving_month_mode" in kw:
        kw["caregiving_month_mode"] = bool(kw["caregiving_month_mode"])
    for k in ("legal_rate", "fault_rate", "pre_offset_deduction", "paid_cure", "advance",
              "ratio_deduction", "full_deduction", "solatium", "past_treatment",
              "past_caregiving_days", "past_caregiving_price", "past_caregiving_actual",
              "caregiving_headcount",
              "severance", "funeral_cost", "life_expectancy"):
        if kw.get(k) is not None:
            kw[k] = Decimal(str(kw[k]))
    kw["wages"] = {str(k): int(v) for k, v in (raw.get("wages") or {}).items()}
    kw["impairments"] = [
        ImpairmentInput(
            dept=i["dept"],
            rate=Decimal(str(i["rate"])),
            prior=Decimal(str(i.get("prior", 0))),
            years=Decimal(str(i["years"])) if i.get("years") else None,
        )
        for i in raw.get("impairments", [])
    ]
    for key, cls in (("treatments", TreatmentInput), ("orthoses", OrthosisInput)):
        kw[key] = [
            cls(
                name=t["name"],
                cost=Decimal(str(t["cost"])),
                first=_d(t["first"]),
                last=_d(t.get("last", t["first"])),
                duration_month=int(t.get("duration_month", 1)),
                prior=Decimal(str(t.get("prior", 0))),
                repeating=bool(t.get("repeating", False)),
            )
            for t in raw.get(key, [])
        ]
    return Case(**kw)
