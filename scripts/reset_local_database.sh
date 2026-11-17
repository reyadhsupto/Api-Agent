#!/usr/bin/env bash

# Reset only this Compose project's PostgreSQL volume, then rebuild and start
# the stack so the backend initializes its current schema.
set -euo pipefail

if [[ ! -t 0 ]]; then
    echo "Refusing to reset without an interactive terminal. Run 'make docker-db-reset' in a terminal." >&2
    exit 2
fi

cat <<'NOTICE'
WARNING: This permanently deletes the PostgreSQL data volume for this Docker
Compose project, including all projects, requests, test cases, executions,
chat threads, briefs, knowledge submissions, and generation activity.
The app will recreate its schema and built-in Default Project afterward.
NOTICE

read -r -p "Type RESET to continue: " confirmation
if [[ "$confirmation" != "RESET" ]]; then
    echo "Database reset cancelled; no Docker resources were changed."
    exit 0
fi

if ! command -v docker >/dev/null 2>&1; then
    echo "Docker is required to reset the Compose database." >&2
    exit 1
fi

compose_config="$(docker compose config --format json)"
volume_name="$(printf '%s' "$compose_config" | python3 -c '
import json
import sys

config = json.load(sys.stdin)
volume = (config.get("volumes") or {}).get("api_agent_pgdata")
if not isinstance(volume, dict):
    raise SystemExit("Could not resolve the Compose PostgreSQL volume; refusing to reset.")
if volume.get("external"):
    raise SystemExit("The PostgreSQL volume is externally managed; refusing to delete it.")
name = volume.get("name")
if not name:
    raise SystemExit("Compose did not provide a resolved PostgreSQL volume name; refusing to reset.")
print(name)
')"

echo "Stopping this Compose project while preserving its other resources..."
docker compose down
echo "Removing PostgreSQL volume: ${volume_name}"
docker volume rm "$volume_name"
echo "Rebuilding and starting the stack with a fresh database..."
docker compose up --build -d
echo "Fresh database started. Backend initialization creates the current schema and Default Project."
