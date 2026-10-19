# db/init_db.py
from db.connect import get_db_connection
import core.config as c

def load_map_tables(con):
    con.execute(
        "CREATE OR REPLACE TABLE health_units AS SELECT * FROM ST_Read(?)",
        [c.gis("health_facilities.geojson")],
    )

    con.execute(
        "CREATE OR REPLACE TABLE flood_hazards AS SELECT * FROM ST_Read(?)",
        [c.gis("laguna_floodhazard_5year.gpkg")],
    )
    con.execute("ALTER TABLE flood_hazards ADD COLUMN geom_3857 GEOMETRY")
    con.execute("""
        UPDATE flood_hazards
        SET geom_3857 = ST_Transform(geom, 'EPSG:4326', 'EPSG:3857', always_xy := true)
    """)
    con.execute("CREATE INDEX flood_rtree ON flood_hazards USING RTREE (geom_3857)")

    con.execute(
        "CREATE OR REPLACE TABLE pcode_lookup AS SELECT * FROM read_csv_auto(?)",
        [c.gis("laguna_pcode_lookup.csv")],
    )
    

def init_db():
    con = get_db_connection()
    try:
        load_map_tables(con)
    finally:
        con.close()
    print("Database initialized successfully.")


if __name__ == "__main__":
    init_db()