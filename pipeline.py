"""
Pipeline Orchestrator — runs the full ETL pipeline end-to-end.

Steps: Ingest → Transform → Quality Check → Load → (optional) dbt

Usage:
    python pipeline.py                                       # Full run (2020-2025)
    python pipeline.py --start 2024-01-01 --end 2024-01-31   # Custom range
    python pipeline.py --skip-ingest                          # Use cached raw data
    python pipeline.py --dbt                                  # Run dbt models after load
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime

import numpy as np

from config import (
    DEFAULT_END_DATE,
    DEFAULT_START_DATE,
    LOG_DATE_FORMAT,
    LOG_FORMAT,
    PROCESSED_DIR,
)


class NumpyEncoder(json.JSONEncoder):
    """JSON encoder that handles numpy types."""
    def default(self, obj):
        if isinstance(obj, (np.bool_,)):
            return bool(obj)
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)

logging.basicConfig(format=LOG_FORMAT, datefmt=LOG_DATE_FORMAT, level=logging.INFO)
logger = logging.getLogger(__name__)


def run_pipeline(
    start_date: str = DEFAULT_START_DATE,
    end_date: str = DEFAULT_END_DATE,
    skip_ingest: bool = False,
    force_load: bool = False,
    run_dbt: bool = False,
) -> dict:
    """
    Execute the full data pipeline.

    Args:
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        skip_ingest: If True, skip API ingestion (use existing raw files)
        force_load: If True, load even if quality checks fail
        run_dbt: If True, run dbt models after loading data

    Returns:
        Pipeline execution summary dict
    """
    pipeline_start = time.time()
    summary = {
        "start_date": start_date,
        "end_date": end_date,
        "pipeline_start": datetime.now().isoformat(),
        "steps": {},
    }

    logger.info("=" * 70)
    logger.info("  CLIMATE DATA PIPELINE")
    logger.info("  Date Range: %s → %s", start_date, end_date)
    logger.info("  Skip Ingest: %s | Force Load: %s", skip_ingest, force_load)
    logger.info("=" * 70)

    # ── Step 1: Ingest ──────────────────────────
    if not skip_ingest:
        logger.info("\n▶ STEP 1/4: DATA INGESTION")
        step_start = time.time()

        from ingest import ingest_all

        ingest_result = ingest_all(start_date, end_date)
        step_duration = time.time() - step_start

        summary["steps"]["ingest"] = {
            "duration_seconds": round(step_duration, 2),
            "success_count": ingest_result["success_count"],
            "failed_count": ingest_result["failed_count"],
        }

        if ingest_result["failed_count"] > 0:
            logger.warning(
                "Some cities failed ingestion: %s",
                ", ".join(ingest_result["failed"]),
            )
    else:
        logger.info("\n▶ STEP 1/4: SKIPPED (using cached raw data)")
        summary["steps"]["ingest"] = {"skipped": True}

    # ── Step 2: Transform ───────────────────────
    logger.info("\n▶ STEP 2/4: DATA TRANSFORMATION")
    step_start = time.time()

    from transform import transform_all

    tables = transform_all(start_date, end_date)

    if not tables:
        logger.error("Transformation produced no data. Aborting pipeline.")
        summary["steps"]["transform"] = {"error": "No data produced"}
        summary["overall_status"] = "FAILED"
        return summary

    step_duration = time.time() - step_start
    summary["steps"]["transform"] = {
        "duration_seconds": round(step_duration, 2),
        "dim_city_rows": len(tables["dim_city"]),
        "dim_date_rows": len(tables["dim_date"]),
        "fact_weather_rows": len(tables["fact_weather"]),
    }

    # ── Step 3: Quality Checks ──────────────────
    logger.info("\n▶ STEP 3/4: DATA QUALITY CHECKS")
    step_start = time.time()

    from quality import run_quality_checks

    quality_report = run_quality_checks(
        tables["fact_weather"],
        tables["dim_city"],
        start_date,
        end_date,
    )

    step_duration = time.time() - step_start
    quality_summary = quality_report.summary
    summary["steps"]["quality"] = {
        "duration_seconds": round(step_duration, 2),
        **quality_summary,
    }

    # Save quality report
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    report_path = os.path.join(PROCESSED_DIR, "quality_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(quality_summary, f, indent=2, cls=NumpyEncoder, default=str)
    logger.info("Quality report saved: %s", report_path)

    if not quality_report.passed and not force_load:
        logger.error(
            "Quality checks FAILED. Use --force to load anyway. Aborting."
        )
        summary["overall_status"] = "FAILED_QUALITY"
        return summary

    # ── Step 4: Load ────────────────────────────
    logger.info("\n▶ STEP 4/4: LOADING INTO WAREHOUSE")
    step_start = time.time()

    from load import load_all

    db_path = load_all(tables["dim_city"], tables["dim_date"], tables["fact_weather"])

    step_duration = time.time() - step_start
    summary["steps"]["load"] = {
        "duration_seconds": round(step_duration, 2),
        "database": db_path,
    }

    # ── Step 5 (optional): dbt ──────────────────
    if run_dbt:
        logger.info("\n▶ STEP 5/5: DBT MODELS")
        step_start = time.time()

        import subprocess
        import sqlite3

        try:
            import duckdb
        except ImportError:
            logger.error("duckdb not installed. Run: pip install duckdb dbt-duckdb")
            summary["steps"]["dbt"] = {"error": "duckdb not installed"}
        else:
            # Export SQLite tables to DuckDB for dbt
            duckdb_path = os.path.join(os.path.dirname(db_path), "warehouse.duckdb")
            duck_conn = duckdb.connect(duckdb_path)
            sqlite_conn = sqlite3.connect(db_path)

            import pandas as pd
            for table_name in ["dim_city", "dim_date", "fact_weather"]:
                df = pd.read_sql_query(f"SELECT * FROM {table_name}", sqlite_conn)
                duck_conn.execute(f"CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM df")
                logger.info("  Exported %s → DuckDB (%d rows)", table_name, len(df))

            sqlite_conn.close()
            duck_conn.close()

            # Run dbt
            dbt_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dbt_project")
            env = os.environ.copy()
            env["DBT_DATABASE_PATH"] = duckdb_path
            
            try:
                result = subprocess.run(
                    ["dbt", "run", "--profiles-dir", dbt_dir, "--project-dir", dbt_dir],
                    capture_output=True, text=True, check=True, cwd=dbt_dir, env=env
                )
                logger.info("dbt run output:\n%s", result.stdout[-500:] if len(result.stdout) > 500 else result.stdout)

                result_test = subprocess.run(
                    ["dbt", "test", "--profiles-dir", dbt_dir, "--project-dir", dbt_dir],
                    capture_output=True, text=True, check=True, cwd=dbt_dir, env=env
                )
                logger.info("dbt test output:\n%s", result_test.stdout[-500:] if len(result_test.stdout) > 500 else result_test.stdout)

                step_duration = time.time() - step_start
                summary["steps"]["dbt"] = {
                    "duration_seconds": round(step_duration, 2),
                    "status": "SUCCESS",
                }
            except subprocess.CalledProcessError as e:
                logger.error("dbt failed:\n%s\n%s", e.stdout, e.stderr)
                summary["steps"]["dbt"] = {"error": str(e), "stderr": e.stderr[-500:]}
            except FileNotFoundError:
                logger.error("dbt CLI not found. Install with: pip install dbt-duckdb")
                summary["steps"]["dbt"] = {"error": "dbt CLI not found"}

    # ── Summary ─────────────────────────────────
    total_duration = time.time() - pipeline_start
    summary["total_duration_seconds"] = round(total_duration, 2)
    summary["overall_status"] = "SUCCESS"
    summary["pipeline_end"] = datetime.now().isoformat()

    logger.info("\n" + "=" * 70)
    logger.info("  PIPELINE COMPLETE ✓")
    logger.info("  Total Duration: %.1f seconds", total_duration)
    logger.info("  Fact Rows: %d", len(tables["fact_weather"]))
    logger.info("  Database: %s", db_path)
    if run_dbt:
        logger.info("  dbt: %s", summary["steps"].get("dbt", {}).get("status", "SKIPPED"))
    logger.info("=" * 70)

    # Save pipeline summary
    summary_path = os.path.join(PROCESSED_DIR, "pipeline_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, cls=NumpyEncoder, default=str)

    return summary


def main():
    parser = argparse.ArgumentParser(
        description="Climate Data Pipeline — Ingest, Transform, Validate, Load"
    )
    parser.add_argument(
        "--start",
        default=DEFAULT_START_DATE,
        help=f"Start date (YYYY-MM-DD), default: {DEFAULT_START_DATE}",
    )
    parser.add_argument(
        "--end",
        default=DEFAULT_END_DATE,
        help=f"End date (YYYY-MM-DD), default: {DEFAULT_END_DATE}",
    )
    parser.add_argument(
        "--skip-ingest",
        action="store_true",
        help="Skip ingestion step (use existing raw files)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force load even if quality checks fail",
    )
    parser.add_argument(
        "--dbt",
        action="store_true",
        help="Run dbt models after loading data (requires dbt-duckdb)",
    )

    args = parser.parse_args()
    result = run_pipeline(args.start, args.end, args.skip_ingest, args.force, args.dbt)

    if result.get("overall_status") != "SUCCESS":
        sys.exit(1)


if __name__ == "__main__":
    main()
