#!/usr/bin/env python3
"""노임표·생명표 추출이 제대로 되었는지 점검한다.

    python scripts/점검.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# 출력이 파이프이면 Windows 파이썬은 cp949 로 쓴다. Claude Code 는 UTF-8 로 읽으므로 맞춘다.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")

OK, WARN, BAD = "  [정상]", "  [확인필요]", "  [문제]"
problems = 0
warnings = 0


def ok(msg): print(f"{OK} {msg}")


def warn(msg):
    global warnings
    warnings += 1
    print(f"{WARN} {msg}")


def bad(msg):
    global problems
    problems += 1
    print(f"{BAD} {msg}")


print("\n=== 1. 파일 ===")
need = ["life_table.csv", "wage_quarterly.csv", "occupation.csv", "wage_occupation.csv"]
missing = [n for n in need if not (ROOT / "data" / n).exists()]
if missing:
    bad("없는 파일: " + ", ".join(missing))
    print("\n노임표추출.bat 을 다시 실행하십시오.")
    sys.exit(1)
for n in need:
    kb = (ROOT / "data" / n).stat().st_size / 1024
    ok(f"{n:<24} {kb:>8,.0f} KB")

from engine.tables import LifeTable, WageTable  # noqa: E402

print("\n=== 2. 생명표 ===")
lt = LifeTable.load()
years = lt.years
print(f"       연도 {min(years)}~{max(years)}, 행 {len(lt.rows):,}")
if len(lt.rows) < 2000:
    bad(f"행이 너무 적습니다({len(lt.rows):,}). 34년 x 101세 = 3,400행 안팎이어야 합니다")
else:
    ok("행 수 충분")
if max(years) < 2020:
    warn(f"최신 연도가 {max(years)}년입니다. 프로그램이 오래된 버전일 수 있습니다")
else:
    ok(f"최신 연도 {max(years)}년")
try:
    m = lt.expectancy(max(years), 60, "M")
    f = lt.expectancy(max(years), 60, "F")
    print(f"       {max(years)}년 60세 기대여명  남 {m}년 / 여 {f}년")
    if not (15 <= m <= 32 and 20 <= f <= 38):
        bad("기대여명이 상식 범위를 벗어납니다. 컬럼 매핑을 확인하십시오")
    elif f <= m:
        warn("여자 기대여명이 남자보다 짧습니다. 남/여 컬럼이 바뀌었을 수 있습니다")
    else:
        ok("기대여명 정상 범위")
except Exception as e:
    bad(f"기대여명 조회 실패: {e}")

print("\n=== 3. 노임단가 ===")
wt = WageTable.load()
print(f"       분기별 {len(wt.quarterly):,}행 / 직종 {len(wt.occupations):,}개 / 직종별단가 {len(wt.by_half):,}건")
if len(wt.occupations) < 50:
    warn(f"직종이 {len(wt.occupations)}개뿐입니다. 통상 수백 개입니다")
else:
    ok("직종 수 충분")

qyears = sorted({int(r["year"]) for r in wt.quarterly})
if qyears:
    print(f"       노임표 연도 {min(qyears)}~{max(qyears)}")
    try:
        city = wt.city_wage(max(qyears), 1)
        rural = wt.rural_wage(max(qyears), 1, "M")
        print(f"       {max(qyears)}년 1분기  도시일용 {city:,}원 / 농촌남 {rural:,}원")
        if not (80_000 <= city <= 400_000):
            bad("도시일용노임이 상식 범위를 벗어납니다")
        else:
            ok("노임단가 정상 범위")
    except Exception as e:
        bad(f"노임단가 조회 실패: {e}")
else:
    bad("분기별 노임표가 비어 있습니다")

hits = wt.find_occupation("보통인부")
if hits:
    ok(f"직종 검색 동작 ('보통인부' {len(hits)}건)")
else:
    warn("'보통인부' 직종을 찾지 못했습니다")

print("\n=== 결과 ===")
if problems:
    print(f"  문제 {problems}건. 위 [문제] 줄을 그대로 붙여 문의하십시오.")
    sys.exit(1)
if warnings:
    print(f"  확인필요 {warnings}건. 계산은 되지만 위 내용을 한 번 보십시오.")
    sys.exit(0)
print("  이상 없습니다. 노임표·생명표가 정상적으로 들어왔습니다.")
