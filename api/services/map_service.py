
import duckdb
from db.queries import fetch_all, fetch_one

import datetime
import json

def flood_hazard(cur: duckdb.DuckDBPyConnection, z: float, x: float, y:float):
    row = cur.execute("""
        WITH t AS (SELECT ST_TileEnvelope(?, ?, ?) AS env)
        SELECT ST_AsMVT(
            {'geom': ST_AsMVTGeom(f.geom_3857, ST_Extent(t.env)),
                'hazard_level': f."Var"},
            'flood')
        FROM flood_hazards f, t
        WHERE ST_Intersects(f.geom_3857, t.env)
    """, [z, x, y]).fetchone()

    return row


def barangay_boundaries(cur):
    rows = fetch_all(cur, """
        SELECT b.barangay_pcode, p.barangay_name,
               ST_AsGeoJSON(ST_SimplifyPreserveTopology(b.geom, 0.0001)) AS geometry
        FROM barangays b
        LEFT JOIN pcode_lookup p USING (barangay_pcode)
    """)
    return {"type": "FeatureCollection", "features": [
        {"type": "Feature",
         "geometry": json.loads(r["geometry"]),
         "properties": {"pcode": r["barangay_pcode"], "name": r["barangay_name"]}}
        for r in rows
    ]}

def health_units(cur: duckdb.DuckDBPyConnection):
    units = fetch_all(
        cur,
        f"""
                WITH filtered AS (
            SELECT
                name,
                amenity,
                geom,
                -- TRUE = always_xy, so the geometry is read as lon/lat; result is in meters
                ST_Transform(geom, 'EPSG:4326', 'EPSG:32651', TRUE) AS geom_m,
                ROW_NUMBER() OVER (
                    ORDER BY
                        CASE amenity WHEN 'hospital' THEN 0 WHEN 'clinic' THEN 1 ELSE 2 END,
                        name
                ) AS prio
            FROM health_units
            WHERE name IS NOT NULL
                AND LOWER(name) NOT LIKE '%dent%'
                AND LOWER(name) NOT LIKE '%skin%'
                AND LOWER(name) NOT LIKE '%cat%'
                AND LOWER(name) NOT LIKE '%dog%'
                AND LOWER(name) NOT LIKE '%bite%'
                AND LOWER(name) NOT LIKE '%animal%'
        )
        SELECT
            a.name,
            a.amenity,
            ST_X(a.geom) AS longitude,
            ST_Y(a.geom) AS latitude
        FROM filtered a
        WHERE NOT EXISTS (
            SELECT 1
            FROM filtered b
            WHERE b.prio < a.prio
            AND ST_Distance(a.geom_m, b.geom_m) < 150
        )
        """,
    )

    features = []

    for row in units:
        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [row["longitude"], row["latitude"]],
            },
            "properties": {
                "name": row["name"],
                "amenity": row["amenity"],
            },
        }
        features.append(feature)

    return {"type": "FeatureCollection", "features": features}

CLUSTER_TABLES = {
    "dengue": "bgy_dengue_clusters",
    "leptospirosis": "bgy_lepto_clusters",
}

def clusters(cur, disease: str, start: datetime.date, end: datetime.date):
    table = CLUSTER_TABLES.get(disease)
    if table is None:
        raise ValueError(f"Unknown disease: {disease}")
    return fetch_all(
        cur,
        f"""
        SELECT barangay_pcode, barangay_name, municipality_name,
               longitude, latitude, cases, start_date, end_date
        FROM {table}
        WHERE longitude IS NOT NULL
          AND start_date = ? AND end_date = ?
        """,
        [start, end],
    )

def cluster_windows(cur, disease: str):
    table = CLUSTER_TABLES.get(disease)
    if table is None:
        raise ValueError(f"Unknown disease: {disease}")
    return fetch_all(
        cur,
        f"SELECT DISTINCT start_date, end_date FROM {table} ORDER BY start_date DESC",
    )

def pcode_lookup(cur: duckdb.DuckDBPyConnection):
    return fetch_all(cur, "SELECT * FROM pcode_lookup")