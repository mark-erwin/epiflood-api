"""Flood-hazard coverage per municipality AND per barangay.
 
Writes `hazard_by_municipality` and `hazard_by_barangay` (pct of unit area per NOAH level).
Cluster data is at barangay resolution, so the barangay table is the one analysis should join.
 
Both tables are defined in schema.sql (init_schema creates them); this module only refills them.
"""
 
import logging
from pathlib import Path
 
import duckdb
import geopandas as gpd
import pandas as pd
import shapely
 
from pipeline.common import GIS_OUT, HAZARD_GPKG_PATH, HAZARD_PATH, TARGET_CRS, connect, init_schema
 
log = logging.getLogger("pipelines")
 
HAZARD_LEVELS = (1, 2, 3)      # NOAH: 1 = low, 2 = medium, 3 = high
HAZARD_LABELS = {1: "Low", 2: "Medium", 3: "High"}
VAR_COL = "Var"
 
 
def read_hazard(path: Path) -> gpd.GeoDataFrame:
    if str(path).lower().endswith((".geojson", ".json")):
        try:
            import pyogrio
            pyogrio.set_gdal_config_options({"OGR_GEOJSON_MAX_OBJ_SIZE": 0})
        except (ImportError, AttributeError):
            pass
    return gpd.read_file(path)
 
 
