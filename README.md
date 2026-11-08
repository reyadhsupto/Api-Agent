# Api-Agent

AI assisted solution to generate and execute API test cases from cURL commands and business requirements.

## Tech Stack
- Backend: Python + FastAPI
- HTTP Client: python requests
- Frontend: Streamlit
- LLM: Multiple free-tier providers with automatic fallback (Groq, OpenRouter, Cohere, HuggingFace)
- Storage: PostgreSQL (local service or Docker Compose)

## Getting Started

### Prerequisites
- Python 3.11+
- Docker Desktop / Docker Compose (for PostgreSQL and container runs)
- Free tier API keys for at least one of: Groq, OpenRouter, Cohere, HuggingFace

### Installation
```bash
cd Api-Agent
make setup
cp .env.example .env
# Edit .env and replace at least one placeholder API key
```

`make setup` installs dependencies into `.venv`. In VS Code, the workspace selects `.venv/bin/python`; if Pylance still shows missing imports after setup, reload the Python language server or reselect that interpreter.

### Configure `.env`

Open `.env` and set at least one LLM provider API key. Set a local PostgreSQL URL and credentials as shown below. Compose overrides the database hostname for its backend service.

```dotenv
GROQ_API_KEY=your_groq_api_key
OPENROUTER_API_KEY=your_openrouter_api_key
OPENROUTER_MODEL=nvidia/nemotron-3-ultra-550b-a55b:free
COHERE_API_KEY=your_cohere_api_key
HUGGINGFACE_API_KEY=your_huggingface_api_key
DATABASE_URL=postgresql://api_agent:change_this_local_password@localhost:5432/api_agent
POSTGRES_DB=api_agent
POSTGRES_USER=api_agent
POSTGRES_PASSWORD=change_this_local_password
API_AGENT_LLM_MAX_OUTPUT_TOKENS=6000
```

You only need to configure the provider or providers you plan to use; leave other values blank or remove those lines. `OPENROUTER_MODEL` is optional. Save `.env` in the repository root, beside `.env.example`. It is excluded by `.gitignore`, so do not commit or share it because it contains secrets.

### Run locally

Start the PostgreSQL container, then run the backend and frontend in separate terminals:

```bash
make docker-db-up
# Terminal 1
make run-local-backend

# Terminal 2
make run-local-frontend
```

### Run the full stack in Docker

```bash
make docker-up
make docker-logs
make docker-down
```

The app is available at http://localhost:8501 and the backend at http://localhost:8000. Services bind to localhost. PostgreSQL data remains in the `api_agent_pgdata` Docker volume when services stop. `make docker-down` keeps that volume; `docker compose down -v` removes it.

If a default port is already in use, set `POSTGRES_PORT`, `BACKEND_PORT`, or `FRONTEND_PORT` in `.env` to an available host port. When changing `POSTGRES_PORT` for a local app run, update the port in `DATABASE_URL` to match.

### Makefile Commands

| Command | Description |
|---------|-------------|
| `make setup` | Create venv and install all dependencies |
| `make run-local-backend` | Start FastAPI backend locally on port 8000 |
| `make run-local-frontend` | Start Streamlit frontend locally on port 8501 |
| `make docker-db-up` | Start only PostgreSQL for local application processes |
| `make docker-up` | Build and start PostgreSQL, backend, and frontend |
| `make docker-down` | Stop Compose services and preserve data volume |
| `make docker-logs` | Follow service logs |
| `make test` | Run unit tests |
| `make clean-cache` | Clean cache files only (keeps venv) |

Run `make docker-db-up` before `make test`; persistence tests use PostgreSQL.

## Project Structure
```
app/
  main.py          # FastAPI app and API routes
  storage.py       # PostgreSQL persistence for projects and test data
  parser.py        # cURL parsing
  generator.py     # LLM test case generation with fallback
  executor.py      # Test execution using python requests
  schemas.py       # Pydantic models
frontend/
  app.py           # Streamlit UI (API Workspace and Test Cases)
tests/
  test_parser.py   # Unit tests for cURL parser
  test_executor.py # Assertion execution tests
  test_frontend.py # Frontend payload-shape tests
  test_storage.py  # PostgreSQL persistence and API tests
```

## Features

- **cURL Parsing**: Paste single-line or multiline cURL into the request URL field; recognized commands auto-parse after one second of inactivity
- **Editable Request Components**: Modify method, URL, enabled query/header rows, and payload after parsing
- **Request Playground Assertions**: Configure repeatable status, body text, JSONPath field value, and JSON Schema checks; run enabled checks together or run one check against a fresh response
- **Unified API Workspace**: Temporary request tabs, manual composition, and cURL parsing in the URL field
- **Contract Import**: Review and import all endpoints from OpenAPI 3.x, Swagger 2.0, Postman Collection 2.1, pasted docs, Markdown files, or public documentation URLs
- **Saved Collections**: Project-scoped request collections with ordered requests, Postman v2.1 import, and export
- **Contract Flow Discovery**: Build dependency edges from matching OpenAPI response fields and downstream path/body fields; generate editable named flows from selected dependency paths
- **Generation Selection**: Choose requests and drag-reorder all eligible requests in one list showing each name, URL, and method; selected requests run in saved project order
- **AI Test Case Generation**: Generates endpoint cases and concise, complete flow scenarios; canonical request data is attached server-side to keep model output compact
- **Per-Test-Case Assertions**: Repeatable status, body contains, JSONPath field-value, and JSON Schema checks with enable/disable controls; schema assertions start disabled and editable on generated tests and flow steps
- **Execution Workspace**: Filter by pass/fail/error/not-run, select cases for batch runs, and track run progress
- **Collapsible Test Case Cards**: Expand/retract each test case for better visibility
- **Grouped Test Cases**: Single tests appear under their source endpoint while retaining their own titles; flow scenarios have a separate group
- **Unified Test Case Cards**: Test cases share compact status cards with separate assertion, request, and response views; flow steps show per-step results
- **Persistent Projects**: Projects, endpoints, test cases, and execution history are stored in PostgreSQL
- **Compact Sidebar**: Sidebar starts collapsed and project names are shown with unique short IDs
- **Readable Request/Response Results**: Side-by-side request and response details, status, latency, payload size, headers, and pretty/raw JSON views
- **Console Logging**: API calls logged to browser DevTools via st.iframe
- **5-Minute Timeout**: Frontend waits up to 5 minutes for LLM generation
- **Quick API Checks**: Send temporary requests and inspect response status, time, headers, and body

