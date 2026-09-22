"""지연손해금 모듈 검증 — 판결 원문 숫자(조사 문서 delay_interest.md 골든 예시)와 규칙 경계.

금액 기대값은 판결문에 적힌 인용액이다. 산식 확인용 기대값은 옆 주석에 식을 적는다.
"""

import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.labor.common import Claim, LaborError
from engine.labor.interest import (
    OPTIONS, calculate_interest, load_interest, sokchok_rate, year_fraction,
)
from engine.fraction import remove_fraction

DEFAULTS = {k: s.default for k, s in OPTIONS.items()}


def opts(**kw):
    return dict(DEFAULTS, **kw)


def interest_amount(principal, rate, start, end, mode="anniv_feb29"):
    frac, _ = year_fraction(start, end, mode)
    return remove_fraction(Decimal(principal) * Decimal(rate) / 100 * frac, 0)


# ---------------------------------------------------------------- DI-11 일할 (판결 숫자)
def test_창원_29일_윤년_분모():
    # 50,000,000 × 6% × 29/366 = 237,704 (2024. 2. 28.~3. 27.)
    assert interest_amount(50_000_000, 6, date(2024, 2, 28), date(2024, 3, 27)) == 237_704


def test_서울남부_1년_넘는_기간():
    assert interest_amount(26_941_165, 5, date(2022, 11, 9), date(2024, 3, 28)) == 1_866_006
    assert interest_amount(192_058_835, 5, date(2022, 11, 9), date(2025, 2, 23)) == 22_020_992


def test_해남_2년_151일_366():
    # 22,000,000 × 10% × (2 + 151/366) = 5,307,650
    assert interest_amount(22_000_000, 10, date(2013, 12, 15), date(2016, 5, 13)) == 5_307_650


def test_분모_규칙이_갈리는_기간():
    f1, d1 = year_fraction(date(2024, 3, 1), date(2024, 12, 31), "anniv_feb29")
    f2, d2 = year_fraction(date(2024, 3, 1), date(2024, 12, 31), "anniv_endyear_leap")
    assert d1 == "306/365" and d2 == "306/366"
    assert year_fraction(date(2023, 12, 1), date(2024, 1, 31), "calendar_split")[1] == "31/365 + 31/366"
    assert year_fraction(date(2024, 1, 1), date(2024, 12, 31), "anniv_feb29")[0] == 1


# ---------------------------------------------------------------- DI-01 이율표
def test_소송촉진법_이율표와_경과조치():
    assert sokchok_rate(date(2015, 9, 30)) == 20
    assert sokchok_rate(date(2015, 10, 1)) == 15
    assert sokchok_rate(date(2019, 6, 1)) == 12
    # 2019. 6. 1. 시행 당시 1심 변론종결 → 종전 15%
    assert sokchok_rate(date(2020, 1, 1), close=date(2019, 5, 20)) == 15
    assert sokchok_rate(date(2020, 1, 1), close=date(2019, 6, 3)) == 12


# ---------------------------------------------------------------- DI-02 퇴직 청산 금품
def _inp(**kw):
    base = dict(employer_merchant=True)
    base.update(kw)
    return load_interest(base)


def test_퇴직금_마지막근무일_15일부터_20():
    # 마지막 근무일 2018. 2. 28. → 지급기한 3. 14., 20%는 3. 15.부터 (판결 주문)
    c = Claim("퇴직금 차액", "퇴직금 차액", Decimal(1_000_000), date(2018, 3, 14), settlement=True)
    r = calculate_interest(_inp(), opts(di_exclusion_end="none"), [c])
    segs = r.schedules[0].segments
    assert segs[0].start == date(2018, 3, 15) and segs[0].rate == 20 and segs[0].end is None


