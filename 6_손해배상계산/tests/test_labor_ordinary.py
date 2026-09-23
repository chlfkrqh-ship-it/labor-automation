"""통상임금 합산·월 기준시간·통상시급 (engine/labor/ordinary.py) 검증.

골든 예시는 조사 문서 ordinary_wage.md 3절과 검증 메모의 판결·행정해석 원문 숫자다.
판결문에 없는 사실(적용 기간 날짜 등)을 테스트용으로 정한 경우 그 사실을 주석에 적었다.
금액 기대값은 판결 숫자이거나, assert 옆에 Decimal 식을 그대로 적은 값이다.
"""

import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.labor.common import LaborError, resolve_options  # noqa: E402
from engine.labor.ordinary import (  # noqa: E402
    BOUNDARY,
    OPTIONS,
    RULES,
    calculate_ordinary,
    load_ordinary,
    monthly_base_hours,
)

D = Decimal
Q = D("1e-10")


def run(raw, **opt):
    inp = load_ordinary(raw)
    opts, _ = resolve_options(opt, OPTIONS)
    return calculate_ordinary(inp, opts)


def hours(**kw):
    h = {"from": "2000-01-01", "weekly_hours": 40, "daily_hours": 8}
    h.update(kw)
    return [h]


def item(name, amount, cycle="month", frm="2018-01-01", to="2018-12-31", old=True, new=None, **kw):
    it = {"name": name, "amount": amount, "cycle": cycle, "from": frm, "to": to, "old": old, "source": "테스트"}
    if new is not None:
        it["new"] = new
    it.update(kw)
    return it


def raw_of(items, wage_form="monthly", **kw):
    r = {"wage_form": wage_form, "hours": hours(), "items": items}
    r.update(kw)
    return r


# ================================================================ 모듈 규약
def test_옵션_키_접두어와_기본값():
    assert all(k.startswith("ow_") for k in OPTIONS)
    values, _ = resolve_options({}, OPTIONS)
    assert values["ow_weeks_per_year"] == "365/7"
    assert values["ow_month_hours_rounding"] == "round_int"
    assert values["ow_hourly_rounding"] == "none"
    assert values["ow_public_holidays_in_hours"] is False          # OW-18 정황 기본값
    assert values["ow_part_time_daily_hours"] == "input"            # OW-17 확인불가 → 기본값으로 쓰지 않음
    assert values["ow_part_time_holiday_hours"] == "input"
    assert values["ow_nonwork_regime"] == "by_date"
    assert "52.14" in OPTIONS["ow_weeks_per_year"].choices         # OW-13 검증 추가 변형


def test_규칙_상태_어휘():
    allowed = {"판례확립", "법령", "행정해석", "하급심", "실무관행", "불명확"}
    for rid, (summary, status) in RULES.items():
        assert summary
        assert set(status.split("·")) <= allowed, rid
    for rid in ("OW-03a", "OW-M1", "OW-M2", "OW-M3", "OW-M4", "OW-M5"):
        assert rid in RULES
    assert RULES["OW-13"][1] == "불명확" and RULES["OW-14"][1] == "불명확"


def test_청구액_없음():
    res = run(raw_of([item("기본급", 2090000)]))
    assert res.total == 0 and res.claims == []


# ================================================================ G1 대법원 2015다73067 (가산율 불고려)
def test_G1_일급_분모_13시간_월급_분모_가산율_없음():
    raw = {"wage_form": "daily", "hours": hours(weekly_overtime_hours="22.5", weekly_night_overtime_hours="2.5",
                                                daily_overtime_hours="4.5", daily_night_overtime_hours="0.5"),
           "items": [item("기본일급", 130000, "day"), item("월 고정수당", 1000000, "month")]}
    res = run(raw, ow_month_hours_rounding="none")
    row = res.rows[0]
    judgment = (D(40) + 8 + D("22.5") + D("2.5")) * 365 / D(12) / D(7)   # 판결 원문 월급 분모 산식
    assert row.monthly_hours == D(73) * 365 / 84
    assert row.monthly_hours.quantize(Q) == judgment.quantize(Q)        # 317.2023809524
    assert row.weekly_base_hours == 73
    shares = {s.name: s for s in row.items}
    assert shares["기본일급"].hourly_part == D(130000) / (D(8) + D("4.5") + D("0.5"))   # 일급 분모 13시간 = 10,000원
    assert shares["월 고정수당"].hourly_part == D(1000000) / (D(73) * 365 / 84)


