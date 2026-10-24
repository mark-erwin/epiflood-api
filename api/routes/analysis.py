
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query

from core.constants import Disease
from db.dependencies import DB
from models.common import PCODE_PATTERN
from models.errors import ERROR_RESPONSES
from services import analysis_service as svc
from services.export_service import FormatQuery, export_response


router = APIRouter(
    prefix="/analysis",
    tags=["Analysis"],
    responses=ERROR_RESPONSES,
)


Geography = Literal["municipality", "barangay"]
RainfallGeography = Literal["municipality", "laguna"]


def validate_dates(
    start: date | None,
    end: date | None,
) -> None:
    if start is not None and end is not None and start > end:
        raise HTTPException(
            status_code=422,
            detail="start must be on or before end",
        )


def validate_years(
    year_from: int | None,
    year_to: int | None,
) -> None:
    if (
        year_from is not None
        and year_to is not None
        and year_from > year_to
    ):
        raise HTTPException(
            status_code=422,
            detail="year_from must be on or before year_to",
        )


def export_rows(rows: list[dict], filename: str, fmt: str):
    return export_response(rows, filename, fmt)


# ---------------------------------------------------------
# Disease over time
# ---------------------------------------------------------

@router.get(
    "/disease-over-time",
    summary="Get observed disease cluster records over time",
)
def disease_over_time(
    db: DB,
    disease: Disease,
    pcode: Annotated[
        str | None, Query(pattern=PCODE_PATTERN)
    ] = None,
    geography: Geography = "municipality",
    start: date | None = None,
    end: date | None = None,
):
    validate_dates(start, end)

    return svc.disease_over_time(
        db,
        disease=disease,
        pcode=pcode,
        geography=geography,
        start=start,
        end=end,
    )


@router.get(
    "/export/disease-over-time",
    summary="Export observed disease cluster records",
)
def export_disease_over_time(
    db: DB,
    disease: Disease,
    pcode: Annotated[
        str | None, Query(pattern=PCODE_PATTERN)
    ] = None,
    geography: Geography = "municipality",
    start: date | None = None,
    end: date | None = None,
    fmt: FormatQuery = "csv",
):
    validate_dates(start, end)

    rows = svc.disease_over_time(
        db,
        disease=disease,
        pcode=pcode,
        geography=geography,
        start=start,
        end=end,
    )

    return export_rows(
        rows,
        f"analysis_disease_over_time_{disease.value}",
        fmt,
    )


# ---------------------------------------------------------
# Rainfall over time
# ---------------------------------------------------------

@router.get(
    "/rainfall-over-time",
    summary="Get observed weekly rainfall records",
)
def rainfall_over_time(
    db: DB,
    geography: RainfallGeography = "municipality",
    municipality_pcode: Annotated[
        str | None, Query(pattern=PCODE_PATTERN)
    ] = None,
    start: date | None = None,
    end: date | None = None,
):
    validate_dates(start, end)

    try:
        return svc.rainfall_over_time(
            db,
            geography=geography,
            municipality_pcode=municipality_pcode,
            start=start,
            end=end,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc


@router.get(
    "/export/rainfall-over-time",
    summary="Export observed weekly rainfall records",
)
def export_rainfall_over_time(
    db: DB,
    geography: RainfallGeography = "municipality",
    municipality_pcode: Annotated[
        str | None, Query(pattern=PCODE_PATTERN)
    ] = None,
    start: date | None = None,
    end: date | None = None,
    fmt: FormatQuery = "csv",
):
    validate_dates(start, end)

    # Avoid accidentally exporting the entire municipality table.
    if (
        geography == "municipality"
        and municipality_pcode is None
        and start is None
        and end is None
    ):
        raise HTTPException(
            status_code=422,
            detail=(
                "For municipality rainfall exports, provide "
                "municipality_pcode, start, or end to narrow the export."
            ),
        )

    try:
        rows = svc.rainfall_over_time(
            db,
            geography=geography,
            municipality_pcode=municipality_pcode,
            start=start,
            end=end,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    filename = f"analysis_rainfall_over_time_{geography}"

    if municipality_pcode is not None:
        filename += f"_{municipality_pcode}"

    return export_rows(rows, filename, fmt)


# ---------------------------------------------------------
# Seasonality of cluster records
# ---------------------------------------------------------

@router.get(
    "/seasonality",
    summary="Summarize cluster cases by ISO week of start date",
)
def seasonality(
    db: DB,
    disease: Disease,
    pcode: Annotated[
        str | None, Query(pattern=PCODE_PATTERN)
    ] = None,
    geography: Geography = "municipality",
    year_from: int | None = Query(None, ge=2016, le=2100),
    year_to: int | None = Query(None, ge=2016, le=2100),
):
    validate_years(year_from, year_to)

    return svc.seasonality(
        db,
        disease=disease,
        pcode=pcode,
        geography=geography,
        year_from=year_from,
        year_to=year_to,
    )


@router.get(
    "/export/seasonality",
    summary="Export seasonality summary of cluster records",
)
def export_seasonality(
    db: DB,
    disease: Disease,
    pcode: Annotated[
        str | None, Query(pattern=PCODE_PATTERN)
    ] = None,
    geography: Geography = "municipality",
    year_from: int | None = Query(None, ge=2016, le=2100),
    year_to: int | None = Query(None, ge=2016, le=2100),
    fmt: FormatQuery = "csv",
):
    validate_years(year_from, year_to)

    rows = svc.seasonality(
        db,
        disease=disease,
        pcode=pcode,
        geography=geography,
        year_from=year_from,
        year_to=year_to,
    )

    filename = f"analysis_seasonality_{disease.value}"

    return export_rows(rows, filename, fmt)


# ---------------------------------------------------------
# Hazard exposure
# ---------------------------------------------------------

@router.get(
    "/hazard-exposure",
    summary="Compare hazard-area measurements with observed cases",
)
def hazard_exposure(
    db: DB,
    disease: Disease,
    hazard_level: int = Query(2, ge=1, le=3),
    year: int | None = Query(None, ge=2016, le=2100),
    geography: Geography = "municipality",
):
    return svc.hazard_exposure(
        db,
        disease=disease,
        hazard_level=hazard_level,
        year=year,
        geography=geography,
    )


@router.get(
    "/export/hazard-exposure",
    summary="Export hazard exposure and observed case counts",
)
def export_hazard_exposure(
    db: DB,
    disease: Disease,
    hazard_level: int = Query(2, ge=1, le=3),
    year: int | None = Query(None, ge=2016, le=2100),
    geography: Geography = "municipality",
    fmt: FormatQuery = "csv",
):
    rows = svc.hazard_exposure(
        db,
        disease=disease,
        hazard_level=hazard_level,
        year=year,
        geography=geography,
    )

    filename = (
        f"analysis_hazard_exposure_{disease.value}_"
        f"{geography}_level_{hazard_level}"
    )

    if year is not None:
        filename += f"_{year}"

    return export_rows(rows, filename, fmt)
