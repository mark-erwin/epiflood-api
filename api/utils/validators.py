"""Checks that need the database."""

import duckdb
from fastapi import HTTPException


def require_municipality(cur: duckdb.DuckDBPyConnection, pcode: str) -> None:
    """404 unless `pcode` is one of the Laguna municipalities in the database."""
    if cur.execute("SELECT 1 FROM municipalities WHERE pcode = ?", [pcode]).fetchone() is None:
        raise HTTPException(404, f"Municipality '{pcode}' not found")
