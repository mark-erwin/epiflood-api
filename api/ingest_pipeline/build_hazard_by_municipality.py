"""Flood-hazard coverage per municipality -> `hazard_by_municipality`.

Replaces: clean_flood_shapefile, _prep, _hazard_area_by_unit,
calculate_flood_hazard_percentages (maps moved to dev_hazard_maps.py).
"""

import logging
from pathlib import Path

import duckdb
import geopandas as gpd
import pandas as pd

from ingest_pipeline.common import GIS_OUT, HAZARD_GPKG_PATH, HAZARD_PATH, TARGET_CRS, connect, init_schema

log = logging.getLogger("pipelines")

HAZARD_LEVELS = (1, 2, 3)      # NOAH: 1 = low, 2 = medium, 3 = high
HAZARD_LABELS = {1: "Low", 2: "Medium", 3: "High"}
VAR_COL = "Var"


def read_hazard(path: Path) -> gpd.GeoDataFrame:
    """Read the NOAH hazard layer (shapefile or GeoJSON)."""
    if str(path).lower().endswith((".geojson", ".json")):
        try:
            import pyogrio
            pyogrio.set_gdal_config_options({"OGR_GEOJSON_MAX_OBJ_SIZE": 0})  # allow huge features
        except (ImportError, AttributeError):
            pass
    return gpd.read_file(path)


def prepare_hazard_layer(hazard: gpd.GeoDataFrame, out_geojson: Path | None = None) -> gpd.GeoDataFrame:
    """EPSG:4326, valid polygons only, hazard labels added. Optionally write GeoJSON."""
    if hazard.crs is None:
        raise ValueError("Hazard layer has no CRS (missing .prj?). Set it before running.")
    if VAR_COL not in hazard.columns:
        raise ValueError(f"Hazard layer has no '{VAR_COL}' column. Found: {list(hazard.columns)}")
    gdf = hazard.to_crs("EPSG:4326") if hazard.crs != "EPSG:4326" else hazard.copy()
    gdf = _polygons_only(gdf)
    gdf["hazard_label"] = gdf[VAR_COL].map(lambda v: HAZARD_LABELS.get(int(v)) if pd.notna(v) else None)
    if out_geojson is not None:
        out_geojson.parent.mkdir(parents=True, exist_ok=True)
        gdf.to_file(out_geojson, driver="GeoJSON")
    return gdf


