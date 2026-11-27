# Agent Context - Api-Agent

## Project Status
Phase: Contract import, schema-based flow discovery, unified API Workspace
Mode: Act

## Completed
- Repository initialized (greenfield, Python .gitignore, README)
- Feasibility analysis completed
- Tech stack selected (FastAPI, python requests, Streamlit, free-tier LLM fallback)
- All project files created (documentation, backend, frontend, tests)
- Knowledge Hub: Implemented `KnowledgeHubPanel` for managing briefs, versioning, restoration, and drafting updates from chat threads.
- Test Case Management: Implemented `ManualCaseBuilder` (single cases/flows) and `TestRunManager` (reusable suites).
- Revisions: Implemented `RevisionDialog` to generate new release revisions based on prior successful generation activities.
- UI/UX: Created `Markdown` and `DiffView` components; enhanced `ActivityDetail` to support structured "generation" and "knowledge" streams.
- Infrastructure: Added typed API clients in `lib/hub.ts`, `lib/runs.ts`, and `lib/revisions.ts`.
- Integration: Wired the Knowledge Hub into the Chat page and the case builder/run manager/revision dialog into the Test Cases page.


- Virtual environment created and dependencies installed
- FastAPI app imports and starts correctly (all routes verified)
- PostgreSQL-backed unit and persistence tests pass (21/21)
- Backend smoke test passed (health, curl parse, generate, execute endpoints)
- Frontend syntax verified
- LLM providers: AMD Token Lab, OpenRouter, Groq (dynamic model), Cohere, Hugging Face; shared environment precedence defaults to AMD first. Provider failures log provider name and HTTP status when available before fallback; successful AMD metadata identifies the configured `AMD_MODEL`.
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
- Generation actions persist project-scoped activity records in PostgreSQL with requirements, endpoint summaries, exact LLM prompt and raw response, status, error, and generated case IDs; Activity Logs → Generation accepts paginated or legacy list responses and shows time, type, state, project, and a View details action
- Revision activity records retain prior requirements, prior release notes, new requirement changes, and cumulative case requirements; the detail modal displays these as separate labeled sections
- Test case CSV export sends only checked case/flow IDs to the project export endpoint; rows include case metadata, technique tags and requirement references as JSON arrays, source endpoint fields, request JSON cells, assertions, and `steps_json` for flow steps or General manual steps, while execution results and suite-level coverage summaries are omitted
- Project summaries and collection exports use a short-lived cache that is invalidated after relevant writes
- API Workspace uses a searchable, collapsible Postman-style collection tree beside the playground, headed by the active project name and a visible Collections label above the tree; collection and request eligibility checkboxes sit at the left edge, collection/request menus stay at the right, and request names open in the playground
- API Workspace desktop navigator uses a balanced responsive 270–320 px width and stacks above the playground below 760 px; request menu columns reserve enough width to keep their three-dot triggers on the same line, while request names truncate and URLs remain available on hover or keyboard focus. The search row contains collection creation and search
- Request menus use plain, unboxed three-dot triggers and support rename, duplicate, and confirmed delete; collection menus use the same trigger and support rename, Postman export, and confirmed delete; icon-only triggers keep accessible labels and omit hover help to prevent lingering tooltips; duplicates receive a new ID and remain excluded from generation by default
- Row-level request checkboxes control generation eligibility; a collection checkbox controls all requests in that collection. Collection creation is the plus action beside search
- Contract import and flow discovery are visible actions in the collection navigator; discovery is disabled until a contract has been imported, and the active tool panel is shown in the playground column
- Expanded contract import and flow discovery panels place an accessible × close action in the title row; closing clears the active panel
- Test Cases generation combines per-run request selection and flow ordering in one list; all eligible request order persists through the project generation-order API
- Single generation sends all selected endpoints in one `/api/v1/test-cases/generate` request; the LLM prompt returns independent cases tagged with their source endpoint ID
- Generation treats scenarios as independent by default; boundary values and different expected outcomes remain separate cases, while flows are reserved for real dependencies or journeys
- Cases store editable `technique_tags` (for example BVA) separately from `requirement_refs` (explicit requirement IDs or generated stable REQ labels); edits participate in saved-versus-session revision checks
- Generation responses and Activity Logs retain `coverage_summary`, mapping requirement references/status/gaps to case IDs and names, plus unsupported coverage claims; branch/statement coverage requires supplied source or logic evidence
- Revision and clarification prompts preserve baseline technique tags and requirement references when omitted by the model; revision coverage is finalized against the complete output suite including unchanged copies
- Selected-case CSV export includes JSON columns `technique_tags_json` and `requirement_refs_json`; suite-level coverage summaries stay in activity records
- Generation supports General requirements-only scenarios alongside Single, Flow, contract-discovered Flow, and Release Revision modes. General cases store ordered `manual_steps` under `case_kind: general` and contain no HTTP request/assertion/mapping data; testers record Passed/Failed as append-only manual history. Failed marks accept an optional `failure_reason`, display it as the case's assertion result, and retain it in history. HTTP batch execution skips these cases
- General cases carry project-scoped `case_collection_id`/`case_collection_name` metadata. `general_case_collections` persists named groups, including empty collections. The General generation form creates and selects a collection before generation or reuses an existing one; startup seeds groups from saved General cases. The existing Collections filter lists these groups without another filter. Legacy General cases use the default General scenarios collection
- All generation prompts request an envelope containing `test_cases` and optional `clarification_questions`; legacy LLM arrays normalize to an empty question list. Clarification entries are normalized from strings or objects containing a `question` and optional `context`. Users can answer questions through explicit project-scoped follow-up actions or dismiss a round; dismissal is persisted on the source activity and survives refresh. Successful non-revision follow-ups supersede source output in active workflows while retaining case records and execution history, and revision follow-ups create a new revision. Activities retain questions, answers, dismissal time, and replacement linkage
- All newly generated single cases and flows receive backend-generated UUID IDs across generation routes; model-provided IDs are ignored, while existing and manual case IDs stay stable
- Each generated case stores the submitted business requirements in its JSON payload; the case editor lets users revise them, and selected generation examples pass those requirements into later prompts
- Test-case generation ignores rapid duplicate submissions per project to prevent queued Streamlit button clicks from issuing a second LLM request
- Release revision baseline defaults to the still-saved generated case IDs associated with the selected source action and resets when that action changes; Select all includes every currently saved, non-superseded project case/flow, while Clear empties selection. Users may add/remove saved manual or generated cases; deleted cases stay excluded and selected unsaved edits block generation
- Revision endpoint selection is optional; revisions can be generated from the saved baseline and requirement context alone, including General scenario suites
- Release revision forms let users mark selected baseline cases as **Keep unchanged**. Those cases are copied unchanged with new IDs and source-case links, excluded from model input, and protected again during revision clarification rounds; all other selected baseline cases are sent to AI
- Successful non-revision clarification follow-ups atomically save linked cases, mark source cases with `superseded_by_activity_id`, and record `supersedes_activity_id` plus archived IDs. Superseded cases are excluded from active Test Cases, generation examples, revision baselines, suites, and execution while case records and execution history remain available
- Failed clarification follow-ups leave source cases active. Revision follow-ups create a distinct revision and never supersede prior revision cases. Activity Logs → Generation details show the replacement relationship, archived output IDs, and unchanged revision case links
- Revised cases and revision activity store cumulative generation requirements: prior business requirements, prior release notes not already represented, and current requirement changes; case/flow editors show this in a Generation requirements expander collapsed by default
- Revision endpoint selection is a collection tree over all currently saved project endpoints regardless of ordinary generation eligibility; all start selected, collection checkboxes toggle child requests, and the API resolves selected IDs to current saved method, URL, headers, query parameters, and body
- Generation activities and revisions retain full project endpoint snapshots with stable IDs and collection placement; comparison badges report added, unchanged, or modified fields (method, URL, headers, query parameters, body), ignore collection moves as request changes, and report unavailable for legacy actions without snapshots
- Revision UI puts baseline inclusion/save guidance in the selector tooltip and selected-case provenance/deleted-endpoint warnings in an expander; endpoint selection is a searchable collection popover with selected counts, collapsible request lists, bulk collection toggles, and concise change statuses
- Legacy endpoint-snapshot guidance is on the endpoint-picker tooltip; prior business requirements/release notes are read-only and new requirement changes are sent as separate context
- PostgreSQL stores revision labels, source activity, requirements, release notes, and ordered case membership; Test Cases defaults to the newest revision, supports individual/all-revision views, and keeps historical revisions read-only
- Execution history survives case edits; every run stores the exact executed case/flow snapshot, flow steps have stable IDs, and per-case History groups flow outcomes by step ID
- Flaky status is computed dynamically from the latest ten outcomes and requires at least three runs with both passes and failures or errors; the UI shows pass/non-pass counts as evidence
- Request Playground has a repeatable Assertions tab for status, body text, JSONPath field values, and JSON Schema; saved requests persist assertion settings, Run All checks enabled assertions with one request, and individual Run checks one assertion with a fresh request
- Generated test and flow-step assertion editors use the same expandable assertion type groups, bordered rows, enable toggles, and add/remove styling as the Request Playground
- Generated single tests and flow steps expose editable JSON Schema response assertions, disabled with an empty schema by default; execution uses the shared Draft 2020-12 validator
- Generated single tests and flow steps expose editable method, URL, params, headers, and body fields; flows can add saved-request steps and reorder or remove steps
- Flow variable mappings are editable repeated source/destination/transform rows and execute into headers, query params, path placeholders, or body fields; query mappings are passed as request params
- Release revision prompts constrain mappings to executable request destinations; unsupported LLM mapping targets are omitted and reported as UI warnings so they cannot block the revision
- The first flow step has no previous response, so its mappings are cleared and the editor hides mapping controls there; empty mapping placeholders on later steps are ignored by API validation
- Test-case edits stage in session until per-case Save changes upserts by stable ID; executions do not save case edits, but persist an immutable snapshot of the exact case/flow configuration that ran
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
- Test Cases has a title-and-actions top bar with a prominent Add manual test action and a secondary Test suites action; its popover loads, saves, updates, and deletes named suites
- Test suites persist unique names and ordered case IDs in the existing project-scoped test-runs table; loading restores selection, updating replaces membership, and execution fetches each latest saved case payload
- Test suite definitions are reusable case selections rather than execution histories; deleted case IDs are ignored during execution and removed the next time a suite is saved
- Test Cases selection toggles between Select all and Deselect all based on whether all singles and flows are checked
- Test Cases cards, toolbars, and reusable-run controls reflow to available width when the sidebar is expanded; request-order drag uses animated layout transitions with reduced-motion support
- Request-order dragging keeps the latest Streamlit callbacks, tracks the pointer through release, auto-scrolls at list edges, and cleans up listeners and styles on completion or unmount; Alt+Up/Down keyboard reordering updates the rank and screen-reader announcement
- Execution latency is formatted as milliseconds through 1000 ms and seconds above 1000 ms
- Test Cases normalizes legacy API envelopes and JSON-encoded case payloads, ignores malformed non-dictionary entries, and collapses duplicate IDs to the latest payload before selection, grouping, or rendering
- Generation accepts a separate project-scoped picker of existing case examples; the backend loads examples by ID, prompts use compact case context, and generated cases merge into the current list without replacing examples
- Test Cases filters combine test suite, collection, endpoint, and result scopes; multi-collection flows appear once when a matching step qualifies and show all participating endpoint and collection provenance
- Project Chat adds multiple PostgreSQL-persisted threads per project using shared LLM provider fallback; the app stores full ordered transcripts, latest model, per-assistant provider/model metadata, rolling summaries, and assistant-side endpoint source snapshots
- Chat requests retrieve up to eight saved endpoint summaries matching meaningful name, URL, or collection tokens; context uses a configurable recent-message count and character budget, summarizing older transcript messages as they leave the recent window without deleting them
- Project Chat stores durable context in a versioned Knowledge Hub: one project-wide page, feature pages, and reusable microservice pages. Chat turns do not extract facts. Users explicitly prepare separate page drafts and section diffs from a selected thread, review/edit them, then save selected pages together as immutable versions.
- Project Chat conversation and thread rail follow normal page scrolling. The message composer uses Streamlit's bottom-pinned container and stays visible while the user scrolls history; it appears only for an active, non-archived thread. The composer is right-aligned at two-thirds width on desktop and nearly full width on narrow screens, with one visible accent focus border. Assistant messages sit left in a muted bubble and user messages sit right in an accent-tinted bubble about two-thirds of the chat width, with a local timestamp above each and no role labels. Long messages are expanded by default and collapsible. Empty threads show a brief prompt above the composer.
- The Project Chat thread filter defaults to Active; archived threads remain available from the filter. The per-thread menu supports rename, archive/restore, and confirmed permanent deletion; deleting a thread removes its messages but preserves Hub pages and generation activity.
- Project Chat tab sits beside Test Cases and Activity Logs; Chat uses a compact left thread list, endpoint/Hub sources, and Conversation / Knowledge Hub views. The Hub supports feature-to-microservice many-to-many links, scrollable current-page and draft-review panels, GitHub-style diffs, and an editable Markdown preview; version history invalidates after updates and restore appends a new version.
- Generation always includes the current project page. Selecting feature pages automatically includes their linked microservice pages. Run-specific Business requirements remain separate and never update saved knowledge. Activity Logs and cases record the exact page versions and contents used.
- `docs/persistent_context.md` documents the chat-to-Hub workflow, explicit draft/review/save process, migration, generation context, provenance, and tradeoffs.
- `make docker-db-reset` requires typing `RESET`, deletes only the current Compose project's PostgreSQL volume, then rebuilds and starts the stack; backend initialization recreates the schema and built-in Default Project. `make docker-down` preserves the database volume
- PostgreSQL still retains pre-Hub submissions, facts, questions, and append-only extraction events for history. Chat messages no longer create submissions or extraction events. Existing active approved/assumed facts and legacy thread briefs are copied once into current Hub page versions with source IDs; original records remain unchanged. Pending or unapproved legacy data is excluded from current context.
- Hub drafting runs only after the explicit **Prepare knowledge update** action. It uses the selected thread and current destination pages to create one draft and section-level diff per page; it does not save automatically. Reviewers can retain uncertainty in a labeled **Open questions** section and save selected pages atomically.
- The Hub uses the existing `project_brief_scopes` and `project_brief_versions` tables as logical page/version storage, plus `knowledge_hub_feature_services` for many-to-many feature/service links. Restore appends a new immutable version.
- Single, Flow, General, contract-discovered Flow, Release Revision, and follow-ups carry exact Hub version references/content snapshots into case payloads and Activity Logs → Generation. Project-wide knowledge is always included; selected feature pages include linked microservices. Run-specific requirements remain separate from Hub content.
- Chat answers should be direct and omit generic unsolicited “next steps” lists.
- Frontend split into `frontend/core.py` (shared state, API clients, helpers), `frontend/views/*` (one module per workspace mode), and `frontend/styles/*` (design tokens plus CSS blocks); `frontend/app.py` is now a thin entry point
- Postman-style light shell: `--aa-*` tokens injected once, left-rail mode switcher replacing top-level tabs, dense surfaces and typography, visible focus rings, and reduced-motion support
- Fixed regressions from the extraction: restored `_toggle_session_state` (deleted with the CSS slice),
  removed the stale `API_BASE` reference, and made the views import `frontend.core` absolutely so package
  imports work under pytest
