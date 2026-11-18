# Api-Agent

Api-Agent is a local workspace for building API requests, generating tests with an LLM, and running those tests against an API. Organize requests into project collections, import endpoints from API contracts, and build multi-step flows that pass values such as an authentication token between requests.

## At a glance

- **Compose and send requests:** Create temporary request tabs, edit methods, URLs, query parameters, headers, and bodies, or paste cURL into the URL field. Recognized cURL is parsed automatically after three seconds without typing.
- **Check responses in the playground:** Add repeatable status, body text, JSONPath field-value, and JSON Schema assertions. Run all enabled checks with one request or run an individual check.
- **Import API definitions:** Review endpoints from OpenAPI 3.x, Swagger 2.0, Postman Collection 2.1, Markdown, prose, or a public documentation URL. Edit request details before saving them into a collection.
- **Discover dependent flows:** For OpenAPI and Swagger contracts, find normalized response-field matches in downstream path or body fields, review the evidence, and ask the LLM to turn selected paths into named scenarios. Generic `id` matches are ignored.
- **Generate test cases:** Choose eligible saved requests, reorder them, and generate independent Single tests, sequential Flows, or requirements-only General scenarios. General scenarios can be assigned to a saved project collection or a newly created collection before generation. Mark a General scenario **Failed** with an optional failure reason; it appears as its assertion result and is retained in execution history. Newly generated cases and flows receive backend UUIDs; existing saved and manual case IDs remain unchanged.
- **Edit and execute tests:** Update generated requests, flow steps, mappings, and assertions. Run one case or a selected batch, inspect request and response details, and save changes to the project.
- **Create manual tests:** Start a single test from any saved request or assemble a flow from an ordered set of saved requests, then edit the case in the Test Cases workspace.
- **Create test suites:** Name and save a selection of cases, reload it later, adjust membership, update it, or execute it using the latest saved case versions.
- **Review activity logs:** Open **Activity Logs** and choose **Generation** to revisit requirements, included endpoints, the prompt, raw LLM response, clarification rounds, and archived output. Choose **Knowledge Extraction** to browse historical extraction attempts and Knowledge Hub activity, including draft prompts/responses, saved page versions, restores, and feature-to-microservice link changes.
- **Discuss and curate project knowledge:** Project Chat stores project-scoped conversations and current Knowledge Hub pages. Chat turns do not trigger extraction. After discussing and clarifying a topic, choose **Prepare knowledge update**, select project, feature, or microservice pages, review each draft and GitHub-style section diff, edit with a Markdown preview, then save selected page versions together. The current page and draft review have independent scroll areas; the chat composer stays near the bottom while scrolling. Assistant replies align left and user replies right with local timestamps. Long messages can be collapsed. Active threads show by default; archived threads can be restored or permanently deleted from the **⋯** menu.
- **Handle clarification questions:** Answer them and choose **Refine generated cases** to request another version, or choose **Dismiss** to keep the current output and hide that question round. Dismissal is saved with the generation activity and remains effective after refresh.
- **Organize the Knowledge Hub:** Keep shared rules in the project-wide page, then create feature and microservice pages. Link multiple microservices to a feature; reuse a microservice across features. Each page has immutable versions, section-level change history, and restore-as-new-version. Existing briefs and approved facts are retained and migrated into page history/content with source identifiers.
- **Generate from selected knowledge:** Generation always includes project-wide knowledge. Select feature pages and their linked microservice pages are included automatically. **Business requirements for this generation** remains run-specific and is recorded with the exact Hub versions, endpoint snapshot, prompt, and response; it never changes saved knowledge by itself.
- **Revise a release suite:** Start from a prior generation action, carry forward existing generated or manual cases, keep prior requirements as read-only context, add new requirement changes, and optionally select current endpoints from every collection. Choose **Keep unchanged** for cases to copy into the complete new suite without AI edits. A saved baseline can be revised without endpoint selection; full endpoint snapshots show added or modified request definitions. Each revision is saved separately.
- **Track execution history:** Each case has a History view with the configuration snapshot used for every run. Flow history also groups outcomes by stable step ID. A case, flow, or step is marked flaky when at least three of its latest ten runs include both passes and failures or errors.
- **Keep project data:** Projects, collections, saved requests, test cases, named runs, execution history, and generation activity are stored in PostgreSQL. Temporary playground tabs and unsaved edits remain in the Streamlit session.

