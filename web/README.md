# Api-Agent Web (Next.js)

The default frontend for Api-Agent. It talks to the FastAPI backend in `app/`
and ships alongside the legacy Streamlit UI in `frontend/` during the migration.

## Run locally

Start the backend from the repository root:

```bash
make docker-db-up
make run-local-backend
```

Then start this app:

```bash
make run-local-web
```

Open [http://localhost:3000](http://localhost:3000).

## Backend proxy

`next.config.ts` rewrites `/api/:path*` and `/health` to the FastAPI service.
The target defaults to `http://localhost:8000` and is overridden with
`BACKEND_URL`. The browser therefore only ever calls this Next.js origin.

## Docker

The image uses a multi-stage standalone build:

```bash
make docker-up-build
```

`docker-compose.yml` starts `postgres`, `backend`, `web` (port 3000), and the
temporary `frontend-legacy` Streamlit service (port 8501).

## Workspace routes

- `/` - backend connectivity check
- `/workspace` - module picker
- `/workspace/api` - request composer and response viewer
- `/workspace/test-cases` - generation, saved list, execution, and manual outcomes
- `/workspace/chat` - persisted conversations with a pinned composer
- `/workspace/activity` - paged generation and Knowledge Extraction activity

## Scripts

- `npm run dev` - development server
- `npm run build` - production build
- `npm run start` - production server
- `npm run lint` - ESLint

