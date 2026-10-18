# api.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
import json
from db.init_db import get_db_connection, init_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(lifespan=lifespan)

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
        SELECT 
            name, 
            amenity, 
            ST_X(geom) AS longitude, 
            ST_Y(geom) AS latitude
        FROM health_units
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