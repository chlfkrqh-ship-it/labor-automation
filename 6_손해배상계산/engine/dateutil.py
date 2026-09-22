"""DateUtil.GetDiffDaysString 대응 — 기간의 년/월/일 계산.

원본: SUT.Common.Helpers.Utils.DateUtil

    public static string GetDiffDaysString(DateTime startDate, DateTime endDate,
                                           ref YMD outObj, bool isNeedPlus1DayToEndDate = true)
    {
        DateTime tmpDate = new DateTime(endDate.Year, endDate.Month, 1);   // 보정 전 endDate 기준
        if (isNeedPlus1DayToEndDate) endDate = endDate.AddDays(1.0);
        int years  = endDate.Year  - startDate.Year;
        int months = endDate.Month - startDate.Month;
        int days   = endDate.Day   - startDate.Day;
        int totalDays = (endDate - startDate).Days;
        if (days < 0) { days += tmpDate.AddDays(-1.0).Day; months--; }
        if (months < 0) { months += 12; years--; }
        outObj.MonthCalc = years + months / 12.0;
        outObj.DayCalc   = totalDays / 365.0;
    }

두 가지가 중요하다.

1. `isNeedPlus1DayToEndDate` 의 **기본값이 true** 다. 즉 기간말일에 하루를 더한다
   (초일산입). 일실수입은 기본값을 그대로 쓰고, 향후치료비만 `false` 를 명시한다.

       IncomeCostPopup      GetDiffDaysString(accidentDate, startDate, ref ymd)        -> +1일
       ToBeTreatmentCost    GetDiffDaysString(accidentDate, tmpDate, ref ymd, false)   -> +1일 없음

2. 일수 보정에 쓰는 `tmpDate` 는 **하루를 더하기 전의** endDate 가 속한 달의 1일이고,
   거기서 하루를 뺀 날(= 그 전달 말일)의 '일' 값을 더한다. endDate 가 월말이면
   +1 로 달이 넘어가지만 tmpDate 는 원래 달 기준이라, 이 어긋남이 결과에 남는다.
   직관적인 개월수 계산과 하루씩 달라지는 원인이므로 그대로 옮긴다.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class YMD:
    year: int
    month: int
    day: int
    month_calc: float   # year + month/12  (일실퇴직금에서 쓴다)
    day_calc: float     # totalDays / 365

    @property
    def total_months(self) -> int:
        """m = Year * 12 + Month. 일(day)은 버린다."""
        return self.year * 12 + self.month


def diff_ymd(start: date, end: date, plus_one_day: bool = True) -> YMD:
    """GetDiffDaysString 그대로."""
    tmp_first = date(end.year, end.month, 1)   # 보정 전 기준
    if plus_one_day:
        end = end + timedelta(days=1)
    years = end.year - start.year
    months = end.month - start.month
    days = end.day - start.day
    total_days = (end - start).days
    if days < 0:
        days += (tmp_first - timedelta(days=1)).day
        months -= 1
    if months < 0:
        months += 12
        years -= 1
    return YMD(years, months, days, years + months / 12.0, total_days / 365.0)


def months_from(accident: date, target: date, plus_one_day: bool = True) -> int:
    """사고일자에서 대상일까지의 개월수. 음수면 0으로 자른다.

    원본: i = ymdClass.Year * 12 + ymdClass.Month;  if (i < 0) i = 0;
    """
    return max(diff_ymd(accident, target, plus_one_day).total_months, 0)


def age_at(birth: date, target: date) -> YMD:
    """연령 계산. GetDiffDaysString 이 아니라 **GetAgeString** 을 쓴다.

    원본: SUT.Common.Helpers.Utils.DateUtil.GetAgeString

        years  = endDate.Year  - startDate.Year;
        months = endDate.Month - startDate.Month;
        days   = endDate.Day   - startDate.Day;
        if (days < 0) { days += new DateTime(endDate.Year, endDate.Month, 1).AddDays(-1.0).Day; months--; }
        if (months < 0) { months += 12; years--; }

    GetDiffDaysString 과 달리 **하루를 더하지 않는다.** 기간 계산은 초일산입이지만
    연령은 아니다. 골든 케이스 2에서 이 차이가 하루로 드러났다.

        1997.05.14. 생, 2024.08.09. 사고
          GetDiffDaysString -> 27년 2월 27일   (초일산입)
          GetAgeString      -> 27세 2개월 26일  <- 프로그램 표시값
    """
    years = target.year - birth.year
    months = target.month - birth.month
    days = target.day - birth.day
    if days < 0:
        days += (date(target.year, target.month, 1) - timedelta(days=1)).day
        months -= 1
    if months < 0:
        months += 12
        years -= 1
    return YMD(years, months, days, years + months / 12.0, 0.0)
