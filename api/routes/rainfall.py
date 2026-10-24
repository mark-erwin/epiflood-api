from datetime import date
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from db.dependencies import DB
from models.common import PCODE_PATTERN
from models.errors import ERROR_RESPONSES
from services import rainfall_service as svc
from services.export_service import FormatQuery, export_response

router = APIRouter(
    prefix="/rainfall",
    tags=["Rainfall"],
    responses=ERROR_RESPONSES,
)


def validate_dates(start: date | None, end: date | None):
    if start is not None and end is not None and start > end:
        raise HTTPException(
            status_code=422,
            detail="start must be on or before end",
        )


# --------------------------------------------------
# Weekly rainfall per municipality
# --------------------------------------------------

@router.get(
    "/export/weekly",
    summary="Export raw weekly rainfall per municipality",
)
def export_weekly(
    db: DB,
    municipality_pcode: Annotated[
        str | None, Query(pattern=PCODE_PATTERN)
    ] = None,
    start: date | None = None,
    end: date | None = None,
    fmt: FormatQuery = "csv",
):
    validate_dates(start, end)

    rows = svc.weekly(
        db,
        municipality_pcode=municipality_pcode,
        start=start,
        end=end,
    )

    filename = "rainfall_weekly"

    if municipality_pcode is not None:
        filename += f"_{municipality_pcode}"

    if start is not None and end is not None:
        filename += f"_{start}_{end}"

    return export_response(rows, filename, fmt)


@router.get(
    "/weekly",
    summary="Raw weekly rainfall per municipality",
)
def weekly(
    db: DB,
    municipality_pcode: Annotated[
        str | None, Query(pattern=PCODE_PATTERN)
    ] = None,
    start: date | None = None,
    end: date | None = None,
):
    validate_dates(start, end)

    return svc.weekly(
        db,
        municipality_pcode=municipality_pcode,
        start=start,
        end=end,
    )


# --------------------------------------------------
# Weekly rainfall for Laguna
# --------------------------------------------------

@router.get(
    "/export/weekly/laguna",
    summary="Export raw weekly rainfall for Laguna",
)
def export_weekly_laguna(
    db: DB,
    start: date | None = None,
    end: date | None = None,
    fmt: FormatQuery = "csv",
):
    validate_dates(start, end)

    rows = svc.weekly_laguna(
        db,
        start=start,
        end=end,
    )

    filename = "rainfall_weekly_laguna"

    if start is not None and end is not None:
        filename += f"_{start}_{end}"

    return export_response(rows, filename, fmt)


@router.get(
    "/weekly/laguna",
    summary="Raw weekly rainfall for Laguna",
)
def weekly_laguna(
    db: DB,
    start: date | None = None,
    end: date | None = None,
):
    validate_dates(start, end)

    return svc.weekly_laguna(
        db,
        start=start,
        end=end,
    )