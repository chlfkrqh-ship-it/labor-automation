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


def test_2월_29일_기산_만_N년은_민법_160조():
    # 2. 29. 기산 1년은 다음 해 2. 28.에 만료(민법 제160조 제3항, retirement.one_year_expiry civil_code 와 같음)
    assert year_fraction(date(2024, 2, 29), date(2025, 2, 28), "anniv_feb29") == (Decimal(1), "1년")
    assert year_fraction(date(2024, 2, 29), date(2025, 2, 27), "anniv_feb29") == (Decimal(365) / 366, "365/366")
    f, desc = year_fraction(date(2024, 2, 29), date(2028, 2, 27), "anniv_feb29")
    assert desc == "3년 + 364/365" and f == 3 + Decimal(364) / 365
    assert year_fraction(date(2024, 2, 29), date(2028, 2, 28), "anniv_feb29") == (Decimal(4), "4년")
    assert year_fraction(date(2024, 2, 29), date(2025, 3, 1), "anniv_feb29")[1] == "1년 + 1/365"


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


def test_퇴직일이_지급기일인_청산금품은_6_후_15일째부터_20():
    # 퇴직금 rs_due_date=day_after_retirement: due_date = 마지막 근무일 2023. 6. 30. → 지연손해금은 7. 1.부터,
    # 20%는 지급사유 발생일 7. 1.부터 14일이 되는 7. 14. 다음 날부터(DI-02). 시효 기산일은 7. 1.(DI-15)
    c = Claim("퇴직금 차액", "퇴직금 차액", Decimal(1_000_000), date(2023, 6, 30), settlement=True)
    inp = load_interest({"employer_merchant": True, "suit_filed_date": "2026-06-25"}, {"last_working_day": "2023-06-30"})
    r = calculate_interest(inp, opts(di_exclusion_end="none"), [c])
    assert [(s.start, s.rate) for s in r.schedules[0].segments] == [
        (date(2023, 7, 1), Decimal(6)), (date(2023, 7, 15), Decimal(20))]
    lr = r.limitation[0]
    assert (lr.start, lr.expiry, lr.suspect) == (date(2023, 7, 1), date(2026, 7, 1), False)
    assert not any("지급기일 − 13일" in w for w in r.warnings)


def test_퇴직_직후_지급기일의_청산금품도_마지막근무일_15일부터_20():
    # 연차 모듈: 첫 정기지급일(3. 5.)이 퇴직(마지막 근무일 3. 3.) 뒤라 min(지급일, 퇴직 + 14일), settlement=True 로 넘긴 행
    c = Claim("연차휴가수당", "연차휴가수당", Decimal(872_727), date(2025, 3, 5), settlement=True)
    inp = load_interest({"employer_merchant": True}, {"last_working_day": "2025-03-03"})
    r = calculate_interest(inp, opts(di_exclusion_end="none"), [c])
    assert [(s.start, s.rate) for s in r.schedules[0].segments] == [
        (date(2025, 3, 6), Decimal(6)), (date(2025, 3, 18), Decimal(20))]
    assert r.limitation[0].start == date(2025, 3, 4)


def test_마지막근무일이_없으면_지급기일에서_역산하고_경고():
    c = Claim("퇴직금 차액", "퇴직금 차액", Decimal(1_000_000), date(2018, 3, 14), settlement=True)
    r = calculate_interest(_inp(), opts(di_exclusion_end="none"), [c])
    assert r.schedules[0].segments[0].start == date(2018, 3, 15)
    assert r.limitation[0].start == date(2018, 3, 1)
    assert any("지급기일 − 13일" in w for w in r.warnings)
    # 원금을 만든 모듈이 지급사유 발생일(trigger_date)을 알려 주면 그 날을 쓴다(퇴직금 모듈)
    c.trigger_date = date(2018, 3, 1)
    r = calculate_interest(_inp(), opts(di_exclusion_end="none"), [c])
    assert not any("지급기일 − 13일" in w for w in r.warnings)


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
    # 변제일(7. 1.)까지는 변제 전 원금 — 창원지법 2018가합52160 충당 이자(아래 G2)와 같은 날짜 규칙(DI-14)
    assert first.end == date(2024, 7, 1) and first.principal == 1_000_000
    # 1,000,000 × 5% × 183/366 = 25,000 → 변제 500,000 중 25,000은 이자, 475,000은 원금
    assert first.interest == 25_000
    assert second.start == date(2024, 7, 2)
    assert second.principal == 1_000_000 - (500_000 - 25_000)


