# Technical Documentation - Api-Agent

## 1. Tech Stack
| Layer | Technology | Reason |
|-------|-----------|--------|
| Backend Language | Python 3.11+ | Project convention, rich AI/HTTP ecosystem |
| Backend Framework | FastAPI | Async support, automatic OpenAPI docs, easy routing |
| HTTP Client | python requests | User-specified standard for outbound API calls |
| Frontend | Streamlit + embedded Components v2 | Python UI with browser controls for cURL debounce and sortable request rows |
| LLM Providers | Groq, OpenRouter, Cohere, HuggingFace | Free tiers, multiple for fallback |
| cURL Parsing | shlex + custom logic | No heavy dependency, easy to understand |
| Contract Parsing | PyYAML + standard JSON parsing | OpenAPI/Swagger YAML and JSON input |
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
- Projects, collections, saved requests, JSON test-case payloads, named test-run selections, execution history, and active project state
- Foreign-key cascades and transactional collection updates

### app/parser.py
- parse_curl(curl_string) -> dict with method, URL, headers, query parameters, and body

### app/contracts.py
- Parses OpenAPI 3.x, Swagger 2.0, Postman Collection 2.1, and public/pasted documentation inputs
- Stores operation fields and source provenance on saved request JSON and derives normalized dependency edges and maximal candidate paths

### app/generator.py
- generate_test_cases(parsed_curl, business_requirements, example_test_cases) -> list of dicts
- generate_flow_test_cases(endpoints, business_requirements, example_test_cases) -> list of flow dicts
- LLM fallback logic inside this module

### app/executor.py
- execute_test_case(test_case, base_url) -> dict with request/response/latency/assertion
- Uses python requests

### app/schemas.py
- Minimal Pydantic models for request/response validation

### frontend/app.py
- Streamlit app with API Workspace and Test Cases tabs plus collapsed-by-default project sidebar
- API Workspace provides temporary request tabs, manual editing, debounced cURL parsing in the URL field, quick sends, response display, and saved project collections
- Single generated tests retain source endpoint metadata and display in endpoint groups; flow scenarios have a separate group
- Saved requests can be selected and explicitly ordered for generation
- Test Cases supports single and flow generation/execution with editable assertions
- Generation controls use a Single/Flow selector, selected saved-request list, optional business requirements, and a primary generation action; no scenario count is requested for flows
- Results use status counts, result filters, select/expand controls, per-case execution, batch execution with progress, and explicit project save
- Each test case card: compact status summary, repeatable status/body-contains/JSONPath/JSON Schema assertions, separate request/result views for single cases, and expandable per-step flow details
- Request/response results show method and URL, headers, readable payloads, response status, latency, payload size, and pretty/raw JSON selection
- Calls FastAPI endpoints via python requests
- Queues five-second success and error toasts for meaningful completed actions; success and error messages use green and red accents, queued messages survive Streamlit reruns, and batch execution reports one aggregate toast
- Running a single test opens its Result tab; running a flow opens its Scenario result tab. Batch execution opens the first failed or errored case, or the last executed case when all pass
- Contract import UI accepts pasted text, JSON/YAML/Markdown/text files, and public anonymous documentation URLs; previews all endpoint proposals before import
- Contract flow UI displays schema-field evidence and lets users select candidate paths before LLM flow generation
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
Body: {"parsed_curl": {...}, "business_requirements": "...", "project_id": "...", "source_endpoint_id": "...", "example_test_case_ids": ["..."]}
Returns list of test cases. Accepts the (optionally edited) parsed_curl from the frontend.
`example_test_case_ids` is optional. Selected cases are loaded from the project and used as scenario-style and coverage context; the endpoint request and business requirements remain the generation target. The cases are not copied or modified. Generated cases receive new IDs and are saved alongside the existing cases.

