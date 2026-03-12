"""
Data Transformation Module — cleans, enriches, and aggregates raw weather data
into a dimensional model ready for loading into the warehouse.

Transforms:
    Raw hourly JSON → Cleaned daily aggregates → Dimension & Fact DataFrames
"""

import json
import logging
import os

import pandas as pd

from config import (
    CITIES,
    LOG_DATE_FORMAT,
    LOG_FORMAT,
    PROCESSED_DIR,
    RAW_DIR,
)

logging.basicConfig(format=LOG_FORMAT, datefmt=LOG_DATE_FORMAT, level=logging.INFO)
logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Helper Functions
# ──────────────────────────────────────────────

def compute_heat_index(temp_c: float, rh: float) -> float:
    """
    Compute the heat index (feels-like temperature) using the Steadman formula.
    Only meaningful when temp >= 27°C and humidity >= 40%.
    """
    if temp_c < 27 or rh < 40:
        return temp_c

    # Rothfusz regression
    temp_f = temp_c * 9 / 5 + 32
    hi = (
        -42.379
        + 2.04901523 * temp_f
        + 10.14333127 * rh
        - 0.22475541 * temp_f * rh
        - 0.00683783 * temp_f**2
        - 0.05481717 * rh**2
        + 0.00122874 * temp_f**2 * rh
        + 0.00085282 * temp_f * rh**2
        - 0.00000199 * temp_f**2 * rh**2
    )
    return round((hi - 32) * 5 / 9, 2)


def get_season(month: int) -> str:
    """Map month number to meteorological season."""
    if month in (12, 1, 2):
        return "Winter"
    elif month in (3, 4, 5):
        return "Spring"
    elif month in (6, 7, 8):
        return "Summer"
    else:
        return "Fall"


# ──────────────────────────────────────────────
# Core Transformation Functions
# ──────────────────────────────────────────────

def parse_raw_json(city_key: str, filepath: str) -> pd.DataFrame:
    """
    Parse a raw Open-Meteo JSON file into a pandas DataFrame with hourly records.
    """
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    hourly = data["hourly"]
    df = pd.DataFrame(hourly)
    df["time"] = pd.to_datetime(df["time"])
    df["city_key"] = city_key
    df["date"] = df["time"].dt.date

    logger.info("Parsed %s: %d hourly records", city_key, len(df))
    return df


def clean_hourly_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean hourly data:
    - Clip out-of-range values
    - Forward-fill small gaps (up to 6 hours)
    """
    df = df.copy()

    # Clip physical bounds
    clip_rules = {
        "temperature_2m": (-60, 60),
        "relative_humidity_2m": (0, 100),
        "precipitation": (0, 500),
        "wind_speed_10m": (0, 300),
        "surface_pressure": (600, 1085),
        "cloud_cover": (0, 100),
    }

    for col, (low, high) in clip_rules.items():
        if col in df.columns:
            df[col] = df[col].clip(lower=low, upper=high)

    # Forward-fill small gaps (up to 6 consecutive nulls = 6 hours)
    weather_cols = list(clip_rules.keys())
    df[weather_cols] = df[weather_cols].ffill(limit=6)
    # Backfill any remaining leading nulls
    df[weather_cols] = df[weather_cols].bfill(limit=6)
    # Interpolate any remaining gaps
    for col in weather_cols:
        if df[col].isna().any():
            df[col] = df[col].interpolate(method='linear', limit=12)

    return df


def aggregate_to_daily(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate hourly data to daily summaries.
    Produces: avg/min/max temp, total precip, avg humidity, avg wind, avg pressure, avg cloud.
    """
    agg_dict = {
        "temperature_2m": ["mean", "min", "max"],
        "relative_humidity_2m": ["mean"],
        "precipitation": ["sum"],
        "wind_speed_10m": ["mean", "max"],
        "surface_pressure": ["mean"],
        "cloud_cover": ["mean"],
    }

    daily = df.groupby(["city_key", "date"]).agg(agg_dict)

    # Flatten multi-level column names
    daily.columns = [
        f"{col}_{agg}" if agg != "mean" else f"{col}_avg"
        for col, agg in daily.columns
    ]

    # Rename for clarity
    daily = daily.rename(
        columns={
            "temperature_2m_avg": "temp_avg",
            "temperature_2m_min": "temp_min",
            "temperature_2m_max": "temp_max",
            "relative_humidity_2m_avg": "humidity_avg",
            "precipitation_sum": "precip_total",
            "wind_speed_10m_avg": "wind_speed_avg",
            "wind_speed_10m_max": "wind_speed_max",
            "surface_pressure_avg": "pressure_avg",
            "cloud_cover_avg": "cloud_cover_avg",
        }
    )

    daily = daily.reset_index()
    daily["date"] = pd.to_datetime(daily["date"])

    # Round numerical columns
    num_cols = daily.select_dtypes(include="number").columns
    daily[num_cols] = daily[num_cols].round(2)

    logger.info("Aggregated to %d daily records", len(daily))
    return daily


