"""HDX 'DOH-Epi Dengue 2016-2021' -> weekly dengue cases for Laguna.

Replaces: clean_doh_epi_dengue.

The old version dropped `loc` after filtering, which loses the municipality if the
file has one. This loader checks what `loc` holds:
  * municipality names  -> municipality-weekly rows in `cases_weekly`
  * just "Laguna"       -> province-weekly rows in `cases_province_weekly`
                           (municipality-level dengue for 2016-2021 is then NOT available)
"""

import logging
from pathlib import Path

import duckdb
import pandas as pd

from ingest_pipeline.common import (
    EPI_OUT, HDX_DENGUE_PATH, OVERRIDES_PATH, PROVINCE, connect, init_schema,
)
from utils.morbidity_week import date_to_mw
from utils.name_matching import (
    build_municipality_lookup, clean_text, load_overrides, match_municipalities,
)

log = logging.getLogger("pipelines")

SOURCE = "doh_hdx"
DISEASE = "dengue"


def read_hdx_laguna(
    csv_path: Path, loc_col="loc", date_col="date", cases_col="cases", deaths_col="deaths",
    muni_col: str | None = None,
) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    has_loc = loc_col in df.columns

    required = [date_col, cases_col, muni_col] + ([loc_col] if has_loc else [])
    missing = [c for c in required if c and c not in df.columns]
    if missing:
        raise ValueError(f"{csv_path.name} is missing columns {missing}. Found: {list(df.columns)}")

    if has_loc:
        df = df[df[loc_col].astype(str).str.contains(PROVINCE, case=False, na=False)].copy()
        if df.empty:
            raise ValueError(f"No rows with '{loc_col}' containing '{PROVINCE}'")
    else:
        log.warning(
            "%s has no '%s' column: treating it as a pre-filtered %s province series",
            csv_path.name, loc_col, PROVINCE,
        )
        df = df.copy()
        df[loc_col] = PROVINCE

    df = df[df[loc_col].astype(str).str.contains(PROVINCE, case=False, na=False)].copy()
    if df.empty:
        raise ValueError(f"No rows with '{loc_col}' containing '{PROVINCE}'")

    df["date"] = pd.to_datetime(df[date_col], errors="coerce")
    bad_dates = int(df["date"].isna().sum())
    if bad_dates:
        log.warning("%d row(s) with unreadable dates dropped", bad_dates)
        df = df[df["date"].notna()]
    log.info("HDX weekday of 'date' column: %s", df["date"].dt.day_name().value_counts().to_dict())

    ymw = [date_to_mw(d.date()) for d in df["date"]]
    df["year"], df["mw"] = [y for y, _ in ymw], [w for _, w in ymw]
    df["loc_raw"] = df[muni_col or loc_col].astype(str).str.strip()
    df["cases"] = pd.to_numeric(df[cases_col], errors="coerce")
    df["deaths"] = pd.to_numeric(df[deaths_col], errors="coerce") if deaths_col in df.columns else float("nan")
    return df[["loc_raw", "date", "year", "mw", "cases", "deaths"]].reset_index(drop=True)


def detect_level(df: pd.DataFrame, muni_col: str | None = None) -> str:
    if muni_col:
        return "municipality"
    keys = {clean_text(v) for v in df["loc_raw"].unique()}
    if keys == {clean_text(PROVINCE)}:
        return "province"
    raise ValueError(
        f"'loc' holds more than just '{PROVINCE}': {sorted(df['loc_raw'].unique())[:10]}. "
        "If another column has the municipality name, pass muni_col='<that column>'."
    )


def _sum_min1(s: pd.Series):
    return s.sum(min_count=1)


