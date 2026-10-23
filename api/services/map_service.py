
import duckdb
from db.queries import fetch_all, fetch_one

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