def test_G1_기본급에_법정_연장수당_포함이면_가산율_반영():
    raw = raw_of([item("기본급", 3000000, includes_statutory_ot=True), item("직책수당", 580000)],
                 hours=hours(weekly_overtime_hours=10))
    res = run(raw, ow_month_hours_rounding="none")
    shares = {s.name: s for s in res.rows[0].items}
    assert shares["기본급"].hourly_part == D(3000000) / ((D(40) + D(10) * D("1.5") + 8) * 365 / 84)
    assert shares["직책수당"].hourly_part == D(580000) / ((D(40) + 10 + 8) * 365 / 84)


# ================================================================ G2·G4·G5·G6·G12 월 기준시간
def test_G2_2019다230899_토요일_4시간_226시간_52주_8시간():
    # "226시간[= {(1주 40시간 + 토요일 4시간 + 일요일 8시간) × 52주 + 8시간} ÷ 12개월]"
    for r in ("round_int", "none"):
        res = run(raw_of([item("기본급", 2260000)], hours=hours(weekly_paid_hours=4)),
                  ow_weeks_per_year="52w+1day", ow_month_hours_rounding=r)
        assert res.rows[0].monthly_hours == 226
        assert res.rows[0].hourly == 10000                  # 2,260,000 ÷ 226


@pytest.mark.parametrize("paid,expected", [(0, 209), (4, 226), (8, 243)])
def test_G4_서울고법_2022나2018325_토요일_처리별_209_226_243(paid, expected):
    # G3(2020다247190 243 수긍), G6(근로기준과-2883 243), G12(안양 2017가단121258 209) 포함
    res = run(raw_of([item("기본급", 2000000)], hours=hours(weekly_paid_hours=paid)))
    assert res.rows[0].monthly_hours == expected


def test_G4_주44시간제_226시간():
    # "226시간[≒ (44+8) × 365/7 ÷ 12]"
    assert run(raw_of([item("기본급", 1)], hours=hours(weekly_hours=44))).rows[0].monthly_hours == 226


def test_G5_행정해석_68201_1568_52주_8시간_209():
    res = run(raw_of([item("기본급", 1)]), ow_weeks_per_year="52w+1day", ow_month_hours_rounding="none")
    assert res.rows[0].monthly_hours == (D(48) * 52 + 8) / 12          # 208.666…
    assert run(raw_of([item("기본급", 1)]), ow_weeks_per_year="52w+1day").rows[0].monthly_hours == 209


def test_기준시간_끝수_옵션_208_57_와_52_14주():
    assert run(raw_of([item("기본급", 1)]), ow_month_hours_rounding="floor_2dp").rows[0].monthly_hours == D("208.57")
    assert run(raw_of([item("기본급", 1)]), ow_month_hours_rounding="none").rows[0].monthly_hours == D(48) * 365 / 84
    assert run(raw_of([item("기본급", 1)]), ow_weeks_per_year="52.14",
               ow_month_hours_rounding="none").rows[0].monthly_hours == D(48) * D("52.14") / 12   # 208.56
    assert monthly_base_hours(D(48), D(8), "365/7", "round_int") == 209


def test_G3_법정_기준시간_직접_입력_243():
    res = run(raw_of([item("기본급", 2430000)], hours=hours(monthly_hours=243)))
    assert res.rows[0].monthly_hours == 243 and res.rows[0].hourly == 10000
    assert any("2018다206899" in w for w in res.warnings)            # OW-M1 경고


