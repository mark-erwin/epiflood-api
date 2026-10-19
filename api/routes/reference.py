"""
reference.py - Reference and lookup routes

Status: Placeholder

Each route returns a plain-text description of what it will do once
implemented. Mounted under /api/v1 in main.py.
"""

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

router = APIRouter(tags=["Reference"])


@router.get("/municipalities", response_class=PlainTextResponse)
def list_municipalities() -> str:
    return (
        "GET /api/v1/municipalities\n"
        "\n"
        "Expected: list of all cities/municipalities in Laguna.\n"
        "Optional query params: search, type.\n"
        "Response: array of { pcode, name, type, province, region }."
    )


@router.get("/municipalities/{pcode}", response_class=PlainTextResponse)
def get_municipality(pcode: str) -> str:
    return (
        f"GET /api/v1/municipalities/{pcode}\n"
        "\n"
        "Expected: details for a single Laguna city/municipality.\n"
        "Response: { pcode, name, type, province, region, centroid, area_km2, "
        "flood_hazard_summary }.\n"
        "Errors: 404 if the pcode is not found."
    )


@router.get("/morbidity-weeks", response_class=PlainTextResponse)
def list_morbidity_weeks() -> str:
    return (
        "GET /api/v1/morbidity-weeks\n"
        "\n"
        "Expected: the years and morbidity weeks available in the database.\n"
        "Optional query params: disease, year.\n"
        "Response: { earliest, latest, years }."
    )
