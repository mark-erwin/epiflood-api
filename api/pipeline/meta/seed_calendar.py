"""Fill `morbidity_weeks` (Sunday-Saturday weeks, week 1 = first week with >= 4 days)."""

import logging
from datetime import date

import duckdb

from pipeline.common import connect, init_schema
from utils.morbidity_week import mw_range, weeks_in_year

log = logging.getLogger("pipelines")

FIRST_YEAR = 2016
LAST_YEAR = 2026    

def seed_calendar(con: duckdb.DuckDBPyConnection, first_year: int = FIRST_YEAR, last_year: int = LAST_YEAR) -> int:
    rows = [
        (year, mw, *mw_range(year, mw))
        for year in range(first_year, last_year + 1)
        for mw in range(1, weeks_in_year(year) + 1)
    ]
    con.execute("DELETE FROM morbidity_weeks WHERE year < ? OR year > ?", [first_year, last_year])
    con.executemany("INSERT OR REPLACE INTO morbidity_weeks VALUES (?, ?, ?, ?)", rows)
    log.info("Calendar: %d weeks (%d-%d)", len(rows), first_year, last_year)
    return len(rows)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    _con = connect()
    init_schema(_con)
    seed_calendar(_con)