# ================================================================ G7 창원 2015나31876 (연액 ÷ 12 ÷ 209, 반올림)
def test_G7_연봉형_기본급_상여금_9902원_10176원():
    # 적용 연도(2013·2014년)는 테스트용
    items = [item("기본급", 18061000, "year", "2013-01-01", "2013-12-31"),
             item("상여금", 6773000, "year", "2013-01-01", "2013-12-31"),
             item("기본급", 18562000, "year", "2014-01-01", "2014-12-31"),
             item("상여금", 6960000, "year", "2014-01-01", "2014-12-31")]
    res = run(raw_of(items), ow_hourly_rounding="half_up")
    assert res.hourly_of(date(2013, 6, 1)) == 9902          # "9,902원(=24,834,000원/12개월/209시간)"
    assert res.hourly_of(date(2014, 6, 1)) == 10176         # "10,176원(=25,522,000원/12개월/209시간)"
    assert res.rows[0].monthly_sum == D(24834000) / 12


# ================================================================ G8 서울중앙 2019가단5120995 (원 미만 버림)
def test_G8_시급_8277원_9234원_연장수당_5959440원():
    items = [item("월 통상임금", 1730000, "month", "2018-01-01", "2018-12-31"),
             item("월 통상임금", 1930000, "month", "2019-01-01", "2019-12-31")]
    res = run(raw_of(items), ow_hourly_rounding="floor")
    assert res.hourly_of(date(2018, 5, 1)) == 8277          # "8,277원(= 1,730,000원 ÷ 209시간, 원 미만 버림)"
    assert res.hourly_of(date(2019, 5, 1)) == 9234
    assert res.hourly_of(date(2018, 5, 1)) * D("1.5") * 4 * 120 == 5959440   # 판결 원문 연장수당
    half = run(raw_of(items), ow_hourly_rounding="half_up")
    assert half.hourly_of(date(2018, 5, 1)) == 8278         # 반올림이면 판결과 다름


def test_G8_원고B_시급_9138원():
    res = run(raw_of([item("월 통상임금", 1910000)]), ow_hourly_rounding="floor")
    assert res.hourly_of("2018-03-01") == 9138
    assert res.daily_ordinary_of("2018-03-01") == D(9138) * 8   # 연차수당 9,138 × 8 × 26 = 1,900,704 의 1일분


# ================================================================ G9 서울중앙 2024나77015 (208.57, 1일 통상임금 버림)
def test_G9_1일_통상임금_122740원():
    raw = raw_of([item("월급", 3200000, "month", "2022-07-01", "2023-10-31")])
    res = run(raw, ow_month_hours_rounding="floor_2dp", ow_daily_rounding="floor")
    assert res.monthly_hours_of(date(2023, 10, 31)) == D("208.57")
    assert res.daily_ordinary_of(date(2023, 10, 31)) == 122740      # 판결 원문 "122,740원"
    unrounded = run(raw, ow_month_hours_rounding="none", ow_daily_rounding="floor")
    assert unrounded.daily_ordinary_of(date(2023, 10, 31)) == 122739  # 208.5714… 그대로면 판결과 다름


# ================================================================ G10 광주 2022가단6251 (버린 시급 × 8)
def test_G10_연봉_63000000원_시급_25119원_1일_200952원():
    raw = raw_of([item("연봉", 63000000, "year", "2015-11-05", "2022-02-28")])
    res = run(raw, ow_hourly_rounding="floor")
    d = date(2022, 2, 28)
    assert res.monthly_ordinary_of(d) == 5250000              # "월 5,250,000원"
    assert res.hourly_of(d) == 25119                          # "25,119원"
    assert res.daily_ordinary_of(d) == 200952                 # "200,952원(= 25,119원 × 8시간)"
    other = run(raw, ow_hourly_rounding="floor", ow_daily_from_rounded_hourly=False, ow_daily_rounding="floor")
    assert other.daily_ordinary_of(d) == 200956               # 버리기 전 시급 × 8 = 200,956.94 → 판결과 다름


