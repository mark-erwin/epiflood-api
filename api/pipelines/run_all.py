"""Rebuild the database from the files in data/.

    python -m pipelines.run_all                       everything
    python -m pipelines.run_all --skip rainfall       skip the network step
    python -m pipelines.run_all --skip maps           skip the spatial map tables (needs DuckDB spatial)
    python -m pipelines.run_all --only eb hdx --year 2026
    python -m pipelines.run_all --eb-source staged    force the staged cluster CSVs

Order matters: EB before HDX, so the result is always
    EB weeks  UNION  HDX weeks not covered by EB.
Stop the API before running (DuckDB allows a single writer).
Exit code: 0 = all hard checks passed, 1 = a check failed, 2 = could not run.
"""

import argparse
import logging
import sys

from db.connect import DB_PATH, DatabaseLockedError
from db import init_db
from pipelines import (
    build_hazard_by_municipality, ingest_boundaries, ingest_doh_dengue_hdx, ingest_doh_eb_weekly,
    ingest_rainfall_openmeteo, seed_calendar, seed_metadata, validate,
)
from pipelines.common import connect, init_schema

STEPS = ["calendar", "boundaries", "eb", "hdx", "rainfall", "hazard", "maps"]
log = logging.getLogger("pipelines")


def run_step(con, step: str, eb_source: str, year: int | None) -> None:
    if step == "calendar":
        seed_calendar.seed_calendar(con)
    elif step == "boundaries":
        ingest_boundaries.run(con)
    elif step == "eb":
        ingest_doh_eb_weekly.load_eb_auto(con, eb_source, year)
    elif step == "hdx":
        ingest_doh_dengue_hdx.load_hdx_dengue(con)
    elif step == "rainfall":
        ingest_rainfall_openmeteo.load_rainfall(con)
    elif step == "hazard":
        build_hazard_by_municipality.run(con)
    elif step == "maps":                      # health_units, flood_hazards (+ tiles index), pcode_lookup
        init_db.load_map_tables(con)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--skip", nargs="*", default=[], choices=STEPS)
    ap.add_argument("--only", nargs="*", default=None, choices=STEPS)
    ap.add_argument("--year", type=int, default=None, help="fallback year for EB file names")
    ap.add_argument("--eb-source", choices=["auto", "raw", "staged"], default="auto")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    wanted = [s for s in (args.only or STEPS) if s not in args.skip]
    try:
        con = connect()
    except DatabaseLockedError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    log.info("Database: %s", DB_PATH)
    init_schema(con)

    done: set[str] = set()
    for step in wanted:
        log.info("=== %s ===", step)
        try:
            run_step(con, step, args.eb_source, args.year)
        except Exception as exc:                      # name the step, keep the traceback
            log.error("Step '%s' failed: %s", step, exc)
            raise
        done.add(step)

    seed_metadata.seed_metadata(con, set().union(*(seed_metadata.STEP_SOURCE.get(s, set()) for s in done)))
    print("\n=== validation ===")
    return 0 if validate.report(validate.run_checks(con)) else 1


if __name__ == "__main__":
    sys.exit(main())
