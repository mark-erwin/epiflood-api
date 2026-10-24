from datetime import date

from core.constants import Disease
from services.common import fetch_dicts


DISEASE_TABLES = {
    "dengue": "bgy_dengue_clusters",
    "leptospirosis": "bgy_leptospirosis_clusters",
}


def get_cases(
    con,
    *,
    disease: Disease,
    municipality_pcode: str | None = None,
    barangay_pcode: str | None = None,
    start: date | None = None,
    end: date | None = None,
) -> list[dict]:
    disease_name = str(
        getattr(disease, "value", disease)
    ).lower()

    table = DISEASE_TABLES.get(disease_name)

    if table is None:
        raise ValueError(f"Unsupported disease: {disease}")

    conditions = []
    params = []

    if municipality_pcode is not None:
        conditions.append("municipality_pcode = ?")
        params.append(municipality_pcode)

    if barangay_pcode is not None:
        conditions.append("barangay_pcode = ?")
        params.append(barangay_pcode)

    # Return clusters whose date intervals overlap
    # the requested date range.
    if start is not None:
        conditions.append("end_date >= ?")
        params.append(start)

    if end is not None:
        conditions.append("start_date <= ?")
        params.append(end)

    where = (
        "WHERE " + " AND ".join(conditions)
        if conditions
        else ""
    )

    return fetch_dicts(
        con,
        f"""
        SELECT
            municipality_pcode,
            barangay_pcode,
            start_date,
            end_date,
            cases
        FROM {table}
        {where}
        ORDER BY start_date, municipality_pcode, barangay_pcode
        """,
        params,
    )


def dengue_laguna_weekly(
    con,
    *,
    start: date | None = None,
    end: date | None = None,
) -> list[dict]:
    conditions = []
    params = []

    if start is not None:
        conditions.append('"date" >= ?')
        params.append(start)

    if end is not None:
        conditions.append('"date" <= ?')
        params.append(end)

    where = (
        "WHERE " + " AND ".join(conditions)
        if conditions
        else ""
    )

    return fetch_dicts(
        con,
        f"""
        SELECT "date", cases, deaths
        FROM DENGUE_CASES_LAGUNA_WEEKLY
        {where}
        ORDER BY "date"
        """,
        params,
    )