# ================================================================ G11 근로기준정책과-3409 (연 3회 상여금)
def test_G11_재직기간별_상여금_연_3회():
    items = [item("기본급", 2090000, "month", "2025-01-01", "2025-03-31", old=None, new=True),
             item("정기상여금", 100000, "year", "2025-01-01", "2025-03-31", old=None, new=True, times_per_year=3)]
    res = run(raw_of(items), ow_month_hours_rounding="round_int")
    shares = {s.name: s for s in res.rows[0].items}
    assert shares["정기상여금"].hourly_part == D(100000) * 3 / 12 / 209   # "[(10만원 + 10만원 + 10만원) / 12개월 / 209시간]"


# ================================================================ OW-03 법리 경계
def _boundary_items(parallel=False):
    return [item("기본급", 2090000, "month", "2024-10-01", "2025-03-31", new=True),
            item("재직조건부 상여금", 600000, "quarter", "2024-10-01", "2025-03-31", old=False, new=True, parallel=parallel)]


def test_2024_12_18과_19_경계():
    res = run(raw_of(_boundary_items()))
    assert res.hourly_of(date(2024, 12, 18)) == D(2090000) / 209
    assert res.hourly_of(date(2024, 12, 19)) == (D(2090000) + D(600000) / 3) / 209
    ends = [(r.start, r.end) for r in res.rows]
    assert (date(2024, 10, 1), date(2024, 12, 18)) in ends and (date(2024, 12, 19), date(2025, 3, 31)) in ends
    assert res.rows[0].regime.startswith("구 법리") and res.rows[1].regime.startswith("신 법리")
    assert BOUNDARY == date(2024, 12, 19)


def test_병행_항목은_신_법리_소급():
    res = run(raw_of(_boundary_items(parallel=True)))
    assert res.hourly_of(date(2024, 12, 18)) == (D(2090000) + D(600000) / 3) / 209
    assert "병행 항목 신 법리 소급" in res.rows[0].regime
    assert any("OW-03a" in w for w in res.warnings)            # parallel_claims 권고
    assert res.hourly_of(date(2024, 12, 18), regime="old") == D(2090000) / 209


def test_병행사건_수당_청구묶음별():
    raw = raw_of(_boundary_items(parallel=True), parallel_claims=[
        {"allowance": "overtime", "bundle": "최초", "served": "2022-05-02", "parallel": True},
        {"allowance": "public_holiday", "bundle": "확장", "served": "2025-03-10", "parallel": False}])
    res = run(raw)
    full = (D(2090000) + D(600000) / 3) / 209
    base = D(2090000) / 209
    assert res.hourly_of(date(2024, 11, 1), allowance="overtime", bundle="최초") == full
    assert res.hourly_of(date(2024, 11, 1), allowance="public_holiday", bundle="확장") == base
    assert res.hourly_of(date(2024, 11, 1), allowance="night") == full         # 표에 없는 수당은 항목 플래그
    with pytest.raises(LaborError, match="parallel_claims"):
        res.hourly_of(date(2024, 11, 1), allowance="overtime", bundle="2차")
    # 12. 19. 이후 공휴일수당: by_date(기본) 신 법리 + 경고, old_unless_parallel 이면 구 법리
    assert res.hourly_of(date(2025, 1, 1), allowance="public_holiday", bundle="확장") == full
    assert any("OW-M5" in w and "공휴일" in w for w in res.warnings)
    alt = run(raw, ow_nonwork_regime="old_unless_parallel")
    assert alt.hourly_of(date(2025, 1, 1), allowance="public_holiday", bundle="확장") == base
    assert alt.hourly_of(date(2025, 1, 1), allowance="overtime", bundle="최초") == full


