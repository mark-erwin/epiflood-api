import io
import time
from pathlib import Path
import re, unicodedata
import pandas as pd
import geopandas as gpd
import pandas as pd
import requests
from shapely.validation import make_valid
import asyncio
import aiohttp
import pyogrio
import matplotlib.pyplot as plt

import os
os.environ["OGR_GEOJSON_MAX_OBJ_SIZE"] = "0"
PROVINCE_COL = "Province/ Highly Independent City"

# ----------------------------------------
# Laguna Administrative Boundaries GeoData
# ----------------------------------------
def load_laguna_admin_geodata(admin_path,  setting="adm4", out_path=None):
    # Load the PH admin4 GeoJSON
    gdf = gpd.read_file(admin_path)
    if gdf.crs != "EPSG:4326":
        gdf = gdf.to_crs("EPSG:4326") # Reproject to EPSG:4326

    if setting == "adm4":
        cols = ["adm4_name", "adm4_pcode", "adm3_name", "adm3_pcode", "area_sqkm", "center_lat", "center_lon", "geometry"] # Keep Laguna only.
        term = "barangay"
    elif setting == "adm3":
        cols = ["adm3_name", "adm3_pcode", "area_sqkm", "center_lat", "center_lon", "geometry"]
        term = "municipality"

    if cols:
        print("Loading GeoJSON...")
        print(gdf.columns)
        
        laguna_gdf = gdf[gdf["adm2_name"] == "Laguna"].copy()
        laguna_gdf = laguna_gdf[cols].copy()

        print(f"Found {len(laguna_gdf)} {term} in Laguna.")
        out_path = f"laguna_{term}_geodata.geojson"
        if out_path:
            laguna_gdf.to_file(out_path, driver="GeoJSON")
        return laguna_gdf

#load_laguna_admin_geodata("phl_admin4.geojson", setting="adm4")
#load_laguna_admin_geodata("phl_admin3.geojson", setting="adm3")

# ----------------------------------------
# Rainfall Per Barangay (Date Range)
# ----------------------------------------
def fetch_rainfall_per_barangay(csv_list, geojson, out_path="rainfall/rainfall_per_bgy_mw.csv"):
    url = "https://archive-api.open-meteo.com/v1/archive"
    
    df1 = pd.read_csv(csv_list[0])
    df2 = pd.read_csv(csv_list[1])
    combined_df = pd.concat([df1, df2], ignore_index=True)
    
    gdf = gpd.read_file(geojson)
    
    pcode_to_lat = dict(zip(gdf['adm4_pcode'], gdf['center_lat']))
    pcode_to_lon = dict(zip(gdf['adm4_pcode'], gdf['center_lon']))
    
    combined_df['latitude'] = combined_df['barangay_pcode'].map(pcode_to_lat)
    combined_df['longitude'] = combined_df['barangay_pcode'].map(pcode_to_lon)
    combined_df = combined_df.dropna(subset=['latitude', 'longitude'])

    unique_requests = combined_df[['barangay_pcode', 'latitude', 'longitude', 'start_date', 'end_date']].drop_duplicates().reset_index(drop=True)
    print(f"Total rows: {len(combined_df)} | Unique API requests needed: {len(unique_requests)}")
    
    results_cache = {}
    
    for idx, row in unique_requests.iterrows():
        pcode = row["barangay_pcode"]
        lat, lon = row["latitude"], row["longitude"]
        start, end = row["start_date"], row["end_date"]
        
        print(f"[{idx+1}/{len(unique_requests)}] Fetching: P-code {pcode} ({start} to {end})")
        
        params = {
            "latitude": lat,
            "longitude": lon,
            "start_date": start,
            "end_date": end,
            "hourly": "precipitation",
            "timezone": "auto",
        }
        
        try:
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()

            total_precip = sum(data["hourly"].get("precipitation", [0]))
            
            # Cache the result using a unique key tuple
            results_cache[(pcode, start, end)] = total_precip

            # Polite delay so Open-Meteo doesn't throttle you
            time.sleep(0.3)

        except Exception as e:
            print(f"Error fetching data for P-code {pcode}: {e}")
            results_cache[(pcode, start, end)] = 0
            time.sleep(1.5)

    combined_df['precipitation_mm'] = combined_df.apply(
            lambda r: results_cache.get((r['barangay_pcode'], r['start_date'], r['end_date']), 0),
            axis=1
        )

    master_df = combined_df[["barangay_pcode", "start_date", "end_date", "precipitation_mm"]]
    master_df.to_csv(out_path, index=False)
        
    print(f"\nSuccessfully processed and saved to {out_path}!")
    return master_df

