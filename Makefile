# Makefile for Api-Agent

VENV := .venv
VENV_PYTHON := $(VENV)/bin/python
PIP := $(VENV_PYTHON) -m pip

.PHONY: help venv install install-frontend install-web setup \
        run-backend run-frontend run-local-backend run-local-frontend run-local-web serve-web \
        test gen-tokens gen-types check-tokens check-types check-web build-web \
        docker-up docker-up-build docker-down docker-legacy docker-db-up docker-db-reset docker-logs \
        clean-cache clean

help:
	@echo "Api-Agent - Make Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make setup            Create venv and install backend, frontend, and web deps"
	@echo "  make install          Install backend dependencies"
	@echo "  make install-frontend Install legacy Streamlit dependencies"
	@echo "  make install-web      Install Next.js dependencies"
	@echo ""
	@echo "Run:"
	@echo "  make run-local-backend  FastAPI on port 8000"
	@echo "  make run-local-web      Next.js on port 3000"
	@echo "  make run-local-frontend Legacy Streamlit on port 8501"
	@echo "  make docker-db-up       PostgreSQL only, for local app processes"
	@echo "  make docker-up          New stack: postgres, backend, Next.js web"
	@echo "  make docker-legacy      Add the legacy Streamlit UI on port 8501"
	@echo "  make docker-up-build    Rebuild images and start the stack"
	@echo "  make docker-down        Stop services and keep PostgreSQL data"
	@echo "  make docker-logs        Follow service logs"
	@echo ""
	@echo "Generate and check:"
	@echo "  make gen-tokens       web/src/app/tokens.css from frontend/styles/tokens.py"
	@echo "  make gen-types        web/openapi.json and web/src/types/api.generated.ts"
	@echo "  make check-tokens     Fail when tokens.css is stale"
	@echo "  make check-types      Fail when the OpenAPI snapshot or types are stale"
	@echo "  make check-web        Typecheck and lint the Next.js frontend"
	@echo "  make build-web        Production build of the Next.js frontend"
	@echo "  make serve-web        Serve the production build on PORT (default 3000)"
	@echo ""
	@echo "Tests and cleanup:"
	@echo "  make test             Backend tests"
	@echo "  make clean-cache      Caches only (keeps venv and node_modules)"
	@echo "  make clean            Remove venv and caches"

venv:
	@if [ ! -d "$(VENV)" ]; then \
		echo "Creating virtual environment..."; \
		python3 -m venv $(VENV); \
	else \
		echo "Virtual environment already exists."; \
	fi

install: venv
	@$(PIP) install --upgrade pip
	@$(PIP) install -r requirements.txt

install-frontend: venv
	@$(PIP) install -r frontend/requirements.txt

install-web:
	@cd web && npm install

setup: install install-frontend install-web
	@echo "Setup complete. Copy .env.example to .env and add LLM keys."

run-local-backend:
	@python -m uvicorn app.main:app --reload --port 8000

run-local-frontend:
	@python -m streamlit run frontend/app.py --server.port 8501

run-local-web:
	@cd web && npm run dev

run-backend: run-local-backend
run-frontend: run-local-frontend

test: venv
	@$(PIP) install pytest 2>/dev/null
	@$(VENV_PYTHON) -m pytest tests/ -v

gen-tokens: venv
	@$(VENV_PYTHON) scripts/gen_tokens.py

gen-types: venv
	@$(VENV_PYTHON) scripts/gen_types.py

check-tokens: venv
	@$(VENV_PYTHON) scripts/gen_tokens.py --check

check-types: venv
	@$(VENV_PYTHON) scripts/gen_types.py --check

check-web:
	@cd web && ./node_modules/.bin/tsc --noEmit
	@cd web && npm run lint

build-web:
	@cd web && npm run build

docker-up:
	@docker compose up --no-build -d

docker-up-build:
	@docker compose up --build -d

docker-db-up:
	@docker compose up -d postgres

docker-db-reset:
	@bash scripts/reset_local_database.sh

docker-legacy:
	@docker compose --profile legacy up -d frontend-legacy

docker-down:
	@docker compose down

docker-logs:
	@docker compose logs -f

clean-cache:
	@rm -rf __pycache__ app/__pycache__ tests/__pycache__ frontend/__pycache__
	@rm -rf .pytest_cache .ruff_cache .mypy_cache *.egg-info build dist
	@find . -name "*.pyc" -delete
	@find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null
	@echo "Cache clean complete."

clean:
	@rm -rf $(VENV) node_modules web/node_modules
	@$(MAKE) clean-cache

serve-web: build-web ## Serve the production build on PORT (default 3000)
	@cd web && mkdir -p .next/standalone/.next && rm -rf .next/standalone/.next/static && cp -R .next/static .next/standalone/.next/static
	@cd web && if [ -d public ]; then rm -rf .next/standalone/public && cp -R public .next/standalone/public; fi
	@cd web && BACKEND_URL=$${BACKEND_URL:-http://127.0.0.1:8000} PORT=$${PORT:-3000} HOSTNAME=127.0.0.1 node .next/standalone/server.js
