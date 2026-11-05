# Product Requirements Document - Api-Agent

## 1. Overview
Api-Agent is a local, single-user tool that accepts raw cURL commands, analyzes them with free-tier AI models, generates functional API test cases (positive, negative, edge, race), executes them, and displays detailed request/response metadata with assertion results. Project data persists locally in SQLite; authentication and exports remain out of scope.

## 2. Goals
- Accept a single cURL command and parse it into structured request components.
- Generate AI-powered test cases based on the parsed request and optional business requirements.
- Execute generated test cases against the target API.
- Display execution results including request URL, headers, path params, query params, payload, response payload, status, latency, headers, and assertion output.
- Support switching between multiple free-tier LLM providers when token limits are exhausted.
- Persist projects, endpoints, generated and edited tests, and execution history in SQLite.

## 3. Non-Goals (Out of Scope for MVP)
- Multi-user workspaces, authentication, and remote database services.
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
- Compare actual response against expected assertion and display pass/fail.

### FR-04: LLM Fallback
- Maintain an ordered list of free-tier LLM providers.
- On rate limit or token exhaustion from Provider A, automatically retry with Provider B.
- Surface a warning to the user when fallback occurs.

### FR-05: Local Persistence
- Store projects, endpoints, generated and edited test cases, and execution history in SQLite.
- Create a default project for standalone generation and restore the active project after restart.
- Keep the SQLite database out of version control.

### FR-06: Flow Scenario Generation
- Accept multiple endpoints in sequence for flow test case generation.
- Generate flow test cases covering: full flow success, step failure, data dependency, edge cases, race conditions.
- Support variable mapping between steps (response field from step N -> request field in step N+1).
- Support per-step assertions (status, body contains, JSONPath).
- Support flow execution: run all steps sequentially with aggregated result.
- Render each flow step as a test case card with editable assertions and per-step execution results.
- Keep single-test and flow-scenario cards visually consistent.
- Provide a compact, retractable project sidebar.


## 6. Acceptance Criteria
- A valid cURL is parsed correctly into all request components.
- At least one test case of each type (positive, negative, edge, race) is generated.
- Execution returns a pass/fail assertion with visible request and response details.
- If the primary LLM provider is rate-limited, the system switches to a secondary provider without user intervention.
- The UI provides endpoint configuration and test case generation/execution tabs.