# ----------------------------------------
# Fetch Weather Data (Single Fetch) (OpenMeteo API Call)
# ----------------------------------------
async def fetch_single(session, sem, url, params, pcode, start, end, retries=3):
    """Fetches weather data with automatic retry handling for HTTP 429 errors."""
    async with sem:
        for attempt in range(retries):
            try:
                async with session.get(url, params=params, timeout=15) as response:
                    if response.status == 200:
                        data = await response.json()
                        total_precip = sum(data.get("hourly", {}).get("precipitation", [0]))
                        return (pcode, start, end), total_precip
                    elif response.status == 429:
                        # Rate limited! Wait longer before retrying
                        wait_time = (attempt + 1) * 2
                        print(f"Rate limited (429) for P-code {pcode}. Retrying in {wait_time}s...")
                        await asyncio.sleep(wait_time)
                    else:
                        print(f"HTTP Error {response.status} for P-code {pcode}")
                        return (pcode, start, end), 0.0
            except Exception as e:
                if attempt == retries - 1:
                    print(f"Request failed for P-code {pcode}: {e}")
                    return (pcode, start, end), 0.0
                await asyncio.sleep(1)
        return (pcode, start, end), 0.0

# ----------------------------------------
# Fetch Weather Data (Multi Fetch) (OpenMeteo API Call)
# ----------------------------------------
async def main_fetch(unique_requests, url):
    # Lower concurrency to 4 to completely eliminate 429 errors on Open-Meteo free tier
    sem = asyncio.Semaphore(4) 
    
    async with aiohttp.ClientSession() as session:
        tasks = []
        for _, row in unique_requests.iterrows():
            params = {
                "latitude": row["latitude"],
                "longitude": row["longitude"],
                "start_date": row["start_date"],
                "end_date": row["end_date"],
                "hourly": "precipitation",
                "timezone": "auto",
            }
            tasks.append(
                fetch_single(
                    session, sem, url, params, 
                    row["barangay_pcode"], row["start_date"], row["end_date"]
                )
            )
        results = await asyncio.gather(*tasks)
        return dict(results)

# ----------------------------------------
# Fetch Weather Data (Faster) (OpenMeteo API Call)
# ----------------------------------------
def fetch_rainfall_per_barangay_fast(csv_list, geojson, out_path="rainfall/rainfall_per_bgy_mw.csv"):
    url = "https://archive-api.open-meteo.com/v1/archive"
    
    df1 = pd.read_csv(csv_list[0])
    df2 = pd.read_csv(csv_list[1])
    combined_df = pd.concat([df1, df2], ignore_index=True)
    
    gdf = gpd.read_file(geojson)
    
    pcode_to_lat = dict(zip(gdf['adm4_pcode'], gdf['center_lat']))
    pcode_to_lon = dict(zip(gdf['adm4_pcode'], gdf['center_lon']))
    
    combined_df['latitude'] = combined_df['barangay_pcode'].map(pcode_to_lat)
    combined_df['longitude'] = combined_df['barangay_pcode'].map(pcode_to_lon)
    combined_df = combined_df.dropna(subset=['latitude', 'longitude'])

    unique_requests = combined_df[['barangay_pcode', 'latitude', 'longitude', 'start_date', 'end_date']].drop_duplicates().reset_index(drop=True)
    print(f"Total rows: {len(combined_df)} | Unique async API requests: {len(unique_requests)}")
    
    results_cache = asyncio.run(main_fetch(unique_requests, url))

    combined_df['precipitation_mm'] = combined_df.apply(
        lambda r: results_cache.get((r['barangay_pcode'], r['start_date'], r['end_date']), 0),
        axis=1
    )

    master_df = combined_df[["barangay_pcode", "start_date", "end_date", "precipitation_mm"]]
    master_df.to_csv(out_path, index=False)
    
    print(f"\nSuccessfully processed and saved to {out_path}!")
    return master_df

