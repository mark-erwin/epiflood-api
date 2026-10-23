"""
export.py - Data export routes (placeholders).

Each route returns a plain-text description of what it will do once implemented.
Mounted under /api/v1 in api.py. Real versions return a file download
(Content-Disposition is already exposed through CORS).
"""

from datetime import date
from typing import Literal

from fastapi import APIRouter, Query
from fastapi.responses import PlainTextResponse

from core.constants import MW_MAX, MW_MIN, Disease

router = APIRouter(prefix="/export", tags=["Export"])

TabularFormat = Literal["csv", "json", "xlsx"]


@router.get("/cases", response_class=PlainTextResponse)
def export_cases(
    fmt: TabularFormat = Query("csv", alias="format"),
    disease: Disease | None = None,
    pcode: str | None = None,
    year: int | None = Query(None, ge=2016, le=2100),
    mw: int | None = Query(None, ge=MW_MIN, le=MW_MAX),
    start: date | None = None,
    end: date | None = None,
) -> str:
    return (
        "GET /api/v1/export/cases\n"
        "\n"
        f"Received: format={fmt}, disease={disease}, pcode={pcode}, year={year}, mw={mw}, "
        f"start={start}, end={end}\n"
        "Expected: the same rows as /cases with the same filters, but unpaginated, as a "
        "downloadable file.\n"
        "Response: file attachment (csv, json, or xlsx)."
    )


@router.get("/rainfall", response_class=PlainTextResponse)
def export_rainfall(
    fmt: TabularFormat = Query("csv", alias="format"),
    pcode: str | None = None,
    start: date | None = None,
    end: date | None = None,
    granularity: Literal["daily", "weekly"] = "weekly",
) -> str:
    return (
        "GET /api/v1/export/rainfall\n"
        "\n"
        f"Received: format={fmt}, pcode={pcode}, start={start}, end={end}, "
        f"granularity={granularity}\n"
        "Expected: the same rows as /rainfall, unpaginated, as a downloadable file.\n"
        "Response: file attachment (csv, json, or xlsx)."
    )


@router.get("/geojson/{layer}", response_class=PlainTextResponse)
def export_geojson(
    layer: Literal["boundaries", "flood-hazard", "dengue-baseline", "dengue-cases", "leptospirosis-cases"],
    year: int | None = Query(None, ge=2016, le=2100),
    mw: int | None = Query(None, ge=MW_MIN, le=MW_MAX),
) -> str:
    return (
        f"GET /api/v1/export/geojson/{layer}\n"
        "\n"
        f"Received: year={year}, mw={mw}\n"
        "Expected: a map layer as a downloadable GeoJSON file (same data as the /map routes, "
        "for use in QGIS or other GIS tools).\n"
        "Response: file attachment (.geojson)."
    )


@router.get("/dataframe", response_class=PlainTextResponse)
def export_dataframe(
    dataset: Literal["cases", "rainfall"] = "cases",
    orient: Literal["split", "records"] = "split",
    disease: Disease | None = None,
    pcode: str | None = None,
    year: int | None = Query(None, ge=2016, le=2100),
) -> str:
    return (
        "GET /api/v1/export/dataframe\n"
        "\n"
        f"Received: dataset={dataset}, orient={orient}, disease={disease}, pcode={pcode}, "
        f"year={year}\n"
        "Expected: JSON that loads straight into pandas with pd.DataFrame(...) or "
        "pd.read_json(..., orient=orient).\n"
        "Note: an HTTP API cannot return a literal DataFrame; this is the closest equivalent."
    )
