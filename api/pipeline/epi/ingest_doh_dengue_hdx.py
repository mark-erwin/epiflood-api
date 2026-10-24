"""HDX DOH-Epi Dengue 2016-2021 -> weekly dengue cases for Laguna.

Loads province-level dengue data into dengue_cases_laguna_weekly.

Target table:
    date DATE PRIMARY KEY,
    cases INTEGER,
    deaths INTEGER

No municipality-level processing is performed.
"""

import logging
from pathlib import Path

import duckdb
import pandas as pd

from pipeline.common import (
    EPI_OUT,
    HDX_DENGUE_PATH,
    PROVINCE,
    connect,
    init_schema,
)
from utils.morbidity_week import date_to_mw

log = logging.getLogger("pipelines")

TABLE_NAME = "dengue_cases_laguna_weekly"


def _sum_min1(series: pd.Series):
    """Sum values while preserving missing values when all are null."""
    return series.sum(min_count=1)


def load_hdx_dengue(
    con: duckdb.DuckDBPyConnection,
    csv_path: Path = HDX_DENGUE_PATH,
    out_dir: Path = EPI_OUT,
    loc_col: str = "loc",
    date_col: str = "date",
    cases_col: str = "cases",
    deaths_col: str = "deaths",
) -> dict:
    df = pd.read_csv(csv_path)

    # Validate the required source columns.
    required = [date_col, cases_col]
    if loc_col in df.columns:
        required.append(loc_col)

    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(
            f"{csv_path.name} is missing columns {missing}. "
            f"Available columns: {list(df.columns)}"
        )

    # Filter to Laguna when a location column is available.
    if loc_col in df.columns:
        df = df[
            df[loc_col].astype(str).str.contains(
                PROVINCE, case=False, na=False
            )
        ].copy()

        if df.empty:
            raise ValueError(
                f"No rows with '{loc_col}' containing '{PROVINCE}'."
            )
    else:
        log.warning(
            "No '%s' column found. Assuming the input is already "
            "filtered to %s.",
            loc_col,
            PROVINCE,
        )

    # Parse dates and discard invalid records.
    df["date"] = pd.to_datetime(
        df[date_col], errors="coerce"
    ).dt.normalize()

    invalid_dates = int(df["date"].isna().sum())
    if invalid_dates:
        log.warning(
            "Dropping %d records with invalid dates.",
            invalid_dates,
        )
        df = df[df["date"].notna()].copy()

    if df.empty:
        raise ValueError("No valid dated records remain.")

    # Convert counts to numeric values.
    df["cases"] = pd.to_numeric(
        df[cases_col], errors="coerce"
    )

    if deaths_col in df.columns:
        df["deaths"] = pd.to_numeric(
            df[deaths_col], errors="coerce"
        )
    else:
        df["deaths"] = float("nan")

    # Derive epidemiological year/week only for grouping.
    week_info = [
        date_to_mw(timestamp.date())
        for timestamp in df["date"]
    ]
    df["epi_year"] = [year for year, _ in week_info]
    df["epi_week"] = [week for _, week in week_info]

    # Aggregate to one record per epidemiological week.
    weekly = (
        df.groupby(["epi_year", "epi_week"], as_index=False)
        .agg(
            cases=("cases", _sum_min1),
            deaths=("deaths", _sum_min1),
        )
    )

    # Use the week-start date as the stored date.
    # The source date is not necessarily the week's start date.
    weekly["date"] = [
        pd.Timestamp.fromisocalendar(int(year), int(week), 1)
        for year, week in zip(
            weekly["epi_year"], weekly["epi_week"]
        )
    ]

    # Retain only the three requested output columns.
    weekly["cases"] = weekly["cases"].round().astype("Int64")
    weekly["deaths"] = weekly["deaths"].round().astype("Int64")

    weekly = weekly[["date", "cases", "deaths"]].sort_values("date")

    # Export CSV.
    out_dir.mkdir(parents=True, exist_ok=True)
    export_path = out_dir / "doh_hdx_laguna_dengue_province.csv"

    weekly.to_csv(
        export_path,
        index=False,
        date_format="%Y-%m-%d",
    )

    # Replace existing records in the target table.
    # The table must already have the schema:
    # date DATE PRIMARY KEY, cases INTEGER, deaths INTEGER.
    con.register("hdx_stage", weekly)

    try:
        con.execute(f"DELETE FROM {TABLE_NAME}")

        con.execute(
            f"""
            INSERT INTO {TABLE_NAME} (date, cases, deaths)
            SELECT
                CAST(date AS DATE),
                CAST(cases AS INTEGER),
                CAST(deaths AS INTEGER)
            FROM hdx_stage
            """
        )
    finally:
        con.unregister("hdx_stage")

    log.info(
        "Loaded %d weekly records into %s.",
        len(weekly),
        TABLE_NAME,
    )

    return {
        "level": "province",
        "rows": len(weekly),
        "csv_path": str(export_path),
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    con = connect()
    try:
        init_schema(con)
        result = load_hdx_dengue(con)
        log.info("HDX dengue load result: %s", result)
    finally:
        con.close()
