# Product Requirements Document - Api-Agent

## 1. Overview
Api-Agent is a local, single-user tool that accepts raw cURL commands, analyzes them with free-tier AI models, generates functional API test cases (positive, negative, edge, race), executes them, and displays detailed request/response metadata with assertion results. No database, no authentication, exports scoped for future.

## 2. Goals
- Accept a single cURL command and parse it into structured request components.
- Generate AI-powered test cases based on the parsed request and optional business requirements.
- Execute generated test cases against the target API.
- Display execution results including request URL, headers, path params, query params, payload, response payload, status, latency, headers, and assertion output.
- Support switching between multiple free-tier LLM providers when token limits are exhausted.
- Provide a simple, in-app memory UI with no backend persistence.

## 3. Non-Goals (Out of Scope for MVP)
- Database persistence of test cases or executions.
- User authentication or multi-user workspaces.
- Postman collection import.
- Export of test cases or reports (JSON, HTML, PDF, JUnit).
- Scheduled or recurring test executions.
- CI/CD integrations.
- Flow/dependency mapping between multiple endpoints.

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

### FR-05: In-App Memory
- Store current session's parsed cURL, generated test cases, and execution results in memory only.
- Data is cleared on page refresh or server restart.

## 6. Acceptance Criteria
- A valid cURL is parsed correctly into all request components.
- At least one test case of each type (positive, negative, edge, race) is generated.
- Execution returns a pass/fail assertion with visible request and response details.
- If the primary LLM provider is rate-limited, the system switches to a secondary provider without user intervention.
- The UI has distinct tabs for: cURL input/parsing, test case generation, and execution results.