Prose documentation endpoint extraction uses the configured LLM providers and displays the source excerpt for review. During import review, each request's method, headers, query parameters, and payload can be edited. GET and DELETE requests are always imported without payloads. Anonymous URL imports are limited to public HTTP(S) hosts and documents up to 5 MB. Requests imported from contracts are excluded from test generation until enabled. OpenAPI response-to-request dependency discovery is limited to matching path and JSON body properties; generic `id` fields are ignored.

## Project Rules
See `agent_rules.md` for coding standards, documentation requirements, and UI/UX guidelines.

## API Endpoints

The backend exposes these routes:

- **Health and request tools**: `GET /health`, `POST /api/v1/curl/parse`, `POST /api/v1/http/send`, `POST /api/v1/http/execute-assertions`
- **Contract import and flow discovery**: `POST /api/v1/contracts/preview`, `POST /api/v1/projects/{project_id}/contracts/import`, `POST /api/v1/projects/{project_id}/contracts/flow-candidates`, `POST /api/v1/projects/{project_id}/contracts/generate-flows`
- **Projects**: `POST /api/v1/projects`, `GET /api/v1/projects`, `GET /api/v1/projects/current`, `GET /api/v1/projects/{project_id}`, `PUT /api/v1/projects/{project_id}`, `DELETE /api/v1/projects/{project_id}`, `PUT /api/v1/projects/{project_id}/generation-order`
- **Collections and saved requests**: `GET|POST /api/v1/projects/{project_id}/collections`, `PUT|DELETE /api/v1/projects/{project_id}/collections/{collection_id}`, `POST /api/v1/projects/{project_id}/collections/{collection_id}/requests`, `PUT|DELETE /api/v1/projects/{project_id}/collections/{collection_id}/requests/{request_id}`, `GET /api/v1/projects/{project_id}/collections/{collection_id}/export`
- **Legacy endpoints**: `POST|PUT /api/v1/projects/{project_id}/endpoints`, `PUT|DELETE /api/v1/projects/{project_id}/endpoints/{endpoint_id}`
- **Test cases**: `POST /api/v1/test-cases/generate`, `POST /api/v1/test-cases/generate-flow`, `POST /api/v1/projects/{project_id}/test-cases/generate-flow`, `POST /api/v1/projects/{project_id}/test-cases/save`, `GET|DELETE /api/v1/projects/{project_id}/test-cases`, `DELETE|PUT /api/v1/projects/{project_id}/test-cases/{test_case_id}`, `POST /api/v1/test-cases/execute`
- **Application state**: `GET /api/v1/memory/state`

## Data Storage

PostgreSQL is initialized automatically at backend startup. Local app processes use `DATABASE_URL` from `.env` (default host `localhost`); the Compose backend connects to the `postgres` service. Projects, collections, saved requests, test cases, and execution history persist in PostgreSQL. Request playground assertions are stored with saved requests; generated test and flow-step assertions are stored with their test cases. Open request tabs and responses remain session drafts. Existing endpoint records are migrated once into each project's **Imported Endpoints** collection, preserving IDs, request fields, enabled fields, order, and generation eligibility. Legacy endpoint routes continue to operate on that collection. There is no automatic migration of old SQLite data.

New requests are excluded from generation by default. Enable eligible requests in API Workspace. In Test Cases, use the combined selection and ordering list to choose requests for a run; all eligible requests are draggable and checked requests execute in the saved project order. The project order is restored after reloads and remains independent of collection request order. Saved-request rows show method, name, and open/delete actions without URLs. Query/header row toggles and payload inclusion control what is sent; they are separate from generation eligibility. Export any collection as Postman Collection v2.1 JSON. Contract import supports Postman Collection v2.1; Postman environments, scripts, and auth configuration are not imported.

The home header summarizes the current project. The collapsed sidebar contains project selection, project actions, counts, and saved test-case fetch. API Workspace manages collections and persistent generation eligibility. Test Cases owns the single per-run selection and ordering panel. Project summaries and collection exports are cached briefly and refreshed after relevant writes.

Flow generation does not request a fixed scenario count. The prompt asks for a small set of complete scenarios and returns endpoint references instead of repeating full request headers and payloads; the backend attaches saved request data to each step. This reduces output truncation, while `API_AGENT_LLM_MAX_OUTPUT_TOKENS` still sets a shared ceiling for providers that support it. Malformed or truncated JSON is reported as an error rather than displayed as partial results.

For imported OpenAPI/Swagger operations, contract metadata is stored inside saved-request JSON so dependency discovery remains available after reload without a database migration. Candidate flows are maximal acyclic dependency paths ranked by dependency-edge count, then method and path. Cyclic edges remain visible as evidence and are omitted from executable candidates.
