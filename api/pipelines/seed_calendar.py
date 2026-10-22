"""Fill `morbidity_weeks` (Sunday-Saturday weeks, week 1 = first week with >= 4 days)."""

import logging
from datetime import date

import duckdb

from pipelines.common import connect, init_schema
from utils.morbidity_week import mw_range, weeks_in_year

log = logging.getLogger("pipelines")


def seed_calendar(con: duckdb.DuckDBPyConnection, first_year: int = 2014, last_year: int | None = None) -> int:
    last_year = last_year or date.today().year + 1
    rows = [
        (year, mw, *mw_range(year, mw))
        for year in range(first_year, last_year + 1)
        for mw in range(1, weeks_in_year(year) + 1)
    ]
    con.executemany("INSERT OR REPLACE INTO morbidity_weeks VALUES (?, ?, ?, ?)", rows)
    log.info("Calendar: %d weeks (%d-%d)", len(rows), first_year, last_year)
    return len(rows)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    _con = connect()
    init_schema(_con)
    seed_calendar(_con)
