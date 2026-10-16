import requests
import pandas as pd
import geopandas as gpd
from shapely.validation import make_valid
import io
import re

from pathlib import Path

'''
gdf = gpd.read_file("gis/phl_admin3.geojson")
if gdf.crs != "EPSG:4326":
    gdf = gdf.to_crs("EPSG:4326")

# Step 1: Get Laguna GeoData
print("Loading GeoJSON...")
print(gdf.columns)
laguna_gdf = gdf[gdf["adm2_name"] == "Laguna"].copy()
print(laguna_gdf[["adm3_pcode", "adm3_name", "center_lat", "center_lon", "area_sqkm",  "geometry"]].head())
print(f"Found {len(laguna_gdf)} municipalities in Laguna.")

#laguna_gdf.to_file("gis/laguna_geodata.geojson", driver="GeoJSON")

# Step 2: Fetch Laguna Rainfall Data (mm)

url = "https://archive-api.open-meteo.com/v1/archive"
all_municipality_weekly_data = []
for index, row in laguna_gdf.iterrows():
    pcode = row["adm3_pcode"]
    name = row[ "adm3_name"]
    lat = row["center_lat"]
    lon = row["center_lon"]
    print(f"Fetching data for: {name} (Lat: {lat}, Lon: {lon})")
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": "2016-01-01",
        "end_date": "2026-10-16",
        "hourly": "precipitation",
        "timezone": "auto"
    }

    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        df_muni = pd.DataFrame({
            "date": data["hourly"]["time"],
            "precipitation_mm": data["hourly"]["precipitation"]
        })
        
        df_muni["date"] = pd.to_datetime(df_muni["date"])
        df_muni = df_muni.set_index("date")
        
        df_weekly = df_muni.resample("W-SUN")["precipitation_mm"].sum().reset_index()
        
        df_weekly["municipality"] = pcode
        
        all_municipality_weekly_data.append(df_weekly)
        
    except Exception as e:
        print(f"Error fetching data for {name}: {e}")

if all_municipality_weekly_data:
    master_df = pd.concat(all_municipality_weekly_data, ignore_index=True)
    
    # Reorder columns to look clean
    master_df = master_df[["municipality", "date", "precipitation_mm"]]
    
    print("\n--- Combined Weekly Rainfall Data Preview ---")
    print(master_df.head(10))
    
    # 4. Save to CSV
    output_path = "gis/laguna_weekly_rainfall_2021_2025.csv"
    master_df.to_csv(output_path, index=False)
    print(f"\nSuccessfully saved all data to {output_path}!")
else:
    print("No data was collected.")
'''
    
'''
# Step 3: Clean doh-epi-dengue-data.csv
df = pd.read_csv("doh-epi-dengue-data-2016-2021.csv")
df_laguna = df[df["loc"].str.contains("Laguna", case=False, na=False)].copy()
df_laguna = df_laguna.drop(columns=["loc", "Region"])
df_laguna["date"] = pd.to_datetime(df_laguna["date"])
df_laguna["date"] = df_laguna["date"].dt.strftime("%Y-%m-%d")
df_laguna = df_laguna.reset_index(drop=True)
df_laguna.to_csv("doh-epi-laguna-dengue-2026-2021.csv", index=False)
'''

'''
# 1. Load your shapefile
shapefile_path = "gis/flood5year/Laguna_Flood_5year.shp"
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
output_geojson = "gis/Laguna_Flood_5year_cleaned.geojson"
gdf.to_file(output_geojson, driver="GeoJSON")
print(f"Successfully converted to GeoJSON: {output_geojson}")


# Optional alternative: Export to GeoParquet (much faster and smaller file size for large layers)
#output_parquet = "data/processed/gis/Laguna_Flood_5year_cleaned.parquet"
#gdf.to_parquet(output_parquet)
#print(f"Successfully converted to GeoParquet: {output_parquet}")
'''

