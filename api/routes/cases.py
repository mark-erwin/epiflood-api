from datetime import date
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from core.constants import Disease
from db.dependencies import DB
from models.common import PCODE_PATTERN
from models.errors import ERROR_RESPONSES
from services import case_service as svc
from services.export_service import FormatQuery, export_response

router = APIRouter(
    prefix="/cases",
    tags=["Cases"],
    responses=ERROR_RESPONSES,
)


def validate_dates(start: date | None, end: date | None):
    if start is not None and end is not None and start > end:
        raise HTTPException(
            status_code=422,
            detail="start must be on or before end",
        )


# --------------------------------------------------
# Weekly Laguna dengue cases and deaths
# --------------------------------------------------

@router.get(
    "/export/dengue/laguna/weekly",
    summary="Export weekly Laguna dengue cases and deaths",
)
def export_dengue_laguna_weekly(
    db: DB,
    start: date | None = None,
    end: date | None = None,
    fmt: FormatQuery = "csv",
):
    validate_dates(start, end)

    rows = svc.dengue_laguna_weekly(
        db,
        start=start,
        end=end,
    )

    filename = "dengue_laguna_weekly"
    if start is not None and end is not None:
        filename = f"dengue_laguna_weekly_{start}_{end}"

    return export_response(rows, filename, fmt)


@router.get(
    "/dengue/laguna/weekly",
    summary="Raw weekly dengue cases and deaths in Laguna",
)
def dengue_laguna_weekly(
    db: DB,
    start: date | None = None,
    end: date | None = None,
):
    validate_dates(start, end)

    return svc.dengue_laguna_weekly(
        db,
        start=start,
        end=end,
    )


# --------------------------------------------------
# Disease cluster records
# --------------------------------------------------

@router.get(
    "/export/{disease}",
    summary="Export disease cluster records",
)
def export_cases(
    db: DB,
    disease: Disease,
    municipality_pcode: Annotated[
        str | None, Query(pattern=PCODE_PATTERN)
    ] = None,
    barangay_pcode: Annotated[
        str | None, Query(pattern=PCODE_PATTERN)
    ] = None,
    start: date | None = None,
    end: date | None = None,
    fmt: FormatQuery = "csv",
):
    validate_dates(start, end)

    rows = svc.get_cases(
        db,
        disease=disease,
        municipality_pcode=municipality_pcode,
        barangay_pcode=barangay_pcode,
        start=start,
        end=end,
    )

    filename = f"cases_{disease.value}"

    return export_response(rows, filename, fmt)


@router.get(
    "/{disease}",
    summary="Get disease cases by barangay",
)
def get_cases(
    db: DB,
    disease: Disease,
    municipality_pcode: Annotated[
        str | None, Query(pattern=PCODE_PATTERN)
    ] = None,
    barangay_pcode: Annotated[
        str | None, Query(pattern=PCODE_PATTERN)
    ] = None,
    start: date | None = None,
    end: date | None = None,
):
    validate_dates(start, end)

    return svc.get_cases(
        db,
        disease=disease,
        municipality_pcode=municipality_pcode,
        barangay_pcode=barangay_pcode,
        start=start,
        end=end,
    )