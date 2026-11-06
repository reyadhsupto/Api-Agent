# Technical Documentation - Api-Agent

## 1. Tech Stack
| Layer | Technology | Reason |
|-------|-----------|--------|
| Backend Language | Python 3.11+ | Project convention, rich AI/HTTP ecosystem |
| Backend Framework | FastAPI | Async support, automatic OpenAPI docs, easy routing |
| HTTP Client | python requests | User-specified standard for outbound API calls |
| Frontend | Streamlit | Pure Python, single-process deployment, no Node.js |
| LLM Providers | Groq, OpenRouter, Cohere, HuggingFace | Free tiers, multiple for fallback |
| cURL Parsing | shlex + custom logic | No heavy dependency, easy to understand |
| Persistence | PostgreSQL + psycopg | Durable storage for local and containerized app runs |
| Testing | pytest | Unit tests |

## 2. Architecture
```
Streamlit UI (port 8501) <--> FastAPI Backend (port 8000) <--> Target API
                                               |
                                               v
                                        LLM Providers (fallback chain)
PostgreSQL (port 5432) <--> FastAPI Backend
```

## 3. Module Responsibilities

### app/main.py
- FastAPI application instance and CORS middleware
- API routes for projects, endpoints, generation, and execution
- Delegates durable reads and writes to the PostgreSQL repository

### app/storage.py
- PostgreSQL schema initialization and data access through psycopg
- Projects, collections, saved requests, JSON test-case payloads, execution history, and active project state
- Foreign-key cascades and transactional collection updates

### app/parser.py
- parse_curl(curl_string) -> dict with method, URL, headers, query parameters, and body

### app/generator.py
- generate_test_cases(parsed_curl, business_requirements) -> list of dicts
- LLM fallback logic inside this module

### app/executor.py
- execute_test_case(test_case, base_url) -> dict with request/response/latency/assertion
- Uses python requests

### app/schemas.py
- Minimal Pydantic models for request/response validation

### frontend/app.py
- Streamlit app with API Workspace and Test Cases tabs plus collapsed-by-default project sidebar
- API Workspace provides temporary request tabs, manual and cURL editing, quick sends, response display, and saved project collections
- Saved requests can be selected and explicitly ordered for generation
- Test Cases supports single and flow generation/execution with editable assertions
- Generation controls use a Single/Flow selector, selected saved-request list, optional business requirements, and a primary generation action; no scenario count is requested for flows
- Results use status counts, result filters, select/expand controls, per-case execution, batch execution with progress, and explicit project save
- Each test case card: compact status summary, repeatable status/body-contains/JSONPath assertions, separate request/result views for single cases, and expandable per-step flow details
- Request/response results show method and URL, headers, readable payloads, response status, latency, payload size, and pretty/raw JSON selection
- Calls FastAPI endpoints via python requests
- Logs all API requests/responses to browser devtools console via st.iframe console.log
- Collections and saved requests persist in PostgreSQL; request drafts and quick-send responses remain in session state
- Flow scenario cards: consistent scenario cards containing ordered step cards with editable assertions, mappings, and per-step results
- Sidebar starts collapsed and shows unique project labels even when names match

## 4. API Endpoints

### GET /health
Returns {"status": "ok"}.

### POST /api/v1/curl/parse
Body: {"curl": "..."}
Returns parsed request components (method, url, headers, body).
Frontend allows user to edit these components before generating test cases.

### POST /api/v1/test-cases/generate
Body: {"parsed_curl": {...}, "business_requirements": "...", "project_id": "..."}
Returns list of test cases. Accepts the (optionally edited) parsed_curl from the frontend.
Prompt instructs LLM to generate as many test cases as possible (positive, negative, edge, race).

