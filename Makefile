# Makefile for Api-Agent
# Assumes virtual environment is activated before running make commands

.PHONY: help install install-frontend setup run-backend run-frontend test clean venv

help: ## Show available make commands
	@echo "Api-Agent - Make Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make setup          Create venv and install all dependencies (backend + frontend)"
	@echo "  make install        Install backend dependencies only"
	@echo "  make install-frontend Install frontend dependencies only"
	@echo ""
	@echo "Run:"
	@echo "  make run-backend    Start FastAPI backend on port 8000"
	@echo "  make run-frontend   Start Streamlit frontend on port 8501"
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
	pip install --upgrade pip
	pip install -r requirements.txt

install-frontend: venv ## Install frontend dependencies
	@echo "Installing frontend dependencies..."
	pip install -r frontend/requirements.txt

setup: install install-frontend ## Full setup: create venv and install all dependencies
	@echo "Setup complete."
	@echo ""
	@echo "Next steps:"
	@echo "  1. Copy .env.example to .env and add your LLM API keys"
	@echo "  2. Run: make run-backend (in one terminal)"
	@echo "  3. Run: make run-frontend (in another terminal)"
	@echo "  4. Open http://localhost:8501"

run-backend: ## Start FastAPI backend on port 8000
	@echo "Starting FastAPI backend on http://localhost:8000"
	uvicorn app.main:app --reload --port 8000

run-frontend: ## Start Streamlit frontend on port 8501
	@echo "Starting Streamlit frontend on http://localhost:8501"
	streamlit run frontend/app.py --server.port 8501

test: venv ## Run unit tests
	@echo "Running unit tests..."
	pip install pytest 2>/dev/null
	python -m pytest tests/ -v

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