### POST /api/v1/test-cases/generate-flow
Body: {"endpoints": [...], "business_requirements": "...", "project_id": "...", "example_test_case_ids": ["..."]}
Generates a small set of concise flow scenarios, prioritizing complete output over volume. The model returns endpoint IDs and step details rather than repeating full endpoint definitions; the backend attaches canonical request data before validation and persistence. Prompt context includes parameter names and body shape, not header values, query values, or body values. The legacy `scenario_count` field is accepted but ignored. Malformed or truncated output is returned as a clear generation error. The scenarios cover:
- Full flow (all steps succeed in sequence)
- Step failure (one step fails, subsequent steps handle it)
- Data dependency (field mapping between steps using variable mappings)
- Edge cases (null/empty values propagated between steps)
- Race-oriented scenarios may be requested, but the current executor runs each scenario's steps sequentially and does not issue concurrent requests.
Each flow scenario contains: id, type, name, description, steps (ordered list with endpoint_id, assertions, variable_mappings), is_flow flag.

### POST /api/v1/projects/{project_id}/test-cases/generate-flow
Body: {"endpoints": [...], "business_requirements": "...", "example_test_case_ids": ["..."]}
Same as above but saves to project scope.

### POST /api/v1/test-cases/execute
Body: {"test_case_id": "...", "assertions": {"status": [...], "body_contains": [...], "jsonpath": [...]}}
Executes a single test case or flow test case.
- For single test cases: executes one HTTP request with assertions.
- For flow test cases (is_flow: true): executes all steps sequentially, applying variable mappings from previous step responses to subsequent requests.
Returns execution result with assertion detail including per-step results for flows.

### POST /api/v1/http/send
Accepts method, absolute URL, headers, query parameters, and optional body. Returns HTTP status, elapsed milliseconds, response headers, response body, and final URL. Ad hoc requests are not persisted.

### POST /api/v1/http/execute-assertions
Accepts `{"request": {"method": "GET", "url": "https://..."}, "assertions": [{"id": "...", "type": "status", "expected_status": 200}]}`. Sends one request and evaluates each assertion against that response. Supported types are `status`, `body_contains`, `jsonpath`, and `response_schema`; results include each assertion ID, type, pass/fail, detail, and aggregate `assertions_passed`. The frontend sends only enabled assertions for Run All, or one selected assertion for an individual run.

### POST /api/v1/contracts/preview
Accepts `source_type` (`text` or `url`), source `content`, optional `source_name`, `format_hint`, and `base_url`. Returns every parsed or LLM-proposed endpoint, source excerpt, contract metadata, dependency evidence, candidate flows, and whether a base URL is required. Structured inputs are OpenAPI 3.x, Swagger 2.0, and Postman Collection 2.1. Public URL fetches are anonymous, restricted to public HTTP(S) hosts, and limited to 5 MB.

### POST /api/v1/projects/{project_id}/contracts/import
Accepts a destination `collection_id` and reviewed `endpoints`. Persists the endpoint batch atomically, keeps generation eligibility disabled, and returns imported requests plus dependency evidence and candidate paths.

### POST /api/v1/projects/{project_id}/contracts/flow-candidates
Accepts `source_id` and rebuilds the dependency graph from saved operation metadata. Edges use normalized exact names between successful response fields and downstream path/body fields; generic `id` matches are ignored. Candidate paths are maximal source-to-leaf paths over non-cyclic edges, ranked by dependency count descending, then method and path ascending.

### POST /api/v1/projects/{project_id}/contracts/generate-flows
Accepts `source_id`, selected `candidate_ids`, and optional `business_requirements`. The LLM returns named flow test cases with ordered endpoint IDs, step assertions, and evidence-backed mappings. The backend attaches persisted requests, rejects endpoint sequences that do not match selected candidates, filters unsupported mappings, and saves the generated cases to the project.

### Project test runs
- `GET /api/v1/projects/{project_id}/test-runs` lists reusable run definitions.
- `POST /api/v1/projects/{project_id}/test-runs` creates a run from `{"name": "Smoke", "case_ids": ["tc_1"]}`.
- `PUT /api/v1/projects/{project_id}/test-runs/{run_id}` replaces its name and ordered case membership; names are unique without case sensitivity within a project.
- `DELETE /api/v1/projects/{project_id}/test-runs/{run_id}` removes the definition only.

Run membership is an ordered list of stable test-case IDs. Saving validates that every case belongs to the project. A run is a reusable selection, not an execution-history container. When a loaded run executes, the UI fetches current persisted cases by ID, so it uses each case's latest saved payload. Deleted cases are omitted from execution and are pruned from the definition the next time it is saved.

