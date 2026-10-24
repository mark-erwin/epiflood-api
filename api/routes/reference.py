"""
reference.py - Lookup routes: /municipalities, /municipalities/{pcode}, /barangays,
/barangays/{pcode}, /morbidity-weeks.

These feed the dashboard's dropdowns and week pickers.
Mounted under /api/v1 in api.py.
"""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query

from core.constants import Disease
from db.dependencies import DB
from models.common import PCODE_PATTERN
from models.errors import ERROR_RESPONSES
from models.reference import (
    Barangay,
    BarangayDetail,
    MorbidityWeeksResponse,
    Municipality,
    MunicipalityDetail,
    MunicipalityType,
)
from services import reference_service
from services.export_service import FormatQuery, PartQuery, export_response, fetch_all

router = APIRouter(tags=["Reference"])


@router.get("/municipalities/export", responses=ERROR_RESPONSES)
def export_municipalities(
    db: DB,
    search: Annotated[str | None, Query(min_length=1, max_length=100, description="Name contains (case-insensitive)")] = None,
    mtype: Annotated[MunicipalityType | None, Query(alias="type")] = None,
    fmt: FormatQuery = "csv",
):
    data = reference_service.list_municipalities(db, search, mtype.value if mtype else None)
    return export_response(data, "municipalities", fmt)

@router.get("/municipalities", response_model=list[Municipality], responses=ERROR_RESPONSES)
def list_municipalities(
    db: DB,
    search: Annotated[str | None, Query(min_length=1, max_length=100, description="Name contains (case-insensitive)")] = None,
    mtype: Annotated[MunicipalityType | None, Query(alias="type")] = None,
):
    """All Laguna cities and municipalities, alphabetical."""
    return reference_service.list_municipalities(db, search, mtype.value if mtype else None)


@router.get("/municipalities/{pcode}/export", responses=ERROR_RESPONSES)
def export_municipality(db: DB, pcode: Annotated[str, Path(pattern=PCODE_PATTERN)], fmt: FormatQuery = "csv"):
    row = reference_service.get_municipality(db, pcode)
    if row is None:
        raise HTTPException(404, f"Municipality '{pcode}' not found")
    return export_response(row, f"municipality_{pcode}", fmt)


@router.get("/municipalities/{pcode}", response_model=MunicipalityDetail, responses=ERROR_RESPONSES)
def get_municipality(db: DB, pcode: Annotated[str, Path(pattern=PCODE_PATTERN)]):
    """One municipality with its centroid, area, and flood-hazard coverage."""
    row = reference_service.get_municipality(db, pcode)
    if row is None:
        raise HTTPException(404, f"Municipality '{pcode}' not found")
    return row


@router.get("/barangays/export", responses=ERROR_RESPONSES)
def export_barangays(
    db: DB,
    search: Annotated[str | None, Query(min_length=1, max_length=100, description="Name contains (case-insensitive)")] = None,
    municipality: Annotated[str | None, Query(pattern=PCODE_PATTERN, description="Only barangays of this municipality pcode")] = None,
    fmt: FormatQuery = "csv",
):
    data = reference_service.list_barangays(db, search, municipality)
    return export_response(data, "barangays", fmt)


@router.get("/barangays", response_model=list[Barangay], responses=ERROR_RESPONSES)
def list_barangays(
    db: DB,
    search: Annotated[str | None, Query(min_length=1, max_length=100, description="Name contains (case-insensitive)")] = None,
    municipality: Annotated[str | None, Query(pattern=PCODE_PATTERN, description="Only barangays of this municipality pcode")] = None,
):
    """Laguna barangays, alphabetical by municipality then name. Filter by name or municipality pcode."""
    return reference_service.list_barangays(db, search, municipality)


@router.get("/barangays/{pcode}/export", responses=ERROR_RESPONSES)
def export_barangay(db: DB, pcode: Annotated[str, Path(pattern=PCODE_PATTERN)], fmt: FormatQuery = "csv"):
    row = reference_service.get_barangay(db, pcode)
    if row is None:
        raise HTTPException(404, f"Barangay '{pcode}' not found")
    return export_response(row, f"barangay_{pcode}", fmt)


@router.get("/barangays/{pcode}", response_model=BarangayDetail, responses=ERROR_RESPONSES)
def get_barangay(db: DB, pcode: Annotated[str, Path(pattern=PCODE_PATTERN)]):
    """One barangay with its parent municipality, centroid, area, and flood-hazard coverage."""
    row = reference_service.get_barangay(db, pcode)
    if row is None:
        raise HTTPException(404, f"Barangay '{pcode}' not found")
    return row


@router.get("/morbidity-weeks/export", responses=ERROR_RESPONSES)
def export_morbidity_weeks(
    db: DB,
    disease: Disease | None = None,
    fmt: FormatQuery = "csv",
    part: PartQuery = None,
):
    data = reference_service.morbidity_weeks(db, disease.value if disease else None)
    return export_response(data, "morbidity_weeks", fmt, part)

@router.get("/morbidity-weeks", response_model=MorbidityWeeksResponse, responses=ERROR_RESPONSES)
def list_morbidity_weeks(db: DB, disease: Disease | None = None):
    """Years and weeks with reported weekly cases (Laguna-wide series), for the year and week selectors."""
    return reference_service.morbidity_weeks(db, disease.value if disease else None)