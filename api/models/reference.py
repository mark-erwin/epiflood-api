"""/municipalities, /municipalities/{pcode}, /morbidity-weeks"""

from enum import Enum

from pydantic import BaseModel, Field


class MunicipalityType(str, Enum):
    city = "city"
    municipality = "municipality"


class Municipality(BaseModel):
    pcode: str
    name: str
    type: MunicipalityType
    province: str
    region: str


class HazardSummary(BaseModel):
    """Share of the municipality's area at each NOAH flood-hazard level (0-100).
    None = not computed (the hazard pipeline has not run, or the level is absent from the layer)."""

    level_1_pct: float | None = Field(None, ge=0, le=100)
    level_2_pct: float | None = Field(None, ge=0, le=100)
    level_3_pct: float | None = Field(None, ge=0, le=100)


class MunicipalityDetail(Municipality):
    centroid: tuple[float, float] | None = Field(None, description="[longitude, latitude]")
    area_km2: float | None = None
    flood_hazard_summary: HazardSummary


class WeekRef(BaseModel):
    year: int
    mw: int


class YearCoverage(BaseModel):
    year: int
    first_mw: int
    last_mw: int
    weeks: int = Field(description="Weeks with data; fewer than last_mw - first_mw + 1 means gaps")


class MorbidityWeeksResponse(BaseModel):
    earliest: WeekRef | None = None
    latest: WeekRef | None = None
    years: list[YearCoverage]
