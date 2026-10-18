# api.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
import json
from db.init_db import get_db_connection, init_db
from fastapi.middleware.cors import CORSMiddleware

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

'''
@app.get("/barangays")
def barangays():
    con = get_db_connection()
    try:
        con.execute("LOAD spatial;")
        cur = con.execute("""
            SELECT * EXCLUDE geom, ST_AsGeoJSON(geom) AS geometry
            FROM barangays
        """)
        cols = [d[0] for d in cur.description]
        features = []
        for row in cur.fetchall():
            rec = dict(zip(cols, row))
            geometry = json.loads(rec.pop("geometry"))
            features.append({
                "type": "Feature",
                "properties": rec,
                "geometry": geometry,
            })
        return {"type": "FeatureCollection", "features": features}
    finally:
        con.close()
'''

@app.get("/health-units")
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