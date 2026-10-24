"""
export.py - Shared helpers for the export routes.

Turns a route's result into a file download: CSV (default, opens cleanly in Excel)
or JSON. GeoJSON results download as .geojson with format=json; as CSV they keep the
feature properties (plus longitude/latitude for point features).
Used by the routes in cases.py, map.py, rainfall.py, reference.py and meta.py.
"""

import csv
import io
import json
from typing import Annotated, Any, Callable, Literal

from fastapi import HTTPException, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import Response

PAGE_SIZE = 1000
MAX_EXPORT_ROWS = 500_000

FormatQuery = Annotated[
    Literal["csv", "json"],
    Query(
        alias="format",
        description="File format: csv (default) or json. GeoJSON layers download as .geojson with json.",
    ),
]
PartQuery = Annotated[
    str | None,
    Query(description="For responses that hold several tables, the name of the one to export."),
]


# ---------- shaping data into rows ----------

def _flat(value: dict, prefix: str = "", out: dict | None = None) -> dict:
    """Flatten nested dicts into dotted keys; lists become JSON text."""
    out = {} if out is None else out
    for key, item in value.items():
        name = f"{prefix}{key}"
        if isinstance(item, dict):
            _flat(item, f"{name}.", out)
        elif isinstance(item, (list, tuple)):
            out[name] = json.dumps(item, ensure_ascii=False)
        else:
            out[name] = item
    return out


def _is_feature_collection(data: Any) -> bool:
    return isinstance(data, dict) and data.get("type") == "FeatureCollection"


def _feature_rows(fc: dict) -> list[dict]:
    rows = []
    for feature in fc.get("features", []):
        row = _flat(feature.get("properties") or {})
        if feature.get("id") is not None:
            row.setdefault("id", feature["id"])
        geom = feature.get("geometry") or {}
        if geom.get("type") == "Point":
            row["longitude"], row["latitude"] = geom["coordinates"][:2]
        rows.append(row)
    return rows


def tabular_rows(data: Any, part: str | None = None) -> list[dict]:
    """Turn any route result into a list of flat dict rows."""
    data = jsonable_encoder(data)

    if _is_feature_collection(data):
        return _feature_rows(data)

    if isinstance(data, list):
        return [_flat(r) if isinstance(r, dict) else {"value": r} for r in data]

    if isinstance(data, dict):
        lists = {k: v for k, v in data.items() if isinstance(v, list)}
        if not lists:
            return [_flat(data)]  # a single record
        if part is None and len(lists) == 1:
            part = next(iter(lists))
        if part is None:
            raise HTTPException(422, f"This response has several tables. Pass part={' or part='.join(sorted(lists))}, or use format=json.")
        if part not in lists:
            raise HTTPException(422, f"part must be one of: {', '.join(sorted(lists))}")
        # Top-level fields that sit beside the table are repeated on every row.
        context = _flat({k: v for k, v in data.items() if not isinstance(v, list)})
        return [{**context, **row} for row in tabular_rows(lists[part])]

    raise HTTPException(422, "This response cannot be exported as CSV. Use format=json.")


def mapping_to_rows(data: Any, key_name: str) -> Any:
    """{key: value} lookups become [{key_name: key, ...value}]. Lists and nested tables pass through."""
    data = jsonable_encoder(data)
    if not isinstance(data, dict) or any(isinstance(v, list) for v in data.values()):
        return data
    return [{key_name: k, **(v if isinstance(v, dict) else {"value": v})} for k, v in data.items()]


def _to_csv(rows: list[dict]) -> str:
    if not rows:
        return ""
    fields = list(dict.fromkeys(key for row in rows for key in row))
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore", lineterminator="\r\n")
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


# ---------- paginated sources ----------

def unpack_page(page: Any) -> tuple[list, int]:
    """Split a Page response (model or dict) into (rows, total)."""
    p = jsonable_encoder(page)
    return p["data"], p["total"]


def fetch_all(fetch_page: Callable[[int, int], tuple[list, int]]) -> list:
    """Page through a service until every row is loaded.

    fetch_page(limit, offset) must return (rows, total)."""
    rows: list = []
    offset = 0
    while True:
        chunk, total = fetch_page(PAGE_SIZE, offset)
        chunk = jsonable_encoder(chunk)
        rows.extend(chunk)
        offset += PAGE_SIZE
        if len(rows) > MAX_EXPORT_ROWS:
            raise HTTPException(413, f"Export is limited to {MAX_EXPORT_ROWS:,} rows. Add filters to narrow it.")
        if not chunk or offset >= total:
            return rows


# ---------- response ----------

def export_response(data: Any, filename: str, fmt: str = "csv", part: str | None = None) -> Response:
    """Build the file download. `filename` has no extension."""
    if fmt == "json":
        data = jsonable_encoder(data)
        geo = _is_feature_collection(data)
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        media, ext = ("application/geo+json", "geojson") if geo else ("application/json", "json")
    else:
        body = _to_csv(tabular_rows(data, part)).encode("utf-8-sig")  # BOM so Excel reads UTF-8
        media, ext = "text/csv; charset=utf-8", "csv"

    return Response(
        content=body,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{filename}.{ext}"'},
    )