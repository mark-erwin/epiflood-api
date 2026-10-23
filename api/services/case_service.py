"""Queries behind /cases, /cases/summary, /cases/timeseries and /cases/distribution.

Rules used throughout:
  * every user value is a `?` parameter; the only text spliced into SQL comes from the
    fixed whitelists in this file (GROUPS) or from our own constants
  * a missing value stays NULL -> None. It is never turned into 0
"""

import duckdb

from db.queries import fetch_all, fetch_one

# group_by -> (select list, GROUP BY list, ORDER BY)
GROUPS = {
    "municipality": ('c.pcode AS "group", m.name AS label', "c.pcode, m.name", "total_cases DESC NULLS LAST, label"),
    "year": ('c.year AS "group", NULL AS label', "c.year", '"group"'),
    "mw": ('c.mw AS "group", NULL AS label', "c.mw", '"group"'),
}

# cases_weekly joined to the municipality name and the week's dates
FROM_CASES = """
    FROM cases_weekly c
    JOIN municipalities m ON m.pcode = c.pcode
    LEFT JOIN morbidity_weeks w ON w.year = c.year AND w.mw = c.mw
"""


def build_where(f) -> tuple[str, list]:
    """WHERE clause for the shared case filters (disease, pcode, year, mw, start, end)."""
    clauses, params = [], []
    if f.disease:
        clauses.append("c.disease = ?")
        params.append(f.disease.value)
    if f.pcode:
        clauses.append("c.pcode = ?")
        params.append(f.pcode)
    if f.year:
        clauses.append("c.year = ?")
        params.append(f.year)
    if f.mw:
        clauses.append("c.mw = ?")
        params.append(f.mw)
    if f.start:
        clauses.append("w.week_start >= ?")
        params.append(f.start)
    if f.end:
        clauses.append("w.week_end <= ?")
        params.append(f.end)
    return ("WHERE " + " AND ".join(clauses)) if clauses else "", params


def list_cases(cur: duckdb.DuckDBPyConnection, f, limit: int, offset: int) -> tuple[list[dict], int]:
    where, params = build_where(f)
    total = cur.execute(f"SELECT COUNT(*) {FROM_CASES} {where}", params).fetchone()[0]
    rows = fetch_all(
        cur,
        f"""
        SELECT c.pcode, m.name AS municipality, c.disease, c.year, c.mw, w.week_start, c.cases, c.deaths
        {FROM_CASES} {where}
        ORDER BY c.year, c.mw, c.pcode
        LIMIT ? OFFSET ?
        """,
        params + [limit, offset],
    )
    return rows, total


def summary(cur: duckdb.DuckDBPyConnection, p) -> list[dict]:
    select, group_by, order_by = GROUPS[p.group_by]       # group_by is validated as a Literal
    where, params = build_where(p)
    return fetch_all(
        cur,
        f"""
        SELECT {select},
               SUM(c.cases)   AS total_cases,
               SUM(c.deaths)  AS total_deaths,
               COUNT(c.cases) AS weeks_reported
        {FROM_CASES} {where}
        GROUP BY {group_by}
        ORDER BY {order_by}
        """,
        params,
    )


def last_reported_week(cur: duckdb.DuckDBPyConnection, disease: str) -> tuple[int, int] | None:
    """(year, mw) of the most recent week with data, municipality-level or Laguna-wide."""
    row = cur.execute(
        """
        SELECT year, mw FROM (
            SELECT year, mw FROM cases_weekly WHERE disease = ? AND cases IS NOT NULL
            UNION
            SELECT year, mw FROM cases_province_weekly WHERE disease = ? AND cases IS NOT NULL
        ) ORDER BY year DESC, mw DESC LIMIT 1
        """,
        [disease, disease],
    ).fetchone()
    return (row[0], row[1]) if row else None


def timeseries(cur: duckdb.DuckDBPyConnection, p) -> list[dict]:
    """One point per morbidity week up to the last week with data. Gaps stay None."""
    disease = p.disease.value
    last = last_reported_week(cur, disease)
    if last is None:
        return []
    year_to = p.year_to or last[0]
    year_from = p.year_from or year_to - 1
    window = [year_from, year_to, last[0], last[1]]
    not_after_last = "(w.year, w.mw) <= (?, ?)"

    if p.pcode:
        return fetch_all(
            cur,
            f"""
            SELECT w.year, w.mw, w.week_start, c.cases
            FROM morbidity_weeks w
            LEFT JOIN cases_weekly c
                   ON c.year = w.year AND c.mw = w.mw AND c.disease = ? AND c.pcode = ?
            WHERE w.year BETWEEN ? AND ? AND {not_after_last}
            ORDER BY w.year, w.mw
            """,
            [disease, p.pcode] + window,
        )

    # Laguna-wide: sum of the municipalities; where none reported, fall back to the
    # province-level figure (e.g. an older source without a municipality breakdown)
    return fetch_all(
        cur,
        f"""
        WITH muni AS (
            SELECT year, mw, SUM(cases) AS cases, COUNT(cases) AS n
            FROM cases_weekly WHERE disease = ? GROUP BY year, mw
        )
        SELECT w.year, w.mw, w.week_start,
               COALESCE(m.cases, p.cases)       AS cases,
               COALESCE(m.n, 0)                 AS municipalities_reporting,
               CASE WHEN m.cases IS NOT NULL THEN 'municipality'
                    WHEN p.cases IS NOT NULL THEN 'province' END AS source
        FROM morbidity_weeks w
        LEFT JOIN muni m ON m.year = w.year AND m.mw = w.mw
        LEFT JOIN cases_province_weekly p
               ON p.year = w.year AND p.mw = w.mw AND p.disease = ?
        WHERE w.year BETWEEN ? AND ? AND {not_after_last}
        ORDER BY w.year, w.mw
        """,
        [disease, disease] + window,
    )


def distribution(cur: duckdb.DuckDBPyConnection, p) -> dict:
    disease = p.disease.value
    year_filter, year_params = ("AND c.year = ?", [p.year]) if p.year else ("", [])

    bins = fetch_all(
        cur,
        f"""
        SELECT (c.cases // ?) * ? AS bin_start, COUNT(*) AS weeks
        FROM cases_weekly c
        WHERE c.disease = ? AND c.cases IS NOT NULL {year_filter}
        GROUP BY 1 ORDER BY 1
        """,
        [p.bin_size, p.bin_size, disease] + year_params,
    )
    for b in bins:
        b["bin_end"] = b["bin_start"] + p.bin_size

    ranking = fetch_all(
        cur,
        f"""
        SELECT c.pcode, m.name AS municipality, SUM(c.cases) AS total_cases,
               RANK() OVER (ORDER BY SUM(c.cases) DESC) AS rank
        FROM cases_weekly c JOIN municipalities m ON m.pcode = c.pcode
        WHERE c.disease = ? AND c.cases IS NOT NULL {year_filter}
        GROUP BY c.pcode, m.name
        ORDER BY rank, m.name
        """,
        [disease] + year_params,
    )
    return {"disease": p.disease, "bin_size": p.bin_size, "histogram": bins, "ranking": ranking}
