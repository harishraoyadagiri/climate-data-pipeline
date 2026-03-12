"""
Data Ingestion Module — fetches historical weather data from the Open-Meteo API.

Usage:
    from ingest import ingest_all, fetch_city_weather
    ingest_all()  # Fetches data for all configured cities
"""

import json
import logging
import os
import time
from datetime import datetime

import requests

from config import (
    API_BASE_URL,
    CITIES,
    DEFAULT_END_DATE,
    DEFAULT_START_DATE,
    HOURLY_VARIABLES,
    LOG_DATE_FORMAT,
    LOG_FORMAT,
    RAW_DIR,
)

logging.basicConfig(format=LOG_FORMAT, datefmt=LOG_DATE_FORMAT, level=logging.INFO)
logger = logging.getLogger(__name__)

# Rate limiting: Open-Meteo allows ~600 requests/minute for free tier
REQUEST_DELAY_SECONDS = 0.5
MAX_RETRIES = 3
RETRY_BACKOFF_FACTOR = 2


def fetch_city_weather(
    city_key: str,
    start_date: str = DEFAULT_START_DATE,
    end_date: str = DEFAULT_END_DATE,
) -> dict | None:
    """
    Fetch historical hourly weather data for a single city from Open-Meteo.

    Args:
        city_key: Key from CITIES dict (e.g., 'new_york')
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format

    Returns:
        Raw API response dict, or None on failure
    """
    city = CITIES[city_key]
    params = {
        "latitude": city["latitude"],
        "longitude": city["longitude"],
        "start_date": start_date,
        "end_date": end_date,
        "hourly": ",".join(HOURLY_VARIABLES),
        "timezone": "America/New_York",
    }

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(
                "Fetching %s (%s, %s) | %s to %s | attempt %d/%d",
                city["name"],
                city["latitude"],
                city["longitude"],
                start_date,
                end_date,
                attempt,
                MAX_RETRIES,
            )
            response = requests.get(API_BASE_URL, params=params, timeout=60)
            response.raise_for_status()

            data = response.json()

            # Validate response structure
            if "hourly" not in data:
                logger.error("Missing 'hourly' key in response for %s", city["name"])
                return None

            # Save raw response
            filename = f"{city_key}_{start_date}_{end_date}.json"
            filepath = os.path.join(RAW_DIR, filename)
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

            logger.info(
                "✓ Saved %s → %s (%d hourly records)",
                city["name"],
                filename,
                len(data["hourly"]["time"]),
            )
            return data

        except requests.exceptions.HTTPError as e:
            if response.status_code == 429:
                wait = RETRY_BACKOFF_FACTOR**attempt
                logger.warning("Rate limited. Waiting %ds before retry...", wait)
                time.sleep(wait)
            else:
                logger.error("HTTP error for %s: %s", city["name"], e)
                return None

        except requests.exceptions.RequestException as e:
            logger.error("Request failed for %s: %s", city["name"], e)
            if attempt < MAX_RETRIES:
                wait = RETRY_BACKOFF_FACTOR**attempt
                logger.info("Retrying in %ds...", wait)
                time.sleep(wait)
            else:
                logger.error("All retries exhausted for %s", city["name"])
                return None

    return None


def ingest_all(
    start_date: str = DEFAULT_START_DATE,
    end_date: str = DEFAULT_END_DATE,
) -> dict:
    """
    Fetch weather data for all configured cities.

    Returns:
        Summary dict with success/failure counts and details
    """
    os.makedirs(RAW_DIR, exist_ok=True)

    results = {"success": [], "failed": [], "start_time": datetime.now().isoformat()}

    logger.info("=" * 60)
    logger.info("STARTING DATA INGESTION")
    logger.info("Cities: %d | Range: %s → %s", len(CITIES), start_date, end_date)
    logger.info("=" * 60)

    for city_key in CITIES:
        data = fetch_city_weather(city_key, start_date, end_date)

        if data is not None:
            results["success"].append(city_key)
        else:
            results["failed"].append(city_key)

        # Rate limiting delay between requests
        time.sleep(REQUEST_DELAY_SECONDS)

    results["end_time"] = datetime.now().isoformat()
    results["total"] = len(CITIES)
    results["success_count"] = len(results["success"])
    results["failed_count"] = len(results["failed"])

    logger.info("=" * 60)
    logger.info(
        "INGESTION COMPLETE: %d/%d succeeded",
        results["success_count"],
        results["total"],
    )
    if results["failed"]:
        logger.warning("Failed cities: %s", ", ".join(results["failed"]))
    logger.info("=" * 60)

    return results


if __name__ == "__main__":
    ingest_all()
