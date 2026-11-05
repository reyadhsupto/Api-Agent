# Api-Agent

AI assisted solution to generate and execute API test cases from cURL commands and business requirements.

## Tech Stack
- Backend: Python + FastAPI
- HTTP Client: python requests
- Frontend: Streamlit
- LLM: Multiple free-tier providers with automatic fallback (Groq, OpenRouter, Cohere, HuggingFace)
- Storage: SQLite database in `.data/api_agent.sqlite3`

## Getting Started

### Prerequisites
- Python 3.11+
- Free tier API keys for at least one of: Groq, OpenRouter, Cohere, HuggingFace

### Installation
```bash
cd Api-Agent
make setup
cp .env.example .env
# Edit .env and replace at least one placeholder API key
```

### Configure `.env`

Open the `.env` file created above and replace the placeholder value for at least one LLM provider with your API key. The app tries configured providers in sequence, so you can add more than one key for fallback.

```dotenv
GROQ_API_KEY=your_groq_api_key
OPENROUTER_API_KEY=your_openrouter_api_key
OPENROUTER_MODEL=nvidia/nemotron-3-ultra-550b-a55b:free
COHERE_API_KEY=your_cohere_api_key
HUGGINGFACE_API_KEY=your_huggingface_api_key
```

You only need to configure the provider or providers you plan to use; leave other values blank or remove those lines. `OPENROUTER_MODEL` is optional. Save `.env` in the repository root, beside `.env.example`. It is excluded by `.gitignore`, so do not commit or share it because it contains secrets.

### Running the Application
```bash
# Terminal 1 - Backend
make run-backend

# Terminal 2 - Frontend
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

## Project Structure
```
app/
  main.py          # FastAPI app and API routes
  storage.py       # SQLite persistence for projects and test data
  parser.py        # cURL parsing
  generator.py     # LLM test case generation with fallback
  executor.py      # Test execution using python requests
  schemas.py       # Pydantic models
frontend/
  app.py           # Streamlit UI (2 tabs: Endpoints + Test Cases)
tests/
  test_parser.py   # Unit tests for cURL parser
  test_executor.py # Assertion execution tests
  test_frontend.py # Frontend payload-shape tests
  test_storage.py  # SQLite persistence and API tests
```

## Features

- **cURL Parsing**: Paste any cURL command to parse method, URL, headers, body
- **Editable Request Components**: Modify method, URL, headers, query params, path params, body after parsing
- **Multi-Endpoint Support**: Add multiple endpoints, toggle include/exclude for test generation
- **AI Test Case Generation**: Generates 6+ test cases (positive, negative, edge, race) using free-tier LLMs
- **Per-Test-Case Assertions**: Status, Body Contains, Exact Field (JSONPath) with individual enable/disable checkboxes
- **Collapsible Test Case Cards**: Expand/retract each test case for better visibility
- **Unified Test Case Cards**: Single tests and flow scenarios share a card layout; flow steps have editable assertions and per-step results
- **Persistent Projects**: Projects, endpoints, test cases, and execution history are stored in SQLite
- **Compact Sidebar**: Sidebar starts collapsed and project names are shown with unique short IDs
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
- GET /api/v1/memory/state - Get persisted project selection state

## Data Storage

SQLite is provided by Python and requires no additional package. The application creates `.data/api_agent.sqlite3` on startup and creates a default project for standalone generation. The `.data/` directory is ignored by Git. Set `API_AGENT_DB_PATH` in the environment to store the database elsewhere.
