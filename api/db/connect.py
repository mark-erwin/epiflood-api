import duckdb
from core.config import settings

def get_db_connection():
    con = duckdb.connect(settings.db_path)
    con.execute("INSTALL spatial;")
    con.execute("LOAD spatial;")
    return con