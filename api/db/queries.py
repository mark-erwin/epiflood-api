"""Small query helpers shared by the services. All values go through `?` placeholders."""

import duckdb


def fetch_all(cur: duckdb.DuckDBPyConnection, sql: str, params: list | None = None) -> list[dict]:
    result = cur.execute(sql, params or [])
    columns = [d[0] for d in result.description]
    return [dict(zip(columns, row)) for row in result.fetchall()]


def fetch_one(cur: duckdb.DuckDBPyConnection, sql: str, params: list | None = None) -> dict | None:
    rows = fetch_all(cur, sql, params)
    return rows[0] if rows else None


def scalar(cur: duckdb.DuckDBPyConnection, sql: str, params: list | None = None):
    row = cur.execute(sql, params or []).fetchone()
    return row[0] if row else None
