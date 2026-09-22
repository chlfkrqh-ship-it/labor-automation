"""노임표·생명표 조회.

원본: C:\\work\\sut\\DB\\CortCalc.accdb (프로그램 버전 1.0.260318.100)
  TB_SUT001  분기별 노임단가   (농촌 남/여는 분기 단위, 도시일용은 반기 단위로 변동)
  TB_SUT002  생명표            (1991~2024, 연령 0~100)
  TB_SUT003  직종 마스터
  TB_SUT004  직종별 반기 노임단가

scripts/normalize.py 가 만든 data/*.csv 를 읽는다.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
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


@dataclass
class WageTable:
    """노임단가 조회."""

    quarterly: list[dict[str, str]]   # TB_SUT001
    occupations: list[dict[str, str]] # TB_SUT003
    by_half: dict[tuple[str, int, int], int]  # (직종SRNO, 연도, 반기) -> 단가

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

    def find_occupation(self, name: str) -> list[dict[str, str]]:
        """직종명 부분일치 검색."""
        return [o for o in self.occupations if name in o["name"] or name in o["merged_name"]]

    def occupation_wage(self, occupation_id: str, year: int, half: int) -> int:
        """직종별 일 노임단가(원)."""
        return self.by_half[(occupation_id, year, half)]

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