def _polygons_only(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Drop empty geometries, repair invalid ones, keep only polygonal parts."""
    gdf = gdf[~gdf.geometry.isna() & ~gdf.geometry.is_empty].copy()
    gdf["geometry"] = gdf.geometry.make_valid()
    gdf = gdf.explode(index_parts=False)               # split GeometryCollections
    gdf = gdf[gdf.geom_type.isin(["Polygon", "MultiPolygon"])]
    return gdf[~gdf.geometry.is_empty].copy()


def _to_projected(gdf: gpd.GeoDataFrame, name: str) -> gpd.GeoDataFrame:
    if gdf.crs is None:
        raise ValueError(f"{name} has no CRS defined; set it before running.")
    if gdf.crs != TARGET_CRS:
        gdf = gdf.to_crs(TARGET_CRS)
    return _polygons_only(gdf)


def _hazard_area_by_unit(admin: gpd.GeoDataFrame, hazard: gpd.GeoDataFrame, level: int, id_col: str) -> pd.Series:
    """Area (m^2) of one hazard level inside each admin unit. Polygons of the level
    are dissolved first so overlaps are never double counted."""
    haz = hazard[hazard[VAR_COL] == level]
    if haz.empty:
        return pd.Series(dtype=float)
    haz = haz.dissolve()[["geometry"]]
    inter = gpd.overlay(admin[[id_col, "geometry"]], haz, how="intersection", keep_geom_type=True)
    inter["area"] = inter.geometry.area
    return inter.groupby(id_col)["area"].sum()


def compute_hazard_areas(
    admin_gdf: gpd.GeoDataFrame,
    hazard_gdf: gpd.GeoDataFrame,
    id_col: str = "adm3_pcode",
    levels: tuple[int, ...] = HAZARD_LEVELS,
) -> pd.DataFrame:
    """Long table: pcode, hazard_level, area_km2, pct_of_area.

    Percentages are area-weighted (hazard area / unit area). Levels that do not
    occur anywhere in the hazard layer are skipped with a warning, not stored as 0.
    """
    admin = _to_projected(admin_gdf, "admin layer")
    hazard = _to_projected(hazard_gdf, "hazard layer")

    present = {int(v) for v in hazard[VAR_COL].dropna().unique()}
    log.info("Hazard '%s' values found: %s", VAR_COL, sorted(present))

    admin = admin.dissolve(by=id_col, as_index=False)[[id_col, "geometry"]]
    admin["total_area"] = admin.geometry.area

    parts = []
    for level in levels:
        if level not in present:
            log.warning("Hazard level %d not present in the hazard layer; skipped", level)
            continue
        log.info("Calculating hazard level %d overlap...", level)
        area = admin[id_col].map(_hazard_area_by_unit(admin, hazard, level, id_col)).fillna(0.0)
        pct = area / admin["total_area"] * 100
        over = int((pct > 100.01).sum())
        if over:
            log.warning("%d units exceed 100%% at level %d (overlapping geometries?)", over, level)
        parts.append(pd.DataFrame({
            "pcode": admin[id_col], "hazard_level": level,
            "area_km2": area / 1e6, "pct_of_area": pct.clip(upper=100.0),
        }))
    if not parts:
        raise ValueError(f"None of the hazard levels {levels} exist in the hazard layer")
    return pd.concat(parts, ignore_index=True)


def load_hazard(con: duckdb.DuckDBPyConnection, df: pd.DataFrame) -> int:
    con.execute("DELETE FROM hazard_by_municipality")
    con.register("haz_stage", df)
    con.execute(
        "INSERT INTO hazard_by_municipality (pcode, hazard_level, area_km2, pct_of_area) "
        "SELECT pcode, hazard_level, area_km2, pct_of_area FROM haz_stage"
    )
    con.unregister("haz_stage")
    return len(df)


def pick_hazard_path(gpkg: Path = HAZARD_GPKG_PATH, shp: Path = HAZARD_PATH) -> Path:
    """Use the GeoPackage the map tables are built from, so percentages and tiles share one source."""
    for path in (gpkg, shp):
        if path.exists():
            return path
    raise FileNotFoundError(
        f"Hazard layer not found: put {gpkg.name} in {gpkg.parent}, or {shp.name} (with its "
        f".dbf/.shx/.prj) in {shp.parent}"
    )


def run(con: duckdb.DuckDBPyConnection, hazard_path: Path | None = None, admin: gpd.GeoDataFrame | None = None) -> pd.DataFrame:
    from ingest_pipeline.ingest_boundaries import load_adm3

    log.info("Loading spatial files...")
    hazard_path = hazard_path or pick_hazard_path()
    log.info("Hazard layer: %s", hazard_path.name)
    admin = load_adm3() if admin is None else admin
    hazard = prepare_hazard_layer(read_hazard(hazard_path), GIS_OUT / "Laguna_Flood_5year_cleaned.geojson")
    result = compute_hazard_areas(admin, hazard, "adm3_pcode")

    known = {r[0] for r in con.execute("SELECT pcode FROM municipalities").fetchall()}
    unknown = sorted(set(result["pcode"]) - known)
    if unknown:
        raise ValueError(f"Hazard result has pcodes not in `municipalities`: {unknown}")

    GIS_OUT.mkdir(parents=True, exist_ok=True)
    result.to_csv(GIS_OUT / "municipality_flood_hazard.csv", index=False)
    load_hazard(con, result)
    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    _con = connect()
    init_schema(_con)
    run(_con)
