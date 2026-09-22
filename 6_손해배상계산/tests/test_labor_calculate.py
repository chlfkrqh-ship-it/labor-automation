"""노동 금액 조립 확인 — cases/labor_sample.yaml 을 cli·감시 폴더와 같은 경로로 끝까지 돌린다.

개별 금액의 정답은 모듈별 테스트(판결 숫자)가 맡는다. 여기서는 모듈 사이 값 전달과 출력 형식을 본다.
"""

import shutil
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import openpyxl
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import cli
import watch
from engine.labor.calculate import calculate_labor, load_labor_case
from engine.labor.common import LaborError
from engine.labor.excel import write_labor_workbook

SAMPLE = ROOT / "cases" / "labor_sample.yaml"


@pytest.fixture(scope="module")
def result():
    return calculate_labor(load_labor_case(SAMPLE))


def test_있는_절이_모두_계산된다(result):
    assert list(result.parts) == ["ordinary", "overtime", "leave", "average_wage", "retirement", "interest"]


def test_원금은_모듈_합계와_같다(result):
    parts = result.parts
    expected = sum((parts[s].total for s in ("overtime", "leave", "retirement")), Decimal(0))
    assert result.principal_total == expected
    assert {c.category for c in result.claims} >= {"퇴직금 차액"}


def test_평균임금에_시간외수당_증가분이_넘어간다(result):
    extra = result.parts["overtime"].extra_wages
    assert extra and all(v >= 0 for v in extra.values())


def test_퇴직금은_평균임금_결과를_쓴다(result):
    avg = result.parts["average_wage"].average_daily_wage
    assert any(getattr(r, "average_daily_wage", None) == avg for r in result.parts["retirement"].rows)


def test_연차수당_1일분은_통상임금_모듈에서_온다(result):
    ordinary = result.parts["ordinary"]
    rows = [r for r in result.parts["leave"].rows if r.daily_wage]
    assert rows
    for r in rows:
        assert r.daily_wage == ordinary.daily_ordinary_of(r.wage_ref_date, allowance="annual_leave")


def test_지연손해금은_모든_원금을_받는다(result):
    it = result.parts["interest"]
    assert len(it.schedules) == len([c for c in result.claims if c.amount > 0])
    settle = [s for s in it.schedules if s.claim.settlement]
    # 퇴직금 차액: 마지막 근무일 2025. 6. 30. + 15일부터 20%, 선고일(2026. 10. 15.)까지는 배제되어 6%
    assert settle and settle[0].segments[0].start == date(2025, 7, 15)
    assert [s.rate for s in settle[0].segments] == [Decimal(6), Decimal(20)]
    assert "청구 최대(배제 없음)" in it.alternatives


def test_계산표_시트(result, tmp_path):
    out = write_labor_workbook(result, tmp_path / "노동.xlsx")
    wb = openpyxl.load_workbook(out)
    assert wb.sheetnames[:2] == ["요약", "통상임금"]
    for name in ("시간외수당", "연차휴가수당", "평균임금", "퇴직금", "지연손해금", "소멸시효", "경고", "근거"):
        assert name in wb.sheetnames
    texts = [c.value for row in wb["요약"].iter_rows() for c in row if isinstance(c.value, str)]
    assert any("다 갚는 날까지 연 20%" in t for t in texts)


def test_cli_와_감시폴더(tmp_path, capsys):
    case = tmp_path / "사건.yaml"
    shutil.copy(SAMPLE, case)
    assert cli.is_labor_yaml(case)
    out = cli.run_labor(case)
    assert out.exists() and "노동금액계산표" in out.name
    root = watch.ensure_root(tmp_path / "감시")
    shutil.copy(SAMPLE, root / "01_입력" / "노동.yaml")
    assert watch.scan_once(root) == 1
    assert list((root / "02_결과").glob("*노동금액계산표*.xlsx"))


def test_해고기간_임금_샘플():
    res = calculate_labor(load_labor_case(ROOT / "cases" / "labor_dismissal_sample.yaml"))
    part = res.parts["dismissal"]
    # 월 4,000,000원(기본급 3,000,000 + 상여 400% ÷ 12) × 12개월
    # − 6개월 × min(중간수입 2,000,000, 4,000,000 − floor(4,000,000 × 0.7))
    assert part.total == Decimal(4_000_000) * 12 - 6 * min(Decimal(2_000_000), Decimal(4_000_000) - Decimal(2_800_000))
    it = res.parts["interest"]
    # 복직(구법 도래분): 20% 없음 — 지급일 다음 날부터 6%, 선고 다음 날부터 소송촉진법 12%
    assert {tuple(s.rate for s in sch.segments) for sch in it.schedules} == {(Decimal(6), Decimal(12))}


def test_앞_절이_없으면_무엇이_필요한지_알린다():
    import yaml

    raw = yaml.safe_load(SAMPLE.read_text(encoding="utf-8"))
    del raw["average_wage"]
    with pytest.raises(LaborError, match="average_wage"):
        calculate_labor(load_labor_case(raw))
    raw = yaml.safe_load(SAMPLE.read_text(encoding="utf-8"))
    raw["options"]["없는옵션"] = 1
    with pytest.raises(LaborError, match="알 수 없는 옵션"):
        load_labor_case(raw)
