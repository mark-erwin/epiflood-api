"""/cases, /cases/summary, /cases/timeseries, /cases/distribution"""

from datetime import date
from typing import Annotated, Literal

from fastapi import HTTPException, Query
from pydantic import BaseModel, Field

from core.constants import Disease
from models.common import MwQuery, PCodeQuery, YearQuery

GroupBy = Literal["municipality", "year", "mw"]


# ---- query-parameter dependencies ---------------------------------------------------------
class CaseFilters:
    """Shared by /cases and (later) /export/cases so both accept identical filters."""

    def __init__(
        self,
        disease: Disease | None = None,
        pcode: PCodeQuery = None,
        year: YearQuery = None,
        mw: MwQuery = None,
        start: date | None = None,
        end: date | None = None,
    ):
        if start and end and start > end:
            raise HTTPException(422, "start must be on or before end")
        self.disease, self.pcode, self.year, self.mw = disease, pcode, year, mw
        self.start, self.end = start, end


class SummaryParams(CaseFilters):
    """Disease is required: adding dengue and leptospirosis together is meaningless."""

    def __init__(
        self,
        disease: Disease,
        group_by: GroupBy = "municipality",
        pcode: PCodeQuery = None,
        year: YearQuery = None,
        mw: MwQuery = None,
        start: date | None = None,
        end: date | None = None,
    ):
        super().__init__(disease, pcode, year, mw, start, end)
        self.group_by = group_by


class TimeseriesParams:
    """No pcode = Laguna-wide. year_from / year_to default to the latest two years with data."""

    def __init__(
        self,
        disease: Disease,
        pcode: PCodeQuery = None,
        year_from: YearQuery = None,
        year_to: YearQuery = None,
    ):
        if year_from and year_to and year_from > year_to:
            raise HTTPException(422, "year_from must be <= year_to")
        self.disease, self.pcode, self.year_from, self.year_to = disease, pcode, year_from, year_to


class DistributionParams:
    def __init__(
        self,
        disease: Disease,
        year: YearQuery = None,
        bin_size: Annotated[int, Query(ge=1, le=1000, description="Histogram bin width, in cases")] = 5,
    ):
        self.disease, self.year, self.bin_size = disease, year, bin_size


# ---- responses -------------------------------------------------------------------------------
class CaseRow(BaseModel):
    pcode: str
    municipality: str
    disease: Disease
    year: int
    mw: int
    week_start: date | None = None
    cases: int | None = Field(None, description="None = not reported (which is different from 0)")
    deaths: int | None = None


class SummaryRow(BaseModel):
    group: str | int | None = Field(description="pcode, year, or mw, depending on group_by")
    label: str | None = Field(None, description="Municipality name when grouped by municipality")
    total_cases: int | None = None
    total_deaths: int | None = None
    weeks_reported: int = Field(ge=0, description="Weeks with a reported value; read the totals together with this")


class TimeseriesPoint(BaseModel):
    year: int
    mw: int
    week_start: date
    cases: int | None = Field(None, description="None marks a gap, so a chart can show a break")
    municipalities_reporting: int | None = Field(
        None, description="Laguna-wide only: how many municipalities contributed (0 when the value is province-level)"
    )
    source: Literal["municipality", "province"] | None = Field(
        None, description="Laguna-wide only: whether the value is a sum of municipalities or a province-level figure"
    )


class DistributionBin(BaseModel):
    bin_start: int = Field(description="Inclusive")
    bin_end: int = Field(description="Exclusive: the bin holds weekly counts in [bin_start, bin_end)")
    weeks: int


class RankingRow(BaseModel):
    pcode: str
    municipality: str
    total_cases: int
    rank: int


class DistributionResponse(BaseModel):
    disease: Disease
    bin_size: int
    histogram: list[DistributionBin]
    ranking: list[RankingRow]
