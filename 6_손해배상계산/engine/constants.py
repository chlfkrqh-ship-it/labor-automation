"""디컴파일 원본에서 확인한 상수와 코드값.

출처: SUT.SBGCalc.View.Popup.IncomeCostPopup
"""

from decimal import Decimal

# 사건유형(SaGbn). IncomeCostPopup:
#     string livingCost = (basicInfo.SaGbn.Equals(1) ? "0" : "1/3");
#     if (basicInfo.SaGbn.Equals(3)) { if (cureEndDate > deathDay) ... }
SAGBN_INJURY = 1        # 부상  -> 생계비 공제 없음
SAGBN_DEATH = 3         # 사망(추정) -> 생계비 1/3 공제. 코드표 확인 필요
LIVING_COST_INJURY = "0"
LIVING_COST_DEATH = "1/3"

# 여명이 가동기간 내로 단축된 구간의 상실률.
# 설명서 16쪽은 "66.6%로 설정"이라고 서술하지만 원본은 8자리를 쓴다.
#     lossStr = "66.66666666";
SHORTENED_LIFE_LOSS_RATE = Decimal("66.66666666")

# 입원기간 상실률은 자동으로 100 (설명서 16쪽, 원본 lossStr 기본값 "100")
HOSPITALIZED_LOSS_RATE = Decimal("100")

# 노임 조회는 두 계통으로 갈린다. IncomeCostPopup:
#     bool isNc = !int.TryParse(strId, out id);
#     decimal wage = isNc ? DBHelper.GetWageFromSalaryDayTable(strId, year, quarter)
#                         : DBHelper.GetWageFromSalaryJobTable(jobNm, year, half);
#
#   GetWageFromSalaryDayTable  농촌일용 (TB_SUT001)  분기 단위, 일수 = nongchonDayCnt
#   GetWageFromSalaryJobTable  직종별   (TB_SUT004)  반기 단위, 일수 = normalDayCnt
#
# 월소득 = 노임단가 x 일수 로 넘어간다.
#     new Income(..., nongchonDayCnt.ToString(), wage.ToString(),
#                (wage * (decimal)nongchonDayCnt).ToString(), ...)
#
# 월 가동일수. IncomeCostPopup 필드 선언:
#     public int normalDayCnt = 20;
#     public int nongchonDayCnt = 25;
NORMAL_DAY_COUNT = 20      # 직종별
RURAL_DAY_COUNT = 25       # 농촌

WAGE_LOOKUP_RURAL = "SalaryDayTable"       # TB_SUT001, 분기
WAGE_LOOKUP_OCCUPATION = "SalaryJobTable"  # TB_SUT004, 반기

# 노임단가 조회 실패 시 -1 을 돌려주고, 그러면 다음 구간 단가로 넘어간다.
#     if (wage == -1m) { wage = prevYearWage; endDate = m_operatingLimitDate; }
#     GetWageFromSalaryJobTableNext(jobNm) / GetWageFromSalaryDayTableNext(strId)
WAGE_NOT_FOUND = Decimal("-1")
