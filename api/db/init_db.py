# database.py
import duckdb

DB_FILE = "database.duckdb"

def get_db_connection():
    con = duckdb.connect(DB_FILE)
    con.execute("INSTALL spatial;")
    con.execute("LOAD spatial;")
    return con

def init_db():
    con = get_db_connection()
    con.execute("""
        CREATE OR REPLACE TABLE barangays AS
        SELECT * FROM ST_Read('../data/gis/laguna_barangay_geodata.geojson')
    """)

    con.execute("""
        CREATE OR REPLACE TABLE health_units AS
        SELECT * FROM ST_Read('../data/gis/health_facilities.geojson')
    """)
        
    con.close()
    print("Database initialized successfully.")