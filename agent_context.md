# Agent Context - Api-Agent

## Project Status
Phase: Implementation Complete (MVP)
Mode: Act

## Completed
- Repository initialized (greenfield, Python .gitignore, README)
- Feasibility analysis completed
- Tech stack selected (FastAPI, python requests, Streamlit, free-tier LLM fallback)
- All project files created (documentation, backend, frontend, tests)
- Virtual environment created and dependencies installed
- FastAPI app imports and starts correctly (all routes verified)
- Unit and SQLite persistence tests pass (14/14)
- Backend smoke test passed (health, curl parse, generate, execute endpoints)
- Frontend syntax verified
- LLM providers: Groq (dynamic model), OpenRouter, Cohere, HuggingFace
- Frontend features: multi-endpoint, editable assertions, collapsible cards, console logging
- Frontend flow rendering: editable ordered step cards with assertions, mappings, and per-step execution results
- Backend features: assertions via execute endpoint, JSONPath checker, 5-min timeout, SQLite persistence
- Makefile with clean-cache command
- Documentation updated (README, technical docs, agent context)

## In Progress
- None

## Blocked
- None

## Next Steps (Post-MVP)
1. Add Postman collection import
2. Add export to JSON/CSV/Postman/JUnit
3. Add race condition concurrent execution
4. Add CI/CD webhook triggers
5. Add user authentication and workspaces
6. Variable mapping UI editor (map response.field -> request.field)

## Key Decisions
- Backend: Python + FastAPI routes in `main.py`, SQLite repository in `storage.py`
- HTTP Client: python requests
- Database: SQLite via Python standard library; `.data/api_agent.sqlite3` by default
- Auth: None (single-user, local)
- Frontend: Streamlit (single Python file, 2 tabs: Endpoints + Test Cases, multi-endpoint support)
- LLM: Multiple free-tier APIs with automatic fallback (Groq, OpenRouter, Cohere, HuggingFace)
- Export: Scoped for future (not in MVP)
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
- Persistence: Projects, endpoints, test cases, executions, and active project are stored in SQLite; standalone generation uses the default project
