"""Queries behind /schema and /sources."""

import duckdb

from db.queries import fetch_all, fetch_one


def list_tables(cur: duckdb.DuckDBPyConnection) -> list[dict]:
    return fetch_all(
        cur,
        """
        SELECT t.table_name AS "table",
               CASE t.table_type WHEN 'VIEW' THEN 'view' ELSE 'table' END AS kind,
               d.description
        FROM information_schema.tables t
        LEFT JOIN table_descriptions d ON d.table_name = t.table_name AND d.column_name = '*'
        WHERE t.table_schema = 'main'
        ORDER BY kind, t.table_name
        """,
    )


def describe_table(cur: duckdb.DuckDBPyConnection, table: str) -> dict | None:
    """Columns of one table or view, or None if it does not exist.
    `table` only ever appears as a bound parameter, never inside the SQL text."""
    head = fetch_one(
        cur,
        """
        SELECT t.table_name AS "table",
               CASE t.table_type WHEN 'VIEW' THEN 'view' ELSE 'table' END AS kind,
               d.description
        FROM information_schema.tables t
        LEFT JOIN table_descriptions d ON d.table_name = t.table_name AND d.column_name = '*'
        WHERE t.table_schema = 'main' AND t.table_name = ?
        """,
        [table],
    )
    if head is None:
        return None
    head["columns"] = fetch_all(
        cur,
        """
        SELECT c.column_name AS name, c.data_type AS type, c.is_nullable = 'YES' AS nullable, d.description
        FROM information_schema.columns c
        LEFT JOIN table_descriptions d ON d.table_name = c.table_name AND d.column_name = c.column_name
        WHERE c.table_schema = 'main' AND c.table_name = ?
        ORDER BY c.ordinal_position
        """,
        [table],
    )
    return head


def list_sources(cur: duckdb.DuckDBPyConnection) -> list[dict]:
    return fetch_all(
        cur,
        """
        SELECT source_id, title, link, description, coverage_start, coverage_end, last_ingested_at, row_count
        FROM data_sources ORDER BY source_id
        """,
    )
