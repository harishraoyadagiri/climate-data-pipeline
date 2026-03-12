"""
Unit tests for the Climate Data Pipeline.

Tests transformation logic, quality checks, and dimensional model construction.
"""

import sys
import os
import pytest
import pandas as pd
import numpy as np
from datetime import datetime

# Ensure project root is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from transform import (
    compute_heat_index,
    get_season,
    clean_hourly_data,
    aggregate_to_daily,
    enrich_daily_data,
    build_dim_city,
    build_dim_date,
)
from quality import QualityReport, check_completeness, check_consistency


# ──────────────────────────────────────────────
# Helper: Create sample data
# ──────────────────────────────────────────────

def make_hourly_df(n_hours=48, city_key="test_city"):
    """Create a sample hourly DataFrame for testing."""
    dates = pd.date_range("2024-01-01", periods=n_hours, freq="h")
    np.random.seed(42)
    return pd.DataFrame({
        "time": dates,
        "city_key": city_key,
        "date": dates.date,
        "temperature_2m": np.random.uniform(-5, 15, n_hours),
        "relative_humidity_2m": np.random.uniform(40, 90, n_hours),
        "precipitation": np.random.uniform(0, 5, n_hours),
        "wind_speed_10m": np.random.uniform(0, 30, n_hours),
        "surface_pressure": np.random.uniform(1000, 1020, n_hours),
        "cloud_cover": np.random.uniform(0, 100, n_hours),
    })


def make_daily_df(n_days=30, city_key="test_city"):
    """Create a sample daily DataFrame for testing."""
    dates = pd.date_range("2024-01-01", periods=n_days, freq="D")
    np.random.seed(42)
    temp_avg = np.random.uniform(-5, 30, n_days)
    return pd.DataFrame({
        "city_key": city_key,
        "date": dates,
        "temp_avg": temp_avg,
        "temp_min": temp_avg - np.random.uniform(2, 8, n_days),
        "temp_max": temp_avg + np.random.uniform(2, 8, n_days),
        "humidity_avg": np.random.uniform(30, 80, n_days),
        "precip_total": np.random.uniform(0, 20, n_days),
        "wind_speed_avg": np.random.uniform(5, 20, n_days),
        "wind_speed_max": np.random.uniform(15, 40, n_days),
        "pressure_avg": np.random.uniform(1000, 1020, n_days),
        "cloud_cover_avg": np.random.uniform(20, 80, n_days),
    })


# ──────────────────────────────────────────────
# Tests: Helper Functions
# ──────────────────────────────────────────────

class TestHeatIndex:
    def test_low_temp_returns_same(self):
        """Heat index not computed below 27°C."""
        assert compute_heat_index(20.0, 50.0) == 20.0

    def test_low_humidity_returns_same(self):
        """Heat index not computed below 40% RH."""
        assert compute_heat_index(30.0, 30.0) == 30.0

    def test_high_heat_index(self):
        """Heat index should be higher than actual temp in hot humid conditions."""
        hi = compute_heat_index(35.0, 80.0)
        assert hi > 35.0

    def test_returns_float(self):
        result = compute_heat_index(30.0, 60.0)
        assert isinstance(result, float)


class TestGetSeason:
    def test_winter(self):
        assert get_season(12) == "Winter"
        assert get_season(1) == "Winter"
        assert get_season(2) == "Winter"

    def test_spring(self):
        assert get_season(3) == "Spring"
        assert get_season(5) == "Spring"

    def test_summer(self):
        assert get_season(6) == "Summer"
        assert get_season(8) == "Summer"

    def test_fall(self):
        assert get_season(9) == "Fall"
        assert get_season(11) == "Fall"


# ──────────────────────────────────────────────
# Tests: Cleaning
# ──────────────────────────────────────────────

class TestCleanHourlyData:
    def test_clips_temperature(self):
        df = make_hourly_df()
        df.loc[0, "temperature_2m"] = 100.0  # Out of range
        cleaned = clean_hourly_data(df)
        assert cleaned["temperature_2m"].max() <= 60.0

    def test_clips_humidity(self):
        df = make_hourly_df()
        df.loc[0, "relative_humidity_2m"] = -10.0
        cleaned = clean_hourly_data(df)
        assert cleaned["relative_humidity_2m"].min() >= 0.0

    def test_forward_fills_small_gaps(self):
        df = make_hourly_df()
        df.loc[5:8, "temperature_2m"] = np.nan  # 4-hour gap
        cleaned = clean_hourly_data(df)
        assert cleaned["temperature_2m"].loc[5:8].notna().all()

    def test_preserves_shape(self):
        df = make_hourly_df()
        cleaned = clean_hourly_data(df)
        assert cleaned.shape == df.shape


# ──────────────────────────────────────────────
# Tests: Aggregation
# ──────────────────────────────────────────────

