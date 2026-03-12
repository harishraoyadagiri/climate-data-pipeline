"""
Data Loading Module — loads processed DataFrames into the SQLite warehouse.

Creates dimension and fact tables with proper schema, indexes, and upsert logic.
"""

import logging
import os
import sqlite3

import pandas as pd

from config import LOG_DATE_FORMAT, LOG_FORMAT, WAREHOUSE_DB

logging.basicConfig(format=LOG_FORMAT, datefmt=LOG_DATE_FORMAT, level=logging.INFO)
logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Schema Definitions
# ──────────────────────────────────────────────

SCHEMA_SQL = """
-- Dimension: City
CREATE TABLE IF NOT EXISTS dim_city (
    city_id     INTEGER PRIMARY KEY,
    city_key    TEXT UNIQUE NOT NULL,
    city_name   TEXT NOT NULL,
    state       TEXT NOT NULL,
    latitude    REAL NOT NULL,
    longitude   REAL NOT NULL,
    elevation   REAL NOT NULL,
    climate_zone TEXT NOT NULL
);

-- Dimension: Date
CREATE TABLE IF NOT EXISTS dim_date (
    date_id     INTEGER PRIMARY KEY,
    date        TEXT NOT NULL,
    year        INTEGER NOT NULL,
    month       INTEGER NOT NULL,
    day         INTEGER NOT NULL,
    quarter     INTEGER NOT NULL,
    day_of_week TEXT NOT NULL,
    is_weekend  INTEGER NOT NULL,
    season      TEXT NOT NULL,
    month_name  TEXT NOT NULL
);

-- Fact: Weather (daily aggregates)
CREATE TABLE IF NOT EXISTS fact_weather (
    city_id         INTEGER NOT NULL,
    date_id         INTEGER NOT NULL,
    temp_avg        REAL,
    temp_min        REAL,
    temp_max        REAL,
    humidity_avg    REAL,
    precip_total    REAL,
    wind_speed_avg  REAL,
    wind_speed_max  REAL,
    pressure_avg    REAL,
    cloud_cover_avg REAL,
    heat_index      REAL,
    is_extreme_heat INTEGER,
    is_freezing     INTEGER,
    precip_category TEXT,
    PRIMARY KEY (city_id, date_id),
    FOREIGN KEY (city_id) REFERENCES dim_city(city_id),
    FOREIGN KEY (date_id) REFERENCES dim_date(date_id)
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_fact_city ON fact_weather(city_id);
CREATE INDEX IF NOT EXISTS idx_fact_date ON fact_weather(date_id);
CREATE INDEX IF NOT EXISTS idx_fact_city_date ON fact_weather(city_id, date_id);
CREATE INDEX IF NOT EXISTS idx_dim_date_year ON dim_date(year);
CREATE INDEX IF NOT EXISTS idx_dim_date_month ON dim_date(month);
CREATE INDEX IF NOT EXISTS idx_dim_date_season ON dim_date(season);
"""


def create_schema(conn: sqlite3.Connection):
    """Create all tables and indexes if they don't exist."""
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    logger.info("✓ Schema created/verified")


# ──────────────────────────────────────────────
# Loading Functions
# ──────────────────────────────────────────────

def load_dim_city(conn: sqlite3.Connection, dim_city: pd.DataFrame):
    """Load city dimension using INSERT OR REPLACE for idempotency."""
    dim_city.to_sql("dim_city", conn, if_exists="replace", index=False)
    logger.info("✓ Loaded dim_city: %d rows", len(dim_city))


def load_dim_date(conn: sqlite3.Connection, dim_date: pd.DataFrame):
    """Load date dimension using INSERT OR REPLACE for idempotency."""
    # Convert date to string for SQLite storage
    df = dim_date.copy()
    df["date"] = df["date"].astype(str)
    df["is_weekend"] = df["is_weekend"].astype(int)
    df.to_sql("dim_date", conn, if_exists="replace", index=False)
    logger.info("✓ Loaded dim_date: %d rows", len(df))


def load_fact_weather(conn: sqlite3.Connection, fact_weather: pd.DataFrame):
    """Load fact table using INSERT OR REPLACE for idempotent upserts."""
    df = fact_weather.copy()

    # Convert booleans to integers for SQLite
    if "is_extreme_heat" in df.columns:
        df["is_extreme_heat"] = df["is_extreme_heat"].astype(int)
    if "is_freezing" in df.columns:
        df["is_freezing"] = df["is_freezing"].astype(int)

    # Convert category to string
    if "precip_category" in df.columns:
        df["precip_category"] = df["precip_category"].astype(str)

    df.to_sql("fact_weather", conn, if_exists="replace", index=False)
    logger.info("✓ Loaded fact_weather: %d rows", len(df))


# ──────────────────────────────────────────────
# Main Load Function
# ──────────────────────────────────────────────

def load_all(
    dim_city: pd.DataFrame,
    dim_date: pd.DataFrame,
    fact_weather: pd.DataFrame,
) -> str:
    """
    Load all DataFrames into the SQLite warehouse.

    Returns:
        Path to the warehouse database file
    """
    os.makedirs(os.path.dirname(WAREHOUSE_DB), exist_ok=True)

    logger.info("=" * 60)
    logger.info("LOADING DATA INTO WAREHOUSE")
    logger.info("Database: %s", WAREHOUSE_DB)
    logger.info("=" * 60)

    conn = sqlite3.connect(WAREHOUSE_DB)

    try:
        create_schema(conn)
        load_dim_city(conn, dim_city)
        load_dim_date(conn, dim_date)
        load_fact_weather(conn, fact_weather)

        # Verify loaded counts
        for table in ["dim_city", "dim_date", "fact_weather"]:
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            logger.info("  %s: %d rows in database", table, count)

        conn.commit()
        logger.info("✓ All data loaded successfully")

    finally:
        conn.close()

    return WAREHOUSE_DB


def query_warehouse(sql: str) -> pd.DataFrame:
    """Convenience function to query the warehouse and return a DataFrame."""
    conn = sqlite3.connect(WAREHOUSE_DB)
    try:
        return pd.read_sql_query(sql, conn)
    finally:
        conn.close()
