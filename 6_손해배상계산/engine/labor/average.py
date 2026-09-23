"""1일 평균임금 산정 (lane: average_wage_severance, 규칙 AW-01~AW-14, MR-4).

사람이 사건.yaml `average_wage:` 절에 적은 산정사유 발생일(또는 마지막 근무일), 임금산정기간별 임금 항목,
상여금·연차수당 지급 내역, 시행령 제2조 제외기간으로 1일 평균임금을 낸다. 통상임금 하한(제2조 제2항)은
deps `daily_ordinary_of(d)` 와 비교한다. 시간외수당 재산정 등으로 늘어난 월별 임금은 deps `extra_wages`
('YYYY-MM' → Decimal, 임금산정기간이 시작하는 달)로 받는다.
법적 판단(임금성, 쟁의행위 적법성, 현저히 부적당한지 등)은 하지 않는다. 사람이 판정해 입력한 값으로 계산만 한다.
이 모듈은 청구 금액을 만들지 않는다(total 0, claims []). 결과 `average_daily_wage` 를 퇴직금·해고기간 임금
모듈이 받는다. 기대값은 판결 원문 숫자로 검증했다(tests/test_labor_average.py).

---------------------------------------------------------------- 기본 산식·산정기간
AW-01 [법령] 1일 평균임금 = 산정기간 임금총액 ÷ 산정기간 총일수(역일, 89~92일. 30일·365일 아님).
      근로기준법 제2조 제1항 제6호 "이를 산정하여야 할 사유가 발생한 날 이전 3개월 동안에 그 근로자에게
      지급된 임금의 총액을 그 기간의 총일수로 나눈 금액". 고용노동부 임금 68207-564 "월의 대소에 따라 89~92일".
AW-02 [판례확립(초일 불산입)·실무관행(발생일 = 마지막 근무일 + 1일)]
      산정사유 발생일 O 는 넣지 않고 O − 1일부터 역일로 3개월 소급: 산정기간 = [O − 3개월, O − 1일].
      대법원 1989. 4. 11. 선고 87다카2901 "사유발생한 날인 초일은 산입하지 아니하여야 할 것이므로(민법 제157조)
      … 1985.8.22부터 소급하여 역일에 의한 3개월을 계산하여야 하는 것이다". 대법원 1996. 7. 9. 선고 96누5469
      이유 본문 "사유 발생한 날인 초일은 산입하지 않아야 할 것이므로(당원 1989. 4. 11. 선고 87다카2901 판결 참조),
      이 사건에 있어서는 소외 1이 사망한 날의 전일인 1995. 4. 19.부터 소급하여 역일에 의한 3개월을 계산하여야
      하는 것이다".
      퇴직금이면 입력 `last_working_day`(L)에서 O = L + 1일(대법원이 정한 것이 아님 — 퇴직연금복지과-954 "실제
      퇴직일", 임금복지과-697, 하급심 실무: 수원지방법원 2018가소24967 퇴직 2015. 6. 30. → 4. 1.~6. 30. 91일,
      부산지방법원 서부지원 2023가단118024 2022. 7. 21.~10. 20. 92일). `occurrence_date` 를 적으면 그것을 쓴다
      (예: 해고기간 임금은 해고일 — 부산지방법원 2020나52559 "부당해고 전 3개월(2019. 4. 1.부터 2019. 6. 30.까지)").
      O − 3개월 달에 같은 날짜가 없을 때(O = 5. 31. 등) 원문 근거 없음 → `aw_window_month_end`, warning.
AW-03 [법령] 취업 후 3개월 미만이면 입사일부터 O − 1일까지("이에 준한다"). O 가 입사일 당일이면 평균임금산정
      특례 고시 제2조 "그 근로자에게 지급하기로 한 임금의 1일 평균액으로 평균임금을 추산한다" → 입력
      `first_day_daily_wage`. 일용근로자(시행령 제3조)는 범위 밖.

---------------------------------------------------------------- 임금총액
AW-04 [판례확립] 계속적·정기적으로 지급되고 지급의무가 있는 금품은 명칭 불문 포함, 지급사유 불확정·일시적
      금품은 제외, 판단 시점은 퇴직(해고) 당시 — 대법원 2018. 8. 1. 선고 2014다48057(상단 경고는 2001다16722의
      취업규칙 불이익변경 법리 폐기에 관한 것으로 이 문장과 무관 — 검증 메모). 시행령 제2조 제2항 임시 지급·통화 외
      지급 제외. 세전(임금 68207-564 "세액 공제전의 임금"). 엔진은 항목별 `include` 를 사람이 정한 대로 쓴다.
      임금산정기간이 산정기간에 일부만 걸리면 `aw_partial_period`: calendar_days(기본) = 금액 × 걸친 일수 ÷ 그
      임금산정기간 역일수 — 87다카2901 바른 산식 "308,760×9/31 … 259,590×22/31". extra_wages 도 같다.
AW-05 [판례확립(가산 구조)·행정해석(12개월 지급일 기준)] 상여금은 3개월분을 임금총액에 미리 넣고 총일수로
      나눈다(87다카2901 "사유가 발생한 날 이전 3개월분의 상여금을 미리 임금의 총액에 포함시킨 다음 그 총액을 그
      기간의 총수로 나누는 것이 합리적인 계산방식", 바른 산식 "(220,500×2×3/12)"). '발생일 이전 12개월 중 지급받은
      총액 × 3/12' 은 행정해석(임금 68207-484 "이전 12개월중에 지급받은 상여금 총액의 3/12")이다.
      12개월 범위 = [O − 12개월, O − 1일](지급일 기준, 발생일 당일 지급분 제외). 퇴직 후 지급되었으나 평가대상기간에
      재직한 성과급: `aw_bonus_after_retirement`(수원지방법원 2022나106429, 대법원 2023다274889 소액 상고기각).
AW-06 [불명확] 연차휴가수당. 대법원 2011. 10. 13. 선고 2009다86246 "연차휴가권의 기초가 된 … 1년간의 일부가
      퇴직한 날 이전 3개월간 내에 포함되는 경우에 그 포함된 부분에 해당하는 연차휴가수당만이 … 산입된다", 적용
      부분 "2000. 12. 21. 원고에게 지급된 연차휴가수당 중 3개월간에 해당하는 부분은 포함될 수 없다고 하더라도
      2001. 12.경 원고에게 지급된 연차휴가수당 중 퇴직일 이전 3개월간에 해당하는 부분이 포함되어야 하는 것이므로"
      (귀속 기준, 지급일 무관). 반면 2014다48057 은 '산정기간 내 지급되었거나 지급되어야 하는 것으로 확정된 경우'로
      한정한 원심을 수긍하며 2009다86246 을 "사안을 달리하여 이 사건에 원용하기에 적절하지 않다"고 했다.
      행정해석(임금 68207-173, 근로개선정책과-4298)은 발생일 전에 이미 청구권이 생긴 미사용수당 × 3/12, 퇴직으로
      비로소 지급사유가 생긴 수당은 불산입. 검증 판정에 따라 `moel_3_12` 를 기본값으로 두지 않는다.
      `aw_annual_leave_mode`: case_prorata(기본) | moel_3_12 | exclude. 두 방식 값을 모두 계산해 결과
      `annual_leave_alternatives` 와 warning 에 병기한다. 안분 단위 `aw_annual_leave_prorata_unit`.
      입력 `cause` 를 비우면 청구권 발생일이 O 이상인 수당을 '퇴직으로 발생'으로 본다(leave.py 의 퇴직 행은
      청구권 발생일 = 마지막 근로일 + 1일이다).

---------------------------------------------------------------- 제외기간
AW-07 [법령] 시행령 제2조 제1항 "그 기간과 그 기간 중에 지급된 임금은 평균임금 산정기준이 되는 기간과 임금의
      총액에서 각각 뺀다" — 1호 수습 3개월 이내, 2호 사용자 귀책 휴업, 3호 출산전후·유산사산휴가, 4호 업무상
      요양 휴업, 5호 육아휴직, 6호 쟁의행위, 7호 병역 등 휴직·결근(임금을 받았으면 제외 안 함), 8호 사용자 승인
      휴업. 남녀고용평등법 제19조의3 제4항·제22조의4 제4항은 근로시간 단축 '기간'만 산정기간에서 제외한다고
      규정하고 그 기간 임금 차감은 조문에 없다 — 엔진은 시행령 제2조와 같이 빼되 근거를 '해석'으로 trace 한다.
      제외일수는 산정기간과 겹치는 날(양끝 포함)의 합집합. 제외기간 임금 `wages` 가 산정기간 밖까지 걸친 기간의
      금액이면 aw_partial_period 로 일할한다. 연차휴가·유급 약정휴가 사용기간은 제외하지 않는다(임금근로시간정책팀-145).
      수습을 3개월보다 길게 입력하면 기간은 시작일부터 3개월로 자르고, 그 wages 는 입력 기간 전체의 금액으로 보아
      입력 기간 역일수로 일할한다(warning).
AW-08 [판례확립] 제6호는 적법한 쟁의행위만. 위법 직장폐쇄로 사용자가 임금지급의무를 지면 제외 안 함.
      대법원 2019. 6. 13. 선고 2015다65561 "위와 같은 요건을 충족하지 못하는 위법한 쟁의행위기간은 이에 포함되지
      않는다", "위법한 직장폐쇄로 사용자가 여전히 임금지급의무를 부담하는 경우라면 … 제6호에 해당하는 기간이라고
      할 수 없다". 적법 직장폐쇄라도 근로자의 위법 쟁의 참가기간과 겹치면 제외 안 함. 적법 여부는 사람이 입력.
AW-09 [법령(고시)] 평균임금산정 특례 고시(제2015-77호) 제1조 제1항 "제외되는 기간이 3개월 이상인 경우 제외되는
      기간의 최초일을 평균임금의 산정사유가 발생한 날로 보아 평균임금을 산정한다". 대법원 2023. 6. 1. 선고
      2018두60380(산재) "그 제외되는 기간의 최초일인 퇴직일을 평균임금 산정사유 발생일로 보아". 2018두60380 은
      제외기간이 산정기간 전부를 덮는 사안이라 '3개월 이상' 판정 방식을 가르지 못한다 → `aw_long_exclusion_trigger`.
      제외기간 최초일은 이어진(겹치거나 맞닿은) 제외기간 묶음의 첫날. 새 발생일로 AW-02·03·05·06 을 다시 적용하고
      통상임금도 새 산정기간 말일 기준(근로기준정책과-64). 고시가 현재 최신본인지는 다시 확인하지 못했다(warning).
      새 발생일이 입사일이면 AW-03 근로 첫날 규칙(`first_day_daily_wage`)을 쓰고, 없으면 오류로 멈춘다.
      제외기간 최초일이 입사일보다 앞서면 입력 오류로 멈춘다.
AW-10 [판례확립] 구속·직위해제·대기발령 기간은 시행령 제2조 어느 호에도 해당하지 않아 제외 불가. 대법원 1994.
      4. 12. 선고 92다20309 이유 본문 "원고의 경우와 같이 개인적인 범죄로 구속기소되어 직위해제되었던 기간은 위
      시행령 제2조 소정의 어느 기간에도 해당하지 않으므로", 2014다48057 "구속되거나 대기발령을 받은 기간은 …
      제외할 수 없으므로". `excluded_periods` 에 넣으면 오류, `unlisted_periods` 에 기록만 한다.
MR-4 [판례확립] 통상임금 대체의 한계: 대법원 1999. 11. 12. 선고 98다49357 은 구속으로 3개월 이상 무급 휴직해
      평균임금이 0원이 된 사안에서 곧바로 통상임금으로 산정한 원심을 파기하고 "피고의 평균임금(월평균 급여)은 그
      휴직 전 3개월간의 임금을 기준으로 하여 산정함이 상당하다"고 했다. 엔진은 판단하지 않고, 비열거 기간이 있는데
      통상임금이 적용되면 `pre_absence_average_daily`(휴직 전 평균임금)와 병기해 AW-12 검토 warning 을 낸다.
AW-11 [행정해석·하급심] 부당해고기간과 그 기간 임금상당액 제외. 근로조건지도과-4843 "시행령 제2조제1항제8호에
      준하는 것으로 보아 동 기간과 임금 상당액은 평균임금 산정 시 각각 제외하는 것이 타당", 임금 68207-353,
      부산지방법원 2021. 7. 14. 선고 2020나52559(확정) "사용자의 귀책사유로 인하여 휴업하는 경우에 해당한다 할
      것이어서, 이는 평균임금 산정에서 제외되어야 한다". 대법원 직접 판단 미발견 → `aw_dismissal_period_exclude`.
AW-12 [판례확립] 원칙 산정값이 특수·우연한 사정으로 현저히 적거나 많으면 통상 생활임금을 반영하는 방법으로 산정
      (98다49357 "근로자의 통상의 생활임금을 사실대로 반영하는 방법으로 그 평균임금을 산정하여야 한다", 2014다48057
      "현저하게 적거나 많다고 볼 예외적인 정도까지 이르지 않은 경우에는 … 원칙에 따라"). 현저성은 판단하지 않는다.
      `override_window`(start, end, reason, apply)를 적으면 그 기간으로 AW-01·04~08 을 다시 계산해 나란히 보이고,
      apply: true 일 때만 그 값을 쓴다.

---------------------------------------------------------------- 통상임금 하한·끝수
AW-13 [법령] 제2조 제2항 "제1항제6호에 따라 산출된 금액이 그 근로자의 통상임금보다 적으면 그 통상임금액을
      평균임금으로 한다". 비교 대상은 시행령 제6조 제2항 통상임금(근로기준정책과-4300) — deps `daily_ordinary_of`
      에 산정기간 말일을 넘겨 1일 통상임금을 받는다. 휴업기간 제외 후 비교(퇴직연금복지과-5241).
AW-14 [불명확] 비교 방식 `aw_ordinary_compare_mode`:
        daily(기본)          1일 평균임금 < 1일 통상임금이면 대체 — 퇴직연금복지과-5241 "일 평균임금을 산정한 후
                             대상 노동자의일 통상임금을 비교한 후 더 큰 금액으로"
        three_month_total    산정기간 임금총액 < 같은 기간 소정근로 대가 통상임금 총액(입력 `ordinary_wage_total`)일
                             때만 대체 — 수원지방법원 2018가소24967(확정, 대법원은 소액사건 상고기각이라 법리 승인 아님)
        exceptional_only     통상 생활임금을 반영하지 못하는 예외적 사정이 있다고 사람이 판단한 경우(입력
                             `ordinary_substitution_exceptional: true`)에만 — 대구지방법원 2025. 8. 21. 선고
                             2024나318050(확정) "평균임금이 통상의 생활임금을 사실적으로 반영할 수 없는 경우에
                             예외적으로 적용되는 것이 … 법령의 취지에 부합한다"
      세 방식의 판정을 모두 계산해 `compare_results` 에 두고, 결과가 갈리면 warning.
RS-04 [불명확] 1일 평균임금 끝수 `aw_round_avg_daily`: jeon2_floor(기본, 수원지방법원 2018가소24967 "소수점
      둘째자리 미만 버림") | won_floor(전주지방법원 군산지원 2023가단56185 "원 미만 버림", 87다카2901 바른 산식
      288,258원 재현) | jeon2_half_up(서울중앙지방법원 2017가단5098186 "소수점 셋째 자리 이하는 반올림") | none.
      통상임금과 비교는 끝수처리 전 값으로 하고, 고른 값에만 끝수처리한다. 결과에 처리 전
      `average_daily_wage_raw` 와 처리 후 `average_daily_wage` 를 모두 둔다.

---------------------------------------------------------------- 미해결로 남긴 것
- 제외기간이 산정기간 일부에만 걸릴 때 상여금·연차수당 3/12 부분도 일할 감액할지(근거 미확인) — 감액하지 않고 warning.
- 재직 12개월 미만자의 상여금 3/12 환산 방식 — 입력대로 3/12, warning.

---------------------------------------------------------------- 사건.yaml `average_wage:` 절
    average_wage:
      occurrence_date: null          # 산정사유 발생일(해고일·사고일 등). 비우면 last_working_day + 1일
      last_working_day: 2015-06-30   # 비우면 worker.last_working_day
      hire_date: 2012-01-02          # 비우면 worker.hire_date
      pay_period_start_day: 1        # 비우면 worker.pay_period_start_day(없으면 1)
      wages:                         # 임금산정기간별(month) 또는 임의 구간(start/end) 임금, 세전
        - month: "2015-04"           # 따옴표로 감싼다(따옴표 없는 2015.10 은 YAML 이 숫자 2015.1 로 읽어 오류)
          items:
            기본급: 3000000                        # 숫자만 적으면 include: true
            가족수당: {amount: 60000, include: true}
            경조금: {amount: 100000, include: false, note: "일시적 지급"}
        - {start: 2015-04-01, end: 2015-06-30, items: {성과연봉급: 1200000}}
      bonuses:                       # 발생일 전 12개월(과 그 뒤) 상여금 지급 내역
        - {paid_date: 2014-12-20, amount: 1000000, include: true, evaluation_start: null, evaluation_end: null}
      annual_leave_pay:              # 연차휴가수당(leave.py 행에서 annual_leave_items_from_rows 로 만들 수 있음)
        - {amount: 900000, paid_date: 2015-01-25, claim_arises: 2015-01-01,
           period_start: 2014-01-01, period_end: 2014-12-31, cause: prior_year_unused}   # | retirement
      excluded_periods:              # 시행령 제2조 제1항 등(EXCLUSION_REASONS)
        - {reason: parental_leave, start: 2015-05-01, end: 2015-05-31, wages: 0}
        - {reason: strike, start: 2015-06-01, end: 2015-06-03, wages: 0, lawful: true}
        - {reason: lockout, start: .., end: .., lawful: false, employer_wage_obligation: true}
        - {reason: military, start: .., end: .., wages: 0, paid: false}
      unlisted_periods:              # 제외할 수 없는 구속·직위해제·대기발령(AW-10, 기록용)
        - {reason: detention, start: 2015-04-10, end: 2015-04-30}
      ordinary_wage_total: null      # three_month_total 비교용 같은 기간 소정근로 대가 통상임금 총액
      ordinary_substitution_exceptional: false   # exceptional_only 비교용 사람 판단
      pre_absence_average_daily: null            # MR-4 병기용 휴직 전 1일 평균임금
      override_window: null          # {start: 2014-10-01, end: 2014-12-31, reason: "휴직 전 3개월", apply: false}
      first_day_daily_wage: null     # 근로 첫날 산정사유 발생 시 약정 임금 1일 평균액(특례 고시 제2조)
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from .common import (
    LaborError,
    OptionSpec,
    Trace,
    add_months,
    days_inclusive,
    dec,
    parse_date,
    pay_periods,
    round_to,
)

__all__ = [
    "EXCLUSION_REASONS", "OPTIONS", "RULES", "UNLISTED_REASONS",
    "AnnualLeavePay", "AverageRow", "AverageWageInput", "AverageWageResult", "Bonus", "ExcludedPeriod",
    "OverrideWindow", "UnlistedPeriod", "WageEntry", "WageItem", "WindowCalc",
    "annual_leave_items_from_rows", "calculate_average_wage", "load_average_wage", "window_bounds",
]

ZERO = Decimal(0)
ONE = Decimal(1)
THREE_TWELFTHS = Decimal(3) / Decimal(12)

EXCLUSION_REASONS = {
    "probation": "수습 시작일부터 3개월 이내 기간(시행령 제2조 제1항 제1호)",
    "employer_shutdown": "사용자 귀책사유 휴업기간(제2호, 법 제46조)",
    "maternity": "출산전후휴가·유산·사산 휴가기간(제3호)",
    "industrial_accident": "업무상 부상·질병 요양 휴업기간(제4호, 법 제78조)",
    "parental_leave": "육아휴직기간(제5호, 남녀고용평등법 제19조)",
    "strike": "쟁의행위기간(제6호) — 적법한 쟁의행위만(대법원 2015다65561)",
    "lockout": "직장폐쇄기간(제6호) — 적법하고 위법 쟁의 참가와 겹치지 않을 때만(대법원 2015다65561)",
    "military": "병역·예비군·민방위 의무이행 휴직·결근기간(제7호) — 임금을 받았으면 제외 안 함",
    "approved_leave": "업무 외 부상·질병 등 사용자 승인 휴업기간(제8호)",
    "childcare_reduced_hours": "육아기 근로시간 단축기간(남녀고용평등법 제19조의3 제4항) — 임금 차감은 해석",
    "family_care_reduced_hours": "가족돌봄 등 근로시간 단축기간(남녀고용평등법 제22조의4 제4항) — 임금 차감은 해석",
    "unfair_dismissal": "부당해고기간(행정해석 근로조건지도과-4843, 부산지방법원 2020나52559) — aw_dismissal_period_exclude",
}

UNLISTED_REASONS = {
    "detention": "구속 기간(대법원 92다20309)",
    "position_removal": "직위해제 기간(대법원 92다20309)",
    "standby": "대기발령 기간(대법원 2014다48057)",
    "other": "기타 시행령 제2조에 열거되지 않은 기간",
}

OPTIONS: dict[str, OptionSpec] = {s.key: s for s in [
    OptionSpec("aw_window_month_end", "next_day", "발생일의 3개월(12개월) 전 달에 같은 날짜가 없을 때 시작일", "AW-02", {
        "next_day": "그 달 말일 다음 날(발생일 5. 31. → 3. 1.) — 원문 근거 미확인",
        "month_end": "그 달 말일(발생일 5. 31. → 2. 28./29.) — 원문 근거 미확인",
    }),
    OptionSpec("aw_partial_period", "calendar_days", "산정기간에 일부만 걸친 임금산정기간 금액", "AW-04", {
        "calendar_days": "금액 × 걸친 일수 ÷ 그 임금산정기간 역일수(대법원 87다카2901 바른 산식 '308,760×9/31')",
        "as_entered": "입력 금액이 이미 걸친 부분의 금액 — 일할하지 않음",
    }),
    OptionSpec("aw_bonus_after_retirement", False, "발생일 뒤 지급됐으나 평가대상기간에 재직한 성과급 산입", "AW-05", {
        False: "지급일 기준 발생일 이전 12개월 지급분만(임금 68207-484)",
        True: "평가대상기간이 발생일 전 재직기간 안이면 발생일 뒤 지급분도 산입(수원지방법원 2022나106429)",
    }),
    OptionSpec("aw_annual_leave_mode", "case_prorata", "연차휴가수당 산입 방식", "AW-06", {
        "case_prorata": "휴가권의 기초가 된 1년과 산정기간이 겹치는 부분만(귀속 기준, 대법원 2009다86246 적용례)",
        "moel_3_12": "발생일 전 1년 내 청구권이 생긴 미사용수당 × 3/12, 퇴직으로 발생한 수당 불산입(임금 68207-173, 근로개선정책과-4298)",
        "exclude": "산입하지 않음",
    }),
    OptionSpec("aw_annual_leave_prorata_unit", "days", "case_prorata 안분 단위", "AW-06", {
        "days": "수당 × 겹친 일수 ÷ 기초 1년 역일수",
        "months": "수당 × 3/12 × 겹친 일수 ÷ 산정기간 역일수",
    }),
    OptionSpec("aw_dismissal_period_exclude", True, "부당해고기간과 그 기간 임금상당액 제외", "AW-11", {
        True: "제외(근로조건지도과-4843, 임금 68207-353, 부산지방법원 2020나52559)",
        False: "제외하지 않음",
    }),
    OptionSpec("aw_long_exclusion_trigger", "window_fully_excluded", "특례 고시 제1조 '제외기간 3개월 이상' 판정", "AW-09", {
        "window_fully_excluded": "제외 후 남는 산정기간 일수가 0일 때(산정기간 전부가 제외기간)",
        "continuous_3_months": "산정기간에 걸친 이어진 제외기간 묶음의 길이가 역에 의한 3개월 이상일 때",
    }),
    OptionSpec("aw_ordinary_compare_mode", "daily", "평균임금과 통상임금 비교 방식(AW-13)", "AW-14", {
        "daily": "1일 평균임금 < 1일 통상임금이면 통상임금(퇴직연금복지과-5241 문언)",
        "three_month_total": "3개월 임금총액 < 같은 기간 소정근로 대가 통상임금 총액일 때만(수원지방법원 2018가소24967)",
        "exceptional_only": "예외적 사정이 있다고 사람이 판단한 경우에만(대구지방법원 2024나318050)",
    }),
    OptionSpec("aw_round_avg_daily", "jeon2_floor", "1일 평균임금 끝수", "RS-04", {
        "jeon2_floor": "소수점 둘째자리 미만 버림(수원지방법원 2018가소24967)",
        "won_floor": "원 미만 버림(전주지방법원 군산지원 2023가단56185, 87다카2901 재현)",
        "jeon2_half_up": "소수점 셋째 자리 이하 반올림(서울중앙지방법원 2017가단5098186)",
        "none": "끝수처리 안 함",
    }),
]}

RULES: dict[str, tuple[str, str]] = {
    "AW-01": ("1일 평균임금 = 산정기간 임금총액 ÷ 산정기간 역일수", "법령"),
    "AW-02": ("산정사유 발생일(초일) 불산입·전일부터 역일 3개월, 퇴직금 발생일 = 마지막 근무일 + 1일은 실무", "판례확립·실무관행"),
    "AW-03": ("재직 3개월 미만이면 입사일부터, 첫날 발생은 약정 임금 1일 평균액", "법령"),
    "AW-04": ("계속적·정기적·지급의무 있는 세전 금품, 항목별 산입 여부는 사람이 입력", "판례확립"),
    "AW-05": ("상여금 3개월분 가산 구조, 12개월 지급분 × 3/12 은 행정해석", "판례확립·행정해석"),
    "AW-06": ("연차휴가수당 산입(귀속 안분 / 행정해석 3/12 병기)", "불명확"),
    "AW-07": ("시행령 제2조 제1항 제외기간·그 기간 임금 차감(근로시간 단축 임금 차감은 해석)", "법령"),
    "AW-08": ("적법한 쟁의행위·적법 직장폐쇄만 제외, 위법 직장폐쇄로 임금지급의무 있으면 제외 안 함", "판례확립"),
    "AW-09": ("제외기간 3개월 이상이면 제외기간 최초일을 발생일로(판정 방식은 옵션)", "법령"),
    "AW-10": ("구속·직위해제·대기발령 기간은 제외 불가", "판례확립"),
    "AW-11": ("부당해고기간·임금상당액 제외", "행정해석·하급심"),
    "AW-12": ("현저히 부적당하면 통상 생활임금 반영 방법 — 사람이 대체 산정기간 지정", "판례확립"),
    "AW-13": ("평균임금이 통상임금보다 적으면 통상임금", "법령"),
    "AW-14": ("평균임금·통상임금 비교 방법(1일 / 3개월 총액 / 예외적 사정)", "불명확"),
    "RS-04": ("1일 평균임금 끝수(둘째자리 버림·원 미만 버림·반올림)", "불명확"),
    "MR-4": ("비열거 기간으로 통상임금 대체 시 휴직 전 3개월 기준 검토(98다49357) — 병기·경고", "판례확립"),
}


# ================================================================ 입력
@dataclass
class WageItem:
    name: str
    amount: Decimal
    include: bool = True
    note: str = ""


@dataclass
class WageEntry:
    """임금산정기간(month) 또는 임의 구간(start~end, 양끝 포함)의 임금 항목."""

    period_start: date
    period_end: date
    items: list
    key: str | None = None
    note: str = ""


@dataclass
class Bonus:
    paid_date: date
    amount: Decimal
    include: bool = True
    evaluation_start: date | None = None
    evaluation_end: date | None = None
    note: str = ""


@dataclass
class AnnualLeavePay:
    """연차휴가수당 한 건. period_* 는 휴가권의 기초가 된 1년(leave.py 산정기간)."""

    amount: Decimal
    paid_date: date | None = None
    claim_arises: date | None = None
    period_start: date | None = None
    period_end: date | None = None
    cause: str | None = None          # prior_year_unused | retirement | None(청구권 발생일로 판정)
    note: str = ""


@dataclass
class ExcludedPeriod:
    reason: str
    start: date
    end: date
    wages: Decimal = ZERO
    lawful: bool | None = None
    employer_wage_obligation: bool | None = None
    worker_unlawful_strike: bool = False
    paid: bool | None = None
    note: str = ""


@dataclass
class UnlistedPeriod:
    reason: str
    start: date
    end: date
    note: str = ""


@dataclass
class OverrideWindow:
    start: date
    end: date
    reason: str
    apply: bool = False


@dataclass
class AverageWageInput:
    occurrence_date: date
    hire_date: date
    occurrence_from_last_working_day: bool = False
    pay_period_start_day: int = 1
    wages: list = field(default_factory=list)
    bonuses: list = field(default_factory=list)
    annual_leave_pay: list = field(default_factory=list)
    excluded_periods: list = field(default_factory=list)
    unlisted_periods: list = field(default_factory=list)
    ordinary_wage_total: Decimal | None = None
    ordinary_substitution_exceptional: bool = False
    pre_absence_average_daily: Decimal | None = None
    override_window: OverrideWindow | None = None
    first_day_daily_wage: Decimal | None = None


# ================================================================ 결과
@dataclass
class AverageRow:
    """계산표 한 줄. kind: window | wage | extra | excluded | unlisted | bonus | annual_leave | shift | total."""

    calc: str                 # principle | override
    kind: str
    label: str
    start: date | None
    end: date | None
    days: int | None
    amount: Decimal | None    # 임금총액에 더한(제외기간은 뺀) 금액
    counted: bool
    note: str = ""


@dataclass
class WindowCalc:
    calc: str
    occurrence_date: date
    start: date
    end: date
    window_days: int
    excluded_days: int
    counted_days: int
    wages_sum: Decimal
    extra_sum: Decimal
    excluded_wages: Decimal
    bonus_total: Decimal
    bonus_addition: Decimal
    annual_leave_addition: Decimal
    annual_leave_alternatives: dict
    wage_total: Decimal
    daily: Decimal            # AW-01 산출액(비교·끝수 전)


@dataclass
class AverageWageResult:
    rows: list
    total: Decimal
    claims: list
    trace: list
    warnings: list
    original_occurrence_date: date
    occurrence_date: date
    window_start: date
    window_end: date
    window_days: int
    excluded_days: int
    counted_days: int
    wage_total: Decimal
    principle_daily: Decimal
    ordinary_daily: Decimal | None
    ordinary_applied: bool
    compare_results: dict
    average_daily_wage_raw: Decimal     # 통상임금 비교 후, 끝수처리 전
    average_daily_wage: Decimal         # 끝수처리 후
    principle: WindowCalc
    override: WindowCalc | None = None
    override_applied: bool = False
    annual_leave_alternatives: dict = field(default_factory=dict)


# ================================================================ 읽기
_KEYS = {
    "occurrence_date", "last_working_day", "hire_date", "pay_period_start_day", "wages", "bonuses",
    "annual_leave_pay", "excluded_periods", "unlisted_periods", "ordinary_wage_total",
    "ordinary_substitution_exceptional", "pre_absence_average_daily", "override_window", "first_day_daily_wage",
}


def _num(v, label: str, default=None) -> Decimal | None:
    if v is None or v == "":
        return default
    if isinstance(v, bool):
        raise LaborError(f"평균임금: {label} 은(는) 숫자여야 합니다: {v!r}")
    try:
        return dec(v)
    except (InvalidOperation, ValueError, TypeError):
        raise LaborError(f"평균임금: {label} 은(는) 숫자여야 합니다: {v!r}") from None


def _date(v, label: str, required: bool = False) -> date | None:
    if v is None or v == "":
        if required:
            raise LaborError(f"평균임금: {label} 이(가) 없습니다")
        return None
    try:
        return parse_date(v)
    except (ValueError, TypeError):
        raise LaborError(f"평균임금: {label} 날짜 형식이 올바르지 않습니다: {v!r}") from None


def _bool(v, label: str, default=None):
    if v is None or v == "":
        return default
    if isinstance(v, bool):
        return v
    raise LaborError(f"평균임금: {label} 은(는) true/false 여야 합니다: {v!r}")


def _dict(v, label: str, allowed: set) -> dict:
    if not isinstance(v, dict):
        raise LaborError(f"평균임금: {label} 은(는) 사전이어야 합니다")
    unknown = set(v) - allowed
    if unknown:
        raise LaborError(f"평균임금: {label} 에 알 수 없는 키: {', '.join(sorted(map(str, unknown)))}")
    return v


def _span(s: date, e: date, label: str) -> None:
    if e < s:
        raise LaborError(f"평균임금: {label} 의 끝 {e} 이 시작 {s} 보다 앞섭니다")


def _month_period(key, start_day: int, label: str) -> tuple[str, date, date]:
    if isinstance(key, date):
        y, m = key.year, key.month
    elif not isinstance(key, str):
        # YAML 은 따옴표 없는 2015.10 을 숫자 2015.1 로 읽는다 — 10월과 1월을 가를 수 없으니 받지 않는다.
        raise LaborError(f"평균임금: {label} 이(가) 숫자 {key!r} 로 읽혔습니다 — YAML 에서 따옴표 없는 2015.10 은 "
                         "숫자 2015.1(1월)이 됩니다. \"2015-10\" 처럼 따옴표로 감싸 적으십시오")
    else:
        parts = key.strip().replace(".", "-").split("-")
        try:
            y, m = int(parts[0]), int(parts[1])
            date(y, m, 1)
        except (ValueError, IndexError):
            raise LaborError(f"평균임금: {label} 은(는) 'YYYY-MM' 이어야 합니다: {key!r}") from None
    anchor = date(y, m, min(start_day, calendar.monthrange(y, m)[1]))
    sl = pay_periods(anchor, anchor, start_day)[0]
    return f"{y:04d}-{m:02d}", sl.period_start, sl.period_end


def _load_items(raw, label: str) -> list:
    if raw is None:
        raise LaborError(f"평균임금: {label}.items 가 없습니다")
    pairs = []
    if isinstance(raw, dict):
        pairs = [(str(k), v) for k, v in raw.items()]
    elif isinstance(raw, list):
        for i, it in enumerate(raw, 1):
            it = _dict(it, f"{label}.items[{i}]", {"name", "amount", "include", "note"})
            if "name" not in it:
                raise LaborError(f"평균임금: {label}.items[{i}] 에 name 이 없습니다")
            pairs.append((str(it["name"]), it))
    else:
        raise LaborError(f"평균임금: {label}.items 는 '항목: 금액' 사전 또는 목록이어야 합니다")
    out = []
    for name, v in pairs:
        lab = f"{label}.items.{name}"
        if isinstance(v, dict):
            v = _dict(v, lab, {"name", "amount", "include", "note"})
            if "amount" not in v:
                raise LaborError(f"평균임금: {lab} 에 amount 가 없습니다")
            amt = _num(v["amount"], f"{lab}.amount")
            inc = _bool(v.get("include"), f"{lab}.include", True)
            note = str(v.get("note") or "")
        else:
            amt = _num(v, lab)
            if amt is None:
                raise LaborError(f"평균임금: {lab} 금액이 없습니다")
            inc, note = True, ""
        if amt is None:
            raise LaborError(f"평균임금: {lab} 금액이 없습니다")
        out.append(WageItem(name, amt, bool(inc), note))
    return out


def load_average_wage(raw: dict, worker: dict | None = None) -> AverageWageInput:
    """사건.yaml `average_wage:` 절(dict)과 `worker:` 절을 읽는다."""
    raw = dict(raw or {})
    worker = dict(worker or {})
    unknown = set(raw) - _KEYS
    if unknown:
        raise LaborError(f"평균임금: average_wage 절에 알 수 없는 키: {', '.join(sorted(unknown))}")

    hire = _date(raw.get("hire_date"), "hire_date") or _date(worker.get("hire_date"), "worker.hire_date")
    if hire is None:
        raise LaborError("평균임금: 입사일(average_wage.hire_date 또는 worker.hire_date)이 없습니다")
    occ = _date(raw.get("occurrence_date"), "occurrence_date")
    from_lwd = False
    if occ is None:
        lwd = _date(raw.get("last_working_day"), "last_working_day") or _date(worker.get("last_working_day"),
                                                                             "worker.last_working_day")
        if lwd is None:
            raise LaborError("평균임금: 산정사유 발생일(occurrence_date) 또는 마지막 근무일(last_working_day)이 없습니다")
        occ = lwd + timedelta(days=1)
        from_lwd = True
    if occ < hire:
        raise LaborError(f"평균임금: 산정사유 발생일 {occ} 이 입사일 {hire} 보다 앞섭니다")

    sd = raw.get("pay_period_start_day")
    if sd in (None, ""):
        sd = worker.get("pay_period_start_day")
    if sd in (None, ""):
        sd = 1
    try:
        if isinstance(sd, bool):
            raise TypeError
        sd = int(sd)
    except (ValueError, TypeError):
        raise LaborError(f"평균임금: pay_period_start_day 는 1~28 정수여야 합니다: {sd!r}") from None
    if not 1 <= sd <= 28:
        raise LaborError(f"평균임금: pay_period_start_day 는 1~28 정수여야 합니다: {sd!r}")

    wages = []
    for i, w in enumerate(raw.get("wages") or [], 1):
        lab = f"wages[{i}]"
        w = _dict(w, lab, {"month", "start", "end", "items", "note"})
        if w.get("month") not in (None, ""):
            if w.get("start") or w.get("end"):
                raise LaborError(f"평균임금: {lab} 에는 month 와 start/end 중 하나만 적습니다")
            key, ps, pe = _month_period(w["month"], sd, f"{lab}.month")
        else:
            ps = _date(w.get("start"), f"{lab}.start")
            pe = _date(w.get("end"), f"{lab}.end")
            if ps is None or pe is None:
                raise LaborError(f"평균임금: {lab} 에 month 또는 start·end 가 없습니다")
            _span(ps, pe, lab)
            key = None
        wages.append(WageEntry(ps, pe, _load_items(w.get("items"), lab), key, str(w.get("note") or "")))

    bonuses = []
    for i, b in enumerate(raw.get("bonuses") or [], 1):
        lab = f"bonuses[{i}]"
        b = _dict(b, lab, {"paid_date", "amount", "include", "evaluation_start", "evaluation_end", "note"})
        amt = _num(b.get("amount"), f"{lab}.amount")
        if amt is None:
            raise LaborError(f"평균임금: {lab}.amount 가 없습니다")
        bonuses.append(Bonus(_date(b.get("paid_date"), f"{lab}.paid_date", required=True), amt,
                             bool(_bool(b.get("include"), f"{lab}.include", True)),
                             _date(b.get("evaluation_start"), f"{lab}.evaluation_start"),
                             _date(b.get("evaluation_end"), f"{lab}.evaluation_end"), str(b.get("note") or "")))

    leaves = []
    for i, a in enumerate(raw.get("annual_leave_pay") or [], 1):
        lab = f"annual_leave_pay[{i}]"
        a = _dict(a, lab, {"amount", "paid_date", "claim_arises", "period_start", "period_end", "cause", "note"})
        amt = _num(a.get("amount"), f"{lab}.amount")
        if amt is None:
            raise LaborError(f"평균임금: {lab}.amount 가 없습니다")
        cause = a.get("cause") or None
        if cause not in (None, "prior_year_unused", "retirement"):
            raise LaborError(f"평균임금: {lab}.cause 는 prior_year_unused 또는 retirement 여야 합니다: {cause!r}")
        item = AnnualLeavePay(amt, _date(a.get("paid_date"), f"{lab}.paid_date"),
                              _date(a.get("claim_arises"), f"{lab}.claim_arises"),
                              _date(a.get("period_start"), f"{lab}.period_start"),
                              _date(a.get("period_end"), f"{lab}.period_end"), cause, str(a.get("note") or ""))
        if (item.period_start is None) != (item.period_end is None):
            raise LaborError(f"평균임금: {lab} 에 period_start 와 period_end 는 함께 적어야 합니다")
        if item.period_start is not None:
            _span(item.period_start, item.period_end, lab)
        leaves.append(item)

    excluded = []
    for i, e in enumerate(raw.get("excluded_periods") or [], 1):
        lab = f"excluded_periods[{i}]"
        e = _dict(e, lab, {"reason", "start", "end", "wages", "lawful", "employer_wage_obligation",
                           "worker_unlawful_strike", "paid", "note"})
        reason = e.get("reason")
        if reason in UNLISTED_REASONS:
            raise LaborError(f"평균임금: {lab} 사유 {reason!r}({UNLISTED_REASONS[reason]})는 시행령 제2조에 열거되지 않아 "
                             "산정기간에서 제외할 수 없습니다(AW-10, 대법원 92다20309) — unlisted_periods 에 적으십시오")
        if reason not in EXCLUSION_REASONS:
            raise LaborError(f"평균임금: {lab} 의 사유 {reason!r} 를 알 수 없습니다. 가능: {', '.join(EXCLUSION_REASONS)}")
        s = _date(e.get("start"), f"{lab}.start", required=True)
        en = _date(e.get("end"), f"{lab}.end", required=True)
        _span(s, en, lab)
        p = ExcludedPeriod(reason, s, en, _num(e.get("wages"), f"{lab}.wages", ZERO),
                           _bool(e.get("lawful"), f"{lab}.lawful"),
                           _bool(e.get("employer_wage_obligation"), f"{lab}.employer_wage_obligation"),
                           bool(_bool(e.get("worker_unlawful_strike"), f"{lab}.worker_unlawful_strike", False)),
                           _bool(e.get("paid"), f"{lab}.paid"), str(e.get("note") or ""))
        if reason in ("strike", "lockout") and p.lawful is None:
            raise LaborError(f"평균임금: {lab} 쟁의행위·직장폐쇄 기간은 적법 여부(lawful: true/false)를 사람이 정해 적어야 합니다(AW-08)")
        if reason == "lockout" and p.lawful is False and p.employer_wage_obligation is None:
            raise LaborError(f"평균임금: {lab} 위법한 직장폐쇄는 사용자의 임금지급의무 여부(employer_wage_obligation)를 적어야 합니다(AW-08)")
        if p.wages < 0:
            raise LaborError(f"평균임금: {lab}.wages 는 음수일 수 없습니다")
        excluded.append(p)

    unlisted = []
    for i, u in enumerate(raw.get("unlisted_periods") or [], 1):
        lab = f"unlisted_periods[{i}]"
        u = _dict(u, lab, {"reason", "start", "end", "note"})
        if u.get("reason") not in UNLISTED_REASONS:
            raise LaborError(f"평균임금: {lab} 의 사유 {u.get('reason')!r} 를 알 수 없습니다. 가능: {', '.join(UNLISTED_REASONS)}")
        s = _date(u.get("start"), f"{lab}.start", required=True)
        en = _date(u.get("end"), f"{lab}.end", required=True)
        _span(s, en, lab)
        unlisted.append(UnlistedPeriod(u["reason"], s, en, str(u.get("note") or "")))

    ov = raw.get("override_window")
    override = None
    if ov:
        ov = _dict(ov, "override_window", {"start", "end", "reason", "apply"})
        s = _date(ov.get("start"), "override_window.start", required=True)
        en = _date(ov.get("end"), "override_window.end", required=True)
        _span(s, en, "override_window")
        if not ov.get("reason"):
            raise LaborError("평균임금: override_window.reason(대체 산정 사유)을 적어야 합니다(AW-12)")
        override = OverrideWindow(s, en, str(ov["reason"]), bool(_bool(ov.get("apply"), "override_window.apply", False)))

    return AverageWageInput(
        occurrence_date=occ,
        hire_date=hire,
        occurrence_from_last_working_day=from_lwd,
        pay_period_start_day=sd,
        wages=wages,
        bonuses=bonuses,
        annual_leave_pay=leaves,
        excluded_periods=excluded,
        unlisted_periods=unlisted,
        ordinary_wage_total=_num(raw.get("ordinary_wage_total"), "ordinary_wage_total"),
        ordinary_substitution_exceptional=bool(_bool(raw.get("ordinary_substitution_exceptional"),
                                                     "ordinary_substitution_exceptional", False)),
        pre_absence_average_daily=_num(raw.get("pre_absence_average_daily"), "pre_absence_average_daily"),
        override_window=override,
        first_day_daily_wage=_num(raw.get("first_day_daily_wage"), "first_day_daily_wage"),
    )


def annual_leave_items_from_rows(rows) -> list:
    """연차 모듈 결과 행(속성 period_start, period_end, amount, claim_arises, pay_due_date)을 AnnualLeavePay 로.

    leave.py 를 import 하지 않고 속성만 읽는다. amount 가 0 인 행은 뺀다. cause 는 비워 두어
    청구권 발생일로 판정하게 한다(발생일 이상이면 퇴직으로 발생).
    """
    out = []
    for r in rows:
        amt = dec(getattr(r, "amount", None), ZERO)
        if not amt:
            continue
        out.append(AnnualLeavePay(amt, getattr(r, "pay_due_date", None), getattr(r, "claim_arises", None),
                                  getattr(r, "period_start", None), getattr(r, "period_end", None), None,
                                  str(getattr(r, "source", "") or "")))
    return out


# ================================================================ 날짜 헬퍼
def _fmt(d: date | None) -> str:
    return "" if d is None else f"{d.year}. {d.month}. {d.day}."


def _back_months(O: date, n: int, mode: str) -> tuple[date, bool]:
    """O 의 n개월 전 같은 날짜. 없으면 mode 에 따라 그 달 말일 다음 날(next_day) 또는 말일(month_end)."""
    y, m = divmod(O.month - 1 - n, 12)
    y += O.year
    m += 1
    last = calendar.monthrange(y, m)[1]
    if O.day <= last:
        return date(y, m, O.day), False
    me = date(y, m, last)
    return (me + timedelta(days=1) if mode == "next_day" else me), True


def window_bounds(occurrence: date, hire: date, mode: str = "next_day") -> tuple[date, date, bool, bool]:
    """(시작, 끝, 대응일 없음 여부, 3개월 미만 재직 여부). 끝 = 발생일 전날(AW-02), 시작은 입사일 이후(AW-03)."""
    start, missing = _back_months(occurrence, 3, mode)
    end = occurrence - timedelta(days=1)
    short = hire > start
    return (hire if short else start), end, missing, short


def _three_months_long(s: date, e: date) -> bool:
    """[s, e] 가 역에 의한 3개월 이상인지(민법 제160조: s 부터 3개월의 만료일이 e 이하)."""
    target = add_months(s, 3)
    expiry = target if target.day != s.day else target - timedelta(days=1)
    return expiry <= e


def _overlap(s1: date, e1: date, s2: date, e2: date) -> tuple[date, date] | None:
    s, e = max(s1, s2), min(e1, e2)
    return (s, e) if s <= e else None


def _settle(x: Decimal) -> Decimal:
    """Decimal 나눗셈의 순환소수 오차 보정(소수 10자리 반올림). 끝수처리 직전에만 쓴다."""
    return x.quantize(Decimal("1e-10"), rounding=ROUND_HALF_UP)


def _round_daily(v: Decimal, mode: str) -> Decimal:
    if mode == "none":
        return v
    v = _settle(v)
    if mode == "won_floor":
        return round_to(v, 0, "floor")
    if mode == "jeon2_floor":
        return round_to(v, 2, "floor")
    return round_to(v, 2, "half_up")


# ================================================================ 계산 내부
@dataclass
class _Ctx:
    o: dict
    trace: list
    warnings: list
    rows: list

    def warn(self, msg: str) -> None:
        if msg not in self.warnings:
            self.warnings.append(msg)


def _read_options(opts: dict | None) -> dict:
    opts = opts or {}
    out = {}
    for key, spec in OPTIONS.items():
        v = opts.get(key, spec.default)
        if spec.choices and v not in spec.choices:
            raise LaborError(f"옵션 {key} 의 값 {v!r} 은 허용되지 않습니다. 가능: {', '.join(map(str, spec.choices))}")
        out[key] = v
    return out


def _effective_exclusions(inp: AverageWageInput, ctx: _Ctx) -> list:
    """[(ExcludedPeriod, 시작, 끝)] — 실제로 빼는 기간만. 판정 근거는 trace 에 남긴다."""
    o = ctx.o
    out = []
    for p in inp.excluded_periods:
        label = f"{EXCLUSION_REASONS[p.reason].split('(')[0]} {_fmt(p.start)}~{_fmt(p.end)}"
        s, e = p.start, p.end
        keep, why = True, ""
        if p.reason == "strike" and not p.lawful:
            keep, why = False, "위법한 쟁의행위기간 — 제6호 아님(대법원 2015다65561)"
        elif p.reason == "lockout":
            if p.lawful is False and p.employer_wage_obligation:
                keep, why = False, "위법한 직장폐쇄로 임금지급의무 존속 — 제6호 아님(대법원 2015다65561)"
            elif p.lawful and p.worker_unlawful_strike:
                keep, why = False, "적법 직장폐쇄이나 근로자의 위법 쟁의 참가기간과 겹침 — 제외 안 함(대법원 2015다65561)"
            elif p.lawful is False:
                ctx.warn(f"{label}: 위법한 직장폐쇄인데 임금지급의무가 없다고 입력되어 제외했습니다 — 사실관계 확인 필요(AW-08)")
        elif p.reason == "military":
            paid = p.paid if p.paid is not None else p.wages > 0
            if p.paid is None:
                ctx.trace.append(Trace("AW-07", f"{label}: 임금 수령 여부", "wages > 0" if paid else "wages = 0",
                                       "paid 미입력 — 그 기간 임금 입력액으로 판정"))
            if paid:
                keep, why = False, "병역 등 의무이행 기간 중 임금을 받음 — 제7호 단서로 제외 안 함"
        elif p.reason == "unfair_dismissal":
            ctx.warn(f"{label}: 부당해고기간 제외(AW-11)는 행정해석·하급심 근거이고 대법원 판단은 확인되지 않았습니다")
            if not o["aw_dismissal_period_exclude"]:
                keep, why = False, "aw_dismissal_period_exclude=false — 제외하지 않음"
        elif p.reason == "probation":
            cap = add_months(p.start, 3)
            cap = (cap if cap.day != p.start.day else cap - timedelta(days=1))
            if p.end > cap:
                e = cap
                ctx.trace.append(Trace("AW-07", f"{label}: 수습 제외기간", f"{_fmt(p.start)}~{_fmt(cap)}",
                                       "수습 시작일부터 3개월 이내만 제외(제1호)"))
                if p.wages:
                    ctx.warn(f"{label}: 수습 제외기간을 {_fmt(p.start)}~{_fmt(cap)} 로 잘랐고, 입력 wages {p.wages}원은 입력 기간 "
                             f"{days_inclusive(p.start, p.end)}일 전체의 금액으로 보아 일할해 뺐습니다 — 3개월 이내 부분의 "
                             f"지급액을 알면 end 를 {_fmt(cap)} 로 하고 그 금액을 적으십시오(AW-07)")
        elif p.reason in ("childcare_reduced_hours", "family_care_reduced_hours"):
            ctx.trace.append(Trace("AW-07", f"{label}: 근로시간 단축기간", "기간·임금 제외",
                                   "조문은 '기간'만 제외 — 그 기간 임금 차감은 시행령 제2조 유추 해석"))
        if keep:
            out.append((p, s, e))
        else:
            ctx.trace.append(Trace("AW-08" if p.reason in ("strike", "lockout") else "AW-07", label, "제외 안 함", why))
    return out


def _blocks(eff: list) -> list[tuple[date, date]]:
    spans = sorted((s, e) for _, s, e in eff)
    out: list[list[date]] = []
    for s, e in spans:
        if out and s <= out[-1][1] + timedelta(days=1):
            out[-1][1] = max(out[-1][1], e)
        else:
            out.append([s, e])
    return [(s, e) for s, e in out]


def _excluded_day_count(eff: list, start: date, end: date) -> int:
    days: set = set()
    for _, s, e in eff:
        ov = _overlap(s, e, start, end)
        if ov:
            d = ov[0]
            while d <= ov[1]:
                days.add(d)
                d += timedelta(days=1)
    return len(days)


def _prorate(amount: Decimal, ps: date, pe: date, start: date, end: date, o: dict, ctx: _Ctx, label: str):
    """(산입액, 걸친 일수, 비고). 겹치지 않으면 None."""
    ov = _overlap(ps, pe, start, end)
    if ov is None:
        return None
    covered = days_inclusive(*ov)
    total = days_inclusive(ps, pe)
    if covered == total:
        return amount, covered, ""
    if o["aw_partial_period"] == "calendar_days":
        return amount * covered / total, covered, f"일할 {amount} × {covered}/{total}"
    ctx.warn(f"{label}: 산정기간에 일부({covered}/{total}일)만 걸친 금액을 일할하지 않고 그대로 넣었습니다(aw_partial_period=as_entered)")
    return amount, covered, "입력 금액 그대로(as_entered)"


def _leave_cause(item: AnnualLeavePay, O: date) -> str | None:
    if item.cause is not None:
        return item.cause
    if item.claim_arises is None:
        return None
    return "retirement" if item.claim_arises >= O else "prior_year_unused"


def _leave_amounts(item: AnnualLeavePay, O: date, start: date, end: date, start12: date, o: dict):
    """{mode: (산입액 | None, 비고)}."""
    res = {}
    # case_prorata
    if item.period_start is None:
        res["case_prorata"] = (None, "기초 1년(period_start/end) 없음")
    else:
        ov = _overlap(item.period_start, item.period_end, start, end)
        if ov is None:
            res["case_prorata"] = (ZERO, "기초 1년이 산정기간과 겹치지 않음")
        else:
            n = days_inclusive(*ov)
            if o["aw_annual_leave_prorata_unit"] == "days":
                y = days_inclusive(item.period_start, item.period_end)
                res["case_prorata"] = (item.amount * n / y, f"{item.amount} × 겹친 {n}일 ÷ 기초기간 {y}일")
            else:
                w = days_inclusive(start, end)
                res["case_prorata"] = (item.amount * THREE_TWELFTHS * n / w, f"{item.amount} × 3/12 × 겹친 {n}일 ÷ 산정기간 {w}일")
    # moel_3_12
    cause = _leave_cause(item, O)
    if cause is None:
        res["moel_3_12"] = (None, "청구권 발생일(claim_arises)·cause 없음")
    elif cause == "retirement":
        res["moel_3_12"] = (ZERO, "퇴직으로 비로소 지급사유 발생 — 불산입(근로개선정책과-4298)")
    elif item.claim_arises is not None and not (start12 <= item.claim_arises < O):
        res["moel_3_12"] = (ZERO, f"청구권 발생일 {_fmt(item.claim_arises)} 이 발생일 이전 1년 밖")
    else:
        res["moel_3_12"] = (item.amount * THREE_TWELFTHS, f"{item.amount} × 3/12(임금 68207-173)")
    res["exclude"] = (ZERO, "산입 안 함")
    return res


def _calc(inp: AverageWageInput, ctx: _Ctx, deps: dict, eff: list, O: date, start: date, end: date,
          calc: str) -> WindowCalc:
    o = ctx.o
    rows = ctx.rows
    window_days = days_inclusive(start, end)
    ex_days = _excluded_day_count(eff, start, end)
    counted = window_days - ex_days
    rows.append(AverageRow(calc, "window", "산정기간", start, end, window_days, None, True,
                           f"발생일 {_fmt(O)}, 제외 {ex_days}일, 산입 {counted}일"))

    # 임금
    wages_sum = ZERO
    covered_days: set = set()
    for i, w in enumerate(inp.wages, 1):
        label = f"wages[{i}] {w.key or (_fmt(w.period_start) + '~' + _fmt(w.period_end))}"
        inc = sum((it.amount for it in w.items if it.include), ZERO)
        out_items = [f"{it.name} {it.amount}" for it in w.items if not it.include]
        pr = _prorate(inc, w.period_start, w.period_end, start, end, o, ctx, label)
        if pr is None:
            continue
        amt, cov, pnote = pr
        ov = _overlap(w.period_start, w.period_end, start, end)
        d = ov[0]
        while d <= ov[1]:
            covered_days.add(d)
            d += timedelta(days=1)
        wages_sum += amt
        note = "; ".join(x for x in (
            ", ".join(f"{it.name} {it.amount}" for it in w.items if it.include),
            ("불산입: " + ", ".join(out_items)) if out_items else "", pnote, w.note) if x)
        rows.append(AverageRow(calc, "wage", label, *ov, cov, amt, True, note))
    missing = window_days - len(covered_days)
    if missing > 0:
        ctx.warn(f"{'원칙' if calc == 'principle' else '대체'} 산정기간 {_fmt(start)}~{_fmt(end)} 중 임금 입력이 없는 날이 {missing}일 있습니다 — "
                 "무급이면 그대로 두고, 아니면 wages 를 보완하십시오")

    extra_sum = ZERO
    extra = deps.get("extra_wages") or {}
    for key in sorted(extra):
        k, ps, pe = _month_period(key, inp.pay_period_start_day, f"extra_wages[{key!r}]")
        amt = dec(extra[key])
        pr = _prorate(amt, ps, pe, start, end, o, ctx, f"extra_wages {k}")
        if pr is None:
            continue
        v, cov, pnote = pr
        extra_sum += v
        rows.append(AverageRow(calc, "extra", f"추가 임금(재산정 증가분) {k}", *_overlap(ps, pe, start, end), cov, v, True, pnote))

    # 제외기간 임금
    excluded_wages = ZERO
    for p, s, e in eff:
        ov = _overlap(s, e, start, end)
        if ov is None:
            continue
        label = f"{EXCLUSION_REASONS[p.reason]} {_fmt(p.start)}~{_fmt(p.end)}"
        # wages 는 입력 기간(p.start~p.end) 전체의 금액이다. 수습을 3개월로 잘랐어도 분모는 입력 기간 역일수,
        # 분자는 (잘린 제외기간 ∩ 산정기간) 일수로 일할한다.
        pr = _prorate(p.wages, p.start, p.end, *ov, o, ctx, label) if p.wages else (ZERO, days_inclusive(*ov), "")
        v, cov, pnote = pr
        excluded_wages += v
        rows.append(AverageRow(calc, "excluded", label, *ov, cov, -v, False,
                               "; ".join(x for x in (f"그 기간 임금 {p.wages} 차감" if p.wages else "그 기간 임금 0",
                                                     pnote, p.note) if x)))
    if len([1 for _, s, e in eff if _overlap(s, e, start, end)]) > 1:
        overlap_sum = sum(days_inclusive(*_overlap(s, e, start, end)) for _, s, e in eff if _overlap(s, e, start, end))
        if overlap_sum != ex_days:
            ctx.warn("제외기간끼리 겹칩니다 — 일수는 한 번만 뺐으나 그 기간 임금은 입력마다 차감했으니 중복 여부를 확인하십시오")

    # 상여금
    start12, missing12 = _back_months(O, 12, o["aw_window_month_end"])
    bonus_total = ZERO
    for i, b in enumerate(inp.bonuses, 1):
        label = f"상여금 {_fmt(b.paid_date)} {b.amount}"
        if not b.include:
            rows.append(AverageRow(calc, "bonus", label, b.paid_date, b.paid_date, None, ZERO, False, "include: false"))
            continue
        if start12 <= b.paid_date < O:
            bonus_total += b.amount
            rows.append(AverageRow(calc, "bonus", label, b.paid_date, b.paid_date, None, b.amount, True,
                                   f"발생일 이전 12개월({_fmt(start12)}~{_fmt(O - timedelta(days=1))}) 지급"))
        elif b.paid_date >= O and o["aw_bonus_after_retirement"]:
            if b.evaluation_start is None or b.evaluation_end is None:
                raise LaborError(f"평균임금: bonuses[{i}] 발생일 뒤 지급 성과급을 산입하려면 evaluation_start·evaluation_end 가 필요합니다")
            if b.evaluation_start >= inp.hire_date and b.evaluation_end < O:
                bonus_total += b.amount
                rows.append(AverageRow(calc, "bonus", label, b.paid_date, b.paid_date, None, b.amount, True,
                                       f"발생일 뒤 지급, 평가대상기간 {_fmt(b.evaluation_start)}~{_fmt(b.evaluation_end)} 재직"
                                       "(aw_bonus_after_retirement, 수원지방법원 2022나106429)"))
                ctx.warn(f"{label}: 발생일 뒤 지급 성과급을 산입했습니다 — 12개월 지급분과 중복되지 않는지 확인하십시오(AW-05)")
            else:
                rows.append(AverageRow(calc, "bonus", label, b.paid_date, b.paid_date, None, ZERO, False,
                                       "평가대상기간이 발생일 전 재직기간 밖"))
        else:
            rows.append(AverageRow(calc, "bonus", label, b.paid_date, b.paid_date, None, ZERO, False,
                                   f"발생일 이전 12개월({_fmt(start12)}~{_fmt(O - timedelta(days=1))}) 밖"))
    bonus_add = bonus_total * THREE_TWELFTHS
    if bonus_total:
        rows.append(AverageRow(calc, "bonus", "상여금 가산액", None, None, None, bonus_add, True, f"{bonus_total} × 3/12"))
        if missing12:
            ctx.warn(f"상여금 12개월 범위 시작일의 대응일이 없어 aw_window_month_end={o['aw_window_month_end']} 로 {_fmt(start12)} 을 썼습니다")
        if ex_days:
            ctx.warn("제외기간이 있는 산정기간에서 상여금 3/12 을 감액하지 않았습니다 — 일할 감액 여부는 근거 미확인(AW-05·07)")
        if inp.hire_date > start12:
            ctx.warn("재직 12개월 미만 — 상여금을 입력 지급액 × 3/12 로 넣었습니다. 환산 방식은 확인되지 않았습니다(AW-05)")

    # 연차휴가수당
    alts = {"case_prorata": ZERO, "moel_3_12": ZERO, "exclude": ZERO}
    alt_ok = {"case_prorata": True, "moel_3_12": True, "exclude": True}
    mode = o["aw_annual_leave_mode"]
    leave_add = ZERO
    for i, item in enumerate(inp.annual_leave_pay, 1):
        res = _leave_amounts(item, O, start, end, start12, o)
        for m, (v, _) in res.items():
            if v is None:
                alt_ok[m] = False
            else:
                alts[m] += v
        v, note = res[mode]
        if v is None:
            need = "period_start·period_end" if mode == "case_prorata" else "claim_arises 또는 cause"
            raise LaborError(f"평균임금: annual_leave_pay[{i}] aw_annual_leave_mode={mode} 계산에 {need} 가 필요합니다")
        leave_add += v
        other = "moel_3_12" if mode == "case_prorata" else "case_prorata"
        ov, onote = res[other]
        rows.append(AverageRow(calc, "annual_leave", f"연차휴가수당 {item.amount}", item.period_start, item.period_end, None,
                               v, v != 0, f"{mode}: {note}; 참고 {other}: {'-' if ov is None else ov} ({onote})"))
    alternatives = {m: (alts[m] if alt_ok[m] else None) for m in alts}
    if inp.annual_leave_pay:
        ctx.warn("연차휴가수당 산입(AW-06)은 불명확 — 귀속 안분(case_prorata, 2009다86246 적용례) "
                 f"{alternatives['case_prorata']} / 행정해석 3/12(moel_3_12) {alternatives['moel_3_12']} 중 "
                 f"{mode} 를 썼습니다. 2014다48057 은 '확정된 경우에 한하여' 원심을 수긍했습니다")

    wage_total = wages_sum + extra_sum - excluded_wages + bonus_add + leave_add
    if wage_total < 0:
        raise LaborError(f"평균임금: 임금총액이 음수입니다({wage_total}) — 제외기간 임금(wages)이 산정기간 임금보다 많습니다")
    if counted <= 0:
        # 원칙 산정이 여기서 멈추면 대체 산정기간(override_window)은 계산되지 않으므로 원칙 쪽에서는 권하지 않는다.
        hint = ("aw_long_exclusion_trigger(AW-09)를 검토하십시오" if calc == "principle"
                else "override_window 기간을 다시 정하십시오(AW-12)")
        raise LaborError(f"평균임금: 산정기간 {_fmt(start)}~{_fmt(end)} 이 전부 제외기간이라 산정할 수 없습니다 — {hint}")
    daily = wage_total / counted
    rows.append(AverageRow(calc, "total", "임금총액 ÷ 산입일수", start, end, counted, wage_total, True,
                           f"임금 {wages_sum} + 추가 {extra_sum} − 제외기간 임금 {excluded_wages} + 상여 {bonus_add} "
                           f"+ 연차 {leave_add} = {wage_total}; ÷ {counted}일 = {_settle(daily).normalize()}"))
    return WindowCalc(calc, O, start, end, window_days, ex_days, counted, wages_sum, extra_sum, excluded_wages,
                      bonus_total, bonus_add, leave_add, alternatives, wage_total, daily)


def _principle_window(inp: AverageWageInput, ctx: _Ctx, eff: list) -> tuple[date, date | None, date | None]:
    """AW-02·03·09 를 적용한 (발생일, 시작, 끝).

    발생일이 입사일이면(처음부터 그렇거나 AW-09 로 제외기간 최초일인 입사일로 옮겨진 경우) 산정기간이 없으므로
    (입사일, None, None) 을 돌려준다 — 호출자가 근로 첫날 규칙(AW-03, 특례 고시 제2조)을 적용한다.
    """
    o = ctx.o
    O = inp.occurrence_date
    blocks = _blocks(eff)
    for _ in range(50):
        if O == inp.hire_date:
            return O, None, None
        start, end, missing, short = window_bounds(O, inp.hire_date, o["aw_window_month_end"])
        if missing:
            ctx.warn(f"발생일 {_fmt(O)} 의 3개월 전 달에 같은 날짜가 없어 aw_window_month_end={o['aw_window_month_end']} 로 "
                     f"시작일 {_fmt(start)} 을 썼습니다 — 원문 근거 미확인(AW-02)")
        if short:
            ctx.trace.append(Trace("AW-03", "재직 3개월 미만", f"{_fmt(start)}~{_fmt(end)}", "입사일부터 발생일 전일까지"))
        window_days = days_inclusive(start, end)
        ex = _excluded_day_count(eff, start, end)
        hit = None
        if o["aw_long_exclusion_trigger"] == "window_fully_excluded":
            if ex == window_days:
                hit = next(b for b in blocks if b[0] <= end <= b[1])
        else:
            for b in reversed(blocks):
                if _overlap(b[0], b[1], start, end) and _three_months_long(*b):
                    hit = b
                    break
        if hit is None or hit[0] >= O:
            return O, start, end
        if hit[0] < inp.hire_date:
            raise LaborError(f"평균임금: 제외기간 최초일 {_fmt(hit[0])} 이 입사일 {_fmt(inp.hire_date)} 보다 앞섭니다 — "
                             "특례 고시 제1조(AW-09)로 발생일을 옮길 수 없으니 excluded_periods 의 start 를 확인하십시오")
        ctx.rows.append(AverageRow("principle", "shift", "제외기간 3개월 이상 — 발생일 변경", hit[0], hit[1],
                                   days_inclusive(*hit), None, False,
                                   f"발생일 {_fmt(O)} → 제외기간 최초일 {_fmt(hit[0])}(특례 고시 제1조, {o['aw_long_exclusion_trigger']})"))
        ctx.trace.append(Trace("AW-09", "발생일 변경", f"{_fmt(O)} → {_fmt(hit[0])}",
                               f"제외기간 {_fmt(hit[0])}~{_fmt(hit[1])}, 판정 {o['aw_long_exclusion_trigger']}"))
        ctx.warn(f"특례 고시 제1조로 발생일을 제외기간 최초일 {_fmt(hit[0])} 로 옮겼습니다 — '3개월 이상' 판정 방식"
                 f"({o['aw_long_exclusion_trigger']})은 불확정이고 고시(제2015-77호) 최신본 여부는 다시 확인하지 못했습니다")
        O = hit[0]
    raise LaborError("평균임금: 제외기간 특례 적용이 반복되어 끝나지 않습니다 — excluded_periods 를 확인하십시오")


def _first_day(inp: AverageWageInput, ctx: _Ctx, eff: list, O: date) -> WindowCalc:
    """근로 첫날 산정사유(AW-03, 특례 고시 제2조) — 입력 발생일이 입사일이거나 AW-09 로 입사일로 옮겨진 경우."""
    shifted = O != inp.occurrence_date
    probation = any(p.reason == "probation" and s <= O <= e for p, s, e in eff)
    probation_note = (" 수습기간 중 산정사유가 생긴 경우 수습기간을 제외기간으로 둘지(excluded_periods 에서 뺄지)는 "
                      "이 엔진이 판단하지 않으니 사람이 정하십시오." if probation else "")
    if inp.first_day_daily_wage is None:
        if not shifted:
            raise LaborError("평균임금: 근로 첫날 산정사유가 발생했습니다 — 약정 임금의 1일 평균액(first_day_daily_wage)을 "
                             "적어야 합니다(평균임금산정 특례 고시 제2조)")
        raise LaborError(f"평균임금: 특례 고시 제1조(AW-09)로 발생일 {_fmt(inp.occurrence_date)} 이 제외기간 최초일인 입사일 "
                         f"{_fmt(O)} 로 옮겨져 그 전 산정기간이 없습니다 — 근로 첫날 규칙(고시 제2조, AW-03)에 따라 약정 임금의 "
                         "1일 평균액(first_day_daily_wage)을 적으십시오." + probation_note)
    why = "특례 고시 제2조" + (" — 특례 고시 제1조(AW-09)로 발생일이 입사일로 옮겨짐" if shifted else "")
    principle = WindowCalc("principle", O, O, O - timedelta(days=1), 0, 0, 0, ZERO, ZERO, ZERO, ZERO, ZERO, ZERO,
                           {}, ZERO, inp.first_day_daily_wage)
    ctx.trace.append(Trace("AW-03", "근로 첫날 발생", str(inp.first_day_daily_wage), why + " — 약정 임금 1일 평균액"))
    ctx.rows.append(AverageRow("principle", "total", "근로 첫날 — 약정 임금 1일 평균액", O, O, 0,
                               inp.first_day_daily_wage, True, why))
    if shifted and probation:
        ctx.warn(f"수습기간을 제외기간으로 둔 채 발생일을 입사일 {_fmt(O)} 로 옮겨 first_day_daily_wage 를 썼습니다(AW-09·AW-03)."
                 + probation_note)
    return principle


def calculate_average_wage(inp: AverageWageInput, opts: dict, **deps) -> AverageWageResult:
    o = _read_options(opts)
    trace: list[Trace] = []
    warnings: list[str] = []
    rows: list[AverageRow] = []
    ctx = _Ctx(o, trace, warnings, rows)
    for key, spec in OPTIONS.items():
        v = o[key]
        trace.append(Trace(spec.rule, f"옵션 {key}", str(v), spec.choices.get(v, spec.description)))
    if inp.occurrence_from_last_working_day:
        trace.append(Trace("AW-02", "산정사유 발생일", _fmt(inp.occurrence_date),
                           "마지막 근무일 + 1일(퇴직연금복지과-954 '실제 퇴직일', 하급심 실무 — 대법원이 정한 것은 초일 불산입까지)"))
    else:
        trace.append(Trace("AW-02", "산정사유 발생일", _fmt(inp.occurrence_date), "입력 occurrence_date"))

    fn = deps.get("daily_ordinary_of")
    if fn is None:
        raise LaborError("평균임금: 통상임금 하한(AW-13) 비교에 1일 통상임금(deps daily_ordinary_of)이 필요합니다")

    eff = _effective_exclusions(inp, ctx)

    # ---- 원칙 산정
    O, start, end = _principle_window(inp, ctx, eff)
    if start is None:
        principle = _first_day(inp, ctx, eff, O)
    else:
        principle = _calc(inp, ctx, deps, eff, O, start, end, "principle")
        trace.append(Trace("AW-01", "원칙 1일 평균임금", str(_settle(principle.daily).normalize()),
                           f"{principle.wage_total} ÷ {principle.counted_days}일"))

    # ---- 대체 산정기간(AW-12)
    override = None
    if inp.override_window is not None:
        ow = inp.override_window
        if ow.start < inp.hire_date:
            raise LaborError(f"평균임금: override_window 시작일 {ow.start} 이 입사일보다 앞섭니다")
        override = _calc(inp, ctx, deps, eff, ow.end + timedelta(days=1), ow.start, ow.end, "override")
        trace.append(Trace("AW-12", "대체 산정기간 1일 평균임금", str(_settle(override.daily).normalize()),
                           f"{_fmt(ow.start)}~{_fmt(ow.end)} — {ow.reason}"))
        ctx.warn(f"대체 산정기간(AW-12) {_fmt(ow.start)}~{_fmt(ow.end)}: 원칙 {_settle(principle.daily).normalize()} / "
                 f"대체 {_settle(override.daily).normalize()} — 현저히 부적당한지(98다49357, 2014다48057)는 사람이 판단합니다"
                 + ("; apply: true 로 대체값을 썼습니다" if ow.apply else "; apply: false 로 원칙값을 썼습니다"))
    chosen = override if (override is not None and inp.override_window.apply) else principle

    # ---- 통상임금 하한(AW-13·14)
    ref = chosen.end if chosen.window_days else chosen.occurrence_date
    ordinary = dec(fn(ref))
    avg = chosen.daily
    lower = avg < ordinary
    compare = {
        "daily": lower,
        "three_month_total": (None if inp.ordinary_wage_total is None or not chosen.window_days
                              else chosen.wage_total < inp.ordinary_wage_total),
        "exceptional_only": lower and inp.ordinary_substitution_exceptional,
    }
    mode = o["aw_ordinary_compare_mode"]
    if mode == "three_month_total" and compare["three_month_total"] is None:
        raise LaborError("평균임금: aw_ordinary_compare_mode=three_month_total 이면 같은 기간 소정근로 대가 통상임금 총액"
                         "(ordinary_wage_total)이 필요합니다")
    applied = bool(compare[mode])
    raw_final = ordinary if applied else avg
    trace.append(Trace("AW-13", "1일 통상임금 비교", f"평균 {_settle(avg).normalize()} / 통상 {ordinary} (기준일 {_fmt(ref)})",
                       f"{mode}: {'통상임금 적용' if applied else '평균임금 유지'}; 방식별 {compare}"))
    decided = {k: v for k, v in compare.items() if v is not None}
    if len(set(decided.values())) > 1 or (lower and compare["three_month_total"] is None):
        ctx.warn(f"평균임금·통상임금 비교 방식(AW-14)이 불명확합니다 — 1일 평균 {_settle(avg).normalize()} < 1일 통상 {ordinary}; "
                 f"방식별 대체 여부 {compare}, {mode} 를 썼습니다(결정은 사람)")
    if applied and inp.unlisted_periods:
        extra = (f", 휴직 전 1일 평균임금 {inp.pre_absence_average_daily}" if inp.pre_absence_average_daily is not None else "")
        ctx.warn(f"비열거 기간(구속·직위해제 등)이 있는 산정기간에서 통상임금 {ordinary} 로 대체했습니다{extra} — "
                 "통상임금 대체도 현저히 부적당하면 휴직 전 3개월 기준으로 산정한 대법원 98다49357 이 있으니 "
                 "override_window(AW-12) 검토 필요(MR-4)")
    for u in inp.unlisted_periods:
        rows.append(AverageRow("principle", "unlisted", UNLISTED_REASONS[u.reason], u.start, u.end,
                               days_inclusive(u.start, u.end), None, True, "제외하지 않음(AW-10, 92다20309·2014다48057)"))
    if inp.unlisted_periods:
        ctx.warn("구속·직위해제·대기발령 기간은 산정기간에서 제외하지 않았습니다(AW-10) — 평균임금이 낮아지면 통상임금 하한과 MR-4 확인")

    final = _round_daily(raw_final, o["aw_round_avg_daily"])
    trace.append(Trace("RS-04", "1일 평균임금 끝수", f"{_settle(raw_final).normalize()} → {final}", o["aw_round_avg_daily"]))

    return AverageWageResult(
        rows=rows, total=ZERO, claims=[], trace=trace, warnings=warnings,
        original_occurrence_date=inp.occurrence_date, occurrence_date=chosen.occurrence_date,
        window_start=chosen.start, window_end=chosen.end, window_days=chosen.window_days,
        excluded_days=chosen.excluded_days, counted_days=chosen.counted_days, wage_total=chosen.wage_total,
        principle_daily=chosen.daily, ordinary_daily=ordinary, ordinary_applied=applied, compare_results=compare,
        average_daily_wage_raw=raw_final, average_daily_wage=final, principle=principle, override=override,
        override_applied=chosen is override, annual_leave_alternatives=chosen.annual_leave_alternatives,
    )
