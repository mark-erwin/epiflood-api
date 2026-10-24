"""Queries behind /municipalities and /morbidity-weeks."""

import duckdb

from db.queries import fetch_all, fetch_one


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

    hazard = {1: None, 2: None, 3: None}
    for r in fetch_all(cur, "SELECT hazard_level, pct_of_area FROM hazard_by_municipality WHERE pcode = ?", [pcode]):
        hazard[r["hazard_level"]] = r["pct_of_area"]
    row["flood_hazard_summary"] = {f"level_{level}_pct": pct for level, pct in hazard.items()}
    return row


def morbidity_weeks(cur: duckdb.DuckDBPyConnection, disease: str | None = None, year: int | None = None) -> dict:
    """Years and weeks that actually hold data (municipality-level or Laguna-wide)."""
    disease_filter = "AND disease = ?" if disease else ""
    sub_params = [disease] if disease else []
    year_filter = "WHERE year = ?" if year else ""
    params = sub_params + sub_params + ([year] if year else [])
    years = fetch_all(
        cur,
        f"""
        WITH reported AS (
            SELECT year, mw FROM cases_weekly WHERE cases IS NOT NULL {disease_filter}
            UNION
            SELECT year, mw FROM cases_province_weekly WHERE cases IS NOT NULL {disease_filter}
        )
        SELECT year, MIN(mw) AS first_mw, MAX(mw) AS last_mw, COUNT(*) AS weeks
        FROM reported {year_filter}
        GROUP BY year ORDER BY year
        """,
        params,
    )
    return {
        "earliest": {"year": years[0]["year"], "mw": years[0]["first_mw"]} if years else None,
        "latest": {"year": years[-1]["year"], "mw": years[-1]["last_mw"]} if years else None,
        "years": years,
    }
