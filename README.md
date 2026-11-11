# Api-Agent

Api-Agent is a local workspace for building API requests, generating tests with an LLM, and running those tests against an API. Organize requests into project collections, import endpoints from API contracts, and build multi-step flows that pass values such as an authentication token between requests.

## At a glance

- **Compose and send requests:** Create temporary request tabs, edit methods, URLs, query parameters, headers, and bodies, or paste cURL into the URL field. Recognized cURL is parsed automatically after three seconds without typing.
- **Check responses in the playground:** Add repeatable status, body text, JSONPath field-value, and JSON Schema assertions. Run all enabled checks with one request or run an individual check.
- **Import API definitions:** Review endpoints from OpenAPI 3.x, Swagger 2.0, Postman Collection 2.1, Markdown, prose, or a public documentation URL. Edit request details before saving them into a collection.
- **Discover dependent flows:** For OpenAPI and Swagger contracts, find normalized response-field matches in downstream path or body fields, review the evidence, and ask the LLM to turn selected paths into named scenarios. Generic `id` matches are ignored.
- **Generate endpoint and flow tests:** Choose eligible saved requests, reorder them, select Single or Flow generation, and optionally add business requirements.
- Newly generated test cases and flows receive UUIDs from the backend; model-provided IDs are ignored. Existing saved and manual case IDs remain unchanged.
- **Edit and execute tests:** Update generated requests, flow steps, mappings, and assertions. Run one case or a selected batch, inspect request and response details, and save changes to the project.
- **Create manual tests:** Start a single test from any saved request or assemble a flow from an ordered set of saved requests, then edit the case in the Test Cases workspace.
- **Create test suites:** Name and save a selection of cases, reload it later, adjust membership, update it, or execute it using the latest saved case versions.
- **Review generation activity:** Use the dedicated Generation Activity tab to revisit requirements, included endpoints, the prompt, and raw LLM response for recent project generation actions.
- **Revise a release suite:** Start from a prior generation action, carry forward existing generated or manual cases, keep prior requirements as read-only context, add new requirement changes, and select current endpoints from every collection. Full endpoint snapshots show added or modified request definitions; each revision is saved as a separate suite.
- **Track execution history:** Each case has a History view with the configuration snapshot used for every run. Flow history also groups outcomes by stable step ID. A case, flow, or step is marked flaky when at least three of its latest ten runs include both passes and failures or errors.
- **Keep project data:** Projects, collections, saved requests, test cases, named runs, execution history, and generation activity are stored in PostgreSQL. Temporary playground tabs and unsaved edits remain in the Streamlit session.

The frontend is built with Streamlit, the API with FastAPI, and request execution uses Python `requests`. LLM providers can be configured from Groq, OpenRouter, Cohere, and Hugging Face.

## Typical workflow