'''
def parse_doh_clustering_csv_with_prompt(raw_csv_text, start_date, end_date):
    """Parses DOH clustering CSV data using user-supplied start and end dates."""
    lines = [
        line.strip() for line in raw_csv_text.strip().split("\n") if line.strip()
    ]

    # Locate header row and load CSV into DataFrame
    header_idx = next(i for i, l in enumerate(lines) if "Region" in l)
    csv_data = "\n".join(lines[header_idx:])
    df = pd.read_csv(io.StringIO(csv_data))
    df.columns = df.columns.str.strip()

    # Filter strictly for Laguna Province
    df_laguna = df[
        df["Province/ Highly Independent City"].str.upper() == "LAGUNA"
    ].copy()

    # Add user-provided date bounds as metadata columns
    df_laguna["start_date"] = pd.to_datetime(start_date)
    df_laguna["end_date"] = pd.to_datetime(end_date)
    df_laguna["period_days"] = (
        pd.to_datetime(end_date) - pd.to_datetime(start_date)
    ).days + 1

    return df_laguna

# Define directory
data_dir = Path("ebweekly26/leptospirosis")
laguna_dfs = []

# Get sorted list of files to enable index-based navigation
csv_files = sorted(list(data_dir.glob("*.csv")))
i = 0

print("💡 Tip: Type 'u' or 'undo' at any prompt to go back to the previous file.")

while i < len(csv_files):
    csv_file = csv_files[i]
    print(f"\n--- Current File [{i+1}/{len(csv_files)}]: {csv_file.name} ---")

    # Prompt user for input
    user_start_input = input(
        "Enter start date (MM-DD or YYYY-MM-DD) [or 'u' to undo]: "
    ).strip()

    # Check for undo command
    if user_start_input.lower() in ["u", "undo"]:
        if laguna_dfs:
            removed = laguna_dfs.pop()
            print(f"↩️ Undid last entry. Removed data from: {removed['source_file'].iloc[0] if not removed.empty else 'previous file'}")
            i = max(0, i - 1)  # Move index back one file
        else:
            print("⚠️ Cannot undo: No files processed yet.")
        continue

    user_end_input = input(
        "Enter end date (MM-DD or YYYY-MM-DD) [or 'u' to undo]: "
    ).strip()

    if user_end_input.lower() in ["u", "undo"]:
        if laguna_dfs:
            removed = laguna_dfs.pop()
            print(f"↩️ Undid last entry. Removed data from: {removed['source_file'].iloc[0] if not removed.empty else 'previous file'}")
            i = max(0, i - 1)
        else:
            print("⚠️ Cannot undo: No files processed yet.")
        continue

    if not user_start_input or not user_end_input:
        print(f"Skipping {csv_file.name} (No dates provided). Moving to next file.")
        i += 1
        continue

    # Automatically prepend 2026- if only month and day (e.g., "02-15") are provided
    user_start = (
        f"2026-{user_start_input}"
        if len(user_start_input) <= 5
        else user_start_input
    )
    user_end = (
        f"2026-{user_end_input}" if len(user_end_input) <= 5 else user_end_input
    )

    try:
        raw_text = csv_file.read_text(encoding="utf-8", errors="ignore")
        df_laguna = parse_doh_clustering_csv_with_prompt(
            raw_text, user_start, user_end
        )

        if not df_laguna.empty:
            df_laguna["source_file"] = csv_file.name
            laguna_dfs.append(df_laguna)
            print(
                f"Successfully parsed {len(df_laguna)} Laguna rows for {csv_file.name}"
            )
        else:
            print(f"No Laguna data found in {csv_file.name}.")

        # Advance to the next file only if successful/processed
        i += 1

    except Exception as e:
        print(f"Error processing {csv_file.name}: {e}. Please re-enter dates.")

# Save master file after loop finishes
if laguna_dfs:
    master_df = pd.concat(laguna_dfs, ignore_index=True)
    print(f"\nProcessing complete! Master DataFrame shape: {master_df.shape}")

    raw_output_name = "laguna_leptospirosis_clusters.csv"

    # Save to CSV
    master_df.to_csv(raw_output_name, index=False)
    print(f"Master dataset successfully saved to: {raw_output_name}")
else:
    print("\nNo Laguna data was parsed across the files.")
'''
'''
# 1. Load the master dataset you generated
df = pd.read_csv("laguna_leptospirosis_clusters.csv")

# Convert date columns to datetime
df["start_date"] = pd.to_datetime(df["start_date"])
df["end_date"] = pd.to_datetime(df["end_date"])

expanded_rows = []

# 2. Expand each 28-day period into daily case contributions
for _, row in df.iterrows():
    period_days = (row["end_date"] - row["start_date"]).days + 1
    daily_rate = row["Cases in the previous 4 weeks"] / period_days

    # Generate dates covered by this report
    date_range = pd.date_range(start=row["start_date"], end=row["end_date"])

    for d in date_range:
        expanded_rows.append(
            {
                "region": row["Region"],
                "province": row["Province/ Highly Independent City"],
                "municipality": row["Municipality/ City"],
                "barangay": row["Barangay"],
                "date": d,
                "daily_cases": daily_rate,
            }
        )

df_daily = pd.DataFrame(expanded_rows)

# 3. Aggregate daily estimates into discrete weekly sums (Sunday-to-Sunday)
df_weekly = (
    df_daily.groupby(
        [
            "region",
            "province",
            "municipality",
            "barangay",
            pd.Grouper(key="date", freq="W-SUN"),
        ]
    )["daily_cases"]
    .sum()
    .reset_index(name="estimated_weekly_cases")
)

# Round to 2 decimal places
df_weekly["estimated_weekly_cases"] = df_weekly[
    "estimated_weekly_cases"
].round(2)

# Save to CSV
df_weekly.to_csv("laguna_leptospirosis_weekly_resampled.csv", index=False)
print("Saved clean weekly estimates! Shape:", df_weekly.shape)
'''

