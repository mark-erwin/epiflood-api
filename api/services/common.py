from typing import Any, Sequence

from fastapi import HTTPException


def fetch_dicts(con, sql: str, params: Sequence[Any] = ()) -> list[dict]:
    con.execute(sql, list(params))
    cols = [d[0] for d in con.description]
    return [dict(zip(cols, row)) for row in con.fetchall()]


def require_municipality(con, pcode: str | None) -> None:
    if pcode and con.execute("SELECT 1 FROM municipalities WHERE pcode = ?", [pcode]).fetchone() is None:
        raise HTTPException(404, f"Unknown municipality {pcode}")
