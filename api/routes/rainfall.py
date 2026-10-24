"""/rainfall/weekly, /rainfall/daily, /rainfall/coverage"""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from db.deps import DB
from models.common import PCODE_PATTERN, Page, Pagination, PCodeQuery, YearQuery
from models.errors import ERROR_RESPONSES
from models.rainfall import RainfallCoverage, RainfallDaily, RainfallWeekly
from services import rainfall_service as svc

router = APIRouter(prefix="/rainfall", tags=["rainfall"], responses=ERROR_RESPONSES)
Pg = Annotated[Pagination, Depends()]


@router.get("/weekly", response_model=Page[RainfallWeekly], summary="Weekly rainfall per municipality, aligned to morbidity weeks")
def weekly(
    db: DB,
    page: Pg,
    pcode: PCodeQuery = None,
    year_from: YearQuery = None,
    year_to: YearQuery = None,
    min_days: Annotated[int, Query(ge=1, le=7, description="Drop weeks with fewer days of data (7 = complete weeks only)")] = 7,
    include_forecast: Annotated[bool, Query(description="Include weeks that contain forecast days")] = False,
):
    if year_from and year_to and year_from > year_to:
        raise HTTPException(422, "year_from must be <= year_to")
    return svc.weekly(db, pcode=pcode, year_from=year_from, year_to=year_to, min_days=min_days,
                      include_forecast=include_forecast, limit=page.limit, offset=page.offset)


@router.get("/daily", response_model=Page[RainfallDaily], summary="Daily rainfall for one municipality")
def daily(
    db: DB,
    page: Pg,
    pcode: Annotated[str, Query(pattern=PCODE_PATTERN, description="Required")],
    start: date | None = None,
    end: date | None = None,
    include_forecast: bool = True,
):
    if start and end and start > end:
        raise HTTPException(422, "start must be on or before end")
    return svc.daily(db, pcode=pcode, start=start, end=end, include_forecast=include_forecast,
                     limit=page.limit, offset=page.offset)


@router.get("/coverage", response_model=RainfallCoverage, summary="What rainfall data is loaded (empty until the pipeline has run)")
def coverage(db: DB):
    return svc.coverage(db)
