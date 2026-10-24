"""Sanity checks to run after every ingest. Hard failures return a non-zero exit code."""

import logging
import sys
from dataclasses import dataclass

import duckdb

from pipeline.common import EXPECTED_LAGUNA_LGUS, connect
from pipeline.meta.seed_metadata import table_count

log = logging.getLogger("pipelines")

@dataclass
class Check:
    name: str
    passed: bool
    detail: str
    hard: bool = True

def _scalar(con, sql: str, params=None):
    return con.execute(sql, params or []).fetchone()[0]

def run_checks(con: duckdb.DuckDBPyConnection, expected_lgus: int = EXPECTED_LAGUNA_LGUS) -> list[Check]:
    checks: list[Check] = []

    n = _scalar(con, "SELECT COUNT(*) FROM municipalities")
    checks.append(Check("municipality count", n == expected_lgus, f"{n} (expected {expected_lgus})"))

    n = _scalar(con, "SELECT COUNT(*) FROM morbidity_weeks")
    checks.append(Check("calendar seeded", n > 0, f"{n} weeks"))

    n = _scalar(con, "SELECT COUNT(*) FROM cases_weekly c LEFT JOIN municipalities m USING (pcode) WHERE m.pcode IS NULL")
    checks.append(Check("no orphan case rows", n == 0, f"{n} orphan rows"))

    n = _scalar(con, "SELECT COUNT(*) FROM cases_weekly WHERE cases < 0 OR deaths < 0")
    checks.append(Check("no negative counts", n == 0, f"{n} rows"))

    n = _scalar(con, "SELECT COUNT(*) FROM cases_weekly c LEFT JOIN morbidity_weeks w USING (year, mw) WHERE w.year IS NULL")
    checks.append(Check("case weeks exist in calendar", n == 0, f"{n} rows outside the calendar"))

    for disease in ("dengue", "leptospirosis"):
        row = con.execute(
            "SELECT MIN(year), MAX(year), COUNT(DISTINCT (year, mw)), COUNT(DISTINCT pcode) "
            "FROM cases_weekly WHERE disease = ? AND cases IS NOT NULL", [disease]
        ).fetchone()
        checks.append(Check(
            f"{disease} municipality coverage", row[2] > 0,
            f"years {row[0]}-{row[1]}, {row[2]} weeks, {row[3]} municipalities", hard=False,
        ))

    n_prov = _scalar(con, "SELECT COUNT(*) FROM cases_province_weekly")
    checks.append(Check("province-level cases (info)", True, f"{n_prov} rows", hard=False))

    n = _scalar(con, "SELECT COUNT(DISTINCT pcode) FROM rainfall_weekly")
    checks.append(Check("rainfall covers all municipalities", n == expected_lgus, f"{n} municipalities", hard=False))

    n = _scalar(con, "SELECT COUNT(*) FROM rainfall_weekly WHERE days_with_data < 7")
    checks.append(Check("incomplete rainfall weeks (info)", True, f"{n} partial municipality-weeks (excluded by default)", hard=False))

    n = _scalar(con, "SELECT COUNT(DISTINCT pcode) FROM hazard_by_municipality")
    checks.append(Check("hazard covers all municipalities", n == expected_lgus, f"{n} municipalities", hard=False))

    n = _scalar(con, "SELECT COUNT(*) FROM hazard_by_municipality WHERE pct_of_area < 0 OR pct_of_area > 100")
    checks.append(Check("hazard percentages in 0-100", n == 0, f"{n} out-of-range rows"))

    n = _scalar(con, "SELECT COUNT(*) FROM municipalities WHERE centroid_lat IS NULL OR centroid_lng IS NULL OR boundary_geojson IS NULL")
    checks.append(Check("municipalities have centroids and boundaries", n == 0, f"{n} incomplete rows"))

    for table, label in (("flood_hazards", "flood hazard polygons"), ("health_units", "health facilities")):
        n = table_count(con, table)
        checks.append(Check(f"{label} loaded (map table)", bool(n), "table missing: run the 'maps' step" if n is None else f"{n} rows", hard=False))

    n = _scalar(con, "SELECT COUNT(DISTINCT municipality_pcode) FROM pcode_lookup l JOIN municipalities m ON m.pcode = l.municipality_pcode")
    checks.append(Check("pcode_lookup covers all municipalities", n == expected_lgus, f"{n} municipalities", hard=False))

    n_desc = _scalar(con, "SELECT COUNT(*) FROM table_descriptions")
    n_src = _scalar(con, "SELECT COUNT(*) FROM data_sources")
    checks.append(Check("metadata seeded", n_desc > 0 and n_src > 0, f"{n_desc} descriptions, {n_src} sources", hard=False))
    return checks


def report(checks: list[Check]) -> bool:
    ok = True
    for c in checks:
        mark = "PASS" if c.passed else ("FAIL" if c.hard else "WARN")
        print(f"[{mark}] {c.name}: {c.detail}")
        ok &= c.passed or not c.hard
    return ok


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sys.exit(0 if report(run_checks(connect())) else 1)
