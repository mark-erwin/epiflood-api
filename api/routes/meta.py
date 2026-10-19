"""
meta.py - liveness check and schema source

Status: Placeholder

Each route returns a plain-text description of what it will do once
implemented. Mounted under /api/v1 in main.py.
"""

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse
from core.config import settings
from fastapi import Response

router = APIRouter(tags=["Meta"])


@router.get("/health")
def health():
    return {"status": "ok", "version": settings.version, "db": "not_connected"}


@router.get("/schema", response_class=PlainTextResponse)
def list_schema() -> str:
    return "GET /api/v1/schema\n\nExpected: list of all tables with descriptions."


@router.get("/schema/{table}", response_class=PlainTextResponse)
def describe_table(table: str) -> str:
    return f"GET /api/v1/schema/{table}\n\nExpected: columns, types, and descriptions for '{table}'."


@router.get("/sources", response_class=PlainTextResponse)
def list_sources() -> str:
    return "GET /api/v1/sources\n\nExpected: data inventory (Appendix B) with links and last-updated times."
