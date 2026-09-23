"""노임단가 변경일 기준 기간분할.

원본: SUT.SBGCalc.View.Popup.IncomeCostPopup (자동입력 핸들러)

    if (isNc) {                                    // 농촌 — 달력 분기 그대로
        if      (d <= new DateTime(d.Year,  3, 31)) { year = d.Year;            quarter = 1; }
        else if (d <= new DateTime(d.Year,  6, 30)) { year = d.Year;            quarter = 2; }
        else if (d <= new DateTime(d.Year,  9, 30)) { year = d.Year;            quarter = 3; }
        else if (d <= new DateTime(d.Year, 12, 31)) { year = d.Year;            quarter = 4; }
        else                                        { year = d.AddYears(1).Year; quarter = 1; }
        wage = GetWageFromSalaryDayTable(strId, year, quarter);   // TB_SUT001
        days = nongchonDayCnt;                                    // 25
    } else {                                       // 직종별 — 달력 반기가 아니다
        if      (d <= new DateTime(d.Year, 4, 30)) { year = d.Year;            half = 1; }
        else if (d <= new DateTime(d.Year, 8, 31)) { year = d.Year;            half = 2; }
        else                                       { year = d.AddYears(1).Year; half = 1; }
        wage = GetWageFromSalaryJobTable(jobNm, year, half);       // TB_SUT004
        days = normalDayCnt;                                      // 20
    }

직종별 반기는 달력 반기와 다르다. 9월 1일부터 이미 '다음 연도 상반기' 단가를 쓴다.

    전년 9. 1. ~ 당해 4.30.   당해 상반기 단가   (8개월)
    당해 5. 1. ~ 당해 8.31.   당해 하반기 단가   (4개월)

즉 일실수입 기간분할 경계는 직종별이면 매년 5월 1일과 9월 1일,
농촌이면 1월 1일·4월 1일·7월 1일·10월 1일이다.

주의: 도시일용노임은 두 경로로 잡힌다. 직종에서 '보통인부'를 고르면 TB_SUT004 를
타서 5/1·9/1 경계가 되고, 농촌 계통의 도시일용 항목(TB_SUT001)으로 잡으면 분기
경계가 된다. 단가 값은 같지만 전환 시점이 달라진다.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .constants import NORMAL_DAY_COUNT, RURAL_DAY_COUNT


def occupation_key(d: date) -> tuple[int, int]:
    """직종별 노임의 (기준연도, 반기). TB_SUT004 조회 키."""
    if d <= date(d.year, 4, 30):
        return d.year, 1
    if d <= date(d.year, 8, 31):
        return d.year, 2
    return d.year + 1, 1


def rural_key(d: date) -> tuple[int, int]:
    """농촌 노임의 (기준연도, 분기). TB_SUT001 조회 키."""
    if d <= date(d.year, 3, 31):
        return d.year, 1
    if d <= date(d.year, 6, 30):
        return d.year, 2
    if d <= date(d.year, 9, 30):
        return d.year, 3
    return d.year, 4


def wage_key(d: date, rural: bool = False) -> tuple[int, int]:
    return rural_key(d) if rural else occupation_key(d)


@dataclass(frozen=True)
class WagePeriod:
    """노임단가가 일정하게 유지되는 한 구간 (일실수입의 한 순번)."""

    start: date
    end: date
    year: int
    index: int      # 직종별이면 반기, 농촌이면 분기
    rural: bool

    @property
    def days(self) -> int:
        """월 가동일수. IncomeCostPopup: normalDayCnt = 20, nongchonDayCnt = 25."""
        return RURAL_DAY_COUNT if self.rural else NORMAL_DAY_COUNT


def _next_boundary(d: date, rural: bool) -> date:
    """d 이후 노임단가가 바뀌는 첫 날."""
    if rural:
        for m in (4, 7, 10):
            if d < date(d.year, m, 1):
                return date(d.year, m, 1)
        return date(d.year + 1, 1, 1)
    if d < date(d.year, 5, 1):
        return date(d.year, 5, 1)
    if d < date(d.year, 9, 1):
        return date(d.year, 9, 1)
    return date(d.year + 1, 5, 1)


def split_periods(
    start: date,
    end: date,
    rural: bool = False,
    has_wage=None,
) -> list[WagePeriod]:
    """[start, end] 를 노임단가 변경일 기준으로 쪼갠다.

    has_wage(year, index) -> bool 을 주면, **다음 구간의 단가가 없을 때 그 자리에서
    끝까지 한 순번으로 묶는다.** 원본이 그렇게 동작한다.

        wage = GetWageFromSalaryJobTable(jobNm, year, half);
        tmpWage4 = (half != 1) ? GetWageFromSalaryJobTable(jobNm, year + 1, 1)
                               : GetWageFromSalaryJobTable(jobNm, year, 2);
        if (tmpWage4 == -1m) {
            wage = GetWageFromSalaryJobTableNext(jobNm);   // 마지막 단가
            endDate = totalEndDate;                        // 가동종료일까지 확장
        }

    미래 노임단가는 알 수 없으므로 마지막으로 공표된 단가를 가동종료일까지 그대로
    쓴다. 골든 케이스에서 순번3이 2026.04.14. ~ 2063.06.30. 으로 한 덩어리인 이유다.
    """
    if end < start:
        return []
    out: list[WagePeriod] = []
    cur = start
    while cur <= end:
        year, index = wage_key(cur, rural)
        boundary = _next_boundary(cur, rural)
        if has_wage is not None and not has_wage(*wage_key(boundary, rural)):
            out.append(WagePeriod(cur, end, year, index, rural))
            break
        seg_end = min(end, date.fromordinal(boundary.toordinal() - 1))
        out.append(WagePeriod(cur, seg_end, year, index, rural))
        cur = date.fromordinal(seg_end.toordinal() + 1)
    return out
