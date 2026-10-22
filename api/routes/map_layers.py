"""
map_layers.py - GeoJSON / tile routes for the dashboard map (placeholders).

Layer 0 flood hazard, Layer 1 municipal boundaries, Layer 2 five-year dengue baseline,
Layers 3 and 4 active-week cases (dengue / leptospirosis).
Each route returns a plain-text description of what it will do once implemented.
Mounted under /api/v1 in api.py.
"""

from fastapi import APIRouter, Path, Query
from fastapi.responses import PlainTextResponse

from core.constants import MW_MAX, MW_MIN, Disease

router = APIRouter(prefix="/map", tags=["Map"])


@router.get("/flood-hazard", response_class=PlainTextResponse)
def flood_hazard(
    level: str | None = Query(None, description="Comma-separated hazard levels, e.g. 1,2,3"),
    bbox: str | None = Query(None, description="minLng,minLat,maxLng,maxLat"),
) -> str:
    return (
        "GET /api/v1/map/flood-hazard   (Layer 0)\n"
        "\n"
        f"Received: level={level}, bbox={bbox}\n"
        "Expected: simplified, bbox-clipped Project NOAH hazard polygons as GeoJSON.\n"
        "Source table: flood_hazard.\n"
        "Response: FeatureCollection, properties = { hazard_level, hazard_label }."
    )


@router.get("/flood-hazard/tiles/{z}/{x}/{y}", response_class=PlainTextResponse)
def flood_hazard_tiles(
    z: int = Path(ge=0, le=22),
    x: int = Path(ge=0),
    y: int = Path(ge=0),
) -> str:
    return (
        f"GET /api/v1/map/flood-hazard/tiles/{z}/{x}/{y}   (Layer 0, vector tiles)\n"
        "\n"
        "Expected: one Mapbox vector tile (.pbf) of the hazard layer.\n"
        "Decision pending: pre-build MBTiles/PMTiles with tippecanoe, or drop this route and "
        "serve simplified GeoJSON from /map/flood-hazard instead."
    )


@router.get("/boundaries", response_class=PlainTextResponse)
def boundaries() -> str:
    return (
        "GET /api/v1/map/boundaries   (Layer 1)\n"
        "\n"
        "Expected: Laguna city/municipality boundaries as GeoJSON.\n"
        "Source table: municipalities (boundary_geojson).\n"
        "Response: FeatureCollection, properties = { pcode, name, type, area_km2 }.\n"
        "Cache: long-lived."
    )


@router.get("/dengue/baseline", response_class=PlainTextResponse)
def dengue_baseline(
    years: int = Query(5, ge=1, le=10),
    mw: int | None = Query(None, ge=MW_MIN, le=MW_MAX),
) -> str:
    return (
        "GET /api/v1/map/dengue/baseline   (Layer 2)\n"
        "\n"
        f"Received: years={years}, mw={mw}\n"
        "Expected: historical dengue baseline per municipality (mean, median, max cases for "
        "the same morbidity week over the previous N years).\n"
        "Source: dengue_baseline_5yr view joined with municipality boundaries.\n"
        "Response: FeatureCollection, properties = { pcode, name, mw, mean_cases, "
        "median_cases, max_cases }."
    )


@router.get("/cases/{disease}", response_class=PlainTextResponse)
def active_cases(
    disease: Disease,
    year: int | None = Query(None, ge=2016, le=2100),
    mw: int | None = Query(None, ge=MW_MIN, le=MW_MAX),
) -> str:
    layer = "Layer 3" if disease == Disease.dengue else "Layer 4"
    return (
        f"GET /api/v1/map/cases/{disease.value}   ({layer})\n"
        "\n"
        f"Received: year={year}, mw={mw}\n"
        "Expected: active-week case counts per municipality as GeoJSON. Defaults to the latest "
        "reported week.\n"
        "Source: cases_weekly joined with municipality boundaries.\n"
        "Response: FeatureCollection, properties = { pcode, name, disease, year, mw, cases, "
        "baseline_mean }.\n"
        "Note: cases = null means 'not reported'."
    )