### Projects, collections, and saved requests
- `POST/GET /api/v1/projects` and `GET/PUT/DELETE /api/v1/projects/{project_id}` manage projects.
- `GET/POST /api/v1/projects/{project_id}/collections` and `PUT/DELETE /api/v1/projects/{project_id}/collections/{collection_id}` manage collections.
- `POST /api/v1/projects/{project_id}/collections/{collection_id}/requests`, `PUT/DELETE .../requests/{request_id}` manage saved requests.
- `GET /api/v1/projects/{project_id}/collections/{collection_id}/export` exports a Postman Collection v2.1 document.
- `PUT /api/v1/projects/{project_id}/generation-order` persists `{"request_ids": ["..."]}` for flow generation. IDs must be unique and belong to the project; the response returns canonical `generation_order_ids`.
- Legacy `/api/v1/projects/{project_id}/endpoints` routes remain available over the Imported Endpoints collection.

## 5. API Workspace and Collections
The API Workspace combines request editing, quick sending, and saved request management. Each open tab is a temporary session draft with independent method, URL, query rows, header rows, payload, assertions, and response. Its request line groups Method, a compact multiline-capable URL field, and Send. A URL input beginning with `curl` triggers parsing after three seconds without input; ordinary URLs are not parsed. The browser component synchronizes parsed URLs back into its state so subsequent sends and assertions use the parsed value. Query values are moved out of the URL into query rows to avoid duplication. The editor uses Params, Headers, Body, and Assertions tabs. Params and headers use editable key/value/description tables with per-row send toggles. Body supports none/raw modes and JSON formatting. Assertions support multiple status, body-contains, JSONPath field-value, and JSON Schema checks. Run All evaluates enabled assertions after one fresh request; each assertion also has an individual Run action that sends a fresh request even if that assertion is disabled for Run All. After a run, the response panel gives a pass/fail or response-ready notice and displays status, elapsed time, per-assertion outcomes, headers, and body, with a control to format valid JSON. On desktop, the playground stays sticky in the workspace while the document scrolls; the playground itself has no internal scroll area. On narrow screens it returns to normal document flow.

Saved requests live in named collections scoped to a project. The API Workspace uses a searchable collection tree beside the playground, headed by the active project name. The desktop navigator is constrained to a compact width; at narrow widths it stacks above the playground. Search matches collection names, request names, and URLs. Collection rows expand to show indented request rows connected to their collection by a subtle tree guide. Collection and request eligibility checkboxes sit at the left edge of their rows, with action menus at the right. Request names truncate to fit and expose the URL on hover and keyboard focus; selecting a name opens its request in a tab. Request rows have no separate disclosure control. Request and collection menus use plain, unboxed three-dot triggers; request actions support rename, duplicate, and delete, while collection actions support rename, Postman export, and delete. Collection creation is available from the plus action beside search. Delete actions require explicit confirmation. Duplicating a request copies its request fields and assertions into a new stable ID, appends “Copy” to its name, and leaves it excluded from generation by default. Icon-only menu triggers retain explicit accessible labels; hover help is omitted so it cannot linger over an opened popover.

New requests default to excluded from generation. Persistent eligibility is controlled by per-request and per-collection checkboxes. In Test Cases, one integrated draggable list shows every eligible request's name, URL, method, drag handle, and per-run checkbox. Pointer dragging and keyboard Alt+Up/Alt+Down reorder requests; the full project order is persisted in `generation_order_json`, restored after reloads, and remains independent of collection display order. Only checked requests run in that saved order. Drafts cannot be selected until saved. Stable IDs distinguish collections and requests even when names match.

Single-endpoint generation sends `source_endpoint_id` with each request. The backend validates that it belongs to the selected project and stores its ID and display name with each generated test case. Optional `example_test_case_ids` are resolved from that same project and passed as prompt context; IDs outside the project or unknown IDs return 404. Examples are compacted to scenario/request/assertion/mapping fields without execution results or authorization headers. Newly generated cases get unique IDs, persist alongside prior cases, and the frontend merges them into its existing case list.

