from datetime import date

from services.common import fetch_dicts


def weekly(
    con,
    *,
    municipality_pcode: str | None = None,
    start: date | None = None,
    end: date | None = None,
) -> list[dict]:
    conditions = []
    params = []

    if municipality_pcode is not None:
        conditions.append("municipality_pcode = ?")
        params.append(municipality_pcode)

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
        SELECT municipality_pcode, "date", precipitation_mm
        FROM rainfall_per_muni_weekly
        {where}
        ORDER BY "date", municipality_pcode
        """,
        params,
    )


def weekly_laguna(
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
        SELECT "date", precipitation_mm
        FROM rainfall_laguna_weekly
        {where}
        ORDER BY "date"
        """,
        params,
    )