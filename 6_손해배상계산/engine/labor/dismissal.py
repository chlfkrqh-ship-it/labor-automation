"""부당해고 기간 임금 상당액과 중간수입 공제(휴업수당 한도) (lane: dismissal_wage DW-01~DW-21, interim_income II-01~II-15).

사람이 사건.yaml `dismissal:` 절에 적은 해고일·종기 사실·임금 항목·중간수입으로 임금산정기간별 예상 임금을 내고,
휴업수당 한도를 넘는 부분에서만 기간이 대응하는 중간수입을 공제해 지급액을 낸다. 변론종결 뒤 "복직시까지 월 X원"
장래분 월 금액, 연차 모듈용 출근 간주 기간, 퇴직금 모듈용 계속근로 기간, 지연손해금 모듈용 원금 항목과
근로관계 정보(`DismissalClaimInfo`)를 함께 낸다. 해고 무효·통상임금성·상당인과관계·복직명령 진정성 같은
법적 판단은 하지 않는다. 사람이 판정해 입력한 값으로 계산만 한다. 지연손해금 이율은 계산하지 않는다
(조사 문서 dismissal_interest_20.md — interest 모듈 담당).
검증 판정(dismissal_wage_verify.json, interim_income_verify.json)이 조사 본문보다 우선한다. '확인불가' 규칙은
기본값으로 쓰지 않고 옵션으로만 둔다. 금액 기대값은 판결 원문 숫자로 검증했다(tests/test_labor_dismissal.py).

---------------------------------------------------------------- 청구권과 포함 임금
DW-01 [판례확립] 해고가 무효이면 민법 제538조 제1항에 따라 "계속 근로하였을 경우에 그 반대급부로 받을 수 있는
      임금 전부"(대법원 1993. 12. 21. 선고 93다11463). 5인 미만 사업장은 시행령 [별표 1]에 제23조 제1항이 없어
      '정당한 이유 없는 해고 = 무효'가 성립하지 않으므로 무효 근거(`invalidity_basis`)를 받는다(검증 수정).
      lsa_23 을 5인 미만 사업장에 쓰면 오류.
DW-02 [판례확립] 근로기준법 제2조의 임금 전부, 통상임금에 국한되지 않음(93다11463 "평균임금산정의 기초가 되는 임금의
      총액에 포섭될 임금이 전부 포함"). 시혜적 금품 제외(대법원 2013. 2. 28. 선고 2010다105815 "반대채무로서의 임금에
      해당하지 아니하는 시혜적인 금품은 … 그 지급을 구할 수 없다").
DW-03 [판례확립·하급심] 항목 분류(`ITEM_CATEGORIES`). 자녀학자금은 기본 포함이 아니라 '심리 필요'(대법원 2011다42324
      "지급되었을 것인지를 따져본 후") → include 를 사람이 적어야 한다. 보직수당(대법원 90다카25277, 교원 사안)도 같다.
      시혜적 금품(discretionary)은 제외. 정기·일률 지급이 아닌 항목(periodic: false)은 제외(90다카25277 입시수당).
      장기근속 포상·무상주식 등은 하급심(서울고법 2014나16809) 표시.
DW-04 [판례확립(제외 원칙)·불명확(경계)] 실비변상적 급여 제외(2011다42324 "실비변상적 성격의 급여는 제외"). 같은 판결은
      '일률적으로' 지급된 자가운전보조금도 차량운행 요건이 없으면 제외 → 조사자의 '일률 지급이면 포함' 기본 로직 폐기(검증).
      `dw_expense_test`: requirement_linked(기본, 지급요건이 비용·업무행위에 연동되면 제외) | uniform_payment(하급심 옵션).
DW-05 [판례확립(포함)·하급심(산정)] 해고가 없었다면 계속 받았으리라 예상되는 연장·야간·휴일수당 포함(대법원 92다39860,
      93다11463 — 모두 원심 방식 수긍). `regular: true` 여야 포함(서울중앙지법 2019가단5138071 "어쩌다 가끔씩 하는 것에
      불과"하면 제외). 동료 평균시간·인상분의 증명책임은 근로자(대법원 1994. 10. 25. 선고 94다25889 "다른 근로자들이
      실제 연장근로하였다는 점 등은 모두 원고에게 입증책임") → warning. 5인 미만은 제56조 미적용 → 가산율 1.0·야간 0.
DW-06 [판례확립] 단협에 따른 인상(대법원 93다21736 "해고처분 이후에 체결된 단체협약서에 의하여 인상된 임금"), 자동승급
      (대법원 92다55480), 평가연동 인상은 적정한 등급(대법원 2018다279040). 재량 승진 보수 증가는 원칙적 불포함
      (대법원 94다446 "자동으로 승진된다거나 … 상당한 정도로 확실하게 예측할 수 있다는 등의 특별한 사정이 없는 한")
      → kind: promotion 은 certain: true 일 때만 반영. 소급 적용일(`applies_from`)은 필수(검증). 누적 인상 끝수는
      수원지법 2019나58100 "소수점 이하는 반올림"(`dw_raise_rounding`, 기본 half_up).
DW-07 [판례확립(포함요건)·하급심(금액)] 성과급은 규정에 지급사유·기준이 있고(rule_basis) 정기·계속 지급되면 포함
      (2011다42324). 동료 평균 등 금액 추정은 하급심(인천지법 2021나70304, 검증 재열람 못함) → warning.
DW-08 [불명확] 기준 월임금 방식은 대법원이 정하지 않음(대법원 94다40987은 근거 없는 단정을 파기했을 뿐). 증명책임은
      근로자(94다25889). `dw_base_wage_method`:
        items                          항목 합산(약정 월급·고정수당·상여 월할 — 창원 2018가합52160, 대구 2020가합210338,
                                       속초 2024가합30450). 항목에 history 를 주면 정상근무기간 월평균(서울고법 2014나16809,
                                       `dw_monthly_avg_rounding`)
        avg_daily_3m                   해고 직전 3개월 평균임금 일액 × 일수(서울중앙지법 2023나15560 114,130원 × 119일)
        avg_monthly_3m_ordinary_floor  3개월 월평균, 통상임금보다 적으면 통상임금(수원지법 여주지원 2023가합11391,
                                       제2조 제2항)
        last_month                     직전 1개월 지급액 고정. 인상 스케줄이 있으면 반영하지 않고 warning(93다21736 파기 사유)
      G6 의 '반올림'은 버림과 결과가 같아 반올림 근거가 아니다(검증).

---------------------------------------------------------------- 기간
DW-09 [실무관행] 기산일. 조사자의 paid_through_date + 1 기본값 폐기(검증: 대구 2020가합210338 "해고 이전 근로를 제공하였으나
      임금을 지급받지 못한 2019. 7. 20.부터 같은 달 24일까지"와 "해고 다음날인 2019. 7. 25.부터"를 구분).
      `dw_start_rule`: effective_date(기본, 해고 효력발생일 당일 — 2023나15560 "2021. 1. 1. ~ 2021. 4. 29.", 속초 2024가합30450)
      | next_day(2020가합210338, 93다21736 원심). `start_date` 를 적으면 그 날(출소 후 기산 등 — 94다25889 출소 4. 28.
      → 5. 1. 사실인정이라 자동 규칙을 두지 않음). `paid_through_date` 다음날부터 기산일 전날까지는 '해고 전 미지급 임금'
      행(kind=pre_dismissal)으로 따로 두고 중간수입 공제·출근 간주에서 뺀다.
DW-10 [판례/법리(정년·만료·장래이행)·하급심(복직명령)] 종기 = 다음 후보 중 가장 이른 날.
        실제 복직일 전날(2014나16809, 2020가합210338)
        근로관계 종료일(termination: 정년·계약만료·사직·사망·재해고·복직 포기 — 2023나15560 "2021. 4. 29.을 최종 퇴사일")
        갱신기대권이 있으면 계약만료 대신 갱신 간주된 계약기간 만료일(`renewed_term_end`, 대법원 2007두1729 "기간만료 후의
        근로관계는 종전의 근로계약이 갱신된 것과 동일")
        정당한 복직명령 불응 시 복직일 전날(하급심 서울중앙지법 2018나34536; 진정성 부정례 속초 2024가합30450)
        — `dw_return_order_end`: apply(기본, genuine·refused 를 사람이 true 로 적은 경우만) | ignore
      2019두52386(전원합의체)은 소의 이익 판결이어서 간접 근거다(검증). 종기가 없거나 변론종결 뒤이면 과거분은
      `past_until`(없으면 변론종결일)까지, 그 뒤는 장래분(DW-19, 90다카25277 "변론종결 이후부터 … 복직할 때까지").
DW-11 [판례확립] 제외기간: 구속(94다40987, 징역형 선고 + 상당기간 구속 전제 — convicted 가 아니면 warning), 수배·도피
      (94다25889 "해고처분시부터 위 출소시까지는 애당초 원고가 근로의 제공을 할 수 없는 처지"), 사업 정당 폐지(93다50017),
      쟁의 참가 명백(2010다99279, 증명책임 사용자), 유효한 정직(2014나16809, 하급심). 다른 직장 취업·창업은 제외 사유가
      아니다(2010다99279). 제외일은 역일 단위로 빼고 부분월은 DW-12 일할. 중간수입 대응 기간에서도 뺀다.
      부당 정직·대기발령에도 같은 계산(2010다99279 무기정직·대기발령 사안) → `discipline_type`.
DW-12 [불명확] 월 중도 일할 분모 `dw_proration`: period_calendar_days(기본 — 임금산정기간 역일수: 2014나16809 29일/31일,
      2020가합210338 ÷31일, 대전지법 2023가합203713 18/30) | fixed_30(창원지법 통영지원 2014가단5110 "27일/30일",
      2023가합11391 "14일/30일"). 기본값은 대법원 근거 없는 실무 선택이다. 기간은 양끝 포함.
DW-13 [실무관행] 끝수. 단계별 옵션: `dw_proration_rounding`(floor 기본 | half_up | ceil10 "원 단위에서 올림"
      2020가합210338 333,340원 | round10_half_up "원 단위에서 반올림" 같은 판결 퇴직금), `dw_monthly_avg_rounding`,
      `dw_daily_rate_rounding`(floor | half_up | keep_2dp 163,043.48원), `dw_bonus_monthly_rounding`(속초 판결은 "원 미만
      반올림"이라 적었으나 합계 4,276,043원은 버림으로만 재현 — 기본 floor), `dw_raise_rounding`, `dw_withholding_rounding`.
      G5 80,129,040원의 10원 올림이 7월분 단계인지 합계 단계인지는 별지 미제공으로 구별 불가(검증) — 엔진은 행 단계에 적용.
DW-14 [하급심·확인불가] 정기상여금 배분 `dw_bonus_allocation`: annual_div_12(기본 — 속초 2024가합30450 "3,115,950원 ×
      150% ÷ 12개월", 93다21736 원심) | payment_month(2014나16809 지급월 계상·지급대상기간 일할 "29일/59일" — 검증에서 원문
      재열람 못함, 옵션으로만).
DW-15 [판례확립] 해고기간은 연간 소정근로일수·출근일수에 모두 산입(대법원 2011다95519) → `result.deemed_attendance_periods`
      (제외기간을 뺀 해고기간). 5인 미만은 제60조 미적용 → leave_allowance 항목 0, warning. 변론종결 시 끝나지 않은 연도의
      연차수당은 장래 청구 배척(속초 2024가합30450) → `dw_future_leave_claim`(기본 false). 연차수당에는 중간수입 공제
      여지가 없다(속초 각주) → `ii_leave_allowance`: exclude_from_deduction(기본) | include_as_claimed(원고가 70%만 청구).
DW-16 [하급심] 해고기간은 퇴직금 계속근로기간에 포함(2023나15560 "3년 98일", 2020가합210338 "515일간 재직") →
      `result.continuous_service_periods`(제외기간 포함 — 2011다42324 재직기간 일부 제외 불허 일반론).
DW-17 [판례확립] 중간수입 공제는 휴업수당 초과분에서만(아래 II 규칙).
DW-18 [판례확립·법령·불명확] 지연손해금은 이 모듈이 계산하지 않는다. Claim.due_date = 각 임금산정기간의 정기지급일,
      근로관계 종료 여부·종료일·사유, 해고무효 확정 여부, 구제명령 여부, 제1심 변론종결일은 `DismissalClaimInfo` 로 넘긴다
      (구법 복직자 20% 부적용 2014다28305, 개정 제37조 제1항 제2호·제2항(2025. 10. 23. 시행), 시행령 제18조 제3호 판단은
      interest 모듈). Claim.settlement 는 근로관계가 끝났어도 False 로 둔다 — interest 모듈은 settlement=True 를
      'due_date = 마지막 근무일 + 14일인 청산 금품'으로 읽기 때문이다(DI-02). 종료일·사유는 interest 절의
      last_working_day·end_cause 로 옮기고, 제36조 기한은 claim_info.settlement_deadline(종료일 + 14일)에 둔다.
      종료일은 근로관계가 실제로 끝난 날이다 — 갱신기대권이 인정되면 원래 계약만료일(termination.date)이 아니라 갱신
      간주된 계약기간 만료일(renewed_term_end)이고, 그 날이 없으면 근로관계 계속(continuing)으로 넘긴다(DW-10, 2007두1729).
      worker.last_working_day 가 이 종료일보다 앞서면(해고일·원래 계약만료일을 적은 경우 등) warning.
DW-19 [판례확립] 과거분 확정액과 "YYYY. M. D.부터 복직시까지 월 X원"(97다58194, 2009다102452, 2024다294156 기판력)
      → `result.future_monthly_amount`, `future_start_date`. 장래분에는 끝나지 않은 중간수입(end 없음)을 계속 반영
      (`dw_future_interim`, 속초 "월 2,993,230원"). 항목 누락은 기판력으로 추가 청구가 막히므로 warning.
DW-20 [법령·하급심] 기지급액은 합의 없으면 민법 제479조 제1항 법정충당(비용→이자→원본). 이자가 필요하므로 이 모듈은
      원금을 줄이지 않고 `payments` 를 claim_info 로 넘기며, 충당 계산 헬퍼 `allocate_payment` 를 둔다(2018가합52160,
      2014나16809). 원금 금액 기준 `dw_amount_basis`: gross(기본) | net_of_withholding — 2018가합52160 은 약정·기지급 모두
      "세금 3.3%를 공제하고 계산한 금액"으로 원금과 지연손해금을 계산(검증: '세전 총액' 단정 반박).
      사용자가 해고기간 중 지급한 휴직수당은 실수령액 공제(90다카25277), 퇴직금은 근로자가 상계를 자인할 때만(하급심).
DW-21 [법령·실무관행] 노동위원회 금전보상 모드(mode: labor_commission_award): 일액 = 월급 × 12 ÷ 365(원 미만 버림) ×
      (기산일~판정일 + 송달기간 30일)(행정심판 2022-09280 인정사실, 재결 원문 미재확인). 5인 미만은 구제신청 불가(별표 1
      제2장에 제28조~제33조 없음) → 오류.

---------------------------------------------------------------- 중간수입 공제
II-01 [판례확립] 노무제공의무를 면한 것과 상당인과관계 있는 이익만 공제(대법원 2014다65397). 노동조합기금 제외
      (대법원 91다2656 "이를 가지고 원고들이 노무제공을 면한 것과 상당인과관계에 있는 이익이라고는 볼 수 없다 할 것이므로").
      수입은 수령일이 아니라 그 수입이 대가인 근로 기간에 귀속(서울중앙지법 2019나53961, 확정). 부업·소액 기타소득은
      상당인과관계 부정례(2019나53961, 창원 2018가합52160 주말 강의) → side_job·other 는 causal: true 일 때만 공제.
II-02 [판례확립] 기간 p마다 limit = max(0, W − H), deduct = min(I, limit), pay = W − deduct. "I − H 를 공제"(대법원
      2021다279903 파기)와 "I < H 이므로 공제 0"(대법원 2014다65397 파기)은 입력(`deduction_formula`)으로 받지 않는다.
      W < H 이면 공제 0, W 로 끌어올리지 않는다(대법원 90다18999 "휴업수당의 한도에서는 이를 중간수입공제의 대상으로
      삼을 수 없고"). 끝수 `ii_rounding`: floor(기본) | half_up(수원고법 2025나11545 "원 미만은 반올림함").
      순서 `ii_rounding_order`: prorate_first(기본, 일할 → 끝수 → 율 → 끝수; 대전지법 2023가합203713 489,516원 =
      floor(floor(2,719,539 × 18/30) × 0.3), 한 번에 곱하면 489,517원) | rate_first(월 한도를 먼저 끊고 일할: 2023가합11391
      "1,320,000원 × (2개월 + 14일/30일)" = 3,256,000원).
II-03 [판례확립(율)·법령] 율: 1989. 3. 28.까지 60%, 1989. 3. 29.부터 70%(90다카25277 "1989.3.28.까지는 … 60퍼센트를, 그 이후부터는
      … 70퍼센트"). 한 창이 경계를 걸치면 일 단위로 나눠 각각 계산한다. 조문: 구 제38조(법률 제3965호 60% → 제4099호 70%) →
      법률 제5245호(1997. 3. 1.) 단서·제2항 신설 → 제5309호 제45조(1997. 3. 13.) → 제8372호 제46조(2007. 4. 11.) →
      현행 법률 제21373호(2026. 8. 20.). 제46조 제2항(노동위원회 승인 휴업)은 입력에서 뺀다.
II-04 [불명확] 휴업수당 기초금액 `ii_cap_base` — 대법원 판시 없음. **기본값을 정하지 않는다**(검증: 조사자의 A 기본 제안은
      근거 없음). 사건.yaml 에서 반드시 고른다. 판결 관찰 빈도는 C(약정 월 임금 × 70%, 곧 30% 한도)가 가장 높다
      (서울중앙지법 2019나79130, 서울고법 2021나2030052, 대전지법 2023가합203713, 서울중앙지법 2020가단5243276,
      수원지법 안산지원 2023가단88293). 옵션별 끝수 위치(검증 M-03):
        A_daily_avg            H = floor(해고 전 3개월 일평균 × 율 × 365/12)(부산고법 2020나54503 2,288,662원)
        B_monthly_avg          H = floor(3개월 월평균 × 율)(대전고법 2017나14978 1,689,613원)
        C_contract_wage_ratio  limit = floor(W × (1 − 율))(2023가합203713). `ii_c_rounding_target=pay` 이면
                               limit = W − floor(W × 율)(속초 2024가합30450: 공제 후 월 2,993,230원 = 4,276,043 × 70% 버림)
        D_rolling_avg          기초 = floor(직전 3개 임금산정기간 가정 임금 합 ÷ 3), H = floor(기초 × 율)(광주지법 2017나58303,
                               "실제 받았을 월 임금 기준" 주장 배척)
        E_avg_wage_fixed_ratio limit = floor(평균임금 월액 × (1 − 율)), W 와 무관(서울중앙지법 2019나53961 883,213원,
                               서울고법 2012나55770)
      A·B·D·E 에는 제2조 제2항 통상임금 하한 적용(M-01): A 는 deps `daily_ordinary_of(해고일)`, B·D·E 는
      `interim_cap.ordinary_monthly_wage`. 월 중 일부 창의 H 일할(A·B·D)은 관찰 사례 없음 → warning.
II-05 [불명확] 제46조 제1항 단서(평균임금 70%가 통상임금 초과 시 통상임금) `ii_apply_ordinary_wage_cap` 기본 false.
      단서 시행(1997. 3. 1.) 전 기간에는 켤 수 없다(오류).
II-06 [판례확립(대응 원칙)·하급심(단위·일할·안분)] 중간수입이 발생한 기간과 시기적으로 대응하는 기간의 임금에서만 공제
      (90다카25277, 대법원 2013다45075). 청구 기간·제외기간·사용자 주장 범위(`employer_claim_periods`, M-05 — 2019나79130)
      밖 수입은 무시하고 warning. 한 창의 초과 수입을 다른 창으로 넘기지 않는다.
        `ii_income_allocation`(기본값은 사용자가 정함 — 필요할 때 없으면 오류): calendar_days(수입 총액 × 겹친 일수 ÷
        수입 기간 일수, 2023가합203713) | assigned_wage_period(항목 assigned_period 로 귀속 임금산정기간 지정, 부산고법
        2020나54503 7. 8.~8. 5. 급여를 7월분에) | annual_equal_monthly(연간 총액 ÷ 12, 서울고법 2012나55770 각주,
        광주지법 2017나58303). 항목에 assigned_period 나 monthly_amount 가 있으면 그것을 따른다. 이 옵션은 여러 비교
        기간에 걸친 총액(amount) 항목에만 적용하고, 비교 기간 하나 안의 수입은 안분하지 않고 그대로 공제한다.
        annual_equal_monthly 는 연간 총액용이다 — 수입 기간이 1년이 아닌 총액에 쓰면 ÷ 12를 하되 warning(연간 총액이
        아니면 monthly_amount 로 적는다).
        `ii_cap_window`: income_overlap_days(기본 — 한도를 수입과 겹친 날의 임금으로만 계산, 2023가합203713·2025나11545) |
        whole_wage_period(임금산정기간 전체 한도, 조사자 원안 — 2023가합203713 11월분이 1,903,678원이 되어 판결과 불일치).
        assigned_period 항목은 그 기간 전체와 비교한다(부산고법).
        `ii_period_anchor`: wage_period(기본) | income_start(수입 시작일부터 1개월 단위 창 — 2019나79130 "2019. 1. 14.부터",
        2023가합11391 "2개월 + 14일"). income_start 창의 공제액은 창 마지막 날이 속한 임금산정기간 행에 넣는다.
        기간 합산 비교(연간·전체기간, 2012나55770·서울중앙 2022가합515465)는 2019나53961 "年이 아닌 月"과 갈려 구현하지 않음.
II-07 [판례확립(원심 수긍 포함)·하급심] 판단축 두 가지(검증): ① 제46조의 '휴업'에 해당하는가(무효 전적 기간은 임금청구여도
      비해당 — 2013다45075 "위와 같은 원심의 판단은 수긍할 수 있고") ② 근로관계 해소 후·고용관계 성립 전 손해배상인가
      (대법원 91다44100 "근로관계가 일단 해소되어 … 근로기준법 제38조를 적용할 수 없다", 2015다232859, 2020다230970 원심
      수긍). ①이 예이고 ②가 아니면 한도 적용. `claim_basis`(CLAIM_BASES)가 두 축의 기본값을 정하고 `art46_suspension`,
      `damages_after_termination` 로 덮어쓸 수 있다. 고용 의사표시 판결 확정(송달)일(`employment_deemed_date`) 전날까지는
      손해배상(한도 없음), 당일부터는 민법 제538조 제1항 임금(2020다230970) — 그 기간 한도 적용은 판시가 없어
      `ii_post_deemed_employment_cap`(기본값 없음, 필요할 때 오류).
II-08 [법령·하급심] 상시 4명 이하 사업장은 제46조 미적용(시행령 [별표 1] 제3장 "제43조부터 제45조까지의 규정, 제47조부터
      제49조까지의 규정") → 한도 없이 W 까지 전액 공제(부산고법 2020나54503). 판정은 시행령 제7조의2(법 적용 사유 발생일 전
      1개월, 기준 미달 일수 2분의 1 보정) — `ii_headcount_basis`: prior_month_majority(기본, 창이 속한 임금산정기간 시작일
      전 1개월 중 deps small_business(d) 가 참인 날이 절반 이상이면 5인 미만. 연인원 자료가 없어 일별 판정으로 근사 —
      부산고법은 2019. 6. 30. 이후 5인 미만인데 7월분까지 한도 적용) | reference_day(시작일 당일 값). 2008. 6. 25.(제7조의2
      신설) 전 기간은 reference_day 로 보고 warning.
II-09 [하급심] 노동위원회 금전보상 임금상당액에도 한도(서울고법 2025누6601) → claim_basis labor_commission_monetary_compensation.
II-10 [판례확립·하급심·확인불가] 수입 종류(INCOME_TYPES): 실업급여(서울고법 2018나2016391 확정)·사학연금(대전고법 2017나14978)·
      전 사용자의 해고예고수당(서울고법 2018나2003456)·노조기금은 공제하지 않는다. 사업소득 필요경비 기준은 확인불가 →
      `ii_business_income_basis` 기본값 없음(사업소득이 있으면 오류). 근로소득 세전/세후도 원문 미확인 → 입력값 그대로.
II-11 [판례확립·하급심] 사용자 기지급 휴직수당은 실수령액 공제(90다카25277, '한도 무관' 문언은 없음 — 해석), 퇴직금은
      근로자가 상계를 자인한 때만(서울고법 2018나2016391 상계 불가, 2012나55770 자인 시 공제). payments 로 받는다(DW-20).
II-12 [판례확립] 사실심에서 주장되지 않은 중간수입은 공제하지 않는다(93다37915) → raised_by: none 은 무시. 한도 없는 공제는
      근로자가 '한도 없는 공제 자체'를 자인한 경우에만(90다카25277 — 가정적 최저임금 상당액 공제 동의 사안).
      수입액 자인만으로는 한도 적용(서울고법 2021나2030052) → `admitted_without_cap` 기본 false.
II-13 [판례확립·불명확] 인용액 W 는 세전(2021다279903 "지급시기 전에 미리 원천세액을 징수·공제할 수는 없고").
      한도·부당이득 계산의 W 기준은 87다카2132(세후 지급 수긍)·2019나53961(세후 W 로 한도)와 긴장 →
      `ii_wage_basis_for_cap`: gross(기본) | net_of_withholding.
II-14 [하급심] 공제 없이 전액 지급했으면 Σ공제액이 부당이득(광주지법 2017나58303 21,180,117원) — mode: refund.
      인용액은 청구액으로 제한해 따로 출력(같은 판결 20,847,000원).
II-15 [불명확] 평균임금 산정기초 밖 임금(in_average_wage: false)을 한도 없이 공제 `ii_exclude_non_avg_items_from_cap`
      기본 false: limit = max(0, W_avg − H) + W_non. 2012나55770 은 한도를 평균임금 30%로 고정한 사례라 반대 근거로도 못 쓴다.

---------------------------------------------------------------- 검증 누락 규칙 반영(M)
DW-M01 5인 미만 분기(무효 근거·가산율·연차·노동위원회 모드·휴업수당 한도) — 구현.
DW-M02 증명책임 메타(94다25889 근로자 / 2010다99279 사용자) — trace·warning.
DW-M03 재량 승진 제외(94다446) — 구현(kind: promotion).
DW-M04 단협 부당징계 가산보상금(2009다102452) — 규정 해석 문제라 구현하지 않음. 사람이 금액을 정해 항목으로 넣는다.
DW-M05 부당 정직·대기발령 동일 산정(2010다99279) — discipline_type.
DW-M06 해고 전 미지급 근로임금 구분(2020가합210338) — pre_dismissal 행.
DW-M07 수배·도피 기간 제외(94다25889) — exclusions reason fugitive.
DW-M08 소멸시효·시효중단(2011다20034) — 판정하지 않음. warning 만.
DW-M09 개정 제37조 제2항 기준일 — interest 모듈. claim_info 로 정기지급일·종료일 전달.
DW-M10 소촉법 이율 경과규정(1심 변론종결 기준, 2019나58100 각주) — interest 모듈. first_instance_closing_date 전달.
DW-M11 원금·기지급액 세전/세후 — dw_amount_basis.
DW-M12 구제명령 임금상당액은 제36조 금품 아님(근로기준정책과-1518) — claim_info.remedy_order 전달.
II-M01 통상임금 하한(제2조 제2항) · II-M02 시행령 제7조의2 · II-M03 옵션별 끝수 위치·순서 · II-M04 고용 의사표시 판결
      확정일 경계 · II-M05 사용자 주장 범위 · II-M06 장래 정기금 · II-M07 원직복직 거부·금전보상 신청 후에도 한도(2025누6601)
      · II-M08 한도 산정 창 · II-M09 옵션 E · II-M10 수입 귀속 기준 · II-M11 세전/세후 한도 · II-M12 조문 연혁 가드 ·
      II-M13 공익신고·급여감액 손해배상 한도 · II-M14 부당이득 청구액 제한 — 구현.
II-M15 사용자 휴업(비해고) 기간(근로복지과-511, W = H 이므로 공제 0) — 해고기간 모듈 범위 밖이라 구현하지 않음.

---------------------------------------------------------------- 사건.yaml `dismissal:` 절
    dismissal:
      mode: back_pay                   # back_pay | refund(II-14) | labor_commission_award(DW-21)
      claim_basis: wage_538_invalid_dismissal   # 필수(CLAIM_BASES)
      discipline_type: dismissal       # dismissal | suspension | standby | transfer
      invalidity_basis: lsa_23         # lsa_23 | cba_rules | procedure | other (5인 미만이면 lsa_23 불가)
      dismissal_date: 2019-07-24       # 해고(징계) 효력발생일
      start_date: null                 # 기산일 직접 지정(출소 후 등)
      paid_through_date: 2019-07-19    # 임금을 받은 마지막 날(해고 전 미지급 임금 행)
      reinstatement_date: 2020-11-25   # 실제 복직일(종기 = 전날)
      return_order: {date: 2021-03-02, effective_date: 2021-03-15, genuine: true, refused: true}
      termination: {date: 2021-04-29, cause: waiver}   # retire | contract_end | resign | death | re_dismissal | waiver
      renewal_expectation: false
      renewed_term_end: null
      closing_date: 2024-09-12         # 변론종결일
      first_instance_closing_date: null
      past_until: 2024-08-31           # 과거분 마감(없으면 closing_date)
      future_start_date: 2024-09-01    # 장래분 시작(없으면 past_until 다음날)
      dismissal_invalid_final: false   # 해고무효 확정 여부(지연손해금 모듈용)
      remedy_order: {issued: true, final: false, date: 2021-03-01}
      small_business: false            # 전 기간 상시 4명 이하(기간별이면 worker.small_business_periods 또는 deps)
      exclusions: [{start: 2009-12-21, end: 2010-03-20, reason: valid_suspension, convicted: null, note: ""}]
      base_wage: {three_month_total: 10500000, three_month_days: 92, avg_daily_wage: null, ordinary_monthly_wage: null}
      wage_items:
        - {name: 기본급, category: base, monthly: 3115950, from: null, to: null}
        - {name: 상여금, category: regular_bonus, annual_rate: 1.5, base_items: [기본급]}
        - {name: 제수당, category: fixed_allowance, history: {total: 3697218, months: 5}}
        - {name: 정기상여, category: regular_bonus, monthly: 1607978, schedule: [{month: 4, rate: 1.0, target_months: 2}]}
        - {name: 연장수당, category: overtime, regular: true,
           overtime: {method: pre_dismissal_avg_hours, hourly_wage: 10000, hours: {overtime: 20, night: 4, holiday: 8}}}
        - {name: 연차수당, category: leave_allowance, monthly: 245520, to: 2021-12-31}
        - {name: 자가운전보조금, category: expense, monthly: 200000, requirement_linked: true}
      raises: [{applies_from: 2011-04-01, amount: 71000, items: [기본급], kind: cba}]
      withholding_rate: 0.033
      payments: [{date: 2018-07-02, amount: 14350000, type: back_pay, basis: net}]
      interim_income:
        - {start: 2020-12-01, end: null, monthly_amount: 2600000, type: employment, raised_by: employer,
           admitted_without_cap: false, causal: null, assigned_period: null, business_expenses: null}
      interim_cap: {avg_daily_wage: 107491, avg_monthly_wage: null, ordinary_monthly_wage: null,
                    pre_dismissal_wages: {"2012-12": 6711061}}
      employer_claim_periods: [[2019-01-14, 2019-09-02]]
      employment_deemed_date: null
      art46_suspension: null
      damages_after_termination: null
      deduction_formula: standard      # 금지 산식(income_minus_allowance, zero_if_income_below_allowance)은 오류
      refund_claimed_amount: null
      labor_commission: {monthly_wage: 3000000, decision_date: 2020-12-17, service_days: 30}
    options:
      ii_cap_base: C_contract_wage_ratio   # 중간수입이 있으면 필수
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_CEILING, ROUND_DOWN, ROUND_HALF_UP, Decimal, InvalidOperation

from .common import (
    Claim,
    LaborError,
    OptionSpec,
    PaySlice,
    Trace,
    add_months,
    dec,
    days_inclusive,
    is_within,
    parse_date,
    pay_date_for,
    pay_periods,
)

__all__ = [
    "CLAIM_BASES", "EXCLUSION_REASONS", "INCOME_TYPES", "ITEM_CATEGORIES", "OPTIONS", "PAYMENT_TYPES", "RULES",
    "TERMINATION_CAUSES",
    "DismissalClaimInfo", "DismissalInput", "DismissalInstallment", "DismissalResult", "DismissalRow",
    "Exclusion", "InterimIncome", "Payment", "Raise", "WageItem",
    "allocate_payment", "calculate_dismissal", "labor_commission_award_amount", "load_dismissal",
]

ZERO = Decimal(0)
ONE = Decimal(1)
RATE_60 = Decimal("0.6")
RATE_70 = Decimal("0.7")

DATE_RATE_70 = date(1989, 3, 29)            # 법률 제4099호 — 휴업지불 60% → 70%
DATE_ORDINARY_PROVISO = date(1997, 3, 1)    # 법률 제5245호 — 통상임금 단서 신설
DATE_HEADCOUNT_RULE = date(2008, 6, 25)     # 시행령 제7조의2 신설
DATE_NEW_ART37 = date(2025, 10, 23)         # 개정 제37조 시행(법률 제20520호)

CLAIM_BASES = {
    # key: (설명, 제46조 휴업 해당, 근로관계 해소 후·고용관계 성립 전 손해배상, 상태)
    "wage_538_invalid_dismissal": ("해고무효 임금청구(민법 제538조 제1항; 90다카25277, 93다37915, 2021다279903)", True, False, "판례확립"),
    "tort_dismissal_relationship_continues": ("근로관계 존속 전제 부당해고 불법행위 손해배상(94다446)", True, False, "판례확립"),
    "tort_reappointment_refusal": ("재임용거부 불법행위 손해배상(2014다65397)", True, False, "판례확립"),
    "tort_whistleblower_punitive": ("공익신고 불이익 징벌적 손해배상의 실제 손해(수원고법 2025나11545 확정)", True, False, "하급심"),
    "tort_suspension_pay_cut": ("직위해제·급여감액 불법행위 손해배상(수원고법 2025나11545 확정)", True, False, "하급심"),
    "labor_commission_monetary_compensation": ("노동위원회 금전보상 임금상당액(서울고법 2025누6601)", True, False, "하급심"),
    "damages_after_relationship_terminated": ("근로관계 해소 후 복직의무 불이행 손해배상(91다44100)", True, True, "판례확립"),
    "damages_direct_hire_duty": ("파견법 직접고용의무 불이행 손해배상(2015다232859)", True, True, "판례확립"),
    "damages_employment_succession_duty": ("고용승계의무 불이행 손해배상(2020다230970 원심 수긍)", True, True, "판례확립"),
    "wage_invalid_transfer": ("무효 전적 기간 임금 — 제46조 '휴업' 비해당(2013다45075 원심 수긍)", False, False, "판례확립"),
}

TERMINATION_CAUSES = {
    "retire": "정년 도달",
    "contract_end": "근로계약기간 만료",
    "resign": "사직",
    "death": "사망",
    "re_dismissal": "재해고(서울고법 2021나2031970 20% 부정례 — 지연손해금 모듈 판단)",
    "waiver": "복직 포기·금전보상 선택(서울중앙지법 2023나15560)",
}

_INTEREST_END_CAUSE = {"retire": "retirement", "contract_end": "contract_end", "resign": "resignation",
                       "death": "death", "re_dismissal": "redismissal", "waiver": "other"}

EXCLUSION_REASONS = {
    "detention": "구속(대법원 94다40987 — 징역형 선고 + 상당기간 구속 전제)",
    "fugitive": "수배·도피(대법원 94다25889)",
    "business_closure": "사용자의 정당한 사업 폐지(대법원 93다50017)",
    "strike": "해고가 없었어도 쟁의행위 참가가 명백한 기간(대법원 2010다99279, 증명책임 사용자)",
    "valid_suspension": "유효한 정직 기간(서울고법 2014나16809, 하급심)",
    "incapacity": "질병 등 사실상 근로 불능(하급심 스니펫, 참고)",
    "other": "기타 근로 제공 불가능 기간(근거를 note 에 적을 것)",
}

ITEM_CATEGORIES = {
    "base": "기본급",
    "fixed_allowance": "고정수당(근속·가족·직무·직책 등, 2011다20034·2010다105815)",
    "regular_bonus": "정기상여금(DW-14)",
    "overtime": "연장·야간·휴일수당(DW-05)",
    "performance_bonus": "성과급·성과배분상여금(DW-07, 2011다42324)",
    "leave_allowance": "연차휴가수당(DW-15, 2011다95519)",
    "attendance_award": "개근·정근 표창(2011다20034)",
    "long_service_award": "장기근속 포상(서울고법 2014나16809, 하급심)",
    "expense": "실비변상적 급여(DW-04)",
    "discretionary": "시혜적 금품(2010다105815) — 제외",
    "child_education": "자녀학자금보조(2011다42324 — 심리 필요, include 필수)",
    "position_allowance": "보직수당(90다카25277 교원 사안 — 해고 당시 보직 여부, include 필수)",
    "other": "기타",
}

INCOME_TYPES = {
    # key: (설명, 처리) 처리: deduct | business | causal_required | never
    "employment": ("다른 직장 근로소득(90다카25277)", "deduct"),
    "research": ("연구용역 등 노무제공 면제와 상당인과관계 있는 수입(2014다65397)", "deduct"),
    "business": ("사업소득(필요경비 기준 확인불가, II-10c)", "business"),
    "side_job": ("겸업·부업·소액 기타소득(상당인과관계 부정례 2018가합52160, 2019나53961)", "causal_required"),
    "other": ("기타 수입(상당인과관계를 사람이 판단)", "causal_required"),
    "union_fund": ("노동조합기금 지급금(91다2656)", "never"),
    "unemployment_benefit": ("고용보험 실업급여(서울고법 2018나2016391 확정)", "never"),
    "pension": ("사학연금 등 연금(대전고법 2017나14978 확정)", "never"),
    "prior_employer_notice_pay": ("다른(전) 사용자가 지급한 해고예고수당(서울고법 2018나2003456 확정)", "never"),
    "other_dispute_settlement": ("해고기간 전 다른 분쟁의 미지급 임금·위로금(2019나53961)", "never"),
}

PAYMENT_TYPES = {
    "back_pay": "해고기간 임금 일부 지급",
    "suspension_allowance": "휴직수당 등 해고기간 중 지급액(90다카25277 실수령액 공제)",
    "notice_pay": "해고예고수당(2023나15560 별도 지급의무 인정례 — 충당 대상인지 사람이 판단)",
    "severance": "퇴직금(근로자가 상계를 자인할 때만 공제 — 서울고법 2018나2016391, 2012나55770)",
    "other": "기타",
}

_ROUND_CHOICES = {
    "floor": "원 미만 버림",
    "half_up": "원 미만 반올림",
}

OPTIONS: dict[str, OptionSpec] = {s.key: s for s in [
    OptionSpec("dw_base_wage_method", "items", "해고기간 기준 월임금 산정 방식", "DW-08", {
        "items": "임금 항목 합산(약정 월급·수당·상여 월할, history 는 정상근무기간 월평균)",
        "avg_daily_3m": "해고 직전 3개월 평균임금 일액 × 일수(서울중앙지법 2023나15560)",
        "avg_monthly_3m_ordinary_floor": "3개월 월평균, 통상임금보다 적으면 통상임금(수원지법 여주지원 2023가합11391)",
        "last_month": "직전 1개월 지급액 고정 — 인상 미반영(93다21736 파기 사유) 경고",
    }),
    OptionSpec("dw_start_rule", "effective_date", "해고기간 기산일", "DW-09", {
        "effective_date": "해고 효력발생일 당일(2023나15560, 속초 2024가합30450)",
        "next_day": "해고일 다음날(대구 2020가합210338, 93다21736 원심)",
    }),
    OptionSpec("dw_proration", "period_calendar_days", "월 중도 일할 분모", "DW-12", {
        "period_calendar_days": "임금산정기간 역일수(2014나16809, 2020가합210338, 2023가합203713)",
        "fixed_30": "30일 고정(창원지법 통영지원 2014가단5110, 2023가합11391)",
    }),
    OptionSpec("dw_proration_rounding", "floor", "일할 임금 끝수", "DW-13", {
        "floor": "원 미만 버림(2018가합52160, 2020가합210338 806,451원)",
        "half_up": "원 미만 반올림",
        "ceil10": "원 단위에서 올림(2020가합210338 333,340원·해고기간 80,129,040원)",
        "round10_half_up": "원 단위에서 반올림(2020가합210338 퇴직금)",
    }),
    OptionSpec("dw_monthly_avg_rounding", "floor", "정상근무기간·3개월 월평균 끝수", "DW-13", {
        "floor": "원 미만 버림(2014나16809 739,443원)",
        "half_up": "원 미만 반올림",
    }),
    OptionSpec("dw_daily_rate_rounding", "floor", "평균임금 일액 끝수", "DW-13", {
        "floor": "원 미만 버림(2023나15560 114,130원)",
        "half_up": "원 미만 반올림",
        "keep_2dp": "소수점 둘째 자리까지(2020가합210338 163,043.48원)",
    }),
    OptionSpec("dw_bonus_monthly_rounding", "floor", "상여금 월할 끝수", "DW-13", {
        "floor": "원 미만 버림(속초 2024가합30450 합계 4,276,043원 재현)",
        "half_up": "원 미만 반올림(속초 판결 문언)",
        "none": "끝수 유지 후 행 합계에서 처리",
    }),
    OptionSpec("dw_bonus_allocation", "annual_div_12", "정기상여금 배분", "DW-14", {
        "annual_div_12": "연 지급률 ÷ 12 매월 가산(속초 2024가합30450)",
        "payment_month": "지급월에 계상하고 지급대상기간 일할(2014나16809 — 검증 재열람 못함)",
    }),
    OptionSpec("dw_raise_rounding", "half_up", "정률 인상 누적 끝수", "DW-06", {
        "half_up": "소수점 이하 반올림(수원지법 2019나58100)",
        "floor": "원 미만 버림",
    }),
    OptionSpec("dw_expense_test", "requirement_linked", "실비변상적 급여 판단 기준", "DW-04", {
        "requirement_linked": "지급요건이 비용 발생·업무행위에 연동되면 제외(2011다42324)",
        "uniform_payment": "실제 비용과 무관한 일률 지급이면 포함(부산지법 동부지원 2023가단133232, 하급심)",
    }),
    OptionSpec("dw_return_order_end", "apply", "정당한 복직명령 불응 시 종기", "DW-10", {
        "apply": "genuine·refused 가 true 이면 복직일 전날까지(서울중앙지법 2018나34536, 하급심)",
        "ignore": "복직명령을 종기로 보지 않음",
    }),
    OptionSpec("dw_future_leave_claim", False, "변론종결 시 끝나지 않은 연도의 연차수당", "DW-15", {
        False: "청구하지 않음(속초 2024가합30450 배척)",
        True: "포함",
    }),
    OptionSpec("dw_amount_basis", "gross", "원금 금액 기준", "DW-20", {
        "gross": "세전 총액(2021다279903 선공제 불가)",
        "net_of_withholding": "원천징수 후 금액(2018가합52160 — 약정·기지급 모두 3.3% 공제 기준)",
    }),
    OptionSpec("dw_withholding_rounding", "floor", "원천징수 후 금액 끝수", "DW-20", _ROUND_CHOICES),
    OptionSpec("dw_future_interim", "continue_open_ended", "장래분 월 금액의 중간수입", "DW-19", {
        "continue_open_ended": "끝나지 않은(end 없음) 월 중간수입을 계속 공제(속초 2024가합30450 월 2,993,230원)",
        "none": "장래분에는 공제하지 않음",
    }),
    OptionSpec("ii_cap_base", None, "휴업수당 한도 기초금액(기본값 없음 — 반드시 선택)", "II-04", {
        None: "미선택 — 공제할 중간수입이 있으면 오류",
        "A_daily_avg": "해고 전 3개월 일평균 × 율 × 365/12(부산고법 2020나54503)",
        "B_monthly_avg": "해고 전 3개월 월평균 × 율(대전고법 2017나14978)",
        "C_contract_wage_ratio": "해당 기간 약정 임금 × (1 − 율) 한도(판결 관찰 빈도 가장 높음)",
        "D_rolling_avg": "매 기간 직전 3개월 가정 임금으로 재산정(광주지법 2017나58303)",
        "E_avg_wage_fixed_ratio": "평균임금 월액 × (1 − 율) 고정 한도(서울중앙지법 2019나53961)",
    }),
    OptionSpec("ii_c_rounding_target", "limit", "옵션 C 끝수 위치", "II-04", {
        "limit": "한도 = floor(W × 30%)(대전지법 2023가합203713)",
        "pay": "지급액 = floor(W × 70%), 한도 = W − 지급액(속초 2024가합30450)",
    }),
    OptionSpec("ii_rounding", "floor", "중간수입·한도 끝수", "II-02", _ROUND_CHOICES | {
        "half_up": "원 미만 반올림(수원고법 2025나11545)"}),
    OptionSpec("ii_rounding_order", "prorate_first", "일할과 율의 순서", "II-02", {
        "prorate_first": "일할 → 끝수 → 율 → 끝수(대전지법 2023가합203713)",
        "rate_first": "월 한도 → 끝수 → 일할 → 끝수(수원지법 여주지원 2023가합11391)",
    }),
    OptionSpec("ii_income_allocation", None, "여러 임금산정기간에 걸친 수입 총액의 안분(기본값은 사용자가 정함)", "II-06", {
        None: "미선택 — 안분이 필요하면 오류",
        "calendar_days": "수입 기간 역일수 비례(대전지법 2023가합203713)",
        "assigned_wage_period": "항목 assigned_period 로 귀속(부산고법 2020나54503)",
        "annual_equal_monthly": "연간 총액 ÷ 12(서울고법 2012나55770, 광주지법 2017나58303) — 여러 기간에 걸친 총액 항목에만, "
                                "수입 기간이 1년이 아니면 경고",
    }),
    OptionSpec("ii_cap_window", "income_overlap_days", "한도 산정 창", "II-06", {
        "income_overlap_days": "수입과 겹친 날의 임금으로 한도(2023가합203713, 2025나11545)",
        "whole_wage_period": "임금산정기간 전체 한도(조사자 원안)",
    }),
    OptionSpec("ii_period_anchor", "wage_period", "공제 비교 단위의 시작점", "II-06", {
        "wage_period": "임금산정기간",
        "income_start": "수입 시작일부터 1개월 단위(서울중앙지법 2019나79130, 2023가합11391)",
    }),
    OptionSpec("ii_headcount_basis", "prior_month_majority", "상시 4명 이하 판정", "II-08", {
        "prior_month_majority": "시행령 제7조의2 — 기간 시작일 전 1개월 중 5인 미만 일수가 절반 이상(일별 근사)",
        "reference_day": "기간 시작일 당일 값",
    }),
    OptionSpec("ii_apply_ordinary_wage_cap", False, "제46조 제1항 단서(통상임금 상한)", "II-05", {
        False: "적용 안 함(판례·행정해석 없음)",
        True: "H = min(H, 월 통상임금) — 1997. 3. 1. 이후 기간만",
    }),
    OptionSpec("ii_exclude_non_avg_items_from_cap", False, "평균임금 비산입 임금은 한도 없이 공제", "II-15", {
        False: "적용 안 함(대법원 판결 없음)",
        True: "limit = max(0, W_avg − H) + W_non",
    }),
    OptionSpec("ii_wage_basis_for_cap", "gross", "한도 계산의 W 기준", "II-13", {
        "gross": "세전(2021다279903)",
        "net_of_withholding": "원천징수 후(87다카2132, 서울중앙지법 2019나53961)",
    }),
    OptionSpec("ii_leave_allowance", "exclude_from_deduction", "연차휴가수당과 중간수입 공제", "DW-15", {
        "exclude_from_deduction": "공제 대상 아님(속초 각주 '공제가 될 여지가 없으나')",
        "include_as_claimed": "원고 청구대로 한도 적용 대상에 넣음(속초 2024가합30450 70% 청구)",
    }),
    OptionSpec("ii_post_deemed_employment_cap", None, "고용 의사표시 판결 확정일 이후 기간의 한도(판시 없음)", "II-07", {
        None: "미선택 — employment_deemed_date 가 있으면 오류",
        "apply": "제538조 제1항 임금으로 보아 한도 적용",
        "no_cap": "한도 없이 공제",
    }),
    OptionSpec("ii_business_income_basis", None, "사업소득 공제 기준(확인불가)", "II-10", {
        None: "미선택 — 사업소득이 있으면 오류",
        "net_of_expenses": "필요경비(business_expenses)를 뺀 소득금액",
        "gross": "수입금액 그대로",
    }),
]}

RULES: dict[str, tuple[str, str]] = {
    "DW-01": ("해고 무효 시 민법 제538조 제1항 임금 전부, 5인 미만은 무효 근거 입력", "판례확립"),
    "DW-02": ("근로기준법 제2조 임금 전부 포함, 시혜적 금품 제외", "판례확립"),
    "DW-03": ("항목별 분류(자녀학자금·보직수당은 심리 필요, 하급심 항목 분리)", "판례확립·하급심"),
    "DW-04": ("실비변상적 급여 제외, 경계는 요건 연동 기준", "판례확립·불명확"),
    "DW-05": ("계속 받았으리라 예상되는 시간외수당 포함, 산정 방식·증명책임", "판례확립·하급심"),
    "DW-06": ("단협 인상·자동승급·적정 등급 반영, 재량 승진 제외", "판례확립"),
    "DW-07": ("성과급 포함요건은 판례, 금액 추정은 하급심", "판례확립·하급심"),
    "DW-08": ("기준 월임금 산정 방식", "불명확"),
    "DW-09": ("기산일(효력발생일 당일/다음날), 해고 전 미지급 임금 구분", "실무관행"),
    "DW-10": ("종기: 복직일 전날·종료일·갱신 간주 만료일·복직명령(하급심)", "판례확립·하급심"),
    "DW-11": ("구속·수배·사업폐지·쟁의·유효 정직 기간 제외", "판례확립"),
    "DW-12": ("월 중도 일할 분모", "불명확"),
    "DW-13": ("단계별 끝수", "실무관행"),
    "DW-14": ("정기상여금 배분(연 ÷ 12 확인, 지급월 배분 확인불가)", "하급심·불명확"),
    "DW-15": ("해고기간 연차 출근 간주, 5인 미만 미적용, 미종료 연도 배척", "판례확립"),
    "DW-16": ("해고기간 계속근로기간 포함", "하급심"),
    "DW-17": ("중간수입은 휴업수당 초과분에서만 공제", "판례확립"),
    "DW-18": ("지연손해금 정보 전달(이율은 interest 모듈)", "판례확립·법령·불명확"),
    "DW-19": ("과거분 확정액과 장래분 월 금액, 기판력", "판례확립"),
    "DW-20": ("기지급액 법정충당, 세전/세후 기준", "법령·하급심"),
    "DW-21": ("노동위원회 금전보상 모드(5인 미만 불가)", "법령·실무관행"),
    "DW-M01": ("5인 미만 적용 제외 분기", "법령"),
    "DW-M02": ("임금 산정 사실 증명책임 근로자, 쟁의 참가 명백은 사용자", "판례확립"),
    "DW-M03": ("재량 승진 보수 증가 불포함", "판례확립"),
    "DW-M04": ("단협 부당징계 가산보상금 — 미구현", "판례확립"),
    "DW-M05": ("부당 정직·대기발령에도 같은 산정", "판례확립"),
    "DW-M06": ("해고 전 미지급 근로임금 별도 행", "하급심"),
    "DW-M07": ("수배·도피 기간 제외", "판례확립"),
    "DW-M08": ("소멸시효·시효중단 — 판정하지 않음", "판례확립"),
    "DW-M09": ("개정 제37조 제2항 기준일 — interest 모듈", "법령"),
    "DW-M10": ("소촉법 이율 경과규정 — interest 모듈", "하급심"),
    "DW-M11": ("원금·기지급액 세전/세후 옵션", "하급심"),
    "DW-M12": ("구제명령 임금상당액과 제36조·제37조 — claim_info 전달", "행정해석"),
    "II-01": ("상당인과관계 있는 이익만 공제, 귀속은 근로 대가 기간", "판례확립·하급심"),
    "II-02": ("limit = max(0, W − H), deduct = min(I, limit), 금지 산식 거부, 끝수 순서", "판례확립"),
    "II-03": ("휴업수당 율 60%(~1989. 3. 28.)/70%, 조문 연혁", "판례확립·법령"),
    "II-04": ("휴업수당 기초금액 A~E(기본값 없음), 통상임금 하한", "불명확"),
    "II-05": ("제46조 제1항 단서 적용(기본 미적용, 1997. 3. 1. 가드)", "불명확"),
    "II-06": ("시기적 대응 원칙, 대응 단위·일할·안분·한도 창", "판례확립·하급심"),
    "II-07": ("한도 적용 판단축: 제46조 휴업 해당성, 근로관계 해소 후 손해배상 여부", "판례확립·하급심"),
    "II-08": ("상시 4명 이하 한도 없음, 시행령 제7조의2 판정", "법령·하급심"),
    "II-09": ("노동위원회 금전보상에도 한도", "하급심"),
    "II-10": ("실업급여·연금·노조기금·전 사용자 예고수당 제외, 사업소득 기준 확인불가", "판례확립·하급심·불명확"),
    "II-11": ("기지급 휴직수당 실수령액 공제, 퇴직금은 자인 시만", "판례확립·하급심"),
    "II-12": ("사실심 미주장 수입 제외, 한도 없는 공제는 그 자체 자인 시만", "판례확립"),
    "II-13": ("인용액 세전, 한도 계산 W 기준 옵션", "판례확립·불명확"),
    "II-14": ("전액 지급 시 공제액 부당이득, 청구액 제한", "하급심"),
    "II-15": ("평균임금 비산입 임금 한도 제외(기본 미적용)", "불명확"),
    "II-M15": ("사용자 휴업(비해고) 기간 — 미구현", "행정해석"),
}


# ================================================================ 입력
@dataclass
class WageItem:
    name: str
    category: str = "fixed_allowance"
    monthly: Decimal | None = None
    annual: Decimal | None = None
    annual_rate: Decimal | None = None
    base_items: list = field(default_factory=list)
    history: tuple | None = None            # (합계, 개월 수)
    schedule: list = field(default_factory=list)   # [(month, rate, target_months)]
    overtime: dict | None = None
    start: date | None = None
    end: date | None = None
    include: bool | None = None
    periodic: bool = True
    discretionary: bool = False
    requirement_linked: bool = True
    uniform_payment: bool = False
    in_average_wage: bool = True
    rule_basis: bool | None = None
    regular: bool | None = None
    note: str = ""

    def active(self, d: date) -> bool:
        return (self.start is None or self.start <= d) and (self.end is None or d <= self.end)


@dataclass
class Raise:
    applies_from: date
    amount: Decimal | None = None
    rate: Decimal | None = None
    items: list = field(default_factory=list)
    kind: str = "cba"                       # cba | automatic_step | evaluation | promotion
    certain: bool = False
    note: str = ""


@dataclass
class Exclusion:
    start: date
    end: date | None
    reason: str
    convicted: bool | None = None
    note: str = ""


@dataclass
class InterimIncome:
    start: date
    end: date | None
    income_type: str
    amount: Decimal | None = None
    monthly_amount: Decimal | None = None
    raised_by: str = "employer"             # employer | worker_admitted | none
    admitted_without_cap: bool = False
    causal: bool | None = None
    assigned_period: str | None = None
    business_expenses: Decimal | None = None
    note: str = ""


@dataclass
class Payment:
    date: date
    amount: Decimal
    type: str = "back_pay"
    basis: str = "gross"
    worker_admits_offset: bool = False
    note: str = ""


@dataclass
class DismissalInput:
    claim_basis: str
    mode: str = "back_pay"
    discipline_type: str = "dismissal"
    invalidity_basis: str | None = None
    dismissal_date: date | None = None
    start_date: date | None = None
    paid_through_date: date | None = None
    reinstatement_date: date | None = None
    return_order: dict | None = None
    termination_date: date | None = None
    termination_cause: str | None = None
    renewal_expectation: bool = False
    renewed_term_end: date | None = None
    closing_date: date | None = None
    first_instance_closing_date: date | None = None
    past_until: date | None = None
    future_start_date: date | None = None
    dismissal_invalid_final: bool | None = None
    remedy_order: dict | None = None
    small_business: bool = False
    small_business_periods: list = field(default_factory=list)
    exclusions: list = field(default_factory=list)
    base_wage: dict = field(default_factory=dict)
    wage_items: list = field(default_factory=list)
    raises: list = field(default_factory=list)
    withholding_rate: Decimal | None = None
    payments: list = field(default_factory=list)
    interim_income: list = field(default_factory=list)
    interim_cap: dict = field(default_factory=dict)
    employer_claim_periods: list = field(default_factory=list)
    employment_deemed_date: date | None = None
    art46_suspension: bool | None = None
    damages_after_termination: bool | None = None
    refund_claimed_amount: Decimal | None = None
    labor_commission: dict | None = None
    pay_period_start_day: int = 1
    pay_day: int | None = None
    pay_month_offset: int = 0
    employer_merchant: bool | None = None
    worker_last_working_day: date | None = None   # worker.last_working_day(지연손해금 모듈이 마지막 근무일로 씀)


# ================================================================ 결과
@dataclass
class DismissalRow:
    """계산표 한 줄(임금산정기간). kind: pre_dismissal(해고 전 미지급 근로임금) | dismissal | future | labor_commission."""

    kind: str
    key: str
    label: str
    period_start: date
    period_end: date
    start: date
    end: date
    period_days: int
    covered_days: int
    excluded_days: int
    proration: str
    items: dict
    wage: Decimal
    deduction_base: Decimal          # 중간수입 공제 대상 임금(연차수당 제외 등 반영)
    small_business: bool | None
    rate: Decimal | None             # 휴업수당 율
    allowance: Decimal | None        # 한도 계산에 쓴 휴업수당 상당액(창 기준 합)
    limit: Decimal | None            # 공제 한도(창 기준 합)
    income: Decimal                  # 대응 중간수입(한도 적용분)
    income_uncapped: Decimal         # 대응 중간수입(한도 없는 공제 자인분)
    deduction: Decimal
    pay: Decimal                     # 세전 지급액
    pay_amount: Decimal              # 금액 기준(dw_amount_basis) 적용 후 청구 금액
    pay_date: date | None
    note: str = ""


@dataclass
class DismissalInstallment:
    label: str
    kind: str
    period_start: date
    period_end: date
    amount: Decimal
    regular_pay_date: date | None
    before_termination: bool | None


@dataclass
class DismissalClaimInfo:
    """지연손해금 모듈이 이율을 판단하는 데 필요한 사실(dismissal_interest_20.md)."""

    employment_status: str                  # continuing | reinstated | terminated
    reinstatement_date: date | None
    termination_date: date | None           # 근로관계가 실제로 끝난 날(갱신기대권이면 갱신 간주 만료일, DW-18)
    termination_cause: str | None
    settlement_deadline: date | None        # 종료일 + 14일(제36조)
    dismissal_invalid_final: bool | None
    remedy_order_issued: bool | None
    remedy_order_final: bool | None
    remedy_order_date: date | None
    employer_merchant: bool | None
    closing_date: date | None
    first_instance_closing_date: date | None
    future_start_date: date | None
    future_monthly_amount: Decimal | None
    future_end_date: date | None
    amount_basis: str
    interest_end_cause: str | None = None   # interest 절 end_cause 어휘(retirement|contract_end|resignation|redismissal|death|other)
    installments: list = field(default_factory=list)
    payments: list = field(default_factory=list)
    notes: list = field(default_factory=list)


@dataclass
class DismissalResult:
    rows: list
    total: Decimal
    claims: list
    trace: list
    warnings: list
    start_date: date | None = None
    end_date: date | None = None
    end_reason: str = ""
    past_end: date | None = None
    pre_dismissal_total: Decimal = ZERO
    dismissal_total: Decimal = ZERO
    wage_total: Decimal = ZERO
    interim_deduction_total: Decimal = ZERO
    future_start_date: date | None = None
    future_monthly_amount: Decimal | None = None
    future_row: DismissalRow | None = None
    deemed_attendance_periods: list = field(default_factory=list)
    continuous_service_periods: list = field(default_factory=list)
    claim_info: DismissalClaimInfo | None = None
    refund_amount: Decimal | None = None
    refund_awardable: Decimal | None = None
    labor_commission_amount: Decimal | None = None
    ignored_income: list = field(default_factory=list)


# ================================================================ 읽기
_KEYS = {
    "mode", "claim_basis", "discipline_type", "invalidity_basis", "dismissal_date", "start_date", "paid_through_date",
    "reinstatement_date", "return_order", "termination", "renewal_expectation", "renewed_term_end", "closing_date",
    "first_instance_closing_date", "past_until", "future_start_date", "dismissal_invalid_final", "remedy_order",
    "small_business", "exclusions", "base_wage", "wage_items", "raises", "withholding_rate", "payments",
    "interim_income", "interim_cap", "employer_claim_periods", "employment_deemed_date", "art46_suspension",
    "damages_after_termination", "deduction_formula", "refund_claimed_amount", "labor_commission",
}
_ITEM_KEYS = {
    "name", "category", "monthly", "annual", "annual_rate", "base_items", "history", "schedule", "overtime", "from",
    "to", "include", "periodic", "discretionary", "expense_reimbursement", "requirement_linked", "uniform_payment",
    "in_average_wage", "rule_basis", "regular", "method", "note", "obligation_source",
}
_INCOME_KEYS = {
    "start", "end", "type", "amount", "monthly_amount", "raised_by", "admitted_without_cap", "causal",
    "assigned_period", "business_expenses", "note",
}
_FORBIDDEN_FORMULAS = {
    "income_minus_allowance": "중간수입에서 휴업수당을 뺀 차액만 공제하는 산식은 대법원 2021다279903 에서 파기되었습니다",
    "zero_if_income_below_allowance": "중간수입이 휴업수당보다 적다는 이유로 공제를 배제하는 판단은 대법원 2014다65397 에서 파기되었습니다",
}


def _num(v, label: str, default=None) -> Decimal | None:
    if v is None or v == "":
        return default
    if isinstance(v, bool):
        raise LaborError(f"해고기간 임금: {label} 은(는) 숫자여야 합니다: {v!r}")
    try:
        return dec(v)
    except (InvalidOperation, ValueError, TypeError):
        raise LaborError(f"해고기간 임금: {label} 은(는) 숫자여야 합니다: {v!r}") from None


def _date(v, label: str) -> date | None:
    if v is None or v == "":
        return None
    try:
        return parse_date(v)
    except (ValueError, TypeError):
        raise LaborError(f"해고기간 임금: {label} 날짜 형식이 올바르지 않습니다: {v!r}") from None


def _bool(v, label: str, default=None):
    if v is None or v == "":
        return default
    if isinstance(v, bool):
        return v
    raise LaborError(f"해고기간 임금: {label} 은(는) true/false 여야 합니다: {v!r}")


def _dict(v, label: str, keys: set | None = None) -> dict:
    if v is None:
        return {}
    if not isinstance(v, dict):
        raise LaborError(f"해고기간 임금: {label} 은(는) 사전이어야 합니다")
    if keys is not None:
        unknown = set(v) - keys
        if unknown:
            raise LaborError(f"해고기간 임금: {label} 에 알 수 없는 키: {', '.join(sorted(map(str, unknown)))}")
    return v


def _choice(v, table, label: str, default=None):
    if v is None or v == "":
        return default
    if v not in table:
        raise LaborError(f"해고기간 임금: {label} 값 {v!r} 을 알 수 없습니다. 가능: {', '.join(table)}")
    return v


def _load_item(raw, label: str) -> WageItem:
    raw = _dict(raw, label, _ITEM_KEYS)
    name = raw.get("name")
    if not name:
        raise LaborError(f"해고기간 임금: {label} 에 name 이 없습니다")
    cat = _choice(raw.get("category"), ITEM_CATEGORIES, f"{label}.category", "fixed_allowance")
    hist = raw.get("history")
    history = None
    if hist is not None:
        if isinstance(hist, dict):
            if "total" not in hist or "months" not in hist:
                raise LaborError(f"해고기간 임금: {label}.history 에는 total 과 months 가 필요합니다")
            history = (_num(hist["total"], f"{label}.history.total"), int(hist["months"]))
        elif isinstance(hist, (list, tuple)) and hist:
            history = (sum((_num(x, f"{label}.history") for x in hist), ZERO), len(hist))
        else:
            raise LaborError(f"해고기간 임금: {label}.history 는 금액 목록 또는 {{total, months}} 여야 합니다")
        if history[1] <= 0:
            raise LaborError(f"해고기간 임금: {label}.history.months 는 1 이상이어야 합니다")
    schedule = []
    for i, s in enumerate(raw.get("schedule") or [], 1):
        s = _dict(s, f"{label}.schedule[{i}]", {"month", "rate", "target_months"})
        if "month" not in s or "rate" not in s:
            raise LaborError(f"해고기간 임금: {label}.schedule[{i}] 에 month 와 rate 가 필요합니다")
        m = int(s["month"])
        if not 1 <= m <= 12:
            raise LaborError(f"해고기간 임금: {label}.schedule[{i}].month 는 1~12 여야 합니다")
        schedule.append((m, _num(s["rate"], f"{label}.schedule[{i}].rate"), int(s.get("target_months") or 1)))
    ot = raw.get("overtime")
    if ot is not None:
        ot = _dict(ot, f"{label}.overtime", {"method", "hourly_wage", "hours", "premium", "amount"})
        method = _choice(ot.get("method"), {"pre_dismissal_avg_hours": 1, "peer_avg_hours": 1, "cba_cap_hours": 1,
                                             "fixed_amount": 1}, f"{label}.overtime.method", "pre_dismissal_avg_hours")
        ot = {
            "method": method,
            "hourly_wage": _num(ot.get("hourly_wage"), f"{label}.overtime.hourly_wage"),
            "hours": {k: _num(v, f"{label}.overtime.hours.{k}", ZERO)
                      for k, v in _dict(ot.get("hours"), f"{label}.overtime.hours", {"overtime", "night", "holiday"}).items()},
            "premium": {k: _num(v, f"{label}.overtime.premium.{k}")
                        for k, v in _dict(ot.get("premium"), f"{label}.overtime.premium", {"overtime", "night", "holiday"}).items()},
            "amount": _num(ot.get("amount"), f"{label}.overtime.amount"),
        }
        if ot["amount"] is None and (ot["hourly_wage"] is None or not ot["hours"]):
            raise LaborError(f"해고기간 임금: {label}.overtime 에는 amount 또는 hourly_wage 와 hours 가 필요합니다")
    item = WageItem(
        name=str(name), category=cat,
        monthly=_num(raw.get("monthly"), f"{label}.monthly"),
        annual=_num(raw.get("annual"), f"{label}.annual"),
        annual_rate=_num(raw.get("annual_rate"), f"{label}.annual_rate"),
        base_items=[str(x) for x in (raw.get("base_items") or [])],
        history=history, schedule=schedule, overtime=ot,
        start=_date(raw.get("from"), f"{label}.from"), end=_date(raw.get("to"), f"{label}.to"),
        include=_bool(raw.get("include"), f"{label}.include"),
        periodic=bool(_bool(raw.get("periodic"), f"{label}.periodic", True)),
        discretionary=bool(_bool(raw.get("discretionary"), f"{label}.discretionary", False)),
        requirement_linked=bool(_bool(raw.get("requirement_linked"), f"{label}.requirement_linked", True)),
        uniform_payment=bool(_bool(raw.get("uniform_payment"), f"{label}.uniform_payment", False)),
        in_average_wage=bool(_bool(raw.get("in_average_wage"), f"{label}.in_average_wage", True)),
        rule_basis=_bool(raw.get("rule_basis"), f"{label}.rule_basis"),
        regular=_bool(raw.get("regular"), f"{label}.regular"),
        note=str(raw.get("note") or ""),
    )
    if _bool(raw.get("expense_reimbursement"), f"{label}.expense_reimbursement", False):
        item.category = "expense"
    kinds = [k for k in ("monthly", "annual", "annual_rate", "history", "overtime") if getattr(item, k) is not None]
    if item.schedule and item.monthly is None and not item.base_items:
        raise LaborError(f"해고기간 임금: {label}.schedule 에는 기준액(monthly) 또는 base_items 가 필요합니다")
    if item.schedule:
        kinds = ["schedule"]
    if len(kinds) != 1:
        raise LaborError(f"해고기간 임금: {label}({name}) 에는 monthly·annual·annual_rate·history·schedule·overtime 중 "
                         f"하나만 적어야 합니다(적은 것: {', '.join(kinds) or '없음'})")
    if item.annual_rate is not None and not item.base_items:
        raise LaborError(f"해고기간 임금: {label}({name}) annual_rate 에는 base_items 가 필요합니다")
    if item.start and item.end and item.end < item.start:
        raise LaborError(f"해고기간 임금: {label}({name}) to 가 from 보다 앞섭니다")
    return item


def _load_income(raw, label: str) -> InterimIncome:
    raw = _dict(raw, label, _INCOME_KEYS)
    start = _date(raw.get("start"), f"{label}.start")
    if start is None:
        raise LaborError(f"해고기간 임금: {label} 에 수입 기간 시작일(start)이 없습니다")
    end = _date(raw.get("end"), f"{label}.end")
    if end is not None and end < start:
        raise LaborError(f"해고기간 임금: {label} end 가 start 보다 앞섭니다")
    if not raw.get("type"):
        raise LaborError(f"해고기간 임금: {label} 에 수입 종류(type)가 없습니다. 가능: {', '.join(INCOME_TYPES)}")
    inc = InterimIncome(
        start=start, end=end,
        income_type=_choice(raw.get("type"), INCOME_TYPES, f"{label}.type"),
        amount=_num(raw.get("amount"), f"{label}.amount"),
        monthly_amount=_num(raw.get("monthly_amount"), f"{label}.monthly_amount"),
        raised_by=_choice(raw.get("raised_by"), {"employer": 1, "worker_admitted": 1, "none": 1}, f"{label}.raised_by", "employer"),
        admitted_without_cap=bool(_bool(raw.get("admitted_without_cap"), f"{label}.admitted_without_cap", False)),
        causal=_bool(raw.get("causal"), f"{label}.causal"),
        assigned_period=str(raw["assigned_period"]) if raw.get("assigned_period") else None,
        business_expenses=_num(raw.get("business_expenses"), f"{label}.business_expenses"),
        note=str(raw.get("note") or ""),
    )
    if (inc.amount is None) == (inc.monthly_amount is None):
        raise LaborError(f"해고기간 임금: {label} 에는 amount(기간 총액)와 monthly_amount(월액) 중 하나만 적어야 합니다")
    if inc.amount is not None and inc.end is None:
        raise LaborError(f"해고기간 임금: {label} 총액(amount)을 적었으면 수입 기간 끝(end)이 필요합니다")
    if inc.admitted_without_cap and inc.raised_by != "worker_admitted":
        raise LaborError(f"해고기간 임금: {label} admitted_without_cap 은 raised_by: worker_admitted 일 때만 쓸 수 있습니다(II-12)")
    return inc


def _periods(raw, label: str) -> list:
    out = []
    for i, pr in enumerate(raw or [], 1):
        if not isinstance(pr, (list, tuple)) or len(pr) != 2:
            raise LaborError(f"해고기간 임금: {label}[{i}] 는 [시작, 끝] 이어야 합니다")
        s, e = _date(pr[0], f"{label}[{i}]"), _date(pr[1], f"{label}[{i}]")
        if s is None or e is None:
            raise LaborError(f"해고기간 임금: {label}[{i}] 는 시작과 끝 날짜를 모두 적어야 합니다 — 끝이 열려 있으면"
                             "(예: '2019. 1. 14.부터 계속') 청구 기간 마지막 날(과거분 마감일·변론종결일)을 적으십시오")
        if e < s:
            raise LaborError(f"해고기간 임금: {label}[{i}] 의 끝 {_fmt(e)} 이 시작 {_fmt(s)} 보다 앞섭니다")
        out.append((s, e))
    return out


def _service_days(v) -> int:
    """노동위원회 금전보상 송달기간 일수(DW-21). 비우면 30일."""
    if v is None or v == "":
        return 30
    bad = LaborError(f"해고기간 임금: labor_commission.service_days 는 정수(일수)여야 합니다: {v!r}")
    if isinstance(v, bool) or (isinstance(v, float) and not v.is_integer()):
        raise bad
    try:
        n = int(v.strip()) if isinstance(v, str) else int(v)
    except (TypeError, ValueError):
        raise bad from None
    if n < 0:
        raise LaborError(f"해고기간 임금: labor_commission.service_days 는 0 이상이어야 합니다: {v!r}")
    return n


def load_dismissal(raw: dict, worker: dict | None = None) -> DismissalInput:
    """사건.yaml `dismissal:` 절(dict)과 `worker:` 절을 읽는다."""
    raw = dict(raw or {})
    worker = dict(worker or {})
    unknown = set(raw) - _KEYS
    if unknown:
        raise LaborError(f"해고기간 임금: dismissal 절에 알 수 없는 키: {', '.join(sorted(unknown))}")
    formula = raw.get("deduction_formula") or "standard"
    if formula in _FORBIDDEN_FORMULAS:
        raise LaborError("해고기간 임금: " + _FORBIDDEN_FORMULAS[formula] + " — deduction_formula 는 standard 만 받습니다(II-02)")
    if formula != "standard":
        raise LaborError(f"해고기간 임금: deduction_formula 값 {formula!r} 을 알 수 없습니다(standard 만 가능)")
    mode = _choice(raw.get("mode"), {"back_pay": 1, "refund": 1, "labor_commission_award": 1}, "mode", "back_pay")
    basis = raw.get("claim_basis")
    if not basis:
        if mode == "labor_commission_award":
            basis = "labor_commission_monetary_compensation"
        else:
            raise LaborError("해고기간 임금: 청구원인(claim_basis)이 없습니다 — 휴업수당 한도 적용 여부가 이것으로 갈립니다"
                             f"(II-07). 가능: {', '.join(CLAIM_BASES)}")
    basis = _choice(basis, CLAIM_BASES, "claim_basis")

    term = _dict(raw.get("termination"), "termination", {"date", "cause"})
    t_date = _date(term.get("date"), "termination.date")
    t_cause = _choice(term.get("cause"), TERMINATION_CAUSES, "termination.cause")
    if (t_date is None) != (t_cause is None):
        raise LaborError("해고기간 임금: termination 에는 date 와 cause 를 함께 적어야 합니다")

    ro = _dict(raw.get("return_order"), "return_order", {"date", "effective_date", "genuine", "refused"})
    return_order = None
    if ro:
        return_order = {"date": _date(ro.get("date"), "return_order.date"),
                        "effective_date": _date(ro.get("effective_date"), "return_order.effective_date"),
                        "genuine": _bool(ro.get("genuine"), "return_order.genuine"),
                        "refused": _bool(ro.get("refused"), "return_order.refused")}
        if return_order["effective_date"] is None:
            raise LaborError("해고기간 임금: return_order.effective_date(복직하라고 한 날)가 없습니다")
    rem = _dict(raw.get("remedy_order"), "remedy_order", {"issued", "final", "date"})
    remedy = {"issued": _bool(rem.get("issued"), "remedy_order.issued"), "final": _bool(rem.get("final"), "remedy_order.final"),
              "date": _date(rem.get("date"), "remedy_order.date")} if rem else None

    exclusions = []
    for i, e in enumerate(raw.get("exclusions") or [], 1):
        e = _dict(e, f"exclusions[{i}]", {"start", "end", "reason", "convicted", "note"})
        s = _date(e.get("start"), f"exclusions[{i}].start")
        if s is None or not e.get("reason"):
            raise LaborError(f"해고기간 임금: exclusions[{i}] 에 start 와 reason 이 필요합니다")
        en = _date(e.get("end"), f"exclusions[{i}].end")
        if en is not None and en < s:
            raise LaborError(f"해고기간 임금: exclusions[{i}] end 가 start 보다 앞섭니다")
        exclusions.append(Exclusion(s, en, _choice(e.get("reason"), EXCLUSION_REASONS, f"exclusions[{i}].reason"),
                                    _bool(e.get("convicted"), f"exclusions[{i}].convicted"), str(e.get("note") or "")))

    bw = _dict(raw.get("base_wage"), "base_wage", {"three_month_total", "three_month_days", "avg_daily_wage", "ordinary_monthly_wage"})
    base_wage = {k: _num(bw.get(k), f"base_wage.{k}") for k in ("three_month_total", "three_month_days", "avg_daily_wage",
                                                                "ordinary_monthly_wage")}
    items = [_load_item(it, f"wage_items[{i}]") for i, it in enumerate(raw.get("wage_items") or [], 1)]
    names = [it.name for it in items]
    if len(set(names)) != len(names):
        raise LaborError("해고기간 임금: wage_items 에 같은 name 이 두 번 있습니다")
    for it in items:
        for b in it.base_items:
            if b not in names:
                raise LaborError(f"해고기간 임금: {it.name} 의 base_items {b!r} 가 wage_items 에 없습니다")

    raises = []
    for i, r in enumerate(raw.get("raises") or [], 1):
        r = _dict(r, f"raises[{i}]", {"applies_from", "agreed_date", "amount", "rate", "items", "kind", "certain", "note"})
        af = _date(r.get("applies_from"), f"raises[{i}].applies_from")
        if af is None:
            raise LaborError(f"해고기간 임금: raises[{i}] 에 적용 개시일(applies_from, 소급 적용일)이 없습니다(DW-06)")
        rs = Raise(af, _num(r.get("amount"), f"raises[{i}].amount"), _num(r.get("rate"), f"raises[{i}].rate"),
                   [str(x) for x in (r.get("items") or [])],
                   _choice(r.get("kind"), {"cba": 1, "automatic_step": 1, "evaluation": 1, "promotion": 1}, f"raises[{i}].kind", "cba"),
                   bool(_bool(r.get("certain"), f"raises[{i}].certain", False)), str(r.get("note") or ""))
        if (rs.amount is None) == (rs.rate is None):
            raise LaborError(f"해고기간 임금: raises[{i}] 에는 amount 와 rate 중 하나만 적어야 합니다")
        for n in rs.items:
            if n not in names:
                raise LaborError(f"해고기간 임금: raises[{i}].items 의 {n!r} 가 wage_items 에 없습니다")
        raises.append(rs)
    raises.sort(key=lambda r: r.applies_from)

    payments = []
    for i, p in enumerate(raw.get("payments") or [], 1):
        p = _dict(p, f"payments[{i}]", {"date", "amount", "type", "basis", "worker_admits_offset", "note"})
        pd_ = _date(p.get("date"), f"payments[{i}].date")
        amt = _num(p.get("amount"), f"payments[{i}].amount")
        if pd_ is None or amt is None:
            raise LaborError(f"해고기간 임금: payments[{i}] 에 date 와 amount 가 필요합니다")
        payments.append(Payment(pd_, amt, _choice(p.get("type"), PAYMENT_TYPES, f"payments[{i}].type", "back_pay"),
                                _choice(p.get("basis"), {"gross": 1, "net": 1}, f"payments[{i}].basis", "gross"),
                                bool(_bool(p.get("worker_admits_offset"), f"payments[{i}].worker_admits_offset", False)),
                                str(p.get("note") or "")))

    cap = _dict(raw.get("interim_cap"), "interim_cap", {"avg_daily_wage", "avg_monthly_wage", "ordinary_monthly_wage",
                                                        "pre_dismissal_wages"})
    interim_cap = {k: _num(cap.get(k), f"interim_cap.{k}") for k in ("avg_daily_wage", "avg_monthly_wage", "ordinary_monthly_wage")}
    interim_cap["pre_dismissal_wages"] = {str(k): _num(v, f"interim_cap.pre_dismissal_wages.{k}")
                                          for k, v in _dict(cap.get("pre_dismissal_wages"), "interim_cap.pre_dismissal_wages").items()}

    lc = raw.get("labor_commission")
    if lc is not None:
        lc = _dict(lc, "labor_commission", {"monthly_wage", "decision_date", "service_days"})
        lc = {"monthly_wage": _num(lc.get("monthly_wage"), "labor_commission.monthly_wage"),
              "decision_date": _date(lc.get("decision_date"), "labor_commission.decision_date"),
              "service_days": _service_days(lc.get("service_days"))}
    if mode == "labor_commission_award" and (lc is None or lc["monthly_wage"] is None or lc["decision_date"] is None):
        raise LaborError("해고기간 임금: 노동위원회 금전보상 모드에는 labor_commission.monthly_wage 와 decision_date 가 필요합니다")

    sbp = [(_date(s, "worker.small_business_periods"), _date(e, "worker.small_business_periods"))
           for s, e in worker.get("small_business_periods") or []]
    try:
        start_day = int(worker.get("pay_period_start_day") or 1)
        pay_day = worker.get("pay_day")
        pay_day = None if pay_day in (None, "") else int(pay_day)
        offset = int(worker.get("pay_month_offset") or 0)
    except (TypeError, ValueError):
        raise LaborError("해고기간 임금: worker.pay_period_start_day·pay_day·pay_month_offset 은 정수여야 합니다") from None
    if pay_day is not None and not 1 <= pay_day <= 31:
        raise LaborError(f"해고기간 임금: worker.pay_day 는 1~31 이어야 합니다: {pay_day}")

    inp = DismissalInput(
        claim_basis=basis, mode=mode,
        discipline_type=_choice(raw.get("discipline_type"), {"dismissal": 1, "suspension": 1, "standby": 1, "transfer": 1},
                                "discipline_type", "dismissal"),
        invalidity_basis=_choice(raw.get("invalidity_basis"), {"lsa_23": 1, "cba_rules": 1, "procedure": 1, "other": 1},
                                 "invalidity_basis"),
        dismissal_date=_date(raw.get("dismissal_date"), "dismissal_date"),
        start_date=_date(raw.get("start_date"), "start_date"),
        paid_through_date=_date(raw.get("paid_through_date"), "paid_through_date"),
        reinstatement_date=_date(raw.get("reinstatement_date"), "reinstatement_date"),
        return_order=return_order, termination_date=t_date, termination_cause=t_cause,
        renewal_expectation=bool(_bool(raw.get("renewal_expectation"), "renewal_expectation", False)),
        renewed_term_end=_date(raw.get("renewed_term_end"), "renewed_term_end"),
        closing_date=_date(raw.get("closing_date"), "closing_date"),
        first_instance_closing_date=_date(raw.get("first_instance_closing_date"), "first_instance_closing_date"),
        past_until=_date(raw.get("past_until"), "past_until"),
        future_start_date=_date(raw.get("future_start_date"), "future_start_date"),
        dismissal_invalid_final=_bool(raw.get("dismissal_invalid_final"), "dismissal_invalid_final"),
        remedy_order=remedy,
        small_business=bool(_bool(raw.get("small_business"), "small_business", False)),
        small_business_periods=sbp, exclusions=exclusions, base_wage=base_wage, wage_items=items, raises=raises,
        withholding_rate=_num(raw.get("withholding_rate"), "withholding_rate"), payments=payments,
        interim_income=[_load_income(x, f"interim_income[{i}]") for i, x in enumerate(raw.get("interim_income") or [], 1)],
        interim_cap=interim_cap, employer_claim_periods=_periods(raw.get("employer_claim_periods"), "employer_claim_periods"),
        employment_deemed_date=_date(raw.get("employment_deemed_date"), "employment_deemed_date"),
        art46_suspension=_bool(raw.get("art46_suspension"), "art46_suspension"),
        damages_after_termination=_bool(raw.get("damages_after_termination"), "damages_after_termination"),
        refund_claimed_amount=_num(raw.get("refund_claimed_amount"), "refund_claimed_amount"),
        labor_commission=lc, pay_period_start_day=start_day, pay_day=pay_day, pay_month_offset=offset,
        employer_merchant=_bool(worker.get("employer_merchant"), "worker.employer_merchant"),
        worker_last_working_day=_date(worker.get("last_working_day"), "worker.last_working_day"),
    )
    if inp.dismissal_date is None and inp.start_date is None:
        raise LaborError("해고기간 임금: 해고 효력발생일(dismissal_date) 또는 기산일(start_date)이 없습니다")
    if inp.renewal_expectation and inp.termination_cause not in (None, "contract_end"):
        raise LaborError("해고기간 임금: renewal_expectation 은 계약만료(termination.cause: contract_end) 사안에만 씁니다")
    return inp


# ================================================================ 헬퍼
def _settle(x: Decimal) -> Decimal:
    """Decimal 나눗셈의 순환소수 오차 보정(소수 10자리 반올림). 끝수처리 직전에만 쓴다."""
    return Decimal(x).quantize(Decimal("1e-10"), rounding=ROUND_HALF_UP)


def _r(x, mode: str) -> Decimal:
    """금액 끝수. 금액은 음수가 아니라고 보고 floor 는 0 방향으로 끊는다."""
    v = _settle(Decimal(x))
    if mode == "floor":
        return v.quantize(ONE, rounding=ROUND_DOWN)
    if mode == "half_up":
        return v.quantize(ONE, rounding=ROUND_HALF_UP)
    if mode == "ceil10":
        return (v / 10).quantize(ONE, rounding=ROUND_CEILING) * 10
    if mode == "round10_half_up":
        return (v / 10).quantize(ONE, rounding=ROUND_HALF_UP) * 10
    if mode == "keep_2dp":
        return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if mode == "none":
        return v
    raise LaborError(f"해고기간 임금: 끝수처리 방식을 알 수 없습니다: {mode}")


def _fmt(d: date | None) -> str:
    return "" if d is None else f"{d.year}. {d.month}. {d.day}."


def _days(s: date, e: date) -> set:
    if e < s:
        return set()
    a = s.toordinal()
    return set(range(a, e.toordinal() + 1))


def _runs(ords: set) -> list:
    """정수 날짜 집합을 연속 구간 [(시작, 끝)] 으로."""
    out = []
    for o in sorted(ords):
        if out and out[-1][1] == o - 1:
            out[-1][1] = o
        else:
            out.append([o, o])
    return [(date.fromordinal(a), date.fromordinal(b)) for a, b in out]


def allocate_payment(principal: Decimal, accrued_interest: Decimal, payment: Decimal) -> dict:
    """민법 제479조 제1항 법정충당 — 이자(지연손해금)에 먼저, 나머지를 원본에(DW-20).

    2018가합52160 "피고가 변제한 위 14,350,000원 중 363,464원은 … 지연손해금의 변제에 우선 충당하고, 남은 금액
    13,986,536원 … 을 위 임금의 변제에 충당". 비용은 입력받지 않는다.
    """
    principal, accrued_interest, payment = dec(principal), dec(accrued_interest), dec(payment)
    to_interest = min(payment, accrued_interest)
    to_principal = min(payment - to_interest, principal)
    return {"to_interest": to_interest, "to_principal": to_principal,
            "remaining_interest": accrued_interest - to_interest, "remaining_principal": principal - to_principal,
            "surplus": payment - to_interest - to_principal}


def labor_commission_award_amount(monthly_wage: Decimal, start: date, decision_date: date,
                                  service_days: int = 30) -> tuple[Decimal, int, Decimal]:
    """노동위원회 금전보상 실무 산식(DW-21): (일액, 일수, 금액). 일액 = floor(월급 × 12 ÷ 365)."""
    daily = _r(dec(monthly_wage) * 12 / 365, "floor")
    n = days_inclusive(start, decision_date) + int(service_days)
    return daily, n, daily * n


def _read_options(opts: dict | None) -> dict:
    opts = opts or {}
    out = {}
    for key, spec in OPTIONS.items():
        v = opts.get(key, spec.default)
        if spec.choices and v not in spec.choices:
            raise LaborError(f"옵션 {key} 의 값 {v!r} 은 허용되지 않습니다. 가능: {', '.join(map(str, spec.choices))}")
        out[key] = v
    return out


# ================================================================ 계산 문맥
@dataclass
class _Full:
    """임금산정기간 1개월 전체 임금(일할 전)."""

    items: dict
    avg: Decimal          # 평균임금 산입 임금(연차 제외)
    non_avg: Decimal      # 평균임금 비산입 임금
    leave: Decimal        # 연차휴가수당
    daily: Decimal | None = None

    @property
    def total(self) -> Decimal:
        return self.avg + self.non_avg + self.leave


class _Ctx:
    def __init__(self, inp: DismissalInput, o: dict, deps: dict):
        self.inp = inp
        self.o = o
        self.deps = deps
        self.trace: list[Trace] = []
        self.warnings: list[str] = []
        self.ignored: list[str] = []
        self._full_cache: dict = {}
        self.daily_rate: Decimal | None = None
        self.base_monthly: Decimal | None = None
        self.included: dict = {}
        self.by_name = {it.name: it for it in inp.wage_items}
        self.avg_cache: dict = {}
        fn = deps.get("small_business")
        sources = []
        if fn is not None:
            sources.append(lambda d: bool(fn(d)))
        if inp.small_business_periods:
            sources.append(lambda d: is_within(d, inp.small_business_periods))
        if inp.small_business:
            sources.append(lambda d: True)
        self.small_fn = (lambda d: any(s(d) for s in sources)) if sources else None

    def warn(self, msg: str) -> None:
        if msg not in self.warnings:
            self.warnings.append(msg)

    def small(self, d: date) -> bool:
        return bool(self.small_fn and self.small_fn(d))

    def prorate(self, amount: Decimal, days: int, period_days: int, mode: str | None = None) -> Decimal:
        """월 금액을 days/period_days 로 일할(DW-12). 전부이면 그대로."""
        if days >= period_days:
            return amount
        if days <= 0:
            return ZERO
        den = 30 if self.o["dw_proration"] == "fixed_30" else period_days
        return min(amount, _r(amount * days / den, mode or self.o["dw_proration_rounding"]))

    def slice_at(self, d: date) -> PaySlice:
        return pay_periods(d, d, self.inp.pay_period_start_day)[0]


# ================================================================ 임금 항목
def _include_item(it: WageItem, ctx: _Ctx) -> bool:
    if it.name in ctx.included:
        return ctx.included[it.name]
    o = ctx.o
    label = f"임금 항목 {it.name}"
    inc, why, rule = True, ITEM_CATEGORIES[it.category], "DW-03"
    if it.include is not None:
        inc, why = it.include, f"사람이 판단(include: {it.include})"
    elif it.category in ("child_education", "position_allowance"):
        raise LaborError(f"해고기간 임금: {label} 은(는) {ITEM_CATEGORIES[it.category]} — include 를 사람이 적어야 합니다")
    elif it.category == "discretionary":
        inc, why, rule = False, "시혜적 금품 — 제외(2010다105815)", "DW-02"
    elif it.category == "expense":
        rule = "DW-04"
        if o["dw_expense_test"] == "requirement_linked":
            inc = not it.requirement_linked
            why = ("지급요건이 비용·업무행위에 연동 — 해고기간에는 요건 행위가 없어 제외(2011다42324)" if not inc
                   else "지급요건이 비용·업무행위와 무관 — 포함")
        else:
            inc = it.uniform_payment
            why = "일률 지급이면 포함(하급심 옵션)" if inc else "일률 지급 아님 — 제외"
        ctx.warn(f"{label}: 실비변상 경계 판단(DW-04)은 불명확합니다(2011다42324 와 하급심 대립)")
    elif not it.periodic:
        inc, why, rule = False, "계속적·정기적 지급이 아님 — 제외(90다카25277 입시수당)", "DW-02"
    elif it.category == "overtime":
        rule = "DW-05"
        if not it.regular:
            inc, why = False, "해고가 없었다면 계속 받았으리라 예상된다는 사정(regular: true)이 없음 — 제외(2019가단5138071)"
        else:
            why = "계속 받았으리라 예상되는 시간외수당 — 포함(92다39860, 93다11463)"
            method = (it.overtime or {}).get("method")
            if method in ("peer_avg_hours", "cba_cap_hours"):
                ctx.warn(f"{label}: 동료 근로자의 실제 연장근로 사실은 근로자에게 증명책임이 있습니다(94다25889)")
    elif it.category == "performance_bonus":
        rule = "DW-07"
        if not it.rule_basis:
            inc, why = False, "규정상 지급사유·기준(rule_basis: true)이 없음 — 제외(2011다42324)"
        else:
            why = "규정에 지급사유·기준이 있고 정기·계속 지급 — 포함(2011다42324)"
            ctx.warn(f"{label}: 성과급 금액 추정 방식은 하급심(인천지법 2021나70304, 검증 재열람 못함)입니다")
    elif it.category == "long_service_award":
        ctx.warn(f"{label}: 장기근속 포상의 임금성은 하급심(서울고법 2014나16809) 판단입니다")
    ctx.included[it.name] = inc
    ctx.trace.append(Trace(rule, label, "포함" if inc else "제외", why))
    return inc


def _raised(it: WageItem, value: Decimal, d: date, ctx: _Ctx) -> Decimal:
    if ctx.o["dw_base_wage_method"] == "last_month":
        return value
    for r in ctx.inp.raises:
        targets = r.items or [x.name for x in ctx.inp.wage_items if x.category in ("base", "fixed_allowance")
                              and (x.monthly is not None or x.history is not None)]
        if it.name not in targets or r.applies_from > d:
            continue
        if r.kind == "promotion" and not r.certain:
            continue
        if r.amount is not None:
            value += r.amount
        else:
            value = _r(value * (ONE + r.rate), ctx.o["dw_raise_rounding"])
    return value


def _item_amount(it: WageItem, d: date, ctx: _Ctx, memo: dict) -> Decimal:
    """d 가 속한 임금산정기간 1개월분 금액(일할 전). 지급월 배분 상여는 0(행에서 따로 계산)."""
    if it.name in memo:
        return memo[it.name]
    o = ctx.o
    val = ZERO
    if it.active(d):
        if it.monthly is not None and not it.schedule:
            val = _raised(it, it.monthly, d, ctx)
        elif it.history is not None:
            total, months = it.history
            val = _raised(it, _r(total / months, o["dw_monthly_avg_rounding"]), d, ctx)
        elif it.annual is not None:
            val = _r(it.annual / 12, o["dw_bonus_monthly_rounding"])
        elif it.annual_rate is not None:
            base = sum((_item_amount(ctx.by_name[b], d, ctx, memo) for b in it.base_items), ZERO)
            val = _r(base * it.annual_rate / 12, o["dw_bonus_monthly_rounding"])
        elif it.schedule:
            if o["dw_bonus_allocation"] == "annual_div_12":
                base = _schedule_base(it, d, ctx, memo)
                val = _r(base * sum((s[1] for s in it.schedule), ZERO) / 12, o["dw_bonus_monthly_rounding"])
        elif it.overtime is not None:
            val = _overtime_amount(it, d, ctx)
    memo[it.name] = val
    return val


def _schedule_base(it: WageItem, d: date, ctx: _Ctx, memo: dict) -> Decimal:
    if it.base_items:
        return sum((_item_amount(ctx.by_name[b], d, ctx, memo) for b in it.base_items), ZERO)
    return _raised(it, it.monthly, d, ctx)


def _overtime_amount(it: WageItem, d: date, ctx: _Ctx) -> Decimal:
    ot = it.overtime
    if ot["amount"] is not None:
        return ot["amount"]
    small = ctx.small(d)
    default = {"overtime": Decimal("1.5"), "night": Decimal("0.5"), "holiday": Decimal("1.5")}
    if small:
        default = {"overtime": ONE, "night": ZERO, "holiday": ONE}
        ctx.warn(f"임금 항목 {it.name}: 상시 4명 이하 기간에는 제56조 가산이 없어 연장·휴일 1.0배, 야간 가산 0 으로 계산했습니다"
                 "(약정 가산이 있으면 premium 에 직접 적을 것)")
    total = ZERO
    for k, h in ot["hours"].items():
        factor = ot["premium"].get(k) if ot["premium"].get(k) is not None else default[k]
        total += h * ot["hourly_wage"] * factor
    return _r(total, "floor")


def _full_wage(ps: date, ctx: _Ctx) -> _Full:
    """ps 로 시작하는 임금산정기간 1개월 전체 임금."""
    if ps in ctx._full_cache:
        return ctx._full_cache[ps]
    o = ctx.o
    method = o["dw_base_wage_method"]
    sl = ctx.slice_at(ps)
    if method == "avg_daily_3m":
        full = _Full({"평균임금 일액": ctx.daily_rate}, ctx.daily_rate * sl.period_days, ZERO, ZERO, daily=ctx.daily_rate)
    elif method == "avg_monthly_3m_ordinary_floor":
        full = _Full({"기준 월임금": ctx.base_monthly}, ctx.base_monthly, ZERO, ZERO)
    else:
        memo: dict = {}
        items, avg, non, leave = {}, ZERO, ZERO, ZERO
        closing = ctx.inp.closing_date
        for it in ctx.inp.wage_items:
            if not _include_item(it, ctx):
                continue
            amt = _item_amount(it, ps, ctx, memo)
            if it.category == "leave_allowance" and amt:
                if ctx.small(ps):
                    ctx.warn(f"임금 항목 {it.name}: 상시 4명 이하 기간에는 제60조가 적용되지 않아 연차휴가수당을 0 으로 했습니다(DW-15)")
                    amt = ZERO
                elif (closing is not None and not o["dw_future_leave_claim"] and ps.year >= closing.year
                      and closing < date(closing.year, 12, 31)):
                    ctx.warn(f"임금 항목 {it.name}: 변론종결일 {_fmt(closing)} 현재 끝나지 않은 {ps.year}년 연차휴가수당은 넣지 않았습니다"
                             "(속초 2024가합30450, dw_future_leave_claim)")
                    amt = ZERO
            if not amt:
                continue
            items[it.name] = amt
            if it.category == "leave_allowance":
                leave += amt
            elif it.in_average_wage:
                avg += amt
            else:
                non += amt
        full = _Full(items, avg, non, leave)
    ctx._full_cache[ps] = full
    return full


def _payment_month_bonus(sl: PaySlice, span: set, ctx: _Ctx) -> tuple[dict, Decimal, Decimal, list]:
    """지급월 배분 상여(DW-14 payment_month). (항목, 평균임금 산입분, 비산입분, 비고)."""
    items, avg, non, notes = {}, ZERO, ZERO, []
    if ctx.o["dw_bonus_allocation"] != "payment_month":
        return items, avg, non, notes
    for it in ctx.inp.wage_items:
        if not it.schedule or not _include_item(it, ctx) or not it.active(sl.period_start):
            continue
        for month, rate, target in it.schedule:
            if sl.period_end.month != month:
                continue
            ts = add_months(sl.period_start, -(target - 1))
            ts = ctx.slice_at(ts).period_start
            tdays = _days(ts, sl.period_end)
            covered = len(tdays & span)
            if not covered:
                continue
            base = _schedule_base(it, sl.period_start, ctx, {})
            full_amt = base * rate
            if covered >= len(tdays):
                amt = _r(full_amt, ctx.o["dw_proration_rounding"])
            else:
                amt = _r(full_amt * covered / len(tdays), ctx.o["dw_proration_rounding"])
                notes.append(f"{it.name} 지급대상기간 {_fmt(ts)}~{_fmt(sl.period_end)} 중 {covered}일/{len(tdays)}일")
            items[it.name] = items.get(it.name, ZERO) + amt
            if it.in_average_wage:
                avg += amt
            else:
                non += amt
    return items, avg, non, notes


# ================================================================ 기간
def _end_candidates(inp: DismissalInput, ctx: _Ctx) -> list:
    c = []
    if inp.reinstatement_date is not None:
        c.append((inp.reinstatement_date - timedelta(days=1), f"복직일 {_fmt(inp.reinstatement_date)} 전날(2014나16809)", "DW-10"))
    if inp.termination_date is not None:
        if inp.termination_cause == "contract_end" and inp.renewal_expectation:
            if inp.renewed_term_end is not None:
                c.append((inp.renewed_term_end, f"갱신기대권 — 갱신 간주된 계약기간 만료일(2007두1729)", "DW-10"))
            else:
                ctx.warn("갱신기대권이 인정되는데 갱신 간주 계약기간 만료일(renewed_term_end)이 없어 계약만료일을 종기로 쓰지 않았고, "
                         "근로관계가 계속된 것으로 보아 지연손해금 모듈에 종료일을 넘기지 않았습니다")
        else:
            c.append((inp.termination_date, f"근로관계 종료일({TERMINATION_CAUSES[inp.termination_cause]})", "DW-10"))
    ro = inp.return_order
    if ro is not None:
        if ctx.o["dw_return_order_end"] == "apply" and ro["genuine"] and ro["refused"]:
            c.append((ro["effective_date"] - timedelta(days=1), "정당한 복직명령 불응 — 복직일 전날(서울중앙지법 2018나34536, 하급심)",
                      "DW-10"))
            ctx.warn("복직명령 불응을 종기로 삼았습니다 — 복직명령의 진정성(임금상당액 미지급 상태 등, 속초 2024가합30450)은 사람이 판단한 값입니다")
        elif ro["genuine"] is None or ro["refused"] is None:
            ctx.warn("return_order 의 genuine·refused 가 비어 있어 복직명령을 종기로 쓰지 않았습니다")
    return c


def _exclusion_days(inp: DismissalInput, ctx: _Ctx, last: date) -> set:
    out = set()
    for e in inp.exclusions:
        end = e.end or last
        out |= _days(e.start, end)
        ctx.trace.append(Trace("DW-11", f"제외기간 {_fmt(e.start)}~{_fmt(e.end) or '종기'}", EXCLUSION_REASONS[e.reason], e.note))
        if e.reason == "detention" and not e.convicted:
            ctx.warn(f"제외기간 {_fmt(e.start)}~: 구속 제외는 징역형 선고 + 상당기간 구속 사안(94다40987)입니다 — 무죄·단기 구금이면 확인 필요")
        if e.reason == "strike":
            ctx.warn("쟁의행위 참가 명백 제외(2010다99279)는 사용자 증명책임이며, 쟁의기간 임금 지급 규정·관행을 고려해야 합니다")
        if e.reason == "incapacity":
            ctx.warn("질병 등 근로 불능 제외는 하급심 스니펫만 확인된 사유입니다")
    return out


# ================================================================ 중간수입
@dataclass
class _Window:
    row: int                  # 공제액을 넣을 행 번호
    days: set
    period_start: date        # 1개월 금액을 정하는 임금산정기간(또는 수입 기준 창) 시작일
    period_days: int
    whole: bool               # 행의 계산 대상 날짜 전체와 같은 창
    ref: date                 # 상시 근로자 수 판정 기준일
    assigned: bool = False
    incomes: dict = field(default_factory=dict)   # 수입 index -> 금액


def _deductible_incomes(inp: DismissalInput, ctx: _Ctx, claim_days: set, future: bool = False) -> list:
    """[(index, income, 공제 대상 날짜 집합, 사업소득 조정 총액)]"""
    o = ctx.o
    out = []
    employer_days = None
    if inp.employer_claim_periods:
        employer_days = set()
        for s, e in inp.employer_claim_periods:
            employer_days |= _days(s, e)
    for idx, inc in enumerate(inp.interim_income):
        label = f"중간수입[{idx + 1}] {_fmt(inc.start)}~{_fmt(inc.end)} {INCOME_TYPES[inc.income_type][0]}"
        treat = INCOME_TYPES[inc.income_type][1]
        if future and (inc.end is not None or inc.monthly_amount is None):
            continue
        if treat == "never":
            if not future:
                ctx.ignored.append(f"{label}: 공제 대상 아님(II-10)")
                ctx.trace.append(Trace("II-10", label, "공제 안 함", INCOME_TYPES[inc.income_type][0]))
            continue
        if treat == "causal_required" and inc.causal is not True:
            if not future:
                ctx.ignored.append(f"{label}: 상당인과관계(causal: true) 판단이 없어 공제하지 않음(II-01)")
            continue
        if inc.causal is False:
            if not future:
                ctx.ignored.append(f"{label}: causal: false — 공제하지 않음(II-01)")
            continue
        if inc.raised_by == "none":
            if not future:
                ctx.ignored.append(f"{label}: 사실심에서 주장되지 않은 수입 — 공제하지 않음(II-12, 93다37915)")
            continue
        amount = inc.amount
        monthly = inc.monthly_amount
        if treat == "business":
            basis = o["ii_business_income_basis"]
            if basis is None:
                raise LaborError("해고기간 임금: 사업소득 중간수입이 있으면 옵션 ii_business_income_basis(net_of_expenses | gross)를 "
                                 "사람이 정해야 합니다(II-10c 확인불가)")
            if basis == "net_of_expenses":
                if inc.business_expenses is None:
                    raise LaborError(f"해고기간 임금: {label} — 필요경비(business_expenses)가 없습니다")
                if amount is not None:
                    amount = max(ZERO, amount - inc.business_expenses)
                else:
                    monthly = max(ZERO, monthly - inc.business_expenses)
            ctx.warn(f"{label}: 사업소득 공제 기준({basis})은 판례 원문으로 확인되지 않았습니다(II-10c)")
        end = inc.end
        days = _days(inc.start, end) if end is not None else {o_ for o_ in claim_days if o_ >= inc.start.toordinal()}
        usable = days & claim_days
        if employer_days is not None:
            outside = usable - employer_days
            if outside and not future:
                ctx.ignored.append(f"{label}: 사용자 주장 범위 밖 {len(outside)}일분 공제하지 않음(M-05)")
            usable &= employer_days
        if not future and len(usable) < len(days) and not inc.assigned_period:
            ctx.ignored.append(f"{label}: 청구 기간(제외기간 포함) 밖 {len(days - usable)}일분은 대응 기간이 아니어서 공제하지 않음(II-06)")
        if not usable and not inc.assigned_period:
            continue
        out.append((idx, inc, usable, days, amount, monthly))
    return out


def _one_year_end(start: date) -> date:
    """start(초일 산입)부터 1년의 만료일 — 민법 제160조(대응일 전날, 대응일이 없으면 그 월 말일)."""
    t = add_months(start, 12)
    return t if t.day != start.day else t - timedelta(days=1)


def _alloc_amount(inc_amount: Decimal | None, monthly: Decimal | None, overlap: int, win_period_days: int,
                  income_days: int, idx: int, spans_many: bool, ctx: _Ctx, inc: InterimIncome | None = None) -> Decimal:
    o = ctx.o
    rnd = o["ii_rounding"]
    if overlap <= 0:
        return ZERO
    if monthly is None and not spans_many:
        # 비교 기간 하나 안의 수입 총액은 안분할 것이 없다 — ii_income_allocation 을 적용하지 않는다(II-06)
        return inc_amount if overlap >= income_days else _r(inc_amount * overlap / income_days, rnd)
    if monthly is None and inc_amount is not None and o["ii_income_allocation"] == "annual_equal_monthly":
        monthly = inc_amount / 12
        if inc is not None and inc.end is not None and inc.end != _one_year_end(inc.start):
            ctx.warn(f"중간수입[{idx + 1}] 수입 기간 {_fmt(inc.start)}~{_fmt(inc.end)}({income_days}일)이 1년이 아닌데 "
                     "ii_income_allocation=annual_equal_monthly 로 총액 ÷ 12를 월액으로 썼습니다 — 연간 총액이 아니면 "
                     "monthly_amount·assigned_period 로 적거나 calendar_days 를 쓰십시오(II-06)")
    if monthly is not None:
        if overlap >= win_period_days:
            return _r(monthly, rnd)
        den = 30 if o["dw_proration"] == "fixed_30" else win_period_days
        return _r(monthly * overlap / den, rnd)
    if not spans_many:
        return inc_amount if overlap >= income_days else _r(inc_amount * overlap / income_days, rnd)
    if o["ii_income_allocation"] is None:
        raise LaborError(f"해고기간 임금: 중간수입[{idx + 1}] 총액이 여러 비교 기간에 걸칩니다 — 옵션 ii_income_allocation"
                         "(calendar_days | assigned_wage_period | annual_equal_monthly)을 정하거나 assigned_period·monthly_amount 로 적어야 합니다")
    if o["ii_income_allocation"] == "assigned_wage_period":
        raise LaborError(f"해고기간 임금: 중간수입[{idx + 1}] ii_income_allocation=assigned_wage_period 이면 assigned_period 가 필요합니다")
    return _r(inc_amount * overlap / income_days, rnd)


def _build_windows(rows: list, row_days: list, incomes: list, ctx: _Ctx) -> list:
    o = ctx.o
    windows: list[_Window] = []
    by_key = {r.key: i for i, r in enumerate(rows)}
    assigned_rows = set()
    for idx, inc, usable, days, amount, monthly in incomes:
        if inc.assigned_period:
            if inc.assigned_period not in by_key:
                ctx.ignored.append(f"중간수입[{idx + 1}]: 귀속 임금산정기간 {inc.assigned_period} 이 청구 행에 없어 공제하지 않음(II-06)")
                continue
            assigned_rows.add(by_key[inc.assigned_period])
    day_incomes = [x for x in incomes if not x[1].assigned_period]
    if o["ii_period_anchor"] == "income_start" and day_incomes:
        union = set()
        for x in day_incomes:
            union |= x[2]
        for rs, re_ in _runs(union):
            if rs.day > 28:
                raise LaborError(f"해고기간 임금: 수입 시작일 {_fmt(rs)} 기준 1개월 창은 29일 이후 시작을 받지 않습니다")
            for sl in pay_periods(rs, re_, rs.day):
                wd = _days(sl.start, sl.end) & union
                if not wd:
                    continue
                last = date.fromordinal(max(wd))
                ri = next((i for i, dset in enumerate(row_days) if last.toordinal() in dset), None)
                if ri is None:
                    continue
                if ri in assigned_rows:
                    raise LaborError("해고기간 임금: 같은 임금산정기간에 assigned_period 수입과 income_start 창을 섞을 수 없습니다")
                windows.append(_Window(ri, wd, sl.period_start, sl.period_days, False, sl.period_start))
                if len(wd & row_days[ri]) != len(wd):
                    ctx.warn(f"수입 기준 창 {_fmt(sl.start)}~{_fmt(sl.end)} 이 두 임금산정기간에 걸쳐 공제액을 마지막 날이 속한 "
                             f"{rows[ri].label} 행에 넣었습니다(II-06 income_start)")
    else:
        for i, r in enumerate(rows):
            if not day_incomes or i in assigned_rows:
                continue
            union = set()
            for x in day_incomes:
                union |= x[2] & row_days[i]
            if not union:
                continue
            wd = union if o["ii_cap_window"] == "income_overlap_days" else row_days[i]
            windows.append(_Window(i, wd, r.period_start, r.period_days, len(wd) == len(row_days[i]), r.period_start))
    for i in sorted(assigned_rows):
        r = rows[i]
        windows.append(_Window(i, row_days[i], r.period_start, r.period_days, True, r.period_start, assigned=True))
    # 수입 배정(귀속 지정 창에도 날짜로 겹치는 다른 수입은 안분해 넣는다)
    for w in windows:
        for idx, inc, usable, days, amount, monthly in incomes:
            if inc.assigned_period:
                if w.assigned and rows[w.row].key == inc.assigned_period:
                    w.incomes[idx] = amount if amount is not None else monthly
                continue
            ov = len(w.days & usable)
            if not ov:
                continue
            spans_many = len(usable - w.days) > 0 or len(days) > len(usable)
            w.incomes[idx] = _alloc_amount(amount, monthly, ov, w.period_days, len(days), idx, spans_many, ctx, inc)
    return [w for w in windows if w.incomes]


def _is_small_window(ref: date, ctx: _Ctx) -> bool:
    if ctx.small_fn is None:
        return False
    if ctx.o["ii_headcount_basis"] == "prior_month_majority":
        if ref < DATE_HEADCOUNT_RULE:
            ctx.warn("2008. 6. 25.(시행령 제7조의2 신설) 전 기간은 상시 근로자 수를 기준일 당일 값으로 보았습니다(판정 방식 확인불가)")
            return ctx.small_fn(ref)
        s = add_months(ref, -1)
        total = (ref - s).days
        small_days = sum(1 for k in range(total) if ctx.small_fn(s + timedelta(days=k)))
        return small_days * 2 >= total
    return ctx.small_fn(ref)


def _cap_flags(ctx: _Ctx) -> tuple[bool, bool]:
    inp = ctx.inp
    _, art46, damages, _ = CLAIM_BASES[inp.claim_basis]
    if inp.art46_suspension is not None:
        art46 = inp.art46_suspension
    if inp.damages_after_termination is not None:
        damages = inp.damages_after_termination
    return art46, damages


def _rate_at(d: date) -> Decimal:
    return RATE_60 if d < DATE_RATE_70 else RATE_70


def _ordinary_monthly(ctx: _Ctx, required: bool, why: str) -> Decimal | None:
    v = ctx.inp.interim_cap.get("ordinary_monthly_wage") or ctx.inp.base_wage.get("ordinary_monthly_wage")
    if v is None and required:
        raise LaborError(f"해고기간 임금: {why}에 월 통상임금(interim_cap.ordinary_monthly_wage)이 필요합니다")
    return v


def _avg_for_cap(ctx: _Ctx, kind: str) -> Decimal:
    """A: 일평균, B·E: 월평균 — 통상임금 하한(제2조 제2항, M-01) 반영."""
    if kind not in ctx.avg_cache:
        ctx.avg_cache[kind] = _avg_for_cap_raw(ctx, kind)
    return ctx.avg_cache[kind]


def _avg_for_cap_raw(ctx: _Ctx, kind: str) -> Decimal:
    inp, deps = ctx.inp, ctx.deps
    if kind == "daily":
        v = inp.interim_cap.get("avg_daily_wage")
        if v is None:
            v = deps.get("average_daily_wage")
        if v is None:
            raise LaborError("해고기간 임금: 옵션 A(ii_cap_base=A_daily_avg)에는 해고 전 3개월 1일 평균임금"
                             "(interim_cap.avg_daily_wage 또는 deps average_daily_wage)이 필요합니다")
        v = dec(v)
        fn = deps.get("daily_ordinary_of")
        if fn is not None and inp.dismissal_date is not None:
            ordinary = dec(fn(inp.dismissal_date))
            if ordinary > v:
                ctx.trace.append(Trace("II-04", "평균임금 통상임금 하한", f"{v} → {ordinary}", "근로기준법 제2조 제2항(M-01)"))
                v = ordinary
        else:
            ctx.warn("옵션 A: 1일 통상임금(deps daily_ordinary_of)이 없어 평균임금 통상임금 하한(제2조 제2항)을 확인하지 못했습니다")
        return v
    v = inp.interim_cap.get("avg_monthly_wage")
    if v is None:
        raise LaborError(f"해고기간 임금: 옵션 {ctx.o['ii_cap_base']} 에는 해고 전 3개월 월평균임금(interim_cap.avg_monthly_wage)이 필요합니다")
    ordinary = _ordinary_monthly(ctx, False, "")
    if ordinary is None:
        ctx.warn(f"옵션 {ctx.o['ii_cap_base']}: 월 통상임금(interim_cap.ordinary_monthly_wage)이 없어 통상임금 하한을 확인하지 못했습니다")
    elif ordinary > v:
        ctx.trace.append(Trace("II-04", "평균임금 통상임금 하한", f"{v} → {ordinary}", "근로기준법 제2조 제2항(M-01)"))
        v = ordinary
    return v


def _rolling_base(ps: date, ctx: _Ctx, first_ps: date) -> Decimal:
    """옵션 D: 직전 3개 임금산정기간 가정 임금 합 ÷ 3(광주지법 2017나58303)."""
    total = ZERO
    for k in (1, 2, 3):
        p = ctx.slice_at(add_months(ps, -k)).period_start
        if p >= first_ps:
            total += _full_wage(p, ctx).avg
        else:
            key = f"{p.year:04d}-{p.month:02d}"
            v = ctx.inp.interim_cap["pre_dismissal_wages"].get(key)
            if v is None:
                raise LaborError(f"해고기간 임금: 옵션 D 에는 해고 전 임금산정기간 {key} 의 임금(interim_cap.pre_dismissal_wages)이 필요합니다")
            total += v
    base = _r(total / 3, ctx.o["ii_rounding"])
    ordinary = _ordinary_monthly(ctx, False, "")
    if ordinary is not None and ordinary > base:
        base = ordinary
    return base


def _net(x: Decimal, ctx: _Ctx) -> Decimal:
    if ctx.o["ii_wage_basis_for_cap"] != "net_of_withholding":
        return x
    if ctx.inp.withholding_rate is None:
        raise LaborError("해고기간 임금: ii_wage_basis_for_cap=net_of_withholding 에는 withholding_rate 가 필요합니다")
    return _r(x * (ONE - ctx.inp.withholding_rate), ctx.o["dw_withholding_rounding"])


def _window_limit(w: _Window, rows: list, row_days: list, ctx: _Ctx, first_ps: date, capped: bool,
                  deemed: date | None) -> tuple[Decimal, Decimal | None, Decimal | None, Decimal]:
    """(공제 한도, 휴업수당 상당액, 율, 창 임금). 한도 없음이면 한도 = 창 임금."""
    o = ctx.o
    rnd = o["ii_rounding"]
    r = rows[w.row]
    include_leave = o["ii_leave_allowance"] == "include_as_claimed"
    split_non = o["ii_exclude_non_avg_items_from_cap"]
    full = _full_wage(w.period_start, ctx)
    full_avg = full.avg + (full.leave if include_leave else ZERO) + (ZERO if split_non else full.non_avg)
    full_non = full.non_avg if split_non else ZERO

    def seg_wage(nd: int, whole_seg: bool) -> tuple[Decimal, Decimal]:
        if whole_seg:
            return r._cap_avg, r._cap_non
        return (ctx.prorate(full_avg, nd, w.period_days, rnd), ctx.prorate(full_non, nd, w.period_days, rnd))

    # 율(1989. 3. 29.)·고용 의사표시 확정일로 창을 나눈다
    cuts = [DATE_RATE_70.toordinal()]
    if deemed is not None:
        cuts.append(deemed.toordinal())
    segs = [w.days]
    for c in cuts:
        nxt = []
        for sgm in segs:
            a = {x for x in sgm if x < c}
            b = sgm - a
            nxt += [x for x in (a, b) if x]
        segs = nxt
    limit_total, h_total, wage_total, rate_shown = ZERO, ZERO, ZERO, None
    any_h = False
    for sgm in segs:
        nd = len(sgm)
        whole_seg = w.whole and len(segs) == 1
        d0 = date.fromordinal(min(sgm))
        rate = _rate_at(d0)
        rate_shown = rate
        w_avg, w_non = seg_wage(nd, whole_seg)
        w_avg, w_non = _net(w_avg, ctx), _net(w_non, ctx)
        wage_total += w_avg + w_non
        seg_capped = capped
        if deemed is not None:
            if d0 < deemed:
                seg_capped = False
            elif o["ii_post_deemed_employment_cap"] == "no_cap":
                seg_capped = False
        if not seg_capped:
            limit_total += w_avg + w_non
            continue
        base = o["ii_cap_base"]
        if base is None:
            raise LaborError("해고기간 임금: 공제할 중간수입이 있으면 옵션 ii_cap_base(A_daily_avg | B_monthly_avg | "
                             "C_contract_wage_ratio | D_rolling_avg | E_avg_wage_fixed_ratio)를 사건.yaml 에서 반드시 골라야 합니다"
                             "(II-04 대법원 판시 없음, 판결 관찰 빈도는 C 가 가장 높음)")
        full_seg = nd >= w.period_days
        order = o["ii_rounding_order"]
        if base == "C_contract_wage_ratio":
            if order == "rate_first" and not full_seg:
                fa = _net(full_avg, ctx)
                lm = _r(fa * (ONE - rate), rnd) if o["ii_c_rounding_target"] == "limit" else fa - _r(fa * rate, rnd)
                den = 30 if o["dw_proration"] == "fixed_30" else w.period_days
                lim = _r(lm * nd / den, rnd)
            else:
                lim = _r(w_avg * (ONE - rate), rnd) if o["ii_c_rounding_target"] == "limit" else w_avg - _r(w_avg * rate, rnd)
            h = w_avg - lim
        else:
            if base == "A_daily_avg":
                hm = _r(_avg_for_cap(ctx, "daily") * rate * 365 / 12, rnd)
            elif base == "B_monthly_avg":
                hm = _r(_avg_for_cap(ctx, "monthly") * rate, rnd)
            elif base == "D_rolling_avg":
                hm = _r(_rolling_base(w.period_start, ctx, first_ps) * rate, rnd)
            else:  # E
                avg = _avg_for_cap(ctx, "monthly")
                hm = avg - _r(avg * (ONE - rate), rnd)
            if o["ii_apply_ordinary_wage_cap"]:
                if d0 < DATE_ORDINARY_PROVISO:
                    raise LaborError("해고기간 임금: 제46조 제1항 단서(통상임금 상한)는 1997. 3. 1.(법률 제5245호) 전 기간에 적용할 수 없습니다")
                ordinary = _ordinary_monthly(ctx, True, "ii_apply_ordinary_wage_cap")
                if ordinary < hm:
                    hm = ordinary
            den = 30 if o["dw_proration"] == "fixed_30" else w.period_days
            if base == "E_avg_wage_fixed_ratio":
                lm = avg - hm
                lim = lm if full_seg else _r(lm * nd / den, rnd)
                h = w_avg - lim
            elif order == "rate_first" and not full_seg:
                fa = _net(full_avg, ctx)
                lim = _r(max(ZERO, fa - hm) * nd / den, rnd)
                h = w_avg - lim
            else:
                h = hm if full_seg else _r(hm * nd / den, rnd)
                lim = max(ZERO, w_avg - h)
            if not full_seg:
                ctx.warn("월 중 일부 창의 휴업수당 일할(옵션 A·B·D·E)은 판결 관찰 사례가 없습니다(II-04)")
        lim = max(ZERO, min(lim, w_avg))
        limit_total += lim + w_non
        h_total += max(ZERO, h)
        any_h = True
    return limit_total, (h_total if any_h else None), rate_shown, wage_total


def _apply_interim(rows: list, row_days: list, incomes: list, ctx: _Ctx, first_ps: date) -> None:
    o = ctx.o
    inp = ctx.inp
    if not incomes:
        return
    art46, damages = _cap_flags(ctx)
    basis_capped = art46 and not damages
    deemed = inp.employment_deemed_date
    if deemed is not None and o["ii_post_deemed_employment_cap"] is None:
        raise LaborError("해고기간 임금: employment_deemed_date 가 있으면 옵션 ii_post_deemed_employment_cap(apply | no_cap)을 "
                         "정해야 합니다(II-07, 확정일 이후 기간 한도 판시 없음)")
    windows = _build_windows(rows, row_days, incomes, ctx)
    for w in windows:
        r = rows[w.row]
        small = _is_small_window(w.ref, ctx)
        capped = basis_capped and not small
        if small:
            r.small_business = True
        lim, h, rate, wage = _window_limit(w, rows, row_days, ctx, first_ps, capped, deemed)
        i_cap = sum((v for k, v in w.incomes.items() if not inp.interim_income[k].admitted_without_cap), ZERO)
        i_unc = sum((v for k, v in w.incomes.items() if inp.interim_income[k].admitted_without_cap), ZERO)
        ded_c = min(i_cap, lim)
        ded_u = min(i_unc, max(ZERO, wage - ded_c))
        r.income += i_cap
        r.income_uncapped += i_unc
        r.deduction += ded_c + ded_u
        r.limit = (r.limit or ZERO) + lim
        if h is not None:
            r.allowance = (r.allowance or ZERO) + h
        r.rate = rate if capped else r.rate
        notes = []
        if not w.whole:
            s, e = date.fromordinal(min(w.days)), date.fromordinal(max(w.days))
            notes.append(f"비교 창 {_fmt(s)}~{_fmt(e)} {len(w.days)}일")
        if small:
            notes.append("상시 4명 이하 — 제46조 미적용, 한도 없이 공제(II-08)")
        elif not basis_capped:
            notes.append(f"청구원인 {inp.claim_basis} — 휴업수당 한도 없음(II-07)")
        if i_unc:
            notes.append(f"한도 없는 공제 자인분 {i_unc}원(II-12)")
        if w.assigned:
            notes.append("귀속 임금산정기간 지정 수입 — 기간 전체 한도와 비교")
        r.note = "; ".join(x for x in [r.note] + notes if x)
    for r in rows:
        if r.deduction > r.deduction_base:
            r.deduction = r.deduction_base


# ================================================================ 행
def _make_row(kind: str, sl: PaySlice, cover: set, excluded: int, span: set, ctx: _Ctx) -> DismissalRow:
    o = ctx.o
    inp = ctx.inp
    full = _full_wage(sl.period_start, ctx)
    nd = len(cover)
    pdays = sl.period_days
    if full.daily is not None:
        wage_regular = _r(full.daily * nd, o["dw_proration_rounding"])
        avg, non, leave = wage_regular, ZERO, ZERO
        prorate_txt = f"일액 {full.daily} × {nd}일"
    else:
        avg = ctx.prorate(full.avg, nd, pdays)
        non = ctx.prorate(full.non_avg, nd, pdays)
        leave = ctx.prorate(full.leave, nd, pdays)
        den = 30 if o["dw_proration"] == "fixed_30" else pdays
        prorate_txt = "전부" if nd >= pdays else f"{nd}일/{den}일"
    items = dict(full.items)
    notes = []
    if kind != "pre_dismissal":
        b_items, b_avg, b_non, b_notes = _payment_month_bonus(sl, span, ctx)
        for k, v in b_items.items():
            items[k] = items.get(k, ZERO) + v
        avg += b_avg
        non += b_non
        notes += b_notes
    wage = avg + non + leave
    include_leave = o["ii_leave_allowance"] == "include_as_claimed"
    split_non = o["ii_exclude_non_avg_items_from_cap"]
    row = DismissalRow(
        kind=kind, key=sl.key,
        label=(f"{sl.period_end.year}. {sl.period_end.month}.분" if inp.pay_period_start_day != 1
               else f"{sl.period_start.year}. {sl.period_start.month}.분"),
        period_start=sl.period_start, period_end=sl.period_end,
        start=date.fromordinal(min(cover)), end=date.fromordinal(max(cover)),
        period_days=pdays, covered_days=nd, excluded_days=excluded, proration=prorate_txt, items=items, wage=wage,
        deduction_base=avg + non + (leave if include_leave else ZERO),
        small_business=None, rate=None, allowance=None, limit=None, income=ZERO, income_uncapped=ZERO,
        deduction=ZERO, pay=ZERO, pay_amount=ZERO,
        pay_date=(pay_date_for(sl.period_end, inp.pay_day, inp.pay_month_offset) if inp.pay_day is not None else None),
        note="; ".join(notes),
    )
    row._cap_avg = avg + (leave if include_leave else ZERO) + (ZERO if split_non else non)
    row._cap_non = non if split_non else ZERO
    if excluded:
        row.note = "; ".join(x for x in (row.note, f"제외기간 {excluded}일" ) if x)
    return row


def _finish_row(r: DismissalRow, ctx: _Ctx) -> None:
    r.pay = r.wage - r.deduction
    if ctx.o["dw_amount_basis"] == "net_of_withholding":
        if ctx.inp.withholding_rate is None:
            raise LaborError("해고기간 임금: dw_amount_basis=net_of_withholding 에는 withholding_rate(예: 0.033)가 필요합니다")
        r.pay_amount = _r(r.pay * (ONE - ctx.inp.withholding_rate), ctx.o["dw_withholding_rounding"])
    else:
        r.pay_amount = r.pay


# ================================================================ 본체
def _setup_base_wage(inp: DismissalInput, ctx: _Ctx) -> None:
    o = ctx.o
    method = o["dw_base_wage_method"]
    bw = inp.base_wage
    ctx.trace.append(Trace("DW-08", "기준 월임금 방식", method, OPTIONS["dw_base_wage_method"].choices[method] +
                           " — 대법원 기준 없음(불명확), 임금액 증명책임은 근로자(94다25889)"))
    if method == "avg_daily_3m":
        daily = bw.get("avg_daily_wage")
        if daily is None and ctx.deps.get("average_daily_wage") is not None:
            daily = dec(ctx.deps["average_daily_wage"])
        if daily is None:
            if bw.get("three_month_total") is None or bw.get("three_month_days") is None:
                raise LaborError("해고기간 임금: avg_daily_3m 방식에는 base_wage.avg_daily_wage 또는 three_month_total·three_month_days"
                                 "(또는 deps average_daily_wage)가 필요합니다")
            daily = _r(bw["three_month_total"] / bw["three_month_days"], o["dw_daily_rate_rounding"])
            ctx.trace.append(Trace("DW-08", "평균임금 일액", str(daily),
                                   f"{bw['three_month_total']}원 ÷ {bw['three_month_days']}일({o['dw_daily_rate_rounding']})"))
        fn = ctx.deps.get("daily_ordinary_of")
        if fn is not None and inp.dismissal_date is not None:
            ordinary = dec(fn(inp.dismissal_date))
            if ordinary > daily:
                ctx.trace.append(Trace("DW-08", "평균임금 통상임금 하한", f"{daily} → {ordinary}", "근로기준법 제2조 제2항"))
                daily = ordinary
        ctx.daily_rate = daily
    elif method == "avg_monthly_3m_ordinary_floor":
        if bw.get("three_month_total") is None:
            raise LaborError("해고기간 임금: avg_monthly_3m_ordinary_floor 방식에는 base_wage.three_month_total 이 필요합니다")
        avg = _r(bw["three_month_total"] / 3, o["dw_monthly_avg_rounding"])
        ordinary = bw.get("ordinary_monthly_wage")
        if ordinary is None:
            raise LaborError("해고기간 임금: avg_monthly_3m_ordinary_floor 방식에는 base_wage.ordinary_monthly_wage 가 필요합니다")
        ctx.base_monthly = max(avg, ordinary)
        ctx.trace.append(Trace("DW-08", "3개월 월평균과 통상임금", f"{avg} / {ordinary} → {ctx.base_monthly}",
                               "평균임금이 통상임금보다 적으면 통상임금(제2조 제2항, 2023가합11391)"))
    else:
        if not inp.wage_items:
            raise LaborError("해고기간 임금: 임금 항목(wage_items)이 없습니다")
        if method == "last_month":
            ctx.warn("기준 월임금을 직전 1개월 지급액으로 고정했습니다 — 해고 후 임금인상을 반영하지 않은 원심은 대법원 93다21736 에서 "
                     "파기되었습니다" + (" (인상 스케줄 raises 가 있으나 반영하지 않음)" if inp.raises else ""))
        for rs in inp.raises:
            if rs.kind == "promotion" and not rs.certain:
                ctx.warn(f"인상 {_fmt(rs.applies_from)}(promotion): 재량 승진 보수 증가는 자동·확실한 경우가 아니면 넣지 않습니다(94다446)")
            elif rs.kind == "evaluation":
                ctx.warn(f"인상 {_fmt(rs.applies_from)}(evaluation): 부당해고 기간을 불리하게 고려하지 않는 '적정한 등급'(2018다279040) — "
                         "등급 결정은 사람이 한 값입니다(환송심 2019나58100 휴직자 등급 준용)")
        if inp.raises:
            ctx.warn("해고기간 중 임금 인상분은 근로자에게 증명책임이 있습니다(94다25889)")


def calculate_dismissal(inp: DismissalInput, opts: dict, **deps) -> DismissalResult:
    o = _read_options(opts)
    ctx = _Ctx(inp, o, deps)
    trace, warnings = ctx.trace, ctx.warnings
    for key, spec in OPTIONS.items():
        v = o[key]
        trace.append(Trace(spec.rule, f"옵션 {key}", str(v), spec.choices.get(v, spec.description) if spec.choices else spec.description))
    trace.append(Trace("II-07", "청구원인", inp.claim_basis, CLAIM_BASES[inp.claim_basis][0]))

    ref = inp.dismissal_date or inp.start_date
    small_at_dismissal = ctx.small(ref)
    if small_at_dismissal:
        if inp.invalidity_basis == "lsa_23":
            raise LaborError("해고기간 임금: 상시 4명 이하 사업장에는 제23조 제1항(해고 제한)이 적용되지 않습니다(시행령 [별표 1]) — "
                             "invalidity_basis 를 단협·취업규칙·절차 위반 등으로 적어야 합니다(DW-01)")
        warnings.append("상시 4명 이하 사업장: 해고제한·구제신청·휴업수당(제46조)·가산임금(제56조)·연차(제60조)가 적용되지 않습니다(DW-M01)")
    if inp.invalidity_basis is None and inp.claim_basis == "wage_538_invalid_dismissal":
        ctx.warn("해고 무효 근거(invalidity_basis)가 없습니다 — 5인 미만 사업장이면 제23조 제1항으로 무효가 되지 않습니다(DW-01)")

    # ---- 노동위원회 금전보상 모드
    if inp.mode == "labor_commission_award":
        if small_at_dismissal:
            raise LaborError("해고기간 임금: 상시 4명 이하 사업장은 노동위원회 구제신청(제28조)을 할 수 없어 금전보상 모드를 쓸 수 없습니다(DW-21)")
        start = inp.start_date or inp.dismissal_date
        lc = inp.labor_commission
        daily, n, amount = labor_commission_award_amount(lc["monthly_wage"], start, lc["decision_date"], lc["service_days"])
        trace.append(Trace("DW-21", "금전보상 임금상당액", str(amount),
                           f"floor({lc['monthly_wage']} × 12 ÷ 365) = {daily}원 × ({_fmt(start)}~{_fmt(lc['decision_date'])} "
                           f"+ 송달 {lc['service_days']}일 = {n}일) — 행정심판 2022-09280 인정사실(재결 원문 미재확인)"))
        warnings.append("노동위원회 금전보상 산식(월급 × 12 ÷ 365 × 일수)은 실무관행이며 제30조 제3항은 '임금 상당액 이상'입니다. "
                        "구제명령 임금상당액은 제36조 금품이 아니라는 행정해석(근로기준정책과-1518)이 있습니다")
        row = DismissalRow("labor_commission", "", "금전보상", start, lc["decision_date"], start, lc["decision_date"],
                           n, n, 0, f"일액 {daily} × {n}일", {"일액": daily}, amount, ZERO, False, None, None, None,
                           ZERO, ZERO, ZERO, amount, amount, None, f"송달기간 {lc['service_days']}일 포함")
        return DismissalResult(rows=[row], total=amount, claims=[], trace=trace, warnings=warnings, start_date=start,
                               labor_commission_amount=amount)

    if inp.pay_day is None:
        raise LaborError("해고기간 임금: 정기지급일(worker.pay_day)이 없습니다 — 각 월 임금의 지급기일(지연손해금 기산)에 필요합니다")
    _setup_base_wage(inp, ctx)

    # ---- 기산일·종기
    if inp.start_date is not None:
        S = inp.start_date
        trace.append(Trace("DW-09", "기산일", _fmt(S), "사람이 지정(start_date)"))
    elif o["dw_start_rule"] == "next_day":
        S = inp.dismissal_date + timedelta(days=1)
        trace.append(Trace("DW-09", "기산일", _fmt(S), f"해고일 {_fmt(inp.dismissal_date)} 다음날"))
    else:
        S = inp.dismissal_date
        trace.append(Trace("DW-09", "기산일", _fmt(S), "해고 효력발생일 당일"))
    cands = _end_candidates(inp, ctx)
    E, end_reason = None, ""
    if cands:
        E, end_reason, _ = min(cands, key=lambda c: c[0])
        trace.append(Trace("DW-10", "종기", _fmt(E), end_reason))
    limit_candidates = [d for d in (inp.past_until, inp.closing_date) if d is not None]
    past_cap = inp.past_until or inp.closing_date
    if E is None and past_cap is None:
        raise LaborError("해고기간 임금: 종기(reinstatement_date·termination 등)나 과거분 마감일(past_until 또는 closing_date)이 없습니다")
    past_end = min(x for x in (E, past_cap) if x is not None)
    if E is not None and E < S:
        raise LaborError(f"해고기간 임금: 종기 {_fmt(E)} 가 기산일 {_fmt(S)} 보다 앞섭니다")
    if past_end < S:
        raise LaborError(f"해고기간 임금: 과거분 마감일 {_fmt(past_end)} 이 기산일 {_fmt(S)} 보다 앞섭니다")
    trace.append(Trace("DW-19", "과거분 마감일", _fmt(past_end), "min(종기, past_until 또는 변론종결일)"))
    if limit_candidates and E is not None and E > past_cap:
        ctx.warn(f"종기 {_fmt(E)} 가 과거분 마감일 {_fmt(past_cap)} 뒤입니다 — 그 사이는 장래분으로 따로 봅니다")
    if inp.discipline_type in ("suspension", "standby"):
        trace.append(Trace("DW-M05", "징계 유형", inp.discipline_type, "무효 정직·대기발령에도 같은 산정(2010다99279)"))
    if inp.discipline_type == "transfer" and inp.claim_basis != "wage_invalid_transfer":
        ctx.warn("전적 사안인데 claim_basis 가 wage_invalid_transfer 가 아닙니다 — 무효 전적은 제46조 휴업이 아니어서 한도가 없습니다(2013다45075)")

    excl = _exclusion_days(inp, ctx, past_end if E is None else max(E, past_end))
    span = _days(S, past_end) - excl

    # ---- 해고 전 미지급 근로임금
    rows: list[DismissalRow] = []
    row_days: list[set] = []
    if inp.paid_through_date is not None and inp.paid_through_date + timedelta(days=1) <= S - timedelta(days=1):
        ps_, pe_ = inp.paid_through_date + timedelta(days=1), S - timedelta(days=1)
        for sl in pay_periods(ps_, pe_, inp.pay_period_start_day):
            cover = _days(sl.start, sl.end)
            rows.append(_make_row("pre_dismissal", sl, cover, 0, span, ctx))
            row_days.append(set())
        trace.append(Trace("DW-M06", "해고 전 미지급 근로임금", f"{_fmt(ps_)}~{_fmt(pe_)}",
                           "해고기간과 구분 — 중간수입 공제·연차 출근 간주 대상 아님(2020가합210338)"))
    elif inp.paid_through_date is not None and inp.paid_through_date >= S:
        ctx.warn(f"임금 지급 완료일 {_fmt(inp.paid_through_date)} 이 해고기간 기산일 {_fmt(S)} 이후입니다 — 기지급분은 payments 로 적어야 합니다")

    # ---- 해고기간 행
    dismissal_first = len(rows)
    for sl in pay_periods(S, past_end, inp.pay_period_start_day):
        full_days = _days(sl.start, sl.end)
        cover = full_days & span
        if not cover:
            trace.append(Trace("DW-11", f"{sl.key} 임금산정기간", "전부 제외기간", ""))
            continue
        rows.append(_make_row("dismissal", sl, cover, len(full_days - cover), span, ctx))
        row_days.append(cover)
    first_ps = ctx.slice_at(S).period_start

    # ---- 중간수입
    d_rows = rows[dismissal_first:]
    d_days = row_days[dismissal_first:]
    incomes = _deductible_incomes(inp, ctx, span)
    _apply_interim(d_rows, d_days, incomes, ctx, first_ps)
    for w in ctx.ignored:
        ctx.warn(w)
    if inp.interim_income:
        trace.append(Trace("II-02", "공제 산식", "limit = max(0, W − H), deduct = min(I, limit)",
                           "중간수입 − 휴업수당 방식 금지(2021다279903), 수입 < 휴업수당이라 공제 0 금지(2014다65397)"))
    for r in rows:
        _finish_row(r, ctx)

    # ---- 장래분
    future_start = future_amount = future_row = None
    future_end = None
    if E is None or E > past_end:
        future_start = inp.future_start_date or past_end + timedelta(days=1)
        sl = ctx.slice_at(future_start)
        if future_start != sl.period_start:
            ctx.warn(f"장래분 시작일 {_fmt(future_start)} 이 임금산정기간 시작일이 아닙니다 — 월 금액은 {_fmt(sl.period_start)} 시작 기간 기준")
        future_end = E
        fspan = _days(sl.period_start, sl.period_end)
        if E is not None:
            fspan = {x for x in fspan if x <= E.toordinal()}
        fspan -= excl
        if fspan:
            frow = _make_row("future", sl, fspan, 0, fspan, ctx)
            if o["dw_future_interim"] == "continue_open_ended":
                fincomes = _deductible_incomes(inp, ctx, fspan, future=True)
                _apply_interim([frow], [fspan], fincomes, ctx, first_ps)
            _finish_row(frow, ctx)
            future_row, future_amount = frow, frow.pay_amount
            trace.append(Trace("DW-19", "장래분", f"{_fmt(future_start)}부터 {'복직시까지' if E is None else _fmt(E) + '까지'} 월 {future_amount}원",
                               "90다카25277 — 변론종결 이후부터 복직할 때까지"))
        warnings.append("확정판결의 기판력은 주문 기간 전체 임금에 미칩니다 — 기본급·수당·상여·연차·성과급·인상분·승급분·명절 금품 등 "
                        "누락 항목이 없는지 확인해야 합니다(97다58194, 2024다294156)")

    # ---- 합계·원금 항목
    pre_total = sum((r.pay_amount for r in rows if r.kind == "pre_dismissal"), ZERO)
    dis_total = sum((r.pay_amount for r in rows if r.kind == "dismissal"), ZERO)
    wage_total = sum((r.wage for r in rows), ZERO)
    ded_total = sum((r.deduction for r in rows), ZERO)
    # 근로관계가 실제로 끝난 날(지연손해금 DI-03 의 마지막 근무일). 갱신기대권이 인정되면 원래 계약만료일이 아니라
    # 갱신 간주된 계약기간 만료일에 끝나고(DW-10, 2007두1729), 그 날이 없으면 근로관계가 계속된 것으로 본다.
    renewal = inp.termination_cause == "contract_end" and inp.renewal_expectation
    t_end = inp.renewed_term_end if renewal else inp.termination_date
    terminated = t_end is not None
    status = "terminated" if terminated else ("reinstated" if inp.reinstatement_date is not None else "continuing")
    renewal_note = ""
    if renewal:
        renewal_note = (f"원래 계약만료일 {_fmt(inp.termination_date)}은 갱신기대권(갱신 간주, 2007두1729)으로 근로관계 종료일이 "
                        "아님 — " + (f"갱신 간주된 계약기간 만료일 {_fmt(t_end)}을 종료일로 봄" if terminated
                                    else "갱신 간주 계약기간 만료일(renewed_term_end)이 없어 근로관계 계속으로 봄"))
        trace.append(Trace("DW-10", "근로관계 종료일(지연손해금용)", _fmt(t_end) if terminated else "계속", renewal_note))
    wl = inp.worker_last_working_day
    if wl is not None and (t_end is None or wl < t_end):
        ctx.warn((f"worker.last_working_day {_fmt(wl)} 이 해고기간 임금 모듈의 근로관계 종료일 {_fmt(t_end)} 보다 앞섭니다. "
                  if terminated else f"worker.last_working_day {_fmt(wl)} 가 있는데 해고기간 임금 모듈은 근로관계가 "
                  f"{'복직으로 이어진' if status == 'reinstated' else '계속되는'} 것으로 계산했습니다. ")
                 + "지연손해금 모듈은 worker.last_working_day 를 마지막 근무일로 보아 구법 도래분 해고기간 임금에 그 15일째부터 "
                 "연 20%를 붙입니다(DI-03) — 해고일·원래 계약만료일을 적었다면 지우고, 실제로 근로관계가 끝났다면 "
                 "dismissal.termination 에도 적으십시오")
    claims, installments = [], []
    for r in rows:
        if r.pay_amount <= 0:
            continue
        cat = "해고 전 미지급 임금" if r.kind == "pre_dismissal" else "해고기간 임금"
        label = f"{cat} {r.label}({_fmt(r.start)}~{_fmt(r.end)})"
        before_t = (r.pay_date <= t_end) if terminated and r.pay_date else None
        note = (f"정기지급일 {_fmt(r.pay_date)}; 근로관계 {status}"
                + (f", 종료일 {_fmt(t_end)}({TERMINATION_CAUSES[inp.termination_cause]}"
                   + (f" — 갱신 간주, 원래 계약만료일 {_fmt(inp.termination_date)}" if renewal else "")
                   + f"), 제36조 기한 {_fmt(t_end + timedelta(days=14))} — 이율 판단은 지연손해금 모듈" if terminated else "")
                + ("; 원천징수 후 금액" if o["dw_amount_basis"] == "net_of_withholding" else ""))
        claims.append(Claim(cat, label, r.pay_amount, r.pay_date, False, note=note))
        installments.append(DismissalInstallment(label, r.kind, r.period_start, r.period_end, r.pay_amount, r.pay_date, before_t))

    info = DismissalClaimInfo(
        employment_status=status, reinstatement_date=inp.reinstatement_date, termination_date=t_end,
        termination_cause=inp.termination_cause if terminated else None,
        settlement_deadline=(t_end + timedelta(days=14)) if terminated else None,
        dismissal_invalid_final=inp.dismissal_invalid_final,
        remedy_order_issued=(inp.remedy_order or {}).get("issued"), remedy_order_final=(inp.remedy_order or {}).get("final"),
        remedy_order_date=(inp.remedy_order or {}).get("date"), employer_merchant=inp.employer_merchant,
        closing_date=inp.closing_date, first_instance_closing_date=inp.first_instance_closing_date,
        future_start_date=future_start, future_monthly_amount=future_amount, future_end_date=future_end,
        amount_basis=o["dw_amount_basis"], installments=installments, payments=list(inp.payments),
        interest_end_cause=_INTEREST_END_CAUSE.get(inp.termination_cause) if terminated else None,
    )
    if renewal_note:
        info.notes.append(renewal_note)
    if any(r.pay_date and r.pay_date >= DATE_NEW_ART37 - timedelta(days=1) for r in rows):
        info.notes.append("정기지급일이 2025. 10. 22. 이후인 임금이 있습니다 — 개정 제37조 제1항 제2호 적용 여부는 불명확(지연손해금 모듈)")
    if inp.payments:
        info.notes.append("기지급액은 합의가 없으면 지연손해금에 먼저 충당합니다(민법 제479조 제1항, allocate_payment)")
        warnings.append("기지급액(payments)은 원금에서 빼지 않았습니다 — 지연손해금 계산 뒤 법정충당(민법 제479조 제1항)해야 합니다(DW-20)")
        for p in inp.payments:
            if p.type == "severance" and not p.worker_admits_offset:
                ctx.warn(f"기지급 {_fmt(p.date)} 퇴직금 {p.amount}원: 임금채권과 상계할 수 없습니다(서울고법 2018나2016391) — "
                         "근로자가 자인한 경우만 공제(2012나55770)")
            if p.basis != ("net" if o["dw_amount_basis"] == "net_of_withholding" else "gross"):
                ctx.warn(f"기지급 {_fmt(p.date)} {p.amount}원의 금액 기준({p.basis})이 원금 기준({o['dw_amount_basis']})과 다릅니다(DW-20)")

    # ---- 연차·퇴직금 연결
    dismissal_span = _days(S, E if E is not None else past_end)
    deemed = _runs(dismissal_span - excl)
    continuous = _runs(dismissal_span)
    trace.append(Trace("DW-15", "연차 출근 간주 기간", ", ".join(f"{_fmt(a)}~{_fmt(b)}" for a, b in deemed),
                       "연간 소정근로일수·출근일수에 모두 산입(2011다95519)"))
    trace.append(Trace("DW-16", "계속근로기간 포함", ", ".join(f"{_fmt(a)}~{_fmt(b)}" for a, b in continuous),
                       "해고기간은 재직기간(2023나15560, 2020가합210338)"))
    if E is None:
        ctx.warn(f"종기가 없어 출근 간주·계속근로 기간을 과거분 마감일 {_fmt(past_end)} 까지만 냈습니다 — 복직일까지 이어집니다")
    if small_at_dismissal:
        ctx.warn("상시 4명 이하 사업장은 연차휴가(제60조)가 없어 출근 간주 기간을 연차 계산에 쓰지 않습니다")
    warnings.append("임금채권 소멸시효(3년)와 시효중단(구제신청 후 행정소송 보조참가 — 2011다20034)은 판정하지 않았습니다 — 소 제기일과 대조 필요")

    result = DismissalResult(
        rows=rows, total=pre_total + dis_total, claims=claims, trace=trace, warnings=warnings, start_date=S, end_date=E,
        end_reason=end_reason, past_end=past_end, pre_dismissal_total=pre_total, dismissal_total=dis_total,
        wage_total=wage_total, interim_deduction_total=ded_total, future_start_date=future_start,
        future_monthly_amount=future_amount, future_row=future_row, deemed_attendance_periods=deemed,
        continuous_service_periods=continuous, claim_info=info, ignored_income=list(ctx.ignored),
    )
    if inp.mode == "refund":
        result.refund_amount = ded_total
        result.refund_awardable = ded_total if inp.refund_claimed_amount is None else min(ded_total, inp.refund_claimed_amount)
        trace.append(Trace("II-14", "부당이득 반환액", f"공제 가능액 {ded_total}원 / 인용 가능 {result.refund_awardable}원",
                           "공제 없이 전액 지급 시 공제한도액 상당 부당이득(광주지법 2017나58303), 청구액 한도"))
        result.total = result.refund_awardable
        result.claims = []
    return result
