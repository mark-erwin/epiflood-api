import io
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests
from shapely.validation import make_valid

PROVINCE_COL = "Province/ Highly Independent City"

# ----------------------------------------------------------------------
# Step 1: Laguna geodata
# ----------------------------------------------------------------------
def load_laguna_geodata(admin3_path="gis/phl_admin3.geojson", out_path=None):
    """Load the PH admin3 GeoJSON, reproject to EPSG:4326, keep Laguna only."""
    gdf = gpd.read_file(admin3_path)
    if gdf.crs != "EPSG:4326":
        gdf = gdf.to_crs("EPSG:4326")

    print("Loading GeoJSON...")
    print(gdf.columns)
    laguna_gdf = gdf[gdf["adm2_name"] == "Laguna"].copy()
    print(
        laguna_gdf[
            ["adm3_pcode", "adm3_name", "center_lat", "center_lon", "area_sqkm", "geometry"]
        ].head()
    )
    print(f"Found {len(laguna_gdf)} municipalities in Laguna.")

    if out_path:
        laguna_gdf.to_file(out_path, driver="GeoJSON")
    return laguna_gdf

# ----------------------------------------------------------------------
# Step 2: Rainfall (hourly -> weekly, W-SUN)
# ----------------------------------------------------------------------
def fetch_rainfall_weekly(
    laguna_gdf,
    start_date="2016-01-01",
    end_date="2026-10-16",
    out_path="gis/laguna_weekly_rainfall_2021_2025.csv",
):
    """Fetch hourly precipitation from Open-Meteo per municipality centroid and
    sum to weeks ending Sunday."""
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

    print("\n--- Combined Weekly Rainfall Data Preview ---")
    print(master_df.head(10))

    master_df.to_csv(out_path, index=False)
    print(f"\nSuccessfully saved all data to {out_path}!")
    return master_df


# ----------------------------------------------------------------------
# Step 3: DOH EPI dengue (2016-2021) -> Laguna only
# ----------------------------------------------------------------------
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

