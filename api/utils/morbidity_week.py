"""Morbidity-week (epidemiological week) helpers.

Convention (same as CDC MMWR): weeks run Sunday-Saturday and week 1 is the
first week with at least 4 days in the new year.
"""
from datetime import date, timedelta


def mw1_start(year: int) -> date:
    jan1 = date(year, 1, 1)
    start = jan1 - timedelta(days=(jan1.weekday() + 1) % 7)   # Sunday on/before Jan 1
    if (jan1 - start).days > 3:                                # <4 days in new year
        start += timedelta(days=7)
    return start


def weeks_in_year(year: int) -> int:
    return (mw1_start(year + 1) - mw1_start(year)).days // 7


def mw_range(year: int, mw: int) -> tuple[date, date]:
    if not 1 <= mw <= weeks_in_year(year):
        raise ValueError(f"{year} has no MW {mw}")
    start = mw1_start(year) + timedelta(weeks=mw - 1)
    return start, start + timedelta(days=6)


def date_to_mw(d: date) -> tuple[int, int]:
    for y in (d.year + 1, d.year, d.year - 1):
        if d >= mw1_start(y):
            return y, (d - mw1_start(y)).days // 7 + 1
    raise ValueError(d)
