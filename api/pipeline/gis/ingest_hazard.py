"""Load precomputed flood-hazard summaries from CSV files.

Municipality CSV:
    municipality_pcode, hazard_level, area_km2, pct_of_area

Barangay CSV:
    adm4_pcode, pct_flood_hazard_2, pct_flood_hazard_3

Both destination tables are defined in schema.sql.
"""

import logging
from pathlib import Path

import duckdb
import pandas as pd

from pipeline.common import GIS_OUT, connect, init_schema

log = logging.getLogger("pipelines")

MUNICIPALITY_CSV = GIS_OUT / "municipality_flood_hazard.csv"
BARANGAY_CSV = GIS_OUT / "barangay_flood_hazard.csv"


def _read_csv(
    path: Path,
    required_columns: set[str],
) -> pd.DataFrame:
    """Read a CSV and validate its required columns."""

    if not path.exists():
        raise FileNotFoundError(f"Hazard CSV not found: {path}")

    df = pd.read_csv(path, dtype=str)

    # Remove accidental whitespace from column names.
    df.columns = df.columns.str.strip()

    missing = required_columns - set(df.columns)
    if missing:
        raise ValueError(
            f"{path.name} is missing columns {sorted(missing)}. "
            f"Found: {list(df.columns)}"
        )

    return df


def _replace_table(
    con: duckdb.DuckDBPyConnection,
    table: str,
    df: pd.DataFrame,
) -> int:
    """Replace all rows in a destination table with validated CSV data."""

    con.register("hazard_stage", df)

    try:
        con.execute("BEGIN TRANSACTION")
        con.execute(f"DELETE FROM {table}")

        columns = list(df.columns)
        column_sql = ", ".join(f'"{col}"' for col in columns)

        con.execute(
            f"INSERT INTO {table} ({column_sql}) "
            f"SELECT {column_sql} FROM hazard_stage"
        )

        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    finally:
        con.unregister("hazard_stage")

    return len(df)


def load_municipality_hazards(
    con: duckdb.DuckDBPyConnection,
    path: Path = MUNICIPALITY_CSV,
) -> int:
    """Load municipality hazard summaries."""

    columns = [
        "municipality_pcode",
        "hazard_level",
        "area_km2",
        "pct_of_area",
    ]

    df = _read_csv(path, set(columns))
    df = df[columns].copy()

    # Preserve administrative codes as strings.
    df["municipality_pcode"] = (
        df["municipality_pcode"].str.strip()
    )

    df["hazard_level"] = pd.to_numeric(
        df["hazard_level"], errors="raise"
    )

    if df["hazard_level"].isna().any():
        raise ValueError(
            "Municipality CSV contains missing hazard_level values"
        )

    if not df["hazard_level"].isin([1, 2, 3]).all():
        raise ValueError(
            "Municipality hazard_level must be 1, 2, or 3"
        )

    if not (df["hazard_level"] % 1 == 0).all():
        raise ValueError(
            "Municipality hazard_level must contain integers"
        )

    df["hazard_level"] = df["hazard_level"].astype("int32")

    for col in ["area_km2", "pct_of_area"]:
        df[col] = pd.to_numeric(df[col], errors="raise")

    if (
        df["municipality_pcode"].isna().any()
        or df["municipality_pcode"].eq("").any()
    ):
        raise ValueError(
            "Municipality CSV contains empty municipality_pcode values"
        )

    if df.duplicated(
        ["municipality_pcode", "hazard_level"]
    ).any():
        raise ValueError(
            "Municipality CSV contains duplicate "
            "(municipality_pcode, hazard_level) records"
        )

    numeric_columns = ["area_km2", "pct_of_area"]

    if df[numeric_columns].isna().any().any():
        raise ValueError(
            "Municipality CSV contains missing numeric values"
        )

    if (df[numeric_columns] < 0).any().any():
        raise ValueError(
            "Municipality CSV contains negative values"
        )

    if (df["pct_of_area"] > 100).any():
        raise ValueError(
            "Municipality pct_of_area cannot exceed 100"
        )

    count = _replace_table(
        con,
        "hazard_by_municipality",
        df,
    )

    log.info("Loaded %d municipality hazard records", count)
    return count


def load_barangay_hazards(
    con: duckdb.DuckDBPyConnection,
    path: Path = BARANGAY_CSV,
) -> int:
    """Load barangay hazard summaries from the source CSV."""

    columns = [
        "barangay_pcode",
        "hazard_level",
        "area_km2",
        "pct_of_area",
    ]

    df = _read_csv(path, set(columns))
    df = df[columns].copy()

    # Preserve administrative codes as strings.
    df["barangay_pcode"] = df["barangay_pcode"].str.strip()

    df["hazard_level"] = pd.to_numeric(
        df["hazard_level"], errors="raise"
    )

    if df["hazard_level"].isna().any():
        raise ValueError(
            "Barangay CSV contains missing hazard_level values"
        )

    if not df["hazard_level"].isin([1, 2, 3]).all():
        raise ValueError(
            "Barangay hazard_level must be 1, 2, or 3"
        )

    if not (df["hazard_level"] % 1 == 0).all():
        raise ValueError(
            "Barangay hazard_level must contain integers"
        )

    df["hazard_level"] = df["hazard_level"].astype("int32")

    for col in ["area_km2", "pct_of_area"]:
        df[col] = pd.to_numeric(df[col], errors="raise")

    if (
        df["barangay_pcode"].isna().any()
        or df["barangay_pcode"].eq("").any()
    ):
        raise ValueError(
            "Barangay CSV contains empty barangay_pcode values"
        )

    if df.duplicated(["barangay_pcode", "hazard_level"]).any():
        raise ValueError(
            "Barangay CSV contains duplicate "
            "(barangay_pcode, hazard_level) records"
        )

    numeric_columns = ["area_km2", "pct_of_area"]

    if df[numeric_columns].isna().any().any():
        raise ValueError(
            "Barangay CSV contains missing numeric values"
        )

    if (df[numeric_columns] < 0).any().any():
        raise ValueError(
            "Barangay CSV contains negative values"
        )

    if (df["pct_of_area"] > 100).any():
        raise ValueError(
            "Barangay pct_of_area cannot exceed 100"
        )

    count = _replace_table(
        con,
        "hazard_by_barangay",
        df,
    )

    log.info("Loaded %d barangay hazard records", count)
    return count


def run(
    con: duckdb.DuckDBPyConnection,
    municipality_csv: Path = MUNICIPALITY_CSV,
    barangay_csv: Path = BARANGAY_CSV,
) -> dict[str, int]:
    """Load both precomputed hazard CSVs into DuckDB."""

    municipality_count = load_municipality_hazards(
        con, municipality_csv
    )

    barangay_count = load_barangay_hazards(
        con, barangay_csv
    )

    counts = {
        "hazard_by_municipality": municipality_count,
        "hazard_by_barangay": barangay_count,
    }

    for table, count in counts.items():
        log.info("%s: %d rows", table, count)

    return counts


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    con = connect()
    try:
        init_schema(con)
        print(run(con))
    finally:
        con.close()
