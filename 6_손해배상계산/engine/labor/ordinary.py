"""통상임금 합산·월 기준시간·통상시급 (lane: ordinary_wage, 규칙 OW-01~OW-19, OW-03a, OW-M1~M5).

사람이 사건.yaml `ordinary:` 절에 적은 임금 항목 판정표(항목별 구·신 법리 산입액)와 근로시간 사실로
기간별 월 통상임금 합, 월 기준시간, 통상시급, 1일 통상임금을 낸다. **통상임금성 판단은 하지 않는다.**
엔진이 하는 일은 (a) 2024. 12. 19. 기준 법리 구간 분할, (b) 월 통상임금 합산, (c) 기준시간 산정,
(d) 통상시급 산정, (e) 끝수처리뿐이다. 이 모듈은 청구액이 없다(total = 0, claims = []).
다른 모듈에는 결과의 콜러블 `hourly_of(d)`, `daily_ordinary_of(d)`, `monthly_ordinary_of(d)` 를 넘긴다.
금액 기대값은 판결 원문 숫자로 검증했다(tests/test_labor_ordinary.py).

---------------------------------------------------------------- 통상임금 판정(사람 입력)
OW-01 [판례확립] 새 개념 — 대법원 2024. 12. 19. 선고 2020다247190 전원합의체 "통상임금은 소정근로의 대가로서
      정기적, 일률적으로 지급하기로 정한 임금을 말한다", 고정성 폐기. 근무일수 조건은 요구일수가 소정근로일수
      '이내'면 산입(같은 경우 포함) — 2023다302838 "소정근로일수를 초과하는 근무일수 조건부 임금은 … 통상임금이
      아니다". 출근율 차등 구간이 있어도 산입액은 온전 제공 시 금액(2021다264628). 항목에 `cond_workdays_required`
      ·`scheduled_workdays` 를 적으면 신 법리 판정과 어긋날 때 경고만 한다.
OW-02 [판례확립] 종전 개념 — 2012다89399 전원합의체(정기성·일률성·고정성). 재직조건·근무일수 조건 임금은 0,
      일할 지급분·최소 보장분만 산입. 일률성 부분(가족수당·휴직자 제한)은 2020다247190이 변경하지 않음.
OW-04 [판례확립, 일부 유추] 판정표: 항목별 `old`·`new` 산입 여부·산입액. 참조표의 근거 등급(검증 반영):
      재직조건부 상여금 구 0/신 전액(대법원), 근무일수 조건 ≤ 소정근로일수 구 0/신 전액(대법원),
      성과급 최소 보장분(대법원), 가족·자녀수당(해당자만) 신 법리 0 은 대법원 직접 판시가 아니라
      장애인수당 판단(2019다204876)·행정해석 3278·1심(서울중앙 2022가합537373)의 유추.
OW-M4 [판례확립(구 법리)] 전년도 실적 성과급을 지급시기만 늦춘 경우 당해 연도가 아니라 전년도 임금(2018다206899 [3]).
      항목의 `from`~`to` 는 **귀속기간**(그 임금이 대가로 하는 기간)이다. 지급 시점은 `paid_in` 에 적어 비고로만 남긴다.
OW-05 [판례확립] 약정액 기준 — 2020다247190 "통상임금은 실제 근무일수나 실제 수령한 임금에 구애되지 않고
      산정하여야 한다". 결근 공제·실수령액을 넣지 않는다. 재직기간별 차등액은 구간별 항목으로 나눠 적는다.
OW-06 [판례확립] 주휴수당 등 법정수당은 산입하지 않음(2020다247190 "개념적으로 통상임금이 될 수 없으므로").
      주휴분이 포함된 월급은 월급 전체를 넣고 기준시간에 주휴시간을 넣는다(월급에서 주휴분을 빼지 않음).
OW-08 [판례확립(법리)] 신의칙은 판단하지 않는다. 인정된 기간·항목을 `good_faith_excluded` 로 적으면 그 기간
      그 항목 산입액을 0 으로 둔다(2012다89399, 2016다7975 "신중하고 엄격하게 판단").

---------------------------------------------------------------- 적용 법리 구간
OW-03 [판례확립] 2020다247190 "이 판결 선고일인 2024. 12. 19. 이후 제공한 연장근로 등에 대한 법정수당은
      새로운 법리에 따른 통상임금의 범위를 기초로 …, 2024. 12. 18.까지 제공한 연장근로 등에 대한 법정수당은
      이 사건 및 병행사건을 제외하고는 종래 법리에 따른 통상임금을 기초로 산정하여야 한다".
      구간은 날짜로 가른다: d >= 2024-12-19 신 법리, d <= 2024-12-18 구 법리(병행사건 항목은 신 법리 소급).
      rows 는 이 경계에서 반드시 나뉜다. 콜러블에 넘기는 날짜 d 는 **근로제공일**을 뜻한다.
OW-M5 [불명확] (검증 '수정필요' 반영) 판시는 "제공한 연장근로 등"에 한정. 주휴·공휴일 유급수당, 연차휴가수당,
      퇴직금·해고예고수당의 기준일은 판결이 정하지 않음. 호출 모듈이 `allowance=` 를 넘기면
      `ow_nonwork_regime` 로 처리: by_date(기본 — 호출 모듈이 고른 날짜로 가름, 경고) |
      old_unless_parallel(서울중앙 2025가합10063 관찰 — 비병행이면 날짜와 무관하게 구 법리).
OW-03a [판례확립(소송물)·하급심(병행 범위)] (검증 '수정필요' 반영) 법정수당 청구별로 별개 소송물
      (대법원 2025. 8. 28. 선고 2021다239134). 병행 여부는 (수당, 청구묶음) 단위 `parallel_claims` 로 적는다.
      청구기간 확장분에 신 법리 적용: 대구고등법원 2025. 9. 10. 선고 2024나17329(확정), 서울중앙 2022가합537373.
      새 수당 항목 추가는 병행 아님: 서울중앙 2025가합10063. 항목의 `parallel` 은 '그 사건에서 통상임금 해당
      여부가 다투어진 항목'을 뜻한다. 판정: 청구묶음이 병행이 아니면 모든 항목 구 법리, 병행이면 `parallel`
      항목만 신 법리. `parallel_claims` 가 없으면 항목 플래그만으로 정한다(경고).
OW-19 [불명확] 2024. 12. 19.이 걸친 임금산정기간의 배분(월 합계 시간만 있을 때)은 시간 자료를 가진 호출 모듈
      (시간외수당)이 정한다. 이 모듈은 날짜 기준 콜러블만 준다.

---------------------------------------------------------------- 기준시간
OW-09 [법령] 시행령 제6조 제2항 — 1호 시간급 그대로, 2호 "일급 금액으로 정한 임금은 그 금액을 1일의 소정근로시간
      수로 나눈 금액", 3호 주급 ÷ 주 기준시간, 4호 "월급 금액으로 정한 임금은 그 금액을 월의 통상임금 산정 기준시간
      수(1주의 통상임금 산정 기준시간 수에 1년 동안의 평균 주의 수를 곱한 시간을 12로 나눈 시간)로 나눈 금액",
      5호 그 밖의 기간은 2~4호에 준함, 7호 "각각 산정된 금액을 합산한 금액". 제3항 일급 = 시간급 × 1일 소정근로시간.
OW-10 [법령·판례확립] 주 기준시간 H = 주 소정근로시간 + 주휴시간 + 약정 유급처리시간. 월 H_m = H × 평균 주 수 ÷ 12.
      2019다230899 "유급휴일에 근무한 것으로 의제하여 이를 소정근로시간과 합하여 총근로시간을 산정".
OW-11 [판례확립] 약정 유급처리시간 포함(2019다230899 "근로계약이나 취업규칙 등에 의하여 유급으로 처리하기로
      정해진 시간도 포함된다"). 토요일 무급 209 / 4시간 226 / 8시간 243(서울고등법원 2022나2018325 확정,
      2020다247190 원심 243 수긍).
OW-M1 [판례확립] (검증 '수정필요' 반영) 법정 통상임금에는 **법정 기준시간만** 쓴다. 대법원 2024. 2. 8. 선고
      2018다206899 "통상임금 여부는 근로기준법에 따르면서 시간급 통상임금의 산정기준이 되는 기준시간 수에 관하여는
      취업규칙, 단체협약에서 정한 바에 따르는 것은 … 허용되지 않는다". 약정 기준시간(183·220·240 등)은 `agreed:`
      절의 약정 항목과만 묶어 `agreed_hourly_of(d)` 로 따로 낸다. 법정·약정 수당의 전체 비교(OW-07)는 수당을
      계산하는 호출 모듈이 한다(2019다204876 "유리한 것만을 개별적으로 취사선택하여 … 허용되지 않는다").
      `hours[].monthly_hours` 는 법원이 확정한 **법정** 기준시간(예: 243, 행정해석 3436의 216)을 적는 칸이다.
OW-12 [판례확립] 기준근로시간 초과 약정근로의 고정수당: 분모에 약정 시간 수 자체를 더하고 가산율을 곱하지 않음
      (2015다73067 전원합의체 "가산율을 고려한 연장근로시간 수와 야간근로시간 수를 합산할 것은 아니다",
      "주휴수당에 정한 가산율을 고려할 것은 아니다"). 월급 분모 "(1주의 기본근로 40시간 + 주휴근로의제 8시간 +
      연장근로 22.5시간 + 연장 및 야간근로 2.5시간) × 365일 ÷ 12월 ÷ 7일", 일급 분모 "기본근로 8시간 +
      연장근로 4.5시간 + 연장 및 야간근로 0.5시간". 예외: 월 기본급에 제56조 연장근로수당이 포함된 항목
      (`includes_statutory_ot: true`)은 연장 × 1.5, 연장·야간 × 2.0 을 반영한 분모("가산율을 고려한 연장근로시간").
OW-13 [불명확] 평균 주 수·끝수 — `ow_weeks_per_year`: 365/7(기본, 2015다73067·서울고법 2022나2018325 산식) |
      52w+1day(행정해석 68201-1568 "[40시간 + 8시간] × 52주 + 8시간 ÷ 12월 ≒ 209시간"; 2019다230899의 226시간은
      취업규칙 산식의 사실 설시로 대법원 판시 아님, 추가 1일분은 1일 소정근로시간) | 52.14(안양 2017가단121258
      원고 주장). `ow_month_hours_rounding`: round_int(기본, 정수 반올림 209 — 행정해석·창원 2015나31876
      "소수점 이하 반올림") | floor_2dp(208.57 — 서울중앙 2024나77015 "소수점 둘째 자리 미만 버림") | none.
      365/7 산식은 H × 365 ÷ 84 로 한 번만 나눈다(나눗셈 순서에 따른 28자리 끝수 차이 방지).
OW-16 [법령·판례확립] 일급 ÷ 1일 소정근로시간(약정 연장시간이 있으면 OW-12 분모), 시급 그대로, 월 고정수당 ÷ 월 기준시간,
      합산. 주휴수당 차액은 시급·일급제만 가능(2019다204876).
OW-M2 [판례확립] (검증 '수정필요' 반영) 월급제는 달리 정하지 않는 한 주휴수당 차액 불가 — 2018다206899
      "월급제 근로자는 근로계약․단체협약 등에서 달리 정하지 않는 한 통상임금이 증액됨을 들어 주휴수당의 차액을
      청구할 수 없다". `result.weekly_holiday_diff_allowed` = wage_form ∈ {daily, hourly} 또는
      `weekly_holiday_diff_agreed: true`.
OW-17 [법령·불명확] (검증 '확인불가' 반영) 제18조 제3항 "15시간 미만인 근로자에 대하여는 제55조와 제60조를
      적용하지 아니한다" → 주 소정근로시간(4주 평균) < 15 이면 주휴시간 0(15.00 은 적용). 이 부분은 원문 확인.
      시행령 별표 2의 단시간 1일 소정근로시간 산식과 '주휴시간 = 1일 소정근로시간'은 원문 미확인이므로 기본값으로
      쓰지 않는다: `ow_part_time_daily_hours` input(기본) | annex2(4주 소정근로시간 ÷ 통상근로자 4주 소정근로일수),
      `ow_part_time_holiday_hours` input(기본, 단시간이면 weekly_holiday_hours 필수) | daily_hours.
OW-18 [불명확] 관공서 공휴일 유급휴일(제55조 제2항) 시간의 기준시간 산입 — 정면 판단 없음. 2020다247190 사안(단협상
      법정공휴일 유급인데 243 수긍)·서울중앙 2022가합537373(209 적용) 정황으로 기본 false.
      true 이면 `public_holiday_hours_per_year` ÷ 12 를 끝수처리 전 월 기준시간에 더한다.
OW-15 [행정해석] 1개월 초과 주기: 월 환산 = 1회 금액 × 연 지급횟수 ÷ 12 (분기 ÷3, 반기 ÷6, 연 ÷12, 격월 ÷2).
      근로기준정책과-3409 "[(10만원 + 10만원 + 10만원) / 12개월 / 209시간]". 연 3회처럼 주기와 횟수가 다르면
      `times_per_year`. 퍼센트형(기본급의 750%/년)은 `base_item`·`rate`(1회 금액 = 기준 항목 약정액 × rate).

---------------------------------------------------------------- 끝수
OW-14 [불명확] 통상시급 `ow_hourly_rounding`: none(기본, Decimal 유지) | floor(원 미만 버림 — 서울중앙 2019가단5120995
      "8,277원(= 1,730,000원 ÷ 209시간, 원 미만 버림)", 광주 2022가단6251) | half_up(창원 2015나31876 — 선원법 유급휴가급
      사안이고 상고심 원문 미열람이라 근거 무게 낮음). 1일 통상임금 `ow_daily_from_rounded_hourly`(기본 true —
      광주 2022가단6251 "200,952원(= 25,119원 × 8시간)") · `ow_daily_rounding` none(기본) | floor | half_up
      (서울중앙 2024나77015 1일 통상임금 122,740.57 → 122,740). 월 통상임금은 끝수처리하지 않는다.
      Decimal 나눗셈 오차는 소수 10자리 반올림 후 끝수처리.
      불일치: 2024나77015 의 퇴직금 4,923,051원은 각주 '원 미만 버림'과 달리 반올림값이라 끝수 근거에서 뺐다.
      2019가단5120995 는 24시간 격일제에 209시간을 다툼 없이 적용한 사안이라 끝수 관찰용으로만 썼다.

---------------------------------------------------------------- 구현하지 않은 것
OW-07 비교 자체, OW-M3(수당별·지급기일별 산정 단위), OW-19 배분은 수당을 계산하는 모듈의 일이다. 이 모듈은
      법정 통상시급과 약정 통상시급(`agreed_hourly_of`)을 따로 줄 뿐 섞지 않는다. 도급제(6호)는 받지 않는다.

---------------------------------------------------------------- 사건.yaml `ordinary:` 절
    ordinary:
      wage_form: monthly             # monthly | daily | hourly (필수)
      part_time: false               # 단시간근로자
      weekly_holiday_diff_agreed: false   # 월급제인데 주휴수당 차액을 달리 정한 경우(OW-M2)
      from: 2021-01-01               # 계산 기간(비우면 항목 기간에서)
      to: 2025-06-30                 # 끝이 열린 항목이 있으면 필수
      hours:                         # from 이후 적용(다음 from 전날까지). 첫 from 은 계산 시작일 이전
        - from: 2021-01-01
          weekly_hours: 40           # 주 소정근로시간(4주 평균)
          daily_hours: 8             # 1일 소정근로시간
          weekly_holiday_hours: null # 주휴시간(비우면 전일제는 daily_hours, 주 15시간 미만은 0)
          weekly_paid_hours: 4       # 약정 유급처리시간(토요일 4시간 등)
          weekly_overtime_hours: 0   # 기준근로시간 초과 약정 연장(OW-12, 가산율 곱하지 않은 시간)
          weekly_night_overtime_hours: 0
          daily_overtime_hours: 0    # 일급 분모용
          daily_night_overtime_hours: 0
          monthly_hours: null        # 법원이 확정한 법정 월 기준시간(있으면 산식 대신)
          public_holiday_hours_per_year: null   # ow_public_holidays_in_hours=true 일 때
          four_week_hours: null      # 단시간 annex2
          full_time_four_week_days: null
          source: "근로계약서 2쪽"
      items:
        - name: 기본급
          amount: 2000000            # 1회(주기당) 약정액. base_item·rate 로 대신할 수 있음
          cycle: month               # month | bimonth | quarter | half | year | week | day | hour (월/격월/분기/반기/연/주/일/시간)
          times_per_year: null       # 주기와 다른 연 지급횟수(연 3회 등)
          from: 2021-01-01           # 귀속기간
          to: null
          old: true                  # 구 법리: true(전액) | false(0) | 금액 | {included: true, amount: 500000}
          new: true                  # 신 법리
          parallel: false            # 병행사건에서 통상임금 해당 여부가 다투어진 항목
          includes_statutory_ot: false   # 제56조 연장수당이 포함된 월 기본급(OW-12 예외)
          cond_workdays_required: null   # 근무일수 조건(경고용)
          scheduled_workdays: null
          paid_in: null              # 지급 시점 메모(OW-M4)
          source: "취업규칙 12쪽, 급여명세서 2024-03"
        - {name: 정기상여금, base_item: 기본급, rate: 1.0, cycle: quarter, from: 2021-01-01, old: false, new: true,
           parallel: true, source: "단협 30조"}
      good_faith_excluded:           # 신의칙 인정 기간·항목(items 비우면 모든 항목)
        - {from: 2021-01-01, to: 2022-12-31, items: [정기상여금], note: "판결 3쪽"}
      parallel_claims:               # (수당, 청구묶음)별 병행사건 여부
        - {allowance: overtime, bundle: 최초, served: 2022-05-02, parallel: true}
        - {allowance: public_holiday, bundle: 2025확장, served: 2025-03-10, parallel: false}
      agreed:                        # 약정 통상임금(전체 비교용, 법정 계산과 섞지 않음)
        monthly_hours: 183
        daily_hours: 8
        items:
          - {name: 기본급, amount: 2000000, cycle: month, from: 2021-01-01}
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal, InvalidOperation

from .common import LaborError, OptionSpec, Trace, dec, parse_date, round_to

__all__ = [
    "ALLOWANCES", "BOUNDARY", "CYCLES", "NONWORK_ALLOWANCES", "OPTIONS", "RULES",
    "AgreedItem", "AgreedOrdinary", "GoodFaithExclusion", "HoursSpec", "Inclusion", "ItemShare",
    "OrdinaryInput", "OrdinaryResult", "OrdinaryRow", "ParallelClaim", "WageItem",
    "calculate_ordinary", "load_ordinary", "monthly_base_hours",
]

ZERO = Decimal(0)
ONE = Decimal(1)
BOUNDARY = date(2024, 12, 19)        # 2020다247190 선고일 — 이날 제공분부터 신 법리
PREMIUM_OT = Decimal("1.5")          # 제56조 제1항
PREMIUM_OT_NIGHT = Decimal("2.0")    # 제56조 제1항 + 제3항

# cycle -> (표시, 연 지급횟수 | None=시간 단위 환산)
CYCLES = {
    "month": ("월", 12), "bimonth": ("격월", 6), "quarter": ("분기", 4), "half": ("반기", 2), "year": ("연", 1),
    "week": ("주", None), "day": ("일", None), "hour": ("시간", None),
}
_CYCLE_ALIASES = {"월": "month", "격월": "bimonth", "분기": "quarter", "반기": "half", "연": "year", "년": "year",
                  "주": "week", "일": "day", "시간": "hour"}

WORK_ALLOWANCES = {
    "overtime": "연장근로수당", "night": "야간근로수당", "holiday_work": "휴일근로수당",
}
NONWORK_ALLOWANCES = {
    "weekly_holiday": "주휴수당", "public_holiday": "공휴일 유급휴일수당", "annual_leave": "연차휴가수당",
    "severance": "퇴직금(통상임금 하한)", "dismissal_notice": "해고예고수당", "dismissal_wage": "해고기간 임금",
    "other": "기타",
}
ALLOWANCES = {**WORK_ALLOWANCES, **NONWORK_ALLOWANCES}

OPTIONS: dict[str, OptionSpec] = {s.key: s for s in [
    OptionSpec("ow_weeks_per_year", "365/7", "1년 평균 주 수 산식", "OW-13", {
        "365/7": "H × 365 ÷ 7 ÷ 12 (2015다73067 월급 분모 산식, 서울고등법원 2022나2018325)",
        "52w+1day": "(H × 52 + 1일 소정근로시간) ÷ 12 (행정해석 68201-1568, 2019다230899 취업규칙 산식)",
        "52.14": "H × 52.14 ÷ 12 (수원지법 안양지원 2017가단121258 원고 주장)",
    }),
    OptionSpec("ow_month_hours_rounding", "round_int", "월 기준시간 끝수", "OW-13", {
        "round_int": "정수 반올림 209/226/243 (행정해석 68201-1568 '≒ 209', 창원 2015나31876 '소수점 이하 반올림')",
        "floor_2dp": "소수 둘째 자리 미만 버림 208.57 (서울중앙 2024나77015)",
        "none": "끝수처리 안 함 (208.5714…)",
    }),
    OptionSpec("ow_public_holidays_in_hours", False, "관공서 공휴일 유급시간을 월 기준시간에 가산", "OW-18", {
        False: "가산 안 함(정면 판단 없음, 2020다247190 사안 243 수긍·서울중앙 2022가합537373 209 정황)",
        True: "public_holiday_hours_per_year ÷ 12 가산(근거 확인 안 됨)",
    }),
    OptionSpec("ow_hourly_rounding", "none", "통상시급 원 미만 끝수", "OW-14", {
        "none": "Decimal 유지(최종 수당액에서 끝수)",
        "floor": "원 미만 버림 (서울중앙 2019가단5120995, 광주 2022가단6251)",
        "half_up": "원 미만 반올림 (창원 2015나31876 — 선원법 사안)",
    }),
    OptionSpec("ow_daily_from_rounded_hourly", True, "1일 통상임금을 끝수처리한 시급에 곱해 산정", "OW-14", {
        True: "끝수처리한 시급 × 1일 소정근로시간 (광주 2022가단6251 '25,119원 × 8시간')",
        False: "끝수처리 전 시급 × 1일 소정근로시간",
    }),
    OptionSpec("ow_daily_rounding", "none", "1일 통상임금 원 미만 끝수", "OW-14", {
        "none": "끝수처리 안 함",
        "floor": "원 미만 버림 (서울중앙 2024나77015 122,740원)",
        "half_up": "원 미만 반올림",
    }),
    OptionSpec("ow_part_time_daily_hours", "input", "단시간근로자 1일 소정근로시간", "OW-17", {
        "input": "입력한 daily_hours 사용(시행령 별표 2 원문 미확인)",
        "annex2": "4주 소정근로시간 ÷ 통상근로자 4주 총 소정근로일수(별표 2 제1호 나목 — 판결 인용으로만 확인)",
    }),
    OptionSpec("ow_part_time_holiday_hours", "input", "단시간근로자 주휴시간", "OW-17", {
        "input": "weekly_holiday_hours 입력 필수(원문 미확인)",
        "daily_hours": "1일 소정근로시간(조문 조합, 판례 확인 안 됨)",
    }),
    OptionSpec("ow_nonwork_regime", "by_date", "연장·야간·휴일근로 외 수당의 신·구 법리 기준", "OW-M5", {
        "by_date": "호출 모듈이 넘긴 날짜로 가름(판시 없음 — 경고)",
        "old_unless_parallel": "병행사건이 아니면 날짜와 무관하게 구 법리(서울중앙 2025가합10063 관찰)",
    }),
]}

RULES: dict[str, tuple[str, str]] = {
    "OW-01": ("새 통상임금 개념(소정근로 대가·정기·일률, 고정성 폐기), 근무일수 조건 ≤ 소정근로일수면 산입 — 사람 판정", "판례확립"),
    "OW-02": ("종전 개념(정기·일률·고정), 재직·근무일수 조건 임금 제외 — 사람 판정", "판례확립"),
    "OW-03": ("2024. 12. 19. 이후 제공분 신 법리, 12. 18.까지 구 법리(병행사건 소급) — 날짜로 구간 분할", "판례확립"),
    "OW-03a": ("병행사건 여부는 (수당, 청구묶음) 단위, 청구기간 확장분 병행 인정은 하급심", "판례확립·하급심"),
    "OW-04": ("항목별 구·신 법리 산입액 판정표(가족수당 신 법리 0 은 유추)", "판례확립"),
    "OW-05": ("약정액 기준, 실근무일수·실수령액 불반영", "판례확립"),
    "OW-06": ("주휴수당 등 법정수당 불산입, 주휴 포함 월급은 기준시간에 주휴 산입", "판례확립"),
    "OW-07": ("법정·약정 통상임금 전체 비교, 항목별 취사선택 금지 — 비교는 호출 모듈", "판례확립"),
    "OW-08": ("신의칙은 사람 입력(기간·항목 제외)", "판례확립"),
    "OW-09": ("시간급 환산(시행령 제6조 제2항 제1~5·7호, 제3항)", "법령"),
    "OW-10": ("주 기준시간 = 소정근로시간 + 주휴 + 약정 유급처리시간, 월 = 주 × 평균 주 수 ÷ 12", "법령·판례확립"),
    "OW-11": ("약정 유급처리시간 포함 209/226/243", "판례확립"),
    "OW-12": ("기준근로시간 초과 약정근로 고정수당 분모에 가산율 불고려(기본급에 법정 연장수당 포함 시 예외)", "판례확립"),
    "OW-13": ("평균 주 수 산식과 월 기준시간 끝수", "불명확"),
    "OW-14": ("통상시급·1일 통상임금 원 미만 끝수", "불명확"),
    "OW-15": ("1개월 초과 주기 금품 월 환산(연간 총액 ÷ 12)", "행정해석"),
    "OW-16": ("일급·시급제 형태별 환산 합산, 주휴수당 차액은 시급·일급제", "법령·판례확립"),
    "OW-17": ("주 15시간 미만 주휴 미적용(법령 확인), 단시간 1일 소정근로시간·주휴시간 산식(별표 2 원문 미확인)", "법령·불명확"),
    "OW-18": ("관공서 공휴일 유급시간의 기준시간 산입", "불명확"),
    "OW-19": ("2024. 12. 19.이 걸친 임금산정기간 배분 — 호출 모듈", "불명확"),
    "OW-M1": ("법정 통상임금 + 약정 기준시간 혼합 금지(2018다206899)", "판례확립"),
    "OW-M2": ("월급제 주휴수당 차액 불가(2018다206899)", "판례확립"),
    "OW-M3": ("법정수당 산정 단위는 수당별·지급기일별(2021다239134) — 호출 모듈", "판례확립"),
    "OW-M4": ("전년도 실적 성과급의 귀속기간(2018다206899) — from~to 를 귀속기간으로 입력", "판례확립"),
    "OW-M5": ("연장근로 외 수당의 신·구 법리 기준일", "불명확"),
}


# ================================================================ 입력
@dataclass
class Inclusion:
    """한 법리에서의 산입 판정. amount 가 None 이면 included 에 따라 약정액 전액 또는 0."""

    included: bool
    amount: Decimal | None = None


@dataclass
class WageItem:
    name: str
    cycle: str
    start: date
    end: date | None = None
    amount: Decimal | None = None
    base_item: str | None = None
    rate: Decimal | None = None
    times_per_year: Decimal | None = None
    old: Inclusion | None = None
    new: Inclusion | None = None
    parallel: bool = False
    includes_statutory_ot: bool = False
    cond_workdays_required: Decimal | None = None
    scheduled_workdays: Decimal | None = None
    paid_in: str = ""
    source: str = ""
    note: str = ""


@dataclass
class HoursSpec:
    start: date
    weekly_hours: Decimal | None = None
    daily_hours: Decimal | None = None
    weekly_holiday_hours: Decimal | None = None
    weekly_paid_hours: Decimal = ZERO
    weekly_overtime_hours: Decimal = ZERO
    weekly_night_overtime_hours: Decimal = ZERO
    daily_overtime_hours: Decimal = ZERO
    daily_night_overtime_hours: Decimal = ZERO
    monthly_hours: Decimal | None = None
    public_holiday_hours_per_year: Decimal | None = None
    four_week_hours: Decimal | None = None
    full_time_four_week_days: Decimal | None = None
    source: str = ""


@dataclass
class GoodFaithExclusion:
    start: date
    end: date
    items: list = field(default_factory=list)     # 비면 모든 항목
    note: str = ""


@dataclass
class ParallelClaim:
    allowance: str
    bundle: str
    parallel: bool
    served: date | None = None
    note: str = ""


@dataclass
class AgreedItem:
    name: str
    amount: Decimal
    cycle: str
    start: date
    end: date | None = None
    times_per_year: Decimal | None = None


@dataclass
class AgreedOrdinary:
    monthly_hours: Decimal
    daily_hours: Decimal | None = None
    items: list = field(default_factory=list)


@dataclass
class OrdinaryInput:
    wage_form: str
    items: list
    hours: list
    part_time: bool = False
    weekly_holiday_diff_agreed: bool = False
    start: date | None = None
    end: date | None = None
    good_faith_excluded: list = field(default_factory=list)
    parallel_claims: list = field(default_factory=list)
    agreed: AgreedOrdinary | None = None


# ================================================================ 결과
@dataclass
class ItemShare:
    """한 구간에서 한 항목이 통상임금에 들어간 몫."""

    name: str
    cycle: str
    regime: str                      # '구' | '신'
    contract_amount: Decimal         # 주기당 약정액
    included_amount: Decimal         # 주기당 산입액
    monthly_equivalent: Decimal | None   # 월 단위 이상 주기의 월 환산액(주·일·시간 단위는 None)
    hourly_part: Decimal             # 통상시급 기여분(끝수처리 전)
    good_faith_excluded: bool
    source: str


@dataclass
class OrdinaryRow:
    start: date
    end: date
    regime: str                      # 적용 법리 설명
    items: list                      # [ItemShare]
    monthly_sum: Decimal             # 월 단위 이상 주기 항목의 월 환산 합
    monthly_ordinary: Decimal        # monthly_sum + 주·일·시간 단위 항목 시급 × 월 기준시간
    weekly_base_hours: Decimal
    monthly_hours: Decimal
    hourly_raw: Decimal
    hourly: Decimal
    daily_hours: Decimal
    daily_ordinary: Decimal
    agreed_hourly: Decimal | None
    note: str


@dataclass
class _Hours:
    daily_hours: Decimal
    weekly_hours: Decimal
    holiday_hours: Decimal
    weekly_base: Decimal
    weekly_base_premium: Decimal
    monthly: Decimal
    monthly_premium: Decimal | None
    daily_denom: Decimal
    daily_denom_premium: Decimal
    notes: list


@dataclass
class _Seg:
    start: date
    end: date
    hours: _Hours
    items: list


@dataclass
class _Calc:
    shares: list
    monthly_sum: Decimal
    monthly_ordinary: Decimal
    hourly_raw: Decimal
    hourly: Decimal
    daily: Decimal


@dataclass
class OrdinaryResult:
    rows: list
    total: Decimal
    claims: list
    trace: list
    warnings: list
    wage_form: str = "monthly"
    weekly_holiday_diff_allowed: bool = False
    period_start: date | None = None
    period_end: date | None = None
    _segs: list = field(default_factory=list, repr=False)
    _engine: object = field(default=None, repr=False)

    def _seg_index(self, d) -> int:
        d = parse_date(d)
        if not self._segs or d < self.period_start or d > self.period_end:
            raise LaborError(f"통상임금: {_fmt(d)} 은(는) 계산 기간({_fmt(self.period_start)}~{_fmt(self.period_end)}) 밖입니다")
        return bisect_right([s.start for s in self._segs], d) - 1

    def _calc(self, d, allowance=None, bundle=None, regime=None) -> tuple[_Seg, _Calc]:
        i = self._seg_index(d)
        variant = self._engine.variant_for(parse_date(d), allowance, bundle, regime, self.warnings)
        return self._segs[i], self._engine.compute(i, variant)

    def hourly_of(self, d, allowance: str | None = None, bundle: str | None = None,
                  regime: str | None = None) -> Decimal:
        """d(근로제공일)가 속한 구간의 통상시급(ow_hourly_rounding 적용).

        allowance·bundle 을 넘기면 parallel_claims 로 병행 여부를 정한다(OW-03a).
        regime='old'|'new' 는 법리를 강제한다(판결 재현용).
        """
        return self._calc(d, allowance, bundle, regime)[1].hourly

    def hourly_raw_of(self, d, allowance=None, bundle=None, regime=None) -> Decimal:
        return self._calc(d, allowance, bundle, regime)[1].hourly_raw

    def daily_ordinary_of(self, d, allowance: str | None = None, bundle: str | None = None,
                          regime: str | None = None) -> Decimal:
        """통상시급 × 1일 소정근로시간(시행령 제6조 제3항, ow_daily_* 적용)."""
        return self._calc(d, allowance, bundle, regime)[1].daily

    def monthly_ordinary_of(self, d, allowance: str | None = None, bundle: str | None = None,
                            regime: str | None = None) -> Decimal:
        """월 통상임금(월 환산 합 + 주·일·시간 단위 항목 시급 × 월 기준시간, 끝수처리 없음)."""
        return self._calc(d, allowance, bundle, regime)[1].monthly_ordinary

    def monthly_hours_of(self, d) -> Decimal:
        return self._segs[self._seg_index(d)].hours.monthly

    def agreed_hourly_of(self, d) -> Decimal:
        """약정 통상시급(agreed 절 항목 ÷ 약정 기준시간). 법정 통상임금과 섞지 않는다(OW-M1)."""
        i = self._seg_index(d)
        v = self._engine.agreed_hourly(i)
        if v is None:
            raise LaborError("통상임금: 약정 통상임금(agreed 절)이 없습니다")
        return v


# ================================================================ 읽기
_ORD_KEYS = {"wage_form", "part_time", "weekly_holiday_diff_agreed", "from", "to", "hours", "items",
             "good_faith_excluded", "parallel_claims", "agreed"}
_ITEM_KEYS = {"name", "amount", "cycle", "times_per_year", "from", "to", "old", "new", "parallel", "base_item", "rate",
              "includes_statutory_ot", "cond_workdays_required", "scheduled_workdays", "paid_in", "source", "note"}
_HOURS_KEYS = {"from", "weekly_hours", "daily_hours", "weekly_holiday_hours", "weekly_paid_hours",
               "weekly_overtime_hours", "weekly_night_overtime_hours", "daily_overtime_hours",
               "daily_night_overtime_hours", "monthly_hours", "public_holiday_hours_per_year", "four_week_hours",
               "full_time_four_week_days", "source"}
_WAGE_FORMS = {"monthly": "월급제", "daily": "일급제", "hourly": "시급제"}
_WAGE_FORM_ALIASES = {"월급": "monthly", "월급제": "monthly", "일급": "daily", "일급제": "daily", "시급": "hourly", "시급제": "hourly"}


def _num(v, label: str, default=None) -> Decimal | None:
    if v is None or v == "":
        return default
    if isinstance(v, bool):
        raise LaborError(f"통상임금: {label} 은(는) 숫자여야 합니다: {v!r}")
    try:
        return dec(v)
    except (InvalidOperation, ValueError, TypeError):
        raise LaborError(f"통상임금: {label} 은(는) 숫자여야 합니다: {v!r}") from None


def _nonneg(v, label: str, default=None) -> Decimal | None:
    n = _num(v, label, default)
    if n is not None and n < 0:
        raise LaborError(f"통상임금: {label} 는 음수일 수 없습니다: {v!r}")
    return n


def _date(v, label: str) -> date | None:
    if v is None or v == "":
        return None
    try:
        return parse_date(v)
    except (ValueError, TypeError):
        raise LaborError(f"통상임금: {label} 날짜 형식이 올바르지 않습니다: {v!r}") from None


def _bool(v, label: str, default=False) -> bool:
    if v is None or v == "":
        return default
    if isinstance(v, bool):
        return v
    raise LaborError(f"통상임금: {label} 은(는) true/false 여야 합니다: {v!r}")


def _cycle(v, label: str) -> str:
    if v is None or v == "":
        raise LaborError(f"통상임금: {label}.cycle(지급주기)이 없습니다")
    c = _CYCLE_ALIASES.get(str(v).strip(), str(v).strip())
    if c not in CYCLES:
        raise LaborError(f"통상임금: {label}.cycle 값 {v!r} 을 알 수 없습니다. 가능: {', '.join(CYCLES)}")
    return c


def _inclusion(v, label: str) -> Inclusion | None:
    if v is None or v == "":
        return None
    if isinstance(v, bool):
        return Inclusion(v)
    if isinstance(v, dict):
        unknown = set(v) - {"included", "amount"}
        if unknown:
            raise LaborError(f"통상임금: {label} 에 알 수 없는 키: {', '.join(sorted(unknown))}")
        if "included" not in v:
            raise LaborError(f"통상임금: {label}.included(산입 여부)가 없습니다")
        inc = _bool(v["included"], f"{label}.included")
        amt = _nonneg(v.get("amount"), f"{label}.amount")
        if not inc and amt:
            raise LaborError(f"통상임금: {label} 는 included: false 인데 산입액 {amt} 이 적혀 있습니다")
        return Inclusion(inc, amt)
    amt = _nonneg(v, label)
    return Inclusion(amt > 0, amt)


def _load_item(raw, label: str) -> WageItem:
    if not isinstance(raw, dict):
        raise LaborError(f"통상임금: {label} 은(는) 사전이어야 합니다")
    unknown = set(raw) - _ITEM_KEYS
    if unknown:
        raise LaborError(f"통상임금: {label} 에 알 수 없는 키: {', '.join(sorted(unknown))}")
    name = str(raw.get("name") or "").strip()
    if not name:
        raise LaborError(f"통상임금: {label}.name(항목명)이 없습니다")
    label = f"{label}({name})"
    start = _date(raw.get("from"), f"{label}.from")
    if start is None:
        raise LaborError(f"통상임금: {label}.from(적용 시작일)이 없습니다")
    end = _date(raw.get("to"), f"{label}.to")
    if end is not None and end < start:
        raise LaborError(f"통상임금: {label} 의 to {end} 가 from {start} 보다 앞섭니다")
    it = WageItem(
        name=name, cycle=_cycle(raw.get("cycle"), label), start=start, end=end,
        amount=_nonneg(raw.get("amount"), f"{label}.amount"),
        base_item=(str(raw["base_item"]).strip() if raw.get("base_item") else None),
        rate=_nonneg(raw.get("rate"), f"{label}.rate"),
        times_per_year=_nonneg(raw.get("times_per_year"), f"{label}.times_per_year"),
        old=_inclusion(raw.get("old"), f"{label}.old"),
        new=_inclusion(raw.get("new"), f"{label}.new"),
        parallel=_bool(raw.get("parallel"), f"{label}.parallel"),
        includes_statutory_ot=_bool(raw.get("includes_statutory_ot"), f"{label}.includes_statutory_ot"),
        cond_workdays_required=_nonneg(raw.get("cond_workdays_required"), f"{label}.cond_workdays_required"),
        scheduled_workdays=_nonneg(raw.get("scheduled_workdays"), f"{label}.scheduled_workdays"),
        paid_in=str(raw.get("paid_in") or ""),
        source=str(raw.get("source") or ""),
        note=str(raw.get("note") or ""),
    )
    if (it.amount is None) == (it.base_item is None):
        raise LaborError(f"통상임금: {label} 에는 amount(약정액)와 base_item·rate 중 하나를 적어야 합니다")
    if it.base_item is not None and it.rate is None:
        raise LaborError(f"통상임금: {label} 에 base_item 을 적었으면 rate 가 필요합니다")
    if it.times_per_year is not None and CYCLES[it.cycle][1] is None:
        raise LaborError(f"통상임금: {label}.times_per_year 는 월 이상 주기(month~year)에만 적습니다")
    if it.times_per_year is not None and it.times_per_year == 0:
        raise LaborError(f"통상임금: {label}.times_per_year 는 0 일 수 없습니다")
    if it.includes_statutory_ot and it.cycle == "hour":
        raise LaborError(f"통상임금: {label} 시간급 항목에는 includes_statutory_ot 를 적지 않습니다")
    needs_old = it.start < BOUNDARY
    needs_new = it.end is None or it.end >= BOUNDARY or it.parallel
    if needs_old and it.old is None:
        raise LaborError(f"통상임금: {label} 는 2024. 12. 18. 이전 기간이 있어 구 법리 산입 여부(old)가 필요합니다")
    if needs_new and it.new is None:
        raise LaborError(f"통상임금: {label} 는 2024. 12. 19. 이후 기간이 있거나 병행 항목이어서 신 법리 산입 여부(new)가 필요합니다")
    return it


def _load_hours(raw, label: str) -> HoursSpec:
    if not isinstance(raw, dict):
        raise LaborError(f"통상임금: {label} 은(는) 사전이어야 합니다")
    unknown = set(raw) - _HOURS_KEYS
    if unknown:
        raise LaborError(f"통상임금: {label} 에 알 수 없는 키: {', '.join(sorted(unknown))}")
    start = _date(raw.get("from"), f"{label}.from")
    if start is None:
        raise LaborError(f"통상임금: {label}.from(적용 시작일)이 없습니다")
    h = HoursSpec(
        start=start,
        weekly_hours=_nonneg(raw.get("weekly_hours"), f"{label}.weekly_hours"),
        daily_hours=_nonneg(raw.get("daily_hours"), f"{label}.daily_hours"),
        weekly_holiday_hours=_nonneg(raw.get("weekly_holiday_hours"), f"{label}.weekly_holiday_hours"),
        weekly_paid_hours=_nonneg(raw.get("weekly_paid_hours"), f"{label}.weekly_paid_hours", ZERO),
        weekly_overtime_hours=_nonneg(raw.get("weekly_overtime_hours"), f"{label}.weekly_overtime_hours", ZERO),
        weekly_night_overtime_hours=_nonneg(raw.get("weekly_night_overtime_hours"), f"{label}.weekly_night_overtime_hours", ZERO),
        daily_overtime_hours=_nonneg(raw.get("daily_overtime_hours"), f"{label}.daily_overtime_hours", ZERO),
        daily_night_overtime_hours=_nonneg(raw.get("daily_night_overtime_hours"), f"{label}.daily_night_overtime_hours", ZERO),
        monthly_hours=_nonneg(raw.get("monthly_hours"), f"{label}.monthly_hours"),
        public_holiday_hours_per_year=_nonneg(raw.get("public_holiday_hours_per_year"), f"{label}.public_holiday_hours_per_year"),
        four_week_hours=_nonneg(raw.get("four_week_hours"), f"{label}.four_week_hours"),
        full_time_four_week_days=_nonneg(raw.get("full_time_four_week_days"), f"{label}.full_time_four_week_days"),
        source=str(raw.get("source") or ""),
    )
    if h.monthly_hours is not None and h.monthly_hours == 0:
        raise LaborError(f"통상임금: {label}.monthly_hours 는 0 일 수 없습니다")
    return h


def load_ordinary(raw: dict, worker: dict | None = None) -> OrdinaryInput:
    """사건.yaml `ordinary:` 절(dict)을 읽는다. worker 절은 쓰지 않는다(인터페이스 통일용)."""
    raw = dict(raw or {})
    unknown = set(raw) - _ORD_KEYS
    if unknown:
        raise LaborError(f"통상임금: ordinary 절에 알 수 없는 키: {', '.join(sorted(unknown))}")
    wf = raw.get("wage_form")
    if wf in (None, ""):
        raise LaborError("통상임금: 임금형태(wage_form: monthly | daily | hourly)가 없습니다")
    wf = _WAGE_FORM_ALIASES.get(str(wf).strip(), str(wf).strip())
    if wf not in _WAGE_FORMS:
        raise LaborError(f"통상임금: wage_form 값 {raw.get('wage_form')!r} 을 알 수 없습니다. 가능: monthly, daily, hourly")

    items_raw = raw.get("items")
    if not items_raw:
        raise LaborError("통상임금: 임금 항목 판정표(items)가 없습니다")
    items = [_load_item(x, f"items[{i}]") for i, x in enumerate(items_raw, 1)]
    names = [it.name for it in items]
    for it in items:
        if it.base_item is not None:
            if it.base_item == it.name:
                raise LaborError(f"통상임금: 항목 {it.name} 의 base_item 이 자기 자신입니다")
            if it.base_item not in names:
                raise LaborError(f"통상임금: 항목 {it.name} 의 base_item {it.base_item!r} 이 판정표에 없습니다")

    hours_raw = raw.get("hours")
    if not hours_raw:
        raise LaborError("통상임금: 근로시간(hours: weekly_hours·daily_hours)이 없습니다")
    if isinstance(hours_raw, dict):
        hours_raw = [hours_raw]
    hours = sorted((_load_hours(x, f"hours[{i}]") for i, x in enumerate(hours_raw, 1)), key=lambda h: h.start)
    if len({h.start for h in hours}) != len(hours):
        raise LaborError("통상임금: hours 에 같은 from 이 두 번 있습니다")

    gf = []
    for i, x in enumerate(raw.get("good_faith_excluded") or [], 1):
        if not isinstance(x, dict):
            raise LaborError(f"통상임금: good_faith_excluded[{i}] 는 사전이어야 합니다")
        s, e = _date(x.get("from"), f"good_faith_excluded[{i}].from"), _date(x.get("to"), f"good_faith_excluded[{i}].to")
        if s is None or e is None:
            raise LaborError(f"통상임금: good_faith_excluded[{i}] 에는 from 과 to 가 모두 필요합니다")
        if e < s:
            raise LaborError(f"통상임금: good_faith_excluded[{i}] 의 to 가 from 보다 앞섭니다")
        its = [str(n) for n in (x.get("items") or [])]
        for n in its:
            if n not in names:
                raise LaborError(f"통상임금: good_faith_excluded[{i}] 의 항목 {n!r} 이 판정표에 없습니다")
        gf.append(GoodFaithExclusion(s, e, its, str(x.get("note") or "")))

    pcs = []
    for i, x in enumerate(raw.get("parallel_claims") or [], 1):
        if not isinstance(x, dict):
            raise LaborError(f"통상임금: parallel_claims[{i}] 는 사전이어야 합니다")
        al = x.get("allowance")
        if al not in ALLOWANCES:
            raise LaborError(f"통상임금: parallel_claims[{i}].allowance 값 {al!r} 을 알 수 없습니다. 가능: {', '.join(ALLOWANCES)}")
        if "parallel" not in x:
            raise LaborError(f"통상임금: parallel_claims[{i}].parallel(병행사건 여부)이 없습니다")
        pc = ParallelClaim(al, str(x.get("bundle") or ""), _bool(x["parallel"], f"parallel_claims[{i}].parallel"),
                           _date(x.get("served"), f"parallel_claims[{i}].served"), str(x.get("note") or ""))
        if any(p.allowance == pc.allowance and p.bundle == pc.bundle for p in pcs):
            raise LaborError(f"통상임금: parallel_claims 에 ({pc.allowance}, {pc.bundle!r}) 가 두 번 있습니다")
        pcs.append(pc)

    agreed = None
    ag = raw.get("agreed")
    if ag:
        if not isinstance(ag, dict):
            raise LaborError("통상임금: agreed 는 사전이어야 합니다")
        mh = _nonneg(ag.get("monthly_hours"), "agreed.monthly_hours")
        if not mh:
            raise LaborError("통상임금: agreed.monthly_hours(약정 월 기준시간)가 없습니다")
        a_items = []
        for i, x in enumerate(ag.get("items") or [], 1):
            lb = f"agreed.items[{i}]"
            if not isinstance(x, dict) or not x.get("name") or x.get("amount") in (None, ""):
                raise LaborError(f"통상임금: {lb} 에는 name 과 amount 가 필요합니다")
            s = _date(x.get("from"), f"{lb}.from")
            if s is None:
                raise LaborError(f"통상임금: {lb}.from 이 없습니다")
            c = _cycle(x.get("cycle"), lb)
            if c == "week":
                raise LaborError(f"통상임금: {lb} 약정 통상임금에는 주 단위 항목을 받지 않습니다")
            a_items.append(AgreedItem(str(x["name"]), _nonneg(x["amount"], f"{lb}.amount"), c, s,
                                      _date(x.get("to"), f"{lb}.to"), _nonneg(x.get("times_per_year"), f"{lb}.times_per_year")))
        if not a_items:
            raise LaborError("통상임금: agreed.items(약정 통상임금 항목)가 없습니다")
        agreed = AgreedOrdinary(mh, _nonneg(ag.get("daily_hours"), "agreed.daily_hours"), a_items)

    start = _date(raw.get("from"), "from")
    end = _date(raw.get("to"), "to")
    return OrdinaryInput(
        wage_form=wf, items=items, hours=hours,
        part_time=_bool(raw.get("part_time"), "part_time"),
        weekly_holiday_diff_agreed=_bool(raw.get("weekly_holiday_diff_agreed"), "weekly_holiday_diff_agreed"),
        start=start, end=end, good_faith_excluded=gf, parallel_claims=pcs, agreed=agreed,
    )


# ================================================================ 헬퍼
def _fmt(d: date | None) -> str:
    return "" if d is None else f"{d.year}. {d.month}. {d.day}."


def _settle(x: Decimal) -> Decimal:
    """Decimal 나눗셈의 순환소수 오차 보정(소수 10자리 반올림). 끝수처리 직전에만 쓴다."""
    return x.quantize(Decimal("1e-10"), rounding=ROUND_HALF_UP)


def _round_won(x: Decimal, mode: str) -> Decimal:
    return x if mode == "none" else round_to(_settle(x), 0, mode)


def monthly_base_hours(weekly_base: Decimal, daily_hours: Decimal, weeks: str = "365/7", rounding: str = "round_int",
                       public_holiday_hours_per_year: Decimal | None = None) -> Decimal:
    """주 기준시간 → 월 기준시간(OW-10·13·18). 공휴일 시간은 끝수처리 전에 더한다."""
    H = Decimal(weekly_base)
    if weeks == "365/7":
        m = H * 365 / 84
    elif weeks == "52w+1day":
        m = (H * 52 + Decimal(daily_hours)) / 12
    elif weeks == "52.14":
        m = H * Decimal("52.14") / 12
    else:
        raise LaborError(f"통상임금: 평균 주 수 산식 {weeks!r} 을 알 수 없습니다")
    if public_holiday_hours_per_year:
        m += Decimal(public_holiday_hours_per_year) / 12
    if rounding == "round_int":
        return _settle(m).quantize(ONE, rounding=ROUND_HALF_UP)
    if rounding == "floor_2dp":
        return _settle(m).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
    if rounding == "none":
        return m
    raise LaborError(f"통상임금: 월 기준시간 끝수 {rounding!r} 을 알 수 없습니다")


def _read_options(opts: dict | None) -> dict:
    opts = opts or {}
    out = {}
    for key, spec in OPTIONS.items():
        v = opts.get(key, spec.default)
        if spec.choices and v not in spec.choices:
            raise LaborError(f"옵션 {key} 의 값 {v!r} 은 허용되지 않습니다. 가능: {', '.join(map(str, spec.choices))}")
        out[key] = v
    return out


def _active(start: date, end: date | None, d: date) -> bool:
    return start <= d and (end is None or d <= end)


# ================================================================ 계산
class _Engine:
    """구간별 계산을 법리 변형(old/new/flags)마다 한 번씩만 하고 기억한다."""

    def __init__(self, inp: OrdinaryInput, o: dict, segs: list):
        self.inp, self.o, self.segs = inp, o, segs
        self.cache: dict = {}
        self.claims = {(p.allowance, p.bundle): p for p in inp.parallel_claims}
        self.claim_allowances = {p.allowance for p in inp.parallel_claims}

    # ---------------------------------------------------------- 법리 선택
    def variant_for(self, d: date, allowance, bundle, regime, warnings: list) -> str:
        if regime is not None:
            if regime not in ("old", "new"):
                raise LaborError(f"통상임금: regime 은 'old' 또는 'new' 여야 합니다: {regime!r}")
            return regime
        claim_parallel = None
        nonwork = False
        if allowance is not None:
            if allowance not in ALLOWANCES:
                raise LaborError(f"통상임금: 수당 종류 {allowance!r} 을 알 수 없습니다. 가능: {', '.join(ALLOWANCES)}")
            nonwork = allowance in NONWORK_ALLOWANCES
            if allowance in self.claim_allowances:
                key = (allowance, "" if bundle is None else str(bundle))
                if key not in self.claims:
                    have = ", ".join(repr(b) for (a, b) in self.claims if a == allowance)
                    raise LaborError(f"통상임금: parallel_claims 에 ({allowance}, {key[1]!r}) 가 없습니다. 적힌 청구묶음: {have}")
                claim_parallel = self.claims[key].parallel
        if nonwork and self.o["ow_nonwork_regime"] == "old_unless_parallel":
            return "old" if claim_parallel is False else "flags"
        if nonwork and d >= BOUNDARY:
            msg = (f"OW-M5: {ALLOWANCES[allowance]}의 신·구 법리 기준일은 판시가 없습니다 — 호출 모듈이 넘긴 날짜 기준"
                   "(ow_nonwork_regime=by_date)으로 가렸습니다")
            if msg not in warnings:
                warnings.append(msg)
        if d >= BOUNDARY:
            return "new"
        if claim_parallel is False:
            return "old"
        return "flags"

    # ---------------------------------------------------------- 금액
    def _contract_amount(self, it: WageItem, d: date) -> Decimal:
        if it.amount is not None:
            return it.amount
        bases = [b for b in self.inp.items if b.name == it.base_item and _active(b.start, b.end, d)]
        if not bases:
            raise LaborError(f"통상임금: {_fmt(d)} 에 항목 {it.name} 의 기준 항목 {it.base_item} 이 적용되지 않습니다")
        if len(bases) > 1:
            raise LaborError(f"통상임금: {_fmt(d)} 에 기준 항목 {it.base_item} 이 둘 이상 겹칩니다")
        base = bases[0]
        if base.amount is None:
            raise LaborError(f"통상임금: 기준 항목 {base.name} 도 base_item 으로 정해져 있습니다(한 단계만 허용)")
        return base.amount * it.rate

    def _excluded(self, it: WageItem, seg: _Seg) -> bool:
        return any(g.start <= seg.start and seg.end <= g.end and (not g.items or it.name in g.items)
                   for g in self.inp.good_faith_excluded)

    def compute(self, i: int, variant: str) -> _Calc:
        key = (i, variant)
        if key in self.cache:
            return self.cache[key]
        seg = self.segs[i]
        h = seg.hours
        o = self.o
        shares = []
        monthly_sum = ZERO
        other_hourly = ZERO
        raw = ZERO
        for it in seg.items:
            use_new = variant == "new" or (variant == "flags" and it.parallel)
            inc = it.new if use_new else it.old
            lab = "신" if use_new else "구"
            if inc is None:
                raise LaborError(f"통상임금: 항목 {it.name} 의 {lab} 법리 산입 여부({'new' if use_new else 'old'})가 없어 "
                                 f"{_fmt(seg.start)}~{_fmt(seg.end)} 을(를) 계산할 수 없습니다")
            contract = self._contract_amount(it, seg.start)
            included = inc.amount if inc.amount is not None else (contract if inc.included else ZERO)
            gf = self._excluded(it, seg)
            if gf:
                included = ZERO
            per_year = CYCLES[it.cycle][1]
            meq = None
            if per_year is not None:
                times = it.times_per_year if it.times_per_year is not None else Decimal(per_year)
                meq = included * times / 12
                denom = h.monthly_premium if it.includes_statutory_ot else h.monthly
                if denom is None:
                    raise LaborError("통상임금: 법정 연장수당 포함 항목(includes_statutory_ot)에는 monthly_hours 직접 입력을 함께 쓸 수 없습니다")
                part = meq / denom
                monthly_sum += meq
            elif it.cycle == "week":
                part = included / (h.weekly_base_premium if it.includes_statutory_ot else h.weekly_base)
                other_hourly += part
            elif it.cycle == "day":
                part = included / (h.daily_denom_premium if it.includes_statutory_ot else h.daily_denom)
                other_hourly += part
            else:
                part = included
                other_hourly += part
            raw += part
            shares.append(ItemShare(it.name, CYCLES[it.cycle][0], lab, contract, included, meq, part, gf, it.source))
        hourly = _round_won(raw, o["ow_hourly_rounding"])
        base = hourly if o["ow_daily_from_rounded_hourly"] else raw
        daily = _round_won(base * h.daily_hours, o["ow_daily_rounding"])
        calc = _Calc(shares, monthly_sum, monthly_sum + other_hourly * h.monthly, raw, hourly, daily)
        self.cache[key] = calc
        return calc

    def agreed_hourly(self, i: int) -> Decimal | None:
        ag = self.inp.agreed
        if ag is None:
            return None
        seg = self.segs[i]
        total = ZERO
        for it in ag.items:
            if not _active(it.start, it.end, seg.start):
                continue
            per_year = CYCLES[it.cycle][1]
            if per_year is not None:
                times = it.times_per_year if it.times_per_year is not None else Decimal(per_year)
                total += it.amount * times / 12 / ag.monthly_hours
            elif it.cycle == "day":
                total += it.amount / (ag.daily_hours or seg.hours.daily_hours)
            else:
                total += it.amount
        return total


def _resolve_hours(spec: HoursSpec, inp: OrdinaryInput, o: dict, needs_premium: bool, trace: list,
                   warnings: list, label: str) -> _Hours:
    notes = []
    wh, dh = spec.weekly_hours, spec.daily_hours
    if inp.part_time and o["ow_part_time_daily_hours"] == "annex2":
        if not spec.four_week_hours or not spec.full_time_four_week_days:
            raise LaborError(f"통상임금: {label} ow_part_time_daily_hours=annex2 이면 four_week_hours 와 "
                             "full_time_four_week_days 가 필요합니다")
        dh = spec.four_week_hours / spec.full_time_four_week_days
        wh = spec.four_week_hours / 4
        notes.append(f"1일 소정근로시간 {dh} = 4주 {spec.four_week_hours}시간 ÷ 통상근로자 {spec.full_time_four_week_days}일(별표 2, 원문 미확인)")
    if wh is None or wh == 0:
        raise LaborError(f"통상임금: {label}.weekly_hours(주 소정근로시간)가 없습니다")
    if dh is None or dh == 0:
        raise LaborError(f"통상임금: {label}.daily_hours(1일 소정근로시간)가 없습니다")

    if wh < 15:
        holiday = ZERO
        if spec.weekly_holiday_hours:
            warnings.append(f"{label}: 주 소정근로시간 {wh}시간(15시간 미만)이라 입력한 주휴시간 {spec.weekly_holiday_hours}을 "
                            "0으로 두었습니다(제18조 제3항). 약정 유급이면 weekly_paid_hours 에 적으십시오")
        notes.append("주 15시간 미만 — 주휴 미적용(제18조 제3항)")
    elif spec.weekly_holiday_hours is not None:
        holiday = spec.weekly_holiday_hours
    elif inp.part_time:
        if o["ow_part_time_holiday_hours"] != "daily_hours":
            raise LaborError(f"통상임금: {label} 단시간근로자는 주휴시간(weekly_holiday_hours)을 적어야 합니다"
                             "(별표 2 원문 미확인 — 또는 옵션 ow_part_time_holiday_hours=daily_hours)")
        holiday = dh
        notes.append(f"주휴시간 = 1일 소정근로시간 {dh}(ow_part_time_holiday_hours=daily_hours, 조문 조합)")
    else:
        holiday = dh
        notes.append(f"주휴시간 = 1일 소정근로시간 {dh}")

    extra = spec.weekly_overtime_hours + spec.weekly_night_overtime_hours
    extra_p = spec.weekly_overtime_hours * PREMIUM_OT + spec.weekly_night_overtime_hours * PREMIUM_OT_NIGHT
    H = wh + extra + holiday + spec.weekly_paid_hours
    Hp = wh + extra_p + holiday + spec.weekly_paid_hours
    if extra:
        notes.append(f"약정 연장 {extra}시간을 가산율 없이 분모에 합산(OW-12)")

    phh = None
    if o["ow_public_holidays_in_hours"]:
        if spec.public_holiday_hours_per_year is None:
            raise LaborError(f"통상임금: {label} ow_public_holidays_in_hours=true 이면 public_holiday_hours_per_year 가 필요합니다")
        phh = spec.public_holiday_hours_per_year
        notes.append(f"공휴일 유급 {phh}시간 ÷ 12 가산(OW-18, 근거 확인 안 됨)")
    elif spec.public_holiday_hours_per_year:
        warnings.append(f"{label}: public_holiday_hours_per_year 를 적었으나 ow_public_holidays_in_hours=false 라 쓰지 않았습니다")

    if spec.monthly_hours is not None:
        monthly = spec.monthly_hours
        monthly_p = None if needs_premium and extra_p != extra else monthly
        notes.append(f"월 기준시간 {monthly} 직접 입력(법정 기준시간으로 확정된 값이어야 함 — OW-M1)")
        warnings.append(f"{label}: 월 기준시간 {monthly}을 직접 입력했습니다. 취업규칙·단협의 약정 기준시간이 아니라 "
                        "법정 기준시간(소정근로시간 + 유급처리시간)이어야 합니다(2018다206899)")
    else:
        w, r = o["ow_weeks_per_year"], o["ow_month_hours_rounding"]
        monthly = monthly_base_hours(H, dh, w, r, phh)
        monthly_p = monthly_base_hours(Hp, dh, w, r, phh) if Hp != H else monthly
    return _Hours(dh, wh, holiday, H, Hp, monthly, monthly_p,
                  dh + spec.daily_overtime_hours + spec.daily_night_overtime_hours,
                  dh + spec.daily_overtime_hours * PREMIUM_OT + spec.daily_night_overtime_hours * PREMIUM_OT_NIGHT,
                  notes)


def calculate_ordinary(inp: OrdinaryInput, opts: dict, **deps) -> OrdinaryResult:
    o = _read_options(opts)
    trace: list[Trace] = []
    warnings: list[str] = []
    for key, spec in OPTIONS.items():
        v = o[key]
        trace.append(Trace(spec.rule, f"옵션 {key}", str(v), spec.choices.get(v, spec.description)))

    # ---------------------------------------------------------- 계산 기간
    start = inp.start or min(it.start for it in inp.items)
    if inp.end is not None:
        end = inp.end
    elif any(it.end is None for it in inp.items):
        raise LaborError("통상임금: 끝이 열린 항목이 있어 계산 기간 끝(ordinary.to)이 필요합니다")
    else:
        end = max(it.end for it in inp.items)
    if end < start:
        raise LaborError(f"통상임금: 계산 기간 끝 {end} 이 시작 {start} 보다 앞섭니다")
    if inp.hours[0].start > start:
        raise LaborError(f"통상임금: 근로시간(hours) 첫 from {inp.hours[0].start} 이 계산 시작일 {start} 보다 늦습니다")

    # ---------------------------------------------------------- 구간 분할
    points = {start, BOUNDARY}
    for it in inp.items:
        points.add(it.start)
        if it.end is not None:
            points.add(it.end + timedelta(days=1))
    for h in inp.hours:
        points.add(h.start)
    for g in inp.good_faith_excluded:
        points.update((g.start, g.end + timedelta(days=1)))
    if inp.agreed is not None:
        for a in inp.agreed.items:
            points.add(a.start)
            if a.end is not None:
                points.add(a.end + timedelta(days=1))
    cuts = sorted(p for p in points if start <= p <= end)
    trace.append(Trace("OW-03", "법리 경계", _fmt(BOUNDARY), "이날 제공분부터 신 법리, 전날까지 구 법리(병행 항목은 신 법리 소급)"))

    needs_premium = any(it.includes_statutory_ot for it in inp.items)
    hours_cache: dict = {}
    segs = []
    for k, s in enumerate(cuts):
        e = cuts[k + 1] - timedelta(days=1) if k + 1 < len(cuts) else end
        hi = max(j for j, h in enumerate(inp.hours) if h.start <= s)
        if hi not in hours_cache:
            hours_cache[hi] = _resolve_hours(inp.hours[hi], inp, o, needs_premium, trace, warnings, f"hours[{hi + 1}]")
        active = [it for it in inp.items if _active(it.start, it.end, s)]
        if not active:
            warnings.append(f"{_fmt(s)}~{_fmt(e)}: 적용되는 임금 항목이 없어 통상임금이 0 입니다")
        segs.append(_Seg(s, e, hours_cache[hi], active))
    for g in inp.good_faith_excluded:
        if g.start < start or g.end > end:
            warnings.append(f"신의칙 제외 기간 {_fmt(g.start)}~{_fmt(g.end)} 이 계산 기간을 벗어난 부분은 쓰지 않았습니다")

    engine = _Engine(inp, o, segs)

    # ---------------------------------------------------------- 행
    rows = []
    for i, seg in enumerate(segs):
        variant = "flags" if seg.start < BOUNDARY else "new"
        c = engine.compute(i, variant)
        if seg.start >= BOUNDARY:
            regime = "신 법리(2020다247190)"
        else:
            par = [it.name for it in seg.items if it.parallel]
            regime = "구 법리(2012다89399)" + (f" — 병행 항목 신 법리 소급: {', '.join(par)}" if par else "")
        notes = list(seg.hours.notes)
        notes += [f"{it.name} 지급 {it.paid_in}" for it in seg.items if it.paid_in]
        notes += [f"{sh.name} 신의칙 제외" for sh in c.shares if sh.good_faith_excluded]
        rows.append(OrdinaryRow(
            start=seg.start, end=seg.end, regime=regime, items=c.shares, monthly_sum=c.monthly_sum,
            monthly_ordinary=c.monthly_ordinary, weekly_base_hours=seg.hours.weekly_base,
            monthly_hours=seg.hours.monthly, hourly_raw=c.hourly_raw, hourly=c.hourly,
            daily_hours=seg.hours.daily_hours, daily_ordinary=c.daily,
            agreed_hourly=engine.agreed_hourly(i), note="; ".join(notes)))

    # ---------------------------------------------------------- 근거·경고
    diff_allowed = inp.wage_form in ("daily", "hourly") or inp.weekly_holiday_diff_agreed
    trace.append(Trace("OW-M2", "주휴수당 차액 산정 가능", "예" if diff_allowed else "아니오",
                       f"{_WAGE_FORMS[inp.wage_form]}" + (" — 달리 정함 입력" if inp.weekly_holiday_diff_agreed else "")
                       + " (2019다204876, 2018다206899)"))
    trace.append(Trace("OW-06", "법정수당 불산입", "판정표 입력 그대로", "주휴 포함 월급은 기준시간에 주휴 산입"))
    trace.append(Trace("OW-M1", "법정 기준시간", "법정 산식(hours)", "약정 기준시간은 agreed 절에서만 사용"))
    if inp.agreed is not None:
        trace.append(Trace("OW-07", "약정 통상시급", f"약정 기준시간 {inp.agreed.monthly_hours}",
                           "법정·약정 수당 전체 비교는 수당 계산 모듈이 함(항목별 취사선택 금지)"))

    for it in inp.items:
        if not it.source:
            warnings.append(f"항목 {it.name}: 판정 근거(source, 파일·쪽)가 없습니다")
        if it.old is not None and it.new is not None:
            old_in = it.old.included or bool(it.old.amount)
            new_in = it.new.included or bool(it.new.amount)
            if old_in and not new_in:
                warnings.append(f"항목 {it.name}: 구 법리 산입인데 신 법리 제외로 적혀 있습니다 — 판정을 확인하십시오(OW-01·02)")
        if it.cond_workdays_required is not None and it.scheduled_workdays is not None and it.new is not None:
            new_in = it.new.included or bool(it.new.amount)
            if it.cond_workdays_required <= it.scheduled_workdays and not new_in:
                warnings.append(f"항목 {it.name}: 요구 근무일수 {it.cond_workdays_required}일 ≤ 소정근로일수 {it.scheduled_workdays}일인데 "
                                "신 법리 제외로 적혀 있습니다(2023다302838 '소정근로일수 이내'면 산입)")
            if it.cond_workdays_required > it.scheduled_workdays and new_in:
                warnings.append(f"항목 {it.name}: 요구 근무일수 {it.cond_workdays_required}일 > 소정근로일수 {it.scheduled_workdays}일인데 "
                                "신 법리 산입으로 적혀 있습니다(2023다302838 '추가 근로의 대가이므로 통상임금이 아니다')")
        if it.includes_statutory_ot:
            trace.append(Trace("OW-12", f"{it.name} 분모", "가산율 반영 총근로시간", "월 기본급에 제56조 연장근로수당 포함(2015다73067)"))

    if start < BOUNDARY and any(it.parallel for it in inp.items) and not inp.parallel_claims:
        warnings.append("OW-03a: 병행사건 여부를 항목 단위로만 적었습니다. 법정수당 청구별로 소송물이 다르므로(2021다239134) "
                        "수당·청구묶음별 parallel_claims 입력을 권합니다(청구기간 확장·새 수당 추가의 병행 여부는 하급심만 있음)")
    if any(p.parallel for p in inp.parallel_claims) and not any(it.parallel for it in inp.items):
        warnings.append("OW-03a: 병행사건 청구묶음이 있으나 parallel 로 표시한 항목이 없어 구 법리와 같게 계산됩니다")
    regime_matters = any(it.old is not None and it.new is not None and (it.old.included, it.old.amount) != (it.new.included, it.new.amount)
                         for it in inp.items)
    if regime_matters and start < BOUNDARY <= end:
        warnings.append("OW-M5: 연장·야간·휴일근로 외 수당(주휴·공휴일·연차·퇴직금·해고예고)의 신·구 법리 기준일은 판시가 없습니다"
                        f" — ow_nonwork_regime={o['ow_nonwork_regime']}")
    if o["ow_public_holidays_in_hours"]:
        warnings.append("OW-18: 관공서 공휴일 유급시간을 월 기준시간에 더했습니다(근거 확인 안 됨)")
    if inp.part_time:
        warnings.append("OW-17: 단시간근로자 1일 소정근로시간·주휴시간 산식(시행령 별표 2)은 원문을 확인하지 못했습니다")
    if o["ow_month_hours_rounding"] != "none" or o["ow_hourly_rounding"] != "none":
        trace.append(Trace("OW-13", "끝수", f"기준시간 {o['ow_month_hours_rounding']} / 시급 {o['ow_hourly_rounding']}",
                           "대법원 판시 없음 — 재현 대상 판결 방식으로 옵션 지정"))

    return OrdinaryResult(rows=rows, total=ZERO, claims=[], trace=trace, warnings=warnings,
                          wage_form=inp.wage_form, weekly_holiday_diff_allowed=diff_allowed,
                          period_start=start, period_end=end, _segs=segs, _engine=engine)