- Test-case toolbar uses one merged Expand/Collapse toggle; Export CSV is a single `st.link_button` that
  streams from the backend export route, because this Streamlit version does not accept a callable for
  `st.download_button(data=...)` and a second widget was not wanted
- Frontend test suite is green (20/20); remaining suite failures are the pre-existing PostgreSQL-backed storage, contract, and provenance tests
- Collections rail: HTTP-method filter, `enabled of total` project counter, and honest collection state
  (`total` when fully enabled, `enabled/total (partial)` when partly, `0/total` when none) because a checkbox
  cannot express indeterminate selection
- Removed the eager Postman-export prefetch from the collection kebab: popover bodies render on every rerun,
  so it was one extra API call per collection per interaction. The action is now an on-demand download link
- Request editor gains an Auth tab (Bearer token, Basic auth, API key) whose header is materialised at
  send time and never overrides an explicit header row
- Body mode is a segmented No body or Raw control with live Content-Type and JSON validity feedback
- Unsaved edits are tracked from a canonical signature, so opening a saved request stays clean; the tab
  strip shows a leading asterisk and the editor shows a caption until the draft is saved
- Playground assertion results render as a compact Test Results table
- Test-case card Delete moved from the footer into a per-card kebab in the header, away from Save
  changes; the delete key is unchanged so saved selections and run references keep resolving
