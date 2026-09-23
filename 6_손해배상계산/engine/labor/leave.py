"""연차휴가 발생일수와 미사용 연차휴가수당 (lane: annual_leave, 규칙 AL-01~AL-23, M1~M6).

사람이 사건.yaml `leave:` 절에 적은 산정기간별 출근 사실로 연차휴가 발생일수를 정하고,
사용·사용촉진 소멸을 뺀 미사용분에 1일 통상임금(deps `daily_ordinary_of(d)`)을 곱해
미사용 연차휴가수당을 낸다. 법적 판단(해고 무효, 쟁의행위 정당성, 사용촉진 적법성,
통상임금성, 회계연도 조항의 해석 범위 등)은 하지 않는다. 사람이 판정해 입력한 값으로 계산만 한다.
금액 기대값은 판결 원문 숫자로 검증했다(tests/test_labor_leave.py).

---------------------------------------------------------------- 적용 범위·법령 버전
AL-01 [법령] 상시 4명 이하 사업장은 제60조·제61조 미적용(제11조 제1항, 시행령 [별표 1] 제4장은
      "제54조, 제55조제1항, 제63조"만 열거). 4주 평균 1주 소정근로시간 15시간 미만이면 미적용
      (제18조 제3항 "… 15시간 미만인 근로자에 대하여는 제55조와 제60조를 적용하지 아니한다").
      15.00시간은 적용(`< 15`). 규모 판단 시점과 4주 평균의 판단 구간은 확인 안 됨 → 사람이 기간별 입력.
      산정기간 입력 `small_business` 가 있으면 그 값, 없으면 `leave.small_business`(전 기간)·worker.small_business_periods·
      deps `small_business(d)` 중 하나라도 참이면 상시 4명 이하로 본다.
AL-02 [법령·하급심] 법령 버전 분기
      - 2012. 8. 2.(법률 제11270호): 제2항에 '1년간 80퍼센트 미만 출근한 근로자' 추가. 부칙 제4조
        "이 법 시행 후의 근로기간이 최초로 1년이 되는 근로자로서 …부터 적용" → 산정기간 시작일이
        2012. 8. 2. 전이면 제2항(b) 미적용.
      - 2018. 5. 29.(법률 제15108호): 구 제3항(최초 1년 15일에 제2항 휴가 포함) 삭제, 제6항 제3호
        (육아휴직 출근 간주) 신설 — 부칙 제2조 "시행 후 최초로 육아휴직을 신청하는 근로자부터".
        구 제3항 삭제의 경과규정은 없고, 적용 기준은 부산지방법원 2022. 6. 10. 선고 2021가단304232
        (확정 표시) "2017. 5. 29. 이전의 입사자에 대하여는 위 조항이 적용되는 것으로 해석된다"뿐이다
        [하급심]. 입사 2017. 5. 29.이면 발생일이 시행일 당일이어서 경계 옵션을 둔다
        (`al_old_art60_3_cutoff`, `al_old_art60_3_compare`).
      - 2020. 3. 31.(법률 제17185호): 1년 미만자 제2항 휴가 사용기간을 '최초 1년의 근로가 끝날 때까지'로,
        제61조 제2항 신설. 부칙 제2조 "이 법 시행 전에 발생한 연차 유급휴가에 대해서는 종전의 규정에
        따른다" → 2020. 3. 31. 전 발생분은 발생일부터 1년 사용.
      - 2024. 10. 22.(법률 제20520호): 제6항 제4호·제5호(육아기·임신기 근로시간 단축으로 단축된
        근로시간) 출근 간주, 부칙 제6조 시행일 이후 단축 시작분부터.
      - 2026. 8. 20.(법률 제21373호, 타법개정): 제6항 제3호 인용조문 "제19조제1항" → "제19조". 산식 영향 없음.
      - 법률 제6974호 시행(규모별 2004. 7. 1.~2011. 7. 1.) 전 구법(월차, 10일/8일)은 범위 밖 → warning.

---------------------------------------------------------------- 발생
AL-03 [판례확립] 산정기간 P_k = 입사일 H(초일 산입)부터 1년 단위. 발생일 A_k = 1년 근로를 마친 다음 날.
      그날 근로관계가 존속해야 발생(마지막 근로일 T 에 대해 A_k <= T).
      대법원 2018. 6. 28. 선고 2016다48297 "연차휴가를 사용할 권리는 다른 특별한 정함이 없는 한 그 전년도
      1년간의 근로를 마친 다음 날 발생한다고 보아야 하므로, 그 전에 퇴직 등으로 근로관계가 종료한 경우에는
      … 연차휴가수당도 청구할 수 없다". 대법원 2021. 10. 14. 선고 2021다227100 (마지막 근로일 2018. 7. 31.,
      "그다음 날인 2018. 8. 1.에는 근로자의 지위에 있지 않으므로" 제1항 휴가 수당 불가).
      날짜는 달력 연산으로만 정한다(365일 상수 금지 — 2019. 3. 1.~2020. 2. 29.은 366일).
      대응일이 없으면 민법 제160조 제3항("최종의 월에 해당일이 없는 때에는 그 월의 말일로 기간이 만료")
      → 2020. 2. 29. 입사자의 1년 만료 2021. 2. 28., 발생일 3. 1. (`al_missing_anniversary`, 판례 미확인).
      산정기간 기준 `period_basis = hire_date | fiscal_year` (대법원 2000. 12. 22. 선고 99다10806).
M1   [판례확립] 발생시기 특약 예외: 대법원 2026. 9. 3. 선고 2024다206043 "근로계약, 취업규칙 등에서 '연차휴가를
      사용할 권리의 발생 시기'에 대하여 이와 달리 정하고 있고, 그에 따라 연차휴가를 사용할 권리가 실제로
      발생하였다면, 근로자는 그 후 근로관계가 종료하였더라도 … 청구할 수 있다". 환송 후 판결 없음.
      옵션 `al_accrual_rule_override=per_input` 일 때만 산정기간 입력 `accrual_date` 를 발생일로 쓴다.
AL-04 [법령] 제1항 "1년간 80퍼센트 이상 출근한 근로자에게 15일". 출근율은 끝수 없이 분수로 `>= 0.8`.
AL-05 [법령(일수 산식)·행정해석(80% 요건)] 제4항 가산: n(완성 계속근로연수) >= 3 이면
      15 + floor((n−1)/2), 상한 25일. 가산은 출근율 80% 충족 시에만(법제처-26-0162, 기속력 없음) →
      `al_bonus_requires_80pct`. 80% 미만 연도를 계속근로연수에 넣는지는 미해결 → 역년 기준으로 세고 warning.
AL-06 [판례확립(11일 상한)·행정해석(나머지)] 제2항 1개월 개근 1일.
      (a) 최초 1년 P_0: 월 구간 M_j = [H + j개월, H + (j+1)개월 − 1일], **j = 0…10 (11개월)**.
          발생일 = H + (j+1)개월(그날 근로관계 존속 필요). 12번째 달의 다음 날은 A_0 이어서 '1년 미만
          근로자'가 아니므로 제외 — 대법원 2021다227100 "최대 11일". 방학 등 비례는 입력값 0~1 소수
          (임금근로시간정책과-389 "1일 * 월 실질소정근로일수 / 월 소정근로일수").
      (b) 1년 이상·출근율 80% 미만: 그 1년(12개 월 구간) 중 개근한 달 수 × 1일을 A_k 에 발생
          (법제처-24-0114, 24-0778). 가산 없음.
      최초 1년 출근율 80% 미만자에게 (a)와 별도로 (b)를 더 주는지 근거 원문 없음 → 기본 비중복
      (`al_first_year_below80=no_double`), warning.
AL-07 [판례확립] 1년 초과 2년 이하 근로자 최대 26일 = 제2항 11일 + A_0 에 제1항 15일
      (대법원 2022. 9. 7. 선고 2022다245419). 구 제3항 적용 대상은 15일에서 공제.
      구 제3항 공제 방식 `al_old_art60_3_deduct`: granted(기본 — 2021가단304232 "1년차 11일, 2년차 4일")는
      최초 1년 제2항 발생일수를, used 는 조문 문언대로 사용일수를 15일에서 뺀다(used 이면 미사용 월 휴가는
      15일에 흡수되어 따로 보상하지 않음).

---------------------------------------------------------------- 출근율
AL-08 [판례확립] 출근율 = (현실 출근일수 + 출근 간주 일수) ÷ 연간 소정근로일수.
      대법원 2013. 12. 26. 선고 2011다4629 "1년간의 총 역일에서 … 근로의무가 없는 날로 정하여진 날을
      제외한 나머지 일수, 즉 연간 근로의무가 있는 일수".
M2   [법령] 제55조 제2항 공휴일 유급휴일(300명 이상·공공기관 2020. 1. 1., 30명 이상 2021. 1. 1.,
      5명 이상 2022. 1. 1.)은 근로의무 없는 날이다. 엔진은 달력을 만들지 않으므로 `scheduled_days`
      입력 시 사람이 반영한다 → warning.
AL-09 [법령·판례확립] 출근 간주(`deemed`, 분자·분모 모두 산입): 업무상 재해 휴업(제6항 제1호,
      대법원 2017. 5. 17. 선고 2014다232296 "장단을 불문하고 … 1년 전체에 걸치거나 … 달리 볼 … 이유가
      없다"), 출산전후·유산사산휴가(제2호), 법정 육아휴직(제3호, 2018. 5. 29. 이후 최초 신청분),
      육아기·임신기 근로시간 단축(제4·5호, 일수 환산 방법 확인 안 됨), 부당해고 기간(대법원 2014. 3. 13.
      선고 2011다95519 "연간 소정근로일수 및 출근일수에 모두 산입"), 위법 직장폐쇄(대법원 2019. 2. 14.
      선고 2015다66052), 무효 출근정지(대전고등법원 2019. 9. 19. 선고 2019나41, 확정 [하급심]).
      부당해고 기간은 `deemed.unfair_dismissal` 로 넣는다.
AL-10 [판례확립] 소정근로일수 제외(`excluded`): 정당한 쟁의행위·2018. 5. 29. 전 신청 육아휴직
      (2011다4629), 적법 직장폐쇄·노조전임(2015다66052), 약정휴직(임금근로시간정책과-389).
      S = 연간 소정근로일수, X = 제외일수, S' = S − X, W = 출근+간주. S' = 0 이면 미발생
      (2015다66052 "노조전임기간이 … 연간 총근로일 전부를 차지하고 있는 경우라면 … 발생하지 않는다").
      요건 W/S' >= 0.8, 일수 = 본래 일수 × S'/S. 비례 조건 `al_proration_mode`:
        supreme_2019(기본) 2015다66052 "출근일수가 연간 소정근로일수의 8할을 밑도는 경우에 한하여" 비례
        moel_always       고용노동부(임금근로시간정책과-389) 문언 — 제외기간 있으면 항상 비례
        supreme_2013      2011다4629 문언(2019 판결 이전 문언) — 항상 비례
      2015다66052는 구법(2012. 2. 1. 개정 전) 사안이므로 현행 제2항(b)와의 관계를 옵션으로 둔다
      (`al_below80_interplay`: prorate_only 기본 | max_with_art60_2 = 비례일수와 개근월수 중 큰 값).
AL-11 [판례확립·하급심] 결근: 적법 직장폐쇄 중 위법 쟁의 참가(2015다66052), 업무 외 병가(2019나41).
      입력상 출근일수에 넣지 않으면 된다. 정당한 정직·직위해제는 확인 안 됨 → `suspension_days` 와
      `al_lawful_suspension`(absent 기본 | excluded), warning.
AL-23 [불명확] 비례로 생긴 소수 일수: 판결은 25.5일·16.75일을 그대로 곱함(관찰) → `al_day_fraction`.

---------------------------------------------------------------- 사용·소멸
AL-16 [법령·판례확립] 제61조 사용촉진이 적법하고 근로자가 자발적으로 쓰지 않아 제60조 제7항 본문에 따라
      소멸하면 보상의무 없음. 산정기간 입력 `promotion.lawful`(사람 판단)이 있으면 그것을 쓰고, 날짜만
      있으면 창을 검사한다. 사용기간 말일 E, 기준일 B1 = (E + 1일) − 6개월(1년 미만자 제2항 휴가는 3개월).
      1차 촉구 창 `al_promotion_window`: after(기본) [B1, B1+9일] | both [B1−10일, B1+10일].
      'before' 창은 두지 않는다 — 대법원 2020. 2. 27. 선고 2019다279283 "6개월 전을 기준으로 10일 이내인
      2016. 7. 6."과 모순. 2차 지정통보는 (E + 1일) − 2개월(1년 미만자는 1개월)의 전날까지(경계 불명확).
      지정일에 근로했고 노무수령 거부가 없었던 일수(`worked_designated_days`)는 보상의무 존속(2019다279283).
      사용기간 중 퇴직하면 제7항 본문 소멸이 아니므로 촉진 효과를 인정하지 않는다(제61조 제1항 문언).
AL-20 [판례확립] 사용일수에는 소정근로일에 쉰 날만 넣는다(대법원 2019. 10. 18. 선고 2018다239110
      "휴일을 대체휴가일로 정할 수는 없다"). 엔진은 `used_days` 입력을 그대로 쓴다.
AL-21 [판례확립] 사용연도에 전혀 출근하지 못해도 이미 발생한 휴가의 수당 청구 가능, 이를 제한하는
      단협·취업규칙 무효(2014다232296). 엔진은 사용연도 출근을 요건으로 두지 않는다.

---------------------------------------------------------------- 수당
AL-12 [판례확립·법령] 기준임금은 취업규칙 등에 정함이 없으면 통상임금(2018다239110). 1일분 = 통상시급 ×
      1일 소정근로시간(시행령 제6조 제3항) — deps `daily_ordinary_of(d)` 가 준다.
M4   [판례확립·하급심] 약정 통상임금·약정 산식(예: 1.5배)이 있으면 법정 산식 결과와 **전체**를 비교해 큰 쪽을
      쓴다. 항목별 혼합(법정 통상임금 × 약정 배수 등) 금지 — 대법원 2026. 8. 13. 선고 2025다218891
      "근로기준법에서 정한 기준과 전체적으로 비교하여 그에 미치지 못하는 근로조건이 포함된 부분에 한하여
      무효", "임금 항목별로 … 유리한 것만을 개별적으로 취사선택하여 법정수당을 산정하는 것은 허용되지
      않는다"; 대전고등법원 2019나41(확정) 단협 '연차일수 × 통상일급 × 1.5'와 법정 '연차일수 × 통상일급' 중
      유리한 쪽. 약정 산식의 '통상임금'이 약정인지 법정인지는 사람이 `agreed_formula.wage_basis` 로 정한다.
      약정 휴가일수(`agreed_days`)가 있으면 약정 산식의 일수는 법정 미사용과 따로 '약정 일수 − 사용일수 − 촉진 소멸일수'로
      센다(법정 일수를 다 써도 약정 초과분은 남는다).
AL-13 [행정해석] 기준 시점: 휴가청구권이 남아 있는 마지막 날(사용기간 말일), 사용기간 중 퇴직이면 마지막
      근로일의 1일 통상임금(임금근로시간정책과-1018 "휴가청구권 … 이 남아 있는 마지막 달(사용기간 중 퇴직한
      경우에는 퇴직시)의 통상임금").
AL-18 [법령·행정해석] 단시간근로자: 시간 = 통상근로자 연차일수 × (단시간 주 소정근로시간 ÷ 통상근로자 주
      소정근로시간) × 8, "1시간 미만은 1시간으로 본다"(시행령 [별표 2] 4. 나목), 임금은 시간급 기준(마목).
      비교 통상근로자 없으면 40시간(임금근로시간과-2754). `al_pt_hour_rounding`.
      시간급은 deps `hourly_of(d)`(통상시급)가 있으면 그 값, 없으면 1일 통상임금 ÷ `daily_hours` 로 환산하고 warning
      (두 모듈의 1일 소정근로시간이 다르면 금액이 틀린다). `daily_hours` 는 사용일수를 시간으로 바꾸는 데도 쓴다.
AL-19 [불명확] 통상·단축근로 혼재 월 단위 비례(근로개선정책과-4216, 재대조 못함, 2024. 10. 22. 개정 후 불명확)
      → `al_mixed_reduced_hours`(none 기본 = 미적용 + warning).
AL-22 [불명확] 끝수: 법령 규정 없음. `al_final_rounding` floor(원 미만 버림, 기본) | floor10 | half_up.
      서울서부지방법원 2023. 6. 16. 선고 2022나48711(확정) "통상임금 5,137,570원 × 1/209시간 × 8시간 ×
      … 25.5일, 10원 미만 버림" = 5,014,660원 — 일당을 먼저 끊으면 5,014,650원이 되어 불일치하므로
      `al_round_after_full_product`(기본 true, 전체 곱한 뒤 끝수). 부산 2021가단304232 '최종 계산액 중 원 이하
      버림'은 인용액 끝자리가 모두 0 → floor10 사례. Decimal 나눗셈 오차는 소수 10자리 반올림 후 끝수처리.

---------------------------------------------------------------- 청구권·지급기일·시효
AL-14 [하급심·행정해석] 청구권 발생일(`claim_arises`)과 지급기일(`pay_due_date`)을 나눈다.
      재직 중: 청구권 발생일 = 사용기간 말일 다음 날(임금근로시간정책과-1018 "휴가권이 소멸된 날의 다음날에
      발생"). 지급기일 `al_in_service_due` = first_regular_payday(기본, 청구권 발생일 이후 첫 정기지급일 —
      대전고등법원 2019나41 "2011년 근무에 따른 연월차휴가 중 미사용분에 대한 피고의 수당지급의무는 …
      2013. 1. 25.에 비로소 발생", 지연손해금 2013. 1. 26.부터) | claim_arises.
      퇴직: 근로관계 종료일(마지막 근로일 T) 다음 날을 지급사유 발생일로 보고 그날부터 14일이 되는 날(T+14일)을
      지급기한 말일로 둔다(제36조). Claim(settlement=True). 지연손해금은 T+15일부터 — 서울중앙지방법원
      2024. 7. 23. 선고 2023나72464 "2018. 3. 8.(원고의 퇴직일로부터 14일 경과 다음날)"(2018. 2. 21.까지 근무),
      2022나48711(2017. 6. 30. 근무 → 7. 15.), 2021가단304232(12. 31. → 1. 15., 2. 29. → 3. 15.),
      서울서부지방법원 2020가단278289(12. 10. → 12. 25.) 모두 일치.
      재직 중 청구권이 생긴 분도 퇴직 판결에서는 퇴직 후 14일 경과일부터 일괄 기산한 예가 있어(2023나72464,
      2020가단278289) `al_due_when_retired = per_row(기본) | all_settlement` 옵션을 둔다.
M3   [하급심·법령] 재직 중 미지급 수당의 지연이자(제37조 제1항 제2호, 2025. 10. 23. 이후 지급사유 발생분)
      적용 여부는 지연손해금 모듈이 정한다. 이 모듈은 지급기일만 넘긴다(Claim.note).
AL-15 [판례확립] 소멸시효 3년, 기산점 = 휴가권 취득일부터 1년 경과로 불실시가 확정된 다음 날(대법원 2023. 11. 16.
      선고 2022다231403). 시효 완성일 = 기산일 + 3년 − 1일(기산일이 0시 시작 → 초일 산입; 이날까지 행사하면
      시효 미완성. 대응일이 없으면 민법 제160조 제3항 — `al_missing_anniversary` 와 무관). 퇴직 시 기산점
      `al_retire_prescription_start = day_after_termination(기본, 수원지방법원 2017나8903 스니펫) | end_of_use_period`.
      **시효 완성 여부는 판정하지 않는다** — warnings 에 '소 제기일과 대조 필요'로 적고 지연손해금 모듈이 최종 표시한다.

---------------------------------------------------------------- 회계연도 기준
AL-17 [행정해석·하급심] `period_basis=fiscal_year` 이면 산정기간은 회계연도, 발생일은 다음 회계연도 시작일,
      발생일수는 사업장 규칙에 따라 실제 부여한 `granted_days`(필수). 회계연도 조항의 해석 범위
      `fy_clause_scope` 는 사람이 정해 반드시 입력한다(기본값 없음):
        grant_date_only  조항이 부여 시점만 정함 → 퇴직 시 입사일 기준 누적 법정일수 N_hire 와 회계연도 기준
                         누적 부여일수 N_fy 를 비교, N_hire > N_fy 이면 차이 일수를 퇴직 시 통상임금으로 정산
                         (근로기준과-5802·임금근로시간정책과-1960 — 재대조 전까지 확인불가).
                         N_hire 산정 자료는 `hire_basis_periods`(없으면 결근 없음으로 가정 + warning).
        accrual_period   조항이 계속근로기간 산정까지 정함 → 입사일 기준 재산정 없음(의정부지방법원 2026. 2. 5.
                         선고 2024나226635, 대법원 2026다202306 상고기각으로 확정).
      N_fy > N_hire 이고 재산정 단서(`recalc_clause`)가 있어도 엔진은 청구액을 줄이지 않고 warning 만 낸다.
M5   [판례확립·하급심] 회계연도 일률 기준의 적법 요건(99다10806 "그 기준일 이전의 1년 이내에 채용된 근로자에
      대하여 잔여기간을 출근한 것으로 보고 1년간 계속근로한 것으로 취급하여 연차휴가를 실시한다면 …
      적법") 충족 여부는 사람이 판단 → warning. 입사년도 비례 부여(근로개선정책과-5352)는 확인불가.

---------------------------------------------------------------- 구현하지 않은 것
M6   [불명확] 해고·고용의무 불이행 기간의 연차수당 상당 손해에서 사용일수를 추정하는 방법(2020다230970,
      2021다245528)은 판시 문장을 확보하지 못해 구현하지 않는다. 사람이 `used_days` 를 정해 넣는다(warning).
      그 밖에: 2004~2011 구법(월차), 제60조 제7항 단서 이월, 초단시간 판단 구간(근로조건지도과-4378),
      사용자 귀책 휴업 기간 처리, 임금 평균 기준 시점(`period_average`)은 구현하지 않는다.

---------------------------------------------------------------- 사건.yaml `leave:` 절
    leave:
      hire_date: 2017-03-01          # 비우면 worker.hire_date
      last_working_day: 2019-12-31   # 근로관계 존속 마지막 날. 비우면 worker.last_working_day(재직 중이면 비움)
      calc_until: 2026-09-15         # 재직 중: 산정기간 자동 생성과 청구권 발생 판단의 기준일(선택)
      period_basis: hire_date        # hire_date | fiscal_year
      fiscal_year_start: "01-01"
      fy_clause_scope: null          # fiscal_year 이면 필수: grant_date_only | accrual_period
      recalc_clause: false           # 퇴직 시 입사일 기준 재산정 단서
      assume_full_attendance: false  # 출근 자료 없는 산정기간을 결근 없음으로 가정
      small_business: false          # 전 기간 상시 4명 이하(기간별이면 worker.small_business_periods)
      weekly_hours: 40               # 1주 소정근로시간(4주 평균)
      full_time_weekly_hours: 40     # 비교 통상근로자 1주 소정근로시간
      daily_hours: 8                 # 1일 소정근로시간
      agreed_formula:                # 약정 수당 산식(없으면 비움)
        multiplier: 1.5
        wage_basis: agreed           # agreed | statutory
        monthly_divisor: 183         # 약정 일급 = 월 통상임금 × daily_hours ÷ monthly_divisor
        daily_hours: 8
      agreed_ordinary_wage:          # 약정 통상임금 이력(from 이후 적용)
        - {from: 2020-01-01, monthly: 6832000}   # 또는 daily: 298666
      periods:                       # 산정기간(년차)별. start 는 모두 적거나(그 기간만 계산) 모두 비움(입사일부터 순서대로)
        - start: 2017-03-01
          scheduled_days: 248        # 연간 소정근로일수(제외기간 포함, 공휴일 유급휴일 반영)
          attended_days: 230         # 현실 출근일수
          deemed: {unfair_dismissal: 10}   # 출근 간주 사유별 일수(DEEMED_REASONS)
          excluded: {lawful_strike: 5}     # 소정근로일수 제외 사유별 일수(EXCLUDED_REASONS)
          suspension_days: 0         # 정당한 정직·직위해제 일수(al_lawful_suspension)
          monthly_perfect: [true, true, true, true, true, true, true, true, true, true, true, true]
          used_days: 3               # 이 기간 근로로 발생일에 생긴 휴가(제1·4항, 제2항 b) 중 사용일수
          used_monthly_days: 0       # 최초 1년 제2항(a) 월 휴가 중 사용일수
          used_hours: null           # 단시간근로자 사용시간(비우면 used_days × daily_hours)
          granted_days: null         # 사람이 확정한 발생일수(회계연도 기준이면 필수)
          agreed_days: null          # 단체협약 등 약정 휴가일수
          paid_amount: 0             # 기지급 수당(발생일 휴가분)
          paid_monthly_amount: 0     # 기지급 수당(최초 1년 월 휴가분)
          promotion: {lawful: null, first_notice: 2018-09-03, second_notice: 2018-12-20,
                      worker_designated_all: false, worked_designated_days: 0}
          promotion_monthly: null    # 1년 미만자 제2항 휴가 촉진(제61조 제2항)
          small_business: null
          weekly_hours: null
          daily_hours: null
          accrual_date: null         # 발생시기 특약(al_accrual_rule_override=per_input)
          reduced_hours: null        # {months: 4, weekly_hours: 20} 통상·단축근로 혼재
      hire_basis_periods: []         # fiscal_year + grant_date_only 비교용 입사일 기준 출근 자료
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_CEILING, ROUND_DOWN, ROUND_HALF_UP, Decimal, InvalidOperation

from .common import (
    Claim,
    LaborError,
    OptionSpec,
    Trace,
    add_months,
    dec,
    is_within,
    parse_date,
    round_to,
)

__all__ = [
    "DEEMED_REASONS", "EXCLUDED_REASONS", "OPTIONS", "RULES",
    "AgreedFormula", "AgreedWage", "LeaveInput", "LeavePeriodInput", "LeaveResult", "LeaveRow",
    "PromotionInput", "ReducedHoursInput",
    "calculate_leave", "load_leave", "period_span", "promotion_first_notice_window",
]

ZERO = Decimal(0)
ONE = Decimal(1)
RATE_80 = Decimal("0.8")

DATE_ART60_2B = date(2012, 8, 2)        # 법률 제11270호 시행
DATE_ART60_3_REPEAL = date(2018, 5, 29)  # 법률 제15108호 시행
DATE_2020_AMEND = date(2020, 3, 31)      # 법률 제17185호 시행
DATE_2024_AMEND = date(2024, 10, 22)     # 법률 제20520호 제60조 제6항 시행
DATE_OLD_LAW_END = date(2011, 7, 1)      # 법률 제6974호 규모별 시행 완료
DATE_PUBLIC_HOLIDAY_FIRST = date(2020, 1, 1)

DEEMED_REASONS = {
    "industrial_accident": "업무상 부상·질병 휴업(제60조 제6항 제1호, 대법원 2014다232296)",
    "maternity": "출산전후휴가·유산사산휴가(제60조 제6항 제2호)",
    "parental_leave": "법정 육아휴직(제60조 제6항 제3호, 2018. 5. 29. 이후 최초 신청분)",
    "childcare_reduced_hours": "육아기 근로시간 단축으로 단축된 근로시간(제6항 제4호, 2024. 10. 22. 이후 시작분)",
    "pregnancy_reduced_hours": "임신기 근로시간 단축으로 단축된 근로시간(제6항 제5호, 2024. 10. 22. 이후 시작분)",
    "unfair_dismissal": "부당해고 기간(대법원 2011다95519)",
    "unlawful_lockout": "위법한 직장폐쇄 기간(대법원 2015다66052)",
    "void_suspension": "무효인 출근정지 기간(대전고등법원 2019나41, 확정)",
    "other": "기타 출근 간주(근거를 비고에 적을 것)",
}

EXCLUDED_REASONS = {
    "lawful_strike": "정당한 쟁의행위 기간(대법원 2011다4629)",
    "old_parental_leave": "2018. 5. 29. 전 신청 법정 육아휴직(대법원 2011다4629)",
    "lawful_lockout": "적법한 직장폐쇄 기간(대법원 2015다66052)",
    "union_full_time": "노조전임 기간(대법원 2015다66052)",
    "agreed_leave": "약정 육아휴직·업무 외 상병휴직 등 약정휴직(임금근로시간정책과-389)",
    "other": "기타 근로제공의무 면제 기간(근거를 비고에 적을 것)",
}

OPTIONS: dict[str, OptionSpec] = {s.key: s for s in [
    OptionSpec("al_old_art60_3_cutoff", "2017-05-29",
               "구 제60조 제3항(최초 1년 15일에 제2항 휴가 포함)을 적용할 입사일 기준일", "AL-02"),
    OptionSpec("al_old_art60_3_compare", "le", "구 제3항 기준일 비교", "AL-02", {
        "le": "기준일 이전(당일 포함) 입사자에게 적용 — 부산지방법원 2021가단304232 '2017. 5. 29. 이전의 입사자'",
        "lt": "기준일 전날까지 입사자에게만 적용 — 입사 2017. 5. 29.이면 발생일이 시행일 당일이라는 해석",
    }),
    OptionSpec("al_old_art60_3_deduct", "granted", "구 제3항 15일에서 빼는 일수", "AL-07", {
        "granted": "최초 1년 제2항 발생일수(2021가단304232 '1년차 11일, 2년차 4일')",
        "used": "최초 1년 제2항 휴가 중 사용일수(조문 문언) — 미사용 월 휴가는 15일에 흡수",
    }),
    OptionSpec("al_missing_anniversary", "civil_code", "기간 말일의 대응일이 없을 때(2. 29.·월말 입사)", "AL-03", {
        "civil_code": "민법 제160조 제3항 — 그 월 말일로 만료, 다음 날 발생(판례 미확인)",
        "clamp": "그 월 말일을 대응일로 보아 전날 만료, 말일에 발생",
    }),
    OptionSpec("al_accrual_rule_override", "none", "발생시기 특약(M1, 대법원 2024다206043)", "AL-03", {
        "none": "원칙 — 1년 근로를 마친 다음 날 발생(2016다48297)",
        "per_input": "산정기간 입력 accrual_date 를 취업규칙 등이 정한 발생일로 사용",
    }),
    OptionSpec("al_bonus_requires_80pct", True, "가산휴가를 출근율 80% 충족 시에만 부여", "AL-05", {
        True: "80% 충족 시에만 가산(법제처-26-0162)",
        False: "80% 미만 연도에도 가산일수를 제2항(b) 일수에 더함",
    }),
    OptionSpec("al_first_year_below80", "no_double", "최초 1년 출근율 80% 미만자의 제2항(a)·(b) 관계", "AL-06", {
        "no_double": "(a) 월 개근 휴가만(비중복, 근거 원문 없음)",
        "add_art60_2b": "A_0 에 12개월 중 개근월수 × 1일을 (a)와 별도로 추가",
    }),
    OptionSpec("al_proration_mode", "supreme_2019", "소정근로일수 제외기간이 있을 때 비례 조건", "AL-10", {
        "supreme_2019": "출근일수 < 연간 소정근로일수 × 0.8 인 경우에만 비례(대법원 2015다66052)",
        "moel_always": "제외기간이 있으면 항상 비례(임금근로시간정책과-389 문언)",
        "supreme_2013": "항상 비례(2011다4629 문언, 2019 판결 이전 문언)",
    }),
    OptionSpec("al_below80_interplay", "prorate_only", "비례 삭감된 제1항 휴가와 제2항(b)의 관계", "AL-10", {
        "prorate_only": "비례 일수만(2015다66052 구법 사안 방식)",
        "max_with_art60_2": "비례 일수와 개근월수 × 1일 중 큰 값",
    }),
    OptionSpec("al_day_fraction", "keep_decimal", "비례로 생긴 소수 일수", "AL-23", {
        "keep_decimal": "소수 그대로 곱함(2022나48711 25.5일, 2024나226635 16.75일 관찰)",
        "ceil_day": "1일 단위 올림",
        "floor_day": "1일 단위 버림",
        "to_hours": "일수 × 1일 소정근로시간을 시간 단위로 올림",
    }),
    OptionSpec("al_pt_hour_rounding", "ceil_total", "단시간근로자 연차시간의 1시간 미만", "AL-18", {
        "ceil_total": "총시간에 1시간 미만 끝수가 있으면 1시간으로 올림(시행령 별표2 4. 나목)",
        "none": "끝수 그대로",
    }),
    OptionSpec("al_mixed_reduced_hours", "none", "통상근로·단축근로 혼재 연도의 월 단위 비례", "AL-19", {
        "none": "미적용(불명확) — 입력이 있으면 warning",
        "moel_2013_prorate": "근로개선정책과-4216 산식(재대조 못함)",
    }),
    OptionSpec("al_lawful_suspension", "absent", "정당한 정직·직위해제 기간", "AL-11", {
        "absent": "결근(소정근로일수에 포함, 출근 아님)",
        "excluded": "소정근로일수에서 제외(비례)",
    }),
    OptionSpec("al_promotion_window", "after", "제61조 1차 촉구 '6개월(3개월) 전을 기준으로 10일 이내'의 창", "AL-16", {
        "after": "기준일부터 10일(기준일 포함) — 2019다279283 사실 서술과 부합",
        "both": "기준일 전후 10일",
    }),
    OptionSpec("al_final_rounding", "floor", "수당 최종 금액 끝수", "AL-22", {
        "floor": "원 미만 버림",
        "floor10": "10원 미만 버림(2022나48711, 2021가단304232)",
        "half_up": "원 미만 반올림",
    }),
    OptionSpec("al_round_after_full_product", True, "1일분 × 일수 전체를 곱한 뒤 끝수처리", "AL-22", {
        True: "전체 곱 후 끝수(2022나48711과 일치)",
        False: "1일분(단시간은 시간급)을 먼저 원 미만 끝수처리한 뒤 곱함",
    }),
    OptionSpec("al_in_service_due", "first_regular_payday", "재직 중 청구권 발생분의 지급기일", "AL-14", {
        "first_regular_payday": "청구권 발생일 이후(당일 포함) 첫 정기지급일(대전고등법원 2019나41)",
        "claim_arises": "청구권 발생일 당일(임금근로시간정책과-1018)",
    }),
    OptionSpec("al_due_when_retired", "per_row", "퇴직자의 재직 중 청구권 발생분 지급기일", "AL-14", {
        "per_row": "행별 지급기일. 지급기일 전에 퇴직했으면 min(지급기일, 퇴직 후 14일)",
        "all_settlement": "모든 미지급분을 퇴직 후 14일 기한으로(2023나72464, 2020가단278289 관찰)",
    }),
    OptionSpec("al_retire_prescription_start", "day_after_termination", "사용기간 중 퇴직한 경우 시효 기산점", "AL-15", {
        "day_after_termination": "근로관계 종료 다음 날(수원지방법원 2017나8903 스니펫)",
        "end_of_use_period": "본래 사용기간 말일 다음 날",
    }),
]}

RULES: dict[str, tuple[str, str]] = {
    "AL-01": ("상시 5명 이상·4주 평균 주 15시간 이상에만 제60조 적용", "법령"),
    "AL-02": ("법령 버전 분기(2012. 8. 2./2018. 5. 29./2020. 3. 31./2024. 10. 22./2026. 8. 20.), 구 제3항 적용 기준일은 하급심", "법령·하급심"),
    "AL-03": ("입사일부터 1년 단위, 1년 근로를 마친 다음 날 근로관계 존속 시 발생(날짜 연산)", "판례확립"),
    "AL-04": ("출근율 80% 이상이면 15일", "법령"),
    "AL-05": ("3년 이상 매 2년 1일 가산, 25일 한도, 80% 요건은 법제처 해석", "법령·행정해석"),
    "AL-06": ("1개월 개근 1일: 1년 미만 최대 11일(j=0…10), 80% 미만자 개근월수, 최초 1년 비중복", "판례확립·행정해석"),
    "AL-07": ("1년 초과 2년 이하 최대 26일", "판례확립"),
    "AL-08": ("출근율 = 출근일수 ÷ 연간 소정근로일수", "판례확립"),
    "AL-09": ("업무상 재해·출산휴가·육아휴직·부당해고 등 출근 간주(무효 출근정지는 하급심)", "법령·판례확립"),
    "AL-10": ("쟁의·노조전임·약정휴직 등 소정근로일수 제외 후 비례", "판례확립"),
    "AL-11": ("적법 직장폐쇄 중 위법 쟁의·업무 외 병가는 결근", "판례확립·하급심"),
    "AL-12": ("미사용수당 기준임금은 통상임금, 1일분 = 시급 × 1일 소정근로시간", "판례확립·법령"),
    "AL-13": ("휴가청구권이 남은 마지막 날(퇴직 시 퇴직 시점)의 통상임금", "행정해석"),
    "AL-14": ("청구권 발생일과 지급기일 분리, 퇴직 시 마지막 근로일 + 14일 기한", "하급심·행정해석"),
    "AL-15": ("소멸시효 3년, 기산점은 사용기간 만료 다음 날", "판례확립"),
    "AL-16": ("적법한 사용촉진 시 미사용분 보상의무 소멸, 지정일 근로 시 존속", "법령·판례확립"),
    "AL-17": ("회계연도 기준 부여와 퇴직 정산(조항 해석 범위 입력)", "행정해석·하급심"),
    "AL-18": ("단시간근로자 시간 비례, 1시간 미만 1시간", "법령·행정해석"),
    "AL-19": ("통상·단축근로 혼재 월 단위 비례", "불명확"),
    "AL-20": ("휴일에 쉰 날은 연차 사용일이 아님", "판례확립"),
    "AL-21": ("사용연도 출근 여부와 무관하게 수당 청구 가능", "판례확립"),
    "AL-22": ("수당 끝수(원 미만 버림·10원 미만 버림·반올림), 전체 곱 후 끝수", "불명확"),
    "AL-23": ("비례 소수 일수·단시간 시간의 끝수", "불명확"),
    "M1": ("발생시기 특약이 있고 실제 발생했으면 퇴직 후에도 청구(2024다206043)", "판례확립"),
    "M2": ("공휴일 법정 유급휴일(규모별 2020~2022 시행)을 소정근로일수에 반영 — 사람이 입력", "법령"),
    "M3": ("재직 중 미지급 수당의 지급기일과 제37조 제1항 제2호 지연이자 — 지연손해금 모듈이 판단", "하급심·법령"),
    "M4": ("약정 통상임금·약정 산식과 법정 결과 전체 비교, 항목별 혼합 금지", "판례확립·하급심"),
    "M5": ("회계연도 일률 기준의 적법 요건(99다10806)과 조항 해석(2024나226635)", "판례확립·하급심"),
    "M6": ("해고·고용의무 불이행 기간 연차수당 상당 손해의 사용일수 추정 — 미구현", "불명확"),
}


# ================================================================ 입력
@dataclass
class PromotionInput:
    """제61조 사용촉진. lawful 이 있으면 그 판단을 쓰고, 날짜만 있으면 창을 검사한다."""

    lawful: bool | None = None
    first_notice: date | None = None
    second_notice: date | None = None
    worker_designated_all: bool = False
    worked_designated_days: Decimal = ZERO


@dataclass
class ReducedHoursInput:
    """통상근로·단축근로 혼재 연도(AL-19)."""

    months: Decimal
    weekly_hours: Decimal


@dataclass
class LeavePeriodInput:
    start: date | None = None
    scheduled_days: Decimal | None = None
    attended_days: Decimal | None = None
    deemed: dict = field(default_factory=dict)
    excluded: dict = field(default_factory=dict)
    suspension_days: Decimal = ZERO
    monthly_perfect: list | None = None
    used_days: Decimal = ZERO
    used_monthly_days: Decimal = ZERO
    used_hours: Decimal | None = None
    granted_days: Decimal | None = None
    agreed_days: Decimal | None = None
    paid_amount: Decimal = ZERO
    paid_monthly_amount: Decimal = ZERO
    promotion: PromotionInput | None = None
    promotion_monthly: PromotionInput | None = None
    small_business: bool | None = None
    weekly_hours: Decimal | None = None
    daily_hours: Decimal | None = None
    accrual_date: date | None = None
    reduced_hours: ReducedHoursInput | None = None
    note: str = ""

    @property
    def has_attendance(self) -> bool:
        return self.scheduled_days is not None and self.attended_days is not None


@dataclass
class AgreedFormula:
    multiplier: Decimal = ONE
    wage_basis: str = "agreed"            # agreed | statutory
    monthly_divisor: Decimal | None = None
    daily_hours: Decimal | None = None


@dataclass
class AgreedWage:
    start: date
    monthly: Decimal | None = None
    daily: Decimal | None = None


@dataclass
class LeaveInput:
    hire_date: date
    last_working_day: date | None = None
    calc_until: date | None = None
    period_basis: str = "hire_date"
    fiscal_year_start: tuple = (1, 1)
    fy_clause_scope: str | None = None
    recalc_clause: bool = False
    assume_full_attendance: bool = False
    small_business: bool = False
    small_business_periods: list = field(default_factory=list)
    weekly_hours: Decimal | None = None
    full_time_weekly_hours: Decimal = Decimal(40)
    daily_hours: Decimal = Decimal(8)
    pay_day: int | None = None
    agreed_formula: AgreedFormula | None = None
    agreed_ordinary_wage: list = field(default_factory=list)
    periods: list = field(default_factory=list)
    hire_basis_periods: list | None = None


# ================================================================ 결과
@dataclass
class LeaveRow:
    """계산표 한 줄. kind: main(발생일 휴가) | monthly(최초 1년 월 개근) | settlement(회계연도 퇴직 정산)."""

    period_no: int
    period_start: date | None
    period_end: date | None
    kind: str
    accrual_date: date | None
    source: str
    attendance_rate: Decimal | None
    accrued_days: Decimal
    accrued_hours: Decimal | None
    unit: str                       # '일' | '시간'
    used: Decimal
    extinguished: Decimal           # 사용촉진 소멸
    unused: Decimal
    use_end: date | None
    wage_ref_date: date | None
    daily_wage: Decimal | None
    statutory_amount: Decimal
    agreed_amount: Decimal | None
    amount: Decimal                 # 선택된 산식의 수당액
    paid_amount: Decimal
    claim_amount: Decimal           # amount − 기지급(음수면 0)
    claim_arises: date | None
    pay_due_date: date | None
    settlement: bool
    prescription_date: date | None
    promotion_lawful: bool | None
    claim_pending: bool
    note: str


@dataclass
class LeaveResult:
    rows: list
    total: Decimal
    claims: list
    trace: list
    warnings: list
    basis: str = "statutory"
    statutory_total: Decimal = ZERO
    agreed_total: Decimal | None = None
    hire_basis_days: Decimal | None = None
    fiscal_basis_days: Decimal | None = None


# ================================================================ 읽기
_PERIOD_KEYS = {
    "start", "scheduled_days", "attended_days", "deemed", "excluded", "suspension_days", "monthly_perfect",
    "used_days", "used_monthly_days", "used_hours", "granted_days", "agreed_days", "paid_amount",
    "paid_monthly_amount", "promotion", "promotion_monthly", "small_business", "weekly_hours", "daily_hours",
    "accrual_date", "reduced_hours", "note",
}
_LEAVE_KEYS = {
    "hire_date", "last_working_day", "calc_until", "period_basis", "fiscal_year_start", "fy_clause_scope",
    "recalc_clause", "assume_full_attendance", "small_business", "weekly_hours", "full_time_weekly_hours",
    "daily_hours", "pay_day", "agreed_formula", "agreed_ordinary_wage", "periods", "hire_basis_periods",
}


def _num(v, label: str, default=None) -> Decimal | None:
    if v is None or v == "":
        return default
    if isinstance(v, bool):
        raise LaborError(f"연차: {label} 은(는) 숫자여야 합니다: {v!r}")
    try:
        return dec(v)
    except (InvalidOperation, ValueError, TypeError):
        raise LaborError(f"연차: {label} 은(는) 숫자여야 합니다: {v!r}") from None


def _date(v, label: str) -> date | None:
    if v is None or v == "":
        return None
    try:
        return parse_date(v)
    except (ValueError, TypeError):
        raise LaborError(f"연차: {label} 날짜 형식이 올바르지 않습니다: {v!r}") from None


def _bool(v, label: str, default=None):
    if v is None or v == "":
        return default
    if isinstance(v, bool):
        return v
    raise LaborError(f"연차: {label} 은(는) true/false 여야 합니다: {v!r}")


def _load_promotion(raw, label: str) -> PromotionInput | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise LaborError(f"연차: {label} 은(는) 사전이어야 합니다")
    unknown = set(raw) - {"lawful", "first_notice", "second_notice", "worker_designated_all", "worked_designated_days"}
    if unknown:
        raise LaborError(f"연차: {label} 에 알 수 없는 키: {', '.join(sorted(unknown))}")
    return PromotionInput(
        lawful=_bool(raw.get("lawful"), f"{label}.lawful"),
        first_notice=_date(raw.get("first_notice"), f"{label}.first_notice"),
        second_notice=_date(raw.get("second_notice"), f"{label}.second_notice"),
        worker_designated_all=bool(_bool(raw.get("worker_designated_all"), f"{label}.worker_designated_all", False)),
        worked_designated_days=_num(raw.get("worked_designated_days"), f"{label}.worked_designated_days", ZERO),
    )


def _load_reasons(raw, table: dict, label: str) -> dict:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise LaborError(f"연차: {label} 은(는) '사유: 일수' 사전이어야 합니다")
    out = {}
    for key, v in raw.items():
        if key not in table:
            raise LaborError(f"연차: {label} 의 사유 {key!r} 를 알 수 없습니다. 가능: {', '.join(table)}")
        n = _num(v, f"{label}.{key}", ZERO)
        if n < 0:
            raise LaborError(f"연차: {label}.{key} 는 음수일 수 없습니다")
        out[key] = n
    return out


def _load_period(raw: dict, label: str) -> LeavePeriodInput:
    if not isinstance(raw, dict):
        raise LaborError(f"연차: {label} 은(는) 사전이어야 합니다")
    unknown = set(raw) - _PERIOD_KEYS
    if unknown:
        raise LaborError(f"연차: {label} 에 알 수 없는 키: {', '.join(sorted(unknown))}")
    monthly = raw.get("monthly_perfect")
    if monthly is not None:
        if not isinstance(monthly, (list, tuple)):
            raise LaborError(f"연차: {label}.monthly_perfect 는 목록이어야 합니다")
        vals = []
        for i, v in enumerate(monthly, 1):
            if isinstance(v, bool):
                vals.append(ONE if v else ZERO)
            else:
                n = _num(v, f"{label}.monthly_perfect[{i}]", ZERO)
                if not ZERO <= n <= ONE:
                    raise LaborError(f"연차: {label}.monthly_perfect[{i}] 는 0~1 이어야 합니다: {v!r}")
                vals.append(n)
        monthly = vals
    reduced = raw.get("reduced_hours")
    if reduced is not None:
        if not isinstance(reduced, dict) or "months" not in reduced or "weekly_hours" not in reduced:
            raise LaborError(f"연차: {label}.reduced_hours 에는 months 와 weekly_hours 가 필요합니다")
        reduced = ReducedHoursInput(_num(reduced["months"], f"{label}.reduced_hours.months"),
                                    _num(reduced["weekly_hours"], f"{label}.reduced_hours.weekly_hours"))
        if not ZERO <= reduced.months <= 12:
            raise LaborError(f"연차: {label}.reduced_hours.months 는 0~12 이어야 합니다")
    p = LeavePeriodInput(
        start=_date(raw.get("start"), f"{label}.start"),
        scheduled_days=_num(raw.get("scheduled_days"), f"{label}.scheduled_days"),
        attended_days=_num(raw.get("attended_days"), f"{label}.attended_days"),
        deemed=_load_reasons(raw.get("deemed"), DEEMED_REASONS, f"{label}.deemed"),
        excluded=_load_reasons(raw.get("excluded"), EXCLUDED_REASONS, f"{label}.excluded"),
        suspension_days=_num(raw.get("suspension_days"), f"{label}.suspension_days", ZERO),
        monthly_perfect=monthly,
        used_days=_num(raw.get("used_days"), f"{label}.used_days", ZERO),
        used_monthly_days=_num(raw.get("used_monthly_days"), f"{label}.used_monthly_days", ZERO),
        used_hours=_num(raw.get("used_hours"), f"{label}.used_hours"),
        granted_days=_num(raw.get("granted_days"), f"{label}.granted_days"),
        agreed_days=_num(raw.get("agreed_days"), f"{label}.agreed_days"),
        paid_amount=_num(raw.get("paid_amount"), f"{label}.paid_amount", ZERO),
        paid_monthly_amount=_num(raw.get("paid_monthly_amount"), f"{label}.paid_monthly_amount", ZERO),
        promotion=_load_promotion(raw.get("promotion"), f"{label}.promotion"),
        promotion_monthly=_load_promotion(raw.get("promotion_monthly"), f"{label}.promotion_monthly"),
        small_business=_bool(raw.get("small_business"), f"{label}.small_business"),
        weekly_hours=_num(raw.get("weekly_hours"), f"{label}.weekly_hours"),
        daily_hours=_num(raw.get("daily_hours"), f"{label}.daily_hours"),
        accrual_date=_date(raw.get("accrual_date"), f"{label}.accrual_date"),
        reduced_hours=reduced,
        note=str(raw.get("note") or ""),
    )
    if (p.scheduled_days is None) != (p.attended_days is None):
        raise LaborError(f"연차: {label} 에 scheduled_days 와 attended_days 는 함께 적어야 합니다")
    for name in ("scheduled_days", "attended_days", "used_days", "used_monthly_days", "granted_days"):
        v = getattr(p, name)
        if v is not None and v < 0:
            raise LaborError(f"연차: {label}.{name} 는 음수일 수 없습니다")
    return p


def load_leave(raw: dict, worker: dict | None = None) -> LeaveInput:
    """사건.yaml `leave:` 절(dict)과 `worker:` 절을 읽는다."""
    raw = dict(raw or {})
    worker = dict(worker or {})
    unknown = set(raw) - _LEAVE_KEYS
    if unknown:
        raise LaborError(f"연차: leave 절에 알 수 없는 키: {', '.join(sorted(unknown))}")

    hire = _date(raw.get("hire_date"), "hire_date") or _date(worker.get("hire_date"), "worker.hire_date")
    if hire is None:
        raise LaborError("연차: 입사일(leave.hire_date 또는 worker.hire_date)이 없습니다")
    last = (_date(raw.get("last_working_day"), "last_working_day")
            or _date(worker.get("last_working_day"), "worker.last_working_day"))
    if last is not None and last < hire:
        raise LaborError(f"연차: 마지막 근로일 {last} 이 입사일 {hire} 보다 앞섭니다")

    basis = raw.get("period_basis") or "hire_date"
    if basis not in ("hire_date", "fiscal_year"):
        raise LaborError(f"연차: period_basis 는 hire_date 또는 fiscal_year 여야 합니다: {basis!r}")
    fys = str(raw.get("fiscal_year_start") or "01-01").replace(".", "-").strip("-").split("-")
    try:
        fy_start = (int(fys[0]), int(fys[1]))
        date(2001, *fy_start)
    except (ValueError, IndexError):
        raise LaborError(f"연차: fiscal_year_start 는 'MM-DD'(2. 29. 제외)여야 합니다: {raw.get('fiscal_year_start')!r}") from None
    scope = raw.get("fy_clause_scope")
    if basis == "fiscal_year":
        if scope not in ("grant_date_only", "accrual_period"):
            raise LaborError("연차: 회계연도 기준(period_basis: fiscal_year)이면 fy_clause_scope "
                             "(grant_date_only | accrual_period)를 사람이 정해 적어야 합니다")
    elif scope is not None and scope not in ("grant_date_only", "accrual_period"):
        raise LaborError(f"연차: fy_clause_scope 값을 알 수 없습니다: {scope!r}")

    af_raw = raw.get("agreed_formula")
    agreed_formula = None
    if af_raw:
        if not isinstance(af_raw, dict):
            raise LaborError("연차: agreed_formula 는 사전이어야 합니다")
        agreed_formula = AgreedFormula(
            multiplier=_num(af_raw.get("multiplier"), "agreed_formula.multiplier", ONE),
            wage_basis=af_raw.get("wage_basis") or "agreed",
            monthly_divisor=_num(af_raw.get("monthly_divisor"), "agreed_formula.monthly_divisor"),
            daily_hours=_num(af_raw.get("daily_hours"), "agreed_formula.daily_hours"),
        )
        if agreed_formula.wage_basis not in ("agreed", "statutory"):
            raise LaborError(f"연차: agreed_formula.wage_basis 는 agreed 또는 statutory 여야 합니다: {agreed_formula.wage_basis!r}")
    wages = []
    for i, w in enumerate(raw.get("agreed_ordinary_wage") or [], 1):
        if not isinstance(w, dict) or "from" not in w:
            raise LaborError(f"연차: agreed_ordinary_wage[{i}] 에 from 이 없습니다")
        aw = AgreedWage(_date(w["from"], f"agreed_ordinary_wage[{i}].from"),
                        _num(w.get("monthly"), f"agreed_ordinary_wage[{i}].monthly"),
                        _num(w.get("daily"), f"agreed_ordinary_wage[{i}].daily"))
        if (aw.monthly is None) == (aw.daily is None):
            raise LaborError(f"연차: agreed_ordinary_wage[{i}] 에는 monthly 와 daily 중 하나만 적습니다")
        wages.append(aw)
    wages.sort(key=lambda w: w.start)
    if wages and any(w.monthly is not None for w in wages):
        if agreed_formula is None or agreed_formula.monthly_divisor is None:
            raise LaborError("연차: 약정 통상임금을 월액으로 적었으면 agreed_formula.monthly_divisor(예: 209, 183)가 필요합니다")
    if agreed_formula is not None and agreed_formula.wage_basis == "agreed" and not wages:
        raise LaborError("연차: agreed_formula.wage_basis 가 agreed 이면 agreed_ordinary_wage 가 필요합니다")

    periods = [_load_period(p, f"periods[{i}]") for i, p in enumerate(raw.get("periods") or [], 1)]
    hbp = raw.get("hire_basis_periods")
    hire_basis = None if hbp is None else [_load_period(p, f"hire_basis_periods[{i}]") for i, p in enumerate(hbp, 1)]

    sbp = []
    for s, e in worker.get("small_business_periods") or []:
        sbp.append((_date(s, "worker.small_business_periods"), _date(e, "worker.small_business_periods")))

    pay_day = raw.get("pay_day")
    if pay_day in (None, ""):
        pay_day = worker.get("pay_day")
    if pay_day not in (None, ""):
        try:
            pay_day = int(pay_day)
        except (ValueError, TypeError):
            raise LaborError(f"연차: pay_day 는 1~31 정수여야 합니다: {pay_day!r}") from None
        if not 1 <= pay_day <= 31:
            raise LaborError(f"연차: pay_day 는 1~31 정수여야 합니다: {pay_day!r}")
    return LeaveInput(
        hire_date=hire,
        last_working_day=last,
        calc_until=_date(raw.get("calc_until"), "calc_until"),
        period_basis=basis,
        fiscal_year_start=fy_start,
        fy_clause_scope=scope,
        recalc_clause=bool(_bool(raw.get("recalc_clause"), "recalc_clause", False)),
        assume_full_attendance=bool(_bool(raw.get("assume_full_attendance"), "assume_full_attendance", False)),
        small_business=bool(_bool(raw.get("small_business"), "small_business", False)),
        small_business_periods=sbp,
        weekly_hours=_num(raw.get("weekly_hours"), "weekly_hours"),
        full_time_weekly_hours=_num(raw.get("full_time_weekly_hours"), "full_time_weekly_hours", Decimal(40)),
        daily_hours=_num(raw.get("daily_hours"), "daily_hours", Decimal(8)),
        pay_day=None if pay_day in (None, "") else pay_day,
        agreed_formula=agreed_formula,
        agreed_ordinary_wage=wages,
        periods=periods,
        hire_basis_periods=hire_basis,
    )


# ================================================================ 날짜 헬퍼
def period_span(start: date, months: int, mode: str = "civil_code") -> tuple[date, date]:
    """start(초일 산입)부터 months 개월 기간의 (만료일, 다음 날).

    민법 제160조 제2항 — 최후의 월에서 기산일에 해당한 날의 전일로 만료.
    제3항 — 최종의 월에 해당일이 없으면 그 월의 말일로 만료(mode='civil_code').
    mode='clamp' 이면 그 달 말일을 해당일로 보아 전날 만료.
    """
    if months <= 0:
        raise LaborError("연차: 기간 개월 수는 1 이상이어야 합니다")
    target = add_months(start, months)
    if target.day != start.day and mode == "civil_code":
        end = target
    else:
        end = target - timedelta(days=1)
    return end, end + timedelta(days=1)


def promotion_first_notice_window(use_end: date, kind: str = "art61_1", window: str = "after") -> tuple[date, date]:
    """제61조 1차 촉구의 적법 창 (첫날, 끝날). kind: art61_1(6개월 전) | art61_2(1년 미만자, 3개월 전)."""
    months = 6 if kind == "art61_1" else 3
    base = add_months(use_end + timedelta(days=1), -months)
    if window == "after":
        return base, base + timedelta(days=9)
    if window == "both":
        return base - timedelta(days=10), base + timedelta(days=10)
    raise LaborError(f"연차: 사용촉진 창 {window!r} 을 알 수 없습니다(after | both)")


def _fmt(d: date | None) -> str:
    return "" if d is None else f"{d.year}. {d.month}. {d.day}."


def _first_payday_on_or_after(d: date, pay_day: int) -> date:
    c = date(d.year, d.month, min(pay_day, calendar.monthrange(d.year, d.month)[1]))
    if c < d:
        n = add_months(date(d.year, d.month, 1), 1)
        c = date(n.year, n.month, min(pay_day, calendar.monthrange(n.year, n.month)[1]))
    return c


def _settle(x: Decimal) -> Decimal:
    """Decimal 나눗셈의 순환소수 오차 보정(소수 10자리 반올림). 끝수처리 직전에만 쓴다."""
    return x.quantize(Decimal("1e-10"), rounding=ROUND_HALF_UP)


# ================================================================ 계산 내부
@dataclass
class _Ctx:
    o: dict
    trace: list
    warnings: list
    T: date | None
    limit: date | None

    def reached(self, d: date) -> bool:
        if self.T is not None:
            return d <= self.T
        if self.limit is not None:
            return d <= self.limit
        return True

    def warn(self, msg: str) -> None:
        if msg not in self.warnings:
            self.warnings.append(msg)


@dataclass
class _Grant:
    period_no: int
    period_start: date | None
    period_end: date | None
    kind: str
    accrual_date: date | None
    accrued: bool
    source: str = ""
    rate: Decimal | None = None
    days: Decimal = ZERO
    hours: Decimal | None = None
    daily_hours: Decimal = Decimal(8)
    used_days: Decimal = ZERO
    used_hours: Decimal | None = None
    use_end: date | None = None
    promotion: PromotionInput | None = None
    promotion_kind: str | None = None
    agreed_days: Decimal | None = None
    paid: Decimal = ZERO
    paid_pool: int | None = None       # 최초 1년 월 휴가 기지급액을 나눌 기간 번호
    merged: bool = False
    notes: list = field(default_factory=list)


def _read_options(opts: dict | None) -> dict:
    opts = opts or {}
    out = {}
    for key, spec in OPTIONS.items():
        v = opts.get(key, spec.default)
        if spec.choices and v not in spec.choices:
            raise LaborError(f"옵션 {key} 의 값 {v!r} 은 허용되지 않습니다. 가능: {', '.join(map(str, spec.choices))}")
        out[key] = v
    try:
        out["al_old_art60_3_cutoff"] = parse_date(out["al_old_art60_3_cutoff"])
    except (ValueError, TypeError):
        raise LaborError(f"옵션 al_old_art60_3_cutoff 날짜 형식이 올바르지 않습니다: {out['al_old_art60_3_cutoff']!r}") from None
    return out


def _generate(inp: LeaveInput, entries: list, ctx: _Ctx, spans, label: str):
    """[(k, start, end, accrual, entry|None)] — spans(k) 가 k번째 산정기간 (start, end, accrual)."""
    starts = [p.start for p in entries]
    sparse = any(s is not None for s in starts)
    if sparse and not all(s is not None for s in starts):
        raise LaborError(f"연차: {label} 의 start 는 모두 적거나 모두 비워야 합니다")
    limit = ctx.T if ctx.T is not None else ctx.limit
    out = []
    if sparse:
        wanted = {p.start: p for p in entries}
        if len(wanted) != len(entries):
            raise LaborError(f"연차: {label} 에 같은 start 가 두 번 있습니다")
        last = max(wanted)
        if limit is not None and last > limit:
            raise LaborError(f"연차: {label} 의 산정기간 시작일 {last} 이 마지막 근로일(기준일) {limit} 뒤입니다")
        k = 0
        while True:
            s, e, a = spans(k)
            if s > last:
                break
            if s in wanted:
                out.append((k, s, e, a, wanted.pop(s)))
            k += 1
        if wanted:
            bad = ", ".join(str(d) for d in sorted(wanted))
            raise LaborError(f"연차: {label} 의 시작일 {bad} 이 {inp.period_basis} 기준 산정기간 시작일과 맞지 않습니다")
        ctx.trace.append(Trace("AL-03", f"{label}: 입력한 산정기간만 계산", ", ".join(_fmt(x[1]) for x in out)))
        return out
    k = 0
    while True:
        s, e, a = spans(k)
        has_entry = k < len(entries)
        if has_entry and limit is not None and s > limit:
            raise LaborError(f"연차: {label}[{k + 1}] 산정기간 시작일 {s} 이 마지막 근로일(기준일) {limit} 뒤입니다")
        if not has_entry and (limit is None or s > limit):
            break
        out.append((k, s, e, a, entries[k] if has_entry else None))
        k += 1
    return out


def _hire_spans(inp: LeaveInput, mode: str):
    H = inp.hire_date

    def spans(k: int):
        s = H if k == 0 else period_span(H, 12 * k, mode)[1]
        e, a = period_span(H, 12 * (k + 1), mode)
        return s, e, a
    return spans


def _fy_spans(inp: LeaveInput):
    mm, dd = inp.fiscal_year_start

    def next_start(d: date) -> date:
        c = date(d.year, mm, dd)
        return c if c > d else date(d.year + 1, mm, dd)

    cache = [inp.hire_date]

    def spans(k: int):
        while len(cache) <= k + 1:
            cache.append(next_start(cache[-1]))
        s, a = cache[k], cache[k + 1]
        return s, a - timedelta(days=1), a
    return spans


def _is_small(p: LeavePeriodInput | None, inp: LeaveInput, deps: dict, d: date) -> bool:
    """산정기간 입력 small_business 가 있으면 그 값. 없으면 leave.small_business·worker 기간·deps 중 하나라도 참이면 소규모.

    조립 모듈은 worker.small_business_periods 로 만든 deps 를 늘 넘기므로(기간이 없으면 항상 거짓),
    deps 가 절 플래그를 덮으면 leave.small_business: true 가 계산에서 사라진다(dismissal 과 같은 방식으로 합친다).
    """
    if p is not None and p.small_business is not None:
        return p.small_business
    if inp.small_business:
        return True
    if inp.small_business_periods and is_within(d, inp.small_business_periods):
        return True
    fn = deps.get("small_business")
    return bool(fn is not None and fn(d))


def _exclusion_reason(p, inp, deps, d, wh) -> str | None:
    if _is_small(p, inp, deps, d):
        return "상시 4명 이하 사업장 — 제60조 미적용(제11조 제1항, 시행령 [별표 1])"
    if wh is not None and wh < 15:
        return "4주 평균 1주 소정근로시간 15시간 미만 — 제60조 미적용(제18조 제3항)"
    return None


def _day_fraction(days: Decimal, daily_hours: Decimal, o: dict) -> Decimal:
    if days == days.to_integral_value():
        return days
    mode = o["al_day_fraction"]
    if mode == "ceil_day":
        return days.to_integral_value(rounding=ROUND_CEILING)
    if mode == "floor_day":
        return days.to_integral_value(rounding=ROUND_DOWN)
    if mode == "to_hours":
        return (days * daily_hours).to_integral_value(rounding=ROUND_CEILING) / daily_hours
    return days


def _round_hours(hours: Decimal, o: dict) -> Decimal:
    if o["al_pt_hour_rounding"] == "ceil_total":
        return _settle(hours).to_integral_value(rounding=ROUND_CEILING)
    return hours


def _attendance(p: LeavePeriodInput, o: dict, label: str, ctx: _Ctx):
    """(S, X, W). 출근 자료가 없으면 None."""
    if not p.has_attendance:
        return None
    S = p.scheduled_days
    X = sum(p.excluded.values(), ZERO)
    if p.suspension_days:
        ctx.warn(f"{label}: 정당한 정직·직위해제 {p.suspension_days}일 처리(al_lawful_suspension={o['al_lawful_suspension']})는 "
                 "대법원 원문으로 확인되지 않은 미해결 쟁점입니다")
        if o["al_lawful_suspension"] == "excluded":
            X += p.suspension_days
    W = p.attended_days + sum(p.deemed.values(), ZERO)
    if X > S:
        raise LaborError(f"연차: {label} 소정근로일수 제외 일수 {X} 가 연간 소정근로일수 {S} 보다 많습니다")
    if W > S - X:
        raise LaborError(f"연차: {label} 출근일수+출근 간주 일수 {W} 가 실질 소정근로일수 {S - X} 보다 많습니다")
    return S, X, W


def _monthly_values(p: LeavePeriodInput | None, count: int, label: str, *, assume_full: bool,
                    att, ctx: _Ctx, required: bool) -> list | None:
    if p is not None and p.monthly_perfect is not None:
        vals = p.monthly_perfect
        if len(vals) < count:
            raise LaborError(f"연차: {label} monthly_perfect 는 {count}개월 이상 적어야 합니다(적은 수 {len(vals)})")
        return vals[:count]
    if att is not None and att[1] == 0 and att[2] >= att[0]:
        ctx.trace.append(Trace("AL-06", f"{label}: 월별 개근 입력 없음", "출근율 100% — 모든 달 개근으로 봄"))
        return [ONE] * count
    if assume_full:
        ctx.warn(f"{label}: 월별 개근 자료가 없어 모든 달 개근으로 가정했습니다(assume_full_attendance)")
        return [ONE] * count
    if required:
        raise LaborError(f"연차: {label} 월별 개근 여부(monthly_perfect, {count}개월)가 없습니다")
    return None


def _art61_kind_monthly(accrual: date) -> str | None:
    return "art61_2" if accrual >= DATE_2020_AMEND else None


def _apply_hours(g: _Grant, wh, ft: Decimal, reduced: ReducedHoursInput | None, o: dict, ctx: _Ctx,
                 p: LeavePeriodInput | None, label: str) -> None:
    """단시간(AL-18)·혼재(AL-19)이면 시간 단위로 바꾼다."""
    if g.days == 0:
        return
    if reduced is not None and g.kind == "main":
        if o["al_mixed_reduced_hours"] == "moel_2013_prorate":
            m = reduced.months
            hours = g.days * 8 * ((12 - m) * ft + reduced.weekly_hours * m) / (12 * ft)
            g.hours = _round_hours(hours, o)
            g.notes.append(f"통상·단축근로 혼재 비례(단축 {m}개월, 주 {reduced.weekly_hours}시간): "
                           f"{g.days}일 × 8시간 × ((12−{m}) × {ft} + {reduced.weekly_hours} × {m}) ÷ (12 × {ft})")
            ctx.warn(f"{label}: 통상·단축근로 혼재 월 단위 비례(AL-19)는 근로개선정책과-4216 재대조 전이고 "
                     "2024. 10. 22. 제60조 제6항 제4·5호 신설 후 유지 여부가 불명확합니다")
        else:
            ctx.warn(f"{label}: reduced_hours 입력이 있으나 al_mixed_reduced_hours=none 이어서 비례하지 않았습니다(AL-19 불명확)")
    if g.hours is None and wh is not None and wh < ft:
        hours = g.days * wh * 8 / ft
        g.hours = _round_hours(hours, o)
        g.notes.append(f"단시간 비례: {g.days}일 × {wh}시간 ÷ {ft}시간 × 8시간 = {_settle(hours).normalize()}시간"
                       + (" → 1시간 미만 올림" if g.hours != hours else ""))
    if g.hours is not None:
        if g.kind == "monthly":
            g.used_hours = g.used_days * g.daily_hours
        elif p is not None and p.used_hours is not None:
            g.used_hours = p.used_hours
        else:
            g.used_hours = g.used_days * g.daily_hours


def _statutory_main_days(k: int, ps: date, p: LeavePeriodInput, att, o: dict, ctx: _Ctx, label: str,
                         below80_years: list) -> tuple[Decimal, str, Decimal | None, list]:
    """발생일(A_k) 휴가의 법정 일수. (일수, 발생 사유, 출근율, 비고)."""
    notes = []
    S, X, W = att
    Sp = S - X
    n = k + 1
    base = 15 if n < 3 else min(25, 15 + (n - 1) // 2)
    if Sp <= 0:
        return ZERO, "소정근로일수 전부 제외 — 미발생(2015다66052)", None, notes
    rate = W / Sp
    if rate >= RATE_80:
        days = Decimal(base)
        source = "15일" if base == 15 else f"15일+가산 {base - 15}일"
        if base > 15 and below80_years:
            ctx.warn(f"{label}: 앞선 80% 미만 연도({', '.join(below80_years)})를 계속근로연수에 넣어 가산일수를 셌습니다 — "
                     "80% 미만 연도의 계속근로연수 산입 여부는 미해결 쟁점(AL-05)")
        if base == 25:
            notes.append("가산휴가 포함 25일 한도(제60조 제4항)")
        if X > 0:
            mode = o["al_proration_mode"]
            prorate = mode != "supreme_2019" or W < RATE_80 * S
            if prorate:
                raw = days * Sp / S
                notes.append(f"비례({mode}): {days}일 × 실질 소정근로일수 {Sp} ÷ 연간 소정근로일수 {S}")
                days = raw
                source += " 비례"
                if o["al_below80_interplay"] == "max_with_art60_2" and W < RATE_80 * S and ps >= DATE_ART60_2B:
                    if p.monthly_perfect is None or len(p.monthly_perfect) < 12:
                        ctx.warn(f"{label}: al_below80_interplay=max_with_art60_2 인데 monthly_perfect(12개월)가 없어 비례 일수만 썼습니다")
                    else:
                        months = sum(p.monthly_perfect[:12], ZERO)
                        if months > days:
                            notes.append(f"개근월수 {months} > 비례 일수 {_settle(days).normalize()} → 제2항(b) 일수 사용")
                            days = months
                            source = "제2항(b) 80% 미만 월 개근(비례보다 많음)"
                ctx.warn(f"{label}: 제외기간 비례 산정(AL-10, {mode}) — 현행 제2항(b)와의 관계는 미해결(al_below80_interplay)")
            else:
                notes.append(f"제외기간 있으나 출근일수 {W} ≥ 연간 소정근로일수 {S} × 0.8 → 비례 안 함(2015다66052)")
        return days, source, rate, notes
    # 80% 미만
    below80_years.append(_fmt(ps))
    if k == 0:
        if o["al_first_year_below80"] == "add_art60_2b":
            vals = p.monthly_perfect
            if vals is None or len(vals) < 12:
                raise LaborError(f"연차: {label} 최초 1년 80% 미만 — al_first_year_below80=add_art60_2b 이면 monthly_perfect 12개월이 필요합니다")
            ctx.warn(f"{label}: 최초 1년 80% 미만자에게 제2항(a)와 별도로 (b)를 부여했습니다(중복 해석, 근거 원문 없음)")
            return sum(vals[:12], ZERO), "제2항(b) 80% 미만 월 개근(최초 1년 중복 해석)", rate, notes
        ctx.warn(f"{label}: 최초 1년 출근율 80% 미만 — 제2항(a) 월 개근 휴가만 두고 (b)는 중복 부여하지 않았습니다(AL-06 미해결)")
        return ZERO, "최초 1년 출근율 80% 미만 — 제1항 미발생", rate, notes
    if ps < DATE_ART60_2B:
        notes.append("산정기간 시작이 2012. 8. 2. 전 — 80% 미만자 제2항(b) 미적용(법률 제11270호 부칙 제4조)")
        return ZERO, "출근율 80% 미만 — 미발생", rate, notes
    vals = p.monthly_perfect
    if vals is None or len(vals) < 12:
        raise LaborError(f"연차: {label} 출근율 80% 미만 — 제2항(b) 계산에 monthly_perfect(12개월)가 필요합니다")
    days = sum(vals[:12], ZERO)
    source = "제2항(b) 80% 미만 월 개근"
    if not o["al_bonus_requires_80pct"] and base > 15:
        days += base - 15
        source += f"+가산 {base - 15}일"
        ctx.warn(f"{label}: 80% 미만 연도에 가산휴가를 더했습니다(al_bonus_requires_80pct=false)")
    return days, source, rate, notes


def _old_art60_3_applies(H: date, o: dict) -> bool:
    cutoff = o["al_old_art60_3_cutoff"]
    return H <= cutoff if o["al_old_art60_3_compare"] == "le" else H < cutoff


def _hire_basis_grants(inp: LeaveInput, entries: list, ctx: _Ctx, deps: dict, *, assume_full: bool,
                       label_prefix: str = "") -> list[_Grant]:
    o = ctx.o
    mode = o["al_missing_anniversary"]
    H = inp.hire_date
    ft = inp.full_time_weekly_hours
    grants: list[_Grant] = []
    below80_years: list[str] = []
    old3 = _old_art60_3_applies(H, o)
    items = _generate(inp, entries, ctx, _hire_spans(inp, mode), f"{label_prefix}periods")

    for k, ps, pe, A0, p in items:
        no = k + 1
        label = f"{label_prefix}제{no} 산정기간({_fmt(ps)}~{_fmt(pe)})"
        wh = (p.weekly_hours if p is not None and p.weekly_hours is not None else inp.weekly_hours)
        dh = (p.daily_hours if p is not None and p.daily_hours is not None else inp.daily_hours)
        A = A0
        if p is not None and p.accrual_date is not None:
            if o["al_accrual_rule_override"] == "per_input":
                A = p.accrual_date
            else:
                ctx.warn(f"{label}: accrual_date 입력이 있으나 al_accrual_rule_override=none 이어서 원칙 발생일 {_fmt(A0)} 을 썼습니다")
        att = _attendance(p, o, label, ctx) if p is not None else None
        if p is not None:
            _check_deemed_dates(p, ps, pe, label, ctx)

        # ---- 최초 1년 제2항(a)
        monthly_grants: list[_Grant] = []
        if k == 0:
            reached_any = ctx.reached(period_span(H, 1, mode)[1])
            reason = _exclusion_reason(p, inp, deps, ps, wh)
            if reason and reached_any:
                grants.append(_Grant(no, ps, pe, "monthly", None, False, source=reason, daily_hours=dh,
                                     notes=["최초 1년 월 개근 휴가 미발생"]))
            elif reached_any:
                vals = _monthly_values(p, 11, label, assume_full=assume_full, att=att, ctx=ctx,
                                       required=p is None or p.granted_days is None)
                if vals is None:
                    ctx.warn(f"{label}: 월별 개근 입력이 없어 최초 1년 제2항(a) 월 휴가를 계산하지 않았습니다")
                else:
                    groups: dict = {}
                    for j in range(11):
                        aj = period_span(H, j + 1, mode)[1]
                        if not ctx.reached(aj) or vals[j] == 0:
                            continue
                        if _is_small(p, inp, deps, aj):
                            continue
                        use_end = period_span(aj, 12, mode)[0] if aj < DATE_2020_AMEND else pe
                        key = use_end
                        if ctx.T is not None and ctx.T < use_end:
                            key = ctx.T
                        groups.setdefault((key, aj >= DATE_2020_AMEND), []).append((aj, vals[j], use_end))
                    for (key, new_law), members in sorted(groups.items(), key=lambda kv: kv[1][0][0]):
                        first, last = members[0][0], members[-1][0]
                        days = sum((m[1] for m in members), ZERO)
                        g = _Grant(no, ps, pe, "monthly", first, True, daily_hours=dh, days=days,
                                   use_end=max(m[2] for m in members))
                        g.source = f"월 개근(제2항, 1년 미만) {len(members)}개월"
                        g.notes.append(f"발생일 {_fmt(first)}" + ("" if first == last else f"~{_fmt(last)}"))
                        g.notes.append("사용기간: 최초 1년 근로가 끝날 때까지(2020. 3. 31. 이후 발생분)" if new_law
                                       else "사용기간: 발생일부터 1년(2020. 3. 31. 전 발생분, 법률 제17185호 부칙 제2조)")
                        if any(m[1] != ONE for m in members):
                            g.notes.append("월 실질 소정근로일 비례 포함(임금근로시간정책과-389)")
                        g.promotion = p.promotion_monthly if p is not None else None
                        g.promotion_kind = "art61_2" if new_law else None
                        g.paid_pool = no
                        monthly_grants.append(g)
                    # 사용일수 FIFO
                    remaining = p.used_monthly_days if p is not None else ZERO
                    for g in monthly_grants:
                        take = min(remaining, g.days)
                        g.used_days = take
                        remaining -= take
                    if remaining > 0:
                        ctx.warn(f"{label}: 최초 1년 월 휴가 사용일수가 발생일수보다 {remaining}일 많습니다 — 초과분은 무시")
                    for g in monthly_grants:
                        _apply_hours(g, wh, ft, None, o, ctx, p, label)
                    grants.extend(monthly_grants)
        monthly_total = sum((g.days for g in monthly_grants), ZERO)

        # ---- 발생일 휴가(제1항·제4항·제2항 b)
        g = _Grant(no, ps, pe, "main", A, ctx.reached(A), daily_hours=dh)
        if not g.accrued:
            _mark_not_reached(g, A, ctx, cite=True)
            grants.append(g)
            continue
        if A != A0:
            g.notes.append(f"발생시기 특약에 따른 발생일 {_fmt(A)} (원칙 {_fmt(A0)}, 대법원 2024다206043)")
            ctx.warn(f"{label}: 발생시기 특약(M1)을 적용했습니다 — 취업규칙·노동관행 등으로 그 정함이 인정되는지 사람이 확인해야 합니다")
        reason = _exclusion_reason(p, inp, deps, A, wh)
        if reason:
            g.source = reason
            grants.append(g)
            continue
        if p is None or (att is None and p.granted_days is None):
            if not assume_full:
                raise LaborError(f"연차: {label} 연간 소정근로일수·출근일수(scheduled_days, attended_days) "
                                 "또는 발생일수(granted_days)가 없습니다")
            ctx.warn(f"{label}: 출근 자료가 없어 결근 없음(출근율 100%)으로 가정했습니다(assume_full_attendance)")
            att = (ONE, ZERO, ONE)
            p = p or LeavePeriodInput()
        stat_days = None
        if att is not None:
            stat_days, source, rate, notes = _statutory_main_days(k, ps, p, att, o, ctx, label, below80_years)
            g.rate = rate
            g.notes.extend(notes)
            if k == 0 and old3 and stat_days > 0:
                deduct = monthly_total if o["al_old_art60_3_deduct"] == "granted" else min(p.used_monthly_days, monthly_total)
                stat_days = max(ZERO, stat_days - deduct)
                source += f" − 구 제3항 공제 {deduct}일"
                g.notes.append(f"구 제60조 제3항(입사 {_fmt(H)}, 기준 {o['al_old_art60_3_compare']} {_fmt(o['al_old_art60_3_cutoff'])}): "
                               f"15일에서 최초 1년 제2항 휴가 {deduct}일({o['al_old_art60_3_deduct']}) 공제 — 부산지방법원 2021가단304232(하급심)")
                if o["al_old_art60_3_deduct"] == "used":
                    for mg in monthly_grants:
                        mg.merged = True
            stat_days = _day_fraction(stat_days, dh, o)
            g.source = source
        days = stat_days
        if p.granted_days is not None:
            if stat_days is None:
                days = p.granted_days
                g.source = "사람이 확정한 발생일수(granted_days)"
            elif p.granted_days != stat_days:
                days = max(stat_days, p.granted_days)
                ctx.warn(f"{label}: 입력 발생일수 {p.granted_days}일과 법정 산정 {_settle(stat_days).normalize()}일이 달라 큰 값 {_settle(days).normalize()}일을 썼습니다")
        g.days = days
        g.used_days = p.used_days
        g.use_end = period_span(A, 12, mode)[0]
        g.promotion = p.promotion
        g.promotion_kind = "art61_1"
        g.agreed_days = p.agreed_days
        g.paid = p.paid_amount
        if p.note:
            g.notes.append(p.note)
        _apply_hours(g, wh, ft, p.reduced_hours, o, ctx, p, label)
        grants.append(g)
    return grants


def _mark_not_reached(g: _Grant, A: date, ctx: _Ctx, *, cite: bool) -> None:
    """발생일에 이르지 못한 행의 발생 사유. 퇴직(T)이면 근로관계 종료, 재직 중이면 기준일(calc_until) 뒤."""
    if ctx.T is not None:
        g.source = "발생일 전 근로관계 종료 — 미발생"
        if cite:
            g.notes.append(f"발생일 {_fmt(A)} 에 근로관계 없음(2016다48297, 2021다227100)")
        return
    g.source = "기준일(calc_until) 뒤 발생 예정 — 계산 대상 아님"
    g.notes.append(f"발생일 {_fmt(A)} 이 기준일 {_fmt(ctx.limit)} 뒤(재직 중)")


def _check_deemed_dates(p: LeavePeriodInput, ps: date, pe: date, label: str, ctx: _Ctx) -> None:
    if p.deemed.get("parental_leave") and pe < DATE_ART60_3_REPEAL:
        ctx.warn(f"{label}: 법정 육아휴직 출근 간주는 2018. 5. 29. 이후 최초 신청분부터입니다 — 그 전 신청분은 excluded.old_parental_leave 로")
    for key in ("childcare_reduced_hours", "pregnancy_reduced_hours"):
        if p.deemed.get(key):
            ctx.warn(f"{label}: {DEEMED_REASONS[key]} — 단축된 '근로시간'을 출근 일수로 환산하는 방법은 확인되지 않았습니다")
            if pe < DATE_2024_AMEND:
                ctx.warn(f"{label}: 근로시간 단축 출근 간주(제60조 제6항 제4·5호)는 2024. 10. 22. 이후 시작분부터입니다")
    if p.deemed.get("void_suspension"):
        ctx.trace.append(Trace("AL-09", f"{label}: 무효 출근정지 출근 간주", str(p.deemed["void_suspension"]),
                               "대전고등법원 2019나41(확정) — 하급심"))
    if p.deemed.get("other") or p.excluded.get("other"):
        ctx.warn(f"{label}: 기타 사유(other) 출근 간주·제외 일수가 있습니다 — 근거 확인 필요")


def _fiscal_grants(inp: LeaveInput, ctx: _Ctx, deps: dict) -> list[_Grant]:
    o = ctx.o
    mode = o["al_missing_anniversary"]
    ft = inp.full_time_weekly_hours
    grants = []
    items = _generate(inp, inp.periods, ctx, _fy_spans(inp), "periods")
    ctx.warn("회계연도 기준: 일률 기준일의 적법 요건(대법원 99다10806 — 기준일 이전 1년 이내 채용자에게 잔여기간 출근 간주·"
             "1년 계속근로 취급)과 최초 1년 제2항 월 휴가가 granted_days 에 반영됐는지 확인해야 합니다(M5)")
    for k, ps, pe, A, p in items:
        no = k + 1
        label = f"제{no} 회계연도 산정기간({_fmt(ps)}~{_fmt(pe)})"
        g = _Grant(no, ps, pe, "main", A, ctx.reached(A))
        dh = p.daily_hours if p is not None and p.daily_hours is not None else inp.daily_hours
        wh = p.weekly_hours if p is not None and p.weekly_hours is not None else inp.weekly_hours
        g.daily_hours = dh
        if not g.accrued:
            _mark_not_reached(g, A, ctx, cite=False)
            grants.append(g)
            continue
        reason = _exclusion_reason(p, inp, deps, A, wh)
        if reason:
            g.source = reason
            grants.append(g)
            continue
        if p is None or p.granted_days is None:
            raise LaborError(f"연차: {label} 회계연도 기준이면 사업장이 부여한 발생일수(granted_days)가 필요합니다")
        att = _attendance(p, o, label, ctx)
        if att is not None:
            _check_deemed_dates(p, ps, pe, label, ctx)
            S, X, W = att
            if S - X > 0:
                g.rate = W / (S - X)
                if g.rate < RATE_80:
                    ctx.warn(f"{label}: 출근율 {_settle(g.rate).normalize()} 로 80% 미만인데 granted_days {p.granted_days}일이 입력되었습니다")
        g.days = p.granted_days
        g.source = "회계연도 기준 부여일수(granted_days)"
        g.used_days = p.used_days
        g.use_end = period_span(A, 12, mode)[0]
        g.promotion = p.promotion
        g.promotion_kind = "art61_1"
        g.agreed_days = p.agreed_days
        g.paid = p.paid_amount
        if p.note:
            g.notes.append(p.note)
        _apply_hours(g, wh, ft, p.reduced_hours, o, ctx, p, label)
        grants.append(g)
    return grants


def _fy_settlement(inp: LeaveInput, fy_grants: list, ctx: _Ctx, deps: dict, result_meta: dict) -> list[_Grant]:
    scope = inp.fy_clause_scope
    if scope == "accrual_period":
        ctx.trace.append(Trace("AL-17", "회계연도 조항 해석 범위", "accrual_period",
                               "계속근로기간 산정까지 회계연도 기준 — 입사일 기준 재산정 없음"
                               "(의정부지방법원 2024나226635, 대법원 2026다202306 상고기각 확정)"))
        return []
    ctx.warn("회계연도 퇴직 정산(grant_date_only)은 근로기준과-5802·임금근로시간정책과-1960(재대조 전 확인불가)에 따른 것입니다")
    if ctx.T is None:
        ctx.trace.append(Trace("AL-17", "회계연도 퇴직 정산", "재직 중 — 정산 없음"))
        return []
    sub = _Ctx(ctx.o, [], [], ctx.T, ctx.limit)
    entries = inp.hire_basis_periods or []
    assume = inp.assume_full_attendance or not entries
    if not entries:
        ctx.warn("입사일 기준 비교: hire_basis_periods 가 없어 결근 없음·모든 달 개근으로 가정했습니다(근로기준과-5802 사안 전제)")
    hire_grants = _hire_basis_grants(inp, entries, sub, deps, assume_full=assume, label_prefix="입사일 기준 비교 ")
    for w in sub.warnings:
        ctx.warn(w)
    ctx.trace.extend(sub.trace)
    n_hire = sum((g.days for g in hire_grants if g.accrued), ZERO)
    n_fy = sum((g.days for g in fy_grants if g.accrued), ZERO)
    result_meta["hire"] = n_hire
    result_meta["fy"] = n_fy
    ctx.trace.append(Trace("AL-17", "누적 발생일수 비교", f"입사일 기준 {n_hire}일 / 회계연도 기준 {n_fy}일"))
    diff = n_hire - n_fy
    if diff <= 0:
        msg = f"회계연도 기준 누적 {n_fy}일이 입사일 기준 {n_hire}일 이상 — 회계연도 기준 유지"
        ctx.trace.append(Trace("AL-17", "회계연도 퇴직 정산", "정산 없음", msg))
        if diff < 0 and inp.recalc_clause:
            ctx.warn(f"{msg}. 퇴직 시 입사일 기준 재산정 단서가 있어 사용자가 {-diff}일 초과 부여를 주장할 여지가 있으나 "
                     "엔진은 청구액을 줄이지 않았습니다")
        return []
    g = _Grant(0, None, None, "settlement", None, True, daily_hours=inp.daily_hours, days=diff)
    g.source = "회계연도 기준 퇴직 정산(입사일 기준 미달분)"
    g.notes.append(f"입사일 기준 {n_hire}일 − 회계연도 기준 {n_fy}일 = {diff}일(근로기준과-5802)")
    return [g]


def _promotion_decision(g: _Grant, o: dict, ctx: _Ctx, label: str) -> tuple[bool, str]:
    pr = g.promotion
    computed = None
    note = ""
    if pr.first_notice is not None:
        lo, hi = promotion_first_notice_window(g.use_end, g.promotion_kind, o["al_promotion_window"])
        first_ok = lo <= pr.first_notice <= hi
        months = 2 if g.promotion_kind == "art61_1" else 1
        deadline = add_months(g.use_end + timedelta(days=1), -months) - timedelta(days=1)
        second_ok = pr.worker_designated_all or (pr.second_notice is not None and pr.second_notice <= deadline)
        computed = first_ok and second_ok
        note = (f"1차 촉구 {_fmt(pr.first_notice)} 창 [{_fmt(lo)}~{_fmt(hi)}] {'충족' if first_ok else '불충족'}, "
                f"2차 통보 기한 {_fmt(deadline)} {'충족' if second_ok else '불충족'}")
    if pr.lawful is not None:
        if computed is not None and computed != pr.lawful:
            ctx.warn(f"{label}: 사용촉진 적법 여부 입력({pr.lawful})과 날짜 검사 결과({computed})가 다릅니다 — {note}")
        return pr.lawful, note
    return bool(computed), note


def _agreed_wage_at(inp: LeaveInput, d: date) -> AgreedWage:
    found = None
    for w in inp.agreed_ordinary_wage:
        if w.start <= d:
            found = w
    if found is None:
        raise LaborError(f"연차: {_fmt(d)} 에 적용할 약정 통상임금(agreed_ordinary_wage)이 없습니다")
    return found


def _money(unit_price_num: Decimal, qty: Decimal, qty_den: Decimal, o: dict, price_den: Decimal = ONE) -> Decimal:
    """(unit_price_num / price_den) × (qty / qty_den) 를 끝수처리한다."""
    mode = o["al_final_rounding"]
    if o["al_round_after_full_product"]:
        raw = unit_price_num * qty / (price_den * qty_den)
    else:
        pre = "floor" if mode == "floor10" else mode
        unit = round_to(_settle(unit_price_num / (price_den * qty_den)), 0, pre)
        raw = unit * qty
    return round_to(_settle(raw), 0, mode)


def _finish(g: _Grant, inp: LeaveInput, ctx: _Ctx, deps: dict) -> LeaveRow:
    o = ctx.o
    T = ctx.T
    hours_mode = g.hours is not None
    label = (f"제{g.period_no} 산정기간({_fmt(g.period_start)}~{_fmt(g.period_end)}) {g.source}"
             if g.kind != "settlement" else g.source)
    notes = list(g.notes)
    base = dict(period_no=g.period_no, period_start=g.period_start, period_end=g.period_end, kind=g.kind,
                accrual_date=g.accrual_date, source=g.source, attendance_rate=g.rate,
                accrued_days=g.days, accrued_hours=g.hours, unit="시간" if hours_mode else "일")
    empty = dict(used=ZERO, extinguished=ZERO, unused=ZERO, use_end=g.use_end, wage_ref_date=None, daily_wage=None,
                 statutory_amount=ZERO, agreed_amount=None, amount=ZERO, paid_amount=g.paid, claim_amount=ZERO,
                 claim_arises=None, pay_due_date=None, settlement=False, prescription_date=None,
                 promotion_lawful=None, claim_pending=False)
    total_units = g.hours if hours_mode else g.days
    if not g.accrued or not total_units:
        return LeaveRow(**base, **empty, note="; ".join(notes))

    # 약정 휴가일수(agreed_days)가 있는 발생일 행은 약정 산식의 미사용일수를 법정 미사용과 따로 센다(M4).
    # 법정 일수를 다 써도 약정 초과분은 남으므로, 사용일수는 법정 일수로 자르기 전 값을 쓴다.
    agreed_days = (g.agreed_days if g.agreed_days is not None and g.kind == "main" and not hours_mode
                   and (inp.agreed_formula is not None or inp.agreed_ordinary_wage) else None)
    used = g.used_hours if hours_mode else g.used_days
    used_input = used
    if used > total_units:
        if agreed_days is not None and used <= agreed_days:
            notes.append(f"사용 {used}일이 법정 발생 {total_units}일보다 많아 법정 미사용 0 — 약정 {agreed_days}일 기준 미사용은 따로 계산")
        else:
            agreed_txt = f"(약정 {agreed_days}일)" if agreed_days is not None else ""
            ctx.warn(f"{label}: 사용 {used}{base['unit']}이 발생 {total_units}{base['unit']}{agreed_txt}보다 많습니다 — 미사용 0으로 처리")
        used = total_units
    unused = total_units - used

    settlement_kind = g.kind == "settlement"
    terminated = settlement_kind or (T is not None and g.use_end is not None and T < g.use_end)

    if g.merged and unused > 0:
        notes.append(f"미사용 {unused}{base['unit']}은 구 제3항에 따라 발생일 15일에 흡수 — 따로 보상하지 않음")
        unused = ZERO

    extinguished = ZERO
    promotion_lawful = None
    if g.promotion is not None and unused > 0:
        if g.promotion_kind is None:
            ctx.warn(f"{label}: 2020. 3. 31. 전 발생한 1년 미만자 제2항 휴가에는 사용촉진(제61조) 규정이 없어 촉진 입력을 무시했습니다")
        elif terminated:
            notes.append("사용기간 중 퇴직 — 제60조 제7항 본문 소멸이 아니어서 사용촉진 효과 없음(제61조)")
        else:
            promotion_lawful, pnote = _promotion_decision(g, o, ctx, label)
            if pnote:
                notes.append(pnote)
            if promotion_lawful:
                worked = g.promotion.worked_designated_days * (g.daily_hours if hours_mode else ONE)
                extinguished = max(ZERO, unused - worked)
                notes.append(f"사용촉진 적법 — {extinguished}{base['unit']} 보상의무 소멸(제61조)"
                             + (f", 지정일 근로 {worked}{base['unit']}은 존속(2019다279283)" if worked else ""))
            else:
                notes.append("사용촉진 요건 불충족 — 보상의무 존속(2019다279283)")
    unused -= extinguished
    agreed_left = ZERO
    if agreed_days is not None:
        agreed_left = max(ZERO, agreed_days - used_input - extinguished)
        notes.append(f"약정 {agreed_days}일 기준 미사용 {agreed_left}일(법정 미사용 {unused}일)")
    payable = unused > 0 or agreed_left > 0

    # ---- 청구권 발생일·지급기일·시효 기산점
    if terminated:
        claim_arises = T + timedelta(days=1)
        ref = T
        due = T + timedelta(days=14)
        settlement = True
        due_note = (f"퇴직: 근로관계 종료일 {_fmt(T)} 다음 날 지급사유 발생, 14일 기한 말일 {_fmt(due)} "
                    "(제36조; 지연손해금은 그 다음 날부터 — 2023나72464 등)")
        if settlement_kind or o["al_retire_prescription_start"] == "day_after_termination":
            presc_start = claim_arises
        else:
            presc_start = g.use_end + timedelta(days=1)
    else:
        claim_arises = g.use_end + timedelta(days=1)
        ref = g.use_end
        settlement = False
        if o["al_in_service_due"] == "first_regular_payday" and (inp.pay_day is not None or payable):
            if inp.pay_day is None:
                raise LaborError("연차: 재직 중 청구권 발생분의 첫 정기지급일을 정하려면 worker.pay_day(또는 leave.pay_day)가 필요합니다")
            due = _first_payday_on_or_after(claim_arises, inp.pay_day)
            due_note = (f"재직 중: 사용기간 말일 {_fmt(g.use_end)} 다음 날 청구권 발생, 첫 정기지급일 {_fmt(due)} "
                        "(대전고등법원 2019나41; 제37조 제1항 제2호 적용 여부는 지연손해금 모듈)")
        elif o["al_in_service_due"] == "claim_arises":
            due = claim_arises
            due_note = f"재직 중: 청구권 발생일 {_fmt(due)} 을 지급기일로 봄(임금근로시간정책과-1018)"
        else:
            due = claim_arises
            due_note = "미사용 없음"
        if T is not None:
            limit = T + timedelta(days=14)
            if o["al_due_when_retired"] == "all_settlement":
                due, settlement = limit, True
                due_note += f" → 퇴직자 일괄 금품청산 기한 {_fmt(limit)}(al_due_when_retired=all_settlement)"
            elif due > T:
                due, settlement = min(due, limit), True
                due_note += f" → 지급기일 전 퇴직, 기한 {_fmt(due)}"
        presc_start = claim_arises
    # AL-15 시효 완성일은 민법 제160조(기산일 + 3년 − 1일, 대응일 없으면 그 월 말일). 발생일 옵션
    # al_missing_anniversary(AL-03)는 시효 계산에 쓰지 않는다.
    prescription = period_span(presc_start, 36)[0]
    pending = (not terminated and T is None and ctx.limit is not None and claim_arises > ctx.limit)

    statutory = ZERO
    agreed_amt = None
    daily = None
    if payable:
        fn = deps.get("daily_ordinary_of")
        if fn is None:
            raise LaborError("연차: 수당 계산에 1일 통상임금(deps daily_ordinary_of)이 필요합니다")
        daily = dec(fn(ref))
        hourly = _hourly_rate(g, daily, ref, deps, ctx) if hours_mode else None
        if unused > 0:
            if hourly is not None:
                statutory = _money(hourly, unused, ONE, o)
            elif hours_mode:
                statutory = _money(daily, unused, g.daily_hours, o)
            else:
                statutory = _money(daily, unused, ONE, o)
        if inp.agreed_formula is not None or inp.agreed_ordinary_wage:
            agreed_amt = _agreed_amount(g, inp, daily, unused, used_input, extinguished, hours_mode, ref, o, ctx, label,
                                        hourly)

    notes.append(due_note)
    if pending:
        notes.append(f"청구권 발생일 {_fmt(claim_arises)} 이 기준일 {_fmt(ctx.limit)} 뒤 — 청구 합계에서 제외")
    return LeaveRow(**base, used=used, extinguished=extinguished, unused=unused, use_end=g.use_end,
                    wage_ref_date=ref if payable else None, daily_wage=daily, statutory_amount=statutory,
                    agreed_amount=agreed_amt, amount=statutory, paid_amount=g.paid, claim_amount=ZERO,
                    claim_arises=claim_arises, pay_due_date=due, settlement=settlement,
                    prescription_date=prescription, promotion_lawful=promotion_lawful, claim_pending=pending,
                    note="; ".join(notes))


def _hourly_rate(g: _Grant, daily: Decimal, ref: date, deps: dict, ctx: _Ctx) -> Decimal | None:
    """시간 단위 행의 통상시급(AL-18 '임금은 시간급 기준'). deps `hourly_of(d)` 가 있으면 그 값을 쓴다.

    없으면 None — 호출자가 1일 통상임금 ÷ leave.daily_hours 로 환산하고, 두 1일 소정근로시간이 같은지
    이 모듈이 확인할 수 없으므로 경고한다. 있으면 1일 통상임금 ÷ 통상시급과 leave.daily_hours 가 다를 때 경고한다
    (사용시간 used_days × daily_hours 환산은 leave.daily_hours 로 하므로).
    """
    fn = deps.get("hourly_of")
    dh = _settle(g.daily_hours).normalize()
    if fn is None:
        ctx.warn(f"시간 단위(단시간) 연차수당의 시급을 1일 통상임금 ÷ leave.daily_hours {dh}시간으로 환산했습니다 — "
                 "통상임금 절의 1일 소정근로시간과 다르면 금액이 틀리니 두 값이 같은지 확인하십시오(AL-18)")
        return None
    hourly = dec(fn(ref))
    if hourly > 0 and abs(daily / hourly - g.daily_hours) > Decimal("0.01"):
        ctx.warn(f"leave.daily_hours {dh}시간이 통상임금 절의 1일 소정근로시간({_settle(daily / hourly).normalize()}시간 = "
                 "1일 통상임금 ÷ 통상시급)과 다릅니다 — 시간 단위 연차수당은 통상시급으로 계산했으나, 사용시간"
                 "(used_days × daily_hours)·지정일 근로시간 환산은 leave.daily_hours 로 했으니 확인하십시오(AL-18)")
    return hourly


def _agreed_amount(g: _Grant, inp: LeaveInput, daily: Decimal, unused: Decimal, used: Decimal,
                   extinguished: Decimal, hours_mode: bool, ref: date, o: dict, ctx: _Ctx, label: str,
                   hourly: Decimal | None = None) -> Decimal:
    """약정 산식 금액. used 는 법정 일수로 자르기 전 사용일수(agreed_days 기준 미사용 = agreed_days − used − 촉진 소멸)."""
    af = inp.agreed_formula or AgreedFormula()
    qty, qty_den = unused, (g.daily_hours if hours_mode else ONE)
    if g.agreed_days is not None and g.kind == "main":
        if hours_mode:
            ctx.warn(f"{label}: 시간 단위 행에는 약정 휴가일수(agreed_days)를 쓰지 않았습니다")
        else:
            qty = max(ZERO, g.agreed_days - used - extinguished)
    mult = af.multiplier
    if af.wage_basis == "statutory":
        if hourly is not None:
            return _money(hourly * mult, qty, ONE, o)
        return _money(daily * mult, qty, qty_den, o)
    w = _agreed_wage_at(inp, ref)
    if w.daily is not None:
        return _money(w.daily * mult, qty, qty_den, o)
    hours = af.daily_hours if af.daily_hours is not None else g.daily_hours
    return _money(w.monthly * hours * mult, qty, qty_den, o, price_den=af.monthly_divisor)


def _global_warnings(inp: LeaveInput, ctx: _Ctx) -> None:
    entries = list(inp.periods) + list(inp.hire_basis_periods or [])
    if any(p.scheduled_days is not None for p in entries) and (inp.last_working_day is None
                                                                or inp.last_working_day >= DATE_PUBLIC_HOLIDAY_FIRST):
        ctx.warn("연간 소정근로일수에 제55조 제2항 공휴일 유급휴일(300명 이상 2020. 1. 1., 30명 이상 2021. 1. 1., "
                 "5명 이상 2022. 1. 1. 시행)을 근로의무 없는 날로 반영했는지 확인해야 합니다(M2)")
    if inp.hire_date < DATE_OLD_LAW_END:
        ctx.warn("입사일이 2011. 7. 1. 전 — 법률 제6974호 규모별 시행(2004. 7. 1.~2011. 7. 1.) 전 구법(월차, 10일/8일 연차) "
                 "기간이 있으면 이 엔진 범위 밖입니다")
    if any(p.deemed.get("unfair_dismissal") for p in entries):
        ctx.warn("해고기간 연차수당 상당 손해에서 사용일수를 추정하는 규칙(M6, 2020다230970·2021다245528)은 구현하지 않았습니다 — "
                 "used_days 를 사람이 정해 입력해야 합니다")


def calculate_leave(inp: LeaveInput, opts: dict, **deps) -> LeaveResult:
    o = _read_options(opts)
    trace: list[Trace] = []
    warnings: list[str] = []
    ctx = _Ctx(o, trace, warnings, inp.last_working_day, inp.calc_until)
    for key, spec in OPTIONS.items():
        v = o[key]
        shown = _fmt(v) if isinstance(v, date) else str(v)
        trace.append(Trace(spec.rule, f"옵션 {key}", shown, spec.choices.get(v, spec.description) if spec.choices else spec.description))
    trace.append(Trace("AL-20", "사용일수", "입력값 그대로", "소정근로일에 쉰 날만 사용일로 셈(2018다239110)"))

    meta: dict = {}
    if inp.period_basis == "hire_date":
        grants = _hire_basis_grants(inp, inp.periods, ctx, deps, assume_full=inp.assume_full_attendance)
    else:
        grants = _fiscal_grants(inp, ctx, deps)
        grants += _fy_settlement(inp, grants, ctx, deps, meta)
    _global_warnings(inp, ctx)
    if not grants:
        warnings.append("계산할 산정기간이 없습니다 — periods 를 적거나 last_working_day·calc_until 을 적어 자동 생성하십시오")

    rows = [_finish(g, inp, ctx, deps) for g in grants]
    live = [r for r in rows if not r.claim_pending]

    statutory_total = sum((r.statutory_amount for r in live), ZERO)
    agreed_total = None
    basis = "statutory"
    if inp.agreed_formula is not None or inp.agreed_ordinary_wage:
        agreed_total = sum(((r.agreed_amount if r.agreed_amount is not None else ZERO) for r in live), ZERO)
        if agreed_total > statutory_total:
            basis = "agreed"
        trace.append(Trace("M4", "약정·법정 산식 전체 비교", f"법정 {statutory_total} / 약정 {agreed_total} → {basis}",
                           "항목별 혼합 금지(대법원 2025다218891, 대전고등법원 2019나41)"))
    if basis == "agreed":
        for r in rows:
            r.amount = r.agreed_amount if r.agreed_amount is not None else ZERO

    # 기지급 공제 — 최초 1년 월 휴가분은 기간별 기지급액을 앞 행부터 나눈다
    pools = {}
    for g in grants:
        if g.paid_pool is not None and g.paid_pool not in pools:
            entry = _entry_for(inp, g.period_no, g.period_start)
            pools[g.paid_pool] = entry.paid_monthly_amount if entry is not None else ZERO
    for g, r in zip(grants, rows):
        if g.paid_pool is not None:
            take = min(pools[g.paid_pool], r.amount)
            r.paid_amount = take
            pools[g.paid_pool] -= take
        if r.paid_amount > r.amount:
            r.note = "; ".join(x for x in (r.note, f"기지급 {r.paid_amount}원이 산정액 {r.amount}원 이상 — 차액 0") if x)
        r.claim_amount = max(ZERO, r.amount - r.paid_amount)
    for no, left in pools.items():
        if left > 0:
            warnings.append(f"제{no} 산정기간 최초 1년 월 휴가 기지급액 중 {left}원이 산정액을 넘어 공제되지 않았습니다")

    claims = []
    total = ZERO
    for r in rows:
        if r.claim_pending or r.claim_amount <= 0:
            continue
        total += r.claim_amount
        label = (f"연차휴가수당 {_fmt(r.period_start)}~{_fmt(r.period_end)} 근로분({r.source})"
                 if r.kind != "settlement" else f"연차휴가수당 {r.source}")
        claims.append(Claim("연차휴가수당", label, r.claim_amount, r.pay_due_date, r.settlement,
                            note=f"청구권 발생일 {_fmt(r.claim_arises)}, 시효 완성일 {_fmt(r.prescription_date)}; " + r.note))
        warnings.append(f"{label}: 소멸시효 기산일 {_fmt(r.claim_arises if r.kind == 'settlement' else _presc_start(r, ctx))}, "
                        f"시효 완성일 {_fmt(r.prescription_date)} — 소 제기일과 대조 필요(AL-15)")
    return LeaveResult(rows=rows, total=total, claims=claims, trace=trace, warnings=warnings, basis=basis,
                       statutory_total=statutory_total, agreed_total=agreed_total,
                       hire_basis_days=meta.get("hire"), fiscal_basis_days=meta.get("fy"))


def _presc_start(r: LeaveRow, ctx: _Ctx) -> date:
    terminated = ctx.T is not None and r.use_end is not None and ctx.T < r.use_end
    if terminated and ctx.o["al_retire_prescription_start"] == "end_of_use_period":
        return r.use_end + timedelta(days=1)
    return r.claim_arises


def _entry_for(inp: LeaveInput, period_no: int, start: date | None) -> LeavePeriodInput | None:
    entries = inp.periods
    if any(p.start is not None for p in entries):
        for p in entries:
            if p.start == start:
                return p
        return None
    return entries[period_no - 1] if 0 < period_no <= len(entries) else None
