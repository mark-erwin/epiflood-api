# FastAPI dependencies for database access

from typing import Annotated
import duckdb
from fastapi import Depends, Request
from db.connect import connect

def open_api_db() -> duckdb.DuckDBPyConnection:
    return connect(read_only=True)

def get_db(request: Request):
    cursor = request.app.state.db.cursor()
    try:
        yield cursor
    finally:
        cursor.close()
        
DB = Annotated[duckdb.DuckDBPyConnection, Depends(get_db)]
