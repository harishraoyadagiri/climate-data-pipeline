# 🌍 Climate Data Pipeline

An end-to-end data pipeline that ingests historical weather data from the [Open-Meteo API](https://open-meteo.com/), transforms it into a dimensional model, validates data quality, and serves interactive analytics through a Streamlit dashboard.

Built to demonstrate **data engineering** skills: API ingestion, ETL, dimensional modeling, data quality validation, dbt transformations, Docker containerization, and CI/CD.

---

## Architecture

```
Open-Meteo API → Ingest (JSON) → Transform (Parquet) → SQLite Warehouse
                                        ↓                      ↓
                                 Quality Checks         DuckDB (via dbt)
                                        ↓                      ↓
                                Validation Reports     Staging → Mart Models
                                                               ↓
                                                     Streamlit Dashboard
```

| Layer | File | Description |
|-------|------|-------------|
| **Config** | `config.py` | Cities, API params, quality thresholds |
| **Ingest** | `ingest.py` | API client with retry logic & rate limiting |
| **Transform** | `transform.py` | Cleaning, aggregation, dimensional model |
| **Quality** | `quality.py` | Completeness, range, freshness, consistency checks |
| **Load** | `load.py` | SQLite schema, indexes, idempotent upserts |
| **dbt** | `dbt_project/` | Staging views + materialized mart tables (DuckDB) |
| **Orchestrate** | `pipeline.py` | Full ETL orchestrator with CLI |
| **Dashboard** | `dashboard.py` | Interactive Streamlit analytics app |

## Data Coverage

- **11 US Cities**: New York, Los Angeles, Chicago, Houston, Phoenix, Philadelphia, San Antonio, San Diego, Dallas, Denver, Austin
- **Variables**: Temperature, humidity, precipitation, wind speed, pressure, cloud cover
- **Granularity**: Hourly → aggregated to daily

---

## Quick Start

### Option A: Docker (Recommended)

```bash
# Build and run everything
docker-compose up --build

# Run only the pipeline
docker-compose up --build pipeline

# Run only the dashboard
docker-compose up --build dashboard
```

### Option B: Local Python

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run pipeline (Jan 2024)
python pipeline.py --start 2024-01-01 --end 2024-01-31

# 3. Run pipeline + dbt models
python pipeline.py --start 2024-01-01 --end 2024-01-31 --dbt

# 4. Launch dashboard
streamlit run dashboard.py --server.port 8502
```

### Makefile Shortcuts

```bash
make install        # Install dependencies
make run            # Run pipeline (Jan 2024)
make run-full       # Full pipeline (2020-2025) + dbt
make dashboard      # Start Streamlit dashboard
make test           # Run pytest
make lint           # Run flake8
make dbt-run        # Run dbt models
make dbt-test       # Run dbt tests
make docker-up      # Docker compose up --build
make docker-down    # Docker compose down
make clean          # Remove generated files
```

---

## dbt Transformation Layer

The pipeline includes a **dbt** layer (using DuckDB adapter) that builds analytics-ready models:

```
Sources (raw)          Staging (views)         Marts (tables)
┌──────────────┐      ┌──────────────┐       ┌───────────────────┐
│ fact_weather  │ ──►  │ stg_weather  │ ──►   │ mart_city_daily   │
│ dim_city      │ ──►  │ stg_cities   │       │ mart_city_monthly │
│ dim_date      │ ──►  │ stg_dates    │       │ mart_city_summary │
└──────────────┘      └──────────────┘       └───────────────────┘
```

| Model | Description |
|-------|-------------|
| `stg_weather` | Type-cast, cleaned facts with computed `temp_range` |
| `stg_cities` | Clean city dimension |
| `stg_dates` | Clean date dimension |
| `mart_city_daily` | Fully denormalized daily weather (joins all dims) |
| `mart_city_monthly` | Monthly aggregates with extreme weather counts |
| `mart_city_summary` | Overall city profiles — used by the Map page |

Schema tests include `not_null`, `unique`, and `accepted_values` validations.

---

## Dashboard Pages

| Page | Description |
|------|-------------|
| 📊 **Overview** | KPI cards, city comparison charts, temperature distribution |
| 📈 **Trends** | Daily temperature & precipitation time-series |
| 🗺️ **Heatmaps** | Monthly temp, precipitation & wind heatmaps |
| 🌎 **Map** | Interactive US map with city markers and climate profiles |

---

## CI/CD

GitHub Actions workflow (`.github/workflows/ci.yml`) with 4 jobs:

| Job | What It Does |
|-----|-------------|
| **test** | Runs `pytest` (32 tests) |
| **lint** | `flake8` + `black --check` |
| **docker** | Builds both Docker images, verifies they start |
| **dbt** | Validates and compiles dbt models |

---

## Data Quality Checks

| Check Type | What It Validates |
|------------|-------------------|
| **Completeness** | Non-null rates for critical columns (≥95%) |
| **Range** | Values within physical bounds (e.g., temp -60°C to 60°C) |
| **Freshness** | Full date coverage per city (≥90%) |
| **Consistency** | No duplicate city-date records, temp_min ≤ avg ≤ max |

---

## Technologies

- **Python** — pandas, requests, sqlite3
- **Storage** — SQLite (warehouse), DuckDB (dbt), Parquet (intermediate)
- **Transformation** — dbt (dbt-duckdb adapter)
- **Visualization** — Streamlit + Plotly
- **Containerization** — Docker + Docker Compose
- **CI/CD** — GitHub Actions
- **Testing** — pytest, flake8, black
- **Data Source** — Open-Meteo Historical Weather API (free, no API key)
