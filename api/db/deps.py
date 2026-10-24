"""FastAPI dependency for database access.

api.py opens ONE read-only connection at startup (app.state.db). Each request gets its
own cursor from it, because a single DuckDB connection must not be shared across threads.
Routes that query the database are declared with plain `def`, so FastAPI runs them in a
thread pool and the blocking query never stalls the event loop.
"""

from typing import Annotated

import duckdb
from fastapi import Depends, Request

from db.connect import connect

def open_api_db() -> duckdb.DuckDBPyConnection:
    """Read-only, so the API never holds the write lock that pipelines need."""
    return connect(read_only=True)

def get_db(request: Request):
    cursor = request.app.state.db.cursor()
    try:
        yield cursor
    finally:
        cursor.close()
        
DB = Annotated[duckdb.DuckDBPyConnection, Depends(get_db)]
