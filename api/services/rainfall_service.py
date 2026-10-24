from datetime import date

from services.common import fetch_dicts, require_municipality


def weekly(con, *, pcode, year_from, year_to, min_days, include_forecast, limit, offset) -> dict:
    require_municipality(con, pcode)
    where, p = ["w.days_with_data >= ?"], [min_days]
    if pcode:
        where.append("w.pcode = ?"); p.append(pcode)
    if year_from:
        where.append("w.year >= ?"); p.append(year_from)
    if year_to:
        where.append("w.year <= ?"); p.append(year_to)
    if not include_forecast:
        where.append("NOT w.includes_forecast")
    clause = " AND ".join(where)
    total = con.execute(f"SELECT COUNT(*) FROM rainfall_weekly w WHERE {clause}", p).fetchone()[0]
    data = fetch_dicts(
        con,
        f"""SELECT w.pcode, m.name AS municipality, w.year, w.mw, w.week_start,
                   w.rain_mm_total, w.days_with_data, w.includes_forecast
            FROM rainfall_weekly w JOIN municipalities m ON m.pcode = w.pcode
            WHERE {clause}
            ORDER BY w.year, w.mw, m.name LIMIT ? OFFSET ?""",
        p + [limit, offset],
    )
    return {"total": total, "limit": limit, "offset": offset, "data": data}


def daily(con, *, pcode, start: date | None, end: date | None, include_forecast, limit, offset) -> dict:
    require_municipality(con, pcode)
    where, p = ["pcode = ?"], [pcode]
    if start:
        where.append("date >= ?"); p.append(start)
    if end:
        where.append("date <= ?"); p.append(end)
    if not include_forecast:
        where.append("NOT is_forecast")
    clause = " AND ".join(where)
    total = con.execute(f"SELECT COUNT(*) FROM rainfall_daily WHERE {clause}", p).fetchone()[0]
    data = fetch_dicts(
        con,
        f"SELECT pcode, date, rain_mm, is_forecast FROM rainfall_daily WHERE {clause} ORDER BY date LIMIT ? OFFSET ?",
        p + [limit, offset],
    )
    return {"total": total, "limit": limit, "offset": offset, "data": data}


def coverage(con) -> dict:
    row = fetch_dicts(
        con,
        """SELECT MIN(date) AS first_date, MAX(date) AS last_date,
                  MAX(date) FILTER (WHERE NOT is_forecast) AS last_observed_date,
                  COUNT(DISTINCT pcode) AS municipalities, COUNT(*) AS total_days,
                  COUNT(*) FILTER (WHERE rain_mm IS NULL) AS missing_days,
                  COALESCE(BOOL_OR(is_forecast), FALSE) AS has_forecast
           FROM rainfall_daily""",
    )[0]
    return row