#fetch_rainfall_per_barangay_fast(["epidemiology/laguna_bgy_pcode_dengue_clusters.csv","epidemiology/laguna_bgy_pcode_leptospirosis_clusters.csv"],"gis/laguna_barangay_geodata.geojson")

# ----------------------------------------
# Rainfall (hourly converted to weekly (Sunday))
# ----------------------------------------
def fetch_rainfall_weekly(
    laguna_gdf,
    start_date="2016-01-01",
    end_date="2026-10-16",
    out_path="gis/laguna_weekly_rainfall_2021_2025.csv",
):
    url = "https://archive-api.open-meteo.com/v1/archive"
    all_weekly = []

    for _, row in laguna_gdf.iterrows():
        pcode, name = row["adm3_pcode"], row["adm3_name"]
        lat, lon = row["center_lat"], row["center_lon"]
        print(f"Fetching data for: {name} (Lat: {lat}, Lon: {lon})")
        params = {
            "latitude": lat,
            "longitude": lon,
            "start_date": start_date,
            "end_date": end_date,
            "hourly": "precipitation",
            "timezone": "auto",
        }

        try:
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()

            df_muni = pd.DataFrame(
                {
                    "date": data["hourly"]["time"],
                    "precipitation_mm": data["hourly"]["precipitation"],
                }
            )
            df_muni["date"] = pd.to_datetime(df_muni["date"])
            df_muni = df_muni.set_index("date")

            df_weekly = df_muni.resample("W-SUN")["precipitation_mm"].sum().reset_index()
            df_weekly["municipality"] = pcode
            all_weekly.append(df_weekly)
        except Exception as e:
            print(f"Error fetching data for {name}: {e}")
    if not all_weekly:
        print("No data was collected.")
        return None

    master_df = pd.concat(all_weekly, ignore_index=True)
    master_df = master_df[["municipality", "date", "precipitation_mm"]]

    master_df.to_csv(out_path, index=False)
    print(f"\nSuccessfully saved all data to {out_path}!")
    return master_df

# ----------------------------------------
# Rainfall weekly per Municipality converted to Mean across All Municipalities in Laguna
# ----------------------------------------
def avg_precipitation_laguna_per_week(in_csv='rainfall/laguna_weekly_rainfall_2016_2026.csv'):
    df = pd.read_csv(in_csv)    
    df['date'] = pd.to_datetime(df['date'])
    weekly_provincial_average = (
        df.groupby('date')['precipitation_mm']
        .mean()
        .reset_index()
    )
    weekly_provincial_average.to_csv("mean_rainfall_across_muni_weekly.csv", index=False)
    return weekly_provincial_average

# ----------------------------------------
# Filtered DOH-EPI Data to Laguna Only
# ----------------------------------------
def clean_doh_epi_dengue(
    in_csv="doh-epi-dengue-data-2016-2021.csv",
    out_csv="doh-epi-laguna-dengue-2026-2021.csv",
):
    df = pd.read_csv(in_csv)
    df_laguna = df[df["loc"].str.contains("Laguna", case=False, na=False)].copy()
    df_laguna = df_laguna.drop(columns=["loc", "Region"])
    df_laguna["date"] = pd.to_datetime(df_laguna["date"])
    df_laguna["date"] = df_laguna["date"].dt.strftime("%Y-%m-%d")
    df_laguna = df_laguna.reset_index(drop=True)
    df_laguna.to_csv(out_csv, index=False)
    return df_laguna

