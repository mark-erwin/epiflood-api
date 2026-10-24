# db/init_db.py

from pathlib import Path

from db.connect import get_db_connection

# Load SCHEMA_SQL at the module level so pipelines/common.py can import it
SCHEMA_SQL_PATH = Path(__file__).parent / "schema.sql"
SCHEMA_SQL = SCHEMA_SQL_PATH.read_text(encoding="utf-8") if SCHEMA_SQL_PATH.exists() else ""

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

if __name__ == "__main__":
    init_schema()