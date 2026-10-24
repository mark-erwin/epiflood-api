"""Human-readable descriptions for every table, view, and column -> `table_descriptions`.

They are served by GET /schema and /schema/{table}.
tests/etl/test_table_descriptions.py fails if this file and schema.sql drift apart.

Run by pipelines.run_all (after the metadata step) and by pipelines.build_data_dictionary.
"""

import logging

import duckdb

from pipeline.common import connect, init_schema

log = logging.getLogger("pipelines")

# table -> (description, {column: description})
TABLES: dict[str, tuple[str, dict[str, str]]] = {
    "municipalities": (
        "The 30 cities and municipalities of Laguna (Region IV-A). Every other table joins here by pcode.",
        {
            "pcode": "Administrative code (PSA/HDX pcode), e.g. PH043404000.",
            "name": "Official name as written in the boundary file.",
            "type": "'city' or 'municipality'.",
            "province": "Province name (always Laguna).",
            "region": "Region name (Region IV-A).",
            "centroid_lng": "Longitude of the centroid; used for rainfall queries.",
            "centroid_lat": "Latitude of the centroid; used for rainfall queries.",
            "area_km2": "Land area in square kilometres.",
            "boundary_geojson": "Simplified boundary geometry as GeoJSON text (map Layer 1).",
        },
    ),
    "municipality_crosswalk": (
        "Audit trail of how raw municipality names in each source were matched to a pcode.",
        {
            "raw_name": "Name exactly as written in the source file.",
            "source": "Source the name came from (doh_hdx, doh_eb).",
            "pcode": "Municipality the name was matched to.",
        },
    ),
    "pcode_lookup": (
        "Barangay -> municipality lookup (names and pcodes), built from the adm4 boundary file.",
        {
            "barangay_pcode": "Barangay administrative code.",
            "barangay_name": "Barangay name.",
            "municipality_pcode": "Code of the city/municipality the barangay belongs to.",
            "municipality_name": "Name of that city/municipality.",
        },
    ),
    "morbidity_weeks": (
        "Calendar of DOH morbidity weeks: Sunday to Saturday, week 1 = first week with at least 4 days in the year.",
        {
            "year": "Morbidity-week year (early January can belong to the previous year, late December to the next).",
            "mw": "Morbidity week number, 1 to 53 (53 in 2014, 2020 and 2025 within 2014-2027).",
            "week_start": "Sunday the week starts on.",
            "week_end": "Saturday the week ends on.",
        },
    ),
    "cases_weekly": (
        "Weekly dengue and leptospirosis cases per municipality. Missing weeks have no row; a NULL count means the source left it blank.",
        {
            "pcode": "Municipality code.",
            "disease": "'dengue' or 'leptospirosis'.",
            "year": "Morbidity-week year.",
            "mw": "Morbidity week.",
            "cases": "Reported cases. NULL = not reported (not the same as 0).",
            "deaths": "Reported deaths. NULL = not reported.",
            "source": "doh_eb (EB weekly reports) or doh_hdx (HDX 2016-2021). EB wins where both cover a week.",
            "ingested_at": "When the row was loaded.",
        },
    ),
    "cases_province_weekly": (
        "Laguna-wide weekly cases. Used only for sources that have no municipality breakdown.",
        {
            "province": "Province name.",
            "disease": "'dengue' or 'leptospirosis'.",
            "year": "Morbidity-week year.",
            "mw": "Morbidity week.",
            "cases": "Reported cases for the whole province. NULL = not reported.",
            "deaths": "Reported deaths for the whole province.",
            "source": "Source file the row came from.",
        },
    ),
    "rainfall_daily": (
        "Daily rainfall at each municipality centroid (Open-Meteo archive, Asia/Manila time).",
        {
            "pcode": "Municipality code.",
            "date": "Calendar date.",
            "rain_mm": "Total precipitation for the day in millimetres. NULL = missing day (not 0 mm).",
            "is_forecast": "True if the value is a forecast rather than an observation.",
            "source": "Data provider (open_meteo).",
        },
    ),
    "hazard_by_municipality": (
        "Share of each municipality covered by each flood-hazard level (area-weighted, precomputed).",
        {
            "pcode": "Municipality code.",
            "hazard_level": "1 = low, 2 = medium, 3 = high.",
            "area_km2": "Area of the municipality at this hazard level.",
            "pct_of_area": "Percentage of the municipality's area at this level (0-100).",
        },
    ),
    "data_sources": (
        "Inventory of the datasets behind the API (Appendix B), with coverage and row counts.",
        {
            "source_id": "Short id used in the source columns of other tables.",
            "title": "Dataset title.",
            "link": "Where the data comes from.",
            "description": "What the dataset contains.",
            "coverage_start": "First date covered by loaded data.",
            "coverage_end": "Last date covered by loaded data.",
            "last_ingested_at": "When the dataset was last refreshed.",
            "row_count": "Rows loaded from this source.",
        },
    ),
    "table_descriptions": (
        "The descriptions you are reading; served by /schema.",
        {
            "table_name": "Table or view name.",
            "column_name": "Column name, or '*' for the table itself.",
            "description": "Plain-language description.",
        },
    ),
    "rainfall_weekly": (
        "View: daily rainfall summed per morbidity week, so weeks line up with case weeks.",
        {
            "pcode": "Municipality code.",
            "year": "Morbidity-week year.",
            "mw": "Morbidity week.",
            "week_start": "Sunday the week starts on.",
            "rain_mm_total": "Rainfall total over the days that have data.",
            "days_with_data": "Days with a value (7 = complete week). Filter on 7 for reliable totals.",
            "includes_forecast": "True if any day in the week is a forecast.",
        },
    ),
    "dengue_baseline_5yr": (
        "View: dengue cases for each morbidity week averaged over the previous five years (map Layer 2).",
        {
            "pcode": "Municipality code.",
            "mw": "Morbidity week.",
            "mean_cases": "Mean weekly cases over the baseline years.",
            "median_cases": "Median weekly cases over the baseline years.",
            "max_cases": "Highest weekly cases over the baseline years.",
        },
    ),
}