def test_계산기간이_2024_12_19_이후에_시작해도_OW_M5_경고():
    # old_unless_parallel 이면 이후 날짜도 구 법리 → 연차수당 등이 옵션에 따라 갈린다. 조립 모듈은 calculate 직후
    # warnings 만 옮기므로 콜러블을 부르기 전에 이미 경고가 있어야 한다
    items = [item("기본급", 2090000, "month", "2025-01-01", "2025-06-30", new=True),
             item("재직조건부 상여금", 600000, "quarter", "2025-01-01", "2025-06-30", old=False, new=True)]
    res = run(raw_of(items))
    assert any(w.startswith("OW-M5") for w in res.warnings)
    alt = run(raw_of(items), ow_nonwork_regime="old_unless_parallel")
    d = date(2025, 3, 1)
    assert res.daily_ordinary_of(d, allowance="annual_leave") != alt.daily_ordinary_of(d, allowance="annual_leave")
    before = run(raw_of([item("기본급", 2090000), item("재직조건부 상여금", 600000, "quarter", old=False, new=True)]))
    assert not any("OW-M5" in w for w in before.warnings)            # 2024. 12. 18. 이전만이면 옵션과 무관


def test_old_unless_parallel_은_경계_뒤_항목에도_old_필요():
    items = [item("기본급", 2090000, "month", "2024-10-01", "2025-06-30", new=True),
             item("신설수당", 209000, "month", "2025-01-01", "2025-06-30", old=None, new=True)]
    d = date(2025, 3, 1)
    assert run(raw_of(items)).daily_ordinary_of(d, allowance="annual_leave") == (D(2090000) + D(209000)) / 209 * 8
    alt = run(raw_of(items), ow_nonwork_regime="old_unless_parallel")
    assert alt.hourly_of(d, allowance="overtime") == (D(2090000) + D(209000)) / 209    # 연장근로수당은 날짜 기준
    with pytest.raises(LaborError, match="old_unless_parallel"):
        alt.daily_ordinary_of(d, allowance="annual_leave")


# ================================================================ OW-15 주기 환산
@pytest.mark.parametrize("cycle,amount", [("quarter", 600000), ("half", 1200000), ("year", 2400000), ("bimonth", 400000),
                                          ("분기", 600000), ("연", 2400000)])
def test_1개월_초과_주기_월_환산(cycle, amount):
    res = run(raw_of([item("상여금", amount, cycle)]))
    assert res.rows[0].monthly_sum == 200000     # 분기 ÷3, 반기 ÷6, 연 ÷12, 격월 ÷2
    assert res.hourly_of("2018-01-01") == D(200000) / 209


def test_퍼센트형_상여금_base_item():
    items = [item("기본급", 2000000), item("상여금", None, "year", base_item="기본급", rate="7.5")]
    del items[1]["amount"]
    res = run(raw_of(items))
    shares = {s.name: s for s in res.rows[0].items}
    assert shares["상여금"].contract_amount == D(2000000) * D("7.5")
    assert shares["상여금"].monthly_equivalent == D(2000000) * D("7.5") / 12


# ================================================================ OW-16·M2 임금형태
def test_일급제_시급_합산과_주휴수당_차액_가능():
    items = [item("일급", 80000, "day"), item("월 고정수당", 209000, "month"), item("시간급 수당", 500, "hour"),
             item("주급 수당", 480000, "week")]
    res = run(raw_of(items, wage_form="daily"))
    d = date(2018, 1, 1)
    assert res.hourly_of(d) == D(80000) / 8 + D(209000) / 209 + 500 + D(480000) / 48
    assert res.daily_ordinary_of(d) == (D(80000) / 8 + D(209000) / 209 + 500 + D(480000) / 48) * 8
    assert res.monthly_ordinary_of(d) == D(209000) + (D(80000) / 8 + 500 + D(480000) / 48) * 209
    assert res.weekly_holiday_diff_allowed is True


def test_시급제와_월급제_주휴수당_차액():
    assert run(raw_of([item("시급", 10030, "hour")], wage_form="시급제")).weekly_holiday_diff_allowed is True
    assert run(raw_of([item("기본급", 2090000)])).weekly_holiday_diff_allowed is False     # 2018다206899
    assert run(raw_of([item("기본급", 2090000)], weekly_holiday_diff_agreed=True)).weekly_holiday_diff_allowed is True