- Frontend GET/DELETE/PUT read timeouts remain scoped (15/30/60 s); POST requests allow up to 1,200 s (20 minutes) for long-running generation
- The app uses one light palette; there is no sidebar theme control or persisted theme choice
- Added `frontend/styles/theme.py` to re-point native surfaces (toolbar, popover, tooltip, toast,
  segmented pill, slider, progress, spinner, tab highlight, notices) at the palette tokens
- Sticky test-case toolbar, sticky-safe responsive breakpoints, and a
  contrast-corrected muted text token
- Generation now reports progress through `st.status` with a terminal state instead of a bare
  spinner

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
- Frontend: Streamlit, single page with a left-rail mode switcher (API Workspace, Test Cases, Project Chat, Activity Logs); Activity Logs contains Generation and Knowledge Extraction subviews; styles in `frontend/styles`, views in `frontend/views`
- Frontend theme: light only, configured in `.streamlit/config.toml`; `Dockerfile.frontend` copies that config into the image, and `frontend/styles/light.py` forces the browser color scheme to light so system dark preferences do not recolor native controls
- LLM: Shared fallback across AMD Token Lab, OpenRouter, Groq, Cohere, and Hugging Face. `LLM_PROVIDER_ORDER` defaults to `amd,openrouter,groq,cohere,huggingface`; missing-key providers are skipped, API failures fall through, and malformed application output does not trigger another provider call. AMD uses `AMD_API_KEY` and reads `AMD_MODEL` per request (default `Gemma-4-31B-IT`); successful provider/model metadata is stored in activity and chat records
- Project Chat: Multi-message completion uses the shared provider order on every call; the thread's stored model is descriptive metadata rather than a provider pin. `PROJECT_CHAT_RECENT_MESSAGES` and `PROJECT_CHAT_CONTEXT_CHAR_BUDGET` bound context
- Knowledge Hub drafting: `PROJECT_BRIEF_DRAFT_CHAR_BUDGET` bounds selected transcript, summary, and current-page content; default is 48000
- Legacy Knowledge submissions/facts/events remain for compatibility and audit history. Current durable product context uses versioned project, feature, and microservice Hub pages.
- Project chat is app-persistent rather than provider-thread-persistent: full messages are in PostgreSQL and older turns are summarized. Generation receives the current project page, selected features and linked services, run-specific requirements, and selected endpoints/baseline, not the full transcript; activity stores exact versions used
- Export/import: Postman Collection v2.1 export and request import; environment, script, and authentication import remain out of scope
- Contract discovery: maximal acyclic dependency paths are ranked by dependency-edge count descending, then endpoint method and path ascending
- Code style: Minimal functions, flat structure, easy to read
- Assertions: Repeatable list-based instances per test or flow step (status, body contains, JSONPath); legacy single-dict configs remain supported
- Request playground assertions are repeatable saved-request JSON data (status, body contains, JSONPath, response schema); schema validation uses JSON Schema Draft 2020-12 and single assertion runs ignore the Run All enabled checkbox
- Generated single-case and flow-step assertion data supports repeatable response_schema entries; generation adds a disabled blank entry when the LLM omits one, and users can edit it in the Test Cases workspace
- Test case cards: Collapsible via st.expander
- Console logging: st.iframe with console.log
- Frontend POST API timeout: 1,200 seconds (20 minutes), including LLM generation; GET/DELETE/PUT timeouts remain 15/30/60 seconds
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
- Test suites are project-scoped ordered case-ID selections with case-insensitive unique names; they do not store case snapshots or execution results and use the existing test-runs API/storage model
- Generation examples are project-scoped saved case IDs, resolved server-side; examples guide style and coverage while the selected Single/Flow mode and requests define new output
- Release revisions are project-scoped immutable suite memberships based on the latest saved case configurations and optionally selected current endpoint definitions. Prior requirements, carried-forward prior release notes, and new requirement changes remain distinct prompt context; each baseline case must be represented once, and revised cases link through `source_case_id`
- New generation activity and revision records include a snapshot of all project endpoints, not only the endpoints selected for that generation action, so later revisions can identify endpoints added or modified since that point
- Flakiness is not persisted as a flag; calculate it from up to ten newest case/step outcomes, requiring at least three observations and a mix of pass and non-pass outcomes
- Execution history is append-only for case updates and contains each executed configuration snapshot; flow step results carry stable `step_id` values
- Manual general-case result marks use the same append-only execution history and count toward dynamic flaky status
- Activity Logs is the top-level workspace with Generation and Knowledge Extraction subviews. Generation is append-only and project-scoped; each row opens a modal containing the full record, including prompt and model response. Knowledge Extraction combines append-only `extracted` and `extraction_failed` events joined to retained source submissions with Knowledge Hub page creation, feature-service link changes, draft preparation/failure, reviewed saves, and version restores. Extraction details include retained source and model output; Hub draft details include exact prompt messages, raw model response, provider/model metadata, thread, and page; save/restore details include page version/content. Chat turns do not automatically create extraction events. Older extraction events may lack prompt, response, or provider metadata snapshots.
- Both Activity Logs views use paginated summary endpoints and load full event details on demand. Knowledge Extraction has dedicated `/knowledge/activity` and `/knowledge/activity/{event_id}` routes, so large prompts and responses are not loaded for every table row.
- Case-list run, collection, and endpoint filters combine across categories and use alternative matching among multiple selected values; a flow step must satisfy active endpoint and collection facets together
- Running a loaded test suite fetches the latest persisted case payloads before execution, while ordinary Run selected uses current in-session case content
- Postman Collection v2.1 export is available for saved collections; legacy endpoint routes use Imported Endpoints
- Existing endpoint rows migrate once into Imported Endpoints with IDs, fields, enabled state, inclusion choice, and order preserved
- Existing SQLite data is not automatically migrated; PostgreSQL initializes a fresh schema
- Local run: `make docker-db-up`, then `make run-local-backend` and `make run-local-frontend`
- Fresh local Compose database: `make docker-db-reset` (destructive; requires typing `RESET`)
- Full Docker run: `make docker-up`, `make docker-logs`, and `make docker-down`