def load_hdx_dengue(
    con: duckdb.DuckDBPyConnection, csv_path: Path = HDX_DENGUE_PATH,
    overrides_path: Path = OVERRIDES_PATH, out_dir: Path = EPI_OUT,
    muni_col: str | None = None, **cols,
) -> dict:
    df = read_hdx_laguna(csv_path, muni_col=muni_col, **cols)
    level = detect_level(df, muni_col)
    out_dir.mkdir(parents=True, exist_ok=True)

    if level == "province":
        agg = df.groupby(["year", "mw"], as_index=False).agg(cases=("cases", _sum_min1), deaths=("deaths", _sum_min1))
        dup = int(df.duplicated(["year", "mw"]).sum())
        if dup:
            log.warning("%d duplicate province-week rows were summed", dup)
        agg["cases"], agg["deaths"] = agg["cases"].round().astype("Int64"), agg["deaths"].round().astype("Int64")
        agg.assign(province=PROVINCE, disease=DISEASE).to_csv(out_dir / "doh_hdx_laguna_dengue_province.csv", index=False)

        con.execute("DELETE FROM cases_province_weekly WHERE source = ? AND disease = ?", [SOURCE, DISEASE])
        con.register("hdx_stage", agg)
        con.execute(
            f"""INSERT OR REPLACE INTO cases_province_weekly (province, disease, year, mw, cases, deaths, source)
                SELECT '{PROVINCE}', '{DISEASE}', year, mw, cases, deaths, '{SOURCE}' FROM hdx_stage"""
        )
        con.unregister("hdx_stage")
        log.warning(
            "HDX dengue is PROVINCE-level: stored in cases_province_weekly. "
            "Municipality-level dengue 2016-2021 is NOT available from this file."
        )
        return {"level": "province", "rows": len(agg)}

    lookup = build_municipality_lookup(con.execute("SELECT pcode, name FROM municipalities").fetchall())
    mapping = match_municipalities(df["loc_raw"], lookup, load_overrides(overrides_path))
    df["pcode"] = df["loc_raw"].map(mapping)
    dup = int(df.duplicated(["pcode", "year", "mw"]).sum())
    if dup:
        log.warning("%d duplicate municipality-week rows were summed", dup)
    agg = df.groupby(["pcode", "year", "mw"], as_index=False).agg(cases=("cases", _sum_min1), deaths=("deaths", _sum_min1))
    agg["cases"], agg["deaths"] = agg["cases"].round().astype("Int64"), agg["deaths"].round().astype("Int64")
    agg["disease"] = DISEASE
    agg.to_csv(out_dir / "doh_hdx_laguna_dengue_2016_2021.csv", index=False)

    con.register("hdx_stage", agg)
    overlap = con.execute(
        """SELECT COUNT(*), AVG(ABS(c.cases - s.cases)) FROM cases_weekly c
           JOIN hdx_stage s ON c.pcode = s.pcode AND c.disease = s.disease AND c.year = s.year AND c.mw = s.mw
           WHERE c.source = 'doh_eb'"""
    ).fetchone()
    if overlap[0]:
        log.info("HDX/EB overlap: %d municipality-weeks, mean |difference| = %s cases (EB is kept)", overlap[0], overlap[1])

    con.execute("DELETE FROM cases_weekly WHERE source = ? AND disease = ?", [SOURCE, DISEASE])
    con.execute(
        f"""INSERT OR IGNORE INTO cases_weekly (pcode, disease, year, mw, cases, deaths, source)
            SELECT pcode, disease, year, mw, cases, deaths, '{SOURCE}' FROM hdx_stage"""
    )
    con.unregister("hdx_stage")

    xw = df[["loc_raw", "pcode"]].drop_duplicates().rename(columns={"loc_raw": "raw_name"})
    xw["source"] = SOURCE
    con.register("xw_stage", xw)
    con.execute("INSERT OR REPLACE INTO municipality_crosswalk (raw_name, source, pcode) SELECT raw_name, source, pcode FROM xw_stage")
    con.unregister("xw_stage")
    return {"level": "municipality", "rows": len(agg)}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    _con = connect()
    init_schema(_con)
    load_hdx_dengue(_con)
