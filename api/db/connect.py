from pathlib import Path
import duckdb
from core.config import settings

# Paths expected by pipelines and db scripts
API_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = getattr(settings, "db_path", API_ROOT / "db" / "database.duckdb")

class DatabaseLockedError(Exception):
    """Raised when the DuckDB database file is locked by another process."""
    pass

def get_db_connection(read_only: bool = False):
    try:
        con = duckdb.connect(str(DB_PATH), read_only=read_only)
        con.execute("INSTALL spatial;")
        con.execute("LOAD spatial;")
        return con
    except duckdb.IOException as e:
        if "lock" in str(e).lower():
            raise DatabaseLockedError(f"Database is locked: {e}") from e
        raise

# Aliases to support any module looking for different names
connect = get_db_connection
get_db = get_db_connection
open_db = get_db_connection