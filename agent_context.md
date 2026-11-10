# Agent Context - Api-Agent

## Project Status
Phase: Contract import, schema-based flow discovery, unified API Workspace
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
- URL input accepts multiline cURL and auto-parses recognized commands beginning with `curl` after three seconds of inactivity through an embedded Streamlit component; regular URLs are left alone
- Parsed cURL URLs are synchronized back into component state to avoid stale-input guards; response and assertion outcomes show a clear notice pointing to the result body and headers
- The frontend imports its sibling request controls as a package in tests and as a local module when Streamlit runs `frontend/app.py` directly
- Generated single-endpoint cases persist source endpoint ID/name and display in endpoint groups, with URL fallback headings; legacy cases associate by request URL when possible, flows remain grouped separately
- Generated test request detail views show query params in a dedicated Params tab, sourced from request data or query strings in the URL
- Test Cases uses one custom pointer-driven draggable list containing every eligible request, with per-run selection, visible request URLs, and full project order persistence through the generation-order API
- Legacy flow generation asks for compact endpoint references and step assertions/mappings; backend restores canonical request data, avoiding repeated headers and reducing output truncation
- Frontend flow rendering: editable ordered step cards with assertions, mappings, and per-step execution results
- Test Cases workspace: guided Single/Flow generation, result counts and filters, per-case and batch execution with progress, compact status cards, and separated assertion/request/response views
- Backend features: assertions via execute endpoint, JSONPath checker, 5-min timeout, PostgreSQL persistence; generation prompts require strict JSON literals, and the response parser safely normalizes bounded string `.repeat(N)` boundary examples; provider fallback handles request failures, while malformed JSON returns an error without another provider call
- Docker Compose services for PostgreSQL, backend, and frontend; Make targets for local and Docker runs
- Docker quick start uses `make docker-up` with existing images; `make docker-up-build` rebuilds images, and Docker BuildKit caches pip downloads between dependency rebuilds
- Documentation updated (README, technical docs, agent context)
- Home header and request library use shared branded styling, compact collection/request rows, and contextual empty states
- Sidebar remains collapsed by default and groups project selection, actions, counts, and saved-test-case fetch
- Per-project generation order is persisted in PostgreSQL via `PUT /api/v1/projects/{project_id}/generation-order`; it is independent of collection request order
- Generation actions persist project-scoped activity records in PostgreSQL with requirements, endpoint summaries, exact LLM prompt and raw response, status, error, and generated case IDs; the Generation Activity tab accepts paginated or legacy list responses and shows time, type, state, project, and a View details action
- Test case CSV export sends only checked case/flow IDs to the project export endpoint; exported rows contain case metadata, generation requirements, source endpoint fields, request JSON cells, assertions, and one `steps_json` cell per flow, while execution results are omitted
- Project summaries and collection exports use a short-lived cache that is invalidated after relevant writes
- API Workspace uses a searchable, collapsible Postman-style collection tree beside the playground, headed by the active project name and a visible Collections label above the tree; collection and request eligibility checkboxes sit at the left edge, collection/request menus stay at the right, and request names open in the playground
- API Workspace desktop navigator uses a balanced responsive 270–320 px width and stacks above the playground below 760 px; request menu columns reserve enough width to keep their three-dot triggers on the same line, while request names truncate and URLs remain available on hover or keyboard focus. The search row contains collection creation and search
- Request menus use plain, unboxed three-dot triggers and support rename, duplicate, and confirmed delete; collection menus use the same trigger and support rename, Postman export, and confirmed delete; icon-only triggers keep accessible labels and omit hover help to prevent lingering tooltips; duplicates receive a new ID and remain excluded from generation by default
- Row-level request checkboxes control generation eligibility; a collection checkbox controls all requests in that collection. Collection creation is the plus action beside search
- Contract import and flow discovery are visible actions in the collection navigator; discovery is disabled until a contract has been imported, and the active tool panel is shown in the playground column
- Expanded contract import and flow discovery panels place an accessible × close action in the title row; closing clears the active panel
- Test Cases generation combines per-run request selection and flow ordering in one list; all eligible request order persists through the project generation-order API
- Single generation sends all selected endpoints in one `/api/v1/test-cases/generate` request; the LLM prompt returns independent cases tagged with their source endpoint ID
- Each generated case stores the submitted business requirements in its JSON payload; the case editor lets users revise them, and selected generation examples pass those requirements into later prompts
- Test-case generation ignores rapid duplicate submissions per project to prevent queued Streamlit button clicks from issuing a second LLM request
- Request Playground has a repeatable Assertions tab for status, body text, JSONPath field values, and JSON Schema; saved requests persist assertion settings, Run All checks enabled assertions with one request, and individual Run checks one assertion with a fresh request
- Generated test and flow-step assertion editors use the same expandable assertion type groups, bordered rows, enable toggles, and add/remove styling as the Request Playground
- Generated single tests and flow steps expose editable JSON Schema response assertions, disabled with an empty schema by default; execution uses the shared Draft 2020-12 validator
- Generated single tests and flow steps expose editable method, URL, params, headers, and body fields; flows can add saved-request steps and reorder or remove steps
- Flow variable mappings are editable repeated source/destination/transform rows and execute into headers, query params, path placeholders, or body fields; query mappings are passed as request params
- The first flow step has no previous response, so its mappings are cleared and the editor hides mapping controls there; empty mapping placeholders on later steps are ignored by API validation
- Test-case edits stage in session until per-case Save changes upserts by stable ID; execution results persist when the executed HTTP request inputs match the saved case despite frontend assertion normalization, while unsaved request or flow mapping changes remain session-only; saving request/step changes clears stale execution results
- Contract import previews every endpoint from OpenAPI 3.x, Swagger 2.0, Postman Collection 2.1, and LLM-assisted prose docs; confirmed requests are saved to a selected project collection and remain generation-ineligible by default
- Contract endpoint review supports editing method, headers, query parameters, and payload; GET and DELETE imports omit payloads and body-field dependency targets
- Public documentation URL imports are anonymous, restricted to public HTTP(S) hosts, and limited to 5 MB; relative or unresolved endpoint bases are supplied in review
- OpenAPI/Swagger request and successful-response schema fields produce normalized exact-name dependency edges (underscore/case separators ignored, generic `id` excluded), with cycle evidence and ranked maximal executable paths
- Selected contract flow paths generate editable, named project scenarios with evidence-filtered JSONPath-to-body/path mappings and step assertions; `request.path.PARAM` mappings URL-encode into `{PARAM}` placeholders
- Contract operation/source metadata is stored in saved-request JSON; no schema migration is needed
- Desktop API Workspace keeps the request playground sticky without an internal scroll area while the document scrolls; on narrow screens the editor returns to normal flow
- Generation eligibility is managed with request-row and collection-row checkboxes plus project-wide bulk actions; eligibility and project flow order remain persisted separately
- Contract review uses side-by-side source/format controls and header/query editors, compact payload/source fields, and bounded dependency candidate lists and editors
- Meaningful completed actions show queued five-second Streamlit toasts with green success and red error accents (request/test-case saves, imports, generation, execution, collection/project changes); API failures retain detailed inline errors, while batch runs use one aggregate result toast
- Running a single test opens its Result tab; running a flow opens Scenario result. Batch execution focuses the first failed/errored case or the last case when all pass
- Test Cases supports manual single-case creation from a saved request and manual flow creation from a selected, ordered set of saved requests; new cases persist immediately by stable ID and open for editing
- Test Cases has a title-and-actions top bar with a prominent Add manual test action and a secondary Reusable runs action; popovers use numbered sections, brief guidance, and responsive sizing
- Named project test runs persist unique names and ordered case IDs in a project-scoped PostgreSQL table; loading restores case selection, updating replaces membership, and execution fetches each latest saved case payload
- Test run definitions are reusable selections rather than execution histories; deleted case IDs are ignored during execution and removed the next time the run is saved
- Test Cases selection toggles between Select all and Deselect all based on whether all singles and flows are checked
- Test Cases cards, toolbars, and reusable-run controls reflow to available width when the sidebar is expanded; request-order drag uses animated layout transitions with reduced-motion support
- Request-order dragging keeps the latest Streamlit callbacks, tracks the pointer through release, auto-scrolls at list edges, and cleans up listeners and styles on completion or unmount; Alt+Up/Down keyboard reordering updates the rank and screen-reader announcement
- Execution latency is formatted as milliseconds through 1000 ms and seconds above 1000 ms
- Test Cases collapses duplicate case IDs in session state to the latest payload before selection, grouping, or rendering to avoid duplicate cards and executions
- Generation accepts a separate project-scoped picker of existing case examples; the backend loads examples by ID, prompts use compact case context, and generated cases merge into the current list without replacing examples
- Test Cases filters combine reusable run, collection, endpoint, and result scopes; multi-collection flows appear once when a matching step qualifies and show all participating endpoint and collection provenance

