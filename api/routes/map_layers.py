from fastapi import APIRouter
from fastapi import Response
from db.connect import get_db_connection

router = APIRouter(tags=["Map"])

@router.get("/health-units")
def health_units():
    con = get_db_connection()
    try:
        cur = con.execute("""
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
        """)
        features = []

        for row in cur.fetchall():
            name, amenity, lon, lat = row
            
            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [lon, lat]
                },
                "properties": {
                    "name": name,
                    "amenity": amenity
                }
            }
            features.append(feature)

        return {"type": "FeatureCollection", "features": features}

    finally:
        con.close()

@router.get("/flood-tiles/{z}/{x}/{y}.pbf")
def flood_tile(z: int, x: int, y: int):
    con = get_db_connection()
    try:
        row = con.execute("""
            WITH t AS (SELECT ST_TileEnvelope(?, ?, ?) AS env)
            SELECT ST_AsMVT(
                {'geom': ST_AsMVTGeom(f.geom_3857, ST_Extent(t.env)),
                 'hazard_level': f."Var"},
                'flood')
            FROM flood_hazards f, t
            WHERE ST_Intersects(f.geom_3857, t.env)
        """, [z, x, y]).fetchone()
    finally:
        con.close()

    return Response(
        bytes(row[0]) if row and row[0] else b"",
        media_type="application/x-protobuf",
        headers={"Cache-Control": "public, max-age=86400"},
    )

