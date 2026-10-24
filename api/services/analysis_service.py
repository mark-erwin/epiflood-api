
from datetime import date

from services.common import fetch_dicts


DISEASE_TABLES = {
    "dengue": "bgy_dengue_clusters",
    "leptospirosis": "bgy_lepto_clusters",
}

GEOGRAPHY_TABLES = {
    "municipality": {
        "hazard_table": "hazard_by_municipality",
        "hazard_code": "municipality_pcode",
        "case_code": "municipality_pcode",
    },
    "barangay": {
        "hazard_table": "hazard_by_barangay",
        "hazard_code": "barangay_pcode",
        "case_code": "barangay_pcode",
    },
}


def _disease_table(disease) -> str:
    name = str(getattr(disease, "value", disease)).lower()
    table = DISEASE_TABLES.get(name)

    if table is None:
        raise ValueError(f"Unsupported disease: {disease}")

    return table


def _geography(geography: str) -> dict:
    result = GEOGRAPHY_TABLES.get(geography)

    if result is None:
        raise ValueError(
            "geography must be 'municipality' or 'barangay'"
        )

    return result


def disease_over_time(
    con,
    *,
    disease,
    pcode: str | None = None,
    geography: str = "municipality",
    start: date | None = None,
    end: date | None = None,
) -> list[dict]:
    """Return observed disease cluster records and their date intervals."""
    table = _disease_table(disease)
    geo = _geography(geography)

    conditions = []
    params = []

    if pcode is not None:
        conditions.append(f"{geo['case_code']} = ?")
        params.append(pcode)

    # Include clusters that overlap the requested date range.
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

    query = f"""
        SELECT
            municipality_pcode,
            barangay_pcode,
            start_date,
            end_date,
            cases
        FROM {table}
        {where}
        ORDER BY start_date, municipality_pcode, barangay_pcode
    """

    return fetch_dicts(con, query, params)


def rainfall_over_time(
    con,
    *,
    geography: str = "municipality",
    municipality_pcode: str | None = None,
    start: date | None = None,
    end: date | None = None,
) -> list[dict]:
    """Return the original weekly rainfall records."""
    conditions = []
    params = []

    if geography == "municipality":
        table = "rainfall_per_muni_weekly"

        if municipality_pcode is not None:
            conditions.append("municipality_pcode = ?")
            params.append(municipality_pcode)

        select_columns = """
            municipality_pcode,
            date,
            precipitation_mm
        """

    elif geography == "laguna":
        if municipality_pcode is not None:
            raise ValueError(
                "municipality_pcode cannot be used with geography='laguna'"
            )

        table = "rainfall_laguna_weekly"
        select_columns = """
            date,
            precipitation_mm
        """

    else:
        raise ValueError(
            "geography must be 'municipality' or 'laguna'"
        )

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

    query = f"""
        SELECT {select_columns}
        FROM {table}
        {where}
        ORDER BY date
    """

    return fetch_dicts(con, query, params)


def seasonality(
    con,
    *,
    disease,
    pcode: str | None = None,
    geography: str = "municipality",
    year_from: int | None = None,
    year_to: int | None = None,
) -> list[dict]:
    """
    Summarize cluster case counts by ISO week of cluster start_date.

    These are cluster-level summaries, not weekly incident-case totals.
    """
    table = _disease_table(disease)
    geo = _geography(geography)

    conditions = []
    params = []

    if pcode is not None:
        conditions.append(f"{geo['case_code']} = ?")
        params.append(pcode)

    if year_from is not None:
        conditions.append("start_date >= ?")
        params.append(date(year_from, 1, 1))

    if year_to is not None:
        conditions.append("start_date < ?")
        params.append(date(year_to + 1, 1, 1))

    where = (
        "WHERE " + " AND ".join(conditions)
        if conditions
        else ""
    )

    query = f"""
        SELECT
            date_part('week', start_date)::INTEGER AS mw,
            AVG(cases) AS mean_cluster_cases,
            MEDIAN(cases) AS median_cluster_cases,
            quantile_cont(cases, 0.9) AS p90_cluster_cases,
            COUNT(
                DISTINCT date_part('year', start_date)
            ) AS years_observed
        FROM {table}
        {where}
        GROUP BY mw
        ORDER BY mw
    """

    return fetch_dicts(con, query, params)


def hazard_exposure(
    con,
    *,
    disease,
    hazard_level: int = 2,
    year: int | None = None,
    geography: str = "municipality",
) -> list[dict]:
    """Compare static hazard-area measurements with observed cluster cases."""
    case_table = _disease_table(disease)
    geo = _geography(geography)

    hazard_table = geo["hazard_table"]
    hazard_code = geo["hazard_code"]
    case_code = geo["case_code"]

    conditions = []
    params = []

    # Only count clusters entirely contained in the selected year.
    if year is not None:
        conditions.append("start_date >= ?")
        params.append(date(year, 1, 1))

        conditions.append("end_date <= ?")
        params.append(date(year, 12, 31))

    where = (
        "WHERE " + " AND ".join(conditions)
        if conditions
        else ""
    )

    query = f"""
        SELECT
            h.{hazard_code} AS pcode,
            h.hazard_level,
            h.area_km2,
            h.pct_of_area AS hazard_pct,
            COALESCE(c.total_cases, 0) AS total_cases
        FROM {hazard_table} AS h
        LEFT JOIN (
            SELECT
                {case_code} AS pcode,
                SUM(cases) AS total_cases
            FROM {case_table}
            {where}
            GROUP BY {case_code}
        ) AS c
            ON h.{hazard_code} = c.pcode
        WHERE h.hazard_level = ?
        ORDER BY h.pct_of_area DESC, h.{hazard_code}
    """

    params.append(hazard_level)

    return fetch_dicts(con, query, params)
