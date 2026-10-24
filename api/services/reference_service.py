"""Queries behind /municipalities, /barangays and /morbidity-weeks."""

import duckdb

from db.queries import fetch_all, fetch_one


def _hazard_summary(rows: list[dict]) -> dict:
    """{level_1_pct, level_2_pct, level_3_pct}; a level with no row stays None."""
    hazard = {1: None, 2: None, 3: None}
    for r in rows:
        hazard[r["hazard_level"]] = r["pct_of_area"]
    return {f"level_{level}_pct": pct for level, pct in hazard.items()}


def list_municipalities(cur: duckdb.DuckDBPyConnection, search: str | None = None, mtype: str | None = None) -> list[dict]:
    clauses, params = [], []
    if search:
        clauses.append("name ILIKE ?")
        params.append(f"%{search}%")
    if mtype:
        clauses.append("type = ?")
        params.append(mtype)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    # boundary_geojson is left out on purpose: it is heavy and served by /map/boundaries
    return fetch_all(cur, f"SELECT pcode, name, type, province, region FROM municipalities {where} ORDER BY name", params)


def get_municipality(cur: duckdb.DuckDBPyConnection, pcode: str) -> dict | None:
    row = fetch_one(
        cur,
        "SELECT pcode, name, type, province, region, centroid_lng, centroid_lat, area_km2 FROM municipalities WHERE pcode = ?",
        [pcode],
    )
    if row is None:
        return None
    lng, lat = row.pop("centroid_lng"), row.pop("centroid_lat")
    row["centroid"] = (lng, lat) if lng is not None and lat is not None else None
    row["flood_hazard_summary"] = _hazard_summary(
        fetch_all(cur, "SELECT hazard_level, pct_of_area FROM hazard_by_municipality WHERE pcode = ?", [pcode])
    )
    return row


def list_barangays(cur: duckdb.DuckDBPyConnection, search: str | None = None, municipality: str | None = None) -> list[dict]:
    """Barangays ordered by municipality then name. `municipality` is a municipality pcode.
    The geometry column is left out on purpose (heavy; served by the map routes)."""
    clauses, params = [], []
    if search:
        clauses.append("barangay_name ILIKE ?")
        params.append(f"%{search}%")
    if municipality:
        clauses.append("municipality_pcode = ?")
        params.append(municipality)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    return fetch_all(
        cur,
        f"""
        SELECT barangay_pcode AS pcode, barangay_name AS name, municipality_pcode, municipality_name
        FROM barangays {where}
        ORDER BY municipality_name, barangay_name
        """,
        params,
    )


def get_barangay(cur: duckdb.DuckDBPyConnection, pcode: str) -> dict | None:
    row = fetch_one(
        cur,
        """
        SELECT barangay_pcode AS pcode, barangay_name AS name, municipality_pcode, municipality_name,
               area_sqkm AS area_km2, longitude, latitude
        FROM barangays WHERE barangay_pcode = ?
        """,
        [pcode],
    )
    if row is None:
        return None
    lng, lat = row.pop("longitude"), row.pop("latitude")
    row["centroid"] = (lng, lat) if lng is not None and lat is not None else None
    row["flood_hazard_summary"] = _hazard_summary(
        fetch_all(cur, "SELECT hazard_level, pct_of_area FROM hazard_by_barangay WHERE barangay_pcode = ?", [pcode])
    )
    return row
