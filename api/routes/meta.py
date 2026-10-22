"""
meta.py - /health, /schema, /schema/{table}, /sources.

/schema exposes the tables and views with their descriptions so client applications can
discover what exists without direct database access.
Mounted under /api/v1 in api.py.
"""

from typing import Annotated

import duckdb
from fastapi import APIRouter, HTTPException, Path, Request

from core.config import settings
from db.deps import DB
from models.errors import ERROR_RESPONSES
from models.meta import HealthResponse, SourceInfo, TableDetail, TableSummary
from services import meta_service

router = APIRouter(tags=["Meta"])


@router.get("/health", response_model=HealthResponse)
def health(request: Request):
    """API liveness plus whether the database is reachable."""
    db = getattr(request.app.state, "db", None)
    if db is None:
        state = "not_connected"
    else:
        try:
            db.cursor().execute("SELECT 1")
            state = "connected"
        except duckdb.Error:
            state = "unavailable"
    return HealthResponse(
        status="ok" if state == "connected" else "degraded",
        version=getattr(settings, "version", "0.1.0"),
        db=state,
    )


# Declared before /schema/{table}
@router.get("/schema", response_model=list[TableSummary], responses=ERROR_RESPONSES)
def list_schema(db: DB):
    """Every table and view with a short description."""
    return meta_service.list_tables(db)


@router.get("/schema/{table}", response_model=TableDetail, responses=ERROR_RESPONSES)
def describe_table(db: DB, table: Annotated[str, Path(max_length=100)]):
    """Columns, types, and descriptions for one table or view."""
    detail = meta_service.describe_table(db, table)
    if detail is None:
        raise HTTPException(404, f"Table '{table}' not found")
    return detail


@router.get("/sources", response_model=list[SourceInfo], responses=ERROR_RESPONSES)
def list_sources(db: DB):
    """The data inventory: where each dataset came from, its coverage and row count."""
    return meta_service.list_sources(db)
