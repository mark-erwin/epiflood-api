# database.py
import duckdb

DB_FILE = "database.duckdb"

def get_db_connection():
    return duckdb.connect(DB_FILE)

def init_db():
    con = get_db_connection()
    
    con.execute("""
        CREATE TABLE IF NOT EXISTS cases (
            case_id INTEGER PRIMARY KEY,
            barangay_code VARCHAR NOT NULL,
            patient_age INTEGER,
            date_reported DATE,
            is_severe BOOLEAN
        )
    """)
    
    con.close()
    print("Database initialized successfully.")