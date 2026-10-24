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

class HazardCoverage(BaseModel):
    hazard_level: int          # 1 = low, 2 = medium, 3 = high
    area_km2: float
    pct_of_area: float
 
"""Add to models/reference.py (next to Municipality / MunicipalityDetail).

BarangayDetail mirrors MunicipalityDetail: `centroid` is a (lng, lat) pair and
`flood_hazard_summary` is {level_1_pct, level_2_pct, level_3_pct}. If MunicipalityDetail already
has a named model for that summary, use it for `flood_hazard_summary` instead of the dict below.
"""

from pydantic import BaseModel


class Barangay(BaseModel):
    pcode: str
    name: str
    municipality_pcode: str
    municipality_name: str

class BarangayDetail(Barangay):
    area_km2: float | None = None
    centroid: tuple[float, float] | None = None
    flood_hazard_summary: dict[str, float | None]

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