### POST /api/v1/test-cases/generate-flow
Body: {"endpoints": [...], "business_requirements": "...", "project_id": "..."}
Generates as many complete flow scenarios as the model can return within the provider output limit. The legacy `scenario_count` field is accepted but ignored. Malformed or truncated output is returned as a clear generation error. The scenarios cover:
- Full flow (all steps succeed in sequence)
- Step failure (one step fails, subsequent steps handle it)
- Data dependency (field mapping between steps using variable mappings)
- Edge cases (null/empty values propagated between steps)
- Race-oriented scenarios may be requested, but the current executor runs each scenario's steps sequentially and does not issue concurrent requests.
Each flow scenario contains: id, type, name, description, steps (ordered list with endpoint_id, assertions, variable_mappings), is_flow flag.

### POST /api/v1/projects/{project_id}/test-cases/generate-flow
Body: {"endpoints": [...], "business_requirements": "..."}
Same as above but saves to project scope.

### POST /api/v1/test-cases/execute
Body: {"test_case_id": "...", "assertions": {"status": [...], "body_contains": [...], "jsonpath": [...]}}
Executes a single test case or flow test case.
- For single test cases: executes one HTTP request with assertions.
- For flow test cases (is_flow: true): executes all steps sequentially, applying variable mappings from previous step responses to subsequent requests.
Returns execution result with assertion detail including per-step results for flows.

### POST /api/v1/http/send
Accepts method, absolute URL, headers, query parameters, and optional body. Returns HTTP status, elapsed milliseconds, response headers, response body, and final URL. Ad hoc requests are not persisted.

### Projects, collections, and saved requests
- `POST/GET /api/v1/projects` and `GET/PUT/DELETE /api/v1/projects/{project_id}` manage projects.
- `GET/POST /api/v1/projects/{project_id}/collections` and `PUT/DELETE /api/v1/projects/{project_id}/collections/{collection_id}` manage collections.
- `POST /api/v1/projects/{project_id}/collections/{collection_id}/requests`, `PUT/DELETE .../requests/{request_id}` manage saved requests.
- `GET /api/v1/projects/{project_id}/collections/{collection_id}/export` exports a Postman Collection v2.1 document.
- Legacy `/api/v1/projects/{project_id}/endpoints` routes remain available over the Imported Endpoints collection.

## 5. API Workspace and Collections
The API Workspace combines request editing, quick sending, and saved request management. Each open tab is a temporary session draft with independent method, URL, query rows, header rows, payload, and response. Its request line groups Method, URL, cURL import, and Send; the editor uses Params, Headers, and Body tabs. Params and headers use editable key/value/description tables with per-row send toggles. cURL parsing fills the active editor; query values are moved out of the URL into query rows to avoid duplication. Body supports none/raw modes and JSON formatting. The response panel displays status, elapsed time, headers, and body, with a control to format valid JSON.

Saved requests live in ordered, named collections scoped to a project. New requests default to excluded from generation. A separate per-request eligibility setting controls generation, and the selection panel supports drag-and-drop ordering for flow generation. Drafts cannot be selected until saved. Stable IDs distinguish collections and requests even when names match.

Postman Collection v2.1 export includes methods, URLs, payloads, and disabled query/header rows. Import and environment management are out of scope. Legacy endpoint routes map to Imported Endpoints. Existing endpoint rows migrate once at startup, retaining IDs, request fields, enabled state, inclusion choice, and order.

## 6. Project Management
Projects, collections, saved requests, test cases, and execution history are stored in PostgreSQL. Nested flow steps, assertions, and request fields remain JSON payloads so API shapes stay compatible.
- Create project with name and description
- Select existing project from sidebar
- Delete project (cascades to collections, requests, and test data)
- Create, rename, delete, and export collections; create, update, and delete saved requests
- Fetch last generated test cases and assertions from project
- Save or update test cases by stable test-case ID without creating duplicates
- Delete a project and its dependent rows through foreign-key cascades

Set `DATABASE_URL` in `.env` for local app processes. Docker Compose connects the backend to the `postgres` service and persists data in the named `api_agent_pgdata` volume. A default project is created automatically and receives standalone generated tests. The selected project is persisted and restored after restart. Collection/request changes and assertion edits are saved explicitly; generated cases and execution results are saved automatically. Existing SQLite files are not migrated automatically.

