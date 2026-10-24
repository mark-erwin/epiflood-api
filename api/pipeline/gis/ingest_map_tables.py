"""Map tables loaded straight from map files with DuckDB's `spatial` extension.

    python -m pipelines.build_map_tables

Creates: health_units, flood_hazards (+ an EPSG:3857 column and R-tree index for the vector
tiles), pcode_lookup, barangays, bgy_dengue_clusters, bgy_lepto_clusters, bgy_rainfall.

Replaces db.init_db.load_map_tables. It is the 'maps' step of run_all and needs the
'boundaries' step first (that step writes laguna_pcode_lookup.csv). The first run needs
internet to install the spatial extension. Stop the API before running.
"""

import logging
from pathlib import Path

import duckdb

from pipeline.common import (
    EB_STAGED, GIS_OUT, HAZARD_GPKG_PATH, HEALTH_FACILITIES_PATH, LAGUNA_ADM4_PATH, RAIN_DIR, connect, init_schema,
)

log = logging.getLogger("pipelines")

BGY_RAINFALL_PATH = RAIN_DIR / "rainfall_per_bgy_mw.csv"
CLUSTER_TABLES = {"dengue": "bgy_dengue_clusters", "leptospirosis": "bgy_lepto_clusters"}


def _load_spatial(con: duckdb.DuckDBPyConnection) -> None:
    try:
        con.execute("LOAD spatial")
    except duckdb.Error:
        con.execute("INSTALL spatial")
        con.execute("LOAD spatial")


def _require(path: Path, what: str, hint: str = "") -> Path:
    if not path.exists():
        raise FileNotFoundError(f"{what} not found: {path}" + (f" ({hint})" if hint else ""))
    return path


def _count(con: duckdb.DuckDBPyConnection, table: str) -> int:
    return con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def load_health_units(con: duckdb.DuckDBPyConnection) -> int:
    path = _require(HEALTH_FACILITIES_PATH, "Health facility points")
    con.execute("CREATE OR REPLACE TABLE health_units AS SELECT * FROM ST_Read(?)", [str(path)])
    return _count(con, "health_units")


def load_flood_hazards(con: duckdb.DuckDBPyConnection) -> int:
    path = _require(HAZARD_GPKG_PATH, "Flood hazard GeoPackage")
    con.execute("DROP INDEX IF EXISTS flood_rtree")
    con.execute(
        """
        CREATE OR REPLACE TABLE flood_hazards AS
        SELECT *, ST_Transform(geom, 'EPSG:4326', 'EPSG:3857', always_xy := true) AS geom_3857
        FROM ST_Read(?)
        """,
        [str(path)],
    )
    con.execute("CREATE INDEX flood_rtree ON flood_hazards USING RTREE (geom_3857)")
    return _count(con, "flood_hazards")


def _barangay_file() -> Path:
    """Processed copy first (the boundaries step guarantees name, parent and area/centroid columns)."""
    for path in (GIS_OUT / "laguna_barangay_geodata.geojson", LAGUNA_ADM4_PATH):
        if path.exists():
            return path
    raise FileNotFoundError("Barangay boundaries not found: run the 'boundaries' step first")



def load_barangays(con: duckdb.DuckDBPyConnection) -> int:
    """One complete barangay table: id, name, parent municipality, area, centroid, geometry."""
    con.execute(
        """
        CREATE OR REPLACE TABLE barangays AS
        SELECT
            CAST(adm4_pcode AS VARCHAR) AS barangay_pcode,
            adm4_name                   AS barangay_name,
            CAST(adm3_pcode AS VARCHAR) AS municipality_pcode,
            adm3_name                   AS municipality_name,
            area_sqkm,
            center_lon AS longitude,
            center_lat AS latitude,
            geom
        FROM ST_Read(?)
        """,
        [str(_barangay_file())],
    )

    obj = con.execute("""
        SELECT table_type
        FROM information_schema.tables
        WHERE table_schema = 'main'
        AND table_name = 'pcode_lookup'
    """).fetchone()

    if obj:
        if obj[0] == "VIEW":
            con.execute("DROP VIEW pcode_lookup")
        else:
            con.execute("DROP TABLE pcode_lookup")

    con.execute(
        """
        CREATE OR REPLACE VIEW pcode_lookup AS
        SELECT barangay_pcode, barangay_name, municipality_pcode, municipality_name FROM barangays
        """
    )
    return _count(con, "barangays")


def load_clusters(con: duckdb.DuckDBPyConnection) -> dict[str, int]:
    """Staged cluster CSVs joined to the barangay lookup and geometry."""
    counts: dict[str, int] = {}

    for disease, table in CLUSTER_TABLES.items():
        path = EB_STAGED[disease]

        if not path.exists():
            log.warning("%s not found: %s not built", path.name, table)
            continue

        con.execute(
            f"""
            CREATE OR REPLACE TABLE {table} AS
            SELECT
                c.*,
                p.barangay_name,
                p.municipality_name,
                b.area_sqkm,
                b.longitude,
                b.latitude,
                b.geom
            FROM read_csv_auto(
                ?,
                types = {{'barangay_pcode': 'VARCHAR'}}
            ) AS c
            LEFT JOIN pcode_lookup AS p USING (barangay_pcode)
            LEFT JOIN barangays AS b USING (barangay_pcode)
            """,
            [str(path)],
        )

        counts[table] = _count(con, table)

    return counts


def load_barangay_rainfall(con: duckdb.DuckDBPyConnection) -> int | None:
    if not BGY_RAINFALL_PATH.exists():
        log.warning("%s not found: bgy_rainfall not built", BGY_RAINFALL_PATH.name)
        return None
    con.execute(
        """
        CREATE OR REPLACE TABLE bgy_rainfall AS
        SELECT c.*, w.year, w.mw, 28 AS window_days,
               p.* EXCLUDE (barangay_pcode), b.geom
        FROM (SELECT DISTINCT * FROM read_csv_auto(?, types={'barangay_pcode': 'VARCHAR'})) AS c
        LEFT JOIN morbidity_weeks AS w ON w.week_start = c.start_date
        LEFT JOIN pcode_lookup AS p USING (barangay_pcode)
        LEFT JOIN barangays AS b USING (barangay_pcode)
        """,
        [str(BGY_RAINFALL_PATH)],
    )
    return _count(con, "bgy_rainfall")


def run(con: duckdb.DuckDBPyConnection) -> dict[str, int]:
    """Build every map table. Order matters: lookup and barangays come before the tables that join them."""
    _load_spatial(con)
    counts: dict[str, int] = {}

    counts["health_units"] = load_health_units(con)
    counts["flood_hazards"] = load_flood_hazards(con)
    counts["barangays"] = load_barangays(con)
    counts.update(load_clusters(con))
    n = load_barangay_rainfall(con)
    if n is not None:
        counts["bgy_rainfall"] = n

    for table, n in counts.items():
        log.info("Map table %s: %d rows", table, n)
    return counts


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    _con = connect()
    init_schema(_con)
    run(_con)