"""/map/layers, /map/hazard (L0), /map/boundaries (L1), /map/baseline (L2), /map/cases (L3, L4)"""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse, Response
from db.deps import DB
from models.common import Page, Pagination
from typing import Annotated
from core.constants import Disease
from fastapi import HTTPException

import datetime

from core.constants import Disease
from models.common import MwQuery, YearQuery
from models.errors import ERROR_RESPONSES
from models.geo import FeatureCollection, LayerInfo
from services import map_service as svc

router = APIRouter(prefix="/map", tags=["Map"])
from services import map_service

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

@router.get("/clusters/{disease}/windows")
def get_cluster_windows(db: DB, disease: Disease):
    return map_service.cluster_windows(db, disease.value)

@router.get("/clusters/{disease}")
def get_clusters(
    db: DB,
    disease: Disease,
    start: datetime.date,
    end: datetime.date,
):
    if start > end:
        raise HTTPException(status_code=422, detail="start must be <= end")

    rows = map_service.clusters(db, disease.value, start, end)
    if not rows:
        raise HTTPException(
            status_code=404,
            detail="No cluster window matches that start and end date",
        )
    return rows


@router.get("/barangays")
def get_barangays(db: DB):
    return map_service.barangay_boundaries(db)

@router.get("/rainfall")
def get_rainfall_window(db: DB, start: datetime.date, end: datetime.date):
    return map_service.rainfall_windows(db, start, end)

@router.get("/rainfall/{barangay_pcode}")
def get_rainfall(
    db: DB,
    barangay_pcode: str,
    start: datetime.date,
    end: datetime.date,
):
    rows = map_service.rainfall(db, barangay_pcode, start, end)
    if not rows:
        raise HTTPException(
            status_code=404,
            detail="No rainfall record matches that barangay, start date and end date",
        )
    print(rows)
    return rows

@router.get("/pcode-lookup")
def get_pcode_lookup(db: DB):
    return map_service.pcode_lookup(db)
