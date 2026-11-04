# Api-Agent

AI assisted solution to generate and execute API test cases from cURL commands and business requirements.

## Tech Stack
- Backend: Python + FastAPI
- HTTP Client: python requests
- Frontend: Streamlit
- LLM: Multiple free-tier providers with automatic fallback (Groq, OpenRouter, Cohere, HuggingFace)
- Storage: In-app memory (no database for MVP)

## Getting Started

### Prerequisites
- Python 3.11+
- Free tier API keys for at least one of: Groq, OpenRouter, Cohere, HuggingFace

### Installation
```bash
cd /Users/reyadhassan/Projects/apiAiTest/Api-Agent
make setup
cp .env.example .env
# Edit .env and add your API keys
```

### Running the Application
```bash
# Terminal 1 - Backend
source .venv/bin/activate
make run-backend

# Terminal 2 - Frontend
source .venv/bin/activate
make run-frontend
```

Open http://localhost:8501 in your browser.

### Makefile Commands

| Command | Description |
|---------|-------------|
| `make setup` | Create venv and install all dependencies |
| `make run-backend` | Start FastAPI backend on port 8000 |
| `make run-frontend` | Start Streamlit frontend on port 8501 |
| `make test` | Run unit tests |
| `make clean-cache` | Clean cache files only (keeps venv) |
| `make clean` | Remove venv and all cache files |

## Project Structure
```
app/
  main.py          # FastAPI app, routes, in-memory storage
  parser.py        # cURL parsing
  generator.py     # LLM test case generation with fallback
  executor.py      # Test execution using python requests
  schemas.py       # Pydantic models
frontend/
  app.py           # Streamlit UI (2 tabs: Endpoints + Test Cases)
tests/
  test_parser.py   # Unit tests for cURL parser
```

## Features

- **cURL Parsing**: Paste any cURL command to parse method, URL, headers, body
- **Editable Request Components**: Modify method, URL, headers, query params, path params, body after parsing
- **Multi-Endpoint Support**: Add multiple endpoints, toggle include/exclude for test generation
- **AI Test Case Generation**: Generates 6+ test cases (positive, negative, edge, race) using free-tier LLMs
- **Per-Test-Case Assertions**: Status, Body Contains, Exact Field (JSONPath) with individual enable/disable checkboxes
- **Collapsible Test Case Cards**: Expand/retract each test case for better visibility
- **Verbose Execution Results**: Full request/response details, latency, assertion evaluation
- **Console Logging**: API calls logged to browser DevTools via st.iframe
- **5-Minute Timeout**: Frontend waits up to 5 minutes for LLM generation

## Project Rules
See `agent_rules.md` for coding standards, documentation requirements, and UI/UX guidelines.

## API Endpoints
- GET /health - Health check
- POST /api/v1/curl/parse - Parse cURL command
- POST /api/v1/test-cases/generate - Generate AI test cases (accepts assertions)
- POST /api/v1/test-cases/execute - Execute a test case with assertions
- GET /api/v1/memory/state - Get in-memory state 