def enrich_daily_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add derived columns to daily data:
    - heat_index, season, is_extreme_heat, is_freezing, precip_category
    """
    df = df.copy()

    # Heat index (using daily avg temp and humidity)
    df["heat_index"] = df.apply(
        lambda row: compute_heat_index(row["temp_avg"], row["humidity_avg"]),
        axis=1,
    )

    # Temporal features
    df["year"] = df["date"].dt.year
    df["month"] = df["date"].dt.month
    df["day_of_week"] = df["date"].dt.day_name()
    df["season"] = df["month"].apply(get_season)
    df["is_weekend"] = df["date"].dt.dayofweek >= 5

    # Extreme weather flags
    df["is_extreme_heat"] = df["temp_max"] > 35.0
    df["is_freezing"] = df["temp_min"] < 0.0

    # Precipitation category
    df["precip_category"] = pd.cut(
        df["precip_total"],
        bins=[-0.01, 0.0, 2.5, 7.6, 50.0, 500.0],
        labels=["Dry", "Light", "Moderate", "Heavy", "Extreme"],
    )
    # Ensure no NaN categories — fill with 'Dry' for 0mm precip
    df["precip_category"] = df["precip_category"].astype(str)
    df.loc[df["precip_category"] == "nan", "precip_category"] = "Dry"

    return df


# ──────────────────────────────────────────────
# Dimension Builders
# ──────────────────────────────────────────────

def build_dim_city() -> pd.DataFrame:
    """Build the city dimension table from config."""
    records = []
    for i, (key, info) in enumerate(CITIES.items(), start=1):
        records.append(
            {
                "city_id": i,
                "city_key": key,
                "city_name": info["name"],
                "state": info["state"],
                "latitude": info["latitude"],
                "longitude": info["longitude"],
                "elevation": info["elevation"],
                "climate_zone": info["climate_zone"],
            }
        )
    return pd.DataFrame(records)


def build_dim_date(start_date: str, end_date: str) -> pd.DataFrame:
    """Build the date dimension table for the given range."""
    dates = pd.date_range(start=start_date, end=end_date, freq="D")
    df = pd.DataFrame({"date": dates})

    df["date_id"] = df["date"].dt.strftime("%Y%m%d").astype(int)
    df["year"] = df["date"].dt.year
    df["month"] = df["date"].dt.month
    df["day"] = df["date"].dt.day
    df["quarter"] = df["date"].dt.quarter
    df["day_of_week"] = df["date"].dt.day_name()
    df["is_weekend"] = df["date"].dt.dayofweek >= 5
    df["season"] = df["month"].apply(get_season)
    df["month_name"] = df["date"].dt.month_name()

    return df


def build_fact_weather(daily_df: pd.DataFrame, dim_city: pd.DataFrame) -> pd.DataFrame:
    """
    Build the fact table by joining daily data with dimension keys.
    """
    # Map city_key → city_id
    city_map = dim_city.set_index("city_key")["city_id"].to_dict()
    fact = daily_df.copy()
    fact["city_id"] = fact["city_key"].map(city_map)
    fact["date_id"] = fact["date"].dt.strftime("%Y%m%d").astype(int)

    # Select fact columns
    fact_columns = [
        "city_id",
        "date_id",
        "temp_avg",
        "temp_min",
        "temp_max",
        "humidity_avg",
        "precip_total",
        "wind_speed_avg",
        "wind_speed_max",
        "pressure_avg",
        "cloud_cover_avg",
        "heat_index",
        "is_extreme_heat",
        "is_freezing",
        "precip_category",
    ]

    return fact[fact_columns]


# ──────────────────────────────────────────────
# Main Transformation Pipeline
# ──────────────────────────────────────────────

def transform_all(start_date: str, end_date: str) -> dict:
    """
    Run the full transformation pipeline:
    1. Parse all raw JSON files
    2. Clean and aggregate to daily
    3. Enrich with derived columns
    4. Build dimension and fact tables
    5. Save processed data as Parquet

    Returns:
        Dict with dim_city, dim_date, fact_weather DataFrames
    """
    os.makedirs(PROCESSED_DIR, exist_ok=True)

    # Step 1: Parse all raw files
    all_hourly = []
    for city_key in CITIES:
        pattern = f"{city_key}_{start_date}_{end_date}.json"
        filepath = os.path.join(RAW_DIR, pattern)

        if not os.path.exists(filepath):
            logger.warning("Raw file not found: %s — skipping", filepath)
            continue

        df = parse_raw_json(city_key, filepath)
        all_hourly.append(df)

    if not all_hourly:
        logger.error("No raw data files found! Run ingestion first.")
        return {}

    combined = pd.concat(all_hourly, ignore_index=True)
    logger.info("Combined %d total hourly records from %d cities", len(combined), len(all_hourly))

    # Step 2: Clean
    cleaned = clean_hourly_data(combined)

    # Step 3: Aggregate to daily
    daily = aggregate_to_daily(cleaned)

    # Step 4: Enrich
    enriched = enrich_daily_data(daily)

    # Step 5: Build dimensions and fact table
    dim_city = build_dim_city()
    dim_date = build_dim_date(start_date, end_date)
    fact_weather = build_fact_weather(enriched, dim_city)

    # Step 6: Save as Parquet
    dim_city.to_parquet(os.path.join(PROCESSED_DIR, "dim_city.parquet"), index=False)
    dim_date.to_parquet(os.path.join(PROCESSED_DIR, "dim_date.parquet"), index=False)
    fact_weather.to_parquet(os.path.join(PROCESSED_DIR, "fact_weather.parquet"), index=False)

    logger.info("✓ Saved dim_city (%d rows)", len(dim_city))
    logger.info("✓ Saved dim_date (%d rows)", len(dim_date))
    logger.info("✓ Saved fact_weather (%d rows)", len(fact_weather))

    return {
        "dim_city": dim_city,
        "dim_date": dim_date,
        "fact_weather": fact_weather,
    }


if __name__ == "__main__":
    from config import DEFAULT_START_DATE, DEFAULT_END_DATE

    transform_all(DEFAULT_START_DATE, DEFAULT_END_DATE)