# ----------------------------------------
# Generate CSV file for Mapping pcode to name
# ----------------------------------------
def generate_pcode_names():
    geo = pd.DataFrame(gpd.read_file("laguna_barangay_geodata.geojson").drop(columns="geometry"))

    lookup = (
        geo[["adm4_pcode", "adm4_name", "adm3_pcode", "adm3_name"]]
        .rename(columns={
            "adm4_pcode": "barangay_pcode",
            "adm4_name": "barangay_name",
            "adm3_pcode": "municipality_pcode",
            "adm3_name": "municipality_name",
        })
        .drop_duplicates("barangay_pcode")
        .sort_values("barangay_pcode")
    )

    assert lookup["barangay_pcode"].is_unique
    lookup.to_csv("laguna_pcode_lookup.csv", index=False, encoding="utf-8-sig")
# generate_pcode_names()


BGY_OVERRIDES = {
    ("SANTA ROSA", "POOC"): "POOK",
}
def fix_mojibake(text):
    try:
        return text.encode("cp1252").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text
def clean_text(text):
    if pd.isna(text):
        return ""
    text = fix_mojibake(str(text))
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = text.upper()
    text = re.sub(r"\([^)]*\)", "", text)             # (HALANG), (CALABUSO), (POB.), ...
    text = re.sub(r"\b(CITY OF|MUNICIPALITY OF)\b", "", text)
    text = re.sub(r"\bCITY\b", "", text)
    text = re.sub(r"\bSTA\b\.?", "SANTA", text)
    text = re.sub(r"\bSTO\b\.?", "SANTO", text)
    text = re.sub(r"[^\w\s]", "", text)
    return " ".join(text.split())

# ----------------------------------------
# Convert name to pcode for Cluster Data
# ----------------------------------------
def map_names_to_pcodes(
    csv_path,
    lookup_path="laguna_pcode_lookup.csv",
    out_path="laguna_bgy_pcode_dengue_clusters.csv",
):
    df = pd.read_csv(csv_path)
    lookup = pd.read_csv(lookup_path, encoding="utf-8-sig")

    lookup["clean_mun"] = lookup["municipality_name"].apply(clean_text)
    lookup["clean_bgy"] = lookup["barangay_name"].apply(clean_text)

    mun_lookup = (
        lookup.drop_duplicates("municipality_pcode")
              .set_index("clean_mun")["municipality_pcode"]
              .to_dict()
    )

    bgy_lookup = {
        (m, b): p
        for m, b, p in zip(
            lookup["municipality_pcode"], lookup["clean_bgy"], lookup["barangay_pcode"]
        )
    }

    df["clean_mun"] = df["municipality"].apply(clean_text)
    df["clean_bgy"] = [
        clean_text(BGY_OVERRIDES.get((m, b), b))
        for m, b in zip(df["clean_mun"], df["barangay"].apply(clean_text))
    ]

    df["municipality_pcode"] = df["clean_mun"].map(mun_lookup)
    df["barangay_pcode"] = [
        bgy_lookup.get((m, b)) for m, b in zip(df["municipality_pcode"], df["clean_bgy"])
    ]

    unmatched_mun = df.loc[df["municipality_pcode"].isna(), "municipality"].unique()
    unmatched_bgy = df.loc[
        df["barangay_pcode"].isna() & df["municipality_pcode"].notna(),
        ["municipality", "barangay"],
    ].drop_duplicates()
    print(f"Unmatched municipalities: {list(unmatched_mun)}")
    print(f"Unmatched barangays ({len(unmatched_bgy)}):\n{unmatched_bgy.to_string(index=False)}")

    df = df.drop(columns=["municipality", "barangay", "clean_mun", "clean_bgy"])
    front = ["municipality_pcode", "barangay_pcode"]
    df = df[front + [c for c in df.columns if c not in front]]

    df.to_csv(out_path, index=False)
    return df