# ================================================================ OW-17 단시간
def test_단시간_주20시간_주휴_입력_104시간():
    raw = raw_of([item("월급", 1040000)], part_time=True, hours=hours(weekly_hours=20, daily_hours=4, weekly_holiday_hours=4))
    res = run(raw)
    assert res.rows[0].weekly_base_hours == 24 and res.rows[0].monthly_hours == 104     # 24 × 365 ÷ 84 = 104.2857 → 104
    assert run(raw, ow_month_hours_rounding="none").rows[0].monthly_hours == D(24) * 365 / 84
    assert any("OW-17" in w for w in res.warnings)


def test_단시간_주휴시간_누락은_오류_옵션이면_1일분():
    raw = raw_of([item("월급", 1040000)], part_time=True, hours=hours(weekly_hours=20, daily_hours=4))
    with pytest.raises(LaborError, match="weekly_holiday_hours"):
        run(raw)
    assert run(raw, ow_part_time_holiday_hours="daily_hours").rows[0].weekly_base_hours == 24


def test_단시간_별표2_옵션():
    raw = raw_of([item("월급", 1040000)], part_time=True,
                 hours=hours(weekly_hours=None, daily_hours=None, four_week_hours=80, full_time_four_week_days=20))
    res = run(raw, ow_part_time_daily_hours="annex2", ow_part_time_holiday_hours="daily_hours")
    assert res.rows[0].daily_hours == D(80) / 20
    assert res.rows[0].weekly_base_hours == D(80) / 4 + D(80) / 20
    with pytest.raises(LaborError, match="weekly_hours"):
        run(raw)                                              # 기본(input)이면 입력 시간 필요


@pytest.mark.parametrize("weekly,expected_base", [("14.99", D("14.99")), ("15", D(15) + 3)])
def test_주_15시간_미만_주휴_미적용(weekly, expected_base):
    raw = raw_of([item("월급", 600000)], part_time=True, hours=hours(weekly_hours=weekly, daily_hours=3, weekly_holiday_hours=3))
    res = run(raw)
    assert res.rows[0].weekly_base_hours == expected_base
    if weekly == "14.99":
        assert any("제18조 제3항" in w for w in res.warnings)


# ================================================================ OW-14 끝수
@pytest.mark.parametrize("mode,expected", [("none", D(1730000) / 209), ("floor", D(8277)), ("half_up", D(8278))])
def test_통상시급_끝수_옵션(mode, expected):
    assert run(raw_of([item("월급", 1730000)]), ow_hourly_rounding=mode).hourly_of("2018-01-01") == expected


def test_1일_통상임금_끝수_옵션():
    raw = raw_of([item("월급", 1730000)])
    assert run(raw).daily_ordinary_of("2018-01-01") == D(1730000) / 209 * 8
    assert run(raw, ow_daily_rounding="half_up").daily_ordinary_of("2018-01-01") == 66220      # 66,220.0956…
    assert run(raw, ow_hourly_rounding="floor").daily_ordinary_of("2018-01-01") == D(8277) * 8


# ================================================================ OW-08·18·M1
def test_신의칙_제외_기간_항목():
    items = [item("기본급", 2090000, "month", "2024-01-01", "2024-12-31", new=True),
             item("상여금", 600000, "quarter", "2024-01-01", "2024-12-31", old=False, new=True, parallel=True)]
    res = run(raw_of(items, good_faith_excluded=[{"from": "2024-01-01", "to": "2024-06-30", "items": ["상여금"]}]))
    assert res.hourly_of("2024-03-01") == D(2090000) / 209
    assert res.hourly_of("2024-07-01") == (D(2090000) + D(600000) / 3) / 209
    assert "신의칙 제외" in res.rows[0].note


def test_신의칙_제외_items_를_비우면_전_항목_제외_경고():
    items = [item("기본급", 2090000), item("상여금", 600000, "quarter")]
    res = run(raw_of(items, good_faith_excluded=[{"from": "2018-01-01", "to": "2018-06-30"}]))
    assert res.hourly_of("2018-03-01") == 0                              # 문서대로 전 항목 제외
    assert any("모든 임금 항목" in w for w in res.warnings)
    named = run(raw_of(items, good_faith_excluded=[{"from": "2018-01-01", "to": "2018-06-30", "items": ["상여금"]}]))
    assert not any("모든 임금 항목" in w for w in named.warnings)