The Test Cases workspace provides project-scoped multi-select filters for reusable runs, collections, and endpoints, alongside execution status. Filters combine across categories and use OR semantics within a category. A single case resolves to its source endpoint ID, with URL/method matching for legacy cases. A flow matches endpoint and collection filters when one of its steps matches all active endpoint/collection criteria; the complete scenario appears once in **Flow scenarios** and lists all participating endpoints and collections. Unresolved cases remain visible unless an endpoint or collection filter is active.

Test cases are grouped by endpoint while each case keeps its own generated title; unnamed endpoints use their URL as the group heading. Users can create manual single cases from one saved request or manual flows from an ordered selection of saved requests; new cases receive stable IDs, are immediately upserted into the project, and open in the editor.

Test-case selection spans single cases and flows. The Test Cases top bar places a prominent **Add manual test** action and a secondary **Reusable runs** action beside the page title. Their popovers use numbered sections and concise guidance; the reusable-runs action remains visible without a project and explains that a project is required. The toolbar shows **Deselect all** only when every case is selected and otherwise shows **Select all**. A named run can load, update, or delete a reusable case selection; changing selection after loading does not change the stored definition until **Update run** is used. Batch execution preserves case-list order. Latency values display in milliseconds through 1000 ms and seconds above that threshold. Test Cases controls and cards reflow to available width when the sidebar is expanded. Request-order drag transitions animate neighboring rows and disable motion when the browser requests reduced motion.

The home header summarizes the selected project. The collapsed app sidebar groups project selection, project actions, counts, and a saved-test-case fetch action. In API Workspace, New, Import, and Discover actions appear in the navigator header; contract review and flow discovery render above the playground in the editor column. Discovery is disabled until an imported contract exists. The collection tree is collapsible and moves above the playground when the page narrows. Persistent eligibility remains separate from per-run request selection, while selection and flow ordering share one Test Cases panel. Project summaries and collection exports use a 15-second Streamlit cache, cleared after relevant writes.

Postman Collection v2.1 export includes methods, URLs, payloads, and disabled query/header rows. Import supports Postman Collection v2.1 requests; environments, scripts, and authentication configuration are not imported. Legacy endpoint routes map to Imported Endpoints. Existing endpoint rows migrate once at startup, retaining IDs, request fields, enabled state, inclusion choice, and order.

Contract import previews every discovered endpoint and allows a user to uncheck entries and edit method, headers, query parameters, and payload before saving to an existing or new collection. The source controls sit side by side, request headers and query editors share a row, and long editors/lists are bounded to keep review compact. GET and DELETE requests are saved without payloads, including when their method is changed during review. A missing or unresolved API server requires a base URL before import. LLM extraction from prose is advisory and includes supporting source excerpts. Newly imported requests are excluded from generation until explicitly enabled.

## 6. Project Management
Projects, collections, saved requests, test cases, named test runs, execution history, and each project's generation order are stored in PostgreSQL. Test runs use a dedicated project-scoped table with a case-insensitive unique name index and JSON-encoded ordered case IDs; startup creates it idempotently. `generation_order_json` is added through an idempotent startup migration; projects without a stored order use their eligible saved-request order as the initial order. Nested flow steps, request playground assertions, request fields, and contract operation metadata remain JSON payloads so API shapes stay compatible; contract import adds no database migration. Response schema assertions use JSON Schema Draft 2020-12 validation.
- Create project with name and description
- Select existing project from sidebar
- Delete project (cascades to collections, requests, and test data)
- Create, rename, delete, and export collections; create, update, and delete saved requests
- Fetch last generated test cases and assertions from project
- Save or update test cases by stable test-case ID without creating duplicates
- Delete a project and its dependent rows through foreign-key cascades

Set `DATABASE_URL` in `.env` for local app processes. Docker Compose connects the backend to the `postgres` service and persists data in the named `api_agent_pgdata` volume. A default project is created automatically and receives standalone generated tests. The selected project is persisted and restored after restart. Collection/request changes and assertion edits are saved explicitly; generated cases and execution results are saved automatically. Existing SQLite files are not migrated automatically.