def _polygons_only(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    gdf = gdf[~gdf.geometry.isna() & ~gdf.geometry.is_empty].copy()
    gdf["geometry"] = gdf.geometry.make_valid()
    gdf = gdf.explode(index_parts=False)
    gdf = gdf[gdf.geom_type.isin(["Polygon", "MultiPolygon"])]
    return gdf[~gdf.geometry.is_empty].copy()
 
 
def prepare_hazard_layer(hazard: gpd.GeoDataFrame, out_geojson: Path | None = None) -> gpd.GeoDataFrame:
    """EPSG:4326, valid polygons only, labels added. Writes GeoJSON only if out_geojson is given."""
    if hazard.crs is None:
        raise ValueError("Hazard layer has no CRS (missing .prj?).")
    if VAR_COL not in hazard.columns:
        raise ValueError(f"Hazard layer has no '{VAR_COL}' column. Found: {list(hazard.columns)}")
    gdf = hazard.to_crs("EPSG:4326") if hazard.crs != "EPSG:4326" else hazard.copy()
    gdf = _polygons_only(gdf)
    gdf["hazard_label"] = gdf[VAR_COL].map(lambda v: HAZARD_LABELS.get(int(v)) if pd.notna(v) else None)
    if out_geojson is not None:
        out_geojson.parent.mkdir(parents=True, exist_ok=True)
        gdf.to_file(out_geojson, driver="GeoJSON")
    return gdf
 
 
def _to_projected(gdf: gpd.GeoDataFrame, name: str) -> gpd.GeoDataFrame:
    if gdf.crs is None:
        raise ValueError(f"{name} has no CRS defined.")
    if gdf.crs != TARGET_CRS:
        gdf = gdf.to_crs(TARGET_CRS)
    return _polygons_only(gdf)
 
 
def dissolve_levels(hazard_projected: gpd.GeoDataFrame, levels=HAZARD_LEVELS) -> dict[int, gpd.GeoDataFrame]:
    """One dissolved geometry per hazard level (done once, reused for every admin layer).
    Dissolving first means overlaps are never double counted."""
    present = {int(v) for v in hazard_projected[VAR_COL].dropna().unique()}
    log.info("Hazard '%s' values found: %s", VAR_COL, sorted(present))
    out = {}
    for level in levels:
        if level not in present:
            log.warning("Hazard level %d not present in the hazard layer; skipped", level)
            continue
        geom = shapely.union_all(hazard_projected.loc[hazard_projected[VAR_COL] == level, "geometry"].values)
        out[level] = gpd.GeoDataFrame(geometry=[geom], crs=hazard_projected.crs)
    if not out:
        raise ValueError(f"None of the hazard levels {levels} exist in the hazard layer")
    return out
 
 
def compute_hazard_areas(admin_gdf: gpd.GeoDataFrame, dissolved: dict[int, gpd.GeoDataFrame], id_col: str) -> pd.DataFrame:
    """Long table: unit_id, hazard_level, area_km2, pct_of_area (area-weighted)."""
    admin = _to_projected(admin_gdf, "admin layer").dissolve(by=id_col, as_index=False)[[id_col, "geometry"]]
    admin["total_area"] = admin.geometry.area
    parts = []
    for level, haz in dissolved.items():
        log.info("%s: hazard level %d overlap...", id_col, level)
        inter = gpd.overlay(admin[[id_col, "geometry"]], haz, how="intersection", keep_geom_type=True)
        inter["area"] = inter.geometry.area
        area = admin[id_col].map(inter.groupby(id_col)["area"].sum()).fillna(0.0)   # 0 = genuinely no overlap
        pct = area / admin["total_area"] * 100
        over = int((pct > 100.01).sum())
        if over:
            log.warning("%d units exceed 100%% at level %d", over, level)
        parts.append(pd.DataFrame({"unit_id": admin[id_col], "hazard_level": level,
                                   "area_km2": area / 1e6, "pct_of_area": pct.clip(upper=100.0)}))
    return pd.concat(parts, ignore_index=True)
 
 
def _replace_table(con: duckdb.DuckDBPyConnection, table: str, id_name: str, df: pd.DataFrame) -> int:
    """Refill a hazard table defined in schema.sql (no second copy of the DDL here)."""
    stage = df.rename(columns={"unit_id": id_name})[[id_name, "hazard_level", "area_km2", "pct_of_area"]]
    con.execute(f"DELETE FROM {table}")
    con.register("haz_stage", stage)
    con.execute(
        f"INSERT INTO {table} ({id_name}, hazard_level, area_km2, pct_of_area) "
        f"SELECT {id_name}, hazard_level, area_km2, pct_of_area FROM haz_stage"
    )
    con.unregister("haz_stage")
    return len(stage)
 
 
def pick_hazard_path(gpkg: Path = HAZARD_GPKG_PATH, shp: Path = HAZARD_PATH) -> Path:
    for path in (gpkg, shp):
        if path.exists():
            return path
    raise FileNotFoundError(f"Hazard layer not found: put {gpkg.name} in {gpkg.parent}, or {shp.name} in {shp.parent}")
 
 
def run(con: duckdb.DuckDBPyConnection, hazard_path: Path | None = None, write_cleaned: bool = False) -> dict[str, int]:
    """Set write_cleaned=True only if you still serve the static layer (build_hazard_layer.py needs it)."""
    from pipeline.gis.ingest_boundaries import load_adm3, load_adm4
 
    hazard_path = hazard_path or pick_hazard_path()
    log.info("Hazard layer: %s", hazard_path.name)
    cleaned = GIS_OUT / "Laguna_Flood_5year_cleaned.geojson" if write_cleaned else None
    hazard = prepare_hazard_layer(read_hazard(hazard_path), cleaned)
    dissolved = dissolve_levels(_to_projected(hazard, "hazard layer"))
    GIS_OUT.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}
 
    muni = compute_hazard_areas(load_adm3(), dissolved, "adm3_pcode")
    known = {r[0] for r in con.execute("SELECT pcode FROM municipalities").fetchall()}
    unknown = sorted(set(muni["unit_id"]) - known)
    if unknown:
        raise ValueError(f"Hazard result has pcodes not in `municipalities`: {unknown}")
    muni.rename(columns={"unit_id": "pcode"}).to_csv(GIS_OUT / "municipality_flood_hazard.csv", index=False)
    counts["hazard_by_municipality"] = _replace_table(con, "hazard_by_municipality", "pcode", muni)
 
    adm4 = load_adm4()
    if adm4 is None:
        log.warning("No admin4 file: hazard_by_barangay not built")
    else:
        bgy = compute_hazard_areas(adm4, dissolved, "adm4_pcode")
        bgy.rename(columns={"unit_id": "barangay_pcode"}).to_csv(GIS_OUT / "barangay_flood_hazard.csv", index=False)
        counts["hazard_by_barangay"] = _replace_table(con, "hazard_by_barangay", "barangay_pcode", bgy)
 
    for t, n in counts.items():
        log.info("%s: %d rows", t, n)
    return counts
 
 
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    _con = connect()
    init_schema(_con)
    run(_con)
