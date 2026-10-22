"""
rainfall.py - Rainfall routes (placeholders).

Each route returns a plain-text description of what it will do once implemented.
Mounted under /api/v1 in api.py.
"""

from datetime import date
from typing import Literal

from fastapi import APIRouter, Query
from fastapi.responses import PlainTextResponse

router = APIRouter(tags=["Rainfall"])


@router.get("/rainfall", response_class=PlainTextResponse)
def get_rainfall(
    pcode: str | None = None,
    start: date | None = None,
    end: date | None = None,
    granularity: Literal["daily", "weekly"] = "weekly",
    complete_weeks_only: bool = True,
    limit: int = Query(1000, ge=1, le=5000),
    offset: int = Query(0, ge=0),
) -> str:
    return (
        "GET /api/v1/rainfall\n"
        "\n"
        f"Received: pcode={pcode}, start={start}, end={end}, granularity={granularity}, "
        f"complete_weeks_only={complete_weeks_only}, limit={limit}, offset={offset}\n"
        "Expected: rainfall (Open-Meteo, municipality centroids) for a date range.\n"
        "Source: rainfall_daily (daily) or the rainfall_weekly view (weekly, aligned to "
        "Sunday-Saturday morbidity weeks).\n"
        "Response (daily): { total, limit, offset, data: [{ pcode, date, rain_mm }] }.\n"
        "Response (weekly): { ..., data: [{ pcode, year, mw, week_start, rain_mm_total, "
        "days_with_data }] }.\n"
        "Note: rain_mm = null is a missing day, not 0 mm. days_with_data < 7 is a partial week; "
        "complete_weeks_only=true hides those."
    )
