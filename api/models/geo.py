"""GeoJSON envelopes for the map layers (Layers 0-4)."""

from typing import Any, Literal

from pydantic import BaseModel, Field


class Feature(BaseModel):
    type: Literal["Feature"] = "Feature"
    id: str | None = None
    geometry: dict[str, Any] | None = Field(None, description="None when ?geometry=false")
    properties: dict[str, Any]


class FeatureCollection(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    metadata: dict[str, Any] = Field(default_factory=dict, description="GeoJSON foreign member: week, legend hints, etc.")
    features: list[Feature]


class LayerInfo(BaseModel):
    layer: int = Field(ge=0, le=4)
    key: Literal["hazard", "boundaries", "baseline", "dengue_cases", "leptospirosis_cases"]
    name: str
    url: str
    params: list[str]
    cache_seconds: int