The frontend is built with Streamlit, the API with FastAPI, and request execution uses Python `requests`. LLM providers include AMD Token Lab, OpenRouter, Groq, Cohere, and Hugging Face; the backend tries configured providers in `LLM_PROVIDER_ORDER` and records which provider/model answered.

## Typical workflow

For the full lifecycle from project chat to reviewed, versioned Knowledge Hub pages and generation context, see the [Project Chat and Knowledge Hub guide](docs/persistent_context.md).

1. **Create or select a project** in the sidebar. Open **Project actions**, enter a project name and optional description, and choose **Create project**; the new project becomes active. Create a collection to organize saved requests.
2. **Add requests** in API Workspace. Compose them manually, paste cURL into the URL field, or use **Import** in the collection navigator. Review and save requests to a collection.
3. **Organize requests** in the compact, collapsible Collections browser. Click a request name to open it, hover or focus it to view its URL, use its three-dot menu to rename, duplicate, or delete it, and use a collection menu to rename, export, or delete that collection.
4. **Choose generation eligibility** in the Collections browser. New requests are excluded by default; use the checkbox beside a request to include it, or the checkbox beside a collection to include or exclude all requests in that collection.
5. **Choose and order requests** in Test Cases. Check requests for this run and drag them into the desired order. The project order is saved and used by future flow generation.
6. **Generate tests.** Select **Single** for independent request cases or **Flow** for sequential scenarios. Add business requirements when useful.
7. **Review and run cases.** Expand a case to edit its request, assertions, or flow steps. Run it to open its result view. Save edits to persist them to the project.
8. **Discuss project context.** In Project Chat, use the compact left thread list to start a chat or reopen its history; each thread has rename and archive actions. Discuss product rules, workflows, integrations, and uncertainties. Chat uses the thread history and matching saved endpoints.
9. **Discuss and clarify.** In Project Chat, explain product rules, workflows, integrations, and uncertainties. Chat history is retained, and current Hub pages appear as grounded sources when relevant. There is no extraction call after each message.
10. **Prepare a Hub update.** Select **Knowledge Hub**, create or choose project-wide, feature, or microservice pages, and link the microservices used by each feature. Return to the conversation, ask for any missing information, then choose **Prepare knowledge update**. Review and edit each page draft and its section changes. Save the selected pages together; retain uncertain details in a labeled **Open questions** section. Nothing is durable until saved.
11. **Generate with selected context.** In Test Cases, project-wide knowledge is included automatically. Select feature pages; their linked microservices are included automatically. Enter **Business requirements for this generation** for action-specific guidance. The model receives saved Hub pages and generation data, not the full chat transcript. Activity and cases retain the exact page versions used.
12. **Create a test suite.** Add manual single tests or flows from saved requests when needed. Select the cases to include, enter a suite name, and save. Later, load that suite, change its selection, and choose **Update suite** or **Run selected**. Suites keep an ordered list of case IDs and execute the latest saved version of each case.

## Set up and run

### Requirements

- Python 3.11 or newer
- Docker Desktop with Docker Compose, for PostgreSQL or the full Docker run
- An API key for at least one supported LLM provider to generate test cases

### Install

```bash
make setup
cp .env.example .env
```

Edit `.env` and add at least one provider API key. Set the PostgreSQL values for local application processes. Keep `.env` private; it is excluded from Git.

```dotenv
AMD_API_KEY=your_amd_token_lab_api_key
AMD_MODEL=Gemma-4-31B-IT
LLM_PROVIDER_ORDER=amd,openrouter,groq,cohere,huggingface
GROQ_API_KEY=your_groq_free_tier_key
OPENROUTER_API_KEY=your_openrouter_api_key
OPENROUTER_MODEL=nvidia/nemotron-3-ultra-550b-a55b:free
COHERE_API_KEY=your_cohere_free_tier_key
HUGGINGFACE_API_KEY=your_huggingface_free_tier_key
DATABASE_URL=postgresql://api_agent:change_this_local_password@localhost:5432/api_agent
POSTGRES_DB=api_agent
POSTGRES_USER=api_agent
POSTGRES_PASSWORD=change_this_local_password
API_AGENT_LLM_MAX_OUTPUT_TOKENS=6000
PROJECT_CHAT_RECENT_MESSAGES=12
PROJECT_CHAT_CONTEXT_CHAR_BUDGET=24000
PROJECT_BRIEF_DRAFT_CHAR_BUDGET=48000
```