## UI revamp pass

### Completed
- Single light workspace enforced at both layers: native theme plus `--aa-canvas`.
- Surface and edge tokens keep every card, input, expander, grid frame, and menu
  visible on the pale canvas.
- Native text, number, date, textarea, select, and upload controls use a stronger
  always-visible edge, with an accent focus ring; inner text fields stay borderless
  so each control reads as one clean surface in the light theme.
- The sidebar project selector has an explicit rail-scoped outline, hover edge,
  and focus ring so its boundary remains visible against the sidebar.
- Project Chat composer and segmented controls use readable light-theme edges and ink.
- `styles/surfaces.py`, `styles/layout.py`, `styles/rail.py` added; layout CSS left
  the views, and a dangling CSS fragment from an earlier edit was removed.
- Chat rebuilt: conversation rail with search and filter, asymmetric shaded
  message bubbles with local timestamps, one Sources disclosure, status-reported send,
  and a peer Knowledge Hub view with page history, diffs, links, and reviewed multi-page updates.
- Project Chat scrolls to the newest assistant reply after send. Long messages are expanded by
  default; their label is visually hidden and the disclosure caret remains the collapse control.
- Release revision moved to a modal opened from Test Cases, so its project and
  activity fetches no longer run on every rerun.
- Generation activity reports a true total via `COUNT(*)` and has a pager with
  boundary-safe offset.