1. **Create or select a project** in the sidebar. Create a collection to organize saved requests.
2. **Add requests** in API Workspace. Compose them manually, paste cURL into the URL field, or use **Import** in the collection navigator. Review and save requests to a collection.
3. **Organize requests** in the compact, collapsible Collections browser. Click a request name to open it, hover or focus it to view its URL, use its three-dot menu to rename, duplicate, or delete it, and use a collection menu to rename, export, or delete that collection.
4. **Choose generation eligibility** in the Collections browser. New requests are excluded by default; use the checkbox beside a request to include it, or the checkbox beside a collection to include or exclude all requests in that collection.
5. **Choose and order requests** in Test Cases. Check requests for this run and drag them into the desired order. The project order is saved and used by future flow generation.
6. **Generate tests.** Select **Single** for independent request cases or **Flow** for sequential scenarios. Add business requirements when useful.
7. **Review and run cases.** Expand a case to edit its request, assertions, or flow steps. Run it to open its result view. Save edits to persist them to the project.
8. **Create a test suite.** Add manual single tests or flows from saved requests when needed. Select the cases to include, enter a suite name, and save. Later, load that suite, change its selection, and choose **Update suite** or **Run selected**. Suites keep an ordered list of case IDs and execute the latest saved version of each case.

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
```

Only configure the providers you plan to use. `OPENROUTER_MODEL` and `API_AGENT_LLM_MAX_OUTPUT_TOKENS` are optional. Compose sets the backend's database host to the `postgres` service; local backend processes use `DATABASE_URL`, normally with host `localhost`.

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

Use `make docker-up` for subsequent starts with the built images; it skips image builds. Run `make docker-up-build` after changing application code or dependencies. Docker caches pip downloads across dependency rebuilds, and application source is copied after dependency installation so source-only edits reuse the installed dependency layers. Open [http://localhost:8501](http://localhost:8501). Stop services with `make docker-down`; PostgreSQL data remains in the `api_agent_pgdata` volume. `docker compose down -v` removes the volume and its data.

If a host port is already in use, set `POSTGRES_PORT`, `BACKEND_PORT`, or `FRONTEND_PORT` in `.env`. For local app processes, keep the port in `DATABASE_URL` aligned with `POSTGRES_PORT`.

## How to use the workspace

### Projects, collections, and requests

Select or create a project in the sidebar. In API Workspace, the compact collection navigator is headed by the active project name, stays beside the playground on desktop, and stacks above it on narrow screens. **Import** and **Discover** open contract tools, and the plus beside search creates a collection. Use the × in an open contract panel’s title row to dismiss it. Search filters collection names, request names, and URLs. Expand a collection to browse its indented requests, which are linked visually to their parent by a subtle tree guide. The checkbox at the left of a collection controls generation eligibility for every request in it; request checkboxes control individual eligibility. Request names are truncated to fit, show the URL on hover or keyboard focus, and open the request in the playground when clicked. Plain, unboxed three-dot menus provide request rename, duplicate, and delete actions, and collection rename, Postman export, and delete actions. A saved request belongs to a project collection; an open request tab is a temporary draft until saved.

The playground supports manual request editing or cURL import. Paste or type a one-line or multiline command beginning with `curl` into the URL field and pause for three seconds; the frontend parses recognized commands automatically. Regular URLs are not parsed as cURL. Review the method, URL, query parameters, headers, and body before sending or saving. Contract imports omit payloads from GET and DELETE requests.

Use **Send** for request-only execution. To check a response, open **Assertions** and add any number of checks:

- **Status:** expected HTTP status code.
- **Body contains:** text that must appear in the response body.
- **Field value:** JSONPath plus the expected value.
- **Response schema:** a JSON Schema document used to validate a JSON response.

Each assertion has an enabled checkbox. **Run All** sends one request and evaluates every enabled assertion; an individual **Run** sends a fresh request for that assertion even when it is disabled for Run All. The response panel shows the HTTP response and each assertion outcome.

### Import contracts and discover flows

Use **Import** in the collection navigator. Provide pasted text, upload a file, or enter a public documentation URL. Structured formats include OpenAPI 3.x, Swagger 2.0, and Postman Collection 2.1; prose extraction is an LLM-generated proposal. Review the discovered endpoint list, edit methods and request data, choose a destination collection, provide a base URL if needed, and confirm import. Use **Discover** beside it to analyze imported OpenAPI/Swagger dependencies and generate scenarios from selected candidate paths.

Imported requests are excluded from generation until enabled. Open **Discover flows from imported contracts** to analyze OpenAPI/Swagger field dependencies. The graph shows matching response and request fields as evidence; cycles remain visible but are omitted from executable paths. Select candidate paths and generate named flow cases with optional business context.

Anonymous URL imports are limited to public HTTP(S) hosts and documents up to 5 MB. Authenticated documentation must be pasted or uploaded. Postman environments, scripts, and authentication settings are not imported.

### Generate and organize test cases

Use the request or collection checkboxes in API Workspace to set persistent generation eligibility. In Test Cases, use the integrated draggable request list to choose requests for the current run and set their order. All eligible requests can be reordered; checked requests are used in the current generation run. The project order persists across reloads.

- **Single** sends all selected endpoints in one generation request and creates independent cases for each endpoint. Cases are grouped by endpoint; each generated scenario retains its own title.
- **Flow** asks the LLM to create sequential scenarios using the selected order. Flows execute one step at a time and can pass values from earlier responses to later requests.

Business requirements are optional. They can describe expected behavior, edge cases, authentication rules, or important assertions. The submitted requirements are saved on each generated case and can be reviewed, updated, or extended in its **Generation requirements** section; save the case to persist edits. When saved cases are selected as examples for a later generation, their requirement text is included as context. Generated tests and each flow step include editable assertion groups for status, body text, JSONPath field value, and response schema.

To prepare a release update, expand **Create a release revision**. Choose the earlier generation action whose requirements should carry forward. The baseline defaults to cases in the newest revision, or to the source action's cases when no revision exists; add or remove saved manual and generated cases as needed. Hover the baseline selector's help icon for inclusion and save guidance. Use **View selected case details** to review provenance and references to deleted endpoints. Deleted cases are excluded, and selected edits must be saved before revision generation.

Choose endpoints with **Choose endpoints**. The picker shows selected counts and keeps the collection tree inside a searchable popover; expand a collection to inspect requests and statuses, or use its checkbox to select or clear all its requests. Every currently saved endpoint is available regardless of normal generation eligibility, and all start selected. Endpoint snapshots compare stable IDs and show added, unchanged, or modified status with changed request fields (method, URL, headers, query parameters, and body). Collection placement is displayed separately; moving a request between collections does not count as a request-definition change. Deleted endpoints are not selectable. Older generation actions show **No comparison** on endpoint rows; hover the picker help icon for the explanation.

Prior business requirements and any release notes from the chosen action remain read-only context. Enter new changes in **New requirement changes**. The LLM receives those contexts separately with the selected saved cases and latest saved endpoint definitions, and must return a complete suite. Each revised case stores the cumulative requirements, including prior requirements, prior release changes not already included, and the new changes. Review or edit this combined text in the case or flow's **Generation requirements** section. Flow mappings can target request headers, query parameters, path placeholders, or body fields. Unsupported destinations are omitted with a warning because the flow runner cannot apply them. Each output gets new case IDs; revised cases link to their source case IDs, and earlier suites remain unchanged. The latest revision is editable. Older revisions are read-only; select **All revisions** to browse the full project history.

Open the **Generation Activity** tab to browse a table of execution time, generation type, state, and project. Choose **View details** on a row to open its requirements, included endpoints, exact prompt, raw LLM response, outcome, and generated case IDs in a modal. Release revision details separately show previous business requirements, previous release notes, new requirement changes, and the cumulative requirements saved on its cases. Records are retained in PostgreSQL for the lifetime of the project.

To extend an existing set, choose **Use existing cases as examples** and select cases whose scenario style or coverage you want repeated. The picker is independent of **Run selected**. Keep the current Single or Flow mode, choose the target endpoints, and add business requirements; the generator uses the selected cases as context and creates additional cases for those endpoints. Existing cases stay unchanged, and new cases are added to the workspace. Example IDs are resolved from the active project before being sent to the configured LLM provider.

### Edit, save, and execute cases

Use **Add manual test** in the Test Cases top bar to create a single test from one saved request or a flow from a selected, ordered set of saved requests. The new case is saved to the project immediately and opened for editing. **Test suites** sits beside it; its popover loads, saves, updates, and deletes named case selections.

Check the cases and flows to export, then use **Export CSV** to download only those saved test case definitions. The CSV includes case identity, type, description, generation requirements, source endpoint details, request fields, and assertions. Each flow occupies one row; its ordered steps, endpoint references, assertions, and variable mappings are preserved in the `steps_json` cell as a foundation for future CSV import. CSV import is not currently available. Execution responses and timing are not included.

The selection toolbar applies to both single tests and flows. It shows **Deselect all** when every case is selected and **Select all** otherwise. In **Test suites**, enter a unique project-level name and save the current selection. Loading a suite restores its selection; **Update suite** saves changes to membership or name, and **Delete suite** removes it. Suites store case IDs rather than snapshots, so **Run selected** loads the latest saved case contents. Saving a suite also persists selected generated cases that are new to the project. Deleted cases disappear from a suite the next time it is saved.

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
- Playground drafts and their unsaved responses remain in Streamlit session state.
- Saved request assertions are stored with the request. Generated case and flow-step assertions are stored with their test cases.
- Existing endpoint records are migrated at startup into each project's **Imported Endpoints** collection. Existing SQLite data is not automatically migrated.
- Five-second success and error toasts use green and red accents; API failures also retain detailed inline errors.

## API overview

The backend is FastAPI. Visit `/docs` on the backend host for the interactive schema and request models.

| Area | Routes |
|---|---|
| Health and request tools | `GET /health`; `POST /api/v1/curl/parse`; `POST /api/v1/http/send`; `POST /api/v1/http/execute-assertions` |
| Projects | `GET, POST /api/v1/projects`; `GET /api/v1/projects/current`; `GET, PUT, DELETE /api/v1/projects/{project_id}`; `PUT /api/v1/projects/{project_id}/generation-order` |
| Collections and requests | `GET, POST /api/v1/projects/{project_id}/collections`; `PUT, DELETE /api/v1/projects/{project_id}/collections/{collection_id}`; `POST /api/v1/projects/{project_id}/collections/{collection_id}/requests`; `PUT, DELETE /api/v1/projects/{project_id}/collections/{collection_id}/requests/{request_id}`; `GET /api/v1/projects/{project_id}/collections/{collection_id}/export` |
| Contract import and discovery | `POST /api/v1/contracts/preview`; `POST /api/v1/projects/{project_id}/contracts/import`; `POST /api/v1/projects/{project_id}/contracts/flow-candidates`; `POST /api/v1/projects/{project_id}/contracts/generate-flows` |
| Test cases, revisions, and runs | `POST /api/v1/test-cases/generate`; `POST /api/v1/test-cases/generate-flow`; `POST /api/v1/projects/{project_id}/test-case-revisions`; `GET /api/v1/projects/{project_id}/test-cases/{test_case_id}/history`; `POST /api/v1/projects/{project_id}/test-cases/generate-flow`; `POST /api/v1/projects/{project_id}/contracts/generate-flows`; `GET /api/v1/projects/{project_id}/generation-activity`; `POST /api/v1/projects/{project_id}/test-cases/save`; `GET, DELETE /api/v1/projects/{project_id}/test-cases`; `PUT, DELETE /api/v1/projects/{project_id}/test-cases/{test_case_id}`; `POST /api/v1/test-cases/execute`; `GET, POST /api/v1/projects/{project_id}/test-runs`; `PUT, DELETE /api/v1/projects/{project_id}/test-runs/{run_id}` |
| Compatibility and app state | Legacy project endpoint routes under `/api/v1/projects/{project_id}/endpoints`; `GET /api/v1/memory/state` |

## Development

### Useful Make commands

| Command | Purpose |
|---|---|
| `make setup` | Create `.venv` and install backend and frontend dependencies |
| `make run-local-backend` | Run FastAPI locally on port 8000 |
| `make run-local-frontend` | Run Streamlit locally on port 8501 |
| `make docker-db-up` | Start PostgreSQL for local app processes |
| `make docker-up` | Start the full Compose stack without rebuilding images |
| `make docker-up-build` | Build images and start the full Compose stack |
| `make docker-down` | Stop services while preserving PostgreSQL data |
| `make docker-logs` | Follow Compose logs |
| `make test` | Run the pytest suite; start PostgreSQL first with `make docker-db-up` |
| `make clean-cache` | Remove Python and tool caches without deleting `.venv` |

### Project structure

```text
app/
  main.py          FastAPI routes and application setup
  storage.py       PostgreSQL persistence
  parser.py        cURL parsing
  contracts.py     Contract import and dependency discovery
  generator.py     LLM test-case generation and provider fallback
  executor.py      HTTP and assertion execution
  schemas.py       API request and response models
frontend/
  app.py           Streamlit workspace and test-case UI
tests/
  test_parser.py
  test_executor.py
  test_frontend.py
  test_storage.py
```

See [technical_documentation.md](technical_documentation.md) for architecture, data models, mapping behavior, and implementation details. See [agent_rules.md](agent_rules.md) for repository coding and documentation conventions.
