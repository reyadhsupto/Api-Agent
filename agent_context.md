# Agent Context - Api-Agent

## Project Status
Phase: Unified API Workspace, PostgreSQL collections, and Postman export
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
- Eligible saved requests can be drag-and-drop ordered for flow generation using `streamlit-sortables`
- Frontend flow rendering: editable ordered step cards with assertions, mappings, and per-step execution results
- Backend features: assertions via execute endpoint, JSONPath checker, 5-min timeout, PostgreSQL persistence
- Docker Compose services for PostgreSQL, backend, and frontend; Make targets for local and Docker runs
- Documentation updated (README, technical docs, agent context)

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
- Flow request order is explicit and independent of collection display order
- Postman Collection v2.1 export is available for saved collections; legacy endpoint routes use Imported Endpoints
- Existing endpoint rows migrate once into Imported Endpoints with IDs, fields, enabled state, inclusion choice, and order preserved
- Existing SQLite data is not automatically migrated; PostgreSQL initializes a fresh schema
- Local run: `make docker-db-up`, then `make run-local-backend` and `make run-local-frontend`
- Full Docker run: `make docker-up`, `make docker-logs`, and `make docker-down`
