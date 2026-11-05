# Makefile for Api-Agent
# Use the project virtual environment consistently, even when it is not activated.

VENV_PYTHON := .venv/bin/python
PIP := $(VENV_PYTHON) -m pip

.PHONY: help install install-frontend setup run-backend run-frontend run-local-backend run-local-frontend docker-up docker-down docker-db-up docker-logs test clean venv

help: ## Show available make commands
	@echo "Api-Agent - Make Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make setup          Create venv and install all dependencies (backend + frontend)"
	@echo "  make install        Install backend dependencies only"
	@echo "  make install-frontend Install frontend dependencies only"
	@echo ""
	@echo "Run:"
	@echo "  make run-local-backend  Start backend locally on port 8000"
	@echo "  make run-local-frontend Start frontend locally on port 8501"
	@echo "  make docker-up          Build and run PostgreSQL + backend + frontend"
	@echo "  make docker-db-up       Run only PostgreSQL for local app development"
	@echo "  make docker-down        Stop Docker Compose services"
	@echo "  make docker-logs        Follow Docker Compose logs"
	@echo ""
	@echo "Test:"
	@echo "  make test           Run unit tests with pytest"
	@echo ""
	@echo "Clean:"
	@echo "  make clean-cache     Clean cache files only (keeps venv)"

venv: ## Create Python virtual environment
	@if [ ! -d ".venv" ]; then \
		echo "Creating virtual environment..."; \
		python3 -m venv .venv; \
	else \
		echo "Virtual environment already exists."; \
	fi

install: venv ## Install backend dependencies
	@echo "Installing backend dependencies..."
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

install-frontend: venv ## Install frontend dependencies
	@echo "Installing frontend dependencies..."
	$(PIP) install -r frontend/requirements.txt

setup: install install-frontend ## Full setup: create venv and install all dependencies
	@echo "Setup complete."
	@echo ""
	@echo "Next steps:"
	@echo "  1. Copy .env.example to .env and add your LLM API keys"
	@echo "  2. Run: make docker-db-up"
	@echo "  3. Run make run-local-backend and make run-local-frontend in separate terminals"
	@echo "  4. Open http://localhost:8501"

run-backend: run-local-backend ## Backward-compatible alias for local backend

run-frontend: run-local-frontend ## Backward-compatible alias for local frontend

run-local-backend: ## Start FastAPI backend locally on port 8000
	@echo "Starting FastAPI backend on http://localhost:8000"
	uvicorn app.main:app --reload --port 8000

run-local-frontend: ## Start Streamlit frontend locally on port 8501
	@echo "Starting Streamlit frontend on http://localhost:8501"
	streamlit run frontend/app.py --server.port 8501

docker-up: ## Build and run PostgreSQL, backend, and frontend in Docker
	docker compose up --build -d

docker-db-up: ## Run PostgreSQL only for locally run app processes
	docker compose up -d postgres

docker-down: ## Stop Docker Compose services and retain PostgreSQL data
	docker compose down

docker-logs: ## Follow Docker Compose service logs
	docker compose logs -f

test: venv ## Run unit tests
	@echo "Running unit tests..."
	$(PIP) install pytest 2>/dev/null
	$(VENV_PYTHON) -m pytest tests/ -v

clean-cache: ## Clean cache files only (keeps venv and dependencies)
	@echo "Cleaning cache files..."
	rm -rf __pycache__
	rm -rf app/__pycache__
	rm -rf tests/__pycache__
	rm -rf frontend/__pycache__
	rm -rf .pytest_cache
	rm -rf .ruff_cache
	rm -rf .mypy_cache
	rm -rf *.egg-info
	rm -rf build
	rm -rf dist
	find . -name "*.pyc" -delete
	find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null
	@echo "Cache clean complete."
