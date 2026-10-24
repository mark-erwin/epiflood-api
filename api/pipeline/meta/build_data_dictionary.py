"""Generate docs/data_dictionary.md from schema.sql + table_descriptions.py.

    python -m pipelines.build_data_dictionary

The tables section is generated (never edit it by hand); the conventions section is the
written record of the data decisions the paper's methodology needs to cite.
"""

import duckdb
from db.connect import API_ROOT
from db.init_db import init_schema
from api.pipeline.meta.seed_table_descriptions import LOADER_TABLES, seed_table_descriptions

OUT_PATH = API_ROOT.parent / "docs" / "data_dictionary.md"

CONVENTIONS = CONVENTIONS = """\
# EpiFlood API data dictionary

## Conventions and data decisions

**Geography and resolution.** The spatial hierarchy is barangay -> city/municipality (30 in
Laguna: 6 cities, 24 municipalities), identified by `pcode`. The data is stored at **two
resolutions**:

- **Barangay resolution:** the outbreak cluster tables (`bgy_dengue_clusters`,
  `bgy_lepto_clusters`), the barangay rainfall table (`bgy_rainfall`), and the `barangays`
  geometry. Cluster detection works at barangay level, so the maps and spatial analysis
  built on it do too. Each barangay row carries its municipality through `pcode_lookup`
  (`barangay_pcode` -> `municipality_pcode`).
- **Municipality resolution:** weekly case counts, `rainfall_weekly`, and flood-hazard
  percentages (`hazard_by_municipality`). The DOH reports give case counts per municipality.

Barangay results can be rolled up to municipality through `pcode_lookup`. Municipality
values are never disaggregated to barangays.

**Morbidity weeks.** DOH weeks run Sunday to Saturday. Week 1 is the first week with at least
4 days in the new year (the CDC MMWR rule). Early-January days can belong to week 52/53 of the
previous year and late-December days to week 1 of the next. Within 2014-2027, 2014, 2020 and
2025 have 53 weeks. Everything (cases, rainfall) is aligned through the `morbidity_weeks` table.

**Missing data.** A municipality-week absent from the source has **no row**. A value the source
left blank or wrote as `-` is stored as `NULL`. A reported zero is stored as `0`. `NULL` and
`0` are never mixed: totals should be read together with the number of weeks reported.

**Sources and precedence.** Case data comes from two sources. DOH EB weekly reports (`doh_eb`)
cover 2021 onward; the HDX file (`doh_hdx`) covers 2016-2021. Where both cover the same
municipality-week, **EB wins**. If the HDX file has no municipality breakdown it is stored
Laguna-wide in `cases_province_weekly` instead.

**Rainfall.** Weekly rainfall totals per morbidity week, loaded from precomputed CSVs
(2016-2026) rather than fetched at run time. They exist at municipality level
(`rainfall_weekly`) and barangay level (`bgy_rainfall`). A missing week is `NULL`, never 0.
`rainfall_weekly` is a table, and `days_with_data` is 7 for a week with a value and 0
otherwise.

**Flood hazard.** Project NOAH 5-year hazard polygons (levels 1 low, 2 medium, 3 high),
summarised per municipality as area-weighted percentages. The raw polygons are kept in
`flood_hazards` for map tiles. Hazard describes terrain, so it does not change from week to week.

**Scope.** The project does not forecast. It consolidates the data and provides mapping,
querying, export, and spatiotemporal analysis.

"""

def build_markdown() -> str:
    con = duckdb.connect()
    init_schema(con)
    seed_table_descriptions(con)
    pks = {
        t: cols
        for t, cols in con.execute(
            "SELECT table_name, constraint_column_names FROM duckdb_constraints() WHERE constraint_type = 'PRIMARY KEY'"
        ).fetchall()
    }
    desc = {(t, c): d for t, c, d in con.execute("SELECT table_name, column_name, description FROM table_descriptions").fetchall()}
    objects = con.execute(
        "SELECT table_name, table_type FROM information_schema.tables WHERE table_schema = 'main' ORDER BY table_type, table_name"
    ).fetchall()

    parts = [CONVENTIONS, "## Tables and views\n"]
    for name, kind in objects:
        parts.append(f"### `{name}`" + (" (view)" if kind == "VIEW" else "") + "\n")
        parts.append((desc.get((name, "*")) or "") + "\n")
        if name in pks:
            parts.append(f"Primary key: `{', '.join(pks[name])}`\n")
        parts.append("| Column | Type | Nullable | Description |\n|---|---|---|---|")
        for col, typ, nullable in con.execute(
            "SELECT column_name, data_type, is_nullable FROM information_schema.columns "
            "WHERE table_schema = 'main' AND table_name = ? ORDER BY ordinal_position", [name]
        ).fetchall():
            text = (desc.get((name, col)) or "").replace("|", "\\|")
            parts.append(f"| `{col}` | {typ} | {nullable} | {text} |")
        parts.append("")
    parts.append("## Map tables created by `db/init_db.py`\n")
    parts.append("These are loaded straight from map files with DuckDB's `spatial` extension, so their "
                 "column set follows the files. Only the known columns are listed.\n")
    for name, (text, columns) in LOADER_TABLES.items():
        parts.append(f"### `{name}`\n")
        parts.append(text + "\n")
        parts.append("| Column | Description |\n|---|---|")
        parts.extend(f"| `{col}` | {d} |" for col, d in columns.items())
        parts.append("")
    return "\n".join(parts)

def main() -> None:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(build_markdown(), encoding="utf-8")
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
