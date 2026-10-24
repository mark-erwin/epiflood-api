"""DOH Epidemiology Bureau weekly clustering reports -> municipality-week cases.

Replaces: parse_doh_clustering_csv, collect_laguna_clusters, _undo_last, map_names_to_pcodes
(municipality part). No interactive prompts: the morbidity week comes from the file name
(or manifest.csv) and the dates are derived from it.

Two ways in (run_all picks automatically, or use --eb-source):

  raw     data/epidemiology/eb/<disease>/**/*.csv        the original weekly reports
          file names carry the week (2026_MW38.csv); optional eb/manifest.csv
          (file,year,mw  OR  file,start_date,end_date)

  staged  data/epidemiology/laguna_bgy_pcode_<disease>_clusters.csv
          the pcode-mapped files the team already built. Rows must carry
          municipality_pcode, start_date and end_date, and every start/end pair must be
          exactly one Sunday-Saturday morbidity week (typos in the typed dates are caught).
"""

import io
import logging
import re
from datetime import date
from pathlib import Path

import duckdb
import pandas as pd

from pipelines.common import (
    DISEASES, EB_DIR, EB_STAGED, EPI_OUT, OVERRIDES_PATH, PCODE_LOOKUP_PATH, PROVINCE, connect,
    init_schema,
)
from utils.morbidity_week import date_to_mw, mw_range
from utils.name_matching import (
    UnmatchedNamesError, build_barangay_lookup, build_municipality_lookup, load_overrides,
    match_municipalities, resolve_barangay,
)

log = logging.getLogger("pipelines")

# Set these if auto-detection is ambiguous (see ColumnDetectionError messages).
CASES_COL: str | None = None
DEATHS_COL: str | None = None

SOURCE = "doh_eb"
MW_PATTERN = re.compile(r"(?:mw|week|wk)[\s_\-]*0*(\d{1,2})", re.IGNORECASE)
YEAR_PATTERN = re.compile(r"(20\d{2})")


class ColumnDetectionError(ValueError):
    pass


class WeekResolutionError(ValueError):
    pass


# ---- reading ---------------------------------------------------------------
def read_text_robust(path: Path) -> str:
    """UTF-8 first, cp1252 as fallback. Never silently drop characters."""
    raw = path.read_bytes()
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("cp1252")


def parse_eb_csv(raw_text: str) -> pd.DataFrame:
    """Skip report preamble, find the header row (the one containing 'Region')."""
    lines = [ln for ln in raw_text.splitlines() if ln.strip()]
    header_idx = next((i for i, ln in enumerate(lines) if "region" in ln.lower()), None)
    if header_idx is None:
        raise ValueError("No header row containing 'Region' found")
    df = pd.read_csv(io.StringIO("\n".join(lines[header_idx:])), dtype=str)
    df.columns = [" ".join(str(c).split()) for c in df.columns]
    return df


def find_column(columns, include, exclude=(), override: str | None = None, label: str = "") -> str:
    """Pick the single header containing an `include` keyword and no `exclude` keyword."""
    columns = list(columns)
    if override:
        if override not in columns:
            raise ColumnDetectionError(f"{label} column '{override}' not found. Headers: {columns}")
        return override
    hits = [
        c for c in columns
        if any(k in c.upper() for k in include) and not any(k in c.upper() for k in exclude)
    ]
    if len(hits) != 1:
        raise ColumnDetectionError(
            f"Could not pick the {label} column automatically (candidates: {hits}). "
            f"Set CASES_COL / DEATHS_COL at the top of ingest_doh_eb_weekly.py. Headers: {columns}"
        )
    return hits[0]


def to_number(series: pd.Series) -> pd.Series:
    """'1,234' -> 1234; '-', blanks and text -> NaN (kept as NULL, never 0)."""
    cleaned = series.astype(str).str.replace(r"[,\s]", "", regex=True)
    return pd.to_numeric(cleaned, errors="coerce")


# ---- which week is this file? ------------------------------------------------------
def load_manifest(eb_dir: Path) -> dict[str, dict]:
    path = eb_dir / "manifest.csv"
    if not path.exists():
        return {}
    df = pd.read_csv(path, dtype=str).fillna("")
    return {r["file"].strip(): r for r in df.to_dict("records")}


