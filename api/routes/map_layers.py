"""
map_layers.py - GeoJSON / tile routes for the dashboard map (placeholders).

Layer 0 flood hazard, Layer 1 municipal boundaries, Layer 2 five-year dengue baseline,
Layers 3 and 4 active-week cases (dengue / leptospirosis).
Each route returns a plain-text description of what it will do once implemented.
Mounted under /api/v1 in api.py.
"""

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse, Response
from db.deps import DB

from core.constants import MW_MAX, MW_MIN, Disease

router = APIRouter(prefix="/map", tags=["Map"])
from services import map_service


'''
@router.get("/cases", response_model=Page[CaseRow], responses=ERROR_RESPONSES)
def list_cases(
    db: DB,
    filters: Annotated[CaseFilters, Depends()],
    page: Annotated[Pagination, Depends()],
):
    """Weekly case rows, oldest week first, paginated.

    `cases` is null when a week was not reported, which is different from 0."""
    if filters.pcode:
        require_municipality(db, filters.pcode)
    rows, total = case_service.list_cases(db, filters, page.limit, page.offset)
    return Page[CaseRow](total=total, limit=page.limit, offset=page.offset, data=rows)
'''

@router.get("/health-units")
def health_units(
    db: DB
):
    return map_service.health_units(db)

@router.get("/flood-tiles/{z}/{x}/{y}.pbf")
def flood_tile(db: DB, z: int, x: int, y: int):
    row = map_service.flood_hazard(db, z, x, y)
    return Response(
        bytes(row[0]) if row and row[0] else b"",
        media_type="application/x-protobuf",
        headers={"Cache-Control": "public, max-age=86400"},
    )


    

'''    
@router.get("/flood-tiles/{z}/{x}/{y}.pbf")
def flood_tile(z: int, x: int, y: int):
    con = get_db_connection()
    try:
        row = con.execute("""
            WITH t AS (SELECT ST_TileEnvelope(?, ?, ?) AS env)
            SELECT ST_AsMVT(
                {'geom': ST_AsMVTGeom(f.geom_3857, ST_Extent(t.env)),
                 'hazard_level': f."Var"},
                'flood')
            FROM flood_hazards f, t
            WHERE ST_Intersects(f.geom_3857, t.env)
        """, [z, x, y]).fetchone()
    finally:
        con.close()

    return Response(
        bytes(row[0]) if row and row[0] else b"",
        media_type="application/x-protobuf",
        headers={"Cache-Control": "public, max-age=86400"},
    )
'''


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
