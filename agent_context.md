# Agent Context - Api-Agent

## Project status

Api-Agent is a local API testing workspace. FastAPI and PostgreSQL provide the backend; the only frontend is the Next.js App Router application under `web/`.

## Architecture and tooling

- `app/main.py` defines the FastAPI API and workflow orchestration.
- `app/storage.py` owns PostgreSQL schema initialization, migrations, and persistence.
- `app/generator.py` handles prompts, provider selection, generation, and output validation.
- `app/contracts.py` parses API definitions and finds response-to-request dependency paths.
- `app/executor.py` runs requests, flow mappings, assertions, and execution snapshots.
- `web/` contains the Next.js, TypeScript, and Tailwind frontend. FastAPI is accessed through authenticated same-origin Next.js Route Handlers.
- `design/tokens.py` is the canonical theme token source; `scripts/gen_tokens.py` generates `web/src/app/tokens.css`.
- `scripts/gen_types.py` generates the OpenAPI snapshot and TypeScript request-body contracts.
- Docker Compose runs PostgreSQL, FastAPI, and Next.js. There is no Python frontend runtime.

## Product behavior

### API Workspace

- The workspace has temporary request tabs, cURL parsing, request editing, response inspection, saved collections, and repeatable assertions.
- Collections and requests are searchable, collections collapse independently, and request/collection generation eligibility is persisted.
- Import supports OpenAPI/Swagger, Postman, Markdown, TXT, PDF, DOCX, and public documentation URLs. Relative URLs require a base URL during review. New imports start excluded from generation.
- **Discover dependencies** analyzes saved imported contract groups, shows response-to-request evidence and candidate paths, and can generate flows from selected paths.

### Test Cases

- Single cases are independent by default. Distinct boundary values and expected outcomes remain separate cases. Flow cases are reserved for real request dependencies or user journeys.
- Generation supports Single, Flow, General, contract-discovered Flow, and release revisions. General cases contain manual steps and no HTTP request/assertion/mapping payload; they are grouped into named General collections.
- Newly generated cases and flows receive UUIDs; existing/manual IDs remain stable.
- Clarification follow-ups create linked generation activities. Successful non-revision follow-ups supersede the previous active cases while retaining their records and execution history. Revision outputs remain separate revisions.
- Release revisions use current saved endpoints and cases, retain prior requirement context, accept new requirement changes, and let users mark selected cases **Keep unchanged**.
- Execution stores the exact case/flow snapshot. Flaky status uses the latest ten outcomes and requires at least three with both passes and non-passes. General outcomes are recorded manually; a failed mark can include an optional failure reason.
- CSV export contains one row per case and serializes flow/manual steps in ordered JSON cells.

### Project Chat and Knowledge Hub

- Project Chat stores multiple project-scoped threads. Chat turns save messages and do not trigger extraction automatically.
- Knowledge Hub pages have project, feature, or microservice scope and immutable versions. Features may link multiple shared microservice pages.
- Users explicitly prepare a Hub update from a conversation, review and edit each page draft, inspect diffs, and save selected versions together. Restoring a version creates a new version.
- Generation always includes the project page, and includes selected feature pages plus their linked microservices. Run-specific Business requirements remain distinct and do not modify Hub content.
- Activity records retain the Hub version snapshots, requirements, prompt, response, provider/model metadata, and source links used by generation.

### Activity Logs

- Activity Logs has Generation and Knowledge activity streams with pagination and a detail view.
- Details separate summary, evidence, LLM prompt, raw LLM response, and raw JSON. Large payloads load from project-scoped detail endpoints.

## Local development

- Use `make setup` to install backend and web dependencies. Activate the Python environment of choice before local backend commands.
- `make docker-db-up` starts PostgreSQL only; `make run-local-backend` and `make run-local-web` run the apps locally.
- `make docker-up-build` builds and starts the full stack; `make docker-up` starts existing images.
- `make docker-db-reset` removes the local Compose database only after the user types `RESET`.
- `make check-web`, `make build-web`, `make check-types`, and `make check-tokens` cover the main frontend and generated-contract checks.

## Authentication and providers

- Authentication is one configured local account using `AUTH_USERNAME`, `AUTH_PASSWORD`, and `AUTH_JWT_SECRET`. Access tokens last 15 minutes; opaque refresh credentials rotate and are stored hashed in PostgreSQL.
- Model calls use `LLM_PROVIDER_ORDER`, defaulting to AMD Token Lab, OpenRouter, Groq, Cohere, then Hugging Face. Providers without keys are skipped. API failures advance to the next provider; malformed generated content is returned as an application error without another provider call.
- AMD uses `AMD_API_KEY` and `AMD_MODEL`; provider/model metadata is retained in chats and activities. LLM-backed browser requests use a 20-minute timeout.

## UI decisions

- Dark is the first-visit theme; light/dark preference and collapsed sidebar state persist across reloads.
- Keep project navigation collapsible, collection/request lists compact, and long outputs in independent scroll areas.
- The sidebar **Project flow** information action explains each workspace page and the usual request-to-generation-to-review workflow; keep it usable in both expanded and collapsed navigation modes.
- Keep run-specific inputs distinct from durable project knowledge. Do not save knowledge without explicit review and user action.
- Use concise tables and drill-down activity detail rather than putting full prompts and responses in list rows.