# ----------------------------------------
# Clean GeoData
# ----------------------------------------
TARGET_CRS = "EPSG:32651"  
def _prep(gdf, name):
    if gdf.crs is None:
        raise ValueError(f"{name} has no CRS defined; set it before running.")
    if gdf.crs != TARGET_CRS:
        gdf = gdf.to_crs(TARGET_CRS)
    gdf = gdf[~gdf.geometry.isna() & ~gdf.geometry.is_empty].copy()
    gdf["geometry"] = gdf.geometry.make_valid()
    return gdf


# ----------------------------------------
# Overlay Admin Area over Hazard Area, return Intersection Area
# ----------------------------------------
def _hazard_area_by_unit(admin_gdf, hazard_gdf, level, id_col="adm4_pcode"):
    # Area (m^2) of a hazard level inside each admin unit.
    # Hazard polygons of the level are dissolved first so overlaps are not double counted.
    haz = hazard_gdf[hazard_gdf["Var"] == level]
    if haz.empty:
        return pd.Series(dtype=float)
    haz = haz.dissolve()[["geometry"]]
    inter = gpd.overlay(admin_gdf[[id_col, "geometry"]], haz,       # Intersection b/w barangay area and hazard tiles
                        how="intersection", keep_geom_type=True)
    inter["area"] = inter.geometry.area
    return inter.groupby(id_col)["area"].sum()

# ----------------------------------------
# Math Operations to Calculate Flood Hazard Area Percentage
# ----------------------------------------
def calculate_flood_hazard_percentages(
    admin_geojson,
    hazard_geojson,
    out_path="gis/bgy_flood_hazard_pct.csv",
    make_maps=False,
    map_dir="gis",
):
    pyogrio.set_gdal_config_options({"OGR_GEOJSON_MAX_OBJ_SIZE": 0})
 
    print("Loading spatial files...")
    admin_gdf = gpd.read_file(admin_geojson)
    hazard_gdf = gpd.read_file(hazard_geojson)
 
    admin_gdf = _prep(admin_gdf, "admin layer")
    hazard_gdf = _prep(hazard_gdf, "hazard layer")
 
    print("Hazard 'Var' values found:", sorted(hazard_gdf["Var"].dropna().unique()))
 
    admin_gdf = admin_gdf.dissolve(by="adm4_pcode", as_index=False)
    admin_gdf["total_area"] = admin_gdf.geometry.area
 
    print("Calculating Hazard Level 2 overlap...")
    h2 = _hazard_area_by_unit(admin_gdf, hazard_gdf, 2.0)
    print("Calculating Hazard Level 3 overlap...")
    h3 = _hazard_area_by_unit(admin_gdf, hazard_gdf, 3.0)
 
    admin_gdf["h2_area"] = admin_gdf["adm4_pcode"].map(h2).fillna(0)
    admin_gdf["h3_area"] = admin_gdf["adm4_pcode"].map(h3).fillna(0)
 
    admin_gdf["pct_flood_hazard_2"] = admin_gdf["h2_area"] / admin_gdf["total_area"] * 100
    admin_gdf["pct_flood_hazard_3"] = admin_gdf["h3_area"] / admin_gdf["total_area"] * 100
 
    pct_cols = ["pct_flood_hazard_2", "pct_flood_hazard_3"]
    over = (admin_gdf[pct_cols] > 100.01).any(axis=1).sum()
    if over:
        print(f"WARNING: {over} barangays exceed 100% - check for overlapping geometries.")
    admin_gdf[pct_cols] = admin_gdf[pct_cols].clip(upper=100)
 
    final_df = admin_gdf[["adm4_pcode"] + pct_cols].copy()
    final_df.to_csv(out_path, index=False)
    print(f"Successfully saved flood hazard stats to {out_path}!")
 
    if make_maps:
        _make_maps(admin_gdf, hazard_gdf, map_dir)
 
    return final_df