'''
# 1. Load the master dataset
df = pd.read_csv("laguna_leptospirosis_clusters.csv")

# Ensure dates are parsed as datetime
df["start_date"] = pd.to_datetime(df["start_date"])
df["end_date"] = pd.to_datetime(df["end_date"])

expanded_rows = []

# 2. Expand each 28-day period into daily case contributions
for _, row in df.iterrows():
    period_days = (row["end_date"] - row["start_date"]).days + 1
    daily_rate = row["Cases in the previous 4 weeks"] / period_days

    # Generate exact dates covered by this report window
    date_range = pd.date_range(start=row["start_date"], end=row["end_date"])

    # Clean municipality name encoding
    clean_municipality = (
        str(row["Municipality/ City"])
        .replace("CITY OF BIÃ‘AN", "CITY OF BIÑAN")
        .strip()
    )

    for d in date_range:
        expanded_rows.append(
            {
                "municipality": clean_municipality,
                "date": d,
                "daily_cases": daily_rate,
            }
        )

df_daily = pd.DataFrame(expanded_rows)

# 3. Aggregate daily estimates into discrete municipal weekly sums (Sunday-to-Sunday)
df_municipal_weekly = (
    df_daily.groupby(
        [
            "municipality",
            pd.Grouper(key="date", freq="W-SUN"),
        ]
    )["daily_cases"]
    .sum()
    .reset_index(name="estimated_weekly_cases")
)

# Round to 2 decimal places for cleanliness
df_municipal_weekly["estimated_weekly_cases"] = df_municipal_weekly[
    "estimated_weekly_cases"
].round(2)

# Save directly to municipal weekly CSV
output_filename = "laguna_leptospirosis_municipal_weekly.csv"
df_municipal_weekly.to_csv(output_filename, index=False)

print(f"Saved clean municipal weekly estimates to {output_filename}!")
print("DataFrame Shape:", df_municipal_weekly.shape)
print(df_municipal_weekly.head())
'''

'''
# 1. Load your municipal weekly dengue dataset
df_dengue = pd.read_csv("laguna_leptospirosis_municipal_weekly.csv")

# Standardize municipality text formatting for matching
df_dengue["municipality_lookup"] = (
    df_dengue["municipality"]
    .str.upper()
    .str.replace("Ã‘", "Ñ", regex=False)
    .str.replace("CITY OF ", "", regex=False)
    .str.strip()
)

# 2. Load your GeoJSON spatial file to extract the pcodes
gdf = gpd.read_file("laguna_geodata.geojson")

# Clean shapefile name column for matching
gdf["municipality_lookup"] = (
    gdf["adm3_name"]
    .str.upper()
    .str.replace("CITY OF ", "", regex=False)
    .str.strip()
)

# Extract just the lookup mapping (municipality name -> adm3_pcode)
name_to_pcode = dict(zip(gdf["municipality_lookup"], gdf["adm3_pcode"]))

# 3. Map the pcode directly onto your dengue dataframe
df_dengue["adm3_pcode"] = df_dengue["municipality_lookup"].map(name_to_pcode)

# Drop the temporary lookup helper column
df_dengue = df_dengue.drop(columns=["municipality_lookup"])

# Reorder columns to put adm3_pcode upfront
df_dengue = df_dengue[
    ["adm3_pcode", "municipality", "date", "estimated_weekly_cases"]
]

# 4. Save to a clean flat CSV file
df_dengue.to_csv("laguna_leptospirosis_pcode_weekly.csv", index=False)

print("Successfully linked dengue time-series data using adm3_pcode!")
print(df_dengue.head())
'''