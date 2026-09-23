"""사건 입력 모델과 YAML 로더.

사건 자료는 저장소에 커밋하지 않는다(.gitignore 의 cases/). 이 모듈은 형식만 정의한다.
"""

from __future__ import annotations

import calendar
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
    # 향후 개호비 단가 표. {"2024-1": 165545, ...} 피해자 노임(wages·직종)과 따로 적는다.
    # 원본은 개호비 화면에서 직종을 따로 고르므로 피해자 노임으로 대신하지 않는다(calculate.py).
    caregiving_wages: dict = field(default_factory=dict)
    caregiving_rural: bool = False       # 개호 단가가 농촌 노임(분기 단위)이면 True. 표 키 번호가 분기가 된다
    severance: Decimal = Decimal(0)
    # 사망 사건 장례비. 비우면 0 이다(기본값을 채우지 않는다). 재산적 손해·합계에는 넣지 않는다(calculate.py).
    funeral_cost: Decimal = Decimal(0)

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

        2월 29일생은 가동연한이 끝나는 해가 평년이면 대응일(2. 29.)이 없다. 민법 제160조 제3항
        (그 월 말일로 만료 -> 2. 28.)과 2. 28. 을 대응일로 보고 전날 만료(-> 2. 27.) 가운데 대법원
        프로그램이 어느 쪽인지 확인되지 않았으므로 정하지 않고 멈춘다. work_end 를 적으면 그 값을 쓴다.
        """
        if self.work_end:
            return self.work_end
        year = self.birth.year + self.work_limit_years
        if (self.birth.month, self.birth.day) == (2, 29) and not calendar.isleap(year):
            raise ValueError(
                f"생년월일이 2월 29일이라 가동연한 {self.work_limit_years}년이 끝나는 {year}년에 "
                f"대응일(2월 29일)이 없습니다. 가동종료일을 {year}. 2. 28.(민법 제160조 제3항 — 그 월 "
                f"말일로 만료)로 볼지 {year}. 2. 27.(2. 28.을 대응일로 보고 전날 만료)로 볼지 엔진이 정하지 "
                "않습니다. 사건 파일에 work_end(가동 종료일)를 적으십시오."
            )
        anniversary = date(year, self.birth.month, self.birth.day)
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
    for k in ("caregiving_month_mode", "caregiving_rural"):
        if k in kw:
            kw[k] = bool(kw[k])
    for k in ("legal_rate", "fault_rate", "pre_offset_deduction", "paid_cure", "advance",
              "ratio_deduction", "full_deduction", "solatium", "past_treatment",
              "past_caregiving_days", "past_caregiving_price", "past_caregiving_actual",
              "caregiving_headcount",
              "severance", "funeral_cost", "life_expectancy"):
        if kw.get(k) is not None:
            kw[k] = Decimal(str(kw[k]))
    kw["wages"] = {str(k): int(v) for k, v in (raw.get("wages") or {}).items()}
    kw["caregiving_wages"] = {
        str(k): int(v) for k, v in (raw.get("caregiving_wages") or {}).items()
    }
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
        items = []
        for t in raw.get(key, []):
            first = _d(t["first"])
            last = _d(t.get("last", t["first"]))
            items.append(
                cls(
                    name=t["name"],
                    cost=Decimal(str(t["cost"])),
                    first=first,
                    last=last,
                    duration_month=int(t.get("duration_month", 1)),
                    prior=Decimal(str(t.get("prior", 0))),
                    # 표시용 구분(반복/1회). 적지 않으면 입력서처럼 최종 필요일이 최초 필요일과 다른지로 정한다.
                    repeating=bool(t["repeating"]) if "repeating" in t else last != first,
                )
            )
        kw[key] = items
    return Case(**kw)
