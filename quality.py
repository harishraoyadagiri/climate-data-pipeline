"""
Data Quality Module — validates processed data against defined thresholds.

Checks:
    - Completeness: non-null rates for critical columns
    - Range: values within physical/statistical bounds
    - Freshness: full date coverage
    - Consistency: no duplicate records
"""

import logging
from datetime import datetime

import pandas as pd

from config import CITIES, LOG_DATE_FORMAT, LOG_FORMAT, QUALITY_THRESHOLDS

logging.basicConfig(format=LOG_FORMAT, datefmt=LOG_DATE_FORMAT, level=logging.INFO)
logger = logging.getLogger(__name__)


class QualityReport:
    """Collects and summarizes data quality check results."""

    def __init__(self):
        self.checks = []
        self.start_time = datetime.now()

    def add_check(self, name: str, passed: bool, details: str, severity: str = "ERROR"):
        self.checks.append(
            {
                "check": name,
                "passed": passed,
                "details": details,
                "severity": severity,
                "timestamp": datetime.now().isoformat(),
            }
        )
        status = "✓ PASS" if passed else f"✗ FAIL [{severity}]"
        logger.info("%s | %s — %s", status, name, details)

    @property
    def passed(self) -> bool:
        """True if all ERROR-severity checks passed."""
        return all(
            c["passed"] for c in self.checks if c["severity"] == "ERROR"
        )

    @property
    def summary(self) -> dict:
        total = len(self.checks)
        passed = sum(1 for c in self.checks if c["passed"])
        failed = total - passed
        return {
            "total_checks": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": round(passed / total * 100, 1) if total > 0 else 0,
            "overall_status": "PASS" if self.passed else "FAIL",
            "checks": self.checks,
            "duration_seconds": (datetime.now() - self.start_time).total_seconds(),
        }


# ──────────────────────────────────────────────
# Completeness Checks
# ──────────────────────────────────────────────

def check_completeness(report: QualityReport, fact_df: pd.DataFrame):
    """Check that critical columns have acceptable non-null rates."""
    threshold = QUALITY_THRESHOLDS["completeness_threshold"]
    critical_cols = [
        "city_id", "date_id", "temp_avg", "temp_min", "temp_max",
        "humidity_avg", "precip_total", "wind_speed_avg",
    ]

    for col in critical_cols:
        if col not in fact_df.columns:
            report.add_check(
                f"completeness_{col}",
                False,
                f"Column '{col}' missing from fact table",
            )
            continue

        non_null_rate = fact_df[col].notna().mean()
        report.add_check(
            f"completeness_{col}",
            non_null_rate >= threshold,
            f"{col}: {non_null_rate:.1%} non-null (threshold: {threshold:.0%})",
            severity="ERROR" if col in ("city_id", "date_id") else "WARNING",
        )


# ──────────────────────────────────────────────
# Range Checks
# ──────────────────────────────────────────────

def check_ranges(report: QualityReport, fact_df: pd.DataFrame):
    """Check that values fall within physically valid ranges."""
    range_checks = {
        "temp_avg": ("temperature_min", "temperature_max"),
        "temp_min": ("temperature_min", "temperature_max"),
        "temp_max": ("temperature_min", "temperature_max"),
        "humidity_avg": ("humidity_min", "humidity_max"),
        "precip_total": ("precipitation_min", "precipitation_max"),
        "wind_speed_avg": ("wind_speed_min", "wind_speed_max"),
        "pressure_avg": ("pressure_min", "pressure_max"),
        "cloud_cover_avg": ("cloud_cover_min", "cloud_cover_max"),
    }

    for col, (min_key, max_key) in range_checks.items():
        if col not in fact_df.columns:
            continue

        col_data = fact_df[col].dropna()
        if col_data.empty:
            continue

        low = QUALITY_THRESHOLDS[min_key]
        high = QUALITY_THRESHOLDS[max_key]

        out_of_range = ((col_data < low) | (col_data > high)).sum()
        total = len(col_data)

        report.add_check(
            f"range_{col}",
            out_of_range == 0,
            f"{col}: {out_of_range}/{total} values out of range [{low}, {high}]",
            severity="WARNING",
        )


# ──────────────────────────────────────────────
# Freshness Checks
# ──────────────────────────────────────────────

def check_freshness(
    report: QualityReport,
    fact_df: pd.DataFrame,
    dim_city: pd.DataFrame,
    expected_start: str,
    expected_end: str,
):
    """Check that each city has data covering the full expected date range."""
    expected_days = (
        pd.to_datetime(expected_end) - pd.to_datetime(expected_start)
    ).days + 1

    for _, city in dim_city.iterrows():
        city_data = fact_df[fact_df["city_id"] == city["city_id"]]
        actual_days = city_data["date_id"].nunique()
        coverage = actual_days / expected_days if expected_days > 0 else 0

        report.add_check(
            f"freshness_{city['city_key']}",
            coverage >= 0.90,  # Allow 10% missing days
            f"{city['city_name']}: {actual_days}/{expected_days} days ({coverage:.1%} coverage)",
            severity="WARNING",
        )


# ──────────────────────────────────────────────
# Consistency Checks
# ──────────────────────────────────────────────

def check_consistency(report: QualityReport, fact_df: pd.DataFrame):
    """Check for duplicate records and logical consistency."""
    # No duplicate city-date combinations
    duplicates = fact_df.duplicated(subset=["city_id", "date_id"]).sum()
    report.add_check(
        "no_duplicates",
        duplicates == 0,
        f"{duplicates} duplicate city-date records found",
    )

    # Logical: temp_min <= temp_avg <= temp_max
    if all(c in fact_df.columns for c in ["temp_min", "temp_avg", "temp_max"]):
        invalid = (
            (fact_df["temp_min"] > fact_df["temp_avg"])
            | (fact_df["temp_avg"] > fact_df["temp_max"])
        ).sum()
        report.add_check(
            "temp_ordering",
            invalid == 0,
            f"{invalid} rows where temp_min > temp_avg or temp_avg > temp_max",
            severity="WARNING",
        )

    # Row count sanity
    total_rows = len(fact_df)
    num_cities = fact_df["city_id"].nunique()
    report.add_check(
        "row_count",
        total_rows > 0,
        f"{total_rows} total rows across {num_cities} cities",
    )


# ──────────────────────────────────────────────
# Main Quality Check Runner
# ──────────────────────────────────────────────

def run_quality_checks(
    fact_weather: pd.DataFrame,
    dim_city: pd.DataFrame,
    start_date: str,
    end_date: str,
) -> QualityReport:
    """
    Run all data quality checks and return a QualityReport.
    """
    report = QualityReport()

    logger.info("=" * 60)
    logger.info("RUNNING DATA QUALITY CHECKS")
    logger.info("=" * 60)

    check_completeness(report, fact_weather)
    check_ranges(report, fact_weather)
    check_freshness(report, fact_weather, dim_city, start_date, end_date)
    check_consistency(report, fact_weather)

    summary = report.summary
    logger.info("=" * 60)
    logger.info(
        "QUALITY CHECK %s: %d/%d passed (%.1f%%)",
        summary["overall_status"],
        summary["passed"],
        summary["total_checks"],
        summary["pass_rate"],
    )
    logger.info("=" * 60)

    return report
