"""Human-readable descriptions for all database tables, views, and columns.

Descriptions are served by GET /schema and GET /schema/{table}.
Generated pipeline objects are documented alongside schema-defined objects.

Run by pipelines.run_all and pipelines.build_data_dictionary.
"""

import logging

import duckdb

from pipeline.common import connect, init_schema

log = logging.getLogger("pipelines")


# table -> (table description, {column name: column description})
TABLES: dict[str, tuple[str, dict[str, str]]] = {
    "municipalities": (
        "The 30 cities and municipalities of Laguna, Region IV-A.",
        {
            "pcode": "Administrative code assigned to the municipality.",
            "name": "Official city or municipality name.",
            "type": "Administrative type: city or municipality.",
            "province": "Province name.",
            "region": "Administrative region.",
            "centroid_lng": "Municipality centroid longitude.",
            "centroid_lat": "Municipality centroid latitude.",
            "area_km2": "Municipality area in square kilometres.",
            "boundary_geojson": "Municipality boundary as GeoJSON text, if available.",
        },
    ),
    "morbidity_weeks": (
        "Calendar mapping morbidity-week years and numbers to Sunday-through-Saturday date ranges.",
        {
            "year": "Morbidity-week year.",
            "mw": "Morbidity week number.",
            "week_start": "Sunday starting the morbidity week.",
            "week_end": "Saturday ending the morbidity week.",
        },
    ),
    "cases_province_weekly": (
        "Laguna-wide weekly case and death counts from the DOH-Epi HDX file (2016-2021). "
        "This is the only weekly case series; barangay data comes as four-week cluster records.",
        {
            "province": "Province covered by the report.",
            "disease": "Disease name, such as dengue or leptospirosis.",
            "year": "Morbidity-week year.",
            "mw": "Morbidity week number.",
            "cases": "Reported case count; NULL means unreported.",
            "deaths": "Reported death count; NULL means unreported.",
            "source": "Identifier of the source dataset.",
        },
    ),
    "rainfall_weekly": (
        "Weekly rainfall totals per municipality aligned to morbidity weeks, "
        "loaded from the weekly rainfall source file.",
        {
            "pcode": "Municipality administrative code.",
            "year": "Morbidity-week year.",
            "mw": "Morbidity week number.",
            "week_start": "Sunday starting the rainfall week.",
            "rain_mm_total": "Weekly precipitation total in millimetres.",
            "days_with_data": "Number of days represented by the weekly rainfall value; 7 indicates a complete week.",
        },
    ),
    "hazard_by_municipality": (
        "Precomputed flood-hazard coverage by municipality and hazard level.",
        {
            "pcode": "Municipality administrative code.",
            "hazard_level": "Flood-hazard category: 1 = low, 2 = medium, 3 = high.",
            "area_km2": "Area covered by this hazard level in square kilometres.",
            "pct_of_area": "Percentage of municipality area covered by this hazard level.",
        },
    ),
    "hazard_by_barangay": (
        "Precomputed flood-hazard coverage by barangay and hazard level.",
        {
            "barangay_pcode": "Barangay administrative code.",
            "hazard_level": "Flood-hazard category: 1 = low, 2 = medium, 3 = high.",
            "area_km2": "Area covered by this hazard level in square kilometres.",
            "pct_of_area": "Percentage of barangay area covered by this hazard level.",
        },
    ),
    "data_sources": (
        "Inventory of datasets loaded into the application, including coverage dates and row counts.",
        {
            "source_id": "Unique identifier for the dataset.",
            "title": "Human-readable dataset title.",
            "link": "URL for the dataset or provider.",
            "description": "Description of the dataset and its purpose.",
            "coverage_start": "Earliest date represented by loaded data, when known.",
            "coverage_end": "Latest date represented by loaded data, when known.",
            "last_ingested_at": "Timestamp of the last recorded ingestion.",
            "row_count": "Number of rows attributed to this source.",
        },
    ),
    "table_descriptions": (
        "Human-readable documentation of database tables, views, and columns.",
        {
            "table_name": "Name of the documented table or view.",
            "column_name": "Column name, or '*' for the table-level description.",
            "description": "Plain-language description of the table or column.",
        },
    ),
}