def test_G2_창원_2018가합52160_변제일까지_변제전_원금_이자():
    # 해고기간 임금(원천징수 후 금액) 네 달분, 상사 6%, 2018. 7. 2. 변제 — 판결: 충당 이자 363,464원
    # (tests/test_labor_dismissal.py G2 의 원금·지급기일). 변제는 원금 항목마다 걸어 변제 전 이자만 모은다.
    claims = [Claim("해고기간 임금", f"G2-{i}", Decimal(a), d) for i, (a, d) in enumerate([
        (6_769_000, date(2018, 2, 10)), (6_769_000, date(2018, 3, 10)),
        (3_868_000, date(2018, 4, 10)), (2_965_466, date(2018, 5, 10))])]
    inp = load_interest({"employer_merchant": True, "calc_until": "2018-07-02",
                         "payments": [{"date": "2018-07-02", "amount": 1, "claim": c.label} for c in claims]})
    r = calculate_interest(inp, opts(di_exclusion_end="none"), claims)
    assert all(row.end == date(2018, 7, 2) for row in r.rows)
    assert sum(row.interest for row in r.rows) == 363_464


def test_지급기일_이전_변제는_원금에서_바로_뺀다():
    c = Claim("퇴직금 차액", "퇴직금 차액", Decimal(10_000_000), date(2024, 1, 14), settlement=True)
    for paid_on in ("2024-01-10", "2024-01-14"):
        inp = load_interest({"employer_merchant": True, "calc_until": "2024-12-31", "last_working_day": "2023-12-31",
                             "payments": [{"date": paid_on, "amount": 6_000_000, "claim": "퇴직금 차액"}]})
        r = calculate_interest(inp, opts(di_exclusion_end="none"), [c])
        [row] = r.rows
        assert (row.start, row.principal) == (date(2024, 1, 15), 4_000_000)
        assert r.total == 769_398                        # 4,000,000 × 20% × 352/366 버림
        assert any("이자 기산일" in w and "원금에서 바로 뺐습니다" in w for w in r.warnings)


def test_같은_날_변제_여러_건과_원천세():
    c = Claim("임금", "임금", Decimal(1_000_000), date(2023, 12, 31))

    def rows(*pays):
        inp = load_interest({"employer_merchant": False, "calc_until": "2024-12-31", "payments": [
            {"date": "2024-07-01", "amount": a, "claim": "임금", "kind": k} for a, k in pays]})
        return [(r.start, r.end, r.principal) for r in calculate_interest(inp, opts(di_exclusion_end="none"), [c]).rows]

    # 같은 날 변제 두 건: 빈 구간 없이 7. 1.까지 변제 전 원금, 7. 2.부터 이자 25,000 을 뺀 나머지로 원금 감액
    assert rows((300_000, "payment"), (200_000, "payment")) == [
        (date(2024, 1, 1), date(2024, 7, 1), 1_000_000), (date(2024, 7, 2), date(2024, 12, 31), 525_000)]
    # 원천세는 입력 순서와 관계없이 그날부터 감액(DI-13), 변제는 그날 이자까지 붙인 뒤 충당(DI-14)
    expected = [(date(2024, 1, 1), date(2024, 6, 30), 1_000_000), (date(2024, 7, 1), date(2024, 7, 1), 900_000),
                (date(2024, 7, 2), date(2024, 12, 31), 900_000 - (300_000 - 24_863 - 123))]
    assert rows((300_000, "payment"), (100_000, "withholding")) == expected
    assert rows((100_000, "withholding"), (300_000, "payment")) == expected


def test_기준일_뒤_변제는_반영하지_않고_경고():
    c = Claim("임금", "임금", Decimal(1_000_000), date(2023, 12, 31))
    inp = load_interest({"employer_merchant": False, "calc_until": "2024-06-30",
                         "payments": [{"date": "2024-07-01", "amount": 500_000, "claim": "임금"}]})
    r = calculate_interest(inp, opts(di_exclusion_end="none"), [c])
    assert [row.principal for row in r.rows] == [1_000_000]
    assert any("계산 기준일" in w and "반영하지 않았습니다" in w for w in r.warnings)


