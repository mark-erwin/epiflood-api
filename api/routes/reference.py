"""
reference.py - Lookup routes: /municipalities, /municipalities/{pcode}, /morbidity-weeks.

These feed the dashboard's dropdowns and week pickers.
Mounted under /api/v1 in api.py.
"""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query

from core.constants import Disease
from db.deps import DB
from models.common import PCODE_PATTERN, YearQuery
from models.errors import ERROR_RESPONSES
from models.reference import MorbidityWeeksResponse, Municipality, MunicipalityDetail, MunicipalityType
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

@router.get("/morbidity-weeks/export", responses=ERROR_RESPONSES)
def export_morbidity_weeks(
    db: DB,
    disease: Disease | None = None,
    year: YearQuery = None,
    fmt: FormatQuery = "csv",
    part: PartQuery = None,
):
    data = reference_service.morbidity_weeks(db, disease.value if disease else None, year)
    return export_response(data, "morbidity_weeks", fmt, part)

@router.get("/morbidity-weeks", response_model=MorbidityWeeksResponse, responses=ERROR_RESPONSES)
def list_morbidity_weeks(db: DB, disease: Disease | None = None, year: YearQuery = None):
    """Years and weeks that hold data, for the dashboard's year and week selectors."""
    return reference_service.morbidity_weeks(db, disease.value if disease else None, year)