For the Docker stack, `make docker-up-build` builds images and starts all services; use `make docker-up` on later starts to skip builds and reuse existing images. Dependency installation is in a separate image layer, after requirements are copied and before application source, so source-only edits do not reinstall packages. BuildKit caches pip downloads for dependency rebuilds.

## 7. Flow Test Cases
Generate test cases for a sequence of endpoints. LLM creates flow test cases covering:
- Full flow (all steps succeed)
- Step failure (one step fails)
- Data dependency (field mapping between steps)
- Edge cases (null/empty propagated)
- Race-oriented scenarios may be requested, but the current executor runs each scenario's steps sequentially and does not issue concurrent requests.

### Flow Scenario Data Model
The model determines the number of scenarios; the API does not impose a requested count. The compact model response references supplied endpoint IDs, and the backend restores full endpoint data before saving. Each flow scenario contains:
- **id**: unique string (e.g., "flow_1")
- **name**: descriptive scenario name
- **type**: positive | negative | edge | race
- **description**: what this flow validates
- **steps**: ordered list of flow step objects

The UI renders each step as an editable test-case card. Single requests and flow steps expose method, URL, Params, Headers, and Body editors; query values in URLs are normalized into the Params editor. Flow steps can be added from saved project requests, reordered, and removed. Each step has repeatable editable variable mapping rows for response JSONPath, request destination, and optional transform. Assertion editing uses the same expandable type groups, enabled toggles, bordered rows, and add/remove controls as the request playground. Execution remains sequential so mappings can consume earlier responses. Results show the scenario outcome and individual step status, assertion details, latency, and response.

Each flow step contains:
- **step_order**: integer (1-based)
- **endpoint_id**: reference to endpoint in collection
- **endpoint**: full endpoint dict (method, url, headers, body)
- **assertions**: per-step assertion config (status, body_contains, jsonpath, response_schema; each accepts one config or a list)
- **variable_mappings**: list of {from, to, transform} for passing response fields to a later request; `from` supports simple paths, numeric array indexes, and array wildcards such as `$.items[*].id`, optionally prefixed with a 1-based response step number. Targets support headers, query parameters, path parameters, and body fields. Wildcard results mapped into request bodies remain JSON arrays; header and query values are compact JSON text.
- Discovered OpenAPI paths can also map a response JSONPath into `request.path.PARAM`; execution URL-encodes the value into a matching `{PARAM}` placeholder.

### Assertion Configuration

Each assertion type is stored as a list so a test case can contain multiple checks:

```json
{
  "status": [{"enabled": true, "expected_status": 200}],
  "body_contains": [{"enabled": true, "value": "success"}],
  "jsonpath": [{"enabled": true, "path": "$.token", "expected_value": "abc"}],
  "response_schema": [{"enabled": false, "schema": "{}"}]
}
```

The executor evaluates every enabled instance with AND semantics, including JSON Schema Draft 2020-12 response validation. Generated single tests and each generated flow step receive one disabled, blank schema assertion unless the model already supplied one. The user can edit, enable, add, or remove schema assertions after generation. Legacy single-dictionary assertion values are normalized to one-item lists, so existing generated and saved test cases remain compatible.

Generated case edits are staged in the frontend until **Save changes** calls `PUT /api/v1/projects/{project_id}/test-cases/{test_case_id}`. The existing storage upsert preserves the row's ordinal and replaces its JSON payload by stable case ID. Run sends the current in-session case to the execution route without saving it; execution results are persisted only when the submitted case matches the saved configuration. Saving request or step changes clears prior execution records for that case. The execution route validates edited single requests, flow steps, and mapping sources and targets before using them. The first flow step cannot consume a previous response, so stale mappings on that step are discarded and the editor does not offer mapping controls there. Empty mapping placeholders on later steps are ignored; partially filled mappings remain validation errors.

### Flow Execution Logic
Flow execution runs all steps sequentially:
1. Apply variable mappings from previous step responses to current request headers, query parameters, path, or body
2. Send HTTP request for current step with enabled headers and query parameters
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
- Unsaved API Workspace requests and responses stay in Streamlit session state only; saved requests persist their assertion definitions
- Clean caches: `make clean-cache` (keeps the virtual environment)
