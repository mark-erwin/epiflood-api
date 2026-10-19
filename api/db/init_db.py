# db/init_db.py
from db.connect import get_db_connection
import core.config as c

DB_PATH = Path(__file__).parent / "base_schema.duckdb"

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

def init_schema():
    con = get_db_connection()

    try:
        # Execute all SQL statements in your schema file
        with open(Path(__file__).parent / "schema.sql", "r") as file:
            sql_script = file.read()

        con.execute(sql_script)

        print("Database initialized successfully!")

    finally:
        con.close()



def init_db():
    con = get_db_connection()
    try:
        load_map_tables(con)
    finally:
        con.close()
    print("Database initialized successfully.")


if __name__ == "__main__":
    init_schema()
    init_db()
