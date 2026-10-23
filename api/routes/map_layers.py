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
from models.common import Page, Pagination
from typing import Annotated
from core.constants import Disease
from fastapi import HTTPException

import datetime

from core.constants import MW_MAX, MW_MIN, Disease

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

@router.get("/pcode-lookup")
def get_pcode_lookup(db: DB):
    return map_service.pcode_lookup(db)