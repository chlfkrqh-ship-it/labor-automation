"""입력서 -> 자동 처리 -> 계산표 전 과정 확인 (골든 케이스 3 재현)."""

import shutil
import sys
from pathlib import Path

import openpyxl
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import watch
from engine.inputform import make_template, read_form
from tests.golden import case_fault_deduction as F

FORM_VALUES = {
    "사건번호": "2024가단1", "성명": "홍길동", "성별": "남",
    "사건종류": "손해배상(자)", "사건유형": "부상", "판결/조정": "판결",
    "생년월일": "19900101", "사고일자": "20240101", "입원치료 종료일": "20240630",
    "가동연한(년)": 65, "변론 종결일": "20260308", "법정이율(%)": 5,
    "기대여명(년)": 47.6, "여명 종료일": "20710727", "직종": "보통인부",
    "원고측 과실비율(%)": 30, "지급 치료비": 1000000,
    "손해배상 선급금": 2000000, "적용 위자료": 20000000,
}
IMPAIRMENTS = [("정형외과", 40, 20), ("안과", 20, None)]
WAGES = [("2024-1", 165545), ("2024-2", 167081), ("2025-1", 169804),
         ("2025-2", 171037), ("2026-1", 172068)]


def _fill(path: Path) -> Path:
    wb = openpyxl.load_workbook(path)
    ws = wb.active
    idx = {ws.cell(r, 2).value: r for r in range(1, ws.max_row + 1)
           if isinstance(ws.cell(r, 2).value, str)}
    for k, v in FORM_VALUES.items():
        ws.cell(idx[k], 4, v)
    r = idx["[노동능력 상실률]"] + 2
    for i, (dept, rate, prior) in enumerate(IMPAIRMENTS):
        ws.cell(r + i, 2, dept)
        ws.cell(r + i, 3, rate)
        if prior:
            ws.cell(r + i, 4, prior)
    r = idx["[노임단가 직접입력]"] + 2
    for i, (k, v) in enumerate(WAGES):
        ws.cell(r + i, 2, k)
        ws.cell(r + i, 3, v)
    wb.save(path)
    return path


@pytest.fixture(scope="module")
def workspace(tmp_path_factory):
    root = watch.ensure_root(tmp_path_factory.mktemp("노동사건자동화"))
    filled = shutil.copy(root / "00_양식" / "입력서.xlsx", root / "01_입력" / "사건.xlsx")
    _fill(Path(filled))
    processed = watch.scan_once(root)
    return root, processed


def test_빈_양식이_만들어진다(tmp_path):
    form = make_template(tmp_path / "입력서.xlsx")
    assert form.exists()
    case = read_form(form)          # 빈 양식도 읽혀야 한다
    assert case.injury_type == "부상"
    assert case.work_limit_years == 65


def test_입력서를_읽으면_사건이_된다(tmp_path):
    form = _fill(make_template(tmp_path / "입력서.xlsx"))
    case = read_form(form)
    assert case.case_no == "2024가단1"
    assert case.birth == F.BIRTH and case.accident == F.ACCIDENT
    assert case.cure_end == F.CURE_END
    assert case.resolved_work_end() == F.WORK_END
    assert [i.dept for i in case.impairments] == ["정형외과", "안과"]
    assert case.impairments[0].prior == 20
    assert case.fault_rate == F.FAULT_RATE
    assert len(case.wages) == 5


def test_입력폴더에_넣으면_결과가_나온다(workspace):
    root, processed = workspace
    assert processed == 1
    assert not list((root / "01_입력").glob("*.xlsx"))     # 입력은 비워지고
    assert list((root / "03_보관").glob("*.xlsx"))          # 보관으로 이동
    assert not list((root / "99_오류").iterdir())           # 오류 없음
    results = list((root / "02_결과").glob("*.xlsx"))
    assert len(results) == 1
    assert "2024가단1(홍길동)" in results[0].name


def test_결과가_골든과_일치한다(workspace):
    root, _ = workspace
    ws = openpyxl.load_workbook(next((root / "02_결과").glob("*.xlsx")))["종합"]
    totals = {}
    for row in range(1, ws.max_row + 1):
        for label_col, value_col in ((2, 14), (17, 20)):
            label = ws.cell(row, label_col).value
            if isinstance(label, str) and label.endswith(" : "):
                totals[label.strip(" :")] = ws.cell(row, value_col).value
    assert totals["일실수입 전체합계"] == int(F.INCOME_TOTAL)
    assert totals["재산상손해 합계"] == int(F.PROPERTY_FINAL)
    assert totals["합계"] == int(F.GRAND_TOTAL)


def test_잘못된_입력은_오류폴더로(tmp_path_factory):
    root = watch.ensure_root(tmp_path_factory.mktemp("bad"))
    shutil.copy(root / "00_양식" / "입력서.xlsx", root / "01_입력" / "빈양식.xlsx")
    (root / "01_입력" / "빈양식.xlsx").touch()
    watch.scan_once(root)
    assert list((root / "99_오류").glob("*.txt")), "오류 사유 파일이 남아야 한다"
    assert not list((root / "02_결과").iterdir())