### Decisions
- One native light theme is used across Streamlit widgets and app-owned surfaces.
- Accent ink is dark; white measures 2.8:1 on the orange.

### Known limitations
- No true overlay drawer in Streamlit; chat and revision detail use columns and
  modals. A docked drawer needs the React path.

## Frontend Migration: Next.js and TypeScript (In Progress)

### Status
- Scaffolded a Next.js App Router application under `web/` with TypeScript, Tailwind CSS, and an accessible design foundation.
- Added `web/Dockerfile` for a multi-stage standalone production build.
- Extended `docker-compose.yml` with a `web` service on port 3000 and kept Streamlit as `frontend-legacy` on port 8501.
- Updated the `Makefile` with `install-web`, `run-local-web`, and revised `setup` commands.

### Connectivity
- The Next.js app proxies `/api/v1/*` to FastAPI through authenticated Route Handlers, using `BACKEND_URL` (default `http://localhost:8000`).
- `web/src/lib/api.ts` is a typed same-origin fetch client; bearer tokens remain in HttpOnly cookies and are added only by the server handler.
- `ProjectProvider` in `web/src/context/ProjectContext.tsx` lists projects from `GET /api/v1/projects` and exposes the selected project to every workspace view.

### Shared Design System
- Ported the light palette from `frontend/styles/tokens.py` into `web/src/app/globals.css` as CSS custom properties.
- Mapped semantic tokens to Tailwind names: `canvas`, `rail`, `panel`, `panel-alt`, `elevated`, `overlay`, `hover`, `active`, `line`, `text`, `text-dim`, `text-mute`, `accent`, `ok`, `warn`, `bad`, and `info`.
- Preserved radius spacing for parity with the Streamlit UI.

