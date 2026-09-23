"""노임표·생명표 조회.

원본: C:\\work\\sut\\DB\\CortCalc.accdb (프로그램 버전 1.0.260318.100)
  TB_SUT001  분기별 노임단가   (농촌 남/여는 분기 단위, 도시일용은 반기 단위로 변동)
  TB_SUT002  생명표            (1991~2024, 연령 0~100)
  TB_SUT003  직종 마스터
  TB_SUT004  직종별 반기 노임단가

scripts/normalize.py 가 만든 data/*.csv 를 읽는다.

직종 찾기. 원본은 직종 '이름'으로 단가를 찾는다(GetWageFromSalaryJobTable(jobNm, year, half) —
constants.py). occupation.csv 는 id 순이라 구 분류('공사'·'원자력'·'기타') 직종이 앞에 오므로
부분일치의 첫 항목을 쓰면 '배관공'이 '원자력배관공'으로, '특별인부'가 '원자력특별인부'로 풀린다.
그래서 이름이 입력과 같은 직종만 고르고, 부분일치로는 고르지 않는다.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _read(name: str) -> list[dict[str, str]]:
    path = DATA_DIR / name
    if not path.exists():
        raise FileNotFoundError(
            f"{path} 가 없습니다. scripts/normalize.py 를 먼저 실행하세요."
        )
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


@dataclass
class LifeTable:
    """기대여명 조회. 키: (기준연도, 연령) -> (남, 여)"""

    rows: dict[tuple[int, int], tuple[float, float]]

    @classmethod
    def load(cls) -> "LifeTable":
        rows = {}
        for r in _read("life_table.csv"):
            key = (int(r["year"]), int(r["age"]))
            rows[key] = (float(r["male"]), float(r["female"]))
        return cls(rows)

    @property
    def years(self) -> list[int]:
        return sorted({y for y, _ in self.rows})

    def expectancy(self, year: int, age: int, sex: str) -> float:
        """기준연도의 해당 연령 기대여명(년).

        요청 연도가 표에 없으면 그 이하의 가장 최근 연도를 쓴다.
        프로그램은 '해당 년도의 생명표가 존재하지 않습니다'로 거절하므로,
        이 fallback 이 프로그램과 같은 동작인지는 확인이 필요하다.
        """
        available = [y for y in self.years if y <= year]
        if not available:
            raise KeyError(f"{year}년 이전 생명표가 없습니다")
        row = self.rows.get((max(available), age))
        if row is None:
            raise KeyError(f"연령 {age} 자료가 없습니다")
        return row[0] if sex == "M" else row[1]


class OccupationNotFound(LookupError):
    """직종명을 노임표의 직종 하나로 정하지 못했다(같은 이름이 없거나 후보가 여럿)."""


class WageNotFound(KeyError):
    """노임표에 그 구간 단가가 없다. 조회기의 has_wage 가 KeyError 로 판정하므로 KeyError 를 잇는다."""

    def __str__(self) -> str:
        return str(self.args[0]) if self.args else ""


def _tokens(merged_name: str) -> list[str]:
    """통합 전 직종명(쉼표 구분)."""
    return [t.strip() for t in (merged_name or "").split(",") if t.strip()]


@dataclass
class WageTable:
    """노임단가 조회."""

    quarterly: list[dict[str, str]]   # TB_SUT001
    occupations: list[dict[str, str]] # TB_SUT003
    by_half: dict[tuple[str, int, int], int]  # (직종SRNO, 연도, 반기) -> 단가
    _keys: dict[str, list[tuple[int, int]]] = field(default_factory=dict, init=False, repr=False)

    @classmethod
    def load(cls) -> "WageTable":
        by_half = {}
        for r in _read("wage_occupation.csv"):
            by_half[(r["occupation_id"], int(r["year"]), int(r["half"]))] = int(r["wage"])
        return cls(
            quarterly=_read("wage_quarterly.csv"),
            occupations=_read("occupation.csv"),
            by_half=by_half,
        )

    def wage_keys(self, occupation_id: str) -> list[tuple[int, int]]:
        """그 직종에 단가가 있는 (연도, 반기) 목록. 오름차순."""
        if not self._keys:
            for oid, y, h in self.by_half:
                self._keys.setdefault(oid, []).append((y, h))
            for keys in self._keys.values():
                keys.sort()
        return self._keys.get(occupation_id, [])

    def occupation_label(self, occupation: dict[str, str]) -> str:
        """계산표·오류 문구용. 예: '배관공(직종코드 7204, 단가 2010-1~2026-1)'."""
        keys = self.wage_keys(occupation["id"])
        span = f"{keys[0][0]}-{keys[0][1]}~{keys[-1][0]}-{keys[-1][1]}" if keys else "없음"
        return f"{occupation['name']}(직종코드 {occupation['id']}, 단가 {span})"

    def search_occupation(self, name: str) -> list[dict[str, str]]:
        """직종명 부분일치 후보. 이름이 같은 것, 통합 전 직종명이 같은 것, 나머지 순서다.

        후보를 보여 줄 때만 쓴다. 계산할 직종은 find_occupation·resolve_occupation 으로 정한다.
        """
        name = (name or "").strip()
        if not name:
            return []
        hits = [o for o in self.occupations if name in o["name"] or name in o["merged_name"]]
        return sorted(hits, key=lambda o: (o["name"] != name, name not in _tokens(o["merged_name"])))

    def find_occupation(self, name: str) -> list[dict[str, str]]:
        """직종명으로 직종을 찾는다. 부분일치로는 고르지 않는다.

        1) 이름이 입력과 같은 직종. 같은 이름이 여럿이면(제철축로공·전기공사기사) 최근 단가가 있는
           계열을 앞에 둔다. 단가는 occupation_wage 가 이름이 같은 계열끼리 이어서 찾는다.
        2) 없으면 통합 전 직종명(merged_name 의 쉼표 구분 항목)이 입력과 같은 직종. 둘 이상에 걸치면
           정하지 않고 OccupationNotFound 로 멈춘다.
        둘 다 없으면 빈 목록이다. 후보는 search_occupation 으로 본다.
        """
        name = (name or "").strip()
        if not name:
            return []
        exact = [o for o in self.occupations if o["name"] == name]
        if exact:
            return sorted(exact, key=lambda o: self.wage_keys(o["id"])[-1:], reverse=True)
        merged = [o for o in self.occupations if name in _tokens(o["merged_name"])]
        if len(merged) > 1:
            raise OccupationNotFound(
                f"직종 '{name}' 은 통합 전 직종명으로 여러 직종에 걸쳐 있어 하나로 정할 수 없습니다. "
                f"후보: {', '.join(self.occupation_label(o) for o in merged)}. 직종명을 하나로 적으십시오."
            )
        return merged

    def resolve_occupation(self, name: str) -> list[dict[str, str]]:
        """find_occupation 과 같되, 못 찾으면 부분일치 후보를 적어 OccupationNotFound 로 멈춘다."""
        found = self.find_occupation(name)
        if found:
            return found
        near = self.search_occupation(name)[:10]
        listed = ", ".join(self.occupation_label(o) for o in near) if near else "없음"
        raise OccupationNotFound(
            f"직종 '{(name or '').strip()}' 과 이름이 같은 직종이 노임표에 없습니다. 부분일치로는 고르지 "
            f"않습니다. 후보: {listed}. 직종명을 노임표 이름 그대로 적거나 노임단가를 직접 입력하십시오."
        )

    def occupation_wage(self, occupation_id: str, year: int, half: int) -> int:
        """직종별 일 노임단가(원).

        원본은 직종 이름으로 찾으므로(GetWageFromSalaryJobTable(jobNm, year, half)), 그 id 에 해당
        반기 단가가 없으면 이름이 같은 다른 계열의 단가를 쓴다. 어디에도 없으면 WageNotFound.
        """
        key = (occupation_id, year, half)
        if key in self.by_half:
            return self.by_half[key]
        own = next((o for o in self.occupations if o["id"] == occupation_id), None)
        if own is not None:
            for o in self.occupations:
                if o["name"] == own["name"] and (o["id"], year, half) in self.by_half:
                    return self.by_half[(o["id"], year, half)]
        label = self.occupation_label(own) if own else f"직종코드 {occupation_id}"
        merged_into = [
            self.occupation_label(o) for o in self.occupations
            if own is not None and o["id"] != own["id"] and own["name"] in _tokens(o["merged_name"])
        ]
        hint = f" 이 직종이 통합된 직종: {', '.join(merged_into)}." if merged_into else ""
        raise WageNotFound(
            f"{label}의 {year}년 {half}반기 노임단가가 노임표에 없습니다.{hint} 단가가 있는 직종명을 "
            "쓰거나 노임단가를 직접 입력하십시오."
        )

    def rural_wage(self, year: int, quarter: int, sex: str) -> int:
        """농촌 일용노임(원). 분기 단위로 변동한다."""
        for r in self.quarterly:
            if int(r["year"]) == year and int(r["quarter"]) == quarter:
                return int(r["rural_male"] if sex == "M" else r["rural_female"])
        raise KeyError(f"{year}년 {quarter}분기 노임표가 없습니다")

    def city_wage(self, year: int, quarter: int) -> int:
        """도시일용노임(원).

        TB_SUT001 의 도시일용 값은 TB_SUT004 '보통인부' 반기 단가와 완전히 일치하며,
        같은 반기에 속한 두 분기가 동일한 값을 갖는다 (2025: Q1=Q2=169804, Q3=Q4=171037).
        즉 도시일용은 반기 단위로 변동한다.

        미확인: 반기 전환의 실제 적용 기준일(7.1. 인지 관행상 9.1. 인지).
                일실수입 기간분할 경계가 여기에 달려 있으므로 디컴파일로 확정할 것.
        """
        for r in self.quarterly:
            if int(r["year"]) == year and int(r["quarter"]) == quarter:
                return int(r["city_daily"])
        raise KeyError(f"{year}년 {quarter}분기 노임표가 없습니다")
