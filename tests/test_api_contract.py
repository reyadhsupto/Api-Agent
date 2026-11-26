# tests/test_api_contract.py

"""Contract guards shared by the FastAPI backend and the Next.js frontend.

These tests avoid a live PostgreSQL server on purpose. They protect the two
properties the web client depends on at build time:

1. ``app.main`` imports with an unreachable database URL, so OpenAPI and the
   TypeScript request types can be generated in CI.
2. The committed snapshot and the generated types stay in step with the routes.
"""

import json
import os
import pathlib
import subprocess
import sys

from app.main import app

ROOT = pathlib.Path(__file__).resolve().parent.parent
SNAPSHOT = ROOT / "web" / "openapi.json"
GENERATED = ROOT / "web" / "src" / "types" / "api.generated.ts"

UNREACHABLE = "postgresql://nobody:nobody@127.0.0.1:1/none"


def test_app_imports_and_builds_schema_without_a_database():
    """The OpenAPI schema must be reachable with an unreachable database URL."""
    script = (
        "import app.main as m\n"
        "print(len(m.app.openapi()['paths']))\n"
        "print(m.get_database.cache_info().currsize)\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        env={**os.environ, "DATABASE_URL": UNREACHABLE},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    lines = result.stdout.strip().splitlines()
    assert int(lines[0]) > 0
    assert lines[1] == "0"


def test_openapi_snapshot_is_current():
    """The committed snapshot must match the live app; regenerate with make gen-types."""
    assert SNAPSHOT.exists(), "run make gen-types"
    committed = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    assert committed == app.openapi(), "run make gen-types"


def test_generated_types_cover_every_schema():
    """A new request model without a generated interface is drift."""
    assert GENERATED.exists(), "run make gen-types"
    source = GENERATED.read_text(encoding="utf-8")
    schemas = (app.openapi().get("components") or {}).get("schemas") or {}
    missing = [
        name for name in schemas
        if "interface " + name not in source and "type " + name not in source
    ]
    assert not missing, missing


def test_web_client_routes_exist_in_backend():
    """Every route the Next.js client calls must be served by FastAPI."""
    paths = app.openapi()["paths"]
    required = [
        "/api/v1/health",
        "/api/v1/projects",
        "/api/v1/curl/parse",
        "/api/v1/http/send",
        "/api/v1/http/execute-assertions",
        "/api/v1/test-cases/generate",
        "/api/v1/test-cases/generate-flow",
        "/api/v1/test-cases/execute",
        "/api/v1/projects/{project_id}/test-cases",
        "/api/v1/projects/{project_id}/test-cases/save",
        "/api/v1/projects/{project_id}/test-cases/export",
        "/api/v1/projects/{project_id}/generation-activity",
        "/api/v1/projects/{project_id}/chat/threads",
        "/api/v1/projects/{project_id}/chat/threads/{thread_id}/messages",
        "/api/v1/projects/{project_id}/knowledge-hub/pages",
    ]
    missing = [path for path in required if path not in paths]
    assert not missing, missing


