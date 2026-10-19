from fastapi import APIRouter
from fastapi import Response
from db.connect import get_db_connection

router = APIRouter(tags=["Map"])

@router.get("/health-units")
def health_units():
    con = get_db_connection()
    try:
        cur = con.execute("""
        WITH cleaned_units AS (SELECT 
            name, 
            amenity, 
            ST_X(geom) AS longitude, 
            ST_Y(geom) AS latitude,
            ROW_NUMBER() OVER (PARTITION BY name) as rn
        FROM health_units
        WHERE name IS NOT NULL
            AND LOWER(COALESCE(name, '')) NOT LIKE '%dent%'
            AND LOWER(COALESCE(name, '')) NOT LIKE '%dental%'
            AND LOWER(COALESCE(name, '')) NOT LIKE '%skin%'
            AND LOWER(COALESCE(name, '')) NOT LIKE '%cat%'
            AND LOWER(COALESCE(name, '')) NOT LIKE '%dog%'
            AND LOWER(COALESCE(name, '')) NOT LIKE '%bite%'
            AND LOWER(COALESCE(name, '')) NOT LIKE '%animal%'
        )

        SELECT name, amenity, longitude, latitude
            FROM cleaned_units
            WHERE rn = 1
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

