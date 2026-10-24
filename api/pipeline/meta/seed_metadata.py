"""Fill `data_sources` (the /sources inventory) with real coverage and row counts.

Sources that have no rows in the database are left out, so /sources only lists
what was actually loaded. PAGASA normals and the HDX rainfall indicators from
Appendix B are not used by the pipeline and are therefore not listed.
"""

import logging

import duckdb

from pipeline.common import connect, init_schema

log = logging.getLogger("pipelines")

SOURCES = {
    "hdx_admin": {
        "title": "Philippines - Subnational Administrative Boundaries",
        "link": "https://data.humdata.org/dataset/cod-ab-phl",
        "description": "Administrative codes and boundaries for Laguna cities, municipalities and barangays.",
    },
    "doh_hdx": {
        "title": "DOH-Epi Dengue Data 2016-2021",
        "link": "https://data.humdata.org/dataset/philippine-dengue-cases-and-deaths",
        "description": "Laguna-wide weekly dengue cases and deaths, 2016-2021 (Humanitarian Data Exchange).",
    },
    "doh_eb": {
        "title": "DOH EB Weekly Surveillance Reports (clustering)",
        "link": "https://doh.gov.ph/health-statistics/",
        "description": "4-Week Rolling Period (Morbidity Week) dengue and leptospirosis cluster reports at barangay level from the DOH Epidemiology Bureau.",
    },
    "open_meteo": {
        "title": "Open-Meteo Historical Weather API",
        "link": "https://open-meteo.com/en/docs/historical-weather-api",
        "description": "Precipitation at barangay and municipality centroids.",
    },
    "health_facilities": {
        "title": "Health facilities in Laguna (OpenStreetMap)",
        "link": "https://www.openstreetmap.org/copyright",
        "description": "Health facility points exported from OpenStreetMap with Overpass Turbo. "
                       "ODbL licence: credit 'OpenStreetMap contributors'. Crowd-sourced, so coverage is incomplete.",
    },
    "noah": {
        "title": "Project NOAH Flood Hazard Maps (5-year)",
        "link": "https://huggingface.co/datasets/bettergovph/project-noah-hazard-maps",
        "description": "Flood hazard levels 1-3, summarised as the share of each municipality's and barangay's area.",
    },
}

# pipeline step -> source it refreshes
STEP_SOURCE = {
    "boundaries": {"hdx_admin"}, "eb": {"doh_eb"}, "hdx": {"doh_hdx"}, "rainfall": {"open_meteo"},
    "hazard": {"noah"}, "maps": {"noah", "health_facilities"},
}

def table_count(con: duckdb.DuckDBPyConnection, table: str) -> int | None:
    """Row count, or None if the table does not exist (e.g. map tables not loaded yet)."""
    exists = con.execute(
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'main' AND table_name = ?", [table]
    ).fetchone()[0]
    return con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] if exists else None

_CASE_STATS = """
    SELECT MIN(w.week_start), MAX(w.week_end), COUNT(*)
    FROM cases_province_weekly c JOIN morbidity_weeks w USING (year, mw)
    WHERE c.source = ?
"""

def _stats(con: duckdb.DuckDBPyConnection, source_id: str) -> tuple:
    if source_id == "doh_hdx":
        return con.execute(_CASE_STATS, [source_id]).fetchone()

    if source_id == "doh_eb":                     # barangay cluster records (4-week periods), no weekly table
        dengue = table_count(con, "bgy_dengue_clusters") or 0
        lepto = table_count(con, "bgy_lepto_clusters") or 0
        return None, None, dengue + lepto

    if source_id == "open_meteo":
        return con.execute("""
            SELECT
                MIN(week_start),
                MAX(week_start) + INTERVAL 6 DAYS,
                COUNT(*)
            FROM rainfall_weekly
        """).fetchone()

    if source_id == "noah":                       # hazard polygons if loaded, else municipality summary rows
        polygons = table_count(con, "flood_hazards")
        return (None, None, polygons or table_count(con, "hazard_by_barangay") or table_count(con, "hazard_by_municipality") or 0)
    if source_id == "health_facilities":
        return (None, None, table_count(con, "health_units") or 0)
    if source_id == "hdx_admin":
        return (None, None, (table_count(con, "municipalities") or 0) + (table_count(con, "barangays") or 0))
    raise KeyError(source_id)


def seed_metadata(con: duckdb.DuckDBPyConnection, refreshed: frozenset[str] | set[str] = frozenset()) -> dict[str, int]:
    """Upsert one row per loaded source. `refreshed` = source ids loaded in this run
    (their last_ingested_at moves to now; the others keep their old timestamp)."""
    counts: dict[str, int] = {}
    for source_id, meta in SOURCES.items():
        start, end, n = _stats(con, source_id)
        if not n:
            con.execute("DELETE FROM data_sources WHERE source_id = ?", [source_id])
            continue
        counts[source_id] = n
        stamp_now = source_id in refreshed
        con.execute(
            """
            INSERT INTO data_sources
                (source_id, title, link, description, coverage_start, coverage_end, last_ingested_at, row_count)
            VALUES (?, ?, ?, ?, ?, ?, now(), ?)
            ON CONFLICT (source_id) DO UPDATE SET
                title = excluded.title, link = excluded.link, description = excluded.description,
                coverage_start = excluded.coverage_start, coverage_end = excluded.coverage_end,
                row_count = excluded.row_count,
                last_ingested_at = CASE WHEN ? THEN now() ELSE data_sources.last_ingested_at END
            """,
            [source_id, meta["title"], meta["link"], meta["description"], start, end, n, stamp_now],
        )
    return counts


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    _con = connect()
    init_schema(_con)
    print(seed_metadata(_con))