# ----------------------------------------------------------------------
# Step 4: Flood hazard shapefile -> cleaned GeoJSON
# ----------------------------------------------------------------------
def clean_flood_shapefile(
    shapefile_path="gis/flood5year/Laguna_Flood_5year.shp",
    out_geojson="gis/Laguna_Flood_5year_cleaned.geojson",
    out_parquet=None,
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

    # Optional: GeoParquet (smaller and faster for large layers)
    if out_parquet:
        gdf.to_parquet(out_parquet)
        print(f"Successfully converted to GeoParquet: {out_parquet}")
    return gdf

# ----------------------------------------------------------------------
# Step 5: DOH clustering CSVs (interactive date entry)
# ----------------------------------------------------------------------
def parse_doh_clustering_csv_with_prompt(raw_csv_text, start_date, end_date):
    """Parses DOH clustering CSV data using user-supplied start and end dates."""
    lines = [line.strip() for line in raw_csv_text.strip().split("\n") if line.strip()]

    # Locate header row and load CSV into DataFrame
    header_idx = next(i for i, l in enumerate(lines) if "Region" in l)
    csv_data = "\n".join(lines[header_idx:])
    df = pd.read_csv(io.StringIO(csv_data))
    df.columns = df.columns.str.strip()

    # Filter strictly for Laguna Province
    df_laguna = df[df[PROVINCE_COL].str.upper() == "LAGUNA"].copy()

    # Add user-provided date bounds as metadata columns
    df_laguna["start_date"] = pd.to_datetime(start_date)
    df_laguna["end_date"] = pd.to_datetime(end_date)
    df_laguna["period_days"] = (pd.to_datetime(end_date) - pd.to_datetime(start_date)).days + 1
    return df_laguna


def _undo_last(laguna_dfs, i):
    """Pop the last parsed file and step the index back by one."""
    if laguna_dfs:
        removed = laguna_dfs.pop()
        name = removed["source_file"].iloc[0] if not removed.empty else "previous file"
        print(f"Undid last entry. Removed data from: {name}")
        return max(0, i - 1)
    print("Cannot undo: No files processed yet.")
    return i


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
            df_laguna = parse_doh_clustering_csv_with_prompt(raw_text, user_start, user_end)

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


# ----------------------------------------------------------------------
# Step 6a: Barangay-level weekly estimates (each window spread over its days)
# ----------------------------------------------------------------------
def _load_clusters(clusters_csv):
    df = pd.read_csv(clusters_csv)
    df["start_date"] = pd.to_datetime(df["start_date"])
    df["end_date"] = pd.to_datetime(df["end_date"])
    return df

# ----------------------------------------------------------------------
# Step 6b: Municipal weekly estimates
# ----------------------------------------------------------------------
def clusters_to_municipal_weekly(
    clusters_csv="laguna_leptospirosis_clusters.csv",
    out_csv="laguna_leptospirosis_municipal_weekly.csv",
):
    df = _load_clusters(clusters_csv)
    expanded_rows = []

    for _, row in df.iterrows():
        period_days = (row["end_date"] - row["start_date"]).days + 1
        daily_rate = row["Cases in the previous 4 weeks"] / period_days

        clean_municipality = (
            str(row["Municipality/ City"]).replace("CITY OF BIÃ‘AN", "CITY OF BIÑAN").strip()
        )
        for d in pd.date_range(start=row["start_date"], end=row["end_date"]):
            expanded_rows.append(
                {"municipality": clean_municipality, "date": d, "daily_cases": daily_rate}
            )

    df_daily = pd.DataFrame(expanded_rows)
    df_municipal_weekly = (
        df_daily.groupby(["municipality", pd.Grouper(key="date", freq="W-SUN")])["daily_cases"]
        .sum()
        .reset_index(name="estimated_weekly_cases")
    )
    df_municipal_weekly["estimated_weekly_cases"] = df_municipal_weekly[
        "estimated_weekly_cases"
    ].round(2)

    df_municipal_weekly.to_csv(out_csv, index=False)
    print(f"Saved clean municipal weekly estimates to {out_csv}!")
    print("DataFrame Shape:", df_municipal_weekly.shape)
    print(df_municipal_weekly.head())
    return df_municipal_weekly


# ----------------------------------------------------------------------
# Step 7: Attach adm3_pcode to a municipal weekly file
# ----------------------------------------------------------------------
def link_pcodes(
    weekly_csv="laguna_leptospirosis_municipal_weekly.csv",
    geodata_path="laguna_geodata.geojson",
    out_csv="laguna_leptospirosis_pcode_weekly.csv",
):
    df = pd.read_csv(weekly_csv)

    # Standardize municipality text for matching
    df["municipality_lookup"] = (
        df["municipality"]
        .str.upper()
        .str.replace("Ã‘", "Ñ", regex=False)
        .str.replace("CITY OF ", "", regex=False)
        .str.strip()
    )

    gdf = gpd.read_file(geodata_path)
    gdf["municipality_lookup"] = (
        gdf["adm3_name"].str.upper().str.replace("CITY OF ", "", regex=False).str.strip()
    )
    name_to_pcode = dict(zip(gdf["municipality_lookup"], gdf["adm3_pcode"]))

    df["adm3_pcode"] = df["municipality_lookup"].map(name_to_pcode)
    df = df.drop(columns=["municipality_lookup"])
    df = df[["adm3_pcode", "municipality", "date", "estimated_weekly_cases"]]

    df.to_csv(out_csv, index=False)
    print("Successfully linked time-series data using adm3_pcode!")
    print(df.head())
    return df


# ----------------------------------------------------------------------
# Run whichever steps you need (same order as the original script)
# ----------------------------------------------------------------------
if __name__ == "__main__":
    # laguna_gdf = load_laguna_geodata("gis/phl_admin3.geojson", out_path="gis/laguna_geodata.geojson")
    # fetch_rainfall_weekly(laguna_gdf)
    # clean_doh_epi_dengue()
    # clean_flood_shapefile()
    # collect_laguna_clusters()
    # clusters_to_barangay_weekly()
    # clusters_to_municipal_weekly()
    # link_pcodes()
    pass