## 7. Flow Test Cases
Generate test cases for a sequence of endpoints. LLM creates flow test cases covering:
- Full flow (all steps succeed)
- Step failure (one step fails)
- Data dependency (field mapping between steps)
- Edge cases (null/empty propagated)
- Race-oriented scenarios may be requested, but the current executor runs each scenario's steps sequentially and does not issue concurrent requests.

### Flow Scenario Data Model
The model determines the number of scenarios from the available output limit; the API does not impose a requested count. Each flow scenario contains:
- **id**: unique string (e.g., "flow_1")
- **name**: descriptive scenario name
- **type**: positive | negative | edge | race
- **description**: what this flow validates
- **steps**: ordered list of flow step objects

The UI renders each step as an editable test-case card. Assertions are edited per step and saved with the scenario; execution remains sequential at the scenario level so variable mappings can use earlier responses. Results show the scenario outcome and individual step status, assertion details, latency, and response.

Each flow step contains:
- **step_order**: integer (1-based)
- **endpoint_id**: reference to endpoint in collection
- **endpoint**: full endpoint dict (method, url, headers, body)
- **assertions**: per-step assertion config (status, body_contains, jsonpath; each accepts one config or a list)
- **variable_mappings**: list of {from, to, transform} for passing response fields to next request

### Assertion Configuration

Each assertion type is stored as a list so a test case can contain multiple checks:

```json
{
  "status": [{"enabled": true, "expected_status": 200}],
  "body_contains": [{"enabled": true, "value": "success"}],
  "jsonpath": [{"enabled": true, "path": "$.token", "expected_value": "abc"}]
}
```

The executor evaluates every enabled instance with AND semantics. Legacy single-dictionary assertion values are normalized to one-item lists, so existing generated and saved test cases remain compatible. The Streamlit editor supports adding and removing instances for each assertion type.

### Flow Execution Logic
Flow execution runs all steps sequentially:
1. Apply variable mappings from previous step responses to current request
2. Send HTTP request for current step
3. Capture response (status, headers, body)
4. Evaluate step assertions
5. If step fails and scenario requires all steps to pass, mark flow as failed
6. Aggregate results: pass if all enabled assertions pass across all steps


## 8. LLM Fallback Strategy
Provider order (configurable via env):
1. Groq (free tier) — dynamically selects the model with the largest context window from `/v1/models`
2. OpenRouter (free tier) — uses model from `OPENROUTER_MODEL` env var (default: `nvidia/nemotron-3-ultra-550b-a55b:free`)
3. Cohere (free tier)
4. HuggingFace (free tier)

Simple function tries providers in order. On 429 or error, moves to next. If all fail, returns error.

Generated test-case output is validated before storage. Malformed JSON or malformed flow steps are rejected with an HTTP 502 error explaining the invalid field; the system does not create synthetic fallback test cases.

### Groq Dynamic Model Selection
Before calling the chat completion API, the system calls `GET /v1/models` to list available models, then selects the one with the largest `context_window` (currently `llama-3.1-8b-instant` with 131072 tokens).

### OpenRouter Configuration
Set `OPENROUTER_API_KEY` in `.env` and optionally `OPENROUTER_MODEL` to choose a specific model. OpenRouter provides access to many free models from various providers.

## 9. Deployment
- Local: `make docker-db-up`, then `make run-local-backend` and `make run-local-frontend` in separate terminals
- Docker: `make docker-up`, `make docker-logs`, and `make docker-down`
- FastAPI local: `uvicorn app.main:app --reload` on port 8000
- Streamlit local: `streamlit run frontend/app.py` on port 8501
- Single user, local only, no auth
- Frontend API timeout: 300 seconds (5 minutes) for LLM generation
- PostgreSQL URL: `DATABASE_URL` in `.env`; Compose volume: `api_agent_pgdata`
- Flow scenario quantity is model-determined; provider output ceiling uses `API_AGENT_LLM_MAX_OUTPUT_TOKENS`
- Unsaved API Workspace requests and quick-send responses stay in Streamlit session state only
- Clean caches: `make clean-cache` (keeps the virtual environment)
