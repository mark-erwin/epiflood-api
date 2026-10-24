"""Optional QA maps for the hazard calculation (not part of run_all).

Replaces: _make_maps.   pip install matplotlib folium mapclassify
"""

import logging
from pathlib import Path

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from pipelines.build_hazard_by_municipality import VAR_COL, _to_projected  # noqa: E402

log = logging.getLogger("pipelines")


def make_maps(admin_gdf: gpd.GeoDataFrame, hazard_gdf: gpd.GeoDataFrame, result: pd.DataFrame,
              out_dir: Path, id_col: str = "adm3_pcode") -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    admin = _to_projected(admin_gdf, "admin layer").dissolve(by=id_col, as_index=False)
    hazard = _to_projected(hazard_gdf, "hazard layer")

    wide = result.pivot(index="pcode", columns="hazard_level", values="pct_of_area")
    wide.columns = [f"pct_level_{int(c)}" for c in wide.columns]
    admin = admin.merge(wide, left_on=id_col, right_index=True, how="left")
    cols = list(wide.columns)

    fig, axes = plt.subplots(1, len(cols), figsize=(8 * len(cols), 8), squeeze=False)
    for ax, col in zip(axes[0], cols):
        admin.plot(column=col, cmap="YlOrRd", vmin=0, vmax=100, linewidth=0.2, edgecolor="grey",
                   legend=True, ax=ax, missing_kwds={"color": "lightgrey"})
        ax.set_title(f"{col}: % of municipality area")
        ax.axis("off")
    fig.tight_layout()
    fig.savefig(out_dir / "flood_hazard_choropleth.png", dpi=200)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, 10))
    admin.boundary.plot(ax=ax, color="black", linewidth=0.3)
    for level, color in ((1, "gold"), (2, "orange"), (3, "red")):
        sub = hazard[hazard[VAR_COL] == level]
        if not sub.empty:
            sub.plot(ax=ax, color=color, alpha=0.6)
    ax.set_title("NOAH 5-year flood hazard over municipal boundaries")
    ax.axis("off")
    fig.savefig(out_dir / "flood_hazard_overlay.png", dpi=200)
    plt.close(fig)

    try:
        m = admin.to_crs("EPSG:4326").explore(
            column=cols[-1], cmap="YlOrRd", scheme="quantiles", k=5,
            tooltip=[id_col] + cols, tiles="CartoDB positron",
            style_kwds={"weight": 0.3, "color": "grey"},
        )
        m.save(out_dir / "flood_hazard_map.html")
    except ImportError:
        log.warning("Skipped interactive map: pip install folium mapclassify")
    log.info("Maps saved to %s", out_dir)
