"""/health, /schema, /schema/{table}, /sources"""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    version: str
    db: Literal["connected", "unavailable", "not_connected"]


class TableSummary(BaseModel):
    table: str
    kind: Literal["table", "view"]
    description: str | None = None


class ColumnInfo(BaseModel):
    name: str
    type: str
    nullable: bool
    description: str | None = None


class TableDetail(BaseModel):
    table: str
    kind: Literal["table", "view"]
    description: str | None = None
    columns: list[ColumnInfo]


class SourceInfo(BaseModel):
    source_id: str
    title: str
    link: str | None = None
    description: str | None = None
    coverage_start: date | None = None
    coverage_end: date | None = None
    last_ingested_at: datetime | None = None
    row_count: int | None = None
