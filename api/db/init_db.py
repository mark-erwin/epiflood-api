from pathlib import Path

from db.connect import get_db_connection

SCHEMA_SQL_PATH = Path(__file__).parent / "schema.sql"
SCHEMA_SQL = SCHEMA_SQL_PATH.read_text(encoding="utf-8") if SCHEMA_SQL_PATH.exists() else ""

def init_schema(con=None):
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

if __name__ == "__main__":
    init_schema()