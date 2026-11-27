# Technical Documentation - Api-Agent

## 1. Tech Stack
| Layer | Technology | Reason |
|-------|-----------|--------|
| Backend Language | Python 3.11+ | Project convention, rich AI/HTTP ecosystem |
| Backend Framework | FastAPI | Async support, automatic OpenAPI docs, easy routing |
| HTTP Client | python requests | User-specified standard for outbound API calls |
| Frontend | Streamlit + embedded Components v2 | Python UI with browser controls for cURL debounce and sortable request rows |
| LLM Providers | AMD Token Lab, OpenRouter, Groq, Cohere, Hugging Face | Ordered environment-based fallback |
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

### frontend (Streamlit UI)
- `frontend/app.py` is a thin entry point: sys.path bootstrap, explicit imports, and `main()`
- `frontend/core.py` holds shared state, API clients, CSS constants, and render helpers
- `frontend/views/{api_workspace,test_cases,chat,activity}.py` render one workspace mode each
- `frontend/styles/{tokens,base,shell,theme,light,request_tabs,test_cases}.py` own the design tokens and CSS blocks
- `.streamlit/config.toml` sets the single native light theme (base light, background #f6f7fa, accent #ff6c37)
- `frontend/styles/theme.py` re-points the native widgets Streamlit paints outside its theme
  variables (toolbar buttons, popover, tooltip, toast, segmented pill, slider, progress, spinner,
  tab highlight, notice) at the `--aa-*` tokens so native surfaces match the light palette
- The left rail switches modes (API Workspace, Test Cases, Project Chat, Activity Logs); Activity Logs has Generation and Knowledge Extraction subviews, and only the selected workspace renders
- Design tokens are emitted once as CSS custom properties on `:root` by `frontend.styles.inject_styles`; components consume `--aa-*` variables instead of hard-coded colours
- Import contract: modules use absolute `frontend.*` imports, so the same files load under `streamlit run` and package imports from tests
- API Workspace provides temporary request tabs, manual editing, debounced cURL parsing in the URL field, quick sends, response display, and saved project collections
- Single generated tests retain source endpoint metadata and display in endpoint groups; flow scenarios have a separate group
- Saved requests can be selected and explicitly ordered for generation
- Test Cases supports single and flow generation/execution with editable assertions
- Generation controls use a Single/Flow selector, selected saved-request list, optional business requirements, and a primary generation action; no scenario count is requested for flows
- Project Chat turns only append to the thread; explicit Knowledge Hub drafts are created only after a user action
- The Knowledge Hub stores immutable project, feature, and microservice page versions; features can link to multiple shared microservice pages
- Generation includes the project page plus selected feature pages and their linked microservices; exact version snapshots are attached to generated cases and activity records
- Results use status counts, result filters, select/expand controls, per-case execution, batch execution with progress, and explicit project save
- Each test case card: compact status summary, repeatable status/body-contains/JSONPath/JSON Schema assertions, separate request/result views for single cases, and expandable per-step flow details
- Request/response results show method and URL, headers, readable payloads, response status, latency, payload size, and pretty/raw JSON selection
- Calls FastAPI endpoints via python requests
- The frontend uses `requests` only; read timeouts are scoped by call type (see the timeout bullet below)
- The test-case toolbar keeps one merged Expand/Collapse control and one Export CSV control
- Export CSV is a `st.link_button` to `/api/v1/projects/{id}/test-cases/export` with repeated
  `selected_case_ids` parameters, so the backend streams the file only on click
- CSV includes `technique_tags_json` and `requirement_refs_json` per case; suite-level coverage summaries remain in generation activity.
- The collections rail filters by HTTP method with a segmented control and shows an
  `enabled of total` counter for the project
- Collection rows show real selection state: `name · total` when every request is enabled and
  `name · enabled/total (partial)` when only some are, because `st.checkbox` cannot render an
  indeterminate mark
- The collection and request kebabs are quiet affordances: three-dot icons at 40% opacity that
  reach full accent opacity on row hover or keyboard focus
- Collection export is a link to the backend route, not a prefetch: Streamlit renders popover
  bodies on every run, so fetching inside a kebab would cost one API call per collection per rerun
- The request editor exposes Params, Headers, Body, Auth, and Assertions tabs
- Body is No body or Raw; Raw shows the effective Content-Type and, for JSON, whether the text parses
- Auth stores credentials on the draft (Bearer token, Basic auth, or API key) and materialises the
  header at send time; an explicit header on the Headers tab takes precedence
- `_request_signature` normalises method, URL, enabled header and query rows, body content, auth, and
  body type, so opening a saved request never reports unsaved changes. A leading asterisk marks a
  request tab with unsaved edits, and the editor shows a caption until the draft is saved
- Playground assertion runs render a Test Results table (Result, Assertion, Detail)
- Each test-case card header carries the Run action for the card type (Run, or Passed/Failed for a
  general scenario) plus a kebab holding Delete; the footer keeps Save changes and its unsaved-edits
  hint, so the destructive action is not adjacent to the save action
- Read timeouts are scoped: 15 s for raw project summaries, 30 s for GET and DELETE, 60 s for PUT, and
  300 s only for POST routes that call an LLM or execute requests
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
Body: {"parsed_curl": {...}, "business_requirements": "...", "project_id": "...", "source_endpoint_id": "...", "example_test_case_ids": ["..."], "mode": "Single", "case_collection_id": "...", "case_collection_name": "..."}
Returns {"test_cases": [...], "clarification_questions": [...], "coverage_summary": {...}, "activity": {...}}. Accepts the (optionally edited) parsed_curl from the frontend. `mode: General` instead requires business requirements and generates manual-only cases with `case_kind: general` and ordered `manual_steps`; endpoint and example inputs are not used. General requests may include a project-scoped `case_collection_id` and `case_collection_name`; cases retain these fields through follow-up and revision generation.
`example_test_case_ids` is optional. Selected cases are loaded from the project and used as scenario-style and coverage context; the endpoint request and business requirements remain the generation target. The cases are not copied or modified. Generated cases receive new IDs and are saved alongside the existing cases.

Generated cases are independent scenarios by default; distinct boundary values or expected outcomes are separate cases. `technique_tags` (for example, BVA) and `requirement_refs` (explicit IDs or stable `REQ-001` labels) are separate editable case fields. The `coverage_summary` envelope and activity snapshot map requirements to case IDs/names, state covered/partial/uncovered/ambiguous status, and list unsupported coverage claims. Branch or statement coverage is not asserted without supplied implementation logic or source. Release revision and clarification prompts preserve baseline tags/references when the model omits them; revision summaries describe the complete output suite, including cases copied unchanged.

Generation output is normalized from an envelope containing `test_cases`, optional `clarification_questions`, and optional `coverage_summary`, or from a legacy bare array (treated as no questions or coverage summary). Clarification questions may be strings or objects with `question` and optional `context`; the API normalizes them to displayable strings. General cases contain no request, mapping, or generated assertion data. The frontend renders their manual steps and records Passed/Failed marks through the project-scoped manual-result endpoint; each mark is appended to execution history and contributes to flaky classification. A Failed mark can include an optional `failure_reason`, shown on the card as its assertion result and retained on the execution entry. HTTP batch runs skip general cases.

General scenario collection groups are separate from endpoint collections. `GET /api/v1/projects/{project_id}/general-case-collections` lists them and `POST` with `{"name":"..."}` creates one before generation. Existing groups are migrated from saved General case metadata at startup, and saving a General case keeps its group metadata synchronized.

### POST /api/v1/projects/{project_id}/generation-activity/follow-up
Body: {"source_activity_id": "...", "answers": {"1": "..."}}
Creates a linked generation activity and a new refined case set. On successful non-revision refinement, source cases receive `superseded_by_activity_id` and leave active case lists, examples, revision baselines, suites, and execution; their records, execution history, and activity remain available. The refinement and supersede markers are written atomically. Failed refinement does not supersede the source cases. The response includes `archived_case_ids` and `coverage_summary`; activity records include `supersedes_activity_id`, archived IDs, questions, answers, and requirement-to-case coverage mappings. Release revision follow-ups instead create a new revision and preserve all prior revision cases.

Revision requests may include `keep_unchanged_case_ids`, a subset of `baseline_case_ids`. The backend copies those cases with new IDs and source links without including them in the model input. Revision clarification follow-ups carry this protection forward and record source and copied IDs in activity details.

### POST /api/v1/projects/{project_id}/test-cases/{test_case_id}/manual-result
Body: {"status": "passed"} or {"status": "failed", "failure_reason": "..."}
The failure reason is optional and limited to 2,000 characters. Each result appends an execution-history entry containing the saved case snapshot and assertion detail, then updates the case's current `manual_status` and `manual_failure_reason`. The earlier `note` field remains accepted for compatibility.

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

The Test Cases workspace provides project-scoped multi-select filters for reusable runs, collections, and endpoints, alongside execution status. General scenarios can be assigned to named, project-scoped case collections. Create one from the General generation form before generation or reuse an existing group; the existing **Collections** filter includes these groups without another filter control. Empty groups persist in PostgreSQL. Existing groups are seeded from saved General cases during startup. Filters combine across categories and use OR semantics within a category. A single case resolves to its source endpoint ID, with URL/method matching for legacy cases. A flow matches endpoint and collection filters when one of its steps matches all active endpoint/collection criteria; the complete scenario appears once in **Flow scenarios** and lists all participating endpoints and collections. General scenarios match their assigned collection and are excluded when an endpoint filter is active.

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

### Project Chat, Knowledge Hub, and generation context

The end-to-end data flow and user workflow are documented in [docs/persistent_context.md](docs/persistent_context.md). Chat loads a bounded thread summary and recent transcript plus relevant current Hub pages and saved endpoints. Each exchange is stored in PostgreSQL; a normal chat turn does not invoke a second extraction request. Users explicitly prepare an update from a discussion, review separate drafts and section-level changes for selected pages, and save selected versions atomically.

The Knowledge Hub uses the existing scoped immutable document-version store. Each project has a shared project-wide page plus feature and microservice pages. A many-to-many link table associates features with reusable microservices. The additive startup migration retains old brief and fact records, appends source-labeled approved facts and legacy thread briefs to Hub page versions once, and leaves unapproved legacy rows out of active prompt context. A history restore appends a new version instead of mutating prior versions. Activity Logs → Knowledge Extraction shows historical extraction attempts together with current Hub operations.

Test generation combines the project page, selected feature pages, linked microservice pages, run-specific Business requirements, and the selected endpoint or revision context. It does not send the full chat transcript to generation or save run-specific requirements into the Hub. Unresolved details belong in a visibly labeled **Open questions** section. Activity Logs → Generation and generated cases preserve exact Hub version references and content snapshots, endpoint snapshot, prompt, response, and action requirements.

Single creates independent endpoint cases; Flow uses the chosen endpoint order; General creates manual requirements-only scenarios; contract-discovered Flow starts from a selected contract dependency path. Release Revision additionally supplies selected saved baseline cases, previous requirements and release notes, new changes, and current selected endpoints. Users can mark baseline cases to carry unchanged. Clarification responses create linked follow-up actions; prior outputs remain available in history according to the active revision/refinement rules. The linked guide describes each mode, its context inputs, limitations, and provenance.

### Reset the local Docker database

`make docker-db-reset` is the destructive reset path for the current Compose project only. It requires an interactive terminal and the exact confirmation `RESET`, stops the Compose stack, resolves and removes only the `api_agent_pgdata` volume, then rebuilds and starts the stack. The backend's idempotent initialization creates the current tables and indexes and its startup bootstrap creates the built-in Default Project and overview scope. Other project-specific Compose volumes are not selected by the reset script. `make docker-down` stops services without deleting data. The reset target never reads or drops a database identified only by a local `DATABASE_URL`.

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

Generated case edits are staged in the frontend until **Save changes** calls `PUT /api/v1/projects/{project_id}/test-cases/{test_case_id}`. The existing storage upsert preserves the row's ordinal and replaces its JSON payload by stable case ID. Run sends the current in-session case to the execution route without saving it. Results are recorded in PostgreSQL when the executed HTTP request inputs match the saved case; editor-added assertion defaults and UI-only row identifiers do not block recording, while unsaved request or flow mapping changes remain session-only. Saving request or step changes clears prior execution records for that case. The execution route validates edited single requests, flow steps, and mapping sources and targets before using them. The first flow step cannot consume a previous response, so stale mappings on that step are discarded and the editor does not offer mapping controls there. Empty mapping placeholders on later steps are ignored; partially filled mappings remain validation errors.

### Flow Execution Logic
Flow execution runs all steps sequentially:
1. Apply variable mappings from previous step responses to current request headers, query parameters, path, or body
2. Send HTTP request for current step with enabled headers and query parameters
3. Capture response (status, headers, body)
4. Evaluate step assertions
5. If step fails and scenario requires all steps to pass, mark flow as failed
6. Aggregate results: pass if all enabled assertions pass across all steps


## 8. LLM Provider Routing and Fallback

Generation, Project Chat, and Knowledge Hub model calls use the shared provider dispatcher. `LLM_PROVIDER_ORDER` is a comma-separated precedence list; the default is `amd,openrouter,groq,cohere,huggingface`. Providers without keys are skipped, and unknown provider names are a configuration error. API or provider response failures advance to the next configured provider. Once a provider returns a completion, application-level validation runs without another provider attempt; malformed JSON and malformed flow data are reported as generation errors.

Provider failures are logged by provider name and HTTP status (when available), without logging prompts or credentials, so silent fallback can be diagnosed. A successful AMD call reports the configured `AMD_MODEL` as its model metadata; the gateway-reported model alias is retained separately when it differs. Chat shows the provider alongside the latest model.

AMD Token Lab uses the OpenAI-compatible chat-completions endpoint `https://api.tokenlab.amd.com/v1/chat/completions`, bearer authorization, and `AMD_MODEL` read at request time (default `Gemma-4-31B-IT`). `AMD_API_KEY` supplies its key. OpenRouter uses `OPENROUTER_API_KEY` and `OPENROUTER_MODEL`; Groq uses its largest available active model; Cohere and Hugging Face retain their configured/default models. `API_AGENT_LLM_MAX_OUTPUT_TOKENS` bounds completion output. The shared dispatcher preserves the existing text-only interface.

Every successful completion returns provider/model metadata. Generation activities and Knowledge Extraction events retain this metadata; assistant chat messages retain it in their message records and return it in the message API response. Chat threads retry the configured provider order on each call; their stored model is descriptive metadata, not a provider pin.

Generated test-case output is validated before storage. Malformed JSON or malformed flow steps are rejected with an HTTP 502 error explaining the invalid field; the system does not create synthetic fallback test cases or call another provider for that application-level validation failure.

### Groq Dynamic Model Selection
Before calling the chat completion API, the system calls `GET /v1/models` to list available models, then selects the one with the largest `context_window` (currently `llama-3.1-8b-instant` with 131072 tokens).

### Provider Configuration
Set one or more provider keys in `.env`, then arrange their precedence with `LLM_PROVIDER_ORDER`. To use AMD Token Lab, set `AMD_API_KEY` and optionally `AMD_MODEL`. Changing `AMD_MODEL` affects the next AMD request without restarting provider selection logic. OpenRouter remains available as a fallback through `OPENROUTER_API_KEY` and `OPENROUTER_MODEL`.

## 9. Deployment
- Local: `make docker-db-up`, then `make run-local-backend` and `make run-local-frontend` in separate terminals
- Docker: `make docker-up`, `make docker-logs`, and `make docker-down`
- Destructive fresh local Docker database: `make docker-db-reset` (requires typing `RESET`)
- FastAPI local: `uvicorn app.main:app --reload` on port 8000
- Streamlit local: `streamlit run frontend/app.py` on port 8501
- Single user, local only, no auth
- Frontend POST API timeout: 1,200 seconds (20 minutes), including LLM generation
- PostgreSQL URL: `DATABASE_URL` in `.env`; Compose volume: `api_agent_pgdata`
- Flow scenario quantity is model-determined; provider output ceiling uses `API_AGENT_LLM_MAX_OUTPUT_TOKENS`
- Unsaved API Workspace requests and responses stay in Streamlit session state only; saved requests persist their assertion definitions
- Clean caches: `make clean-cache` (keeps the virtual environment)
- Native Streamlit widget colours come from `.streamlit/config.toml`; the app palette lives in `frontend/styles/tokens.py`
- The frontend uses one light palette; no theme selector or dark-mode session state is exposed
- Streamlit 1.66 publishes no theme custom properties (no `--text-color`, no `--st-*`), so `frontend/styles/light.py` restates native surfaces to match the app palette
- Data grids and charts use Streamlit's native light canvas, with surrounding borders and captions styled from the same light tokens
- `.st-key-test-case-toolbar` is sticky; breakpoints at
  1440, 1024, and 768 px reflow the workspace without hiding actions
- Vertical and horizontal gaps are tightened for fine pointers only, so coarse pointers keep
  44 px touch targets
- Muted text uses #8a919c, which clears 4.5:1 on black and on the panel surfaces
- Test-case generation runs inside a `st.status` block that settles to running, complete, no
  cases, or failed, instead of leaving a spinner of unknown weight

## Frontend theme and surface system

### Single light palette

`frontend/styles/tokens.py` retains matching `DARK` and `LIGHT` token maps for
stylesheet compatibility, but only `LIGHT` is used by the application.
`DEFAULT_THEME` is `light`, and `active_theme()` always returns that value.
There is no in-app theme switch or theme session key.

`.streamlit/config.toml` configures Streamlit's native theme as light and is
copied into the frontend Docker image by `Dockerfile.frontend`. The app also
sets the document `color-scheme` to light and injects `frontend/styles/light.py` to align native surfaces such as menus,
dialogs, tooltips, toasts, code, alerts, chat bubbles, and widget edges with the
light tokens. Data grids and charts use Streamlit's native light canvas as well.

### The box system

`frontend/styles/surfaces.py` owns one card recipe (`.aa-box` plus quiet, inset,
raised, and selected variants) and the explicit edges of native containers.
Every value is a token, so the recipe needs no theme branch.

Light mode separates surfaces with a pale canvas (`#f6f7fa`), white panels,
slightly tinted inner panels, and a graduated border ladder. Interactive edges
remain stronger than card dividers so controls are identifiable without hover.

Nested boxes drop to `--aa-line-soft` and `--aa-panel-alt`, so a card inside a
card reads as a child rather than a second frame.

### Collection rail

`frontend/styles/layout.py` holds the workspace grid (rail pinned, editor
fluid, single column below 760px). `frontend/styles/rail.py` turns each
collection into a filled card with a declared border, joins its requests with a
vertical guide line, and marks the active request with an accent bar. Selection
is carried by the accent edge, never by fill alone, so it survives both
palettes. The three-dot triggers rest at reduced opacity and resolve to the
accent on row hover, row focus, or their own focus.

### Chat workspace

`frontend/views/chat.py` renders a conversation rail (search, All/Active/Archived
filter, per-thread action menu) beside a flat transcript. Each message has a
local timestamp above it; assistant bubbles align left with a muted surface and
user bubbles align right with an accent tint, without role labels. Long messages
start expanded and can collapse. Bubbles use two-thirds of the transcript width
on desktop and expand on narrow screens. The transcript uses normal page
scrolling, and the composer has a palette-aware outline and focus ring. The
thread rail defaults to Active and supports archive, restore, and confirmed
permanent deletion; thread deletion cascades to its messages while preserving
Knowledge Hub pages and generation activity. Grounded answers include one `Sources`
disclosure instead of a code block per endpoint. Sending a message reports
through `st.status` with terminal states. Knowledge Hub is a peer view beside
Conversation. Its page editor shows version history and diffs, supports feature
to microservice links, and reviews multi-page updates before an atomic save.

### Release revisions

The revision workflow moved out of a collapsed expander at the foot of the
generation panel into `_render_revision_dialog`, opened from a `Create release
revision` button in Test Cases. Because a dialog body runs only while the dialog
is open, the saved project and the generation history are now read once per
session instead of on every rerun of the panel.

### Activity log views

The Activity Logs workspace has two project-scoped subviews. Generation uses the paged `generation-activity` API and opens full activity records in a dialog. Knowledge Extraction combines retained `extracted` and `extraction_failed` events with append-only Knowledge Hub events for page creation, feature-to-microservice link changes, draft preparation/failure, reviewed page saves, and version restores. Chat turns do not create extraction events. Hub draft events retain the exact prompt messages, raw model response, provider/model metadata, source thread, and destination page; save/restore events retain the resulting version and content. The paged activity-list API returns summaries without loading large prompt/response bodies, while a project-scoped detail API loads the full record when the user opens a row. Historical extraction prompts and provider metadata remain available where those snapshots were recorded.

`GET /api/v1/projects/{id}/knowledge/activity?limit=25&offset=0` returns paged summaries for extraction and Hub events. `GET /api/v1/projects/{id}/knowledge/activity/{event_id}` returns the full event payload and, for extraction events, its retained source submission. Both routes enforce project scope.

### Generation activity paging

`GET /api/v1/projects/{id}/generation-activity` returns
`{"activities", "total", "limit", "offset"}`. `total` is a `COUNT(*)`
(`Database.count_generation_activity`), not the page length, so a pager can state
the real number of pages. The view keeps the page size and offset in session
state, clamps the offset when records are deleted, and disables Previous
and Next at the boundaries.

## Next.js frontend and shared design tokens

`web/` is a Next.js App Router and TypeScript application served on port 3000. Browser requests use same-origin Route Handlers under `web/src/app/api/`; the catch-all handler forwards `/api/v1/*` to `BACKEND_URL` (default `http://localhost:8000`) after reading the HttpOnly access-token cookie. The browser never sees bearer credentials or contacts the backend origin directly.

### Local authentication

Set `AUTH_USERNAME`, `AUTH_PASSWORD`, and `AUTH_JWT_SECRET` for the single local account. The signing secret must contain at least 32 characters; generate one with `python -c "import secrets; print(secrets.token_urlsafe(48))"`. FastAPI middleware protects versioned API routes, with health and the login, refresh, and logout endpoints public. Access JWTs expire after 15 minutes. Refresh credentials are opaque, stored as hashes in `auth_refresh_tokens`, expire after 30 days, and rotate transactionally on use. Next.js stores both values in HttpOnly, SameSite=Lax cookies and retries one API call after refresh. Streamlit holds the same token pair only in server-side session state. This local single-account mechanism is not a user/role system.

### Contract file import

`POST /api/v1/contracts/upload-preview` accepts multipart uploads up to 5 MB for OpenAPI/Swagger JSON or YAML, Postman JSON, Markdown, TXT, PDF, and DOCX. PDF text is extracted with `pypdf`; DOCX paragraphs are read from the document XML. The resulting text is passed through the existing contract parser, so prose extraction can use the configured LLM. The API Workspace displays the parsed endpoint list for review and imports only selected endpoints into the chosen collection. The ordinary preview route continues to accept pasted content and public URLs. File parsing limits extracted text to 5 MB and PDFs to 500 pages.

### One token source

The colour contract lives in `frontend/styles/tokens.py` (`DARK`, `LIGHT`, `RADII`, `MOTION`, `FONTS`). `scripts/gen_tokens.py` renders it into `web/src/app/tokens.css`:

- light values in `:root`
- dark values in `.dark`
- both blocks declare the same names, asserted by the generator
- `@theme inline` maps the names onto Tailwind v4 `--color-*`, `--radius-*`, `--shadow-*`, and `--font-*`

Light is the first-visit default. A pre-paint script applies the saved `localStorage['aa-theme']` choice before rendering, and the sidebar Appearance control persists changes across reloads.

Run `make gen-tokens` after changing a token; `make check-tokens` fails when the generated stylesheet is stale.

### Typed backend boundary

`scripts/gen_types.py` imports `app.main` and writes `web/openapi.json` plus `web/src/types/api.generated.ts`. The FastAPI routes return plain dictionaries and declare `no response_model`, so OpenAPI carries only request schemas; response types are hand written in `web/src/types/api.ts` and guarded by `tests/test_api_contract.py`. Adding `response_model` to those routes would silently drop undeclared fields, so it is deliberately not done.

`app.main` constructs the repository lazily through `get_database()`; importing it no longer runs schema DDL or needs PostgreSQL.

### Surfaces

| Route | Status |
| --- | --- |
| `/workspace/api` | Migrated: draft tabs, collections, cURL parse, params/headers/body/auth editors, checks, response inspector, Postman export, and reviewed imports from OpenAPI/Swagger, Postman, Markdown, TXT, PDF, DOCX, or public documentation URLs |
| `/workspace/test-cases` | Migrated: Single/General/Flow generation, examples and briefs context, clarifications, coverage, revision and collection filters, per-case assertions, history and flaky signal, batch run, CSV export |
| `/workspace/chat` | Migrated: thread rail with search and Active/All/Archived scope, per-thread rename, archive/restore and confirmed delete, transcript with role, local time, ordinal, 900-character collapse and a cited-source disclosure per message, day dividers, and a composer that is a flex sibling of the transcript so it never scrolls |
| `/workspace/activity` | Migrated: Generation and Knowledge extraction streams, page sizes 10/25/50/100, real total from COUNT(*), Previous and Next with boundary disabling, offset clamping when history shrinks, and a detail dialog that fetches the full knowledge event |

The activity list uses a compact table with details in a drill-down dialog and a bottom pager. Revision generation labels its run-specific input **New requirement changes**. Knowledge Hub pages are listed together with scope type, version count, latest version/date, and page actions. Request-exclusion lists are height-bounded and scroll independently. Markdown rendering uses GFM, including horizontally scrollable tables. Menus close on outside clicks and Escape. The workspace rail collapses to icon navigation, includes a Home link, and persists its width. Important form fields expose concise native or labelled tooltips.

### Serving the production build

`web/next.config.ts` sets `output: "standalone"`, so `next start` is not the serving command and prints a warning. Build first, then run the standalone server:

```bash
make serve-web              # build, stage .next/static into standalone, serve on PORT=3000
```

The staging step is required: the standalone bundle does not copy `.next/static` or `public`, so without it the page HTML arrives but its client chunks 404 and interactive surfaces never hydrate.
