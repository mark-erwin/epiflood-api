"""Shared building blocks: pcode/week types, query-parameter types, pagination."""

from typing import Annotated, Generic, TypeVar

from fastapi import Query
from pydantic import BaseModel, Field

from core.constants import MW_MAX, MW_MIN

T = TypeVar("T")

YEAR_MIN, YEAR_MAX = 2016, 2100
PCODE_PATTERN = r"^PH\d+$"          # format only; whether it exists is checked against the database

# Optional query parameters, reused by every route that filters on them
PCodeQuery = Annotated[str | None, Query(pattern=PCODE_PATTERN, description="Municipality pcode, e.g. PH043404000")]
YearQuery = Annotated[int | None, Query(ge=YEAR_MIN, le=YEAR_MAX)]
MwQuery = Annotated[int | None, Query(ge=MW_MIN, le=MW_MAX, description="Morbidity week (Sunday-Saturday)")]


class Pagination:
    """Dependency: ?limit=100&offset=0 (limit capped at 1000)."""

    def __init__(
        self,
        limit: Annotated[int, Query(ge=1, le=1000)] = 100,
        offset: Annotated[int, Query(ge=0)] = 0,
    ):
        self.limit = limit
        self.offset = offset


class Page(BaseModel, Generic[T]):
    total: int = Field(ge=0, description="Rows matching the filters, ignoring limit and offset")
    limit: int
    offset: int
    data: list[T]
