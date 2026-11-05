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
| Persistence | Python sqlite3 | Local durable storage without an ORM dependency |
| Testing | pytest | Unit tests |

## 2. Architecture
```
Streamlit UI (port 8501) <--> FastAPI Backend (port 8000) <--> Target API
                                               |
                                               v
                                        LLM Providers (fallback chain)
```

## 3. Module Responsibilities

### app/main.py
- FastAPI application instance and CORS middleware
- API routes for projects, endpoints, generation, and execution
- Delegates durable reads and writes to the SQLite repository

### app/storage.py
- SQLite schema initialization and data access
- Projects, ordered endpoints, JSON test-case payloads, execution history, and active project state
- Foreign-key cascades and transactional collection updates

### app/parser.py
- parse_curl(curl_string) -> dict with method, url, headers, body

### app/generator.py
- generate_test_cases(parsed_curl, business_requirements) -> list of dicts
- LLM fallback logic inside this module

### app/executor.py
- execute_test_case(test_case, base_url) -> dict with request/response/latency/assertion
- Uses python requests

### app/schemas.py
- Minimal Pydantic models for request/response validation

### frontend/app.py
- Streamlit app with 2 tabs + sidebar project management
- Tab 1: Endpoints - Parse cURL, add/edit multiple endpoints with include/exclude checkbox, method, url, headers, query params, path params, body, name, reorder (Up/Down buttons), collapsible cards
- Tab 2: Test Cases - generate (single or flow) and execute merged with per-test-case cards
- Each test case card: visual separation, assertion editor (enable/disable checkbox, expected status, body assertion type: Body Contains or Exact Field JSONPath, expected value input), execute button, verbose request/response results
- Calls FastAPI endpoints via python requests
- Logs all API requests/responses to browser devtools console via st.iframe console.log
- Endpoints stored as list in session state with reorder support
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
Generates flow test cases for a sequence of endpoints. LLM creates flow scenarios covering:
- Full flow (all steps succeed in sequence)
- Step failure (one step fails, subsequent steps handle it)
- Data dependency (field mapping between steps using variable mappings)
- Edge cases (null/empty values propagated between steps)
- Race conditions (concurrent flow executions)
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

## 5. Multi-Endpoint Support
Endpoints are stored as a list in Streamlit session state. Each endpoint has a unique ID and can be independently configured and selected for test case generation. This lays the groundwork for future flow/sequence mapping between endpoints.

## 6. Project Management
Projects, endpoints, test cases, and execution history are stored in SQLite. Nested flow steps and assertion configuration remain JSON payloads so API response shapes stay compatible.
- Create project with name and description
- Select existing project from sidebar
- Delete project (cascades to endpoints and test cases)
- Replace and save the current endpoint collection by stable endpoint ID
- Fetch last generated test cases and assertions from project
- Save or update test cases by stable test-case ID without creating duplicates
- Delete a project and its dependent rows through foreign-key cascades

The database defaults to `.data/api_agent.sqlite3` under the repository. Set `API_AGENT_DB_PATH` to override the location. A default project is created automatically and receives standalone generated tests. The selected project is persisted and restored after restart. Endpoint edits and assertion edits are persisted through the explicit save actions; generated cases and execution results are saved automatically.

## 7. Flow Test Cases
Generate test cases for a sequence of endpoints. LLM creates flow test cases covering:
- Full flow (all steps succeed)
- Step failure (one step fails)
- Data dependency (field mapping between steps)
- Edge cases (null/empty propagated)
- Race conditions (concurrent flow executions)

### Flow Scenario Data Model
Each flow scenario contains:
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
- Run FastAPI on port 8000: uvicorn app.main:app --reload
- Run Streamlit on port 8501: streamlit run frontend/app.py
- Single user, local only, no auth
- Frontend API timeout: 300 seconds (5 minutes) for LLM generation
- Local database: `.data/api_agent.sqlite3` by default; `API_AGENT_DB_PATH` overrides the path
- Clean caches: make clean-cache (keeps venv), make clean (removes venv + caches)
