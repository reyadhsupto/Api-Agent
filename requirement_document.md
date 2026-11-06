# Product Requirements Document - Api-Agent

## 1. Overview
Api-Agent is a local, single-user tool that manages API requests, uses free-tier AI models to generate functional test cases (positive, negative, edge, race), executes them, and displays detailed request/response metadata with assertion results. Project data and saved request collections persist in PostgreSQL; a unified API Workspace supports request composition and quick checks.

## 2. Goals
- Accept a single cURL command and parse it into structured request components.
- Generate AI-powered test cases based on the parsed request and optional business requirements.
- Execute generated test cases against the target API.
- Display execution results including request URL, headers, path params, query params, payload, response payload, status, latency, headers, and assertion output.
- Support switching between multiple free-tier LLM providers when token limits are exhausted.
- Persist projects, endpoints, generated and edited tests, and execution history in PostgreSQL.
- Provide a unified API Workspace for request composition, cURL import, quick sends, saved collections, and generation selection.
- Export saved collections as Postman Collection v2.1 JSON.
- Allow the model to return as many complete flow scenarios as the provider output limit supports; do not request a fixed count.

## 3. Non-Goals (Out of Scope for MVP)
- Multi-user workspaces and authentication.
- Postman collection import.
- Export of test cases or reports (JSON, HTML, PDF, JUnit).
- Scheduled or recurring test executions.
- CI/CD integrations.

## 4. User Stories
### As a QA Engineer
I want to paste a cURL command so that I can see its parsed components (URL, headers, params, body).

I want to provide business requirements so that the AI generates test cases relevant to my domain logic.

I want to generate positive, negative, edge, and race test cases so that I can validate API behavior comprehensively.

I want to execute a generated test case and see the full request/response cycle with assertion results so that I can determine pass/fail status.

I want to switch LLM providers automatically if one hits a free token limit so that generation is not interrupted.

I want to compose a temporary request in the API Workspace, import cURL, and inspect its response without saving it as a test case.

## 5. Functional Requirements
### FR-01: cURL Input
- Accept raw cURL command text input.
- Parse into: HTTP method, URL, headers, query parameters, path parameters, request body/payload.

### FR-02: Test Case Generation
- Generate at least four test case types: positive, negative, edge, race.
- Accept optional business requirements text to influence generated assertions.
- Allow user to review and edit generated test cases before execution.

### FR-03: Test Execution
- Execute a selected test case against the target endpoint.
- Capture and display: request URL, headers, path params, query params, payload, response status, response headers, response payload, latency in milliseconds.
- Compare actual response against status, body-contains, JSONPath field-value, and JSON Schema assertions and display pass/fail.
- Allow multiple assertion instances per type and enable/disable each assertion before execution.

### FR-04: LLM Fallback
- Maintain an ordered list of free-tier LLM providers.
- On rate limit or token exhaustion from Provider A, automatically retry with Provider B.
- Surface a warning to the user when fallback occurs.

### FR-05: PostgreSQL Persistence
- Store projects, endpoints, generated and edited test cases, and execution history in PostgreSQL.
- Create a default project for standalone generation and restore the active project after restart.
- Initialize PostgreSQL schema at startup and cascade dependent records on project deletion.
- Support local app runs and Docker Compose services for PostgreSQL, backend, and frontend.

### FR-06: Flow Scenario Generation
- Accept the legacy `scenario_count` API field for compatibility, but ignore it during generation.
- Accept multiple endpoints in sequence for flow test case generation.
- Generate flow test cases covering: full flow success, step failure, data dependency, edge cases, race conditions.
- Support variable mapping between steps (response field from step N -> request field in step N+1).
- Support per-step assertions (status, body contains, JSONPath, and JSON Schema); generated steps include an editable schema assertion disabled by default.
- Support flow execution: run all steps sequentially with aggregated result.
- Render each flow step as a test case card with editable assertions and per-step execution results.
- Keep single-test and flow-scenario cards visually consistent.
- Provide a compact, retractable project sidebar.

### FR-07: Unified API Workspace and Collections
- Support multiple temporary request tabs with independent session-only edits and responses.
- Compose manually or populate the active request from common cURL commands.
- Save requests to project-scoped collections; support collection and request CRUD.
- Provide enabled toggles for individual query rows, header rows, and payload inclusion.
- Keep new requests excluded from generation until selected; allow ordering selected requests for flow generation.
- Export complete collections in Postman Collection v2.1 format, preserving disabled query/header rows and payload state.
- Compose and send GET, POST, PUT, PATCH, DELETE, HEAD, and OPTIONS requests with URL, query parameters, headers, and body.
- Import common cURL flags into editable request fields.
- Display response status, elapsed time, headers, and body, including non-2xx responses.
- Keep open request tabs and quick-send responses in the current frontend session only.
- Migrate existing endpoint records into an Imported Endpoints collection and preserve legacy endpoint API routes.


## 6. Acceptance Criteria
- A valid cURL is parsed correctly into all request components.
- The generation prompt requests positive, negative, edge, and race coverage; returned scenario count and category coverage depend on the model response and provider output limit.
- Execution returns a pass/fail assertion with visible request and response details.
- If the primary LLM provider is rate-limited, the system switches to a secondary provider without user intervention.
- The UI provides an API Workspace and test case generation/execution tabs.
- Only selected saved requests are eligible for generation; temporary drafts are excluded.
