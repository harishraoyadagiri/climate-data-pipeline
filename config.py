"""
Configuration for the Climate Data Pipeline.
Defines cities, date ranges, API settings, and file paths.
"""

import os

# ──────────────────────────────────────────────
# Project Paths
# ──────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
RAW_DIR = os.path.join(DATA_DIR, "raw")
PROCESSED_DIR = os.path.join(DATA_DIR, "processed")
WAREHOUSE_DB = os.path.join(DATA_DIR, "warehouse.db")

# ──────────────────────────────────────────────
# Date Range
# ──────────────────────────────────────────────
DEFAULT_START_DATE = "2020-01-01"
DEFAULT_END_DATE = "2026-02-28"

# ──────────────────────────────────────────────
# Open-Meteo API Configuration
# ──────────────────────────────────────────────
API_BASE_URL = "https://archive-api.open-meteo.com/v1/archive"

# Hourly variables to fetch
HOURLY_VARIABLES = [
    "temperature_2m",
    "relative_humidity_2m",
    "precipitation",
    "wind_speed_10m",
    "surface_pressure",
    "cloud_cover",
]

# ──────────────────────────────────────────────
# Cities — 10 Major US Cities
# ──────────────────────────────────────────────
CITIES = {
    "new_york": {
        "name": "New York",
        "state": "NY",
        "latitude": 40.7128,
        "longitude": -74.0060,
        "elevation": 10,
        "climate_zone": "Humid Subtropical",
    },
    "los_angeles": {
        "name": "Los Angeles",
        "state": "CA",
        "latitude": 34.0522,
        "longitude": -118.2437,
        "elevation": 71,
        "climate_zone": "Mediterranean",
    },
    "chicago": {
        "name": "Chicago",
        "state": "IL",
        "latitude": 41.8781,
        "longitude": -87.6298,
        "elevation": 181,
        "climate_zone": "Humid Continental",
    },
    "houston": {
        "name": "Houston",
        "state": "TX",
        "latitude": 29.7604,
        "longitude": -95.3698,
        "elevation": 12,
        "climate_zone": "Humid Subtropical",
    },
    "phoenix": {
        "name": "Phoenix",
        "state": "AZ",
        "latitude": 33.4484,
        "longitude": -112.0740,
        "elevation": 331,
        "climate_zone": "Arid Desert",
    },
    "philadelphia": {
        "name": "Philadelphia",
        "state": "PA",
        "latitude": 39.9526,
        "longitude": -75.1652,
        "elevation": 12,
        "climate_zone": "Humid Subtropical",
    },
    "san_antonio": {
        "name": "San Antonio",
        "state": "TX",
        "latitude": 29.4241,
        "longitude": -98.4936,
        "elevation": 198,
        "climate_zone": "Humid Subtropical",
    },
    "san_diego": {
        "name": "San Diego",
        "state": "CA",
        "latitude": 32.7157,
        "longitude": -117.1611,
        "elevation": 20,
        "climate_zone": "Mediterranean",
    },
    "dallas": {
        "name": "Dallas",
        "state": "TX",
        "latitude": 32.7767,
        "longitude": -96.7970,
        "elevation": 131,
        "climate_zone": "Humid Subtropical",
    },
    "denver": {
        "name": "Denver",
        "state": "CO",
        "latitude": 39.7392,
        "longitude": -104.9903,
        "elevation": 1609,
        "climate_zone": "Semi-Arid",
    },
    "austin": {
        "name": "Austin",
        "state": "TX",
        "latitude": 30.2672,
        "longitude": -97.7431,
        "elevation": 149,
        "climate_zone": "Humid Subtropical",
    },
}

# ──────────────────────────────────────────────
# Data Quality Thresholds
# ──────────────────────────────────────────────
QUALITY_THRESHOLDS = {
    "temperature_min": -60.0,   # °C
    "temperature_max": 60.0,    # °C
    "humidity_min": 0.0,        # %
    "humidity_max": 100.0,      # %
    "precipitation_min": 0.0,   # mm
    "precipitation_max": 500.0, # mm (daily)
    "wind_speed_min": 0.0,      # km/h
    "wind_speed_max": 300.0,    # km/h
    "pressure_min": 600.0,      # hPa (lowered for high-elevation cities like Denver ~820 hPa)
    "pressure_max": 1085.0,     # hPa
    "cloud_cover_min": 0.0,     # %
    "cloud_cover_max": 100.0,   # %
    "completeness_threshold": 0.95,  # 95% non-null required
}

# ──────────────────────────────────────────────
# Logging
# ──────────────────────────────────────────────
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