Configure one or more provider keys. `LLM_PROVIDER_ORDER` controls precedence; its default tries AMD Token Lab, OpenRouter, Groq, Cohere, then Hugging Face, skipping providers without keys. Set `AMD_MODEL` in `.env` to choose the AMD model (default `Gemma-4-31B-IT`); `OPENROUTER_MODEL` and `API_AGENT_LLM_MAX_OUTPUT_TOKENS` configure their respective provider/output limit. Generation, Project Chat, and Knowledge Hub model calls share this fallback. A provider/API failure advances to the next provider; malformed generated JSON is reported without another model call. Activity records and chat replies retain provider/model metadata. Normal chat turns do not trigger a separate extraction call. `PROJECT_CHAT_RECENT_MESSAGES` controls recent messages sent with the rolling summary. `PROJECT_CHAT_CONTEXT_CHAR_BUDGET` bounds chat turns; `PROJECT_BRIEF_DRAFT_CHAR_BUDGET` bounds multi-page Hub drafting. Full transcripts and page versions remain in PostgreSQL. Compose sets the backend database host to `postgres`; local processes normally use `DATABASE_URL` with host `localhost`.

### Run locally

Start PostgreSQL, then start the backend and frontend in separate terminals:

```bash
make docker-db-up
```

```bash
make run-local-backend
```

```bash
make run-local-frontend
```

