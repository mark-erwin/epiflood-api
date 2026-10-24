"""Load municipality-level and Laguna-wide weekly rainfall from CSVs.

Municipality CSV columns:
    municipality, date, precipitation_mm

Province-wide CSV columns:
    date, precipitation_mm

Dates remain DATE values. No morbidity-week joins or re-aggregation.
"""

import logging
from pathlib import Path

import duckdb
import pandas as pd

from pipeline.common import RAIN_DIR, connect, init_schema

log = logging.getLogger("pipelines")

MUNI_WEEKLY_CSV = RAIN_DIR / "rainfall_per_muni_weekly_2016_2026.csv"
LAGUNA_WEEKLY_CSV = RAIN_DIR / "mean_rainfall_across_muni_weekly_2016_2026.csv"


def _ensure_tables(con: duckdb.DuckDBPyConnection) -> None:
    """Create rainfall tables using the project schema."""

    con.execute("""
        CREATE TABLE IF NOT EXISTS rainfall_per_muni_weekly (
            municipality_pcode VARCHAR NOT NULL,
            date DATE,
            precipitation_mm DOUBLE,
            PRIMARY KEY (municipality_pcode, date)
        )
    """)

    con.execute("""
        CREATE TABLE IF NOT EXISTS rainfall_laguna_weekly (
            date DATE,
            precipitation_mm DOUBLE,
            PRIMARY KEY (date)
        )
    """)


def _read_rainfall_csv(
    path: Path,
    required_columns: set[str],
) -> pd.DataFrame:
    """Read and validate a rainfall CSV while preserving dates as dates."""

    if not path.exists():
        raise FileNotFoundError(f"Rainfall CSV not found: {path}")

    df = pd.read_csv(path)

    missing = required_columns - set(df.columns)
    if missing:
        raise ValueError(
            f"{path.name} is missing columns {sorted(missing)}. "
            f"Found columns: {list(df.columns)}"
        )

    df = df.copy()

    parsed_dates = pd.to_datetime(df["date"], errors="coerce")

    if parsed_dates.isna().any():
        bad_rows = df.index[parsed_dates.isna()].tolist()[:10]
        raise ValueError(
            f"{path.name} contains invalid dates at rows {bad_rows}"
        )

    # Keep calendar dates; do not convert them to morbidity weeks.
    df["date"] = parsed_dates.dt.date

    df["precipitation_mm"] = pd.to_numeric(
        df["precipitation_mm"],
        errors="coerce",
    )

    invalid_rain = df["precipitation_mm"].isna()
    if invalid_rain.any():
        log.warning(
            "%s: %d precipitation values are missing or non-numeric",
            path.name,
            int(invalid_rain.sum()),
        )

    return df


def load_municipality_rainfall(
    con: duckdb.DuckDBPyConnection,
    path: Path = MUNI_WEEKLY_CSV,
) -> int:
    """Load municipality rainfall into rainfall_per_muni_weekly."""

    df = _read_rainfall_csv(
        path,
        {"municipality", "date", "precipitation_mm"},
    )

    df["municipality_pcode"] = (
        df["municipality"].astype("string").str.strip()
    )

    if (
        df["municipality_pcode"].isna().any()
        or df["municipality_pcode"].eq("").any()
    ):
        raise ValueError(
            f"{path.name} contains missing municipality codes"
        )

    duplicates = df.duplicated(
        subset=["municipality_pcode", "date"]
    ).sum()

    if duplicates:
        raise ValueError(
            f"{path.name} contains {duplicates} duplicate "
            "(municipality, date) records"
        )

    out = df[
        ["municipality_pcode", "date", "precipitation_mm"]
    ].copy()

    con.register("municipality_rainfall_stage", out)

    try:
        con.execute("BEGIN TRANSACTION")
        con.execute("DELETE FROM rainfall_per_muni_weekly")
        con.execute("""
            INSERT INTO rainfall_per_muni_weekly (
                municipality_pcode,
                date,
                precipitation_mm
            )
            SELECT
                municipality_pcode,
                CAST(date AS DATE),
                precipitation_mm
            FROM municipality_rainfall_stage
        """)
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    finally:
        con.unregister("municipality_rainfall_stage")

    log.info(
        "Loaded %d municipality rainfall records across %d municipalities",
        len(out),
        out["municipality_pcode"].nunique(),
    )

    return len(out)


def load_laguna_rainfall(
    con: duckdb.DuckDBPyConnection,
    path: Path = LAGUNA_WEEKLY_CSV,
) -> int:
    """Load Laguna-wide rainfall into rainfall_laguna_weekly."""

    df = _read_rainfall_csv(
        path,
        {"date", "precipitation_mm"},
    )

    duplicates = df.duplicated(subset=["date"]).sum()

    if duplicates:
        raise ValueError(
            f"{path.name} contains {duplicates} duplicate dates"
        )

    out = df[["date", "precipitation_mm"]].copy()

    con.register("laguna_rainfall_stage", out)

    try:
        con.execute("BEGIN TRANSACTION")
        con.execute("DELETE FROM rainfall_laguna_weekly")
        con.execute("""
            INSERT INTO rainfall_laguna_weekly (
                date,
                precipitation_mm
            )
            SELECT
                CAST(date AS DATE),
                precipitation_mm
            FROM laguna_rainfall_stage
        """)
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    finally:
        con.unregister("laguna_rainfall_stage")

    log.info("Loaded %d Laguna-wide rainfall records", len(out))

    return len(out)


def load_rainfall(
    con: duckdb.DuckDBPyConnection,
    municipality_path: Path = MUNI_WEEKLY_CSV,
    laguna_path: Path = LAGUNA_WEEKLY_CSV,
) -> dict[str, int]:
    """Load both rainfall datasets."""

    _ensure_tables(con)

    municipality_count = load_municipality_rainfall(
        con, municipality_path
    )
    laguna_count = load_laguna_rainfall(con, laguna_path)

    return {
        "rainfall_per_muni_weekly": municipality_count,
        "rainfall_laguna_weekly": laguna_count,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    con = connect()
    try:
        init_schema(con)
        counts = load_rainfall(con)
        print(counts)
    finally:
        con.close()