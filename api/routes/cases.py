"""
cases.py - Dengue and leptospirosis case routes.

All paths are fixed (no /cases/{something}), so declaration order does not matter.
Mounted under /api/v1 in api.py.
"""

from typing import Annotated

from fastapi import APIRouter, Depends

from db.deps import DB
from models.cases import (
    CaseFilters, CaseRow, DistributionParams, DistributionResponse, SummaryParams, SummaryRow,
    TimeseriesParams, TimeseriesPoint,
)
from models.common import Page, Pagination
from models.errors import ERROR_RESPONSES
from services import case_service
from utils.validators import require_municipality

router = APIRouter(tags=["Cases"])


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


@router.get("/cases/summary", response_model=list[SummaryRow], responses=ERROR_RESPONSES)
def cases_summary(db: DB, params: Annotated[SummaryParams, Depends()]):
    """Totals per municipality, year, or morbidity week. Read `total_cases` with `weeks_reported`."""
    if params.pcode:
        require_municipality(db, params.pcode)
    return case_service.summary(db, params)


@router.get("/cases/timeseries", response_model=list[TimeseriesPoint], responses=ERROR_RESPONSES)
def cases_timeseries(db: DB, params: Annotated[TimeseriesParams, Depends()]):
    """One point per morbidity week for charts, ending at the last week with data.

    No `pcode` gives Laguna-wide totals. Weeks without data come back with `cases: null`."""
    if params.pcode:
        require_municipality(db, params.pcode)
    return case_service.timeseries(db, params)


@router.get("/cases/distribution", response_model=DistributionResponse, responses=ERROR_RESPONSES)
def cases_distribution(db: DB, params: Annotated[DistributionParams, Depends()]):
    """Histogram of weekly case counts plus a municipality ranking."""
    return case_service.distribution(db, params)