# ----------------------------------------
# Make 3 Types of Maps out of Flood Hazard Data
# ----------------------------------------
def _make_maps(admin_gdf, hazard_gdf, map_dir):

    # Haz2 Haz3 Comparison map
    fig, axes = plt.subplots(1, 2, figsize=(16, 8))
    for ax, col, title in zip(
        axes,
        ["pct_flood_hazard_2", "pct_flood_hazard_3"],
        ["Medium hazard (Var 2): % of barangay area",
         "High hazard (Var 3): % of barangay area"],
    ):
        admin_gdf.plot(column=col, cmap="YlOrRd", vmin=0, vmax=100,
                       linewidth=0.2, edgecolor="grey", legend=True, ax=ax,
                       missing_kwds={"color": "lightgrey", "label": "No data"})
        ax.set_title(title)
        ax.axis("off")
    plt.tight_layout()
    plt.savefig(f"{map_dir}/flood_hazard_choropleth.png", dpi=200)
    plt.close(fig)

    # Validation map
    fig, ax = plt.subplots(figsize=(10, 10))
    admin_gdf.boundary.plot(ax=ax, color="black", linewidth=0.3)
    hazard_gdf[hazard_gdf["Var"] == 2].plot(ax=ax, color="orange", alpha=0.6)
    hazard_gdf[hazard_gdf["Var"] == 3].plot(ax=ax, color="red", alpha=0.7)
    ax.set_title("NOAH 5-year flood hazard over barangay boundaries")
    ax.axis("off")
    plt.savefig(f"{map_dir}/flood_hazard_overlay.png", dpi=200)
    plt.close(fig)
 
    # Interactive map (needs folium + mapclassify)
    try:
        m = admin_gdf.to_crs("EPSG:4326").explore(
            column="pct_flood_hazard_3",
            cmap="YlOrRd",
            scheme="quantiles", k=5,
            tooltip=["adm4_pcode", "pct_flood_hazard_2", "pct_flood_hazard_3"],
            tiles="CartoDB positron",
            style_kwds={"weight": 0.3, "color": "grey"},
        )
        m.save(f"{map_dir}/flood_hazard_map.html")
    except ImportError:
        print("Skipped interactive map: pip install folium mapclassify")
 
    print(f"Maps saved to {map_dir}/")
 
#calculate_flood_hazard_percentages("gis/laguna_barangay_geodata.geojson","gis/laguna_floodhazard_5year.geojson")
#map_names_to_pcodes("laguna_leptospirosis_clusters.csv")

# ----------------------------------------
# Convert Flood Hazard Shapefile to GeoJSON
# ----------------------------------------
def clean_flood_shapefile(
    shapefile_path="gis/flood5year/Laguna_Flood_5year.shp",
    out_geojson="gis/Laguna_Flood_5year_cleaned.geojson",
):
    gdf = gpd.read_file(shapefile_path)
    print("Found laguna shapefile")
    print(gdf.columns)

    if gdf.crs != "EPSG:4326":
        gdf = gdf.to_crs("EPSG:4326")

    print("Cleaning shapefiles")
    gdf["geometry"] = gdf["geometry"].apply(make_valid)
    gdf = gdf[gdf["geometry"].notnull() & ~gdf["geometry"].is_empty]

    print("Done cleaning... labeling hazards")
    if "Var" in gdf.columns:
        hazard_mapping = {1: "Low", 2: "Medium", 3: "High"}
        gdf["hazard_label"] = gdf["Var"].map(hazard_mapping)

    print("Outputting GeoJSON...")
    gdf.to_file(out_geojson, driver="GeoJSON")
    print(f"Successfully converted to GeoJSON: {out_geojson}")
    return gdf

# ----------------------------------------
# Pop the last parsed file and step the index back by one.
# ----------------------------------------
def _undo_last(laguna_dfs, i):
    if laguna_dfs:
        removed = laguna_dfs.pop()
        name = removed["source_file"].iloc[0] if not removed.empty else "previous file"
        print(f"Undid last entry. Removed data from: {name}")
        return max(0, i - 1)
    print("Cannot undo: No files processed yet.")
    return i