def test_소멸시효_만료일():
    c = Claim("임금", "2021. 5.분", Decimal(1_000_000), date(2021, 5, 25))
    inp = _inp(suit_filed_date="2024-06-03")
    lr = calculate_interest(inp, opts(), [c]).limitation[0]
    assert lr.expiry == date(2024, 5, 27)   # 2024. 5. 25. 토요일 → 5. 27. 월요일
    assert lr.suspect is True


def test_청산금품_시효는_초일산입_날짜도_비고에_적고_이른_날로_의심판정():
    # 마지막 근무일 2025. 6. 30. → 기산일 7. 1.(0시 시작). 초일 불산입(DI-15) 2028. 7. 1.(토) → 7. 3.(월),
    # 초일 산입(연차 AL-15 방식) 2028. 6. 30. — 두 날짜 사이에 소를 내면 '시효 완성 의심'
    c = Claim("퇴직금 차액", "퇴직금 차액", Decimal(1_000_000), date(2025, 7, 14), settlement=True)
    worker = {"last_working_day": "2025-06-30"}
    r = calculate_interest(load_interest({"employer_merchant": True, "suit_filed_date": "2028-07-01"}, worker), opts(), [c])
    lr = r.limitation[0]
    assert (lr.start, lr.expiry) == (date(2025, 7, 1), date(2028, 7, 3))
    assert "2028. 6. 30." in lr.note and lr.suspect is True
    assert any("초일 산입" in w and "2028. 6. 30." in w and "소 제기일" in w for w in r.warnings)
    assert any("두 규칙은 통일되지 않았으니" in w for w in r.warnings)
    r = calculate_interest(load_interest({"employer_merchant": True, "suit_filed_date": "2028-06-30"}, worker), opts(), [c])
    assert r.limitation[0].suspect is False
    # 정기지급일 임금은 초일 불산입만(비고 없음)
    wage = Claim("임금", "2025. 5.분", Decimal(1_000_000), date(2025, 5, 25))
    assert calculate_interest(load_interest({"employer_merchant": True}, worker), opts(), [wage]).limitation[0].note == ""


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


def test_알_수_없는_키는_오류():
    # service_date 오타 하나로 소송촉진법 구간이, items[].settlement 오타로 20%가 조용히 빠지지 않게 한다
    with pytest.raises(LaborError, match="알 수 없는 키: service_day"):
        load_interest({"employer_merchant": True, "service_day": "2024-09-02"})
    with pytest.raises(LaborError, match=r"items\[0\] 에 알 수 없는 키: settlment"):
        load_interest({"employer_merchant": True, "items": [
            {"label": "퇴직금", "amount": 1000, "due_date": "2024-03-15", "settlment": True}]})
    with pytest.raises(LaborError, match=r"payments\[0\] 에 알 수 없는 키: claim_label"):
        load_interest({"employer_merchant": True, "payments": [{"date": "2024-07-01", "amount": 1, "claim_label": "임금"}]})
    with pytest.raises(LaborError, match=r"exclusions\[0\] 에 알 수 없는 키: to"):
        load_interest({"employer_merchant": True, "exclusions": [{"start": "2024-01-01", "to": "2024-02-01"}]})
    with pytest.raises(LaborError, match="first_instance_close_date"):
        load_interest({"employer_merchant": True, "first_instance_closing_date": "2025-05-01"})
    with pytest.raises(LaborError, match="사전"):
        load_interest({"employer_merchant": True, "items": ["퇴직금"]})


def test_빈_값은_worker_값을_쓴다():
    inp = load_interest({"employer_merchant": None, "last_working_day": ""},
                        {"employer_merchant": False, "last_working_day": "2024-12-31"})
    assert inp.employer_merchant is False and inp.last_working_day == date(2024, 12, 31)
    assert load_interest({"employer_merchant": True, "last_working_day": "2025-01-31"},
                         {"last_working_day": "2024-12-31"}).last_working_day == date(2025, 1, 31)


# ---------------------------------------------------------------- DI-04·DI-13·끝수·분모·배제 종기 옵션 고정
def _retire_claim():
    return Claim("퇴직금 차액", "퇴직금 차액", Decimal(10_000_000), date(2024, 1, 14), settlement=True)


