# Api-Agent Web

The only frontend for Api-Agent. It uses Next.js App Router, TypeScript, and Tailwind CSS, and communicates with the FastAPI backend through authenticated same-origin Route Handlers.

## Run locally

From the repository root, start PostgreSQL and the backend, then start the web app:

```bash
make docker-db-up
make run-local-backend
make run-local-web
```

Open [http://localhost:3000](http://localhost:3000). The API proxy uses `BACKEND_URL`, defaulting to `http://localhost:8000`.

## Docker

```bash
make docker-up-build
```

Compose starts PostgreSQL, FastAPI, and this Next.js app. Use `make docker-up` to start existing images and `make docker-down` to stop the stack.

## Workspace routes

- `/` and `/workspace` - workspace home
- `/workspace/api` - request composer, collections, imports, and dependency discovery
- `/workspace/test-cases` - generation, revisions, saved cases, and execution
- `/workspace/chat` - project conversations and Knowledge Hub
- `/workspace/activity` - generation and Knowledge activity logs

## Commands

From `web/`, `npm run dev`, `npm run build`, `npm run start`, and `npm run lint` provide the standard Next.js workflows. From the repository root, `make check-web` typechecks and lints, while `make build-web` creates the production build.