### Migrated Views
- **API Workspace** (`web/src/app/workspace/api/page.tsx`): cURL parsing, request composer, execution, and response viewer.
- **Test Cases** (`web/src/app/workspace/test-cases/page.tsx`): Single, Flow, and General generation, saved case list, HTTP execution, and manual outcomes.
- **Project Chat and Knowledge Hub** (`web/src/app/workspace/chat/page.tsx`): thread rail, message transcript, reviewed page updates, version history, diffs, and a pinned composer.
- **Activity Logs** (`web/src/app/workspace/activity/page.tsx`): paged generation and Knowledge Extraction activity in a table with details.
- **API imports** (`web/src/app/workspace/api/page.tsx`): reviewed file/text/URL endpoint previews and collection import.

### Verification
- `tsc --noEmit` passes with zero errors.
- `npm run lint` passes with zero warnings and zero errors.
- `npm run build` compiles every App Router route in Turbopack.
- Corrupted escaped-quote sequences fixed in KnowledgeHubPanel.tsx, Sidebar.tsx, and primitives.tsx.
- Unused imports removed: `prettyPayload` (activity/page.tsx), `truncate` (ActivityDetail.tsx), `Tooltip` (KnowledgeHubPanel.tsx), `PageRowDeleted` function (KnowledgeHubPanel.tsx).