def resolve_week(path: Path, manifest: dict[str, dict] | None = None, default_year: int | None = None) -> tuple[int, int]:
    """Return (year, mw) for a report file. Fails loudly instead of guessing."""
    manifest = manifest or {}
    row = manifest.get(path.name)
    if row:
        if row.get("start_date") and row.get("end_date"):
            start, end = date.fromisoformat(row["start_date"]), date.fromisoformat(row["end_date"])
            if start.weekday() != 6 or (end - start).days != 6:
                raise WeekResolutionError(
                    f"{path.name}: {start}..{end} is not exactly one Sunday-Saturday morbidity week. "
                    "Municipality-weekly data needs one week per file."
                )
            return date_to_mw(start)
        if row.get("year") and row.get("mw"):
            year, mw = int(row["year"]), int(row["mw"])
            mw_range(year, mw)   # validates
            return year, mw

    m = MW_PATTERN.search(path.stem)
    if not m:
        raise WeekResolutionError(
            f"Cannot find a morbidity week in '{path.name}'. Rename it (e.g. 2026_MW38.csv) "
            "or add a row to manifest.csv."
        )
    mw = int(m.group(1))
    year_match = YEAR_PATTERN.search(path.stem) or next(
        (YEAR_PATTERN.search(p) for p in map(str, path.parents) if YEAR_PATTERN.search(p)), None
    )
    year = int(year_match.group(1)) if year_match else default_year
    if year is None:
        raise WeekResolutionError(f"Cannot find a year for '{path.name}'. Put it in the file/folder name or pass --year.")
    try:
        mw_range(year, mw)
    except ValueError as exc:
        raise WeekResolutionError(f"{path.name}: {exc}") from exc
    return year, mw


# ---- parsing one file ----------------------------------------------------------------
def parse_eb_file(
    path: Path, disease: str, manifest=None, default_year: int | None = None,
    cases_col: str | None = CASES_COL, deaths_col: str | None = DEATHS_COL,
) -> pd.DataFrame:
    """Barangay-level Laguna rows for one weekly report."""
    year, mw = resolve_week(path, manifest, default_year)
    start, end = mw_range(year, mw)
    df = parse_eb_csv(read_text_robust(path))

    prov = find_column(df.columns, ["PROVINCE"], label="province")
    mun = find_column(df.columns, ["MUNICIPALITY", "CITY"], exclude=["PROVINCE", "HIGHLY"], label="municipality")
    bgy = find_column(df.columns, ["BARANGAY", "BRGY", "BGY"], label="barangay")
    cas = find_column(df.columns, ["CASE"], exclude=["DEATH", "RATE", "CFR"], override=cases_col, label="cases")
    dth = None
    if deaths_col or any("DEATH" in c.upper() for c in df.columns):
        dth = find_column(df.columns, ["DEATH"], exclude=["RATE"], override=deaths_col, label="deaths")

    rows = df[df[prov].fillna("").str.strip().str.upper() == PROVINCE.upper()]
    out = pd.DataFrame({
        "municipality_raw": rows[mun].str.strip(),
        "barangay_raw": rows[bgy].str.strip(),
        "cases": to_number(rows[cas]),
        "deaths": to_number(rows[dth]) if dth else float("nan"),
    })
    out["disease"], out["year"], out["mw"] = disease, year, mw
    out["week_start"], out["week_end"], out["source_file"] = start, end, path.name
    return out.reset_index(drop=True)


def collect_eb(
    eb_dir: Path, disease: str, default_year: int | None = None, cases_col=CASES_COL, deaths_col=DEATHS_COL,
) -> pd.DataFrame:
    folder = eb_dir / disease
    files = sorted(p for p in folder.rglob("*.csv") if p.name.lower() != "manifest.csv")
    if not files:
        return pd.DataFrame()
    manifest = load_manifest(eb_dir)

    seen: dict[tuple[int, int], str] = {}
    frames = []
    for path in files:
        key = resolve_week(path, manifest, default_year)
        if key in seen:
            raise WeekResolutionError(f"{path.name} and {seen[key]} are both {disease} {key[0]} MW{key[1]}")
        seen[key] = path.name
        df = parse_eb_file(path, disease, manifest, default_year, cases_col, deaths_col)
        if df.empty:
            log.warning("%s: no %s rows", path.name, PROVINCE)
            continue
        frames.append(df)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