# Tables created by pipelines/build_map_tables.py straight from map files (ST_Read), so their
# column set follows the files. They are not in schema.sql; only the columns known to exist are described.
LOADER_TABLES: dict[str, tuple[str, dict[str, str]]] = {
    "health_units": (
        "Health facilities in Laguna (map points) from OpenStreetMap, exported with Overpass Turbo "
        "(ODbL licence: credit 'OpenStreetMap contributors'). Loaded from health_facilities.geojson; "
        "the file carries many sparsely filled OSM tag columns, only the useful ones are listed here.",
        {
            "id": "OpenStreetMap element id, e.g. way/25589105 (unique).",
            "@id": "Same OpenStreetMap id as written by Overpass.",
            "name": "Facility name (missing for a few facilities).",
            "amenity": "OSM category: clinic, hospital, doctors, health_post (a few rows are not health facilities, e.g. townhall).",
            "healthcare": "Second OSM category tag (hospital, clinic, doctor, community_health_worker, birthing_centre...). Often empty.",
            "operator": "Who runs the facility.",
            "operator:type": "government, public or private; inconsistently filled.",
            "emergency": "'yes' if the facility has emergency services.",
            "ref:doh": "DOH facility reference, where mapped.",
            "addr:city": "City or municipality from the address tags (filled for under half of the rows).",
            "@geometry": "'center' when the OSM element was a building outline reduced to a point.",
            "geom": "Point geometry (EPSG:4326).",
        },
    ),
    "flood_hazards": (
        "Project NOAH 5-year flood-hazard polygons for Laguna (map Layer 0 and vector tiles). "
        "Loaded from laguna_floodhazard_5year.gpkg.",
        {
            "Var": "Hazard level: 1 = low, 2 = medium, 3 = high.",
            "geom": "Polygon geometry in EPSG:4326.",
            "geom_3857": "The same geometry in Web Mercator (EPSG:3857), with an R-tree index (flood_rtree) for tile lookups.",
        },
    ),
}


def seed_table_descriptions(con: duckdb.DuckDBPyConnection) -> int:
    """Replace the contents of `table_descriptions`. Safe to run repeatedly.

    Loader tables (LOADER_TABLES) are described only if they exist in the database,
    and only for the columns that actually exist."""
    rows = []
    for table, (desc, columns) in TABLES.items():
        rows.append((table, "*", desc))
        rows.extend((table, col, text) for col, text in columns.items())

    existing: dict[str, set[str]] = {}
    for table, col in con.execute(
        "SELECT table_name, column_name FROM information_schema.columns WHERE table_schema = 'main'"
    ).fetchall():
        existing.setdefault(table, set()).add(col)
    for table, (desc, columns) in LOADER_TABLES.items():
        if table in existing:
            rows.append((table, "*", desc))
            rows.extend((table, col, text) for col, text in columns.items() if col in existing[table])

    con.execute("DELETE FROM table_descriptions")
    con.executemany("INSERT INTO table_descriptions VALUES (?, ?, ?)", rows)
    log.info("Descriptions: %d rows", len(rows))
    return len(rows)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    _con = connect()
    init_schema(_con)
    print(seed_table_descriptions(_con), "description rows")