# Pipeline-generated tables and views.
# Column descriptions are inserted only when the column exists in DuckDB.
LOADER_TABLES: dict[str, tuple[str, dict[str, str]]] = {
    "pcode_lookup": (
        "Lookup mapping barangay administrative codes and names to their parent municipalities.",
        {
            "barangay_pcode": "Barangay administrative code.",
            "barangay_name": "Barangay name.",
            "municipality_pcode": "Parent municipality administrative code.",
            "municipality_name": "Parent municipality name.",
        },
    ),
    "barangays": (
        "Barangay boundary polygons for Laguna, including parent municipality, area, centroid and geometry.",
        {
            "barangay_pcode": "Barangay administrative code.",
            "barangay_name": "Barangay name.",
            "municipality_pcode": "Parent municipality administrative code.",
            "municipality_name": "Parent municipality name.",
            "area_sqkm": "Barangay area in square kilometres.",
            "longitude": "Barangay centroid longitude.",
            "latitude": "Barangay centroid latitude.",
            "geom": "Barangay boundary geometry.",
        },
    ),
    "health_units": (
        "Health facility map points sourced from OpenStreetMap. Coverage depends on mapped OSM data.",
        {
            "id": "OpenStreetMap element identifier.",
            "@id": "OpenStreetMap identifier as exported.",
            "name": "Facility name, if available.",
            "amenity": "OpenStreetMap amenity category.",
            "healthcare": "OpenStreetMap healthcare category.",
            "operator": "Facility operator, if available.",
            "operator:type": "Operator type, if available.",
            "emergency": "Emergency service tag, if available.",
            "ref:doh": "DOH facility reference, if mapped.",
            "addr:city": "City or municipality from address tags.",
            "geom": "Health facility point geometry.",
        },
    ),
    "flood_hazards": (
        "Project NOAH five-year flood-hazard polygons used for map display and spatial analysis.",
        {
            "Var": "Flood-hazard level: 1 = low, 2 = medium, 3 = high.",
            "geom": "Hazard polygon geometry in EPSG:4326.",
            "geom_3857": "Hazard geometry transformed to Web Mercator, EPSG:3857.",
        },
    ),
    "bgy_dengue_clusters": (
        "Barangay dengue cluster records from DOH Epidemiology Bureau reports. "
        "Source records cover four-week periods and are not individual weekly counts.",
        {
            "barangay_pcode": "Barangay administrative code.",
            "barangay_name": "Matched barangay name, if available.",
            "municipality_pcode": "Parent municipality administrative code, if available.",
            "municipality_name": "Parent municipality name, if available.",
            "area_sqkm": "Barangay area in square kilometres.",
            "longitude": "Barangay centroid longitude.",
            "latitude": "Barangay centroid latitude.",
            "geom": "Barangay boundary geometry.",
        },
    ),
    "bgy_lepto_clusters": (
        "Barangay leptospirosis cluster records from DOH Epidemiology Bureau reports. "
        "Source records cover four-week periods and are not individual weekly counts.",
        {
            "barangay_pcode": "Barangay administrative code.",
            "barangay_name": "Matched barangay name, if available.",
            "municipality_pcode": "Parent municipality administrative code, if available.",
            "municipality_name": "Parent municipality name, if available.",
            "area_sqkm": "Barangay area in square kilometres.",
            "longitude": "Barangay centroid longitude.",
            "latitude": "Barangay centroid latitude.",
            "geom": "Barangay boundary geometry.",
        },
    ),
    "bgy_rainfall": (
        "Barangay rainfall records joined to morbidity-week dates and barangay geometry.",
        {
            "barangay_pcode": "Barangay administrative code.",
            "barangay_name": "Barangay name, if available.",
            "municipality_pcode": "Parent municipality administrative code, if available.",
            "municipality_name": "Parent municipality name, if available.",
            "start_date": "Start date of the rainfall aggregation window, if present.",
            "end_date": "End date of the rainfall aggregation window, if present.",
            "year": "Morbidity-week year, if matched.",
            "mw": "Morbidity week number, if matched.",
            "window_days": "Number of days in the rainfall aggregation window.",
            "geom": "Barangay boundary geometry.",
        },
    ),
}


def seed_table_descriptions(con: duckdb.DuckDBPyConnection) -> int:
    """Refresh descriptions for every existing main-schema table and view.

    Known tables receive curated descriptions. Any other generated table or
    view receives a generic description, ensuring no existing object is omitted.
    Only columns actually present in DuckDB are documented.
    """
    existing: dict[str, set[str]] = {}
    kinds: dict[str, str] = {}

    for table, col, kind in con.execute(
        """
        SELECT c.table_name, c.column_name, t.table_type
        FROM information_schema.columns c
        JOIN information_schema.tables t
          ON c.table_catalog = t.table_catalog
         AND c.table_schema = t.table_schema
         AND c.table_name = t.table_name
        WHERE c.table_schema = 'main'
        """
    ).fetchall():
        existing.setdefault(table, set()).add(col)
        kinds[table] = kind

    descriptions = {**TABLES, **LOADER_TABLES}
    rows = []

    for table, columns in existing.items():
        if table in descriptions:
            desc, column_descriptions = descriptions[table]
        else:
            kind = kinds.get(table, "table").lower()
            desc = (
                f"Pipeline-generated {kind} used for epidemiological, "
                "environmental, geographic, or application data."
            )
            column_descriptions = {}

        rows.append((table, "*", desc))
        rows.extend(
            (table, col, text)
            for col, text in column_descriptions.items()
            if col in columns
        )

    con.execute("DELETE FROM table_descriptions")
    con.executemany(
        "INSERT INTO table_descriptions VALUES (?, ?, ?)",
        rows,
    )

    log.info(
        "Descriptions: %d rows across %d database objects",
        len(rows),
        len(existing),
    )
    return len(rows)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    con = connect()
    init_schema(con)
    print(seed_table_descriptions(con), "description rows")