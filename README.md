# Climate Data Pipeline

## [Live Dashboard](https://climate-data-dashboard-harish.streamlit.app/)

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

---

## Walkthrough: Docker + dbt + CI/CD

### 1. Docker Containerization

Created a two-container setup:

| File | Purpose |
|------|---------|
| `Dockerfile` | Pipeline runner — Python 3.11, runs ETL |
| `Dockerfile.dashboard` | Streamlit dashboard with health check |
| `docker-compose.yml` | Orchestrates both, shared `./data` volume |
| `.dockerignore` | Excludes caches and data from build |

**Key design decisions:**
- Pipeline container runs ETL then exits; dashboard waits for it via `depends_on: service_completed_successfully`
- Both share `./data` volume so the warehouse persists locally
- Dashboard has a health check on `/_stcore/health`

---

### 2. dbt Transformation Layer

Created a full dbt project using `dbt-duckdb` adapter:

```
dbt_project/
├── dbt_project.yml          # Project config
├── profiles.yml             # DuckDB connection
└── models/
    ├── schema.yml           # Tests: not_null, unique, accepted_values
    ├── staging/
    │   ├── sources.yml      # Raw table definitions
    │   ├── stg_weather.sql  # Cleaned facts + temp_range
    │   ├── stg_cities.sql   # City dimension
    │   └── stg_dates.sql    # Date dimension
    └── marts/
        ├── mart_city_daily.sql    # Denormalized daily (star→flat)
        ├── mart_city_monthly.sql  # Monthly aggregates
        └── mart_city_summary.sql  # City climate profiles
```

**Pipeline integration:** Added `--dbt` flag to `pipeline.py` — exports SQLite → DuckDB, then runs `dbt run` + `dbt test`.

---

### 3. CI/CD (GitHub Actions)

`.github/workflows/ci.yml` — 4 jobs:

| Job | Steps |
|-----|-------|
| **test** | `pytest` — 32 tests |
| **lint** | `flake8` + `black --check` |
| **docker** | Build both images, verify startup |
| **dbt** | `dbt debug` + `dbt compile` |

---

### 4. Developer Tooling

| File | Purpose |
|------|---------|
| `Makefile` | 15 commands: `make run`, `make dbt-run`, `make docker-up`, etc. |
| `.flake8` | Linter config (120 char lines, dashboard exemptions) |
| `requirements.txt` | Added dbt-duckdb, duckdb, flake8, black |

---

## Final Project Structure

```
climate-data-pipeline/
├── .dockerignore
├── .flake8
├── .github/workflows/ci.yml
├── Dockerfile
├── Dockerfile.dashboard
├── docker-compose.yml
├── Makefile
├── README.md
├── requirements.txt
├── config.py
├── ingest.py
├── transform.py
├── quality.py
├── load.py
├── pipeline.py
├── dashboard.py
├── dbt_project/
│   ├── dbt_project.yml
│   ├── profiles.yml
│   └── models/
│       ├── schema.yml
│       ├── staging/
│       │   ├── sources.yml
│       │   ├── stg_weather.sql
│       │   ├── stg_cities.sql
│       │   └── stg_dates.sql
│       └── marts/
│           ├── mart_city_daily.sql
│           ├── mart_city_monthly.sql
│           └── mart_city_summary.sql
├── tests/
│   ├── __init__.py
│   └── test_pipeline.py
└── data/
    ├── raw/
    ├── processed/
    └── warehouse.db
```
Would love to hear any suggestions or modifications - email: harishraoyadagiri@gmail.com