# ---- barangay detail (staging only) and municipality aggregation ----------------------
def attach_pcodes(
    rows: pd.DataFrame, mun_lookup: dict[str, str], overrides: dict[str, str],
    barangay_lookup: dict | None = None,
) -> pd.DataFrame:
    """Municipality pcode is mandatory (raises if unmatched); barangay pcode is best effort."""
    mapping = match_municipalities(rows["municipality_raw"], mun_lookup, overrides)
    out = rows.copy()
    out["pcode"] = out["municipality_raw"].map(mapping)
    if barangay_lookup:
        out["barangay_pcode"] = [
            resolve_barangay(m, p, b, barangay_lookup)
            for m, p, b in zip(out["municipality_raw"], out["pcode"], out["barangay_raw"])
        ]
        missing = out["barangay_pcode"].isna().sum()
        if missing:
            log.warning("%d barangay row(s) have no barangay pcode (not needed for municipality tables)", missing)
    else:
        out["barangay_pcode"] = None
    return out


def aggregate_to_municipality(rows: pd.DataFrame) -> pd.DataFrame:
    """Sum barangay rows into municipality-weeks. All-missing groups stay NULL."""
    agg = (
        rows.groupby(["pcode", "disease", "year", "mw"], as_index=False)
        .agg(cases=("cases", lambda s: s.sum(min_count=1)), deaths=("deaths", lambda s: s.sum(min_count=1)))
    )
    agg["cases"] = agg["cases"].round().astype("Int64")
    agg["deaths"] = agg["deaths"].round().astype("Int64")
    return agg


def _store(con: duckdb.DuckDBPyConnection, agg: pd.DataFrame, disease: str) -> None:
    """Replace this source's rows for one disease. EB wins over HDX on overlapping weeks."""
    con.execute("DELETE FROM cases_weekly WHERE source = ? AND disease = ?", [SOURCE, disease])
    con.register("eb_stage", agg)
    con.execute(
        f"""INSERT OR REPLACE INTO cases_weekly (pcode, disease, year, mw, cases, deaths, source)
            SELECT pcode, disease, year, mw, cases, deaths, '{SOURCE}' FROM eb_stage"""
    )
    con.unregister("eb_stage")


def _store_crosswalk(con: duckdb.DuckDBPyConnection, rows: pd.DataFrame) -> None:
    xw = rows[["municipality_raw", "pcode"]].drop_duplicates().rename(columns={"municipality_raw": "raw_name"})
    xw["source"] = SOURCE
    con.register("xw_stage", xw)
    con.execute("INSERT OR REPLACE INTO municipality_crosswalk (raw_name, source, pcode) SELECT raw_name, source, pcode FROM xw_stage")
    con.unregister("xw_stage")


def load_eb(
    con: duckdb.DuckDBPyConnection, eb_dir: Path = EB_DIR, default_year: int | None = None,
    overrides_path: Path = OVERRIDES_PATH, lookup_path: Path = PCODE_LOOKUP_PATH,
    out_dir: Path = EPI_OUT, cases_col=CASES_COL, deaths_col=DEATHS_COL,
) -> dict[str, int]:
    """Raw mode: read the original weekly CSVs."""
    mun_lookup = build_municipality_lookup(con.execute("SELECT pcode, name FROM municipalities").fetchall())
    if not mun_lookup:
        raise RuntimeError("`municipalities` is empty. Run ingest_boundaries first.")
    overrides = load_overrides(overrides_path)
    bgy_lookup = build_barangay_lookup(pd.read_csv(lookup_path, encoding="utf-8-sig", dtype=str)) if lookup_path.exists() else None

    out_dir.mkdir(parents=True, exist_ok=True)
    summary: dict[str, int] = {}
    for disease in DISEASES:
        rows = collect_eb(eb_dir, disease, default_year, cases_col, deaths_col)
        if rows.empty:
            log.warning("No %s reports found under %s", disease, eb_dir / disease)
            continue
        rows = attach_pcodes(rows, mun_lookup, overrides, bgy_lookup)
        rows.to_csv(out_dir / f"eb_{disease}_barangay_staging.csv", index=False)   # barangay detail kept
        agg = aggregate_to_municipality(rows)
        _store(con, agg, disease)
        _store_crosswalk(con, rows)
        summary[disease] = len(agg)
        log.info("EB %s: %d municipality-weeks from %d files", disease, len(agg), rows["source_file"].nunique())
    return summary


