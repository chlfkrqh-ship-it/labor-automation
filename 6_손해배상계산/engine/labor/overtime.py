"""연장·야간·휴일근로수당 재산정과 기지급 대비 차액 (lane: overtime, 규칙 OT-01~OT-22, M1~M11).

사건.yaml `overtime:` 절의 (a) 임금산정기간별 집계 시간 또는 (b) 일별 근무기록으로 가산 대상 시간을
구분하고, 그 날의 통상시급(deps `hourly_of(d)`)으로 법정수당을 다시 계산해 기지급 수당과 비교한다.
사업장 규모(deps `small_business(d)`, 상시 4명 이하면 True)는 조립 모듈이 넘긴다.
법적 판단(통상임금성, 휴일 해당 여부, 포괄임금 성립·유효, 간주합의 존부, 휴게시간 자유이용 여부,
시간의 증명 여부 등)은 하지 않는다. 사람이 판정해 입력한 값으로 계산만 한다.
금액 기대값은 판결 원문 숫자(서울중앙지방법원 2021. 9. 2. 선고 2020나38982)와 테스트 안의 Decimal
식으로 검증했다(tests/test_labor_overtime.py). 검증 판정(overtime_verify.json)이 조사 본문보다 우선한다.

---------------------------------------------------------------- 적용 범위
OT-01 [법령·하급심] 상시 4명 이하 기간은 연장·휴일 가산 0(제11조 제2항, 시행령 제7조 [별표 1]).
      야간 가산(제56조 제3항)도 기본 0 — 서울북부지방법원 2024. 9. 24. 선고 2022나44324 "[별표 1]에는 …
      야간근로에 대하여 통상임금의 100분의 50을 가산하여 지급할 것을 정하는 근로기준법 제56조 제3항이
      포함되어 있지 않다"(하급심, 별표 1 원문 미열람) → `ot_night_premium_under5`(false 기본).
      실근로 100% 기본분은 그대로 계산. 규모는 deps `small_business(d)`, 또는 입력 `headcount`
      (시행령 제7조의2 제1항 '1개월 연인원 ÷ 가동일수', 하급심 인용·조문 미열람, M7)가 있으면 그 값.
OT-02 [행정해석] 제63조 적용제외(`exempt_63`): 연장·휴일 가산 0, 휴일 판정·휴게 자동공제도 적용하지 않음,
      야간 가산은 적용 — 법제처-15-0344 "“감시ㆍ단속적 근로자”가 야간근로를 하는 경우에도 같은 법 제56조에
      따라 야간근로수당을 지급해야 합니다". 제3호(감시·단속적)는 `approved_on`(고용노동부장관 승인일) 이후만.
OT-03 [법령] 가산율 시점 분할 — 근로일(시업일) 2018. 3. 19.까지 구 제56조("연장근로 … 와 야간근로 … 또는
      휴일근로에 대하여는 통상임금의 100분의 50 이상을 가산", 2011다112391 본문 인용), 2018. 3. 20.부터
      현행 제56조 제2항 "1. 8시간 이내의 휴일근로: 통상임금의 100분의 50 2. 8시간을 초과한 휴일근로:
      통상임금의 100분의 100". 부칙 <법률 제15513호> 제1조 제5항(공포일 시행)은 검증 단계에서 원문 재확인
      실패(국가법령정보센터 오류) — 재확인 대상.
      둘째 분할축(검증 교정): 제2조 제1항 제7호 "‘1주’란 휴일을 포함한 7일" 규모별 시행일(부칙 제1조 제2항,
      2011다112391 보충의견) — `size_band` 300+ 2018. 7. 1., 50-299 2020. 1. 1., 30-49·5-29 2021. 7. 1.
      그 전 주는 휴일근로를 1주 40시간·12시간 한도에 넣지 않는다.
OT-04 [판례확립] 가산 대상 연장 = 실근로시간이 1일 8시간·1주 40시간을 넘는 시간(2020도15393, 94다26721
      "실제로 근로한 시간을 기초로"). 법정 기준시간은 상수가 아니라 입력(`standard_hours` 이력, `minor` 이면
      1일 7시간·1주 35시간 — 제69조, M2). 1주 기산 요일 `week_start` 는 사람이 입력(moelCgmExpc-18116
      "노사가 협의하여 … 정할 수 있음"). 같은 해석은 "소정 근로일과 휴일의 근로를 구분하지 않음"까지 이어진다.
OT-05 [실무관행] 1일 초과분과 1주 초과분 중복 제거(2011다112391 김재형 보충의견 "중복 지급은 이중평가"):
      주별로 daily_ot_d = max(h_d − 8, 0), weekly_ot = max(Σ min(h_d, 8) − 40, 0), 연장 = Σ daily_ot + weekly_ot.
      주 초과분을 어느 날에 배정할지 `ot_weekly_allocation`, 개정 1주 정의 시행 후 휴일근로를 40시간 합계에
      넣을지 `ot_holiday_in_weekly_40` — 둘 다 근거가 없어 **기본값이 없다**(검증 교정). 선택에 따라 결과가
      달라지는 사건이면 두 결과 합계를 적어 LaborError 로 선택을 요구한다. 결과가 같으면 선택 없이 계산한다.
      include 이면 휴일근로의 8시간 이내분을 합계에 넣되 주 초과분은 휴일 아닌 날에만 배정한다(휴일근로는
      제56조 제2항 가산만 — "제1항에도 불구하고"). 구 1주 정의 기간은 exclude 로 고정(OT-10).
OT-06 [판례확립] 1주 연장 한도 판정(표시용, 가산액 불변) — 2020도15393 "1일 8시간을 초과하였는지를 고려하지
      않고 1주간의 근로시간 중 40시간을 초과하는 근로시간을 기준으로 판단". 판결은 "(휴일을 제외한다 …)"로
      계산 → 구 1주 정의 기간은 휴일 제외, 시행 후는 전체. 한도 12시간, 5-29 규모 2021. 7. 1.~2022. 12. 31.
      특별연장 +8시간, 연소자 5시간. `result.weeks` 에 기록하고 초과면 warning.
OT-07 [판례확립] 법내 초과근로(소정 초과·법정 이내)는 가산 없음 — 97다14200 "이른바 법내 초과근로는 …
      할증임금을 지급할 필요가 없다". 기본분 100%만. 산식은 OT-05와 같은 일·주 중복 제거
      (소정 1일 `scheduled_*_hours`, 비번일은 기록의 `scheduled_hours: 0`).
      약정 가산은 약정 산정방법 전체가 법 기준을 충족할 때만(`agreed.valid`, 검증 교정 — 97다14200).
OT-08 [법령, 검증 확인불가] 단시간근로자 소정 초과근로 50% 가산(기간제법 제6조 제3항, 2014. 9. 19. 시행 후
      최초 초과근로부터, 상시 5인 이상). 검증에서 조문·부칙 원문을 열람하지 못해 기본값으로 쓰지 않는다 →
      `ot_part_time_premium`(off 기본 | daily | daily_weekly). 4명 이하 적용 여부 미확인 → 4명 이하는 0.
OT-09 [법령] 야간(22:00 이상 ~ 06:00 미만) 50%는 연장·휴일 가산과 별도로 더한다(제56조 제3항, 2019다261084
      "휴일근로와 야간근로 등이 실제 중복되는 구체적인 범위를 심리"). 야간시간도 근로자가 증명(2022다291153,
      검증 교정) → 기록별 `night_proven`.
OT-10 [판례확립·실무관행] 구법 휴일근로: 8시간 이내는 휴일 가산만(2011다112391 "휴일근로에 따른 가산임금과
      연장근로에 따른 가산임금은 중복하여 지급될 수 없다") [판례확립]. 8시간 초과분의 휴일+연장 중복 가산은
      대법원이 원심 계산방식을 수긍한 수준(90다6545 "원심의 계산방식은 … 각 각 가산하여 산정한 것임이
      명백하므로", 2012다23931) [실무관행] → `ot_pre2018_holiday_over8_add_ot`(true 기본, 하급심 다수).
OT-11 [판례확립·법령·행정해석] 휴일 = 주휴일·약정휴일(2016다9704)·근로자의 날·관공서 공휴일(제55조 제2항,
      규모별 시행 300+ 2020. 1. 1., 30-299 2021. 1. 1., 5-29 2022. 1. 1. — 시행 전 공휴일은 휴일 아님).
      적법한 휴일대체면 통상근로(99다7367, 공무원 사안). 대체 요건(검증 교정): 공휴일은 근로자대표 서면합의
      (제55조 제2항 단서 "근로자대표와 서면으로 합의한 경우", M3), 주휴·약정휴일은 근거 규정 또는 근로자 동의,
      모두 사전 특정·통지. 24시간 전 통지(근로기준정책과-7347 "적어도 24시간 전에 근로자에게 통지하여야",
      M9)는 `ot_substitution_notice_24h`(true 기본). 요건 불충족이면 휴일근로 + warning.
OT-12 [행정해석] 유급휴일 근로 250% 중 당연지급분 100%는 월급에 포함 — 엔진은 근로분 100%(기본분) + 가산만
      계산한다(근기 1455-14157).
OT-13 [행정해석] 역일을 넘는 연속근로는 시업일의 근로(근기 01254-20752 "계속되는 연장근로는 1근무로 취급하여
      시업시간이 속하는 날의 근로의 연속으로"). 휴일에 시작해 자정을 넘은 근로의 휴일 범위는 미해결 —
      `ot_holiday_boundary`: shift_start_day(기본, 2020나38982가 12시간 전체를 휴일근로로 계산) |
      calendar_day(자정에서 나눔 — 두 날의 휴일 여부가 다를 때만, 뒷부분은 다음 날 근로로 귀속).
OT-14 [판례확립·하급심] 실근로 = 근로구간 − 휴게. 휴게라도 자유이용이 보장되지 않았으면 공제하지 않음
      (부산고등법원(창원) 2017나24321, 대법원 2020다212262 상고기각 "실질적으로 자유로운 이용이 보장되었던
      것으로 보기 어렵고", M8) → 휴게 구간별 `free`. 연장 4시간마다 30분 자동 공제는 `ot_assume_ot_break`
      (false 기본 — 2020도15393은 "포함되었을 여지가 커 보인다"고만 함).
OT-15 [판례확립] 취사선택 금지 — 법정 통상시급·법정 시간·법정 가산율로 전체를 산정(A_legal)하고, 약정 통상시급·
      약정 가산율 전체로 산정(A_contract)해 기간 전체를 비교한다. 법정 통상시급 × 약정 가산율 조합은 만들지
      않는다(2006다81523, 2019다261084 "통상임금의 범위뿐 아니라 가산율 역시 근로기준법에서 정한 기준을
      적용하였어야"). `ot_claim_basis`: legal(기본) | contract | greater(전체 합계가 큰 쪽).
OT-16 [판례확립] 간주 시간외근로 합의가 해당 기간에 **존재한다고 입력된 경우에만** 시간 = max(실근로, 합의시간)
      (2006다81523 "실제 근무시간이 위 합의한 시간에 미달함을 이유로 근무시간을 다투는 것이 허용되지 아니한다").
      합의가 없으면 증명된 실제 시간만(2022다291153 "실제 연장근로시간은 연장근로수당의 지급을 청구하는
      근로자가 증명하여야", M4) — 기록·집계별 `proven: false` 는 계산에서 빼고 따로 집계한다.
OT-17 [판례확립] 포괄임금(검증 교정 3분기) `inclusive_wage`: valid_hard_to_measure → 차액 0(2008다6052 "근로시간의
      산정이 어려운 경우 … 차액을 청구하는 것은 받아들일 수 없다", M5) | invalid_measurable → 미달분만 무효,
      법정수당 − 정액수당 | not_formed → 법정수당 − 명목 기지급 수당(2023다221359 "미달하는 부분이 있다면 …
      그 미달하는 차액을 지급할 의무가 있을 뿐"). 정액수당은 기간별 `paid.lump`.
OT-18 [불명확] 비교 단위와 초과 지급분 충당 — **기본값 없음**(결과를 예단하지 않음). 결과가 달라지면
      선택지별 합계를 적어 LaborError. `ot_overpayment_character`(검증 교정: 약정 산정방법이 법 기준에 비추어
      유효한지로 판정):
        erroneous   무효인 산정방법에 따른 지급 → 같은 청구기간의 다른 기간·다른 항목 부족분에 충당
                    (94다26721 "상계나 그 충당을 주장하는 것도 허용된다", 95다2227 "다른 법정수당의 초과지급
                    부분", 97다14200 "그 초과 부분은 잘못 지급된 것"). 월별 0 처리와의 조합은 두지 않는다
                    (대법원이 두 번 파기 — 검증 교정).
        contractual 유효한 약정에 따른 초과지급 → 다른 항목 공제 불허(부산고등법원(창원) 2017나24321 "초과지급한
                    다른 항목의 법정수당 등이 공제되어야 한다고 할 수는 없으므로", 2020다212262 상고기각).
                    `ot_compare_unit`(month | pay_unit[`compare_units`] | whole_period) 안에서 같은 항목끼리만.
      충당 순서는 지급기일이 먼저 온 부족분부터(민법 제477조 법정충당의 이행기 순서를 따름 — 판례 미확인).
      정액수당(lump)이 있는 기간은 항목을 나눌 수 없어 합계로 비교한다.
OT-19 [하급심] 배수 구조 — 기본분(100%)이 이미 지급된 시간은 가산분만(입력 `base_paid`), 아니면 100% + 가산.
      표시·끝수 구조 `ot_multiplier_structure`: split(기본분 줄과 가산분 줄 분리, 기본 — 2020나38982
      "기본임금 99,936원 … + 연장근로 가산임금 16,656원 … + 야간근로 가산임금 33,312원", 항소심 2017나24321
      "(시간급 통상임금 × 야간근로시간 × 50%)") | combined(1.5·2.0 배수 한 줄). 창원 1심의 휴일 중복할증
      (200%−150%) 산식은 항소심에서 청구 취하되어 근거에서 뺐다(검증 교정).
OT-20 [판례확립] 고정수당 포함 월급의 시급 환산(2015다73067)은 통상임금 모듈 몫 — 이 모듈은 `hourly_of` 를 받기만.
OT-21 [불명확, 검증 확인불가] 끝수: 법령 규정 없음. `ot_hourly_rounding`(none 기본 — common.py 중간값 정밀도
      유지), `ot_amount_rounding`(floor 기본 | half_up | ceil | floor10 | ceil10 — 2020나38982의 원고 계산
      "일의 자리에서 올림"은 ceil10), `ot_rounding_stage`(line 기본 | item), 시간 끝수 `ot_hours_rounding`
      (none 기본 | floor_2dp | floor_1dp | floor_int — 2017나24321 243시간 버림, 2022다291153 23.78시간, M11).
      의정부고양 2014가합53189 "516,517원(= 6,622원 × 1.5 × 52시간)"은 곱이 516,516원이라 기대값으로 쓰지 않음.
OT-22 [법령, 검증 확인불가] 임금채권 3년(제49조). 기산점 판결 미확인 — 절단하지 않고 Claim.note 에
      '소 제기일과 대조' 표시, 판단은 지연손해금 모듈.

---------------------------------------------------------------- 누락 규칙(verify missed_rules) 처리
M1  탄력적·선택적 근로시간제 — 산정 방식 미확인 → 구현하지 않음. `flexible_periods` 안의 일별 기록은 LaborError
    (집계 방식 (a)로 사람이 산정한 시간을 넣어야 함).
M2  연소근로자 1일 7시간·1주 35시간(제69조), 한도 1주 5시간 — `minor` 로 구현.
M3  공휴일 대체 근로자대표 서면합의 — OT-11 로 구현.
M4  간주합의 부존재 시 증명책임 — `proven`/`night_proven` 으로 구현, 미증명 시간은 행 `unproven_hours`·warning.
M5  유효 포괄임금 게이트 — OT-17 로 구현.
M6  2024. 12. 19. 통상임금 법리 변경(2023다302838) — 시급 분할은 통상임금 모듈(`hourly_of`) 몫. 청구기간이
    그날을 걸치면 warning 만.
M7  상시근로자수 산정 — `headcount`(기간별 연인원·가동일수)로 구현. '법 적용 사유 발생일 전 1개월' 구간 설정은
    사람이 한다.
M8  휴게시간 실질 — OT-14 로 구현.   M9  휴일대체 24시간 전 통지 — OT-11 로 구현.
M10 법정 1주 기준시간 연혁(44→40, 규모별 시행일 미확인) — `standard_hours` 이력 입력으로 구현, 상수 없음.
    2011. 7. 1. 전 날짜가 있는데 이력이 없으면 warning.
M11 시간·일수 끝수 — `ot_hours_rounding`. 일수 끝수(월 평균 주휴일수 등)는 통상임금 모듈 몫.

---------------------------------------------------------------- 사건.yaml `overtime:` 절
    overtime:
      week_start: monday             # 1주 기산 요일(일별 기록이 있으면 필수) monday … sunday | 0~6 | 월 … 일
      size_band: "5-29"              # 300+ | 50-299 | 30-49 | 5-29 | under5, 또는 [{from: 2019-01-01, band: "50-299"}]
      standard_hours: []             # [{from: 2004-07-01, daily: 8, weekly: 40}] 법정 기준시간 이력(비우면 8/40)
      minor: false                   # 연소근로자(7/35)
      scheduled_daily_hours: 8       # 1일 소정근로시간(비우면 법정 1일 기준)
      scheduled_weekly_hours: 40     # 1주 소정근로시간(비우면 법정 1주 기준)
      part_time: false               # 단시간근로자(OT-08)
      base_paid: false               # 초과시간 기본분 100% 기지급 여부(기간·기록별로 덮어씀)
      inclusive_wage: none           # none | valid_hard_to_measure | invalid_measurable | not_formed
      claim_from: 2018-02-01         # 청구 대상 기간(비우면 입력 전부). 밖의 기록은 주 40시간 판정에만 씀
      claim_to: 2018-05-31
      pay_day: 25                    # 비우면 worker.pay_day (필수)
      pay_month_offset: 0            # 비우면 worker.pay_month_offset, 그것도 없으면 0
      pay_period_start_day: 1        # 비우면 worker.pay_period_start_day, 그것도 없으면 1
      exempt_63: [{from: 2019-01-01, to: null, category: 3, approved_on: 2019-03-01}]
      headcount: [{from: 2019-01-01, to: 2019-12-31, person_days: 90, operating_days: 22}]
      flexible_periods: []           # [[2020-01-01, 2020-06-30]] 탄력적·선택적 근로시간제 기간
      agreed_hours:                  # OT-16 간주 시간외근로 합의(존재한다고 사람이 판단한 기간만)
        - {from: 2019-01-01, to: 2019-12-31, overtime: 20, night: 0, holiday_le8: 0, holiday_gt8: 0}
      agreed:                        # OT-15 약정 기준(없으면 비움)
        valid: true                  # 약정 산정방법 전체가 법 기준을 충족하는지(사람 판단)
        hourly: [{from: 2018-01-01, amount: 9000}]
        rates: {overtime: 0.5, in_law: 0, night: 0.5, holiday_le8: 0.5, holiday_gt8: 1.0, holiday_gt8_ot: 0, part_time: 0}
      compare_units: [[2018-01-01, 2018-12-31]]   # ot_compare_unit=pay_unit 일 때 약정 임금 산정 단위기간
      months:                        # (a) 임금산정기간별 집계
        - period: "2020-03"          # 임금산정기간 시작 달(YYYY-MM)
          from: null                 # 기간 안에서 가산율·시급·규모가 바뀌면 from/to 로 나눠 여러 줄
          to: null
          overtime_hours: 20         # 가산 대상 연장(1일·1주 중복 제거 후)
          in_law_hours: 0            # 법내 초과(단시간이면 소정 초과시간)
          night_hours: 10
          holiday_le8_hours: 8
          holiday_gt8_hours: 2
          overtime_night_hours: 2    # 중복 시간(표시용)
          holiday_night_hours: 0
          base_paid: null
          proven: true
          paid: {overtime: 300000, night: 40000, holiday: 120000, lump: 0}
      days:                          # (b) 일별 근무기록(한 줄 = 한 근무)
        - date: 2018-02-19
          start: "20:00"             # 따옴표 권장(YAML 1.1 은 20:00 을 1200 으로 읽음 — 정수는 분으로 봄)
          end: "08:00"               # start 이하면 다음 날
          breaks: [{start: "00:00", end: "01:00", free: true}]
          break_minutes: 0           # 위치 모르는 휴게(야간시간에서는 빼지 않음)
          hours: null                # 시각 대신 실근로시간(이때 night_hours 로 야간시간)
          night_hours: null
          holiday: false
          holiday_kind: null         # weekly | agreed | labor_day | public
          next_day_holiday: false    # ot_holiday_boundary=calendar_day 에서 다음 날 휴일 여부
          substitution: {basis: true, worker_rep_agreement: null, notice_at: "2018-02-10 09:00"}
          scheduled_hours: 0         # 그날 소정근로시간(비번일 0)
          base_paid: null
          proven: true
          night_proven: true
      paid:                          # (b) 방식의 기간별 기지급 수당
        - {period: "2018-02", overtime: 210840, night: 0, holiday: 0, lump: 45180}
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal, InvalidOperation

from .common import (
    Claim,
    LaborError,
    OptionSpec,
    Trace,
    dec,
    is_within,
    parse_date,
    pay_date_for,
    pay_periods,
    round_to,
)

__all__ = [
    "ITEMS", "OPTIONS", "RULES", "SIZE_BANDS",
    "AgreedHours", "AgreedTerms", "BreakInput", "DayRecord", "MonthEntry", "OvertimeInput", "OvertimeLine",
    "OvertimeResult", "OvertimeRow", "PaidInput", "SubstitutionInput", "WeekCheck",
    "calculate_overtime", "load_overtime",
]

ZERO = Decimal(0)
ONE = Decimal(1)
HALF = Decimal("0.5")
SIXTY = Decimal(60)

DATE_2018_AMEND = date(2018, 3, 20)      # 제56조 개정(법률 제15513호) 공포일
DATE_PT_PREMIUM = date(2014, 9, 19)      # 기간제법 제6조 제3항 시행
DATE_ORDINARY_2024 = date(2024, 12, 19)  # 2023다302838 전원합의체
DATE_OLD_STANDARD_WARN = date(2011, 7, 1)
DATE_SPECIAL_EXT = (date(2021, 7, 1), date(2022, 12, 31))

ITEMS = ("overtime", "night", "holiday")
ITEM_LABELS = {"overtime": "연장", "night": "야간", "holiday": "휴일", "lump": "정액", "all": "합계"}

SIZE_BANDS = {
    #            1주=휴일 포함 7일 시행   공휴일 유급휴일 시행
    "300+": (date(2018, 7, 1), date(2020, 1, 1)),
    "50-299": (date(2020, 1, 1), date(2021, 1, 1)),
    "30-49": (date(2021, 7, 1), date(2021, 1, 1)),
    "5-29": (date(2021, 7, 1), date(2022, 1, 1)),
    "under5": (None, None),
}

WEEKDAYS = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6,
    "mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6,
    "월": 0, "화": 1, "수": 2, "목": 3, "금": 4, "토": 5, "일": 6,
}

HOLIDAY_KINDS = {
    "weekly": "주휴일(제55조 제1항)",
    "agreed": "단체협약·취업규칙 등 약정휴일(2016다9704)",
    "labor_day": "근로자의 날",
    "public": "관공서 공휴일(제55조 제2항, 규모별 시행)",
}

INCLUSIVE = {
    "none": "포괄임금 약정 없음",
    "valid_hard_to_measure": "근로시간 산정 곤란 — 유효한 포괄임금, 차액 청구 불가(2008다6052)",
    "invalid_measurable": "산정 곤란 아닌 포괄임금 — 미달분만 무효(2008다6052)",
    "not_formed": "포괄임금 불성립 — 명목 기지급 수당 공제(2023다221359)",
}

CATEGORY_LABELS = {
    "base": "기본분(100%)",
    "overtime": "연장 가산",
    "in_law": "법내 초과",
    "part_time": "단시간 소정 초과 가산",
    "holiday_le8": "휴일 8시간 이내 가산",
    "holiday_gt8": "휴일 8시간 초과 가산",
    "holiday_gt8_ot": "휴일 8시간 초과 연장 가산(구법)",
    "night": "야간 가산",
}

OPTIONS: dict[str, OptionSpec] = {s.key: s for s in [
    OptionSpec("ot_night_premium_under5", False, "상시 4명 이하 기간의 야간 가산", "OT-01", {
        False: "야간 가산도 미적용(서울북부지방법원 2022나44324 — 별표 1에 제56조 제3항 미포함)",
        True: "야간 가산 적용",
    }),
    OptionSpec("ot_holiday_in_weekly_40", "unset", "개정 1주 정의 시행 후 휴일근로를 1주 40시간 합계에 넣는지", "OT-05", {
        "unset": "정하지 않음 — 결과가 달라지면 오류로 선택 요구(근거 없음, 검증 교정)",
        "exclude": "넣지 않음",
        "include": "8시간 이내분을 넣음(moelCgmExpc-18116 '소정 근로일과 휴일의 근로를 구분하지 않음'), 주 초과분은 평일에 배정",
    }),
    OptionSpec("ot_weekly_allocation", "unset", "1주 40시간 초과분을 배정할 날", "OT-05", {
        "unset": "정하지 않음 — 결과가 달라지면 오류로 선택 요구(근거 없음, 검증 교정)",
        "last_days_first": "주의 마지막 근로일부터 거꾸로",
        "chronological": "주의 첫 근로일부터",
    }),
    OptionSpec("ot_pre2018_holiday_over8_add_ot", True, "2018. 3. 19.까지 휴일 8시간 초과분에 연장 가산 중복", "OT-10", {
        True: "휴일 50% + 연장 50%(90다6545·2012다23931 원심 방식 수긍, 하급심 다수)",
        False: "휴일 50%만",
    }),
    OptionSpec("ot_holiday_boundary", "shift_start_day", "휴일에 시작해 자정을 넘은(또는 휴일로 넘어간) 근로의 휴일 범위", "OT-13", {
        "shift_start_day": "시업일 기준 한 근무 전체(2020나38982 관찰)",
        "calendar_day": "자정에서 나눠 각 날짜의 휴일 여부로",
    }),
    OptionSpec("ot_assume_ot_break", False, "연장 4시간마다 30분 휴게 자동 공제", "OT-14", {
        False: "입력한 휴게만 공제",
        True: "휴게 부여 사실이 인정된 경우 — 1일 기준 초과 4시간마다 30분 공제(2020도15393)",
    }),
    OptionSpec("ot_substitution_notice_24h", True, "휴일대체 통지 24시간 전 요건", "OT-11", {
        True: "휴일 시작 24시간 전까지 통지해야 적법(근로기준정책과-7347)",
        False: "휴일 전에 통지했으면 적법",
    }),
    OptionSpec("ot_part_time_premium", "off", "단시간근로자 소정 초과근로 50% 가산(기간제법 제6조 제3항)", "OT-08", {
        "off": "적용 안 함 — 검증 확인불가라 기본값으로 쓰지 않음(사람 확인 후 켬)",
        "daily": "1일 소정 초과분만",
        "daily_weekly": "1일 소정 초과분 + 1주 소정 초과분(중복 제거)",
    }),
    OptionSpec("ot_claim_basis", "legal", "법정 기준 전체와 약정 기준 전체 중 청구 기준", "OT-15", {
        "legal": "법정 통상시급·법정 가산율 전체(2019다261084)",
        "contract": "약정 통상시급·약정 가산율 전체(약정수당 청구 — 별개 청구원인)",
        "greater": "두 전체 합계 중 큰 쪽(항목별 혼합 없음)",
    }),
    OptionSpec("ot_overpayment_character", "unset", "기지급 초과분의 성격(약정 산정방법의 유효성)", "OT-18", {
        "unset": "정하지 않음 — 초과지급이 있어 결과가 달라지면 오류로 선택 요구",
        "erroneous": "무효 산정방법에 따른 착오 지급 — 다른 기간·항목에 충당(94다26721, 95다2227, 97다14200)",
        "contractual": "유효 약정에 따른 초과지급 — 다른 항목 공제 불허(부산고등법원(창원) 2017나24321)",
    }),
    OptionSpec("ot_compare_unit", "unset", "contractual 일 때 같은 항목 안의 비교 단위", "OT-18", {
        "unset": "정하지 않음 — 결과가 달라지면 오류로 선택 요구",
        "month": "임금산정기간별",
        "pay_unit": "약정 임금 산정 단위기간(compare_units)",
        "whole_period": "청구기간 전체",
    }),
    OptionSpec("ot_multiplier_structure", "split", "배수 줄 구조", "OT-19", {
        "split": "기본분 줄과 가산분 줄을 나눔(2020나38982 표기)",
        "combined": "기본분+가산분 배수를 한 줄로(1.5배·2.0배)",
    }),
    OptionSpec("ot_hourly_rounding", "none", "통상시급 끝수", "OT-21", {
        "none": "끝수 그대로",
        "floor": "원 미만 버림",
        "half_up": "원 미만 반올림",
        "floor_1dp": "0.1원 미만 버림",
    }),
    OptionSpec("ot_amount_rounding", "floor", "금액 끝수", "OT-21", {
        "floor": "원 미만 버림",
        "half_up": "원 미만 반올림",
        "ceil": "원 미만 올림",
        "floor10": "10원 미만 버림",
        "ceil10": "일의 자리에서 올림",
    }),
    OptionSpec("ot_rounding_stage", "line", "금액 끝수처리 단계", "OT-21", {
        "line": "줄마다(시간 × 시급 × 배수)",
        "item": "임금산정기간의 항목(연장·야간·휴일) 합계에서 한 번",
    }),
    OptionSpec("ot_hours_rounding", "none", "줄별 시간 끝수", "OT-21", {
        "none": "끝수 그대로",
        "floor_2dp": "소수 셋째 자리 이하 버림",
        "floor_1dp": "소수 둘째 자리 이하 버림",
        "floor_int": "1시간 미만 버림",
    }),
]}

RULES: dict[str, tuple[str, str]] = {
    "OT-01": ("상시 4명 이하 기간은 연장·휴일·야간 가산 0(야간은 옵션)", "법령·하급심"),
    "OT-02": ("제63조 적용제외: 연장·휴일 가산·휴일 판정·휴게 미적용, 야간 가산 적용", "행정해석"),
    "OT-03": ("가산율 2018. 3. 20. 분할, 1주 정의는 규모별 시행일로 별도 분할", "법령"),
    "OT-04": ("연장 = 실근로 1일 8시간·1주 40시간 초과, 기준시간·기산 요일은 입력", "판례확립"),
    "OT-05": ("1일 초과분과 1주 초과분 중복 제거, 배정·휴일 합산은 선택 강제", "실무관행"),
    "OT-06": ("1주 연장 한도(휴일 제외 여부는 1주 정의 시행일) — 표시만", "판례확립"),
    "OT-07": ("법내 초과근로는 기본분만, 약정 가산은 약정 전체 유효 시", "판례확립"),
    "OT-08": ("단시간근로자 소정 초과 50% 가산(검증 확인불가 → 옵션)", "법령"),
    "OT-09": ("야간 50% 별도 중복 가산, 야간시간 증명 플래그", "법령"),
    "OT-10": ("구법 휴일 8시간 이내 연장 중복 불가(확립), 8시간 초과 중복 가산(실무관행)", "판례확립·실무관행"),
    "OT-11": ("휴일 범위·공휴일 규모별 시행·휴일대체 요건(서면합의·24시간 통지)", "판례확립·법령·행정해석"),
    "OT-12": ("유급휴일 근로의 당연지급분은 월급 포함 — 근로분 100% + 가산만", "행정해석"),
    "OT-13": ("역일을 넘는 연속근로는 시업일 귀속, 휴일 경계는 옵션", "행정해석"),
    "OT-14": ("휴게 공제(자유이용 보장된 휴게만), 연장 휴게 자동 공제는 옵션", "판례확립·하급심"),
    "OT-15": ("법정 전체와 약정 전체 비교, 요소별 취사선택 금지", "판례확립"),
    "OT-16": ("간주합의 존재 입력 시 합의시간 하한", "판례확립"),
    "OT-17": ("포괄임금 유효(차액 0)·미달분 무효·불성립 3분기", "판례확립"),
    "OT-18": ("비교 단위·초과지급 충당 — 기본값 없음", "불명확"),
    "OT-19": ("기본분 기지급 여부에 따른 배수, 줄 구조 옵션", "하급심"),
    "OT-20": ("고정수당 포함 월급 시급 환산 — 통상임금 모듈", "판례확립"),
    "OT-21": ("시급·금액·시간 끝수 옵션", "불명확"),
    "OT-22": ("임금채권 3년 — 절단하지 않고 표시", "법령"),
    "M1": ("탄력적·선택적 근로시간제 연장 산정 — 미구현(일별 기록 오류)", "불명확"),
    "M2": ("연소근로자 1일 7시간·1주 35시간, 한도 5시간", "법령"),
    "M3": ("공휴일 대체는 근로자대표 서면합의", "법령"),
    "M4": ("간주합의 없으면 연장·야간시간은 근로자 증명", "판례확립"),
    "M5": ("유효 포괄임금이면 차액 청구 불가", "판례확립"),
    "M6": ("2024. 12. 19. 통상임금 법리 변경 시점 — 시급 모듈 몫, 걸치면 경고", "판례확립"),
    "M7": ("상시근로자수 = 연인원 ÷ 가동일수", "하급심"),
    "M8": ("자유이용이 보장되지 않은 휴게는 근로시간", "하급심"),
    "M9": ("휴일대체 24시간 전 통지", "행정해석"),
    "M10": ("법정 1주 기준시간 연혁은 입력 이력", "불명확"),
    "M11": ("시간 단위 끝수", "불명확"),
}


# ================================================================ 입력
@dataclass
class BreakInput:
    start: int              # 분(당일 0시 기준, 다음 날이면 1440 이상으로 보정)
    end: int
    free: bool = True


@dataclass
class SubstitutionInput:
    basis: bool | None = None                 # 근거 규정 또는 근로자 동의(주휴·약정휴일)
    worker_rep_agreement: bool | None = None  # 근로자대표 서면합의(공휴일)
    notice_at: datetime | None = None


@dataclass
class DayRecord:
    date: date
    start: int | None = None
    end: int | None = None
    hours: Decimal | None = None
    night_hours: Decimal | None = None
    breaks: list = field(default_factory=list)
    break_minutes: Decimal = ZERO
    holiday: bool = False
    holiday_kind: str | None = None
    next_day_holiday: bool = False
    substitution: SubstitutionInput | None = None
    scheduled_hours: Decimal | None = None
    base_paid: bool | None = None
    proven: bool = True
    night_proven: bool = True
    note: str = ""


@dataclass
class PaidInput:
    overtime: Decimal = ZERO
    night: Decimal = ZERO
    holiday: Decimal = ZERO
    lump: Decimal = ZERO

    @property
    def total(self) -> Decimal:
        return self.overtime + self.night + self.holiday + self.lump


@dataclass
class MonthEntry:
    key: str
    start: date | None = None
    end: date | None = None
    overtime_hours: Decimal = ZERO
    in_law_hours: Decimal = ZERO
    night_hours: Decimal = ZERO
    holiday_le8_hours: Decimal = ZERO
    holiday_gt8_hours: Decimal = ZERO
    overtime_night_hours: Decimal = ZERO
    holiday_night_hours: Decimal = ZERO
    base_paid: bool | None = None
    proven: bool = True
    paid: PaidInput | None = None
    note: str = ""


@dataclass
class AgreedHours:
    start: date
    end: date | None
    overtime: Decimal = ZERO
    night: Decimal = ZERO
    holiday_le8: Decimal = ZERO
    holiday_gt8: Decimal = ZERO


@dataclass
class AgreedTerms:
    valid: bool
    hourly: list                 # [(from, amount)]
    rates: dict


@dataclass
class OvertimeInput:
    pay_day: int
    pay_month_offset: int = 0
    pay_period_start_day: int = 1
    week_start: int | None = None
    size_band: list = field(default_factory=list)       # [(from|None, band)]
    standard_hours: list = field(default_factory=list)  # [(from, daily, weekly)]
    minor: bool = False
    scheduled_daily_hours: Decimal | None = None
    scheduled_weekly_hours: Decimal | None = None
    part_time: bool = False
    base_paid: bool = False
    inclusive_wage: str = "none"
    claim_from: date | None = None
    claim_to: date | None = None
    exempt_63: list = field(default_factory=list)       # [(from, to, category, approved_on)]
    headcount: list = field(default_factory=list)       # [(from, to, person_days, operating_days)]
    flexible_periods: list = field(default_factory=list)
    agreed_hours: list = field(default_factory=list)
    agreed: AgreedTerms | None = None
    compare_units: list = field(default_factory=list)
    months: list = field(default_factory=list)
    days: list = field(default_factory=list)
    paid: dict = field(default_factory=dict)            # key -> PaidInput


# ================================================================ 결과
@dataclass
class OvertimeLine:
    """계산 한 줄. kind: base(기본분) | premium(가산분) | combined(배수 합산)."""

    basis: str           # legal | contract
    item: str            # overtime | night | holiday
    category: str
    kind: str
    label: str
    hours: Decimal
    hourly: Decimal
    multiplier: Decimal
    amount: Decimal      # 줄 단계 끝수처리(ot_rounding_stage=item 이면 끝수 전 값)


@dataclass
class WeekCheck:
    """1주 연장 한도 판정(OT-06) — 가산액과 무관한 표시용."""

    week_start: date
    week_end: date
    limit_basis_hours: Decimal     # 한도 판정 합계(구 1주 정의면 휴일 제외)
    limit_overtime_hours: Decimal  # 합계 − 1주 기준시간
    limit: Decimal
    violation: bool
    premium_overtime_hours: Decimal  # OT-05 가산 대상 연장시간(대조용)
    holiday_included: bool


@dataclass
class OvertimeRow:
    key: str
    period_start: date
    period_end: date
    due_date: date
    overtime_hours: Decimal
    in_law_hours: Decimal
    part_time_hours: Decimal
    night_hours: Decimal
    holiday_le8_hours: Decimal
    holiday_gt8_hours: Decimal
    overtime_night_hours: Decimal
    holiday_night_hours: Decimal
    unproven_hours: Decimal
    lines: list
    contract_lines: list
    legal_by_item: dict
    contract_by_item: dict | None
    legal_amount: Decimal
    contract_amount: Decimal | None
    amount_by_item: dict
    amount: Decimal              # 선택된 기준(ot_claim_basis)의 재산정 수당
    paid: PaidInput
    paid_total: Decimal
    diff: Decimal                # amount − paid_total(음수 가능)
    claim_amount: Decimal        # 비교 단위·충당 적용 후 청구액
    note: str


@dataclass
class OvertimeResult:
    rows: list
    total: Decimal
    claims: list
    trace: list
    warnings: list
    extra_wages: dict = field(default_factory=dict)
    weeks: list = field(default_factory=list)
    alternatives: dict = field(default_factory=dict)
    basis: str = "legal"
    legal_total: Decimal = ZERO
    contract_total: Decimal | None = None
    method: str = ""


# ================================================================ 읽기
_TOP_KEYS = {
    "week_start", "size_band", "standard_hours", "minor", "scheduled_daily_hours", "scheduled_weekly_hours",
    "part_time", "base_paid", "inclusive_wage", "claim_from", "claim_to", "pay_day", "pay_month_offset",
    "pay_period_start_day", "exempt_63", "headcount", "flexible_periods", "agreed_hours", "agreed",
    "compare_units", "months", "days", "paid",
}
_MONTH_KEYS = {
    "period", "from", "to", "overtime_hours", "in_law_hours", "night_hours", "holiday_le8_hours",
    "holiday_gt8_hours", "overtime_night_hours", "holiday_night_hours", "base_paid", "proven", "paid", "note",
}
_DAY_KEYS = {
    "date", "start", "end", "hours", "night_hours", "breaks", "break_minutes", "holiday", "holiday_kind",
    "next_day_holiday", "substitution", "scheduled_hours", "base_paid", "proven", "night_proven", "note",
}
_PAID_KEYS = {"overtime", "night", "holiday", "lump"}
_RATE_KEYS = {"overtime", "in_law", "night", "holiday_le8", "holiday_gt8", "holiday_gt8_ot", "part_time"}


def _err(msg: str) -> LaborError:
    return LaborError(f"시간외수당: {msg}")


def _num(v, label: str, default=None) -> Decimal | None:
    if v is None or v == "":
        return default
    if isinstance(v, bool):
        raise _err(f"{label} 은(는) 숫자여야 합니다: {v!r}")
    try:
        return dec(v)
    except (InvalidOperation, ValueError, TypeError):
        raise _err(f"{label} 은(는) 숫자여야 합니다: {v!r}") from None


def _nonneg(v, label: str, default=ZERO) -> Decimal:
    n = _num(v, label, default)
    if n is not None and n < 0:
        raise _err(f"{label} 은(는) 음수일 수 없습니다: {v!r}")
    return n


def _date(v, label: str) -> date | None:
    if v is None or v == "":
        return None
    try:
        return parse_date(v)
    except (ValueError, TypeError):
        raise _err(f"{label} 날짜 형식이 올바르지 않습니다: {v!r}") from None


def _bool(v, label: str, default=None):
    if v is None or v == "":
        return default
    if isinstance(v, bool):
        return v
    raise _err(f"{label} 은(는) true/false 여야 합니다: {v!r}")


def _int(v, label: str, lo: int, hi: int, default=None) -> int | None:
    if v is None or v == "":
        return default
    try:
        n = int(v)
    except (ValueError, TypeError):
        raise _err(f"{label} 은(는) {lo}~{hi} 정수여야 합니다: {v!r}") from None
    if isinstance(v, bool) or not lo <= n <= hi or (isinstance(v, (float, Decimal)) and n != v):
        raise _err(f"{label} 은(는) {lo}~{hi} 정수여야 합니다: {v!r}")
    return n


def _clock(v, label: str) -> int | None:
    """'HH:MM' → 분. YAML 1.1 이 20:00 을 1200(60진수)으로 읽으므로 정수는 분으로 본다."""
    if v is None or v == "":
        return None
    if isinstance(v, bool):
        raise _err(f"{label} 시각 형식이 올바르지 않습니다: {v!r}")
    if isinstance(v, int):
        m = v
    elif isinstance(v, time):
        m = v.hour * 60 + v.minute
    else:
        s = str(v).strip()
        try:
            hh, mm = s.split(":")[:2]
            m = int(hh) * 60 + int(mm)
            if not 0 <= int(mm) < 60:
                raise ValueError
        except ValueError:
            raise _err(f"{label} 시각은 'HH:MM' 이어야 합니다: {v!r}") from None
    if not 0 <= m <= 1440:
        raise _err(f"{label} 시각은 00:00~24:00 이어야 합니다: {v!r}")
    return m


def _datetime(v, label: str) -> datetime | None:
    if v is None or v == "":
        return None
    if isinstance(v, datetime):
        return v
    if isinstance(v, date):
        return datetime(v.year, v.month, v.day)
    try:
        return datetime.fromisoformat(str(v).strip().replace("T", " "))
    except ValueError:
        raise _err(f"{label} 일시 형식은 'YYYY-MM-DD HH:MM' 이어야 합니다: {v!r}") from None


def _dict(v, label: str, keys: set) -> dict:
    if v is None:
        return {}
    if not isinstance(v, dict):
        raise _err(f"{label} 은(는) 사전이어야 합니다")
    unknown = set(v) - keys
    if unknown:
        raise _err(f"{label} 에 알 수 없는 키: {', '.join(sorted(map(str, unknown)))}")
    return v


def _range_list(v, label: str) -> list:
    out = []
    for i, pair in enumerate(v or [], 1):
        if isinstance(pair, dict):
            pair = [pair.get("from"), pair.get("to")]
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            raise _err(f"{label}[{i}] 은(는) [시작, 끝] 이어야 합니다")
        s, e = _date(pair[0], f"{label}[{i}] 시작"), _date(pair[1], f"{label}[{i}] 끝")
        if s is None:
            raise _err(f"{label}[{i}] 시작일이 없습니다")
        if e is not None and e < s:
            raise _err(f"{label}[{i}] 끝이 시작보다 앞섭니다")
        out.append((s, e))
    return out


def _load_paid(raw, label: str) -> PaidInput:
    raw = _dict(raw, label, _PAID_KEYS | {"period"})
    return PaidInput(*(_nonneg(raw.get(k), f"{label}.{k}") for k in ("overtime", "night", "holiday", "lump")))


def _parse_key(v, label: str) -> str:
    if isinstance(v, date):
        return f"{v.year:04d}-{v.month:02d}"
    s = str(v or "").strip().replace(".", "-")
    try:
        y, m = s.split("-")[:2]
        y, m = int(y), int(m)
        date(y, m, 1)
    except (ValueError, TypeError):
        raise _err(f"{label} 은(는) 'YYYY-MM' 이어야 합니다: {v!r}") from None
    return f"{y:04d}-{m:02d}"


def _load_day(raw, label: str) -> DayRecord:
    raw = _dict(raw, label, _DAY_KEYS)
    d = _date(raw.get("date"), f"{label}.date")
    if d is None:
        raise _err(f"{label} 에 date 가 없습니다")
    start, end = _clock(raw.get("start"), f"{label}.start"), _clock(raw.get("end"), f"{label}.end")
    hours = _nonneg(raw.get("hours"), f"{label}.hours", None)
    if hours is None and (start is None or end is None):
        raise _err(f"{label}({d}) 에는 start·end 시각 또는 hours 가 필요합니다")
    if hours is not None and (start is not None or end is not None):
        raise _err(f"{label}({d}) 에 시각(start·end)과 hours 를 함께 적을 수 없습니다")
    if hours is None and start == end:
        raise _err(f"{label}({d}) 의 start 와 end 가 같습니다(24시간 넘는 근무는 나눠 적으십시오)")
    breaks = []
    for j, b in enumerate(raw.get("breaks") or [], 1):
        b = _dict(b, f"{label}.breaks[{j}]", {"start", "end", "free"})
        bs, be = _clock(b.get("start"), f"{label}.breaks[{j}].start"), _clock(b.get("end"), f"{label}.breaks[{j}].end")
        if bs is None or be is None or bs == be:
            raise _err(f"{label}.breaks[{j}] 에는 서로 다른 start·end 가 필요합니다")
        breaks.append(BreakInput(bs, be, bool(_bool(b.get("free"), f"{label}.breaks[{j}].free", True))))
    if breaks and hours is not None:
        raise _err(f"{label}({d}) 의 hours 방식에는 breaks 구간을 적지 않습니다(hours 는 휴게를 뺀 시간)")
    kind = raw.get("holiday_kind")
    if kind is not None and kind not in HOLIDAY_KINDS:
        raise _err(f"{label}.holiday_kind 를 알 수 없습니다: {kind!r} (가능: {', '.join(HOLIDAY_KINDS)})")
    holiday = bool(_bool(raw.get("holiday"), f"{label}.holiday", False))
    if holiday and kind is None:
        raise _err(f"{label}({d}) 이 휴일이면 holiday_kind({', '.join(HOLIDAY_KINDS)})가 필요합니다")
    sub = None
    if raw.get("substitution") is not None:
        s = _dict(raw["substitution"], f"{label}.substitution", {"basis", "worker_rep_agreement", "notice_at"})
        sub = SubstitutionInput(_bool(s.get("basis"), f"{label}.substitution.basis"),
                                _bool(s.get("worker_rep_agreement"), f"{label}.substitution.worker_rep_agreement"),
                                _datetime(s.get("notice_at"), f"{label}.substitution.notice_at"))
    return DayRecord(
        date=d, start=start, end=end, hours=hours,
        night_hours=_nonneg(raw.get("night_hours"), f"{label}.night_hours", None),
        breaks=breaks, break_minutes=_nonneg(raw.get("break_minutes"), f"{label}.break_minutes"),
        holiday=holiday, holiday_kind=kind,
        next_day_holiday=bool(_bool(raw.get("next_day_holiday"), f"{label}.next_day_holiday", False)),
        substitution=sub,
        scheduled_hours=_nonneg(raw.get("scheduled_hours"), f"{label}.scheduled_hours", None),
        base_paid=_bool(raw.get("base_paid"), f"{label}.base_paid"),
        proven=bool(_bool(raw.get("proven"), f"{label}.proven", True)),
        night_proven=bool(_bool(raw.get("night_proven"), f"{label}.night_proven", True)),
        note=str(raw.get("note") or ""),
    )


def _load_month(raw, label: str) -> MonthEntry:
    raw = _dict(raw, label, _MONTH_KEYS)
    if raw.get("period") in (None, ""):
        raise _err(f"{label} 에 period(YYYY-MM)가 없습니다")
    m = MonthEntry(key=_parse_key(raw["period"], f"{label}.period"),
                   start=_date(raw.get("from"), f"{label}.from"), end=_date(raw.get("to"), f"{label}.to"),
                   base_paid=_bool(raw.get("base_paid"), f"{label}.base_paid"),
                   proven=bool(_bool(raw.get("proven"), f"{label}.proven", True)),
                   paid=None if raw.get("paid") is None else _load_paid(raw["paid"], f"{label}.paid"),
                   note=str(raw.get("note") or ""))
    for k in ("overtime_hours", "in_law_hours", "night_hours", "holiday_le8_hours", "holiday_gt8_hours",
              "overtime_night_hours", "holiday_night_hours"):
        setattr(m, k, _nonneg(raw.get(k), f"{label}.{k}"))
    return m


def load_overtime(raw: dict, worker: dict | None = None) -> OvertimeInput:
    """사건.yaml `overtime:` 절(dict)과 `worker:` 절을 읽는다."""
    raw = dict(raw or {})
    worker = dict(worker or {})
    unknown = set(raw) - _TOP_KEYS
    if unknown:
        raise _err(f"overtime 절에 알 수 없는 키: {', '.join(sorted(map(str, unknown)))}")

    pay_day = _int(raw.get("pay_day", worker.get("pay_day")), "pay_day", 1, 31)
    if pay_day is None:
        raise _err("정기지급일(overtime.pay_day 또는 worker.pay_day)이 없습니다 — 차액의 지급기일을 정할 수 없습니다")
    offset = _int(raw.get("pay_month_offset", worker.get("pay_month_offset")), "pay_month_offset", 0, 12, 0)
    start_day = _int(raw.get("pay_period_start_day", worker.get("pay_period_start_day")), "pay_period_start_day", 1, 28, 1)

    ws = raw.get("week_start")
    week_start = None
    if ws not in (None, ""):
        if isinstance(ws, int) and not isinstance(ws, bool) and 0 <= ws <= 6:
            week_start = ws
        elif str(ws).strip().lower() in WEEKDAYS:
            week_start = WEEKDAYS[str(ws).strip().lower()]
        else:
            raise _err(f"week_start 를 알 수 없습니다: {ws!r} (monday … sunday, 0~6, 월 … 일)")

    bands = []
    sb = raw.get("size_band")
    if isinstance(sb, (str, int)) and not isinstance(sb, bool) and sb != "":
        bands = [(None, str(sb))]
    elif isinstance(sb, list):
        for i, b in enumerate(sb, 1):
            b = _dict(b, f"size_band[{i}]", {"from", "band"})
            bands.append((_date(b.get("from"), f"size_band[{i}].from"), str(b.get("band"))))
        bands.sort(key=lambda x: x[0] or date.min)
    elif sb not in (None, ""):
        raise _err("size_band 는 문자열 또는 [{from, band}] 목록이어야 합니다")
    for _, b in bands:
        if b not in SIZE_BANDS:
            raise _err(f"size_band 값을 알 수 없습니다: {b!r} (가능: {', '.join(SIZE_BANDS)})")

    std = []
    for i, s in enumerate(raw.get("standard_hours") or [], 1):
        s = _dict(s, f"standard_hours[{i}]", {"from", "daily", "weekly"})
        f = _date(s.get("from"), f"standard_hours[{i}].from")
        dly, wk = _nonneg(s.get("daily"), f"standard_hours[{i}].daily", None), _nonneg(s.get("weekly"), f"standard_hours[{i}].weekly", None)
        if f is None or not dly or not wk:
            raise _err(f"standard_hours[{i}] 에는 from·daily·weekly 가 필요합니다")
        std.append((f, dly, wk))
    std.sort(key=lambda x: x[0])

    part_time = bool(_bool(raw.get("part_time"), "part_time", False))
    sd = _nonneg(raw.get("scheduled_daily_hours"), "scheduled_daily_hours", None)
    sw = _nonneg(raw.get("scheduled_weekly_hours"), "scheduled_weekly_hours", None)
    if part_time and (sd is None or sw is None):
        raise _err("단시간근로자(part_time)는 scheduled_daily_hours 와 scheduled_weekly_hours 가 필요합니다")

    inclusive = raw.get("inclusive_wage") or "none"
    if inclusive not in INCLUSIVE:
        raise _err(f"inclusive_wage 값을 알 수 없습니다: {inclusive!r} (가능: {', '.join(INCLUSIVE)})")

    exempt = []
    for i, e in enumerate(raw.get("exempt_63") or [], 1):
        e = _dict(e, f"exempt_63[{i}]", {"from", "to", "category", "approved_on"})
        f = _date(e.get("from"), f"exempt_63[{i}].from")
        cat = _int(e.get("category"), f"exempt_63[{i}].category", 1, 4)
        if f is None or cat is None:
            raise _err(f"exempt_63[{i}] 에는 from 과 category(제63조 호, 1~4)가 필요합니다")
        appr = _date(e.get("approved_on"), f"exempt_63[{i}].approved_on")
        if cat == 3 and appr is None:
            raise _err(f"exempt_63[{i}] 제63조 제3호(감시·단속적)는 고용노동부장관 승인일(approved_on)이 필요합니다")
        exempt.append((f, _date(e.get("to"), f"exempt_63[{i}].to"), cat, appr))

    heads = []
    for i, h in enumerate(raw.get("headcount") or [], 1):
        h = _dict(h, f"headcount[{i}]", {"from", "to", "person_days", "operating_days"})
        f, t = _date(h.get("from"), f"headcount[{i}].from"), _date(h.get("to"), f"headcount[{i}].to")
        pdays, odays = _nonneg(h.get("person_days"), f"headcount[{i}].person_days", None), _nonneg(h.get("operating_days"), f"headcount[{i}].operating_days", None)
        if f is None or pdays is None or not odays:
            raise _err(f"headcount[{i}] 에는 from·person_days·operating_days(0 초과)가 필요합니다")
        heads.append((f, t, pdays, odays))

    agreed_hours = []
    for i, a in enumerate(raw.get("agreed_hours") or [], 1):
        a = _dict(a, f"agreed_hours[{i}]", {"from", "to", "overtime", "night", "holiday_le8", "holiday_gt8"})
        f = _date(a.get("from"), f"agreed_hours[{i}].from")
        if f is None:
            raise _err(f"agreed_hours[{i}] 에 from 이 없습니다(합의가 존속한 기간)")
        agreed_hours.append(AgreedHours(f, _date(a.get("to"), f"agreed_hours[{i}].to"),
                                        *(_nonneg(a.get(k), f"agreed_hours[{i}].{k}") for k in ("overtime", "night", "holiday_le8", "holiday_gt8"))))

    agreed = None
    if raw.get("agreed"):
        a = _dict(raw["agreed"], "agreed", {"valid", "hourly", "rates"})
        valid = _bool(a.get("valid"), "agreed.valid")
        if valid is None:
            raise _err("agreed.valid(약정 산정방법 전체가 법 기준을 충족하는지, 사람 판단)가 없습니다")
        hourly = []
        for i, h in enumerate(a.get("hourly") or [], 1):
            h = _dict(h, f"agreed.hourly[{i}]", {"from", "amount"})
            f, amt = _date(h.get("from"), f"agreed.hourly[{i}].from"), _nonneg(h.get("amount"), f"agreed.hourly[{i}].amount", None)
            if f is None or amt is None:
                raise _err(f"agreed.hourly[{i}] 에는 from 과 amount 가 필요합니다")
            hourly.append((f, amt))
        if not hourly:
            raise _err("agreed.hourly(약정 통상시급 이력)가 없습니다")
        hourly.sort(key=lambda x: x[0])
        r = _dict(a.get("rates"), "agreed.rates", _RATE_KEYS)
        missing = [k for k in ("overtime", "night", "holiday_le8", "holiday_gt8") if r.get(k) in (None, "")]
        if missing:
            raise _err(f"agreed.rates 에 {', '.join(missing)} 가 없습니다 — 약정 가산율은 전체를 적어야 합니다(OT-15)")
        rates = {k: _nonneg(r.get(k), f"agreed.rates.{k}") for k in _RATE_KEYS}
        agreed = AgreedTerms(valid, hourly, rates)

    months = [_load_month(m, f"months[{i}]") for i, m in enumerate(raw.get("months") or [], 1)]
    days = [_load_day(d, f"days[{i}]") for i, d in enumerate(raw.get("days") or [], 1)]
    if days and week_start is None:
        raise _err("일별 근무기록(days)이 있으면 1주 기산 요일 week_start 가 필요합니다(OT-04)")

    paid: dict = {}
    for i, p in enumerate(raw.get("paid") or [], 1):
        if not isinstance(p, dict) or p.get("period") in (None, ""):
            raise _err(f"paid[{i}] 에 period(YYYY-MM)가 없습니다")
        key = _parse_key(p["period"], f"paid[{i}].period")
        if key in paid:
            raise _err(f"paid 에 {key} 가 두 번 있습니다")
        paid[key] = _load_paid(p, f"paid[{i}]")
    for m in months:
        if m.paid is not None:
            if m.key in paid:
                raise _err(f"{m.key} 기지급액이 months 와 paid 에 함께 있습니다 — 한 곳에만 적으십시오")
            paid[m.key] = m.paid
    month_paid_keys = [m.key for m in months if m.paid is not None]
    if len(month_paid_keys) != len(set(month_paid_keys)):
        raise _err("같은 period 의 months 여러 줄에 paid 를 나눠 적었습니다 — 한 줄에만 적으십시오")

    return OvertimeInput(
        pay_day=pay_day, pay_month_offset=offset, pay_period_start_day=start_day, week_start=week_start,
        size_band=bands, standard_hours=std, minor=bool(_bool(raw.get("minor"), "minor", False)),
        scheduled_daily_hours=sd, scheduled_weekly_hours=sw, part_time=part_time,
        base_paid=bool(_bool(raw.get("base_paid"), "base_paid", False)), inclusive_wage=inclusive,
        claim_from=_date(raw.get("claim_from"), "claim_from"), claim_to=_date(raw.get("claim_to"), "claim_to"),
        exempt_63=exempt, headcount=heads, flexible_periods=_range_list(raw.get("flexible_periods"), "flexible_periods"),
        agreed_hours=agreed_hours, agreed=agreed, compare_units=_range_list(raw.get("compare_units"), "compare_units"),
        months=months, days=days, paid=paid,
    )


# ================================================================ 헬퍼
def _fmt(d: date | None) -> str:
    return "" if d is None else f"{d.year}. {d.month}. {d.day}."


def _settle(x: Decimal) -> Decimal:
    """Decimal 나눗셈 순환소수 오차 보정(소수 10자리 반올림). 끝수처리 직전에만."""
    return x.quantize(Decimal("1e-10"), rounding=ROUND_HALF_UP)


def _round_amount(x: Decimal, mode: str) -> Decimal:
    x = _settle(x)
    if mode == "ceil10":
        return (x / 10).quantize(ONE, rounding=ROUND_CEILING) * 10
    return round_to(x, 0, mode)


def _round_hourly(x: Decimal, mode: str) -> Decimal:
    if mode == "none":
        return x
    if mode == "floor_1dp":
        return round_to(_settle(x), 1, "floor")
    return round_to(_settle(x), 0, mode)


def _round_hours(x: Decimal, mode: str) -> Decimal:
    if mode == "none":
        return x
    digits = {"floor_2dp": 2, "floor_1dp": 1, "floor_int": 0}[mode]
    return round_to(_settle(x), digits, "floor")


def _timeline(items: list, d: date, label: str):
    """[(from, value…)] 에서 d 에 적용할 값(from <= d 인 마지막)."""
    found = None
    for it in items:
        if it[0] is None or it[0] <= d:
            found = it
    return found


@dataclass
class _Ctx:
    inp: OvertimeInput
    o: dict
    deps: dict
    trace: list
    warnings: list

    def warn(self, msg: str) -> None:
        if msg not in self.warnings:
            self.warnings.append(msg)

    # ---- 날짜별 사실
    def hourly(self, d: date) -> Decimal:
        fn = self.deps.get("hourly_of")
        if fn is None:
            raise _err("재산정에 통상시급(deps hourly_of)이 필요합니다")
        v = fn(d)
        if v is None:
            raise _err(f"{_fmt(d)} 의 통상시급을 통상임금 모듈이 주지 않았습니다")
        return _round_hourly(dec(v), self.o["ot_hourly_rounding"])

    def contract_hourly(self, d: date) -> Decimal:
        found = _timeline(self.inp.agreed.hourly, d, "agreed.hourly")
        if found is None:
            raise _err(f"{_fmt(d)} 에 적용할 약정 통상시급(agreed.hourly)이 없습니다")
        return _round_hourly(found[1], self.o["ot_hourly_rounding"])

    def small(self, d: date) -> bool:
        for f, t, pdays, odays in self.inp.headcount:
            if f <= d and (t is None or d <= t):
                return pdays / odays < 5
        fn = self.deps.get("small_business")
        return bool(fn(d)) if fn is not None else False

    def exempt(self, d: date) -> bool:
        for f, t, cat, appr in self.inp.exempt_63:
            if f <= d and (t is None or d <= t) and (cat != 3 or appr <= d):
                return True
        return False

    def band(self, d: date) -> str | None:
        found = _timeline(self.inp.size_band, d, "size_band")
        return None if found is None else found[1]

    def std(self, d: date) -> tuple[Decimal, Decimal]:
        found = _timeline(self.inp.standard_hours, d, "standard_hours")
        if found is not None:
            return found[1], found[2]
        return (Decimal(7), Decimal(35)) if self.inp.minor else (Decimal(8), Decimal(40))

    def week_def_applies(self, d: date, need: bool) -> bool:
        """d 가 속한 주에 '1주 = 휴일 포함 7일'(제2조 제1항 제7호)이 시행 중인지."""
        band = self.band(d)
        if band is None:
            if need and d >= SIZE_BANDS["300+"][0]:
                raise _err(f"{_fmt(d)} 주에 휴일근로가 있어 1주 정의 시행일(규모별)을 정해야 합니다 — size_band 가 필요합니다(OT-03)")
            return False
        eff = SIZE_BANDS[band][0]
        return eff is not None and d >= eff

    def slice(self, d: date):
        return pay_periods(d, d, self.inp.pay_period_start_day)[0]


# ================================================================ 일별 기록 → 근무 조각
@dataclass
class _Piece:
    date: date
    minutes: Decimal
    night_min: Decimal
    unproven_night_min: Decimal
    ot_night_min: Decimal
    holiday: bool
    scheduled: Decimal | None
    base_paid: bool | None
    label: str


def _subtract(segs: list, a: int, b: int) -> list:
    out = []
    for s, e in segs:
        if b <= s or e <= a:
            out.append((s, e))
            continue
        if s < a:
            out.append((s, a))
        if b < e:
            out.append((b, e))
    return out


def _cut_by_offset(segs: list, off_a: int, off_b: int) -> list:
    """근로 누적 분 [off_a, off_b) 에 해당하는 실제 구간을 뺀다."""
    acc = 0
    cut = []
    for s, e in segs:
        ln = e - s
        lo, hi = max(off_a, acc), min(off_b, acc + ln)
        if lo < hi:
            cut.append((s + lo - acc, s + hi - acc))
        acc += ln
    for a, b in cut:
        segs = _subtract(segs, a, b)
    return segs


def _after_offset(segs: list, off: int) -> list:
    acc = 0
    out = []
    for s, e in segs:
        ln = e - s
        if acc + ln > off:
            out.append((s + max(0, off - acc), e))
        acc += ln
    return out


def _night(segs: list) -> int:
    total = 0
    for s, e in segs:
        for k in range(-1, 3):
            a, b = k * 1440 + 22 * 60, (k + 1) * 1440 + 6 * 60
            total += max(0, min(e, b) - max(s, a))
    return total


def _holiday_status(rec: DayRecord, ctx: _Ctx) -> bool:
    if not rec.holiday:
        return False
    d = rec.date
    label = f"{_fmt(d)} {HOLIDAY_KINDS[rec.holiday_kind]}"
    if ctx.exempt(d):
        ctx.warn(f"{label}: 제63조 적용제외 근로자 — 휴일 규정 미적용, 휴일근로 가산 없음(OT-02)")
        return False
    if rec.holiday_kind == "public":
        band = ctx.band(d)
        if band is None:
            raise _err(f"{label}: 공휴일 유급휴일 시행일(제55조 제2항)을 정하려면 size_band 가 필요합니다(OT-11)")
        eff = SIZE_BANDS[band][1]
        if eff is None or d < eff:
            ctx.warn(f"{label}: 규모 {band} 의 공휴일 유급휴일 시행({_fmt(eff) or '미적용'}) 전 — 약정휴일이 아니면 휴일근로가 아님. "
                     "약정휴일이면 holiday_kind: agreed 로 적으십시오")
            return False
    sub = rec.substitution
    if sub is None:
        return True
    need = sub.worker_rep_agreement if rec.holiday_kind == "public" else sub.basis
    start = datetime(d.year, d.month, d.day)
    reasons = []
    if not need:
        reasons.append("근로자대표 서면합의 없음(제55조 제2항 단서)" if rec.holiday_kind == "public"
                       else "근거 규정 또는 근로자 동의 없음(99다7367)")
    if sub.notice_at is None:
        reasons.append("대체일 사전 통지 일시 없음")
    else:
        limit = start - timedelta(hours=24) if ctx.o["ot_substitution_notice_24h"] else start
        if sub.notice_at > limit:
            reasons.append(f"통지 {sub.notice_at:%Y-%m-%d %H:%M} 가 "
                           + ("24시간 전 기한을 넘김(근로기준정책과-7347)" if ctx.o["ot_substitution_notice_24h"] else "휴일 시작 뒤"))
    if reasons:
        ctx.warn(f"{label}: 휴일대체 요건 불충족 — {', '.join(reasons)} → 휴일근로로 계산(사후 대체휴일로 가산이 없어지지 않음)")
        return True
    ctx.trace.append(Trace("OT-11", f"{label} 휴일대체", "적법 — 통상근로", "원래 휴일은 통상 근로일(99다7367)"))
    return False


def _pieces(ctx: _Ctx) -> tuple[list, dict]:
    """일별 기록 → 귀속일별 근무 조각. 두 번째 값은 {귀속일: 미증명 분}."""
    o = ctx.o
    out, unproven = [], {}
    for rec in ctx.inp.days:
        d = rec.date
        if is_within(d, ctx.inp.flexible_periods):
            raise _err(f"{_fmt(d)} 는 탄력적·선택적 근로시간제 기간 — 연장시간 산정 방식이 확인되지 않아(M1) 일별 기록으로 계산하지 않습니다. "
                       "사람이 산정한 시간을 months(집계 방식)로 넣으십시오")
        D, _ = ctx.std(d)
        exempt = ctx.exempt(d)
        hol = _holiday_status(rec, ctx)
        label = f"{_fmt(d)} 근무"
        if rec.hours is not None:
            minutes = rec.hours * SIXTY
            night = (rec.night_hours or ZERO) * SIXTY
            if o["ot_assume_ot_break"] and not exempt:
                raw_ot = minutes - D * SIXTY
                n = int(raw_ot // 240) if raw_ot > 0 else 0
                minutes -= 30 * n
            if not rec.proven:
                unproven[d] = unproven.get(d, ZERO) + minutes
                continue
            out.append(_Piece(d, minutes, night if rec.night_proven else ZERO, ZERO if rec.night_proven else night,
                              ZERO, hol, rec.scheduled_hours, rec.base_paid, label))
            continue
        s, e = rec.start, rec.end if rec.end > rec.start else rec.end + 1440
        segs = [(s, e)]
        for b in rec.breaks:
            bs = b.start if b.start >= s else b.start + 1440
            be = b.end
            while be <= bs:
                be += 1440
            if not (s <= bs and be <= e):
                raise _err(f"{label}: 휴게 구간이 근무시간 밖입니다")
            if b.free:
                segs = _subtract(segs, bs, be)
            else:
                ctx.warn(f"{label}: 자유이용이 보장되지 않은 휴게 {be - bs}분은 근로시간으로 봄(2017나24321, M8)")
        worked = sum(b - a for a, b in segs)
        untimed = rec.break_minutes
        if untimed > worked:
            raise _err(f"{label}: 휴게시간이 근무시간보다 깁니다")
        if o["ot_assume_ot_break"] and not exempt:
            raw_ot = Decimal(worked) - untimed - D * SIXTY
            n = int(raw_ot // 240) if raw_ot > 0 else 0
            base_off = int(D * SIXTY)
            for k in range(n, 0, -1):
                segs = _cut_by_offset(segs, base_off + 240 * k - 30, base_off + 240 * k)
            if n:
                ctx.trace.append(Trace("OT-14", f"{label} 연장 휴게 자동 공제", f"{30 * n}분"))
        night_all = _night(segs)
        if untimed and night_all:
            ctx.warn(f"{label}: 위치 모르는 휴게 {untimed}분은 야간시간에서 빼지 않았습니다 — 휴게 구간을 적으면 정확해집니다")
        if not rec.proven:
            unproven[d] = unproven.get(d, ZERO) + Decimal(sum(b - a for a, b in segs)) - untimed
            continue
        split = (o["ot_holiday_boundary"] == "calendar_day" and e > 1440 and hol != rec.next_day_holiday)
        if e > 1440 and (hol or rec.next_day_holiday):
            ctx.warn(f"{label}: 휴일과 자정을 걸친 근무 — 휴일근로 범위는 ot_holiday_boundary={o['ot_holiday_boundary']} 로 정함(OT-13 미해결)")
        parts = []
        if split:
            first = [(a, min(b, 1440)) for a, b in segs if a < 1440]
            second = [(max(a, 1440) - 1440, b - 1440) for a, b in segs if b > 1440]
            parts = [(d, first, hol, untimed), (d + timedelta(days=1), second, rec.next_day_holiday, ZERO)]
        else:
            parts = [(d, segs, hol, untimed)]
        for pd, psegs, phol, pun in parts:
            mins = Decimal(sum(b - a for a, b in psegs))
            pun = min(pun, mins)
            nm = Decimal(_night(psegs))
            ot_nm = Decimal(_night(_after_offset(psegs, int(D * SIXTY))))
            out.append(_Piece(pd, mins - pun, nm if rec.night_proven else ZERO, ZERO if rec.night_proven else nm,
                              ot_nm if rec.night_proven else ZERO, phol, rec.scheduled_hours if pd == d else None,
                              rec.base_paid, label if pd == d else f"{label}(자정 이후분)"))
    return out, unproven


# ================================================================ 주 단위 분류(OT-04·05·06·07·08·10)
@dataclass
class _Day:
    date: date
    hours: Decimal
    holiday: bool
    scheduled: Decimal
    base_paid: bool
    night: Decimal
    unproven_night: Decimal
    ot_night: Decimal
    exempt: bool
    overtime: Decimal = ZERO
    in_law: Decimal = ZERO
    part_time: Decimal = ZERO
    le8: Decimal = ZERO
    gt8: Decimal = ZERO


def _days(pieces: list, ctx: _Ctx) -> list:
    inp = ctx.inp
    by = {}
    for p in pieces:
        by.setdefault(p.date, []).append(p)
    out = []
    for d in sorted(by):
        ps = by[d]
        hols = {p.holiday for p in ps}
        if len(hols) > 1:
            raise _err(f"{_fmt(d)} 에 휴일인 근무와 휴일 아닌 근무가 함께 있습니다 — 기록의 holiday 를 맞추십시오")
        bps = {p.base_paid for p in ps if p.base_paid is not None}
        if len(bps) > 1:
            raise _err(f"{_fmt(d)} 의 근무 기록들의 base_paid 가 서로 다릅니다")
        D, W = ctx.std(d)
        scheds = [p.scheduled for p in ps if p.scheduled is not None]
        if scheds:
            sched = min(scheds)
        elif inp.scheduled_daily_hours is not None:
            sched = inp.scheduled_daily_hours
        else:
            sched = D
        out.append(_Day(d, sum((p.minutes for p in ps), ZERO) / SIXTY, hols.pop(), sched,
                        bps.pop() if bps else inp.base_paid,
                        sum((p.night_min for p in ps), ZERO) / SIXTY,
                        sum((p.unproven_night_min for p in ps), ZERO) / SIXTY,
                        sum((p.ot_night_min for p in ps), ZERO) / SIXTY,
                        ctx.exempt(d)))
    return out


def _allocate_week(amount: Decimal, capacities: list, order: str) -> list:
    idx = list(range(len(capacities)))
    if order == "last_days_first":
        idx.reverse()
    take = [ZERO] * len(capacities)
    left = amount
    for i in idx:
        t = min(left, capacities[i])
        take[i] = t
        left -= t
    return take


def _classify(days: list, ctx: _Ctx, hol_weekly: str, alloc: str) -> list:
    inp, o = ctx.inp, ctx.o
    weeks = {}
    for dd in days:
        ws = dd.date - timedelta(days=(dd.date.weekday() - inp.week_start) % 7)
        weeks.setdefault(ws, []).append(dd)
    checks = []
    for ws in sorted(weeks):
        wdays = weeks[ws]
        D_week, W = ctx.std(ws)
        has_hol = any(x.holiday and x.hours for x in wdays)
        new_week = ctx.week_def_applies(ws, need=has_hol)
        include = new_week and hol_weekly == "include"
        normal = [x for x in wdays if not x.holiday]
        within = []
        for x in normal:
            D, _ = ctx.std(x.date)
            dot = max(x.hours - D, ZERO)
            x.overtime = dot
            within.append(x.hours - dot)
        S = sum(within, ZERO)
        if include:
            S += sum((min(x.hours, ctx.std(x.date)[0]) for x in wdays if x.holiday), ZERO)
        weekly_ot = min(max(S - W, ZERO), sum(within, ZERO))
        alloc_eff = alloc
        takes = _allocate_week(weekly_ot, within, alloc_eff)
        regular = []
        for x, w, t in zip(normal, within, takes):
            x.overtime += t
            regular.append(w - t)
        # 법내 초과(OT-07)·단시간 소정 초과(OT-08) — 일·주 중복 제거
        sched_week = inp.scheduled_weekly_hours if inp.scheduled_weekly_hours is not None else W
        daily_ex, inside = [], []
        for x, r in zip(normal, regular):
            ex = max(r - x.scheduled, ZERO)
            daily_ex.append(ex)
            inside.append(r - ex)
        wk_ex = max(sum(inside, ZERO) - sched_week, ZERO)
        wk_takes = _allocate_week(wk_ex, inside, alloc_eff)
        pt_mode = o["ot_part_time_premium"]
        for x, de, wt in zip(normal, daily_ex, wk_takes):
            x.in_law = de + wt
            if inp.part_time and pt_mode != "off":
                x.part_time = de if pt_mode == "daily" else de + wt
        for x in wdays:
            if x.holiday:
                x.le8 = min(x.hours, Decimal(8))
                x.gt8 = max(x.hours - 8, ZERO)
        # 한도 판정(OT-06)
        basis = sum((x.hours for x in wdays if new_week or not x.holiday), ZERO)
        limit = Decimal(5) if inp.minor else Decimal(12)
        band = ctx.band(ws)
        if band == "5-29" and DATE_SPECIAL_EXT[0] <= ws <= DATE_SPECIAL_EXT[1]:
            limit += 8
        lot = max(basis - W, ZERO)
        premium_ot = sum((x.overtime for x in normal), ZERO)
        skip = all(x.exempt or ctx.small(x.date) for x in wdays)
        chk = WeekCheck(ws, ws + timedelta(days=6), basis, lot, limit, (not skip) and lot > limit, premium_ot, new_week)
        checks.append(chk)
        if chk.violation:
            ctx.warn(f"{_fmt(ws)}~{_fmt(chk.week_end)} 주: 1주 연장 {lot}시간이 한도 {limit}시간 초과(제53조, 2020도15393) — "
                     "가산액은 바꾸지 않음(OT-06)")
    return checks


# ================================================================ 줄 구성
@dataclass
class _Comp:
    """배수를 곱하기 전 시간 묶음. base/prem 은 legal, c_base/c_prem 은 contract."""

    date: date
    key: str
    item: str
    category: str
    hours: Decimal
    base: Decimal
    prem: Decimal
    c_base: Decimal
    c_prem: Decimal


def _rates(ctx: _Ctx, d: date, exempt: bool, base_paid: bool) -> dict:
    o, inp = ctx.o, ctx.inp
    small = ctx.small(d)
    old = d < DATE_2018_AMEND
    base = ZERO if base_paid else ONE
    legal = {
        "overtime": ZERO if (small or exempt) else HALF,
        "in_law": ZERO,
        "part_time": HALF if (inp.part_time and o["ot_part_time_premium"] != "off" and d >= DATE_PT_PREMIUM and not small) else ZERO,
        "holiday_le8": ZERO if (small or exempt) else HALF,
        "holiday_gt8": ZERO if (small or exempt) else (HALF if old else ONE),
        "holiday_gt8_ot": HALF if (old and o["ot_pre2018_holiday_over8_add_ot"] and not small and not exempt) else ZERO,
        "night": HALF if (not small or o["ot_night_premium_under5"]) else ZERO,
    }
    if inp.agreed is not None:
        r = inp.agreed.rates
        contract = {k: r.get(k) or ZERO for k in legal}
    else:
        contract = {k: ZERO for k in legal}
    return {"base": base, "legal": legal, "contract": contract}


def _comps_for_day(x: _Day, ctx: _Ctx) -> list:
    rt = _rates(ctx, x.date, x.exempt, x.base_paid)
    key = ctx.slice(x.date).key
    b = rt["base"]
    L, C = rt["legal"], rt["contract"]
    rows = [
        ("overtime", "overtime", x.overtime, b),
        ("overtime", "in_law", x.in_law - x.part_time, b),
        ("overtime", "part_time", x.part_time, b),
        ("holiday", "holiday_le8", x.le8, b),
        ("holiday", "holiday_gt8", x.gt8, b),
        ("holiday", "holiday_gt8_ot", x.gt8, ZERO),
        ("night", "night", x.night, ZERO),
    ]
    return [_Comp(x.date, key, item, cat, h, base, L[cat], base, C[cat]) for item, cat, h, base in rows if h > 0]


def _comps_for_month(m: MonthEntry, ctx: _Ctx) -> tuple[list, date, date]:
    inp = ctx.inp
    ps = pay_periods(date(int(m.key[:4]), int(m.key[5:]), inp.pay_period_start_day),
                     date(int(m.key[:4]), int(m.key[5:]), inp.pay_period_start_day), inp.pay_period_start_day)[0]
    s = m.start or ps.period_start
    e = m.end or ps.period_end
    if s < ps.period_start or e > ps.period_end or e < s:
        raise _err(f"months {m.key} 의 from/to({s}~{e})가 임금산정기간 {ps.period_start}~{ps.period_end} 밖입니다")
    base_paid = inp.base_paid if m.base_paid is None else m.base_paid
    checks = [
        ("통상시급", lambda d: ctx.hourly(d)),
        ("상시 4명 이하 여부", ctx.small),
        ("제63조 적용제외 여부", ctx.exempt),
        ("가산율 체계(2018. 3. 20.)", lambda d: d < DATE_2018_AMEND),
        ("단시간 가산 시행(2014. 9. 19.)", lambda d: d < DATE_PT_PREMIUM),
    ]
    if inp.agreed is not None:
        checks.append(("약정 통상시급", lambda d: ctx.contract_hourly(d)))
    for name, fn in checks:
        if fn(s) != fn(e):
            raise _err(f"months {m.key}: {_fmt(s)}~{_fmt(e)} 안에서 {name}이(가) 바뀝니다 — from/to 로 나눠 여러 줄로 적으십시오")
    if is_within(s, inp.flexible_periods) or is_within(e, inp.flexible_periods):
        ctx.trace.append(Trace("M1", f"months {m.key}", "탄력적·선택적 근로시간제 기간", "사람이 산정한 시간을 그대로 사용"))
    if inp.part_time and ctx.o["ot_part_time_premium"] != "off":
        pt, law = m.in_law_hours, ZERO
    else:
        pt, law = ZERO, m.in_law_hours
    x = _Day(s, ZERO, False, ZERO, base_paid, m.night_hours, ZERO, m.overtime_night_hours, ctx.exempt(s),
             overtime=m.overtime_hours, in_law=law + pt, part_time=pt, le8=m.holiday_le8_hours, gt8=m.holiday_gt8_hours)
    comps = _comps_for_day(x, ctx)
    for c in comps:
        c.key = m.key
    if m.holiday_le8_hours < 8 and m.holiday_gt8_hours > 0:
        ctx.trace.append(Trace("OT-03", f"months {m.key}", "휴일 8시간 초과 입력", "일별 합산값으로 봄"))
    return comps, s, e


def _build_lines(comps: list, ctx: _Ctx, basis: str) -> list:
    o = ctx.o
    structure = o["ot_multiplier_structure"]
    groups: dict = {}
    for c in comps:
        base = c.base if basis == "legal" else c.c_base
        prem = c.prem if basis == "legal" else c.c_prem
        hourly = ctx.hourly(c.date) if basis == "legal" else ctx.contract_hourly(c.date)
        if structure == "split":
            parts = []
            if base > 0:
                parts.append(("base", "base", base))
            if prem > 0:
                parts.append((c.category, "premium", prem))
        else:
            if c.category == "holiday_gt8_ot":
                parts = [("holiday_gt8", "combined", prem)] if prem > 0 else []
            else:
                parts = [(c.category, "combined", base + prem)] if base + prem > 0 else []
        for cat, kind, mult in parts:
            k = (c.item, cat, kind, hourly, mult)
            groups[k] = groups.get(k, ZERO) + c.hours
    lines = []
    order = {"base": 0, "overtime": 1, "in_law": 2, "part_time": 3, "holiday_le8": 4, "holiday_gt8": 5,
             "holiday_gt8_ot": 6, "night": 7}
    item_order = {"overtime": 0, "holiday": 1, "night": 2}
    for (item, cat, kind, hourly, mult), hours in sorted(groups.items(), key=lambda kv: (item_order[kv[0][0]], order[kv[0][1]], kv[0][3], kv[0][4])):
        hours = _round_hours(hours, o["ot_hours_rounding"])
        raw = hours * hourly * mult
        amount = _round_amount(raw, o["ot_amount_rounding"]) if o["ot_rounding_stage"] == "line" else raw
        if kind == "base":
            label = f"{ITEM_LABELS[item]} {CATEGORY_LABELS['base']}"
        elif kind == "combined":
            label = f"{CATEGORY_LABELS[cat].replace(' 가산', '')} {mult}배"
        else:
            label = CATEGORY_LABELS[cat]
        lines.append(OvertimeLine(basis, item, cat, kind, label, hours, hourly, mult, amount))
    return lines


def _item_totals(lines: list, ctx: _Ctx) -> dict:
    out = {i: ZERO for i in ITEMS}
    for ln in lines:
        out[ln.item] += ln.amount
    if ctx.o["ot_rounding_stage"] == "item":
        out = {k: _round_amount(v, ctx.o["ot_amount_rounding"]) for k, v in out.items()}
    return out


def _combined_holiday_gt8_fix(comps: list) -> list:
    """combined 구조에서 구법 휴일 8시간 초과 연장 가산을 holiday_gt8 배수에 합치기 위해 comp 를 합친다."""
    out = []
    ot = {}
    for c in comps:
        if c.category == "holiday_gt8_ot":
            ot[(c.date, c.key)] = c
    for c in comps:
        if c.category == "holiday_gt8_ot":
            continue
        if c.category == "holiday_gt8" and (c.date, c.key) in ot:
            extra = ot[(c.date, c.key)]
            c = _Comp(c.date, c.key, c.item, c.category, c.hours, c.base, c.prem + extra.prem, c.c_base, c.c_prem + extra.c_prem)
        out.append(c)
    return out


# ================================================================ 기간 행
@dataclass
class _Core:
    rows: list
    weeks: list
    fingerprint: tuple


def _core(ctx: _Ctx, hol_weekly: str, alloc: str) -> _Core:
    inp, o = ctx.inp, ctx.o
    pieces, unproven = _pieces(ctx)
    days = _days(pieces, ctx)
    weeks = _classify(days, ctx, hol_weekly, alloc) if days else []

    def in_claim(d: date) -> bool:
        return (inp.claim_from is None or d >= inp.claim_from) and (inp.claim_to is None or d <= inp.claim_to)

    per: dict = {}     # key -> dict
    day_keys = set()

    def slot(key: str, ps: date, pe: date) -> dict:
        return per.setdefault(key, dict(start=ps, end=pe, comps=[], hours={k: ZERO for k in (
            "overtime", "in_law", "part_time", "night", "holiday_le8", "holiday_gt8", "overtime_night", "holiday_night", "unproven")},
            notes=[], last=None, base_paid=inp.base_paid))

    for x in days:
        if not in_claim(x.date):
            continue
        sl = ctx.slice(x.date)
        st = slot(sl.key, sl.period_start, sl.period_end)
        day_keys.add(sl.key)
        st["comps"].extend(_comps_for_day(x, ctx))
        h = st["hours"]
        h["overtime"] += x.overtime
        h["in_law"] += x.in_law
        h["part_time"] += x.part_time
        h["night"] += x.night
        h["holiday_le8"] += x.le8
        h["holiday_gt8"] += x.gt8
        h["overtime_night"] += x.ot_night
        h["holiday_night"] += x.night if x.holiday else ZERO
        h["unproven"] += x.unproven_night
        st["last"] = x.date if st["last"] is None or x.date > st["last"] else st["last"]
    for d, mins in unproven.items():
        if not in_claim(d):
            continue
        sl = ctx.slice(d)
        st = slot(sl.key, sl.period_start, sl.period_end)
        st["hours"]["unproven"] += mins / SIXTY
    for m in inp.months:
        if m.key in day_keys:
            raise _err(f"{m.key} 에 일별 기록(days)과 집계(months)가 함께 있습니다 — 한 방식만 쓰십시오")
        ps = pay_periods(date(int(m.key[:4]), int(m.key[5:]), inp.pay_period_start_day),
                         date(int(m.key[:4]), int(m.key[5:]), inp.pay_period_start_day), inp.pay_period_start_day)[0]
        st = slot(m.key, ps.period_start, ps.period_end)
        if m.note:
            st["notes"].append(m.note)
        if not m.proven:
            total = m.overtime_hours + m.in_law_hours + m.holiday_le8_hours + m.holiday_gt8_hours + m.night_hours
            st["hours"]["unproven"] += total
            continue
        comps, s, e = _comps_for_month(m, ctx)
        st["comps"].extend(comps)
        h = st["hours"]
        pt_on = inp.part_time and o["ot_part_time_premium"] != "off"
        h["overtime"] += m.overtime_hours
        h["in_law"] += m.in_law_hours
        h["part_time"] += m.in_law_hours if pt_on else ZERO
        h["night"] += m.night_hours
        h["holiday_le8"] += m.holiday_le8_hours
        h["holiday_gt8"] += m.holiday_gt8_hours
        h["overtime_night"] += m.overtime_night_hours
        h["holiday_night"] += m.holiday_night_hours
        st["last"] = e if st["last"] is None or e > st["last"] else st["last"]
        if m.base_paid is not None:
            st["base_paid"] = m.base_paid
    for key in inp.paid:
        if key not in per:
            y, mth = int(key[:4]), int(key[5:])
            a = date(y, mth, inp.pay_period_start_day)
            ps = pay_periods(a, a, inp.pay_period_start_day)[0]
            slot(key, ps.period_start, ps.period_end)

    # OT-16 간주 시간 하한
    for key, st in per.items():
        for ah in inp.agreed_hours:
            if not (ah.start <= st["start"] and (ah.end is None or st["start"] <= ah.end)):
                continue
            ref = st["last"] or min(st["end"], inp.claim_to or st["end"])
            exempt = ctx.exempt(ref)
            x = _Day(ref, ZERO, False, ZERO, st["base_paid"], ZERO, ZERO, ZERO, exempt)
            for cat, attr, hk in (("overtime", "overtime", "overtime"), ("night", "night", "night"),
                                  ("holiday_le8", "holiday_le8", "holiday_le8"), ("holiday_gt8", "holiday_gt8", "holiday_gt8")):
                agreed = getattr(ah, cat)
                actual = st["hours"][hk]
                if agreed > actual:
                    short = agreed - actual
                    st["hours"][hk] = agreed
                    if cat == "overtime":
                        x.overtime = short
                    elif cat == "night":
                        x.night = short
                    elif cat == "holiday_le8":
                        x.le8 = short
                    else:
                        x.gt8 = short
                    st["notes"].append(f"간주합의 {CATEGORY_LABELS[cat].replace(' 가산', '')} {agreed}시간 < 실근로 {actual}시간 보충(OT-16)")
            comps = _comps_for_day(x, ctx)
            for c in comps:
                c.key = key
            st["comps"].extend(comps)

    rows = []
    for key in sorted(per, key=lambda k: per[k]["start"]):
        st = per[key]
        comps = st["comps"]
        if o["ot_multiplier_structure"] == "combined":
            comps = _combined_holiday_gt8_fix(comps)
        lines = _build_lines(comps, ctx, "legal")
        legal_by_item = _item_totals(lines, ctx)
        contract_lines, contract_by_item = [], None
        if inp.agreed is not None:
            contract_lines = _build_lines(comps, ctx, "contract")
            contract_by_item = _item_totals(contract_lines, ctx)
        paid = inp.paid.get(key, PaidInput())
        h = st["hours"]
        if h["unproven"]:
            st["notes"].append(f"증명되지 않은 시간 {h['unproven']}시간 제외(2022다291153)")
        rows.append(OvertimeRow(
            key=key, period_start=st["start"], period_end=st["end"],
            due_date=pay_date_for(st["end"], inp.pay_day, inp.pay_month_offset),
            overtime_hours=h["overtime"], in_law_hours=h["in_law"], part_time_hours=h["part_time"],
            night_hours=h["night"], holiday_le8_hours=h["holiday_le8"], holiday_gt8_hours=h["holiday_gt8"],
            overtime_night_hours=h["overtime_night"], holiday_night_hours=h["holiday_night"], unproven_hours=h["unproven"],
            lines=lines, contract_lines=contract_lines, legal_by_item=legal_by_item, contract_by_item=contract_by_item,
            legal_amount=sum(legal_by_item.values(), ZERO),
            contract_amount=None if contract_by_item is None else sum(contract_by_item.values(), ZERO),
            amount_by_item=dict(legal_by_item), amount=sum(legal_by_item.values(), ZERO),
            paid=paid, paid_total=paid.total, diff=ZERO, claim_amount=ZERO, note="; ".join(st["notes"]),
        ))
    fp = tuple((r.key, tuple(sorted(r.legal_by_item.items())),
                None if r.contract_by_item is None else tuple(sorted(r.contract_by_item.items()))) for r in rows)
    return _Core(rows, weeks, fp)


# ================================================================ 비교·충당(OT-18)
def _row_diffs(r: OvertimeRow) -> dict:
    if r.paid.lump:
        return {"all": r.amount - r.paid_total}
    return {i: r.amount_by_item.get(i, ZERO) - getattr(r.paid, i) for i in ITEMS}


def _offset(entries: list) -> dict:
    """[(행 번호, 차액)] 에서 음수(초과지급)를 지급기일이 먼저 온 부족분부터 충당."""
    pool = -sum((v for _, v in entries if v < 0), ZERO)
    out = {}
    for i, v in entries:
        if v <= 0:
            continue
        take = min(pool, v)
        pool -= take
        out[i] = out.get(i, ZERO) + v - take
    return out


def _allocate(rows: list, method: str, units: list) -> list:
    claims = [ZERO] * len(rows)
    if method == "erroneous":
        nets = [(i, sum(_row_diffs(r).values(), ZERO)) for i, r in enumerate(rows)]
        for i, v in _offset(nets).items():
            claims[i] += v
        return claims
    unit = method.split("/", 1)[1]
    if unit == "month":
        groups = [[i] for i in range(len(rows))]
    elif unit == "whole_period":
        groups = [list(range(len(rows)))]
    else:
        groups = []
        for s, e in units:
            groups.append([i for i, r in enumerate(rows) if s <= r.period_start and (e is None or r.period_end <= e)])
        covered = {i for g in groups for i in g}
        missing = [rows[i].key for i in range(len(rows)) if i not in covered]
        if missing:
            raise _err(f"compare_units 가 임금산정기간 {', '.join(missing)} 을(를) 온전히 덮지 않습니다")
    diffs = [_row_diffs(r) for r in rows]
    for g in groups:
        keys = sorted({k for i in g for k in diffs[i]})
        for k in keys:
            entries = [(i, diffs[i][k]) for i in g if k in diffs[i]]
            for i, v in _offset(entries).items():
                claims[i] += v
    return claims


def _methods(inp: OvertimeInput) -> list:
    out = ["erroneous", "contractual/month"]
    if inp.compare_units:
        out.append("contractual/pay_unit")
    out.append("contractual/whole_period")
    return out


# ================================================================ 계산
def _read_options(opts: dict | None) -> dict:
    opts = opts or {}
    out = {}
    for key, spec in OPTIONS.items():
        v = opts.get(key, spec.default)
        if spec.choices and v not in spec.choices:
            raise LaborError(f"옵션 {key} 의 값 {v!r} 은 허용되지 않습니다. 가능: {', '.join(map(str, spec.choices))}")
        out[key] = v
    return out


def _all_dates(inp: OvertimeInput) -> list:
    ds = [r.date for r in inp.days]
    for m in inp.months:
        y, mth = int(m.key[:4]), int(m.key[5:])
        ds.append(m.start or date(y, mth, inp.pay_period_start_day))
    return ds


def calculate_overtime(inp: OvertimeInput, opts: dict, **deps) -> OvertimeResult:
    o = _read_options(opts)
    if deps.get("hourly_of") is None and (inp.days or inp.months or inp.agreed_hours):
        raise _err("재산정에 통상시급(deps hourly_of)이 필요합니다")
    trace: list[Trace] = []
    warnings: list[str] = []
    for key, spec in OPTIONS.items():
        v = o[key]
        trace.append(Trace(spec.rule, f"옵션 {key}", str(v), spec.choices.get(v, spec.description) if spec.choices else spec.description))
    if deps.get("small_business") is None and not inp.headcount:
        trace.append(Trace("OT-01", "사업장 규모", "deps small_business 없음", "전 기간 상시 5명 이상으로 봄"))
    trace.append(Trace("OT-03", "부칙 <법률 제15513호> 제1조 제5항", "원문 재확인 대상", "제56조 개정규정 공포일(2018. 3. 20.) 시행으로 계산"))
    if o["ot_claim_basis"] in ("contract", "greater") and inp.agreed is None:
        raise _err(f"ot_claim_basis={o['ot_claim_basis']} 이면 agreed(약정 통상시급·가산율)가 필요합니다(OT-15)")
    if o["ot_compare_unit"] == "pay_unit" and not inp.compare_units:
        raise _err("ot_compare_unit=pay_unit 이면 compare_units(약정 임금 산정 단위기간)가 필요합니다(OT-18)")

    # ---- OT-05 선택 강제: 결과가 달라지는 경우만
    hw = ["exclude", "include"] if o["ot_holiday_in_weekly_40"] == "unset" else [o["ot_holiday_in_weekly_40"]]
    al = ["last_days_first", "chronological"] if o["ot_weekly_allocation"] == "unset" else [o["ot_weekly_allocation"]]
    cores = {}
    ctxs = {}
    for h in hw:
        for a in al:
            c = _Ctx(inp, o, deps, [], [])
            cores[(h, a)] = _core(c, h, a)
            ctxs[(h, a)] = c
    first = next(iter(cores))
    if len({c.fingerprint for c in cores.values()}) > 1:
        detail = ", ".join(f"{h}/{a} 재산정 {sum((r.legal_amount for r in c.rows), ZERO)}원" for (h, a), c in cores.items())
        need = []
        if len(hw) > 1 and any(cores[("exclude", a)].fingerprint != cores[("include", a)].fingerprint for a in al):
            need.append("ot_holiday_in_weekly_40(exclude | include)")
        if len(al) > 1 and any(cores[(h, "last_days_first")].fingerprint != cores[(h, "chronological")].fingerprint for h in hw):
            need.append("ot_weekly_allocation(last_days_first | chronological)")
        raise _err(f"선택에 따라 결과가 달라집니다(OT-05, 근거 없음) — 옵션 {', '.join(need)} 을(를) 사람이 정해야 합니다: {detail}")
    core = cores[first]
    ctx = ctxs[first]
    ctx.trace[:0] = trace
    trace, warnings = ctx.trace, ctx.warnings
    if len(cores) > 1 or o["ot_holiday_in_weekly_40"] == "unset" or o["ot_weekly_allocation"] == "unset":
        trace.append(Trace("OT-05", "주 초과분 배정·휴일 합산", "선택에 따라 결과가 같음", f"계산에 쓴 값 {first[0]}/{first[1]}"))
    rows = core.rows

    # ---- OT-15 기준 선택
    legal_total = sum((r.legal_amount for r in rows), ZERO)
    contract_total = None
    basis = "legal"
    if inp.agreed is not None:
        contract_total = sum((r.contract_amount for r in rows), ZERO)
        choice = o["ot_claim_basis"]
        if choice in ("contract", "greater") and not inp.agreed.valid:
            if choice == "contract":
                raise _err("약정 산정방법이 법 기준에 미달해 유효하지 않다고 입력(agreed.valid=false)했으므로 약정 기준으로 청구할 수 없습니다(97다14200)")
            ctx.warn("약정 산정방법이 유효하지 않아(agreed.valid=false) 법정 기준으로 계산했습니다(OT-07·15)")
        elif choice == "contract" or (choice == "greater" and contract_total > legal_total):
            basis = "contract"
        trace.append(Trace("OT-15", "법정 전체·약정 전체 비교", f"법정 {legal_total} / 약정 {contract_total} → {basis}",
                           "요소별 취사선택 금지(2006다81523, 2019다261084)"))
    if basis == "contract":
        for r in rows:
            r.amount_by_item = dict(r.contract_by_item)
            r.amount = r.contract_amount
    for r in rows:
        r.diff = r.amount - r.paid_total

    # ---- OT-17 포괄임금 게이트
    alternatives: dict = {}
    method = ""
    if inp.inclusive_wage == "valid_hard_to_measure":
        trace.append(Trace("OT-17", "포괄임금", INCLUSIVE[inp.inclusive_wage], "차액 0"))
        ctx.warn("근로시간 산정이 어려워 포괄임금 약정이 유효하다고 입력 — 실근로시간 전제 차액 청구는 받아들여지지 않아 합계 0(2008다6052)")
        claims_amt = [ZERO] * len(rows)
        method = "inclusive_valid"
    else:
        if inp.inclusive_wage != "none":
            trace.append(Trace("OT-17", "포괄임금", INCLUSIVE[inp.inclusive_wage], "법정수당 − 기지급 정액·명목 수당"))
            if not any(r.paid.lump or r.paid_total for r in rows):
                ctx.warn("포괄임금 사안인데 기지급 정액수당(paid.lump)이 입력되지 않았습니다")
        allocs = {m: _allocate(rows, m, inp.compare_units) for m in _methods(inp)}
        alternatives = {m: sum(v, ZERO) for m, v in allocs.items()}
        char, unit = o["ot_overpayment_character"], o["ot_compare_unit"]
        if char == "erroneous":
            cands = ["erroneous"]
        elif char == "contractual":
            cands = [m for m in allocs if m.startswith("contractual/")] if unit == "unset" else [f"contractual/{unit}"]
        else:
            if unit == "unset":
                cands = list(allocs)
            else:
                cands = ["erroneous", f"contractual/{unit}"]
        distinct = {tuple(allocs[m]) for m in cands}
        if len(distinct) > 1:
            detail = ", ".join(f"{m} {alternatives[m]}원" for m in cands)
            need = []
            if char == "unset":
                need.append("ot_overpayment_character(erroneous | contractual)")
            if unit == "unset" and len({tuple(allocs[m]) for m in cands if m.startswith("contractual/")}) > 1:
                need.append("ot_compare_unit(month | pay_unit | whole_period)")
            raise _err(f"초과 지급분 충당 방식에 따라 결과가 달라집니다(OT-18, 불명확) — 옵션 {', '.join(need)} 을(를) 사람이 정해야 합니다: {detail}")
        method = cands[0]
        claims_amt = allocs[method]
        if len(cands) > 1:
            trace.append(Trace("OT-18", "비교 단위·충당", "선택지별 결과가 같음", ", ".join(cands)))
        else:
            trace.append(Trace("OT-18", "비교 단위·충당", method, "충당은 지급기일이 먼저 온 부족분부터"))
    for r, c in zip(rows, claims_amt):
        r.claim_amount = c
        if r.diff < 0:
            r.note = "; ".join(x for x in (r.note, f"기지급 {r.paid_total}원이 재산정 {r.amount}원보다 많음") if x)
        if r.paid.lump:
            r.note = "; ".join(x for x in (r.note, "정액수당(lump) — 항목 합계로 비교") if x)

    # ---- 경고
    dates = _all_dates(inp)
    if dates:
        lo, hi = min(dates), max(dates)
        if lo < DATE_OLD_STANDARD_WARN and not inp.standard_hours:
            ctx.warn("2011. 7. 1. 전 날짜가 있습니다 — 그때 법정 1주 기준시간이 44시간이었을 수 있어 standard_hours 이력을 확인해야 합니다(M10)")
        if lo < DATE_ORDINARY_2024 <= hi:
            ctx.warn("청구기간이 2024. 12. 19.(2023다302838 통상임금 법리 변경)을 걸칩니다 — hourly_of 가 그날로 나뉘었는지 확인해야 합니다(M6)")
        if any(ctx.small(d) for d in dates):
            ctx.warn("상시 4명 이하 기간이 있습니다 — 시행령 [별표 1] 원문(야간 가산 포함 여부)은 미확인이며 하급심 판단으로 가산 0 처리(OT-01)")
        if inp.part_time and o["ot_part_time_premium"] == "off":
            ctx.warn("단시간근로자 소정 초과근로 가산(기간제법 제6조 제3항)은 검증에서 원문 확인불가라 적용하지 않았습니다 — "
                     "확인 후 ot_part_time_premium 을 켜십시오(OT-08)")
    if inp.days:
        ctx.warn("일별 기록이 없는 날은 근로하지 않은 것으로 보고 1주 40시간을 판정했습니다 — 주 단위로 빠짐없이 적었는지 확인해야 합니다(OT-04)")
    unproven_total = sum((r.unproven_hours for r in rows), ZERO)
    if unproven_total:
        ctx.warn(f"증명되지 않은 시간 {unproven_total}시간은 계산에서 뺐습니다(간주합의 없으면 근로자 증명 — 2022다291153)")

    claims = []
    total = ZERO
    extra = {}
    for r in rows:
        if r.claim_amount <= 0:
            continue
        total += r.claim_amount
        extra[r.key] = extra.get(r.key, ZERO) + r.claim_amount
        label = f"{r.period_start.year}. {r.period_start.month}.분 시간외수당 차액"
        claims.append(Claim("시간외수당 차액", label, r.claim_amount, r.due_date, False,
                            note=f"임금산정기간 {_fmt(r.period_start)}~{_fmt(r.period_end)}, 정기지급일 {_fmt(r.due_date)}; "
                                 "임금채권 3년(제49조) — 기산점·소 제기일 대조는 지연손해금 모듈(OT-22)"))
    return OvertimeResult(rows=rows, total=total, claims=claims, trace=trace, warnings=warnings, extra_wages=extra,
                          weeks=core.weeks, alternatives=alternatives, basis=basis, legal_total=legal_total,
                          contract_total=contract_total, method=method)