def test_퇴직금_다툼_적절하면_선고일까지_6():
    c = Claim("퇴직금 차액", "퇴직금 차액", Decimal(1_000_000), date(2018, 3, 14), settlement=True)
    inp = _inp(service_date="2019-01-10", first_instance_judgment_date="2020-02-05")
    r = calculate_interest(inp, opts(), [c])
    segs = r.schedules[0].segments
    assert [(s.start, s.end, s.rate) for s in segs] == [
        (date(2018, 3, 15), date(2020, 2, 5), Decimal(6)),
        (date(2020, 2, 6), None, Decimal(20)),
    ]
    assert "그 다음 날부터 다 갚는 날까지 연 20%" in r.order_text
    # 대안: 배제 없음이면 처음부터 20%
    alt = r.alternatives["청구 최대(배제 없음)"][1][0].segments
    assert alt[0].rate == 20


def test_2005년_7월_전_퇴직은_20_없음():
    c = Claim("퇴직금", "퇴직금", Decimal(1_000_000), date(2005, 6, 14), settlement=True)
    r = calculate_interest(_inp(employer_merchant=False), opts(di_exclusion_end="none"), [c])
    assert {s.rate for s in r.schedules[0].segments} == {Decimal(5)}


# ---------------------------------------------------------------- DI-03 재직 중·해고기간 임금
def test_구법_복직자_해고기간_임금은_6_후_소촉법():
    c = Claim("해고기간 임금", "2024. 3.분", Decimal(3_000_000), date(2024, 3, 25))
    inp = _inp(service_date="2024-09-02", first_instance_judgment_date="2025-06-12")
    r = calculate_interest(inp, opts(), [c])
    assert [(s.start, s.rate) for s in r.schedules[0].segments] == [
        (date(2024, 3, 26), Decimal(6)), (date(2025, 6, 13), Decimal(12))]


def test_구법_해고기간_중_정년퇴직이면_종료일_15일부터_20():
    c = Claim("해고기간 임금", "2024. 3.분", Decimal(3_000_000), date(2024, 3, 25))
    inp = load_interest({"employer_merchant": True, "service_date": "2024-09-02",
                         "first_instance_judgment_date": "2025-06-12", "end_cause": "retirement"},
                        {"last_working_day": "2024-12-31"})
    segs = calculate_interest(inp, opts(), [c]).schedules[0].segments
    assert [(s.start, s.rate) for s in segs] == [(date(2024, 3, 26), Decimal(6)), (date(2025, 6, 13), Decimal(20))]
    # 배제 없음이면 2025. 1. 15.부터 20%
    segs = calculate_interest(inp, opts(di_exclusion_end="none"), [c]).schedules[0].segments
    assert (segs[-1].start, segs[-1].rate) == (date(2025, 1, 15), Decimal(20))


def test_재해고_종료_옵션():
    c = Claim("해고기간 임금", "2024. 3.분", Decimal(3_000_000), date(2024, 3, 25))
    inp = load_interest({"employer_merchant": True, "end_cause": "redismissal"}, {"last_working_day": "2024-12-31"})
    r = calculate_interest(inp, opts(di_exclusion_end="none"), [c])
    assert r.schedules[0].segments[-1].rate == 20
    assert any("2021나2031970" in w for w in r.warnings)
    r = calculate_interest(inp, opts(di_exclusion_end="none", di_redismissal_20=False), [c])
    assert {s.rate for s in r.schedules[0].segments} == {Decimal(6)}


def test_개정법_도래분_기본_20과_대안():
    c = Claim("해고기간 임금", "2025. 11.분", Decimal(3_000_000), date(2025, 11, 25))
    inp = _inp(service_date="2025-12-10", first_instance_judgment_date="2026-07-23")
    r = calculate_interest(inp, opts(), [c])
    assert [(s.start, s.rate) for s in r.schedules[0].segments] == [
        (date(2025, 11, 26), Decimal(6)), (date(2026, 7, 24), Decimal(20))]
    alt = r.alternatives["개정법 미적용"][1][0].segments
    assert [(s.start, s.rate) for s in alt] == [(date(2025, 11, 26), Decimal(6)), (date(2026, 7, 24), Decimal(12))]
    assert any("2026가합20004" in w for w in r.warnings)
    # 경계: 2025. 10. 2. 지급일분은 개정법 미적용(서울중앙 2025가합10452 각주)
    old = Claim("해고기간 임금", "2025. 9.분", Decimal(3_000_000), date(2025, 10, 2))
    segs = calculate_interest(_inp(), opts(di_exclusion_end="none"), [old]).schedules[0].segments
    assert {s.rate for s in segs} == {Decimal(6)}