@pytest.mark.parametrize("section,value", [
    ("good_faith_excluded", [{"from": "2018-01-01", "to": "2018-06-30", "item": ["상여금"]}]),   # items 오타 → 전 항목 0
    ("parallel_claims", [{"allowance": "overtime", "bundel": "최초", "parallel": True}]),
    ("agreed", {"monthly_hours": 183, "daily_hour": 8, "items": [{"name": "기본급", "amount": 1, "cycle": "month",
                                                                  "from": "2018-01-01"}]}),
    ("agreed", {"monthly_hours": 183, "items": [{"name": "기본급", "amount": 1, "cycle": "month", "from": "2018-01-01",
                                                 "too": "2018-06-30"}]}),
])
def test_하위_목록의_모르는_키는_오류(section, value):
    raw = raw_of([item("기본급", 2090000), item("상여금", 600000, "quarter")], **{section: value})
    with pytest.raises(LaborError, match="알 수 없는 키"):
        load_ordinary(raw)


def test_공휴일_유급시간_옵션():
    raw = raw_of([item("기본급", 1)], hours=hours(public_holiday_hours_per_year=88))
    assert run(raw).rows[0].monthly_hours == 209
    assert run(raw, ow_public_holidays_in_hours=True).rows[0].monthly_hours == 216      # 208.571 + 88 ÷ 12 = 215.905
    with pytest.raises(LaborError, match="public_holiday_hours_per_year"):
        run(raw_of([item("기본급", 1)]), ow_public_holidays_in_hours=True)


def test_월_기준시간_직접_입력이면_공휴일_가산을_했다고_적지_않음():
    # monthly_hours 는 '있으면 산식 대신' — 공휴일 시간을 더하지 않으므로 비고·경고도 더했다고 남기지 않는다
    raw = raw_of([item("기본급", 2090000)], hours=hours(monthly_hours=209, public_holiday_hours_per_year=120))
    res = run(raw, ow_public_holidays_in_hours=True)
    row = res.rows[0]
    assert row.monthly_hours == 209 and row.hourly == 10000
    assert "공휴일 유급" not in row.note
    assert not any("더했습니다" in w for w in res.warnings)
    assert any("직접 입력해 공휴일" in w for w in res.warnings)
    run(raw_of([item("기본급", 1)], hours=hours(monthly_hours=209)), ow_public_holidays_in_hours=True)   # 공휴일 시간 없어도 됨
    mixed = raw_of([item("기본급", 1)], hours=[
        {"from": "2000-01-01", "weekly_hours": 40, "daily_hours": 8, "monthly_hours": 243},
        {"from": "2018-07-01", "weekly_hours": 40, "daily_hours": 8, "public_holiday_hours_per_year": 88}])
    res = run(mixed, ow_public_holidays_in_hours=True)
    assert [r.monthly_hours for r in res.rows] == [243, 216]
    assert "공휴일 유급" not in res.rows[0].note and "공휴일 유급" in res.rows[1].note
    assert any("더했습니다" in w for w in res.warnings)


def test_약정_통상시급은_약정_기준시간과만_묶음():
    raw = raw_of([item("기본급", 2090000)], agreed={"monthly_hours": 183, "items": [
        {"name": "기본급", "amount": 2090000, "cycle": "month", "from": "2018-01-01"}]})
    res = run(raw)
    assert res.hourly_of("2018-05-01") == D(2090000) / 209               # 법정은 법정 기준시간
    assert res.agreed_hourly_of("2018-05-01") == D(2090000) / 183
    assert res.rows[0].agreed_hourly == D(2090000) / 183
    with pytest.raises(LaborError, match="agreed"):
        run(raw_of([item("기본급", 1)])).agreed_hourly_of("2018-05-01")


