#!/usr/bin/env python3
"""추출한 노임표·생명표가 제대로 들어왔는지 확인한다."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.tables import LifeTable, WageTable  # noqa: E402

lt = LifeTable.load()
years = lt.years
print(f"  생명표      {min(years)}~{max(years)}년")
print(f"  2024년 60세 남 기대여명  {lt.expectancy(2024, 60, 'M')}년")
print(f"  2024년 60세 여 기대여명  {lt.expectancy(2024, 60, 'F')}년")

wt = WageTable.load()
print(f"  분기별 노임단가  {len(wt.quarterly):,}행")
print(f"  직종 마스터      {len(wt.occupations):,}행")
