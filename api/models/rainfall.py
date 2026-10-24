"""/rainfall/weekly, /rainfall/daily, /rainfall/coverage"""

from datetime import date as Date

from pydantic import BaseModel, Field


class RainfallWeekly(BaseModel):
    pcode: str
    municipality: str
    year: int
    mw: int
    week_start: Date
    rain_mm_total: float | None = None
    days_with_data: int = Field(ge=0, le=7, description="Days in the week with a rainfall value; 7 = complete")
    includes_forecast: bool = Field(description="True when at least one day is a model forecast, not an observation")


class RainfallDaily(BaseModel):
    pcode: str
    date: Date
    rain_mm: float | None = Field(None, description="None = missing, which is different from 0 mm")
    is_forecast: bool


class RainfallCoverage(BaseModel):
    first_date: Date | None = None
    last_date: Date | None = None
    last_observed_date: Date | None = Field(None, description="Last non-forecast day")
    municipalities: int = 0
    total_days: int = 0
    missing_days: int = Field(0, description="Rows whose rain_mm is NULL")
    has_forecast: bool = False