Open [http://localhost:8501](http://localhost:8501). FastAPI's interactive API documentation is at [http://localhost:8000/docs](http://localhost:8000/docs).

### Run the full stack in Docker

```bash
make docker-up-build
make docker-logs
```

Use `make docker-up` for subsequent starts with the built images; it skips image builds. Run `make docker-up-build` after changing application code, dependencies, or Streamlit configuration. The frontend image includes `.streamlit/config.toml` so its native theme stays light regardless of the host system preference. Docker caches pip downloads across dependency rebuilds, and application source is copied after dependency installation so source-only edits reuse the installed dependency layers. Open [http://localhost:8501](http://localhost:8501). Stop services with `make docker-down`; PostgreSQL data remains in the `api_agent_pgdata` volume.

To permanently erase this Compose project's PostgreSQL data and start with the current schema, run `make docker-db-reset` in an interactive terminal and type `RESET` when prompted. This removes all saved projects and their requests, cases, run history, chat, Knowledge Hub pages, and generation activity. It rebuilds and starts the stack; backend initialization creates the tables and built-in Default Project with its project-wide page. It does not target a local process configured with `DATABASE_URL` or an external PostgreSQL volume. See the [full context and database guide](docs/persistent_context.md) for how context is stored and used.

If a host port is already in use, set `POSTGRES_PORT`, `BACKEND_PORT`, or `FRONTEND_PORT` in `.env`. For local app processes, keep the port in `DATABASE_URL` aligned with `POSTGRES_PORT`.

## How to use the workspace

### Projects, collections, and requests

Select or create a project in the sidebar. In API Workspace, the compact collection navigator is headed by the active project name, stays beside the playground on desktop, and stacks above it on narrow screens. **Import** and **Discover** open contract tools, and the plus beside search creates a collection. Use the × in an open contract panel’s title row to dismiss it. Search filters collection names, request names, and URLs, and the method filter narrows the tree to GET, POST, PUT, PATCH, or DELETE requests. An enabled-of-total counter under the search box summarises generation eligibility for the project. Expand a collection to browse its indented requests, which are linked visually to their parent by a subtle tree guide. The checkbox at the left of a collection controls generation eligibility for every request in it; request checkboxes control individual eligibility. A partly enabled collection shows enabled/total (partial) beside its name, so an unchecked box is not mistaken for a fully excluded collection. Request names are truncated to fit, show the URL on hover or keyboard focus, and open the request in the playground when clicked. Plain, unboxed three-dot menus provide request rename, duplicate, and delete actions, and collection rename, Postman export download, and delete actions. Export downloads the collection only when you click it, so browsing the tree does not issue export requests. A saved request belongs to a project collection; an open request tab is a temporary draft until saved.

The playground supports manual request editing or cURL import. Paste or type a one-line or multiline command beginning with `curl` into the URL field and pause for three seconds; the frontend parses recognized commands automatically. Regular URLs are not parsed as cURL. Review the method, URL, query parameters, headers, and body before sending or saving. Contract imports omit payloads from GET and DELETE requests.

Use **Send** for request-only execution. To check a response, open **Assertions** and add any number of checks:

- **Status:** expected HTTP status code.
- **Body contains:** text that must appear in the response body.
- **Field value:** JSONPath plus the expected value.
- **Response schema:** a JSON Schema document used to validate a JSON response.

An **Auth** tab holds Bearer token, Basic auth, or API key credentials. They stay with the request and become the header only when it is sent; an explicit header on the Headers tab still wins. **Body** offers No body or Raw and reports the effective Content-Type plus whether the text parses as JSON. A request tab prefixed with an asterisk has unsaved edits, and the editor shows a matching caption.

Each assertion has an enabled checkbox. **Run All** sends one request and evaluates every enabled assertion; an individual **Run** sends a fresh request for that assertion even when it is disabled for Run All. The response panel shows status, latency, payload size, Pretty or Raw body, headers, and a Test Results table with one row per assertion.

### Import contracts and discover flows

Use **Import** in the collection navigator. Provide pasted text, upload a file, or enter a public documentation URL. Structured formats include OpenAPI 3.x, Swagger 2.0, and Postman Collection 2.1; prose extraction is an LLM-generated proposal. Review the discovered endpoint list, edit methods and request data, choose a destination collection, provide a base URL if needed, and confirm import. Use **Discover** beside it to analyze imported OpenAPI/Swagger dependencies and generate scenarios from selected candidate paths.

Imported requests are excluded from generation until enabled. Open **Discover flows from imported contracts** to analyze OpenAPI/Swagger field dependencies. The graph shows matching response and request fields as evidence; cycles remain visible but are omitted from executable paths. Select candidate paths and generate named flow cases with optional business context.

Anonymous URL imports are limited to public HTTP(S) hosts and documents up to 5 MB. Authenticated documentation must be pasted or uploaded. Postman environments, scripts, and authentication settings are not imported.

### Generate and organize test cases

Use the request or collection checkboxes in API Workspace to set persistent generation eligibility. In Test Cases, use the integrated draggable request list to choose requests for the current run and set their order. All eligible requests can be reordered; checked requests are used in the current generation run. The project order persists across reloads.

Each test case row has **Run** on the right and a three-dot menu holding **Delete test case**. Delete
is kept apart from **Save changes** on purpose: the two are a single click apart at the end of a card
otherwise, and Save is the safe one.

- **Single** sends all selected endpoints in one generation request and creates independent cases for each endpoint. Cases are grouped by endpoint; each generated scenario retains its own title.
- **Flow** asks the LLM for sequential scenarios only when steps represent a real dependency or user journey. Flows execute one step at a time, pass values from earlier responses to later requests, and stop at the first failed or errored step.
- **General** generates requirements-only manual scenarios without endpoint or example selection.

Cases are independent by default. Different boundary values and expected outcomes (below, exactly at, and above a threshold) become separate cases, even when they share setup. The generator maps atomic requirements to cases before adding dependency-driven flows or supplementary edge cases. Each case stores **Technique tags** (such as BVA or equivalence partitioning) separately from **Requirement references** (such as HD-7); unnumbered requirements receive stable `REQ-001` style references. Edit these comma-separated fields in a case’s Coverage metadata and save them with the case. The latest generation coverage expander and Activity Logs → Generation details show requirement status, linked cases, gaps, ambiguities, and unsupported branch or statement coverage claims. Such code coverage claims remain unsupported unless source or logic was supplied.

General cases contain ordered human-readable steps and no request, mapping, or assertion configuration. Choose an existing project-scoped General scenario collection or create one, such as a product or business context; the existing **Collections** filter lists those groups without adding another filter. Mark each scenario **Passed** or **Failed** to append a manual result to its history; batch HTTP runs skip these cases.

**Business requirements for this generation** is run-specific guidance for Single, Flow, or General generation. For General scenarios, it can be left blank when the project-wide or selected feature knowledge supplies context. The text is combined with the current project page and selected feature pages (including linked services), then recorded with the activity and generated cases; it never updates the Hub automatically. Promote settled product rules by preparing and saving an explicit reviewed Hub update from Project Chat. Case-level **Generation requirements** shows the context used. Generated tests and each flow step include editable assertion groups for status, body text, JSONPath field value, and response schema.

The generated cases and Activity Logs → Generation retain the exact Knowledge Hub page versions used. Chat history is not sent wholesale to generation, and run-specific requirements do not update the Hub.

In Project Chat, use **Conversation** to explore the product and **Knowledge Hub** to maintain versioned pages. Drafting is a deliberate user action after discussion; it creates per-page drafts and diffs but does not save them. Saving selected pages appends versions atomically. Open questions remain visibly labeled. Feature pages link to reusable microservice pages, and generation includes those linked pages automatically.

Generation responses may include clarification questions. Review the questions under the generation controls, enter answers, and choose **Refine generated cases**. The workspace shows a progress message while AI refines the cases. On success, the refined output replaces the source cases in active workflows: archived cases are hidden from Test Cases, generation examples, revision baselines, execution, and saved test suites. Their case records and execution history remain available from the source activity details. If refinement fails, the source output remains active. You can repeat this for another clarification round. Release revision clarifications create a separate revision and keep earlier revisions intact. Activity Logs → Generation details show the questions and answers, the replacement relationship, archived case summaries, and a way to load archived execution histories. APIs return `{ "test_cases": [...], "clarification_questions": [...] }`; legacy LLM array responses are treated as having no questions.

To prepare a release update, choose **Create release revision** in Test Cases. The workflow opens in a modal and loads the saved project and generation history when it opens, so browsing the panel costs no extra requests. Choose the prior generation action whose requirements should carry forward. The baseline selects only that action’s still-saved cases and flows by default. Use **Select all** to include every currently saved, non-superseded case in the project, including manual cases and cases from other actions, or add/remove cases individually. Choose **Keep unchanged** for baseline cases that should be copied into the new complete suite exactly as saved; other selected cases are sent to AI for revision. Kept cases receive new revision IDs linked to their source cases, and their protection carries into revision clarification rounds. Hover the baseline selector's help icon for inclusion and save guidance. Use **View selected case details** to review provenance and references to deleted endpoints. Deleted cases are excluded, and selected edits must be saved before revision generation.

Choose endpoints with **Choose endpoints** when current API definitions should inform the revision. The picker shows selected counts and keeps the collection tree inside a searchable popover; expand a collection to inspect requests and statuses, or use its checkbox to select or clear all its requests. Every currently saved endpoint is available regardless of normal generation eligibility, and all start selected. You can clear them all and generate from the selected baseline alone, including a General scenarios baseline. Endpoint snapshots compare stable IDs and show added, unchanged, or modified status with changed request fields (method, URL, headers, query parameters, and body). Collection placement is displayed separately; moving a request between collections does not count as a request-definition change. Deleted endpoints are not selectable. Older generation actions show **No comparison** on endpoint rows; hover the picker help icon for the explanation.

Prior business requirements and any release notes from the chosen action remain read-only context. Enter new changes in **New requirement changes**. The LLM receives those contexts separately with the selected saved cases and latest saved endpoint definitions, and must return a complete suite. Each revised case stores the cumulative requirements, including prior requirements, prior release changes not already included, and the new changes. Review or edit this combined text in the case or flow's **Generation requirements** section. Flow mappings can target request headers, query parameters, path placeholders, or body fields. Unsupported destinations are omitted with a warning because the flow runner cannot apply them. Each output gets new case IDs; revised cases link to their source case IDs, and earlier suites remain unchanged. The latest revision is editable. Older revisions are read-only; select **All revisions** to browse the full project history.

Open **Activity Logs → Generation** to browse a paged table (10, 25, 50, or 100 rows) of execution time, generation type, state, and project, counted against the true record total. A replaced source action is labeled **Superseded**. Choose **View details** to open its requirements, included endpoints, exact prompt, raw LLM response, outcome, generated case IDs, clarification linkage, and whether clarification questions were dismissed. For refinement activities, the modal lists archived cases and can load their execution histories. Release revision details separately show previous business requirements, previous release notes, new requirement changes, cases copied unchanged, and the cumulative requirements saved on revised cases. Records are retained in PostgreSQL for the lifetime of the project.

Open **Activity Logs → Knowledge Extraction** to review legacy extraction attempts and current Knowledge Hub activity. Draft rows retain the prompt, provider/model, and raw response; save and restore rows retain the page content and version; page creation and feature-service link changes are also recorded. Chat turns themselves do not trigger extraction. The list is paginated and opens full prompt/response or version details on demand.

To extend an existing set, choose **Use existing cases as examples** and select cases whose scenario style or coverage you want repeated. The picker is independent of **Run selected**. Keep the current Single or Flow mode, choose the target endpoints, and add business requirements; the generator uses the selected cases as context and creates additional cases for those endpoints. Existing cases stay unchanged, and new cases are added to the workspace. Example IDs are resolved from the active project before being sent to the configured LLM provider.

### Edit, save, and execute cases

Use **Add manual test** in the Test Cases top bar to create a single test from one saved request or a flow from a selected, ordered set of saved requests. The new case is saved to the project immediately and opened for editing. **Test suites** sits beside it; its popover loads, saves, updates, and deletes named case selections.

Check the cases and flows to export, then use **Export CSV** to download only those saved test case definitions. Columns are `test_case_id`, `name`, `type`, `description`, `business_requirements`, `technique_tags_json`, `requirement_refs_json`, `is_flow`, `source_endpoint_id`, `source_endpoint_name`, `request_method`, `request_url`, `request_headers_json`, `request_query_params_json`, `request_body_json`, `assertions_json`, and `steps_json`. Tags and requirement references are JSON arrays. Coverage summaries remain in generation activity rather than repeating on each CSV row. Each flow occupies one row; its ordered steps, endpoint references, assertions, and variable mappings are preserved in `steps_json`. General scenarios store ordered `manual_steps` in that cell. Single-request columns are blank for flows and General scenarios; assertion data is blank for General scenarios. CSV import is not currently available. Execution responses and timing are not included.

The selection toolbar applies to both single tests and flows. It shows **Deselect all** when every case is selected and **Select all** otherwise. In **Test suites**, enter a unique project-level name and save the current selection. Loading a suite restores its selection; **Update suite** saves changes to membership or name, and **Delete suite** removes it. Suites store case IDs rather than snapshots, so **Run selected** loads the latest saved case contents. Saving a suite also persists selected generated cases that are new to the project. Deleted cases disappear from a suite the next time it is saved; successful clarification refinement removes superseded cases from saved suites immediately.

Use the **Test suites**, **Collections**, and **Endpoints** filters together to narrow the list; multiple selections within one filter are alternatives, while different filters combine. The result filter remains available, and **Clear** resets all filters. Single tests stay grouped by endpoint. Flows appear once in **Flow scenarios** when at least one step matches a selected endpoint or collection, with their participating endpoints and collections shown on each flow.

Expand a single test to edit its method, URL, query parameters, headers, body, assertions, and scenario name. Expand a flow to edit each step, change its request and assertions, manage variable mappings, or add, remove, and reorder steps. Added steps use saved project requests.

Edits stay in the current session until **Save changes** is selected on the case. Saving updates the existing case by its stable ID. Running a case uses the current in-session values; it does not save them. Every run, including runs of unsaved edits, is retained with an immutable snapshot of the configuration that executed.

Use **Run** on one case or select cases and choose **Run selected** for a batch. Results include pass/fail/error status, latency, request details, response headers and body, and per-step results for flows. A run opens the relevant Result or Scenario result view. Batch execution focuses the first failed case, or the last case if all passed. Project-scoped generation stores cases in the project; **Save to project** saves the current case list again when needed.

Open a case's **History** tab to browse timestamped outcomes and the exact executed configuration and response details. Flow history includes each step's outcomes grouped by stable step ID. Flakiness is calculated dynamically from the latest ten outcomes: fewer than three runs or all-pass/all-non-pass results are not flaky; a mix of passes and failures or execution errors is.

### Pass values between flow steps

Variable mappings are scoped to one flow scenario. They pass a value from a previous response into a later request; they are not project-wide or Postman environment variables. For example, put a login request first, then map its access token into the `Authorization` header of a later step:

```json
{
  "from": "1:$.access_token",
  "to": "headers.Authorization",
  "transform": "Bearer {value}"
}
```

`1:` identifies the first step's response, and `$.access_token` selects the field. The transform adds the Bearer prefix. The first step cannot map a previous response. If a source omits the step number, it reads the immediately preceding response. Supported destinations include headers, query parameters, path parameters, and body fields. Add a mapping to every later step that needs the token.

## Data and defaults

- New requests and imported requests are excluded from test generation by default.
- Query and header row **Send** toggles control outgoing request fields; these are separate from generation eligibility.
- Projects, collections, saved requests, test cases, release revisions, execution history, generation activity, and generation order persist in PostgreSQL. Execution records retain the run's exact case/flow configuration snapshot.
- Successful clarification refinements retain archived case payloads and histories while marking them inactive; their IDs are removed from saved test suites and they cannot be edited, used as generation examples, revised, or executed.
- Playground drafts and their unsaved responses remain in Streamlit session state.
- Saved request assertions are stored with the request. Generated case and flow-step assertions are stored with their test cases.
- Existing endpoint records are migrated at startup into each project's **Imported Endpoints** collection. Existing SQLite data is not automatically migrated.
- Five-second success and error toasts use green and red accents; API failures also retain detailed inline errors.
- The app uses a single light theme with a pale canvas, white panels, and consistent contrast across requests, assertions, results, and tables.
- Project Chat scrolls to each new assistant reply. Long messages open expanded by default and can be collapsed with the disclosure caret; the message-context label is hidden to save space.

## API overview

The backend is FastAPI. Visit `/docs` on the backend host for the interactive schema and request models.

| Area | Routes |
|---|---|
| Health and request tools | `GET /health`; `POST /api/v1/curl/parse`; `POST /api/v1/http/send`; `POST /api/v1/http/execute-assertions` |
| Projects | `GET, POST /api/v1/projects`; `GET /api/v1/projects/current`; `GET, PUT, DELETE /api/v1/projects/{project_id}`; `PUT /api/v1/projects/{project_id}/generation-order` |
| Collections and requests | `GET, POST /api/v1/projects/{project_id}/collections`; `PUT, DELETE /api/v1/projects/{project_id}/collections/{collection_id}`; `POST /api/v1/projects/{project_id}/collections/{collection_id}/requests`; `PUT, DELETE /api/v1/projects/{project_id}/collections/{collection_id}/requests/{request_id}`; `GET /api/v1/projects/{project_id}/collections/{collection_id}/export` |
| Contract import and discovery | `POST /api/v1/contracts/preview`; `POST /api/v1/projects/{project_id}/contracts/import`; `POST /api/v1/projects/{project_id}/contracts/flow-candidates`; `POST /api/v1/projects/{project_id}/contracts/generate-flows` |
| Test cases, revisions, and suites | `POST /api/v1/test-cases/generate` (Single or General); `POST /api/v1/test-cases/generate-flow` (standalone); `POST /api/v1/projects/{project_id}/test-cases/generate-flow`; `POST /api/v1/projects/{project_id}/test-case-revisions`; `POST /api/v1/projects/{project_id}/generation-activity/follow-up`; `POST /api/v1/projects/{project_id}/generation-activity/{activity_id}/dismiss-clarifications`; `GET /api/v1/projects/{project_id}/generation-activity`; `POST /api/v1/projects/{project_id}/test-cases/save`; `GET, DELETE /api/v1/projects/{project_id}/test-cases`; `GET /api/v1/projects/{project_id}/test-cases/export`; `PUT, DELETE /api/v1/projects/{project_id}/test-cases/{test_case_id}`; `POST /api/v1/projects/{project_id}/test-cases/{test_case_id}/manual-result`; `GET /api/v1/projects/{project_id}/test-cases/{test_case_id}/history`; `POST /api/v1/test-cases/execute`; `GET, POST /api/v1/projects/{project_id}/test-runs`; `PUT, DELETE /api/v1/projects/{project_id}/test-runs/{run_id}` |
| General scenario collections | `GET, POST /api/v1/projects/{project_id}/general-case-collections`; collections are persisted separately from API request collections and may exist before they contain cases |
| Project chat, Knowledge Hub, and activity | Chat thread routes under `/api/v1/projects/{project_id}/chat/threads`; pages at `/api/v1/projects/{project_id}/knowledge-hub/pages`; feature-service links at `/api/v1/projects/{project_id}/knowledge-hub/features/{feature_id}/microservices`; history at `/knowledge-hub/pages/{scope_id}/versions`, compare at `/knowledge-hub/pages/{scope_id}/compare`, restore under `/knowledge-hub/pages/{scope_id}/versions/{version_id}/restore`; explicit drafts at `/chat/threads/{thread_id}/knowledge-draft`; atomic reviewed saves at `/knowledge-hub/updates`; paged Knowledge Extraction activity at `/api/v1/projects/{project_id}/knowledge/activity` and full event details at `/api/v1/projects/{project_id}/knowledge/activity/{event_id}` |
| Compatibility and app state | `POST, PUT /api/v1/projects/{project_id}/endpoints`; `PUT, DELETE /api/v1/projects/{project_id}/endpoints/{endpoint_id}` (legacy endpoint routes); `GET /api/v1/memory/state` |

## Development

### Useful Make commands

| Command | Purpose |
|---|---|
| `make setup` | Create `.venv` and install backend and frontend dependencies |
| `make run-local-backend` | Run FastAPI locally on port 8000 |
| `make run-local-frontend` | Run Streamlit locally on port 8501 |
| `make docker-db-up` | Start PostgreSQL for local app processes |
| `make docker-db-reset` | Delete this Compose project's PostgreSQL data after typing `RESET`, then rebuild and start the stack |
| `make docker-up` | Start the full Compose stack without rebuilding images |
| `make docker-up-build` | Build images and start the full Compose stack |
| `make docker-down` | Stop services while preserving PostgreSQL data |
| `make docker-logs` | Follow Compose logs |
| `make test` | Run the pytest suite; start PostgreSQL first with `make docker-db-up` |
| `make clean-cache` | Remove Python and tool caches without deleting `.venv` |

### Project structure

```text
.streamlit/
  config.toml          Streamlit's native light theme and server settings
app/
  main.py              FastAPI routes and application setup
  storage.py           PostgreSQL persistence and history
  parser.py            cURL parsing
  contracts.py         Contract import and dependency discovery
  generator.py         LLM prompts, provider routing, and case generation
  executor.py          HTTP and assertion execution
  schemas.py           API request and response models
frontend/
  app.py               Streamlit entry point
  core.py              Shared frontend state, API clients, and helpers
  request_controls.py  Custom URL and request-order components
  views/
    api_workspace.py   Request editor and collection navigator
    test_cases.py      Generation, test-case editing, and execution
    chat.py            Project Chat and Knowledge Hub
    activity.py        Generation and Knowledge Extraction activity logs
  styles/              Design tokens and workspace styles
docs/
  persistent_context.md  Project Chat, Knowledge Hub, and generation workflow
scripts/
  reset_local_database.sh  Confirmed local Compose database reset
tests/
  ...                  API, persistence, execution, generation, and UI tests
Dockerfile.backend       Backend container image
Dockerfile.frontend      Frontend image; includes Streamlit configuration
docker-compose.yml       PostgreSQL, backend, and frontend services
Makefile                 Local and Docker workflows
README.md
technical_documentation.md
agent_context.md         Current implementation handoff notes
agent_rules.md           Repository conventions
requirement_document.md  Product requirements
```

See [technical_documentation.md](technical_documentation.md) for architecture, data models, mapping behavior, and implementation details. See [agent_rules.md](agent_rules.md) for repository coding and documentation conventions.

## Appearance

Api-Agent uses a single light theme. The sidebar does not include a theme
switch, and Streamlit's native widgets and the app's custom surfaces are both
configured for light backgrounds.

## Workspace behaviour

- The collection rail lists collections as cards joined to their requests by a
  guide line; the open request carries an accent bar, and each row has a quiet
  three-dot menu for rename, duplicate, export, and delete.
- Project Chat has a conversation rail with search and an Active/Archived filter,
  endpoint and Knowledge Hub sources, project/feature/microservice pages,
  feature-service links, reviewed multi-page drafts, version diffs, and history.
- Release revisions are created from a modal opened in Test Cases; the saved
  project and generation history load when the modal opens, not on every rerun.
- Generation Activity is paged (10, 25, 50, 100 rows) against a real record count.
