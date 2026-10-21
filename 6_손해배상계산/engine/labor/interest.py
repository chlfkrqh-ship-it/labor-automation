"""지연손해금 — 근로기준법 제37조 연 20%, 상사 6%·민사 5%, 소송촉진법 이율, 소멸시효 표시
(lane: delay_interest, 규칙 DI-01~DI-19 / 해고기간 임금 20% 쟁점: dismissal_interest_20).

다른 모듈이 만든 원금 항목(`Claim`)마다 날짜별 이율을 정해 구간표를 만들고,
(1) 청구취지·주문형 문구(기산일·이율 구간, 끝은 '다 갚는 날까지'), (2) 기준일까지의 금액,
(3) 소멸시효 완성일 표시를 낸다. 해고 무효·다툼의 적절성 같은 법적 판단은 하지 않는다.
사람이 사건.yaml `interest:` 절에 적은 날짜(송달일, 사실심 선고일 등)로 계산만 한다.

---------------------------------------------------------------- 이율
DI-01 [법령] 민사 연 5%(민법 제379조), 상사 연 6%(상법 제54조), 근로기준법 지연이자 연 20%
      (시행령 제17조 "연 100분의 20"). 20%는 **지급사유 발생일이 2005. 7. 1. 이후**인 금품에만
      (법률 제7465호 부칙 "시행 후 최초로 지급사유가 발생하는 경우부터") — 날짜 구간으로 구현하지 않는다.
      소송촉진법 법정이율: 1981. 3. 1. 25% → 2003. 6. 1. 20% → 2015. 10. 1. 15% → 2019. 6. 1. 12%.
      2015·2019 개정 부칙: 시행 당시 1심 변론이 종결된 사건은 종전 이율(`first_instance_close_date`).
      2003 부칙은 원문 재대조 안 됨 → 1심 변론종결일이 2003. 6. 1. 전이면 경과조치를 적용하지 않고 warning.
DI-02 [법령·판례확립/하급심] 퇴직·사망 청산 금품(Claim.settlement=True)은 지급사유 발생일부터 14일이 되는 날
      (= 마지막 근무일 + 14일, Claim.due_date)까지 미지급이면 그 다음 날부터 20%. 지급사유 발생일은 원금 항목의
      `trigger_date` 속성이 있으면 그 날, 없으면 마지막 근무일(`last_working_day`) 다음 날, 둘 다 없으면 due_date − 13일로
      본다(warning).
      - 14일째가 토·일요일·공휴일이면 민법 제161조로 다음 평일까지 늘리고 그 다음 날부터 — 서울북부지법 2019나40407·
        2019나35184(확정), 의정부지법 2020가합52832(확정), 부산지법 서부지원 2022가단4913(확정), 대전지법 2023나222268,
        광주지법 2024나84218. 공휴일(1. 1.·개천절·한글날)까지 늘렸다. 테스트에 쓰던 수원지법 성남지원 2021가합413433 은
        무변론으로 제161조를 다루지 않았다. `di_deadline_holiday_shift`. 공휴일은 관공서의 공휴일에 관한 규정 제2조의 양력
        공휴일과 제3조의 그 대체공휴일을 엔진이 세고, 설·추석·부처님 오신 날(과 그 대체공휴일)·임시공휴일·선거일은
        `interest.holidays` 로 받는다(warning).
      - due_date 가 그 기한보다 이르면(퇴직금 `rs_due_date=day_after_retirement`, 퇴직 직후 지급기일의 연차수당 등)
        due_date 다음 날부터 6%/5%, 20%는 기한 다음 날부터.
      - due_date 가 그 기한보다 늦으면 합의로 연장한 지급기일(제36조 단서·퇴직급여법 제9조 단서)로 보고 6%/5%·20% 모두
        그 다음 날부터(warning — 연장 합의는 사람이 확인). 연장 합의가 인정된 판결은 모두 연장된 지급기일 다음 날부터
        지연손해금을 붙였다 — 인천지법 부천지원 2020가단270(확정, '퇴직일로부터 30일 이내' 합의), 서울남부지법 2023나60986
        (확정), 의정부지법 2021가단114471(확정), 수원지법 안산지원 2016가단23809(확정, 분할지급 합의), 창원지법 2014나33141
        (확정, 지급유예). 합의로 연장해도 지연이자 의무를 면하지 못한다는 고용노동부 2005. 7. 28. 근로기준과-3981 과 같은
        판결은 찾지 못하였다(2026. 10. 21. LBOX).
DI-03 [법령/판례확립/불명확] 재직 중 정기임금(Claim.settlement=False)
      - 개정 제37조 제1항 제2호(법률 제20520호, 2025. 10. 23. 시행): 제43조 제2항 정기지급일까지
        미지급이면 다음 날부터 20%. 부칙 제2조 "시행 이후 … 지연이자 지급사유가 발생하는 경우부터".
        경계 정기지급일 2025. 10. 22.(고용노동부 Q&A '10. 23. 0시부터 지급 지연') — 서울고법 2025나208365(확정)
        "2025. 10. 21.을 지급일로 하는 2025년 10월분 임금은 2025. 10. 22.에 임금 미지급이 처음 발생한 경우여서 개정 전
        법률이 적용되어야 한다", `di_new_law_cutoff`. 퇴직 후에도 정기지급일 기준 유지(제37조 제2항). 정기지급일이 퇴직
        뒤인 임금은 DI-19.
      - 구법 적용분: 재직(복직) 중이면 20% 없음 — 대법원 2014. 8. 26. 선고 2014다28305(원심 판단
        수긍) "해고가 무효로 되어 갑이 복직한 이상 이에 해당한다고 보기 어렵고 … 상법이 정한 연 6%".
        근로관계가 끝났으면(정년·계약만료·사직·재해고) 마지막 근무일 + 14일(14일째가 토·일요일·공휴일이면 DI-02 처럼
        민법 제161조로 늘림)의 다음 날부터 20%(하급심 다수: 서울고법 2017나28919 확정, 대전고법 2019나13573 심리불속행,
        14일째가 일요일이던 대전지법 2023나222268 은 제161조로 늘림). 재해고로 끝난 경우는 확정 고법 판결이 갈린다
        (대전고법 2019나13573 적용 / 서울고법 2021나2031970 부정) → `di_redismissal_20`. 두 옵션은 퇴직 전에 정기지급일이
        온 임금에만 쓴다 — 정기지급일이 퇴직 뒤인 임금은 DI-19.
      - 개정법 도래분을 해고기간 임금에 적용하는 1심은 세 갈래(서울북부 2026가합20004 지급일 다음날부터
        20%·배제 없음 / 서울중앙 2025가합10452 선고일까지 배제 / 창원 2025구합1375 선고 후 12%). 확정 고법 판결인
        서울고법 2025나208365 는 개정법 도래 해고기간 임금에 항소심 선고일까지 6%, 그 다음 날부터 20%를 붙였다(서울중앙 쪽).
        기본 계산에 20%를 쓰고(배제는 di_exclusion_end) '대안: 개정법 미적용' 결과를 함께 낸다.
DI-04 [법령] 20% 적용 제외(제37조 제3항, 시행령 제18조): 회생·파산 등, 자금 확보 곤란, 존부를 법원·
      노동위원회에서 다투는 것이 적절, 이에 준하는 사유 — "그 사유가 존속하는 기간"만. `exclusions[]`.
DI-05 [판례확립] 제18조 제3호 기준은 "사용자 주장에 상당한 근거"(대법원 2026. 4. 30. 선고 2026다200272,
      2022. 3. 31. 선고 2020다294486). 종기는 사실심 판결 선고일 — 당일까지 저율, 다음 날부터 20%.
      1심 일부 인용 후 항소심 유지도 원심 선고 시까지(2020다294486). 판결 확정일까지 배제한 판결은 없고
      서울고법 2019나2050152(확정) "판결 확정 이후에 이르러서야 … 적용된다고 볼 수는 없다" → `finality`
      선택 시 warning. 해고무효가 이미 확정되었으면 배제 없음(`dismissal_validity_settled`).
DI-06 [판례확립] 20% 미적용 구간: 사용자가 상인이면 6%, 비상인(의료법인·학교법인·비영리법인 등) 5%.
      `employer_merchant` 필수.
DI-07 [법령·판례확립] 소송촉진법 이율: 소장 부본 송달 다음 날부터. 다투는 것이 타당한 범위에서 사실심
      선고일까지 배제(제3조 제2항). 장래이행 부분 제외(이 모듈은 과거분만 받는다).
DI-08 [판례확립/하급심] 같은 날 이율을 겹치지 않는다. 우선순위 20% → 소송촉진법 → 6%/5%.
      회생 등 제18조 제1호 제외기간에 소송촉진법 이율을 붙인 사례는 약해서(서울서부 2019가단214470)
      기본 미적용, `di_sokchok_in_exclusion`.
DI-09 [판례확립·법령] 재직 중 임금 기본형: 정기지급일 다음 날부터 6%/5%, 송달 다음 날부터 소송촉진법 이율.
      근로관계가 끝난 뒤 정기지급일이 오는 임금은 DI-19 의 지급기일 다음 날부터.
DI-10 확정 지연손해금의 원금화: 구현하지 않음(원본이 상사채권일 때 이율 미확인) → 필요하면 수동 항목.
---------------------------------------------------------------- 일할·끝수·충당
DI-11 [불명확] `원금 × 연이율 × 기간`, 기산일·종기 모두 산입. 1년 이상이면 기산일부터 만 N년 + 잔여일수/분모.
      만 N년의 만료일은 민법 제160조(대응일 전날, 대응일이 없으면 그 월 말일 — 2. 29. 기산 1년은 다음 해 2. 28.까지).
      분모: 잔여기간에 2. 29.이 들면 366(`anniv_feb29`, 기본) / 잔여기간 종료연도가 윤년이면 366
      (`anniv_endyear_leap`) — 판결 골든 4건은 둘 다와 일치하고 2024. 3. 1.~12. 31.처럼 갈리는 경우는 판결
      미확인. 그 밖에 `calendar_split`(역년별 분모), `actual_365`.
DI-12 [실무관행] 구간별 산출 후 원 미만 버림, 합산(`floor_per_segment`) / 합계 후 버림(`floor_total`).
DI-13 [판례확립] 원금은 세전. 원천징수세액은 실제 납부한 경우 그 납부일에 원금에서 뺀다(대법원 2013다36347,
      다툼으로 소송에 이른 경우 달리 볼 여지 유보) → `payments[].kind = withholding` 은 원금 직접 감액 + warning.
      납부일 당일부터 줄어든 원금을 쓴다(변제충당 DI-14 와 달리 납부일 이자를 납부 전 원금에 붙이지 않는다).
DI-14 [법령] 변제충당: 이자(지연손해금) → 원본(민법 제479조). `payments[].kind = payment`.
      변제일까지는 변제 전 원금에 이자가 붙고, 줄어든 원금은 다음 날부터 적용한다(창원지법 2018가합52160 충당 이자
      363,464원 = 지급기일 다음 날부터 변제일까지). 이자 기산일 전(지급기일 당일 포함) 변제는 발생한 이자가 없으므로
      원본에 바로 충당하고 warning, 계산 기준일 뒤 변제는 반영하지 않고 warning.
DI-15 [법령·판례확립] 소멸시효 3년(근로기준법 제49조, 퇴직급여법 제10조). 임금은 정기지급일(퇴직 뒤 정기지급일이 오는
      임금은 DI-19)부터, 청산 금품은 지급사유 발생일(마지막 근무일 다음 날, DI-02 와 같은 방법으로 정함)부터. 초일 불산입 →
      만료일 = 기산일의 3년 뒤 해당일. 말일이 토·일요일·공휴일이면 다음 날(민법 제161조 — 서울서부지법 2013가단223120(확정)
      퇴직금 시효, `di_limitation_weekend_shift`. 공휴일은 DI-02 와 같이 셈한다). 소 제기일(`suit_filed_date`)이 만료일 뒤면
      '시효 완성 의심' 표시(재판 외 최고·일부청구는 사람이 판단). 청산 금품의 기산일은 0시에 시작하므로 초일 산입(민법
      제157조 단서 — 연차 모듈 AL-15 방식)으로 보면
      만료일이 '기산일 + 3년 − 1일'로 앞당겨진다. 두 규칙은 통일되지 않았으므로 그 날짜를 비고에 적고, 시효 완성
      의심은 이른 날짜로 판단한다(warning).
DI-16 DC형 부담금 지연이자(연 10%→20%): 범위 밖, 구현하지 않음.
DI-18 [법령] 근로기준법 적용 제외 사업(동거 친족만 사용하는 사업·가사 사용인, 제11조 제1항 단서)은 제37조 20% 없음
      → `lsa_not_applicable`. 상시 4명 이하 사업장은 시행령 별표 1이 제36조~제37조를 적용하므로 20% 적용.
      해고예고수당의 20% 대상 여부는 하급심이 갈려 warning 만(settlement 값은 사람이 정함).
검증: 반박 검증 메모(delay_interest_검증메모.md) 판정 반영. 검색 보강(결정례·유권해석 탭, 3페이지)은 하지 않았다.
DI-17 [법령] 청구 범위 제한: `di_claimed_rate_cap`(연 %) — 원고가 구한 이율보다 높게 계산하지 않는다.
DI-19 [법령·하급심/불명확] 근로관계가 끝난 뒤(last_working_day) 정기지급일이 오는 원금(Claim.settlement=False — 마지막 달
      임금·시간외수당 차액 등). 근로기준법 적용 제외 사업(DI-18)은 제36조가 없으므로 정기지급일 그대로 둔다. 이 경우를 정면으로
      다룬 판결은 찾지 못하였다(2026. 10. 21. LBOX 20개·법제처 6개 검색어).
      - 20%: 마지막 근무일 + 14일(토·일요일·공휴일이면 DI-02 처럼 민법 제161조로 늘림)의 다음 날부터. 정기지급일이 그보다
        늦어도 같다. 제36조 "근로자가 사망 또는 퇴직한
        경우에는 그 지급 사유가 발생한 때부터 14일 이내에 임금, 보상금, 그 밖의 모든 금품을 지급하여야 한다", 구 제37조 제1항
        "제36조에 따라 지급하여야 하는 임금 …의 전부 또는 일부를 그 지급 사유가 발생한 날부터 14일 이내에 지급하지 아니한 경우
        그 다음 날부터", 개정 제37조 제1항 제1호 "지급 사유가 발생한 날부터 14일이 되는 날". 퇴직자의 미지급 임금·수당·퇴직금에
        퇴직일부터 14일이 지난 다음 날부터 20%를 붙인 판결이 많고(대법원 2024다230084·2023다279983·2022다200249 자판,
        서울남부지법 2019가합109927 — 익월 20일 지급 사업장), 정기지급일 다음 날부터 붙인 판결은 찾지 못하였다.
        제36조 금품이므로 구법·개정법이 같고, 퇴직 전에 정기지급일이 온 임금에 쓰는 di_ended_old_law_20·di_redismissal_20 과도
        무관하다. 개정법 도래분도 정기지급일이 퇴직 뒤 14일 안에 오면 제1항 제2호(그 지급일 다음 날)가 아니라 제1호로 본다 —
        개정 제2항("지연이자를 지급할 의무가 발생한 이후 근로자가 사망 또는 퇴직한 경우")이 퇴직 전에 지연이자 의무가 생긴 임금만
        정기지급일 기준으로 남겨 두었고, 제36조가 퇴직 뒤 14일을 청산 기간으로 주기 때문이다. 연차 모듈 AL-14 의 같은 행(청산
        금품, DI-02)과 같다. 제1항 본문 '어느 하나에 해당하는'을 들어 이른 날(지급일 다음 날)로 보는 해석도 있을 수 있으나
        판결·고용노동부 해석은 찾지 못하였다. 개정 제2항을 해석한 판결도 없다(2026. 10. 21. LBOX). 구법 사안으로 정기지급일
        (매월 15일)이 퇴직 뒤 14일 안에 온 임금에 약정 지급일 다음 날부터 퇴직 + 14일까지 6%, 그다음 날부터 20%를 붙인
        수원지법 안산지원 2025가단63416 이 있다(아래 statutory_14 와 같다).
      - 6%/5% 시작 `di_post_retirement_due`: statutory_14(기본) = min(정기지급일, 마지막 근무일 + 14일) 다음 날부터 — 부산고법
        2018나57479 "임금 및 퇴직금에 대한 지연손해금은 퇴직일로부터 14일이 경과한 다음 날부터 발생한다고 봄이 타당하다"(원고의
        '퇴직 다음 날~14일째 5%' 청구를 받아들이지 않음. 지연이율은 대법원 2022다200249 로 파기자판되었고 자판도 같은 기산일),
        광주고법 2021나24973(퇴직금 — 14일 안에 이행청구를 받았으면 그 다음 날부터, 없었으면 14일 경과 다음 날부터),
        의정부지법 고양지원 2025가단55109(퇴직 다음 날부터 곧바로 지체책임을 진다는 청구 배척).
        day_after_retirement = 퇴직 다음 날부터 — 대법원 2025다219095 자판, 서울중앙지법 2022가단5203043, 서울북부지법
        2019가단120197(원고가 그렇게 구한 사안으로 보임). 지급기일은 연차 모듈 AL-14 '지급기일 전 퇴직'(min(지급일, 퇴직 + 14일))과
        같고, 퇴직금 RS-06 `rs_due_date` 도 같은 갈래다.
      - 시효(DI-15): 기산일 = min(정기지급일, 마지막 근무일 + 14일(제161조로 늘린 날)) — 서울중앙지법 2013가합89100(확정)은 퇴직자 임금채권의 변제기가
        늦어도 퇴직일로부터 14일이 경과한 날에 전부 도래하여 그때부터 시효가 진행된다고 하였다. 퇴직금을 퇴직 다음 날부터 행사할
        수 있다고 본 대법원 2001다24051 판결요지 [4]("사용자에게 위 기간 동안 임금이나 퇴직금 지급의무의 이행을 유예하여 준
        것이라고 볼 수는 없으므로")를 옮기면 더 이르므로, 퇴직 다음 날부터 초일 산입으로 센 날을 비고에 적고 시효 완성 의심은
        이른 날로 판단한다(warning). 약정 지급일(익월 15일)을 지급기일로 본 서울동부지법 2021가합116437(확정, 결론에 영향 없음)도 있다.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from functools import lru_cache

from .common import (
    Claim, LaborError, OptionSpec, Trace, add_months, dec, parse_date, round_money,
)

# ---------------------------------------------------------------- 옵션·규칙
OPTIONS: dict[str, OptionSpec] = {s.key: s for s in [
    OptionSpec("di_new_law_cutoff", "2025-10-22",
               "개정 제37조 제1항 제2호를 적용하는 첫 정기지급일", "DI-03"),
    OptionSpec("di_regime", "auto", "재직 중 정기임금의 20% 적용 방식", "DI-03", {
        "auto": "개정법 도래분(정기지급일 ≥ 경계일)은 지급일 다음 날부터 20%, 대안 결과를 함께 출력",
        "new_2ho_off": "개정법 도래분도 구법 규칙으로 계산 — 재직(복직) 중이면 20% 없음, 근로관계가 끝났으면 "
                       "퇴직 후 14일 경과 다음 날부터 20%(di_ended_old_law_20·di_redismissal_20). auto 의 '대안: 개정법 미적용'과 같음",
        "old_only": "new_2ho_off 와 같은 계산(별칭)",
    }),
    OptionSpec("di_ended_old_law_20", True,
               "구법 도래분(di_regime 이 auto 가 아니면 개정법 도래분 포함)이 퇴직(근로관계 종료) 때까지 미지급이면 "
               "퇴직 후 14일 경과 다음 날부터 20%(정기지급일이 퇴직 뒤인 임금은 이 옵션과 무관하게 20% — DI-19)", "DI-03"),
    OptionSpec("di_redismissal_20", True,
               "재해고로 근로관계가 끝난 경우에도 위 20% 적용(대전고법 2019나13573 / 반대 서울고법 2021나2031970)",
               "DI-03"),
    OptionSpec("di_exclusion_end", "final_fact_instance", "제18조 제3호·소송촉진법 제3조 제2항 배제 종기", "DI-05", {
        "final_fact_instance": "사실심 최종 선고일(항소심 선고일이 있으면 그날, 없으면 1심 선고일)",
        "first_instance": "1심 선고일",
        "none": "배제 없음(사용자가 다투지 않았거나 해고무효가 이미 확정)",
        "finality": "판결 확정일(근거 판결 없음 — 서울고법 2019나2050152 반대)",
    }),
    OptionSpec("di_sokchok_in_exclusion", False,
               "회생 등 20% 제외기간에 소송촉진법 이율 적용(근거 약함)", "DI-08"),
    OptionSpec("di_day_count", "anniv_feb29", "일할 계산 분모", "DI-11", {
        "anniv_feb29": "만 N년 + 잔여일수/(잔여기간에 2. 29. 포함 시 366, 아니면 365)",
        "anniv_endyear_leap": "만 N년 + 잔여일수/(잔여기간 종료연도 윤년이면 366)",
        "calendar_split": "역년별 일수/그해 일수 합",
        "actual_365": "총일수/365",
    }),
    OptionSpec("di_rounding", "floor_per_segment", "지연손해금 끝수", "DI-12", {
        "floor_per_segment": "구간별 원 미만 버림 후 합산",
        "floor_total": "원금 항목별 합계 후 원 미만 버림",
    }),
    OptionSpec("di_claimed_rate_cap", None, "원고가 구한 최고 이율(연 %). 비우면 제한 없음", "DI-17"),
    OptionSpec("di_limitation_weekend_shift", True,
               "시효 만료일이 토·일요일·공휴일이면 다음 날로(민법 제161조 — 서울서부지법 2013가단223120 확정)", "DI-15"),
    OptionSpec("di_deadline_holiday_shift", True,
               "제36조 14일 기한의 말일이 토·일요일·공휴일이면 다음 평일까지 늘림(민법 제161조 — 서울북부지법 2019나40407 등 "
               "6건, 반대 판결 없음). false 면 14일째 다음 날부터", "DI-02"),
    OptionSpec("di_post_retirement_due", "statutory_14",
               "퇴직 뒤 정기지급일이 오는 임금의 6%/5% 시작일(20%·시효 기산일은 바꾸지 않음)", "DI-19", {
        "statutory_14": "min(정기지급일, 마지막 근무일 + 14일) 다음 날부터(부산고법 2018나57479, 대법원 2022다200249 자판)",
        "day_after_retirement": "퇴직 다음 날부터(대법원 2025다219095 자판 등 — 원고가 그렇게 구한 사안으로 보임)",
    }),
]}

RULES: dict[str, tuple[str, str]] = {
    "DI-01": ("이율표(5%/6%/20%/소송촉진법 25→20→15→12%), 20%는 지급사유 발생일 2005. 7. 1. 이후분", "법령"),
    "DI-02": ("퇴직 청산 금품은 마지막 근무일 + 14일(토·일요일·공휴일이면 민법 제161조로 늘림) 다음 날부터 20%, "
              "합의로 연장했으면 연장된 지급기일 다음 날부터", "법령·판례확립/하급심"),
    "DI-03": ("재직 중 임금: 개정법 도래분 지급일 다음 날부터 20%, 구법분은 복직이면 없음·종료면 종료일 + 14일(제161조) 다음 날부터",
              "법령/판례확립/불명확"),
    "DI-04": ("20% 적용 제외 사유는 존속기간만", "법령"),
    "DI-05": ("다툼 적절 시 사실심 선고일까지 20% 배제", "판례확립"),
    "DI-06": ("20% 미적용 구간: 상인 6%, 비상인 5%", "판례확립"),
    "DI-07": ("소송촉진법 이율은 송달 다음 날부터, 다툼 타당 범위는 선고일까지 배제", "법령·판례확립"),
    "DI-08": ("같은 날 이율 중첩 없음: 20% → 소송촉진법 → 6%/5%", "판례확립"),
    "DI-09": ("재직 중 임금 기본형: 지급일 다음 날부터 6%/5%", "판례확립"),
    "DI-11": ("일할: 만 N년(민법 제160조) + 잔여일수/분모(분모 규칙 옵션)", "불명확"),
    "DI-12": ("구간별 원 미만 버림", "실무관행"),
    "DI-13": ("원금은 세전, 실제 납부한 원천세만 납부일에 감액", "판례확립"),
    "DI-14": ("변제충당: 이자 → 원본, 변제일까지는 변제 전 원금(창원지법 2018가합52160)", "법령·하급심"),
    "DI-15": ("소멸시효 3년 만료일 표시 — 청산 금품은 초일 산입 날짜를 함께 적고 이른 날로 완성 의심 판정", "법령·판례확립"),
    "DI-17": ("원고가 구한 이율 상한", "법령"),
    "DI-18": ("근로기준법 적용 제외 사업은 20% 없음, 해고예고수당 20% 여부는 경고", "법령/하급심"),
    "DI-19": ("퇴직 뒤 정기지급일이 오는 임금: 20%는 마지막 근무일 + 14일(제161조) 다음 날부터, 6%/5% 시작은 옵션, 시효는 "
              "min(정기지급일, 그 기한)부터(퇴직 다음 날 기산을 비고에)", "법령·하급심/불명확"),
}

LSA20_EFFECTIVE = date(2005, 7, 1)
LSA20 = Decimal("20")
SOKCHOK_TABLE = [   # (시행일, 연 %)
    (date(1981, 3, 1), Decimal("25")),
    (date(2003, 6, 1), Decimal("20")),
    (date(2015, 10, 1), Decimal("15")),
    (date(2019, 6, 1), Decimal("12")),
]
SOKCHOK_TRANSITIONS = (date(2015, 10, 1), date(2019, 6, 1))
END_CAUSES = {"retirement": "정년", "contract_end": "계약기간 만료", "resignation": "사직",
              "redismissal": "재해고", "death": "사망", "other": "기타"}


# ---------------------------------------------------------------- 입력
@dataclass
class Exclusion:
    start: date
    end: date
    reason: str = ""


@dataclass
class Payment:
    date: date
    amount: Decimal
    claim: str = ""          # 원금 항목 label. 비우면 적용하지 않고 warning
    kind: str = "payment"    # payment(이자 → 원본 충당) | withholding(원금 직접 감액)


@dataclass
class InterestInput:
    employer_merchant: bool
    calc_until: date | None = None
    service_date: date | None = None
    first_instance_judgment_date: date | None = None
    appellate_judgment_date: date | None = None
    finality_date: date | None = None
    first_instance_close_date: date | None = None
    suit_filed_date: date | None = None
    last_working_day: date | None = None      # 근로관계 종료 시 마지막 근무일(재직이면 None)
    end_cause: str = ""
    dismissal_validity_settled: bool = False
    lsa_not_applicable: bool = False          # 동거 친족만 사용하는 사업·가사 사용인(제11조 제1항 단서)
    exclusions: list[Exclusion] = field(default_factory=list)
    payments: list[Payment] = field(default_factory=list)
    items: list[Claim] = field(default_factory=list)   # 다른 모듈 밖에서 직접 넣는 원금
    holidays: frozenset = frozenset()         # 엔진이 모르는 공휴일(설·추석·부처님 오신 날·임시공휴일·선거일 등, DI-02)


def _d(v, label):
    if v in (None, ""):
        return None
    try:
        return parse_date(v)
    except Exception as exc:
        raise LaborError(f"interest.{label}: 날짜 형식이 아닙니다: {v!r}") from exc


_KEYS = {"employer_merchant", "calc_until", "service_date", "first_instance_judgment_date", "appellate_judgment_date",
         "finality_date", "first_instance_close_date", "suit_filed_date", "last_working_day", "end_cause",
         "dismissal_validity_settled", "lsa_not_applicable", "exclusions", "payments", "items", "holidays"}
_ITEM_KEYS = {"category", "label", "amount", "due_date", "settlement", "note"}
_PAYMENT_KEYS = {"date", "amount", "claim", "kind", "note"}      # note 는 계산에 쓰지 않는 메모(dismissal 절과 같음)
_EXCLUSION_KEYS = {"start", "end", "reason", "note"}
_KEY_HINTS = {"first_instance_closing_date": "dismissal 절 이름입니다 — interest 절은 first_instance_close_date"}


def _check_keys(v, keys: set, label: str) -> dict:
    """알 수 없는 키는 오류 — 오타 하나로 이율 구간·20%가 조용히 빠지지 않게 한다(다른 노동 모듈과 같은 규약)."""
    if not isinstance(v, dict):
        raise LaborError(f"{label} 은(는) 사전이어야 합니다: {v!r}")
    unknown = sorted(map(str, set(v) - keys))
    if unknown:
        hints = [f"{k}: {_KEY_HINTS[k]}" for k in unknown if k in _KEY_HINTS]
        raise LaborError(f"{label}{'' if label.endswith('절') else ' '}에 알 수 없는 키: {', '.join(unknown)}"
                         + (f" ({'; '.join(hints)})" if hints else "") + f". 가능: {', '.join(sorted(keys))}")
    return v


def load_interest(raw: dict | None, worker: dict | None = None) -> InterestInput:
    """사건.yaml `interest:` 절. 아래에 없는 키는 오류다(items·payments·exclusions 의 하위 키도 같다).

    interest:
      employer_merchant: true           # 필수(비우면 worker.employer_merchant). 회사=상인 6%, 비상인 5%
      calc_until: 2026-10-01            # 금액 계산 기준일. 비우면 구간표·문구만
      service_date: 2025-08-20          # 소장 부본 송달일
      first_instance_judgment_date: 2026-10-01   # 선고(예정)일
      appellate_judgment_date: null
      finality_date: null
      first_instance_close_date: null   # 소송촉진법 경과조치용 1심 변론종결일
      suit_filed_date: 2025-08-01       # 시효 표시
      last_working_day: null            # 근로관계 종료 시 마지막 근무일. 비우면 worker.last_working_day(재직이면 비움)
      end_cause: retirement             # 근로관계 종료 사유: retirement|contract_end|resignation|redismissal|death|other
      dismissal_validity_settled: false # 해고무효(구제명령)가 이미 확정·다툼 없음이면 true → 배제 없음
      lsa_not_applicable: false         # 근로기준법 적용 제외 사업(동거 친족만 사용·가사 사용인)이면 true
      exclusions: [{start: 2024-01-10, end: 2024-06-30, reason: 회생절차}]   # 제18조 제1·2·4호
      payments: [{date: 2026-01-05, amount: 1000000, claim: "2024. 3.분", kind: payment}]
      items: [{category: 해고예고수당, label: 해고예고수당, amount: 3000000, due_date: 2024-03-15, settlement: true, note: ""}]
      holidays: [2024-02-09, 2024-02-12]   # 설·추석·부처님 오신 날과 그 대체공휴일, 임시공휴일, 선거일(민법 제161조, DI-02).
                                        # 토·일요일과 양력 공휴일·그 대체공휴일은 엔진이 센다
    """
    raw = _check_keys(dict(raw or {}), _KEYS, "interest 절")
    worker = dict(worker or {})

    def pick(key):
        v = raw.get(key)
        return worker.get(key) if v in (None, "") else v

    merchant = pick("employer_merchant")
    if merchant is None:
        raise LaborError("interest.employer_merchant(사용자가 상인인지 여부)가 없습니다. "
                         "회사면 true(연 6%), 의료법인·학교법인·비영리법인·개인 비상인이면 false(연 5%).")
    end_cause = str(raw.get("end_cause") or "")
    if end_cause and end_cause not in END_CAUSES:
        raise LaborError(f"interest.end_cause 값 {end_cause!r} 은 허용되지 않습니다. 가능: {', '.join(END_CAUSES)}")
    items = []
    for i, it in enumerate(raw.get("items") or []):
        it = _check_keys(it, _ITEM_KEYS, f"interest.items[{i}]")
        for k in ("label", "amount", "due_date"):
            if it.get(k) in (None, ""):
                raise LaborError(f"interest.items[{i}].{k} 가 없습니다.")
        items.append(Claim(str(it.get("category") or "기타"), str(it["label"]), dec(it["amount"]),
                           _d(it["due_date"], f"items[{i}].due_date"), bool(it.get("settlement", False)),
                           str(it.get("note") or "")))
    pays = []
    for i, p in enumerate(raw.get("payments") or []):
        p = _check_keys(p, _PAYMENT_KEYS, f"interest.payments[{i}]")
        kind = str(p.get("kind") or "payment")
        if kind not in ("payment", "withholding"):
            raise LaborError(f"interest.payments[{i}].kind 는 payment 또는 withholding 입니다.")
        if p.get("date") in (None, "") or p.get("amount") in (None, ""):
            raise LaborError(f"interest.payments[{i}] 에 date·amount 가 필요합니다.")
        pays.append(Payment(_d(p["date"], f"payments[{i}].date"), dec(p["amount"]), str(p.get("claim") or ""), kind))
    excl = []
    for i, e in enumerate(raw.get("exclusions") or []):
        e = _check_keys(e, _EXCLUSION_KEYS, f"interest.exclusions[{i}]")
        s, t = _d(e.get("start"), f"exclusions[{i}].start"), _d(e.get("end"), f"exclusions[{i}].end")
        if not s or not t or t < s:
            raise LaborError(f"interest.exclusions[{i}] 의 start·end 가 없거나 순서가 맞지 않습니다.")
        excl.append(Exclusion(s, t, str(e.get("reason") or "")))
    hol = raw.get("holidays") or []
    if not isinstance(hol, (list, tuple)):
        raise LaborError(f"interest.holidays 는 날짜 목록이어야 합니다: {hol!r}")
    holidays = frozenset(_d(h, f"holidays[{i}]") for i, h in enumerate(hol) if h not in (None, ""))
    return InterestInput(
        employer_merchant=bool(merchant),
        calc_until=_d(raw.get("calc_until"), "calc_until"),
        service_date=_d(raw.get("service_date"), "service_date"),
        first_instance_judgment_date=_d(raw.get("first_instance_judgment_date"), "first_instance_judgment_date"),
        appellate_judgment_date=_d(raw.get("appellate_judgment_date"), "appellate_judgment_date"),
        finality_date=_d(raw.get("finality_date"), "finality_date"),
        first_instance_close_date=_d(raw.get("first_instance_close_date"), "first_instance_close_date"),
        suit_filed_date=_d(raw.get("suit_filed_date"), "suit_filed_date"),
        last_working_day=_d(pick("last_working_day"), "last_working_day"),
        end_cause=end_cause,
        dismissal_validity_settled=bool(raw.get("dismissal_validity_settled", False)),
        lsa_not_applicable=bool(raw.get("lsa_not_applicable", False)),
        exclusions=excl, payments=pays, items=items, holidays=holidays,
    )


# ---------------------------------------------------------------- 결과
@dataclass
class Segment:
    start: date
    end: date | None          # None = 다 갚는 날까지
    rate: Decimal
    rule: str                 # DI-xx
    basis: str                # '상사 6%', '근로기준법 20%', '소송촉진법 12%' 등


@dataclass
class InterestRow:
    claim: str
    category: str
    principal: Decimal
    start: date
    end: date
    days: int
    fraction: str             # '1년 + 45/366' 등
    rate: Decimal
    basis: str
    rule: str
    interest: Decimal


@dataclass
class LimitationRow:
    claim: str
    category: str
    start: date
    expiry: date
    suspect: bool | None      # 소 제기일이 없으면 None. 초일 산입 날짜(비고)가 더 이르면 그 날짜로 판단
    note: str = ""


@dataclass
class ClaimSchedule:
    claim: Claim
    segments: list[Segment]
    interest_total: Decimal = Decimal(0)
    order_text: str = ""


@dataclass
class InterestResult:
    rows: list[InterestRow]
    total: Decimal
    claims: list[Claim]
    trace: list[Trace]
    warnings: list[str]
    schedules: list[ClaimSchedule] = field(default_factory=list)
    limitation: list[LimitationRow] = field(default_factory=list)
    alternatives: dict = field(default_factory=dict)   # 이름 -> (합계, schedules) — 대안 계산
    order_text: str = ""


# ---------------------------------------------------------------- 날짜·이율
def _add_years(d: date, n: int) -> date:
    return add_months(d, 12 * n)


def _period_end(start: date, months: int) -> date:
    """start(초일 산입)부터 months 개월 기간의 만료일 — 민법 제160조 제2항(대응일 전날)·제3항(대응일이 없으면 그 월 말일).
    retirement.one_year_expiry(civil_code)·leave.period_span 과 같은 규칙."""
    target = add_months(start, months)
    return target if target.day != start.day else target - timedelta(days=1)


# ---------------------------------------------------------------- 공휴일(민법 제161조, DI-02·DI-15)
def _fixed_holidays(year: int) -> dict[date, str]:
    """관공서의 공휴일에 관한 규정 제2조 가운데 양력 날짜가 정해진 공휴일(일요일 제외, 2005년 이후 기준).
    제헌절은 2007. 12. 31.까지(2005. 6. 30. 개정 부칙 제2항 경과조치)와 2026. 5. 11.부터(2026. 4. 30. 개정 — 국경일 전부),
    한글날은 2012. 12. 28. 개정부터, 노동절은 2026. 5. 1.부터 공휴일이다. 식목일은 2005. 6. 30. 개정으로 빠졌다."""
    days = {date(year, 1, 1): "1월 1일", date(year, 3, 1): "3·1절", date(year, 5, 5): "어린이날",
            date(year, 6, 6): "현충일", date(year, 8, 15): "광복절", date(year, 10, 3): "개천절",
            date(year, 12, 25): "기독탄신일"}
    if year <= 2007 or date(year, 7, 17) >= date(2026, 5, 11):
        days[date(year, 7, 17)] = "제헌절"
    if date(year, 10, 9) >= date(2012, 12, 28):
        days[date(year, 10, 9)] = "한글날"
    if date(year, 5, 1) >= date(2026, 5, 1):
        days[date(year, 5, 1)] = "노동절"
    if date(year, 4, 5) < date(2005, 6, 30):
        days[date(year, 4, 5)] = "식목일"
    return days


@lru_cache(maxsize=None)
def _holidays_of(year: int, extra: frozenset) -> frozenset:
    """그해 공휴일(일요일 제외) — 양력 공휴일, 사람이 넣은 날(interest.holidays), 양력 공휴일에서 생기는 대체공휴일(제3조).
    대체공휴일: 2013. 11. 5. 신설 때는 어린이날이 토요일이나 다른 공휴일과 겹칠 때만, 2021. 8. 4. 전문개정부터 국경일·어린이날이
    토·일요일과 겹치거나 평일에 다른 공휴일과 겹칠 때(대체공휴일이 토요일이면 그 다음), 2023. 5. 4. 기독탄신일, 2026. 5. 1.
    노동절, 2026. 5. 11. 제헌절이 대상에 들었다. 설·추석·부처님 오신 날의 대체공휴일은 사람이 넣는다."""
    fixed = _fixed_holidays(year)
    extra_year = {d for d in extra if d.year == year}
    days = set(fixed) | extra_year

    def off(x: date) -> bool:              # 제2조의 공휴일(일요일 포함)
        return x.weekday() == 6 or x in days

    for d, name in sorted(fixed.items()):
        if d < date(2013, 11, 5):
            continue
        if d < date(2021, 8, 4):
            hit, skip_saturday = name == "어린이날" and (d.weekday() >= 5 or d in extra_year), False
        else:
            subject = {"3·1절", "광복절", "개천절", "한글날", "어린이날"}
            if d >= date(2023, 5, 4):
                subject.add("기독탄신일")
            if d >= date(2026, 5, 1):
                subject.add("노동절")
            if d >= date(2026, 5, 11):
                subject.add("제헌절")
            hit, skip_saturday = name in subject and (d.weekday() >= 5 or d in extra_year), True
        if hit:
            x = d + timedelta(days=1)
            while off(x) or (skip_saturday and x.weekday() == 5):
                x += timedelta(days=1)
            days.add(x)
    return frozenset(days)


def _is_rest(d: date, extra: frozenset) -> bool:
    """민법 제161조의 '토요일 또는 공휴일'(일요일은 공휴일)."""
    return d.weekday() >= 5 or d in _holidays_of(d.year, extra)


def _next_business_day(d: date, extra: frozenset) -> date:
    while _is_rest(d, extra):
        d += timedelta(days=1)
    return d


def _deadline(raw: date, inp: "InterestInput", o: dict) -> date:
    """제36조 14일 기한의 말일 — 14일째가 토·일요일·공휴일이면 민법 제161조로 그 다음 평일(DI-02 di_deadline_holiday_shift)."""
    return _next_business_day(raw, inp.holidays) if o["di_deadline_holiday_shift"] else raw


def _weekday(d: date) -> str:
    return f"{_fmt(d)}({'월화수목금토일'[d.weekday()]})"


def year_fraction(start: date, end: date, mode: str) -> tuple[Decimal, str]:
    """[start, end] 양끝 포함 기간의 연 환산값과 설명(DI-11). 만 N년은 민법 제160조로 센다."""
    days = (end - start).days + 1
    if mode == "actual_365":
        return Decimal(days) / 365, f"{days}/365"
    if mode == "calendar_split":
        total, parts = Decimal(0), []
        for y in range(start.year, end.year + 1):
            a, b = max(start, date(y, 1, 1)), min(end, date(y, 12, 31))
            n, den = (b - a).days + 1, 366 if calendar.isleap(y) else 365
            total += Decimal(n) / den
            parts.append(f"{n}/{den}")
        return total, " + ".join(parts)
    n = 0
    while _period_end(start, 12 * (n + 1)) <= end:
        n += 1
    rest_start = start if n == 0 else _period_end(start, 12 * n) + timedelta(days=1)
    if rest_start > end:
        return Decimal(n), f"{n}년"
    rem = (end - rest_start).days + 1
    if mode == "anniv_feb29":
        den = 366 if any(calendar.isleap(y) and rest_start <= date(y, 2, 29) <= end
                         for y in range(rest_start.year, end.year + 1)) else 365
    elif mode == "anniv_endyear_leap":
        den = 366 if calendar.isleap(end.year) else 365
    else:
        raise LaborError(f"일할 방식을 알 수 없습니다: {mode}")
    return Decimal(n) + Decimal(rem) / den, (f"{n}년 + " if n else "") + f"{rem}/{den}"


def sokchok_rate(d: date, close: date | None = None) -> Decimal | None:
    """소송촉진법 법정이율(DI-01). close = 1심 변론종결일(2015·2019 경과조치)."""
    def table(x: date) -> Decimal | None:
        rate = None
        for since, r in SOKCHOK_TABLE:
            if x >= since:
                rate = r
        return rate

    if close is not None and close < d and any(close < c <= d for c in SOKCHOK_TRANSITIONS):
        return table(close)
    return table(d)


# ---------------------------------------------------------------- 계산
def _exclusion_end(inp: InterestInput, o: dict, warnings: list) -> date | None:
    mode = o["di_exclusion_end"]
    if inp.dismissal_validity_settled or mode == "none":
        return None
    if mode == "first_instance":
        return inp.first_instance_judgment_date
    if mode == "finality":
        warnings.append("배제 종기를 판결 확정일로 두었습니다. 확정일까지 배제한 판결은 확인되지 않았고 "
                        "서울고법 2019나2050152(확정)는 '판결 확정 이후에 이르러서야 … 적용된다고 볼 수는 없다'고 했습니다.")
        return inp.finality_date
    return inp.appellate_judgment_date or inp.first_instance_judgment_date


def _settle_trigger(c: Claim, inp: InterestInput) -> date:
    """청산 금품의 지급사유 발생일(DI-02·DI-15). 원금 항목의 trigger_date 속성 → 마지막 근무일 다음 날 →
    due_date − 13일(due_date 가 마지막 근무일 + 14일이라는 규약) 순으로 정한다."""
    explicit = getattr(c, "trigger_date", None)
    if explicit is not None:
        return explicit
    if inp.last_working_day is not None:
        return inp.last_working_day + timedelta(days=1)
    return c.due_date - timedelta(days=13)


def _after_retirement(c: Claim, inp: InterestInput) -> bool:
    """근로관계가 끝난 뒤 정기지급일이 오는 원금인가(DI-19). 청산 금품(원금을 만든 모듈이 due_date 를 정함, DI-02)과
    근로기준법 적용 제외 사업(제36조 없음)은 아니다."""
    end = inp.last_working_day
    return not c.settlement and end is not None and not inp.lsa_not_applicable and c.due_date > end


def _due36(c: Claim, inp: InterestInput, o: dict) -> date:
    """20%·시효에 쓰는 지급기일. 청산 금품은 due_date 가 제36조 기한(지급사유 발생일부터 14일이 되는 날)이고 그날이
    토·일요일·공휴일이면 민법 제161조로 늘린 날, 그 밖에는 due_date(그보다 이른 지급일·합의로 연장한 지급기일, DI-02).
    퇴직 뒤 정기지급일이 오는 임금은 min(정기지급일, 늘린 기한)(DI-19). 근로기준법 적용 제외 사업은 due_date 그대로."""
    if c.settlement and not inp.lsa_not_applicable:
        raw = _settle_trigger(c, inp) + timedelta(days=13)
        deadline = _deadline(raw, inp, o)
        return deadline if raw <= c.due_date <= deadline else c.due_date
    if not _after_retirement(c, inp):
        return c.due_date
    return min(c.due_date, _deadline(inp.last_working_day + timedelta(days=14), inp, o))


def _due(c: Claim, inp: InterestInput, o: dict) -> date:
    """6%/5% 구간이 시작하는 날의 전날(DI-19 `di_post_retirement_due`). day_after_retirement 이면 퇴직 뒤 정기지급일이
    오는 임금은 마지막 근무일 — 퇴직 다음 날부터 6%/5%."""
    if o["di_post_retirement_due"] == "day_after_retirement" and _after_retirement(c, inp):
        return inp.last_working_day
    return _due36(c, inp, o)


def _holiday_note(raw: date, deadline: date) -> str:
    return (f" — 14일째 {_weekday(raw)}가 토·일요일·공휴일이라 {_weekday(deadline)}까지(민법 제161조)"
            if deadline > raw else "")


def _lsa20_start(c: Claim, inp: InterestInput, o: dict, regime: str, trace: list, warnings: list) -> tuple[date | None, str]:
    """20% 기산일과 근거 문구. 적용 없으면 (None, 사유)."""
    if inp.lsa_not_applicable:
        return None, "근로기준법 적용 제외 사업(제11조 제1항 단서) — 제37조 없음"
    if c.settlement:
        trigger = _settle_trigger(c, inp)
        if trigger < LSA20_EFFECTIVE:
            return None, "지급사유 발생일이 2005. 7. 1. 전(DI-01)"
        raw = trigger + timedelta(days=13)               # 지급사유 발생일부터 14일이 되는 날
        deadline = _deadline(raw, inp, o)
        why = "퇴직 청산 금품 14일 경과(DI-02)" + _holiday_note(raw, deadline)
        if c.due_date < raw:
            why += f" — 지급기일 {_fmt(c.due_date)} 다음 날부터 {_fmt(deadline)}까지는 20% 아님"
        elif c.due_date > deadline:
            why += f" — 합의로 연장한 지급기일 {_fmt(c.due_date)} 다음 날부터"
        return max(c.due_date, deadline) + timedelta(days=1), why

    end = inp.last_working_day
    if _after_retirement(c, inp):
        # 정기지급일이 퇴직 뒤인 임금은 제36조 금품 — 구법·개정법(제1항 제1호) 모두 퇴직 후 14일 경과 다음 날부터(DI-19)
        if end + timedelta(days=1) < LSA20_EFFECTIVE:
            return None, "지급사유 발생일이 2005. 7. 1. 전(DI-01)"
        raw = end + timedelta(days=14)
        deadline = _deadline(raw, inp, o)
        why = (f"퇴직 뒤 정기지급일({_fmt(c.due_date)}) — 퇴직 후 14일 경과(제36조·제37조 제1항, DI-19)"
               + _holiday_note(raw, deadline))
        if deadline < c.due_date:
            why += f" — 정기지급일이 제36조 기한 {_fmt(deadline)}보다 늦어 기한 다음 날부터"
        return deadline + timedelta(days=1), why

    cutoff = parse_date(o["di_new_law_cutoff"])
    if regime == "auto" and c.due_date >= cutoff:
        return c.due_date + timedelta(days=1), "개정 제37조 제1항 제2호 정기지급일 경과(DI-03, 불명확)"

    if end is None or not o["di_ended_old_law_20"]:
        return None, "재직(복직) 중 구법 적용분(DI-03, 2014다28305)"
    if inp.end_cause == "redismissal" and not o["di_redismissal_20"]:
        return None, "재해고로 종료 — 20% 미적용 옵션(서울고법 2021나2031970)"
    if end + timedelta(days=15) < LSA20_EFFECTIVE:
        return None, "퇴직일이 2005. 7. 1. 전(DI-01)"
    raw = end + timedelta(days=14)
    deadline = _deadline(raw, inp, o)
    return deadline + timedelta(days=1), "근로관계 종료 후 14일 경과(DI-03, 하급심 다수)" + _holiday_note(raw, deadline)


def _schedule(c: Claim, inp: InterestInput, o: dict, regime: str, trace: list, warnings: list) -> list[Segment]:
    base_rate = Decimal("6") if inp.employer_merchant else Decimal("5")
    base_label = "상사 6%" if inp.employer_merchant else "민사 5%"
    due = _due(c, inp, o)
    start = due + timedelta(days=1)
    lsa_start, lsa_why = _lsa20_start(c, inp, o, regime, trace, warnings)
    lsa_rule = "DI-02" if c.settlement else ("DI-19" if _after_retirement(c, inp) else "DI-03")
    excl_end = _exclusion_end(inp, o, warnings)
    sok_start = inp.service_date + timedelta(days=1) if inp.service_date else None
    cap = dec(o.get("di_claimed_rate_cap"))

    # 이율이 바뀔 수 있는 날을 모두 모은다.
    points = {start}
    for p in (lsa_start, sok_start, excl_end and excl_end + timedelta(days=1)):
        if p and p > start:
            points.add(p)
    for e in inp.exclusions:
        for p in (e.start, e.end + timedelta(days=1)):
            if p > start:
                points.add(p)
    for since, _ in SOKCHOK_TABLE:
        if since > start:
            points.add(since)
    ordered = sorted(points)

    def rate_on(d: date) -> tuple[Decimal, str, str]:
        in_dispute = excl_end is not None and d <= excl_end
        in_other_excl = any(e.start <= d <= e.end for e in inp.exclusions)
        if lsa_start and d >= lsa_start and not in_dispute and not in_other_excl:
            return LSA20, "근로기준법 20%", lsa_rule
        if sok_start and d >= sok_start and not in_dispute and (not in_other_excl or o["di_sokchok_in_exclusion"]):
            r = sokchok_rate(d, inp.first_instance_close_date)
            if r is not None:
                return r, f"소송촉진법 {r}%", "DI-07"
        return base_rate, base_label, "DI-06" if lsa_start else "DI-09"

    segs: list[Segment] = []
    for i, s in enumerate(ordered):
        e = ordered[i + 1] - timedelta(days=1) if i + 1 < len(ordered) else None
        r, label, rule = rate_on(s)
        if cap is not None and r > cap:
            r, label = cap, f"{label} → 청구 상한 {cap}%"
        if segs and segs[-1].rate == r and segs[-1].basis == label:
            segs[-1].end = e
        else:
            segs.append(Segment(s, e, r, rule, label))
    due36 = _due36(c, inp, o)
    if due36 > c.due_date:
        trace.append(Trace("DI-02", f"{c.label} 지급기일", _fmt(due36),
                           f"지급기일 {_weekday(c.due_date)}이 토·일요일·공휴일이라 민법 제161조로 늘림"))
    elif due36 < c.due_date:
        trace.append(Trace("DI-19", f"{c.label} 지급기일", _fmt(due36),
                           f"정기지급일 {_fmt(c.due_date)}이 마지막 근무일 + 14일(제36조)보다 늦음"))
    if due < due36:
        trace.append(Trace("DI-19", f"{c.label} 6%/5% 시작", _fmt(start),
                           "퇴직 다음 날부터(di_post_retirement_due=day_after_retirement)"))
    trace.append(Trace(lsa_rule, f"{c.label} 20% 판단", lsa_why))
    return segs


def _fmt(d: date) -> str:
    return f"{d.year}. {d.month}. {d.day}."


def _order_text(c: Claim, segs: list[Segment]) -> str:
    parts = []
    for s in segs:
        if s.end is None:
            parts.append(f"{_fmt(s.start)}부터 다 갚는 날까지 연 {s.rate}%" if not parts
                         else f"그 다음 날부터 다 갚는 날까지 연 {s.rate}%")
        else:
            parts.append(f"{_fmt(s.start)}부터 {_fmt(s.end)}까지 연 {s.rate}%" if not parts
                         else f"그 다음 날부터 {_fmt(s.end)}까지 연 {s.rate}%")
    return f"{int(c.amount):,}원에 대하여 " + ", ".join(parts)


def _withholding_warning(c: Claim, p: Payment) -> str:
    return (f"{c.label}: 원천세 {int(p.amount):,}원을 {_fmt(p.date)}에 원금에서 뺐습니다. "
            "실제 납부한 경우에만 뺄 수 있고(대법원 2013다36347), 다툼으로 소송에 이른 경우 달리 볼 여지가 있습니다.")


def _accrue(c: Claim, segs: list[Segment], until: date, pays: list[Payment], o: dict,
            rows: list[InterestRow], warnings: list) -> Decimal:
    """기준일까지 금액. 변제·원천세가 있으면 그 날짜로 구간을 더 나눈다.

    변제(payment)는 변제일까지 변제 전 원금에 이자를 붙이고 이자 → 원본 순으로 충당해 다음 날부터 줄어든 원금을
    쓴다(DI-14, 창원지법 2018가합52160). 원천세(withholding)는 납부일부터 줄어든 원금을 쓴다(DI-13).
    이자 기산일 전(지급기일 당일 포함) 변제·원천세는 발생한 이자가 없으므로 원금에서 바로 뺀다.
    """
    principal = c.amount
    unpaid_interest = Decimal(0)
    # 같은 날이면 원천세(그날부터 감액)를 변제(그날 이자까지 붙인 뒤 충당)보다 먼저 처리 — 입력 순서와 무관하게
    events = sorted(pays, key=lambda p: (p.date, p.kind != "withholding"))
    first = segs[0].start if segs else c.due_date + timedelta(days=1)
    for p in events:
        if p.date < first:
            principal = max(principal - p.amount, Decimal(0))
            warnings.append(_withholding_warning(c, p) if p.kind == "withholding" else
                            f"{c.label}: {_fmt(p.date)} 변제 {int(p.amount):,}원은 이자 기산일({_fmt(first)}) 전이라 "
                            "발생한 지연손해금이 없어 원금에서 바로 뺐습니다(DI-14).")
        elif p.date > until:
            warnings.append(f"{c.label}: {_fmt(p.date)} {'원천세' if p.kind == 'withholding' else '변제'} "
                            f"{int(p.amount):,}원은 계산 기준일({_fmt(until)}) 뒤라 반영하지 않았습니다.")
    cuts = []
    for s in segs:
        if s.start > until:
            break
        cuts.append((s.start, min(s.end or until, until), s))
    total = Decimal(0)
    for s_start, s_end, seg in cuts:
        cur = s_start
        for p in [p for p in events if s_start <= p.date <= s_end] + [None]:
            if p is None:
                stop = s_end
            elif p.kind == "withholding":
                stop = p.date - timedelta(days=1)    # 납부일부터 줄어든 원금(DI-13)
            else:
                stop = p.date                        # 변제일까지 변제 전 원금(DI-14)
            if stop >= cur and principal > 0:
                frac, desc = year_fraction(cur, stop, o["di_day_count"])
                raw = principal * seg.rate / 100 * frac
                amt = round_money(raw) if o["di_rounding"] == "floor_per_segment" else raw
                rows.append(InterestRow(c.label, c.category, principal, cur, stop, (stop - cur).days + 1,
                                        desc, seg.rate, seg.basis, seg.rule, amt))
                unpaid_interest += amt
                total += amt
            if p is not None:
                if p.kind == "withholding":
                    principal = max(principal - p.amount, Decimal(0))
                    warnings.append(_withholding_warning(c, p))
                else:
                    to_interest = min(p.amount, unpaid_interest)
                    unpaid_interest -= to_interest
                    principal = max(principal - (p.amount - to_interest), Decimal(0))
                cur = max(cur, stop + timedelta(days=1))
    if o["di_rounding"] == "floor_total":
        total = round_money(total)
    return total


def _limitation(c: Claim, inp: InterestInput, o: dict) -> tuple[LimitationRow, date | None, str]:
    """(시효 표시 행, 더 이른 만료일 또는 None, 그 날짜의 근거 'settlement'·'post_retirement') — DI-15·DI-19."""
    start = _settle_trigger(c, inp) if c.settlement else _due36(c, inp, o)
    expiry = _add_years(start, 3)
    if o["di_limitation_weekend_shift"]:
        expiry = _next_business_day(expiry, inp.holidays)       # 토·일요일·공휴일(민법 제161조)
    early, kind, notes = None, "", []
    if c.settlement:
        # 지급사유 발생일(퇴직 다음 날)은 0시에 시작 — 초일 산입(민법 제157조 단서)이면 '기산일 + 3년 − 1일'(연차 AL-15)
        alt = _period_end(start, 36)
        if alt < expiry:
            early, kind = alt, "settlement"
            notes.append(f"초일 산입(민법 제157조 단서 — 연차 모듈 AL-15 방식)이면 {_fmt(alt)} 만료. "
                         "두 규칙이 통일되지 않아 시효 완성 의심은 이 날짜로 판단")
    elif _after_retirement(c, inp):
        if start < c.due_date:
            notes.append(f"정기지급일 {_fmt(c.due_date)}이 제36조 기한보다 늦어 기한 {_fmt(start)}을 기산일로 봄(DI-19)")
        # 퇴직금처럼 퇴직 다음 날부터 행사할 수 있다고 보면(대법원 2001다24051) 더 이르다 — 청산 금품과 같이 초일 산입으로 센다
        alt = _period_end(inp.last_working_day + timedelta(days=1), 36)
        if alt < expiry:
            early, kind = alt, "post_retirement"
            notes.append(f"퇴직 다음 날부터 초일 산입으로 세면(대법원 2001다24051 의 퇴직금 논리) {_fmt(alt)} 만료. "
                         "규칙이 통일되지 않아 시효 완성 의심은 이 날짜로 판단(DI-19)")
    check = early or expiry
    suspect = None if inp.suit_filed_date is None else inp.suit_filed_date > check
    return LimitationRow(c.label, c.category, start, expiry, suspect, "; ".join(notes)), early, kind


def _run(claims: list[Claim], inp: InterestInput, o: dict, regime: str, trace, warnings, rows) -> tuple[Decimal, list[ClaimSchedule]]:
    total = Decimal(0)
    schedules = []
    for c in claims:
        if c.amount <= 0:
            continue
        segs = _schedule(c, inp, o, regime, trace, warnings)
        sch = ClaimSchedule(c, segs, order_text=_order_text(c, segs))
        if inp.calc_until and inp.calc_until > _due(c, inp, o):
            pays = [p for p in inp.payments if p.claim == c.label]
            sch.interest_total = _accrue(c, segs, inp.calc_until, pays, o, rows, warnings)
            total += sch.interest_total
        schedules.append(sch)
    return total, schedules


def calculate_interest(inp: InterestInput, opts: dict, claims: list[Claim] | None = None) -> InterestResult:
    o = {k: (opts or {}).get(k, s.default) for k, s in OPTIONS.items()}
    trace: list[Trace] = []
    warnings: list[str] = []
    all_claims = list(claims or []) + list(inp.items)
    if not all_claims:
        return InterestResult([], Decimal(0), [], trace, ["지연손해금을 계산할 원금 항목이 없습니다."])

    labels = {c.label for c in all_claims}
    for p in inp.payments:
        if p.claim not in labels:
            warnings.append(f"변제 {_fmt(p.date)} {int(p.amount):,}원은 claim 이름이 원금 항목과 맞지 않아 반영하지 않았습니다.")
    if inp.last_working_day is None and any(c.settlement and getattr(c, "trigger_date", None) is None
                                            for c in all_claims if c.amount > 0):
        warnings.append("마지막 근무일(worker.last_working_day 또는 interest.last_working_day)이 없어 청산 금품의 "
                        "지급사유 발생일을 지급기일 − 13일(지급기일 = 마지막 근무일 + 14일 규약)로 보았습니다. 지급기일이 그와 다르면"
                        "(퇴직금 rs_due_date=day_after_retirement, 퇴직 직후 지급기일의 연차수당 등) 20% 기산일과 시효 기산일이 "
                        "틀리므로 마지막 근무일을 적으십시오(DI-02·DI-15).")
    if inp.first_instance_close_date and inp.first_instance_close_date < date(2003, 6, 1):
        warnings.append("1심 변론종결일이 2003. 6. 1. 전입니다. 2003년 소송촉진법 이율 개정 부칙은 확인되지 않아 경과조치를 적용하지 않았습니다.")
    for c in all_claims:
        if "해고예고" in c.category or "해고예고" in c.label:
            warnings.append(f"{c.label}: 해고예고수당이 연 20% 대상인지는 판결이 갈립니다"
                            "(원금에 넣어 20% — 대전지법 2018가합107477 / 12% — 성남지원 2023가단208164). "
                            "settlement 값으로 계산 방식을 정했는지 확인하세요.")
        if c.settlement and c.amount > 0 and not inp.lsa_not_applicable:
            deadline = _deadline(_settle_trigger(c, inp) + timedelta(days=13), inp, o)
            if c.due_date > deadline:
                warnings.append(f"{c.label}: 지급기일 {_fmt(c.due_date)}이 지급사유 발생일부터 14일이 되는 날({_fmt(deadline)})보다 "
                                "늦어 합의로 연장한 지급기일로 보고 그 다음 날부터 지연손해금·20%를 셈하였습니다(인천지법 부천지원 "
                                "2020가단270 등, DI-02). 연장 합의(제36조 단서·퇴직급여법 제9조 단서)가 증명되지 않으면 기한 다음 날부터이므로 "
                                f"지급기일을 {_fmt(deadline)}로 고치고, 정기지급일이 있는 임금이면 settlement 를 false 로 넣으십시오(DI-19).")
    if o["di_deadline_holiday_shift"]:
        raws = {_settle_trigger(c, inp) + timedelta(days=13) for c in all_claims
                if c.settlement and c.amount > 0 and not inp.lsa_not_applicable}
        if inp.last_working_day is not None and not inp.lsa_not_applicable \
                and any(not c.settlement and c.amount > 0 for c in all_claims):
            raws.add(inp.last_working_day + timedelta(days=14))
        if raws:
            shown = ", ".join(_weekday(d) + (f" → {_weekday(_deadline(d, inp, o))}" if _deadline(d, inp, o) > d else "")
                              for d in sorted(raws))
            warnings.append(f"제36조 14일 기한(지급사유 발생일부터 14일이 되는 날): {shown}. 토·일요일·공휴일이면 민법 제161조로 "
                            "다음 평일까지 늘렸습니다(서울북부지법 2019나40407 등, DI-02). 엔진은 양력 공휴일과 그 대체공휴일만 알고 "
                            "설·추석·부처님 오신 날(과 그 대체공휴일)·임시공휴일·선거일은 모르므로, 기한이 그런 날이면 "
                            "interest.holidays 에 적어 다시 계산하십시오(시효 만료일도 같습니다).")
    if inp.end_cause == "redismissal" and inp.last_working_day:
        warnings.append("재해고로 근로관계가 끝난 경우 구법 도래분 20% 적용은 확정 고법 판결이 갈립니다"
                        "(적용: 대전고법 2019나13573 / 부정: 서울고법 2021나2031970).")
    if o["di_exclusion_end"] == "final_fact_instance" and not inp.dismissal_validity_settled \
            and not (inp.first_instance_judgment_date or inp.appellate_judgment_date):
        warnings.append("선고(예정)일이 없어 20%·소송촉진법 배제기간을 두지 않았습니다. 사용자 주장에 상당한 근거가 있으면 "
                        "사실심 선고일까지 배제됩니다(대법원 2026다200272). 선고 예정일을 넣어 다시 계산하세요.")

    regime = o["di_regime"]
    rows: list[InterestRow] = []
    total, schedules = _run(all_claims, inp, o, regime, trace, warnings, rows)

    alternatives = {}
    cutoff = parse_date(o["di_new_law_cutoff"])
    # 정기지급일이 퇴직 뒤인 임금은 제1항 제2호가 아니라 제1호(DI-19)라 대안과 경고가 필요 없다
    if regime == "auto" and any(not c.settlement and c.due_date >= cutoff and not _after_retirement(c, inp)
                                for c in all_claims):
        warnings.append("개정 근로기준법 제37조 제1항 제2호(2025. 10. 23. 시행)를 해고기간 등 다툼이 있는 임금에 적용하는 방식은 "
                        "1심 판결이 갈리고(서울북부 2026가합20004 / 서울중앙 2025가합10452 / 창원 2025구합1375) "
                        "확정 고법 판결은 항소심 선고일까지 6%, 그 다음 날부터 20%를 붙인 서울고법 2025나208365 이고 대법원 판단은 "
                        "없습니다. '대안: 개정법 미적용' 결과를 함께 확인하세요.")
        alt_total, alt_sched = _run(all_claims, inp, o, "new_2ho_off", [], [], [])
        alternatives["개정법 미적용"] = (alt_total, alt_sched)
    if not inp.dismissal_validity_settled and o["di_exclusion_end"] != "none":
        max_o = dict(o, di_exclusion_end="none")
        cm_total, cm_sched = _run(all_claims, inp, max_o, regime, [], [], [])
        alternatives["청구 최대(배제 없음)"] = (cm_total, cm_sched)

    limitation = []
    early_kinds = set()
    for c in all_claims:
        if c.amount <= 0:
            continue
        lr, early, kind = _limitation(c, inp, o)
        limitation.append(lr)
        if early is not None:
            early_kinds.add(kind)
        if not lr.suspect:
            continue
        if inp.suit_filed_date > lr.expiry:
            warnings.append(f"{lr.claim}: 시효 만료일 {_fmt(lr.expiry)}이 소 제기일보다 앞섭니다. 최고·승인 등 중단 사유를 확인하세요.")
        elif kind == "post_retirement":
            warnings.append(f"{lr.claim}: 퇴직 다음 날부터 초일 산입으로 세면(대법원 2001다24051 의 퇴직금 논리) 시효 만료일 "
                            f"{_fmt(early)}이 소 제기일보다 앞섭니다(지급기일 기준이면 {_fmt(lr.expiry)}까지). 규칙이 통일되지 "
                            "않았으므로 최고·승인 등 중단 사유를 확인하세요.")
        else:
            warnings.append(f"{lr.claim}: 초일 산입(민법 제157조 단서)으로 보면 시효 만료일 {_fmt(early)}이 소 제기일보다 앞섭니다"
                            f"(초일 불산입이면 {_fmt(lr.expiry)}까지). 규칙이 통일되지 않았으므로 최고·승인 등 중단 사유를 확인하세요.")
    if "settlement" in early_kinds:
        warnings.append("청산 금품의 시효 만료일은 초일 불산입(DI-15)으로 적었습니다. 기산일(마지막 근무일 다음 날)이 0시에 "
                        "시작하므로 초일 산입(민법 제157조 단서 — 연차휴가수당 시트의 시효 완성일, AL-15)이면 더 이른 날이 "
                        "만료일입니다(소멸시효 시트 비고). 두 규칙은 통일되지 않았으니 청구 시기는 이른 날짜를 기준으로 판단하세요.")
    if "post_retirement" in early_kinds:
        warnings.append("퇴직 뒤 정기지급일이 오는 임금(DI-19)의 시효 만료일은 지급기일 min(정기지급일, 마지막 근무일 + 14일)부터 "
                        "적었습니다(서울중앙지법 2013가합89100). 퇴직금을 퇴직 다음 날부터 행사할 수 있다고 본 대법원 2001다24051 의 "
                        "논리를 옮기면 더 이른 날이 만료일입니다(소멸시효 시트 비고). 판결이 통일되지 않았으니 청구 시기는 이른 날짜를 "
                        "기준으로 판단하세요.")
    if inp.suit_filed_date is None:
        warnings.append("소 제기일이 없어 시효 완성 여부는 표시하지 않고 만료일만 적었습니다.")

    trace.append(Trace("DI-06", "20% 미적용 구간 이율", "상사 6%" if inp.employer_merchant else "민사 5%"))
    trace.append(Trace("DI-11", "일할 분모", o["di_day_count"], "판결로 갈리지 않는 분모 규칙 — 옵션"))
    if inp.calc_until:
        trace.append(Trace("DI-12", "금액 계산 기준일", _fmt(inp.calc_until), o["di_rounding"]))

    order = "\n".join(s.order_text for s in schedules)
    return InterestResult(rows, total, [], trace, warnings, schedules, limitation, alternatives, order)
