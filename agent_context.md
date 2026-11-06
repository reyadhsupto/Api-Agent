# Agent Context - Api-Agent

## Project Status
Phase: Unified API Workspace, project-persistent flow ordering, and request library redesign
Mode: Act

## Completed
- Repository initialized (greenfield, Python .gitignore, README)
- Feasibility analysis completed
- Tech stack selected (FastAPI, python requests, Streamlit, free-tier LLM fallback)
- All project files created (documentation, backend, frontend, tests)
- Virtual environment created and dependencies installed
- FastAPI app imports and starts correctly (all routes verified)
- PostgreSQL-backed unit and persistence tests pass (21/21)
- Backend smoke test passed (health, curl parse, generate, execute endpoints)
- Frontend syntax verified
- LLM providers: Groq (dynamic model), OpenRouter, Cohere, HuggingFace
- Frontend features: unified API Workspace with temporary request tabs, cURL parsing, saved collections, and generation selection
- API Workspace editor uses Postman-like request tabs with horizontal scrolling and right-aligned close controls, a Method/URL/Send row, Params and Headers tables, and none/raw Body modes
- Test Cases combines per-run request selection with drag-and-drop flow ordering; arrow controls remain available when the optional sorter is missing
- Frontend flow rendering: editable ordered step cards with assertions, mappings, and per-step execution results
- Test Cases workspace: guided Single/Flow generation, result counts and filters, per-case and batch execution with progress, compact status cards, and separated assertion/request/response views
- Backend features: assertions via execute endpoint, JSONPath checker, 5-min timeout, PostgreSQL persistence
- Docker Compose services for PostgreSQL, backend, and frontend; Make targets for local and Docker runs
- Documentation updated (README, technical docs, agent context)
- Home header and request library use shared branded styling, compact collection/request rows, and contextual empty states
- Sidebar remains collapsed by default and groups project selection, actions, counts, and saved-test-case fetch
- Per-project generation order is persisted in PostgreSQL via `PUT /api/v1/projects/{project_id}/generation-order`; it is independent of collection request order
- Project summaries and collection exports use a short-lived cache that is invalidated after relevant writes
- Saved-request library uses compact color-coded method pills, truncated escaped names, and open/delete icons revealed on hover or keyboard focus; URLs are omitted and empty collections retain their guidance
- Test Cases generation combines per-run request selection and flow ordering in one panel; ordering persists through the project generation-order API
- Request Playground has a repeatable Assertions tab for status, body text, JSONPath field values, and JSON Schema; saved requests persist assertion settings, Run All checks enabled assertions with one request, and individual Run checks one assertion with a fresh request
- Generated single tests and flow steps expose editable JSON Schema response assertions, disabled with an empty schema by default; execution uses the shared Draft 2020-12 validator

## In Progress
- None

## Blocked
- None

## Next Steps (Post-MVP)
1. Add Postman collection import
2. Add test result export to JSON/CSV/JUnit
3. Add race condition concurrent execution
4. Add CI/CD webhook triggers
5. Add user authentication and workspaces
6. Variable mapping UI editor (map response.field -> request.field)

## Key Decisions
- Backend: Python + FastAPI routes in `main.py`, PostgreSQL repository in `storage.py`
- HTTP Client: python requests
- Database: PostgreSQL via psycopg; `DATABASE_URL` configuration and Docker volume `api_agent_pgdata`
- Auth: None (single-user, local)
- Frontend: Streamlit (API Workspace and Test Cases tabs)
- LLM: Multiple free-tier APIs with automatic fallback (Groq, OpenRouter, Cohere, HuggingFace)
- Export: Postman Collection v2.1 for saved collections; collection import remains out of scope
- Code style: Minimal functions, flat structure, easy to read
- Assertions: Repeatable list-based instances per test or flow step (status, body contains, JSONPath); legacy single-dict configs remain supported
- Request playground assertions are repeatable saved-request JSON data (status, body contains, JSONPath, response schema); schema validation uses JSON Schema Draft 2020-12 and single assertion runs ignore the Run All enabled checkbox
- Generated single-case and flow-step assertion data supports repeatable response_schema entries; generation adds a disabled blank entry when the LLM omits one, and users can edit it in the Test Cases workspace
- Test case cards: Collapsible via st.expander
- Console logging: st.iframe with console.log
- Timeout: 300 seconds (5 minutes) for LLM generation
- Flow execution: Sequential HTTP calls with variable substitution between steps
- Flow failure handling: Stop on first failed step (configurable per scenario)
- Scenario grouping: Multiple scenarios per flow (positive, negative, edge, race)
- Flow UI: Scenario cards with ordered step cards, editable step assertions, and per-step results; execution remains sequential per scenario
- Sidebar: Starts collapsed and disambiguates projects with matching names
- Persistence: Projects, collections, requests, test cases, executions, and active project are stored in PostgreSQL; standalone generation uses the default project
- Flow generation: no requested scenario count; the model returns as many complete, useful scenarios as its provider output ceiling allows (`API_AGENT_LLM_MAX_OUTPUT_TOKENS`)
- API Workspace drafts and quick-send results are session-only; saved requests are project-scoped collections
- Request row enabled flags control sending; generation eligibility is separate, persisted, and off by default for new requests
- API Workspace controls persistent generation eligibility; Test Cases controls per-run selection and ordering for eligible requests
- Flow request order is explicit and independent of collection display order
- Flow request order is stored per project, restored on project load, and filtered by relative order when a generation run selects a subset
- Postman Collection v2.1 export is available for saved collections; legacy endpoint routes use Imported Endpoints
- Existing endpoint rows migrate once into Imported Endpoints with IDs, fields, enabled state, inclusion choice, and order preserved
- Existing SQLite data is not automatically migrated; PostgreSQL initializes a fresh schema
- Local run: `make docker-db-up`, then `make run-local-backend` and `make run-local-frontend`
- Full Docker run: `make docker-up`, `make docker-logs`, and `make docker-down`
