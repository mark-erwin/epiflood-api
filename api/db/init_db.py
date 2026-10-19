# database.py
from pathlib import Path
import duckdb

DB_FILE = "database.duckdb"

# This file lives at msynk-pjdsc-2026/api/db/init_db.py (or similar).
# parents[0] = db, parents[1] = api, parents[2] = msynk-pjdsc-2026
BASE_DIR = Path(__file__).resolve().parents[2]
GIS_DIR = BASE_DIR / "data" / "gis"
EPI_DIR = BASE_DIR / "data" / "epidemiology"


def gis(name: str) -> str:
    return (GIS_DIR / name).as_posix()

def epi(name: str) -> str:
    return (EPI_DIR / name).as_posix()


def get_db_connection():
    con = duckdb.connect(DB_FILE)
    con.execute("INSTALL spatial;")
    con.execute("LOAD spatial;")
    return con


def init_db():
    con = get_db_connection()

    con.execute(
        "CREATE OR REPLACE TABLE barangays AS SELECT * FROM ST_Read(?)",
        [gis("laguna_barangay_geodata.geojson")],
    )

    con.execute(
        "CREATE OR REPLACE TABLE health_units AS SELECT * FROM ST_Read(?)",
        [gis("health_facilities.geojson")],
    )

    con.execute(
        "CREATE OR REPLACE TABLE flood_hazards AS SELECT * FROM ST_Read(?)",
        [gis("laguna_floodhazard_5year.gpkg")],
    )

    con.execute("ALTER TABLE flood_hazards ADD COLUMN geom_3857 GEOMETRY")
    con.execute("""
        UPDATE flood_hazards
        SET geom_3857 = ST_Transform(geom, 'EPSG:4326', 'EPSG:3857', always_xy := true)
    """)
    con.execute("CREATE INDEX flood_rtree ON flood_hazards USING RTREE (geom_3857)")

    con.execute(       
        """
        CREATE OR REPLACE TABLE pcode_lookup AS 
        SELECT * FROM ST_Read(?)
        """,
        [gis("laguna_pcode_lookup.csv")],
    )

    con.execute(
        """
        CREATE OR REPLACE TABLE bgy_dengue_cluster AS 
        SELECT 
            d.*, 
            l.barangay_name,
            ST_X(ST_Centroid(b.geom)) AS longitude,
            ST_Y(ST_Centroid(b.geom)) AS latitude
        FROM ST_Read(?) AS d
        JOIN pcode_lookup AS l 
            ON d.barangay_pcode = l.barangay_pcode
        JOIN barangays AS b 
            ON d.barangay_pcode = b.barangay_pcode
        """,
        [epi("laguna_bgy_pcode_dengue_clusters.csv")],
    )

    con.close()
    print("Database initialized successfully.")