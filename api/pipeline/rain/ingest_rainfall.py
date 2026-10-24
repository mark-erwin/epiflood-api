"""Weekly rainfall per municipality from api/data/rain/rainfall_per_muni_weekly_2016_2026.csv.

CSV columns: municipality (a pcode), date (Sunday = morbidity-week start), precipitation_mm.
No API calls. `rainfall_weekly` is a table (the source is already weekly).
"""

import logging
from datetime import date
from pathlib import Path

import duckdb
import pandas as pd

from pipeline.common import RAIN_DIR, connect, init_schema

log = logging.getLogger("pipelines")

MUNI_WEEKLY_CSV = RAIN_DIR / "rainfall_per_muni_weekly_2016_2026.csv"

def _ensure_table(con: duckdb.DuckDBPyConnection) -> None:
    """rainfall_weekly must be a table. Drop a leftover view only if one really exists."""
    kind = con.execute(
        "SELECT table_type FROM information_schema.tables "
        "WHERE table_schema = 'main' AND table_name = 'rainfall_weekly'"
    ).fetchone()
    if kind and kind[0] == "VIEW":
        con.execute("DROP VIEW rainfall_weekly")
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS rainfall_weekly (
            pcode VARCHAR, year INTEGER, mw INTEGER, week_start DATE,
            rain_mm_total DOUBLE, days_with_data INTEGER,
            PRIMARY KEY (pcode, year, mw)
        )
        """
    )

def load_rainfall(con: duckdb.DuckDBPyConnection, path: Path = MUNI_WEEKLY_CSV, today: date | None = None) -> int:
    today = today or date.today()
    if not path.exists():
        raise FileNotFoundError(f"Rainfall CSV not found: {path}")
    raw = pd.read_csv(path, dtype={"municipality": str}, parse_dates=["date"])
    missing = {"municipality", "date", "precipitation_mm"} - set(raw.columns)
    if missing:
        raise RuntimeError(f"{path.name}: missing columns {sorted(missing)}. Found: {list(raw.columns)}")

    raw["pcode"] = raw["municipality"].str.strip()
    known = {r[0] for r in con.execute("SELECT pcode FROM municipalities").fetchall()}
    if not known:
        raise RuntimeError("`municipalities` is empty. Run the boundaries step first.")
    unknown = sorted(set(raw["pcode"]) - known)
    if unknown:
        raise RuntimeError(f"Pcodes in {path.name} not in `municipalities`: {unknown}")

    raw["date"] = raw["date"].dt.date
    raw["rain_mm_total"] = pd.to_numeric(raw["precipitation_mm"], errors="coerce")
    n_dup = int(raw.duplicated(["pcode", "date"]).sum())
    if n_dup:
        log.warning("%d duplicate (pcode, date) rows; keeping the last", n_dup)
        raw = raw.drop_duplicates(["pcode", "date"], keep="last")

    _ensure_table(con)
    con.register("rain_stage", raw[["pcode", "date", "rain_mm_total"]])
    joined = con.execute(
        """
        SELECT r.pcode, w.year, w.mw, r.date AS week_start, r.rain_mm_total
        FROM rain_stage r LEFT JOIN morbidity_weeks w ON w.week_start = r.date
        """
    ).df()
    con.unregister("rain_stage")

    no_week = joined["mw"].isna()
    if no_week.any():
        bad = sorted({str(d) for d in joined.loc[no_week, "week_start"]})[:10]
        raise RuntimeError(f"{int(no_week.sum())} dates are not a morbidity-week start; examples: {bad}")

    n_null = int(joined["rain_mm_total"].isna().sum())
    if n_null:
        log.warning("%d weekly values are NULL (kept as NULL, not 0)", n_null)

    elapsed = (pd.Timestamp(today) - pd.to_datetime(joined["week_start"])).dt.days.clip(upper=7)
    joined["days_with_data"] = elapsed.where(joined["rain_mm_total"].notna(), 0).astype(int)
    joined["year"], joined["mw"] = joined["year"].astype(int), joined["mw"].astype(int)

    out = joined[["pcode", "year", "mw", "week_start", "rain_mm_total", "days_with_data"]]
    con.register("rain_out", out)
    con.execute("INSERT OR REPLACE INTO rainfall_weekly SELECT * FROM rain_out")
    con.unregister("rain_out")
    log.info("Rainfall: %d weekly rows for %d municipalities", len(out), out["pcode"].nunique())
    return len(out)

def weekly_rainfall(con: duckdb.DuckDBPyConnection, complete_weeks_only: bool = True) -> pd.DataFrame:
    where = "WHERE days_with_data = 7" if complete_weeks_only else ""
    return con.execute(
        f"SELECT pcode, year, mw, week_start, rain_mm_total, days_with_data "
        f"FROM rainfall_weekly {where} ORDER BY pcode, year, mw"
    ).df()

def laguna_weekly_mean(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return con.execute(
        """
        SELECT year, mw, week_start, AVG(rain_mm_total) AS mean_rain_mm, COUNT(*) AS municipalities
        FROM rainfall_weekly WHERE days_with_data = 7
        GROUP BY year, mw, week_start ORDER BY year, mw
        """
    ).df()
