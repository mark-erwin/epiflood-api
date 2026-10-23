# db/init_db.py
from pathlib import Path
from db.connect import get_db_connection
import core.config as c

DB_PATH = Path(__file__).parent / "base_schema.duckdb"

# Load SCHEMA_SQL at the module level so pipelines/common.py can import it
SCHEMA_SQL_PATH = Path(__file__).parent / "schema.sql"
SCHEMA_SQL = SCHEMA_SQL_PATH.read_text(encoding="utf-8") if SCHEMA_SQL_PATH.exists() else ""

def load_map_tables(con):

    # Health Units
    con.execute(
        "CREATE OR REPLACE TABLE health_units AS SELECT * FROM ST_Read(?)",
        [c.gis("health_facilities.geojson")],
    )

    # Flood Hazards
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

    # Pcode Lookup
    con.execute(
        "CREATE OR REPLACE TABLE pcode_lookup AS SELECT * FROM read_csv_auto(?)",
        [c.gis("laguna_pcode_lookup.csv")],
    )

def init_schema(con=None):
    """Executes the schema.sql script on the provided connection or creates a new one."""
    close_conn = False
    if con is None:
        con = get_db_connection()
        close_conn = True

    try:
        if SCHEMA_SQL:
            con.execute(SCHEMA_SQL)
        else:
            raise FileNotFoundError(f"schema.sql not found at {SCHEMA_SQL_PATH}")
        print("Database schema initialized successfully!")
    finally:
        if close_conn:
            con.close()

def init_db():
    con = get_db_connection()
    try:
        load_map_tables(con)
    finally:
        con.close()
    print("Database map tables initialized successfully.")

if __name__ == "__main__":
    init_schema()
    init_db()