# DarijaAI — dev & worker commands
# Windows dev paths (.venv/Scripts/*). On Linux/CI use backend/.venv/bin/*.

PY := backend/.venv/Scripts/python.exe
ARQ := backend/.venv/Scripts/arq.exe
RUFF := backend/.venv/Scripts/ruff.exe
MYPY := backend/.venv/Scripts/mypy.exe
PYTEST := backend/.venv/Scripts/pytest.exe

.PHONY: help worker fetch-articles process-pending dev-up dev-down lint typecheck test

help:
	@echo "worker          - run the arq worker + scheduler (fetch/process/retry cron)"
	@echo "fetch-articles  - ingest all active RSS sources once (manual)"
	@echo "process-pending - localize all pending raw articles once (manual)"
	@echo "dev-up          - start postgres + redis (docker compose)"
	@echo "dev-down        - stop postgres + redis"
	@echo "lint / typecheck / test - backend quality gates"

# --- Worker / scheduler -----------------------------------------------------
worker:
	cd backend && .venv/Scripts/arq.exe app.workers.settings.WorkerSettings

fetch-articles:
	cd backend && .venv/Scripts/python.exe -m app.scripts.run_ingestion

process-pending:
	cd backend && .venv/Scripts/python.exe -m app.scripts.process_pending

# --- Local infra ------------------------------------------------------------
dev-up:
	docker compose -f infra/docker-compose.yml up -d

dev-down:
	docker compose -f infra/docker-compose.yml down

# --- Quality gates ----------------------------------------------------------
lint:
	cd backend && .venv/Scripts/ruff.exe check app && .venv/Scripts/ruff.exe format --check app

typecheck:
	cd backend && .venv/Scripts/mypy.exe --strict app/workers app/services/pipeline

test:
	cd backend && .venv/Scripts/pytest.exe