### UI polish completed
- Scrollable excluded-APIs list uses a compact height-bounded region.
- Modal click-outside close: Modal component handles backdrop click via `onMouseDown` target check.
- Sidebar collapse wiring: collapse button toggles `setCollapsed` state; width switches between `w-16` and `w-64`.
- Theme persistence: ThemeProvider reads/writes `aa-theme` localStorage; DEFAULT_THEME is `light`; boot script applies stored preference before first paint.

### Deferred
- Playwright smoke coverage and removal of the legacy Streamlit service.

## Web frontend status
... [rest of the content] ...

## Web frontend status

The Next.js app in `web/` is the migration target, not the default UI yet.

- Migrated: `/workspace/api` (draft tabs, collections, cURL parse, request editor, assertions, response inspector, Postman export, and reviewed imports) and `/workspace/test-cases` (Single, General and Flow generation, clarification, revisions, execution history, suites, and CSV export).
- Migrated: `/workspace/chat` (thread management, transcript, source details, reviewed Knowledge Hub updates and versioning) and `/workspace/activity` (two streams, table summaries, pagination, and detail view).
- One token source: `web/src/app/tokens.css` is generated from `frontend/styles/tokens.py` by `scripts/gen_tokens.py`. Light is the first-visit default; the user's theme preference persists.
- Generated contracts: `scripts/gen_types.py` writes `web/openapi.json` and `web/src/types/api.generated.ts`. Response types stay hand written because the routes return dictionaries without `response_model`.
- Lazy backend: `app.main` builds the repository through `get_database()` on first use, so it imports without PostgreSQL.
- Verified: `npm run lint` clean, `npm run build` green, `pytest tests/test_theme_tokens.py tests/test_frontend.py` 33 passed.

