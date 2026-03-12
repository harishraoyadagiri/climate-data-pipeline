# ─────────────────────────────────────────────────
# Climate Data Pipeline — Makefile
# ─────────────────────────────────────────────────

.PHONY: help install run dashboard test lint dbt docker-up docker-down clean

help: ## Show available commands
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

install: ## Install Python dependencies
	pip install -r requirements.txt

run: ## Run the ETL pipeline (Jan 2024)
	python pipeline.py --start 2024-01-01 --end 2024-01-31

run-full: ## Run the full pipeline (2020–2025) with dbt
	python pipeline.py --start 2020-01-01 --end 2025-12-31 --dbt

dashboard: ## Start the Streamlit dashboard
	streamlit run dashboard.py --server.port 8502

test: ## Run pytest test suite
	pytest tests/ -v --tb=short

lint: ## Run flake8 linter
	flake8 . --config=.flake8

format: ## Format code with black
	black .

format-check: ## Check formatting without changing files
	black --check --diff .

dbt-run: ## Run dbt models
	cd dbt_project && dbt run --profiles-dir . --project-dir .

dbt-test: ## Run dbt tests
	cd dbt_project && dbt test --profiles-dir . --project-dir .

dbt-docs: ## Generate dbt documentation
	cd dbt_project && dbt docs generate --profiles-dir . --project-dir . && dbt docs serve --profiles-dir . --project-dir .

docker-up: ## Build and start all Docker containers
	docker-compose up --build

docker-down: ## Stop and remove Docker containers
	docker-compose down

docker-pipeline: ## Run only the pipeline container
	docker-compose up --build pipeline

docker-dashboard: ## Run only the dashboard container
	docker-compose up --build dashboard

clean: ## Remove generated files
	rm -rf data/raw/*.csv data/processed/* data/warehouse.db data/warehouse.duckdb
	rm -rf __pycache__ .pytest_cache
	rm -rf dbt_project/target dbt_project/logs dbt_project/dbt_packages