def test_기준시간_이력_변경():
    raw = raw_of([item("기본급", 2260000)], hours=[
        {"from": "2018-01-01", "weekly_hours": 40, "daily_hours": 8},
        {"from": "2018-07-01", "weekly_hours": 40, "daily_hours": 8, "weekly_paid_hours": 4}])
    res = run(raw)
    assert res.monthly_hours_of("2018-06-30") == 209 and res.monthly_hours_of("2018-07-01") == 226


def test_근무일수_조건_경고():
    items = [item("근무일수 수당", 100000, frm="2025-01-01", to="2025-01-31", old=None, new=False,
                  cond_workdays_required=20, scheduled_workdays=20)]
    res = run(raw_of(items))
    assert any("소정근로일수 이내" in w for w in res.warnings)          # OW-01 요구일수 == 소정근로일수도 산입


# ================================================================ 입력 오류
def test_임금형태_누락():
    with pytest.raises(LaborError, match="wage_form"):
        load_ordinary({"hours": hours(), "items": [item("기본급", 1)]})


def test_판정표_누락():
    with pytest.raises(LaborError, match="items"):
        load_ordinary({"wage_form": "monthly", "hours": hours()})


def test_근로시간_누락():
    with pytest.raises(LaborError, match="hours"):
        load_ordinary({"wage_form": "monthly", "items": [item("기본급", 1)]})
    with pytest.raises(LaborError, match="daily_hours"):
        run(raw_of([item("기본급", 1)], hours=[{"from": "2000-01-01", "weekly_hours": 40}]))


def test_구_신_법리_판정_누락():
    with pytest.raises(LaborError, match="old"):
        load_ordinary(raw_of([item("기본급", 1, old=None)]))
    with pytest.raises(LaborError, match="new"):
        load_ordinary(raw_of([item("기본급", 1, to="2025-01-31")]))
    with pytest.raises(LaborError, match="new"):
        load_ordinary(raw_of([item("기본급", 1, parallel=True)]))


def test_끝_열린_항목에_계산기간_끝_누락():
    with pytest.raises(LaborError, match="ordinary.to"):
        run(raw_of([item("기본급", 1, to=None, new=True)]))
    res = run(raw_of([item("기본급", 1, to=None, new=True)], to="2025-02-28"))
    assert res.period_end == date(2025, 2, 28)


def test_기간_밖_날짜():
    res = run(raw_of([item("기본급", 2090000)]))
    with pytest.raises(LaborError, match="계산 기간"):
        res.hourly_of(date(2019, 1, 1))
    with pytest.raises(LaborError, match="계산 기간"):
        res.daily_ordinary_of(date(2017, 12, 31))
    with pytest.raises(LaborError, match="계산 기간"):
        res.monthly_ordinary_of(date(2019, 1, 1))


def test_기타_입력_오류():
    with pytest.raises(LaborError, match="cycle"):
        load_ordinary(raw_of([item("기본급", 1, "biweekly")]))
    with pytest.raises(LaborError, match="알 수 없는 키"):
        load_ordinary(raw_of([item("기본급", 1, amt=3)]))
    with pytest.raises(LaborError, match="included: false"):
        load_ordinary(raw_of([item("기본급", 1, old={"included": False, "amount": 5})]))
    with pytest.raises(LaborError, match="amount"):
        load_ordinary(raw_of([{"name": "기본급", "cycle": "month", "from": "2018-01-01", "to": "2018-12-31", "old": True}]))
    with pytest.raises(LaborError, match="첫 from"):
        run(raw_of([item("기본급", 1)], hours=[{"from": "2018-02-01", "weekly_hours": 40, "daily_hours": 8}]))
    with pytest.raises(LaborError, match="regime"):
        run(raw_of([item("기본급", 1)])).hourly_of("2018-01-01", regime="both")
    with pytest.raises(LaborError):
        calculate_ordinary(load_ordinary(raw_of([item("기본급", 1)])), {"ow_hourly_rounding": "ceil"})