def test_청구_이율_상한():
    c = Claim("퇴직금", "퇴직금", Decimal(1_000_000), date(2020, 1, 14), settlement=True)
    r = calculate_interest(_inp(), opts(di_exclusion_end="none", di_claimed_rate_cap="12"), [c])
    assert r.schedules[0].segments[0].rate == 12


# ---------------------------------------------------------------- 금액·충당·시효
def test_기준일까지_금액과_구간별_버림():
    c = Claim("퇴직금 차액", "퇴직금 차액", Decimal(50_000_000), date(2024, 2, 27), settlement=True)
    inp = _inp(employer_merchant=True, calc_until="2024-03-27", first_instance_judgment_date="2024-03-27")
    r = calculate_interest(inp, opts(), [c])
    assert r.total == 237_704          # 2. 28.~3. 27. 6%, 창원 사례와 같은 구간
    assert r.rows[0].fraction == "29/366"


def test_변제는_이자부터_충당():
    c = Claim("임금", "임금", Decimal(1_000_000), date(2023, 12, 31))
    inp = load_interest({"employer_merchant": False, "calc_until": "2024-12-31",
                         "payments": [{"date": "2024-07-01", "amount": 500_000, "claim": "임금"}]})
    r = calculate_interest(inp, opts(di_exclusion_end="none"), [c])
    first, second = r.rows
    assert first.end == date(2024, 6, 30) and first.principal == 1_000_000
    # 1,000,000 × 5% × 182/366 = 24,863 → 변제 500,000 중 24,863은 이자, 475,137은 원금
    assert first.interest == 24_863
    assert second.principal == 1_000_000 - (500_000 - 24_863)


def test_소멸시효_만료일():
    c = Claim("임금", "2021. 5.분", Decimal(1_000_000), date(2021, 5, 25))
    inp = _inp(suit_filed_date="2024-06-03")
    lr = calculate_interest(inp, opts(), [c]).limitation[0]
    assert lr.expiry == date(2024, 5, 27)   # 2024. 5. 25. 토요일 → 5. 27. 월요일
    assert lr.suspect is True


def test_14일째가_일요일이어도_다음날부터_20():
    # 성남지원 2021가합413433: 지급기한 2022. 7. 10.(일) → 20%는 7. 11.부터
    c = Claim("임금", "최종월 임금", Decimal(2_800_000), date(2022, 7, 10), settlement=True)
    segs = calculate_interest(_inp(), opts(di_exclusion_end="none"), [c]).schedules[0].segments
    assert (segs[0].start, segs[0].rate) == (date(2022, 7, 11), Decimal(20))


def test_근로기준법_적용제외_사업은_20_없음():
    c = Claim("퇴직금", "퇴직금", Decimal(1_000_000), date(2020, 1, 14), settlement=True)
    r = calculate_interest(_inp(lsa_not_applicable=True), opts(di_exclusion_end="none"), [c])
    assert {s.rate for s in r.schedules[0].segments} == {Decimal(6)}


def test_해고예고수당은_경고():
    c = Claim("해고예고수당", "해고예고수당", Decimal(3_000_000), date(2024, 3, 15), settlement=True)
    r = calculate_interest(_inp(), opts(), [c])
    assert any("해고예고수당" in w and "갈립니다" in w for w in r.warnings)


def test_입력_누락_오류():
    with pytest.raises(LaborError, match="employer_merchant"):
        load_interest({})
    with pytest.raises(LaborError, match="end_cause"):
        load_interest({"employer_merchant": True, "end_cause": "해고"})
