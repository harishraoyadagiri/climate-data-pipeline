# ─────────────────────────────────────────────────
# Climate Data Pipeline — ETL Runner
# ─────────────────────────────────────────────────
FROM python:3.11-slim AS base

LABEL maintainer="haris" \
      description="Climate Data Pipeline — ETL ingestion, transformation, and loading"

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY config.py ingest.py transform.py load.py quality.py pipeline.py ./
COPY tests/ ./tests/

# Create data directories
RUN mkdir -p data/raw data/processed

# Copy dbt project
COPY dbt_project/ ./dbt_project/

# Default: run the pipeline for Jan 2024
ENTRYPOINT ["python", "pipeline.py"]
CMD ["--start", "2024-01-01", "--end", "2024-01-31"]