def test_제외기간_20_중단과_원천세_원금감액():
    inp = load_interest({"employer_merchant": True, "calc_until": "2024-12-31", "last_working_day": "2023-12-31",
                         "exclusions": [{"start": "2024-03-01", "end": "2024-06-30", "reason": "회생절차"}],
                         "payments": [{"date": "2024-09-01", "amount": 330_000, "claim": "퇴직금 차액",
                                       "kind": "withholding"}]})
    r = calculate_interest(inp, opts(di_exclusion_end="none"), [_retire_claim()])
    assert [(s.start, s.end, s.rate) for s in r.schedules[0].segments] == [
        (date(2024, 1, 15), date(2024, 2, 29), Decimal(20)),
        (date(2024, 3, 1), date(2024, 6, 30), Decimal(6)),       # 제18조 제1호 등 — 소송촉진법도 미적용(DI-08)
        (date(2024, 7, 1), None, Decimal(20))]
    # 원천세는 납부일(9. 1.)부터 줄어든 원금(DI-13)
    assert [(row.start, row.end, row.principal) for row in r.rows][-2:] == [
        (date(2024, 7, 1), date(2024, 8, 31), Decimal(10_000_000)), (date(2024, 9, 1), date(2024, 12, 31), Decimal(9_670_000))]
    assert r.rows[-1].interest == 9_670_000 * 20 * 122 // (100 * 365)
    assert any("원천세 330,000원" in w and "2013다36347" in w for w in r.warnings)


def test_끝수_합계후_버림과_분모_actual_365():
    inp = load_interest({"employer_merchant": True, "calc_until": "2024-12-31", "last_working_day": "2023-12-31",
                         "exclusions": [{"start": "2024-03-01", "end": "2024-06-30"}]})
    per = calculate_interest(inp, opts(di_exclusion_end="none"), [_retire_claim()])
    tot = calculate_interest(inp, opts(di_exclusion_end="none", di_rounding="floor_total"), [_retire_claim()])
    # 20% 46/366(2. 29. 포함) + 6% 122/365 + 20% 184/365
    raw = [Decimal(10_000_000) * r / 100 * Decimal(n) / den for r, n, den in ((20, 46, 366), (6, 122, 365), (20, 184, 365))]
    assert [row.fraction for row in per.rows] == ["46/366", "122/365", "184/365"]
    assert per.total == sum(remove_fraction(x, 0) for x in raw) == 1_460_132
    assert tot.total == remove_fraction(sum(raw), 0) == 1_460_133
    act = calculate_interest(inp, opts(di_exclusion_end="none", di_day_count="actual_365"), [_retire_claim()])
    assert [row.fraction for row in act.rows] == ["46/365", "122/365", "184/365"]


def test_배제_종기_선택지():
    c = Claim("퇴직금 차액", "퇴직금 차액", Decimal(1_000_000), date(2018, 3, 14), settlement=True)
    inp = _inp(first_instance_judgment_date="2020-02-05", appellate_judgment_date="2021-03-10",
               finality_date="2021-06-01")
    ends = {mode: calculate_interest(inp, opts(di_exclusion_end=mode), [c]).schedules[0].segments[0].end
            for mode in ("final_fact_instance", "first_instance", "finality")}
    assert ends == {"final_fact_instance": date(2021, 3, 10), "first_instance": date(2020, 2, 5),
                    "finality": date(2021, 6, 1)}
    assert any("2019나2050152" in w for w in calculate_interest(inp, opts(di_exclusion_end="finality"), [c]).warnings)


def test_직접_넣은_원금_항목():
    inp = load_interest({"employer_merchant": True, "items": [
        {"category": "해고예고수당", "label": "해고예고수당", "amount": 3_000_000, "due_date": "2024-03-15",
         "settlement": True, "note": "근로기준법 제26조"}]})
    r = calculate_interest(inp, opts(di_exclusion_end="none"), [])
    [sch] = r.schedules
    assert sch.claim.settlement and sch.claim.note == "근로기준법 제26조"
    assert (sch.segments[0].start, sch.segments[0].rate) == (date(2024, 3, 16), Decimal(20))