# ----------------------------------------
# Simple Parser per DOH EB Weekly Report CSV file
# ----------------------------------------
def parse_doh_clustering_csv(raw_csv_text, start_date, end_date):
    lines = [line.strip() for line in raw_csv_text.strip().split("\n") if line.strip()]

    header_idx = next(i for i, l in enumerate(lines) if "Region" in l)
    csv_data = "\n".join(lines[header_idx:])
    df = pd.read_csv(io.StringIO(csv_data))
    df.columns = df.columns.str.strip()
    df_laguna = df[df[PROVINCE_COL].str.upper() == "LAGUNA"].copy()
    df_laguna["start_date"] = pd.to_datetime(start_date)
    df_laguna["end_date"] = pd.to_datetime(end_date)
    return df_laguna

# ----------------------------------------
# Given directory containing .csv files from DOH EB Weekly Reports, prompt user to input start and end dates, then compile into one CSV file
# ----------------------------------------
def collect_laguna_clusters(
    data_dir="ebweekly26/leptospirosis",
    out_csv="laguna_leptospirosis_clusters.csv",
    year=2026,
):
    """Prompt for start/end dates per CSV file, parse Laguna rows, save master CSV."""
    laguna_dfs = []
    csv_files = sorted(list(Path(data_dir).glob("*.csv")))
    i = 0

    print("Type 'u' or 'undo' at any prompt to go back to the previous file.")

    while i < len(csv_files):
        csv_file = csv_files[i]
        print(f"\n--- Current File [{i + 1}/{len(csv_files)}]: {csv_file.name} ---")

        user_start_input = input(
            "Enter start date (MM-DD or YYYY-MM-DD) [or 'u' to undo]: "
        ).strip()
        if user_start_input.lower() in ["u", "undo"]:
            i = _undo_last(laguna_dfs, i)
            continue

        user_end_input = input(
            "Enter end date (MM-DD or YYYY-MM-DD) [or 'u' to undo]: "
        ).strip()
        if user_end_input.lower() in ["u", "undo"]:
            i = _undo_last(laguna_dfs, i)
            continue

        if not user_start_input or not user_end_input:
            print(f"Skipping {csv_file.name} (No dates provided). Moving to next file.")
            i += 1
            continue

        # Prepend the year if only month and day (e.g., "02-15") are provided
        user_start = f"{year}-{user_start_input}" if len(user_start_input) <= 5 else user_start_input
        user_end = f"{year}-{user_end_input}" if len(user_end_input) <= 5 else user_end_input

        try:
            raw_text = csv_file.read_text(encoding="utf-8", errors="ignore")
            df_laguna = parse_doh_clustering_csv(raw_text, user_start, user_end)

            if not df_laguna.empty:
                df_laguna["source_file"] = csv_file.name
                laguna_dfs.append(df_laguna)
                print(f"Successfully parsed {len(df_laguna)} Laguna rows for {csv_file.name}")
            else:
                print(f"No Laguna data found in {csv_file.name}.")

            i += 1  # advance only if processed
        except Exception as e:
            print(f"Error processing {csv_file.name}: {e}. Please re-enter dates.")

    if not laguna_dfs:
        print("\nNo Laguna data was parsed across the files.")
        return None

    master_df = pd.concat(laguna_dfs, ignore_index=True)
    print(f"\nProcessing complete! Master DataFrame shape: {master_df.shape}")
    master_df.to_csv(out_csv, index=False)
    print(f"Master dataset successfully saved to: {out_csv}")
    return master_df

def clean_geojson():
    src = "gis/laguna_floodhazard_5year.geojson"
    dst = "gis/laguna_floodhazard_5year.gpkg"

    gdf = gpd.read_file(src)
    print(gdf.shape, gdf.crs, gdf.geom_type.unique())

    gdf = gdf.to_crs(4326)                        # normalize CRS
    gdf["geometry"] = gdf.geometry.make_valid()   # fix invalid polygons
    gdf = gdf.explode(index_parts=False)          # one polygon per row (optional, but faster queries)

    gdf.to_file(dst, driver="GPKG")
    print("Saved", dst)
#clean_geojson()

