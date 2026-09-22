"""골든 케이스 2 — 사망 사건. 대법원 프로그램 엑셀표저장 결과에서 뽑은 기대값.

원본 파일과 성명·사건번호는 옮기지 않았다.

손해배상(산) / 사망 / 남 / 호프만식

주의: 이 출력은 **구 손해배상 프로그램(DamgCalc)** 형식이다. 종합 시트가
[일실수입]/[기타손해]/[과실상계]/[공제]/[위자료 및 합계] 로 구성되고 컬럼이
소문자 m1/m2 이며, 상실률 자리에 생계비가 온다. 신 프로그램(SBGCalc)의
[소극손해]/[적극손해]/[과실상계 전 공제] 구성과 다르다.

그래서 **산식 검증에는 쓰되 순번 구성 검증에는 쓰지 않는다.** 구 프로그램은
노임단가 변경일로 기간을 쪼개지 않고 사고일~가동종료일을 한 순번으로 잡는다.
"""

from datetime import date
from decimal import Decimal

BIRTH = date(1997, 5, 14)
ACCIDENT = date(2024, 8, 9)
WORK_END = date(2062, 5, 13)       # 가동종료일 (가동연한 65세)
LIFE_END = date(2078, 1, 7)        # 여명종료일
HIRE = date(2024, 6, 19)           # 입사일

AGE_AT_ACCIDENT = (27, 2, 26)      # 사고시 연령 '27세 2개월 26일'
LIFE_EXPECTANCY = Decimal("53.45")

# [일실수입] — 한 순번
WAGE = 167081                      # 2024 반기2 보통인부
DAYS = 20
SALARY = 3341620
LIVING_COST = "1/3"
M1, HOFFMAN1 = 453, "254.1673"
M2, HOFFMAN2 = 0, "0"
ADJUST_HOFFMAN = "240"             # 254.1673 이 240 으로 잘린다
INCOME_TOTAL = Decimal("534659200")

# [기타손해]
FUNERAL_COST = Decimal("5000000")  # 사망이면 기본 500만원 (설명서 33쪽)

# [위자료 및 합계]
SOLATIUM = Decimal("100000000")
PROPERTY_DAMAGE = Decimal("534659200")
GRAND_TOTAL = Decimal("634659200")

# 퇴직금(일반) 시트 — 상실률 100%
MONTHLY_SALARY = Decimal("2334000")
SERVICE_AT_ACCIDENT = ("0년 1월 22일", "0.0833333333333333", "0.142465753424658")
SEVERANCE_AT_ACCIDENT_MONTH = Decimal("194499")
SEVERANCE_AT_ACCIDENT_DAY = Decimal("332515")
SEVERANCE_RETIREMENT_PV = Decimal("2240640")
METHOD_B_MONTH = Decimal("2046141")
METHOD_B_DAY = Decimal("1908125")