## In Progress
- None

## Blocked
- None

## Next Steps (Post-MVP)
1. Add Postman environment, script, and authentication import
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
- Frontend: Streamlit (API Workspace, Test Cases, and Generation Activity tabs)
- LLM: Multiple free-tier APIs with automatic fallback (Groq, OpenRouter, Cohere, HuggingFace)
- Export/import: Postman Collection v2.1 export and request import; environment, script, and authentication import remain out of scope
- Contract discovery: maximal acyclic dependency paths are ranked by dependency-edge count descending, then endpoint method and path ascending
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
- Flow generation: no fixed scenario count; prompt prioritizes a small set of complete compact scenarios and backend hydrates endpoint references from canonical requests
- API Workspace drafts and quick-send results are session-only; saved requests are project-scoped collections
- Request row enabled flags control sending; generation eligibility is separate, persisted, and off by default for new requests
- API Workspace controls persistent generation eligibility; Test Cases controls per-run selection and ordering for eligible requests
- Flow request order is explicit and independent of collection display order
- Flow request order is stored per project, restored on project load, and filtered by relative order when a generation run selects a subset
- Named test runs are project-scoped ordered case-ID selections with case-insensitive unique names; they do not store case snapshots or execution results
- Generation examples are project-scoped saved case IDs, resolved server-side; examples guide style and coverage while the selected Single/Flow mode and requests define new output
- Generation activity is append-only and project-scoped; its table loads in the dedicated tab and each row opens a modal containing the full record, including prompt and model response
- Case-list run, collection, and endpoint filters combine across categories and use alternative matching among multiple selected values; a flow step must satisfy active endpoint and collection facets together
- Running a loaded named test run fetches the latest persisted case payloads before execution, while ordinary Run selected uses current in-session case content
- Postman Collection v2.1 export is available for saved collections; legacy endpoint routes use Imported Endpoints
- Existing endpoint rows migrate once into Imported Endpoints with IDs, fields, enabled state, inclusion choice, and order preserved
- Existing SQLite data is not automatically migrated; PostgreSQL initializes a fresh schema
- Local run: `make docker-db-up`, then `make run-local-backend` and `make run-local-frontend`
- Full Docker run: `make docker-up`, `make docker-logs`, and `make docker-down`