class TestAggregateToDaily:
    def test_produces_daily_records(self):
        df = make_hourly_df(n_hours=48)  # 2 days
        daily = aggregate_to_daily(df)
        assert len(daily) == 2

    def test_has_required_columns(self):
        df = make_hourly_df()
        daily = aggregate_to_daily(df)
        required = ["city_key", "date", "temp_avg", "temp_min", "temp_max", "precip_total"]
        for col in required:
            assert col in daily.columns, f"Missing column: {col}"

    def test_min_less_than_max(self):
        df = make_hourly_df()
        daily = aggregate_to_daily(df)
        assert (daily["temp_min"] <= daily["temp_max"]).all()


# ──────────────────────────────────────────────
# Tests: Enrichment
# ──────────────────────────────────────────────

class TestEnrichDailyData:
    def test_adds_season(self):
        df = make_daily_df()
        enriched = enrich_daily_data(df)
        assert "season" in enriched.columns
        assert enriched["season"].isin(["Winter", "Spring", "Summer", "Fall"]).all()

    def test_adds_extreme_heat_flag(self):
        df = make_daily_df()
        enriched = enrich_daily_data(df)
        assert "is_extreme_heat" in enriched.columns

    def test_adds_freezing_flag(self):
        df = make_daily_df()
        enriched = enrich_daily_data(df)
        assert "is_freezing" in enriched.columns

    def test_adds_precip_category(self):
        df = make_daily_df()
        enriched = enrich_daily_data(df)
        assert "precip_category" in enriched.columns


# ──────────────────────────────────────────────
# Tests: Dimension Builders
# ──────────────────────────────────────────────

class TestDimCity:
    def test_has_11_cities(self):
        dim = build_dim_city()
        assert len(dim) == 11

    def test_has_required_columns(self):
        dim = build_dim_city()
        required = ["city_id", "city_key", "city_name", "state", "latitude", "longitude"]
        for col in required:
            assert col in dim.columns

    def test_unique_ids(self):
        dim = build_dim_city()
        assert dim["city_id"].is_unique


class TestDimDate:
    def test_correct_row_count(self):
        dim = build_dim_date("2024-01-01", "2024-01-31")
        assert len(dim) == 31

    def test_has_season(self):
        dim = build_dim_date("2024-06-01", "2024-06-30")
        assert (dim["season"] == "Summer").all()

    def test_unique_date_ids(self):
        dim = build_dim_date("2024-01-01", "2024-12-31")
        assert dim["date_id"].is_unique


# ──────────────────────────────────────────────
# Tests: Quality Checks
# ──────────────────────────────────────────────

class TestQualityReport:
    def test_all_pass(self):
        report = QualityReport()
        report.add_check("test1", True, "OK")
        report.add_check("test2", True, "OK")
        assert report.passed is True
        assert report.summary["pass_rate"] == 100.0

    def test_failure_detected(self):
        report = QualityReport()
        report.add_check("test1", True, "OK")
        report.add_check("test2", False, "Failed", severity="ERROR")
        assert report.passed is False

    def test_warning_does_not_fail(self):
        report = QualityReport()
        report.add_check("test1", True, "OK")
        report.add_check("test2", False, "Warning", severity="WARNING")
        assert report.passed is True


class TestCompleteness:
    def test_passes_with_complete_data(self):
        fact = pd.DataFrame({
            "city_id": [1, 1],
            "date_id": [20240101, 20240102],
            "temp_avg": [10.0, 12.0],
            "temp_min": [5.0, 6.0],
            "temp_max": [15.0, 18.0],
            "humidity_avg": [60.0, 65.0],
            "precip_total": [0.0, 2.0],
            "wind_speed_avg": [10.0, 12.0],
        })
        report = QualityReport()
        check_completeness(report, fact)
        assert all(c["passed"] for c in report.checks)

    def test_fails_with_nulls(self):
        fact = pd.DataFrame({
            "city_id": [1, None],
            "date_id": [20240101, 20240102],
            "temp_avg": [10.0, None],
            "temp_min": [5.0, None],
            "temp_max": [15.0, None],
            "humidity_avg": [60.0, None],
            "precip_total": [0.0, None],
            "wind_speed_avg": [10.0, None],
        })
        report = QualityReport()
        check_completeness(report, fact)
        failed = [c for c in report.checks if not c["passed"]]
        assert len(failed) > 0


class TestConsistency:
    def test_no_duplicates(self):
        fact = pd.DataFrame({
            "city_id": [1, 1, 2],
            "date_id": [20240101, 20240102, 20240101],
            "temp_min": [5, 6, 7],
            "temp_avg": [10, 12, 11],
            "temp_max": [15, 18, 16],
        })
        report = QualityReport()
        check_consistency(report, fact)
        dup_check = [c for c in report.checks if c["check"] == "no_duplicates"][0]
        assert dup_check["passed"] == True

    def test_detects_duplicates(self):
        fact = pd.DataFrame({
            "city_id": [1, 1],
            "date_id": [20240101, 20240101],  # Duplicate!
            "temp_min": [5, 5],
            "temp_avg": [10, 10],
            "temp_max": [15, 15],
        })
        report = QualityReport()
        check_consistency(report, fact)
        dup_check = [c for c in report.checks if c["check"] == "no_duplicates"][0]
        assert dup_check["passed"] == False
