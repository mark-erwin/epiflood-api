"""/map/layers, /map/hazard (L0), /map/boundaries (L1), /map/baseline (L2), /map/cases (L3, L4)"""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse, Response
from db.deps import DB
from fastapi import APIRouter, Query
from fastapi.responses import FileResponse

from core.constants import Disease
from models.common import MwQuery, YearQuery
from models.errors import ERROR_RESPONSES
from models.geo import FeatureCollection, LayerInfo
from services import map_service as svc

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

Geometry = Annotated[bool, Query(description="false = properties only, for joining onto /map/boundaries client-side")]


@router.get("/layers", response_model=list[LayerInfo], summary="Catalogue of Layers 0-4")
def layers():
    return svc.LAYERS


@router.get(
    "/hazard",
    summary="Layer 0: NOAH flood hazard, one MultiPolygon per level (1-3)",
    response_model=None,
    responses={200: {"content": {"application/geo+json": {}}}},
)
def hazard(detail: Annotated[Literal["low", "high"], Query(description="low = simplified, small; high = fuller detail")] = "low"):
    return FileResponse(svc.hazard_path(detail), media_type="application/geo+json")


@router.get("/boundaries", response_model=FeatureCollection, summary="Layer 1: municipal boundaries")
def boundaries(db: DB, geometry: Geometry = True):
    return svc.boundaries(db, geometry)


@router.get("/baseline", response_model=FeatureCollection, summary="Layer 2: 5-year dengue baseline for one morbidity week")
def baseline(db: DB, mw: MwQuery = None, geometry: Geometry = True):
    return svc.baseline(db, mw, geometry)


@router.get("/cases", response_model=FeatureCollection, summary="Layers 3-4: weekly cases per municipality")
def cases(db: DB, disease: Disease, year: YearQuery = None, mw: MwQuery = None, geometry: Geometry = True):
    return svc.cases(db, disease.value, year, mw, geometry)
