from datetime import date, timedelta

import pytest

from utils.morbidity_week import date_to_mw, mw_range, mw1_start, weeks_in_year


def test_known_doh_weeks():
    assert mw_range(2019, 42) == (date(2019, 10, 13), date(2019, 10, 19))
    assert mw_range(2026, 38) == (date(2026, 9, 20), date(2026, 9, 26))


def test_weeks_in_year():
    assert weeks_in_year(2020) == 53
    assert weeks_in_year(2025) == 53
    assert weeks_in_year(2021) == 52
    assert weeks_in_year(2026) == 52


def test_early_january_belongs_to_previous_year():
    assert date_to_mw(date(2021, 1, 1)) == (2020, 53)
    assert date_to_mw(date(2021, 1, 3)) == (2021, 1)


def test_late_december_can_belong_to_next_year():
    assert date_to_mw(date(2024, 12, 31)) == (2025, 1)


def test_weeks_start_on_sunday():
    assert all(mw1_start(y).weekday() == 6 for y in range(2016, 2028))


def test_invalid_week_rejected():
    with pytest.raises(ValueError):
        mw_range(2021, 53)


def test_round_trip_every_day():
    d = date(2016, 1, 1)
    while d < date(2027, 1, 1):
        y, w = date_to_mw(d)
        start, end = mw_range(y, w)
        assert start <= d <= end
        d += timedelta(days=1)