def load_staged_clusters(
    con: duckdb.DuckDBPyConnection, csv_path: Path, disease: str,
    cases_col: str | None = CASES_COL, deaths_col: str | None = DEATHS_COL, out_dir: Path = EPI_OUT,
) -> int:
    """Staged mode: a pcode-mapped cluster CSV with start_date / end_date columns."""
    df = pd.read_csv(csv_path, dtype=str, encoding="utf-8-sig")
    df.columns = [" ".join(str(c).split()) for c in df.columns]
    missing = [c for c in ("municipality_pcode", "start_date", "end_date") if c not in df.columns]
    if missing:
        raise ValueError(f"{csv_path.name} is missing columns {missing}. Found: {list(df.columns)}")

    cas = find_column(df.columns, ["CASE"], exclude=["DEATH", "RATE", "CFR"], override=cases_col, label="cases")
    dth = None
    if deaths_col or any("DEATH" in c.upper() for c in df.columns):
        dth = find_column(df.columns, ["DEATH"], exclude=["RATE"], override=deaths_col, label="deaths")

    # every row must be exactly one Sunday-Saturday morbidity week
    start = pd.to_datetime(df["start_date"], errors="coerce")
    end = pd.to_datetime(df["end_date"], errors="coerce")
    one_week = (start.dt.weekday == 6) & ((end - start).dt.days == 6)
    if not one_week.all():
        cols = [c for c in ("source_file", "start_date", "end_date") if c in df.columns]
        sample = df.loc[~one_week, cols].drop_duplicates().head(15).to_string(index=False)
        raise WeekResolutionError(
            f"{int((~one_week).sum())} row(s) in {csv_path.name} are not exactly one Sunday-Saturday "
            f"morbidity week (typo in a typed date, or a multi-week window):\n{sample}"
        )

    ymw = [date_to_mw(d.date()) for d in start]
    rows = pd.DataFrame({
        "pcode": df["municipality_pcode"].str.strip(),
        "barangay_pcode": df["barangay_pcode"] if "barangay_pcode" in df.columns else None,
        "cases": to_number(df[cas]),
        "deaths": to_number(df[dth]) if dth else float("nan"),
        "disease": disease,
        "year": [y for y, _ in ymw], "mw": [w for _, w in ymw],
        "week_start": start.dt.date, "week_end": end.dt.date,
        "source_file": df["source_file"] if "source_file" in df.columns else csv_path.name,
    })

    known = {r[0] for r in con.execute("SELECT pcode FROM municipalities").fetchall()}
    if not known:
        raise RuntimeError("`municipalities` is empty. Run ingest_boundaries first.")
    unknown = sorted(set(rows["pcode"]) - known)
    if unknown:
        raise UnmatchedNamesError(f"{len(unknown)} municipality pcode(s) in {csv_path.name} are not in `municipalities`: {unknown}")

    files_per_week = rows.groupby(["year", "mw"])["source_file"].nunique()
    clash = files_per_week[files_per_week > 1]
    if len(clash):
        raise WeekResolutionError(f"Several files claim the same {disease} week: {clash.index.tolist()[:10]}")

    out_dir.mkdir(parents=True, exist_ok=True)
    rows.to_csv(out_dir / f"eb_{disease}_barangay_staging.csv", index=False)
    agg = aggregate_to_municipality(rows)
    _store(con, agg, disease)
    log.info("EB %s (staged): %d municipality-weeks from %s", disease, len(agg), csv_path.name)
    return len(agg)


def load_eb_auto(con: duckdb.DuckDBPyConnection, source: str = "auto", default_year: int | None = None) -> dict[str, int]:
    """Pick raw or staged input. 'auto' prefers raw reports when any exist."""
    if source not in ("auto", "raw", "staged"):
        raise ValueError("source must be auto, raw or staged")
    raw_files = any(p for d in DISEASES if (EB_DIR / d).exists() for p in (EB_DIR / d).rglob("*.csv"))
    if source == "raw" or (source == "auto" and raw_files):
        summary = load_eb(con, default_year=default_year)
        if summary:
            return summary
    staged = {d: p for d, p in EB_STAGED.items() if p.exists()}
    if source in ("auto", "staged") and staged:
        return {d: load_staged_clusters(con, p, d) for d, p in staged.items()}
    raise FileNotFoundError(
        f"No EB data found. Put weekly reports in {EB_DIR}/<disease>/ or the staged files "
        f"{[p.name for p in EB_STAGED.values()]} in {EB_STAGED['dengue'].parent}."
    )


if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO)
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=None, help="fallback year when file names have none")
    ap.add_argument("--eb-source", choices=["auto", "raw", "staged"], default="auto")
    args = ap.parse_args()
    _con = connect()
    init_schema(_con)
    load_eb_auto(_con, args.eb_source, args.year)