### Remaining before cutover

- Remove `frontend/` and `Dockerfile.frontend` only after parity and deployment checks pass.

- Streamlit is now optional at runtime: the legacy service is behind the compose profile `legacy` and starts only with `make docker-legacy`. Every surface exists in `web/`.
- `next start` is incompatible with `output: "standalone"`; use `make serve-web`, which stages `.next/static` (and `public` when present) into the standalone directory before running it.

## Next.js Workspace UX and Local Authentication (2026-11-27)

- Next.js is protected by a single configured local account. Set `AUTH_USERNAME`, `AUTH_PASSWORD`, and a random `AUTH_JWT_SECRET` (at least 32 characters) in `.env`. FastAPI protects `/api/v1/*` except health and auth endpoints. Access tokens last 15 minutes; refresh tokens last 30 days, are stored hashed in PostgreSQL, and rotate on refresh.
- Next.js keeps credentials in HttpOnly cookies and forwards API requests through `web/src/app/api/v1/[...path]/route.ts`; do not restore direct `/api` rewrites. Streamlit keeps tokens in server-side session state. Both frontends share the same account. This is not multi-user authentication.
- `AuthGate` always renders workspace route children under an opaque, inert session-check overlay so Next.js instant-navigation validation can inspect each page; the backend remains the authorization boundary.
- The `/` route redirects to `/workspace`; navigation marks Home active only on the exact workspace landing route. Activity detail separates Summary, Evidence, LLM prompt, raw LLM response, and Raw JSON, displaying `N/A` for missing scalar and payload values.
- In collapsed navigation, the project icon opens a searchable project-selection modal and navigation icons expose their names on hover. Activity Evidence lays out each coverage gap and clarification as a labeled card with status, detail/context, and answer state.
- Test case cards show a green or red left-edge marker for the latest pass/fail result. General cases have direct Pass and Fail actions that open a confirmation dialog; the failure reason is optional and appears only for Fail, with each outcome retained in execution history.
- Expanded Flow and General case cards separate the overview from a numbered, ordered Test process. Case action menus render in a viewport portal so card overflow cannot clip them.
- API Workspace's **Generate eligible** action opens Test Cases with enabled endpoints selected; excluded endpoints are hidden from the generation picker. Selected Flow endpoints can be dragged to reorder, and the project generation order is updated. Requirements-only General generation does not require endpoints.
- API Workspace success, error, and informational feedback notices clear themselves after three seconds.
- API Workspace collection groups expand and collapse independently. Their selection checkbox, enabled/total count, and action menu remain visible while request rows are collapsed.
- Light is the first-visit theme; the selected theme persists in localStorage. Sidebar collapse state persists as well. The collapsed rail retains navigation icons, Home, project selection, theme toggle, and sign-out. Mobile navigation exposes sign-out in the header.
- API Workspace imports JSON/YAML OpenAPI or Swagger, Postman JSON, Markdown, TXT, PDF, DOCX, and public documentation URLs. The user reviews endpoints and selects a destination collection before import. Uploads are limited to 5 MB, extracted text to 5 MB, and PDFs to 500 pages; `pypdf` is required for PDFs.
- Activity uses a table with a bottom page-size/pagination row and a detail dialog. The Knowledge Hub lists every page with type, total versions, latest version/time, and actions. Release revision input is labeled **New requirement changes** while retaining the existing API payload field for compatibility.
- The Test Cases endpoint-exclusion chooser is height-bounded and independently scrollable. Markdown tables use GFM and horizontal overflow. Menus dismiss on outside click or Escape. Important request, generation, import, and revision inputs have contextual tooltips.
- LLM-backed requests use 20-minute timeouts in the Python provider client and Next.js browser API client. Keep these aligned with any proxy/server timeout configured by a deployment platform.
- Local backend and Streamlit Make targets use `python` from the caller's active environment; activate `.venv` before running them. Dependency installation, test, and Docker targets keep their existing behavior.
- `technical_documentation.md` documents auth token lifetimes/storage, the BFF flow, file import limits, and current UX behavior. `README.md` contains local auth configuration and supported import formats.
