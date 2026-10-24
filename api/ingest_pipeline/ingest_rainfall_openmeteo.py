"""Daily rainfall per municipality from Open-Meteo, stored once in `rainfall_daily`.

Replaces: fetch_rainfall_per_barangay, fetch_single, main_fetch,
fetch_rainfall_per_barangay_fast, fetch_rainfall_weekly, avg_precipitation_laguna_per_week.

Why daily and once: weekly (morbidity-week) totals come from the `rainfall_weekly`
view, so week boundaries always match the case data, any window can be summed
later, and the API is called ~30 times instead of thousands.
"""

import logging
import time
from datetime import date, timedelta
from pathlib import Path

import duckdb
import pandas as pd
import requests

from ingest_pipeline.common import RAIN_DIR, connect, init_schema

log = logging.getLogger("pipelines")

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
START_DATE = date(2015, 11, 1)     # a few weeks before MW1 2016 so lag features have history
ARCHIVE_LAG_DAYS = 5               # the archive trails real time by a few days
RETRY_STATUS = {429, 500, 502, 503, 504}


class RainfallFetchError(RuntimeError):
    """Open-Meteo could not provide data for one or more municipalities."""


def fetch_daily_rainfall(
    session, lat: float, lon: float, start: date, end: date, retries: int = 5, backoff: float = 2.0
) -> list[tuple[date, float | None]]:
    """Daily precipitation sums. Missing days stay None. Failures raise (never 0)."""
    params = {
        "latitude": lat, "longitude": lon,
        "start_date": start.isoformat(), "end_date": end.isoformat(),
        "daily": "precipitation_sum", "timezone": "Asia/Manila",
    }
    last_error = "no attempt made"
    for attempt in range(retries):
        try:
            resp = session.get(ARCHIVE_URL, params=params, timeout=60)
        except requests.RequestException as exc:
            last_error = str(exc)
        else:
            if resp.status_code == 200:
                daily = resp.json().get("daily") or {}
                times, values = daily.get("time"), daily.get("precipitation_sum")
                if times is None or values is None or len(times) != len(values):
                    raise RainfallFetchError(f"Unexpected response shape for ({lat}, {lon})")
                return [(date.fromisoformat(t), None if v is None else float(v)) for t, v in zip(times, values)]
            if resp.status_code not in RETRY_STATUS:
                raise RainfallFetchError(f"HTTP {resp.status_code} for ({lat}, {lon}): {resp.text[:200]}")
            last_error = f"HTTP {resp.status_code}"
        time.sleep(backoff * (attempt + 1))
    raise RainfallFetchError(f"Gave up after {retries} attempts for ({lat}, {lon}): {last_error}")


def load_rainfall(
    con: duckdb.DuckDBPyConnection,
    session=None,
    start: date = START_DATE,
    end: date | None = None,
    pause: float = 0.5,
) -> int:
    """Fetch every municipality first; write only if all succeed (no partial/zero-filled data)."""
    end = end or date.today() - timedelta(days=ARCHIVE_LAG_DAYS)
    session = session or requests.Session()

    munis = con.execute(
        "SELECT pcode, name, centroid_lat, centroid_lng FROM municipalities ORDER BY pcode"
    ).fetchall()
    if not munis:
        raise RuntimeError("`municipalities` is empty. Run ingest_boundaries first.")
    bad = [m[0] for m in munis if m[2] is None or m[3] is None]
    if bad:
        raise RuntimeError(f"Municipalities without centroids: {bad}")

    frames, failed = [], []
    for i, (pcode, name, lat, lon) in enumerate(munis, 1):
        log.info("[%d/%d] %s (%s)", i, len(munis), name, pcode)
        try:
            rows = fetch_daily_rainfall(session, lat, lon, start, end)
        except RainfallFetchError as exc:
            log.error("%s: %s", pcode, exc)
            failed.append(pcode)
            continue
        frames.append(pd.DataFrame(rows, columns=["date", "rain_mm"]).assign(pcode=pcode))
        time.sleep(pause)

    if failed:
        raise RainfallFetchError(f"Failed for {len(failed)} municipalities: {failed}. Nothing was written; re-run.")

    df = pd.concat(frames, ignore_index=True)
    df["is_forecast"] = False
    n_null = int(df["rain_mm"].isna().sum())
    if n_null:
        log.warning("%d daily values are missing (kept as NULL, not 0)", n_null)

    con.register("rain_stage", df)
    con.execute(
        """
        INSERT OR REPLACE INTO rainfall_daily (pcode, date, rain_mm, is_forecast, source)
        SELECT pcode, date, rain_mm, is_forecast, 'open_meteo' FROM rain_stage
        """
    )
    con.unregister("rain_stage")
    log.info("Rainfall: %d daily rows for %d municipalities", len(df), len(munis))
    return len(df)


def weekly_rainfall(con: duckdb.DuckDBPyConnection, complete_weeks_only: bool = True) -> pd.DataFrame:
    """Municipality x morbidity-week totals (replaces the old W-SUN resample)."""
    where = "WHERE days_with_data = 7" if complete_weeks_only else ""
    return con.execute(
        f"SELECT pcode, year, mw, week_start, rain_mm_total, days_with_data "
        f"FROM rainfall_weekly {where} ORDER BY pcode, year, mw"
    ).df()


def laguna_weekly_mean(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Mean weekly rainfall across municipalities (replaces avg_precipitation_laguna_per_week)."""
    return con.execute(
        """
        SELECT year, mw, week_start, AVG(rain_mm_total) AS mean_rain_mm, COUNT(*) AS municipalities
        FROM rainfall_weekly WHERE days_with_data = 7
        GROUP BY year, mw, week_start ORDER BY year, mw
        """
    ).df()


def export_weekly_csv(con: duckdb.DuckDBPyConnection, out_path: Path | None = None) -> Path:
    out_path = out_path or RAIN_DIR / "laguna_weekly_rainfall.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    weekly_rainfall(con).to_csv(out_path, index=False)
    return out_path


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    _con = connect()
    init_schema(_con)
    load_rainfall(_con)
