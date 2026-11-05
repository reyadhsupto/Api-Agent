"""PostgreSQL persistence for projects, endpoints, test cases, and executions."""

import json
import os
import uuid
from contextlib import contextmanager
from datetime import datetime
from typing import Iterator

import psycopg
from psycopg.rows import dict_row


def _now() -> str:
    """Return a local ISO timestamp for persisted records."""
    return datetime.now().isoformat()


def _execute(connection, query: str, params=()):
    """Run existing repository SQL using psycopg's positional placeholders."""
    return connection.execute(query.replace("?", "%s"), params)


class Database:
    """PostgreSQL repository that keeps the API's nested JSON payloads intact."""

    def __init__(self, dsn: str | None = None):
        """Create the database wrapper and initialize its PostgreSQL schema."""
        self.dsn = dsn or os.getenv(
            "DATABASE_URL",
            "postgresql://api_agent:api_agent@localhost:5432/api_agent",
        )
        self.initialize()

    def connect(self) -> psycopg.Connection:
        """Open a PostgreSQL connection that returns rows as dictionaries."""
        return psycopg.connect(self.dsn, connect_timeout=10, row_factory=dict_row)

    @contextmanager
    def session(self) -> Iterator[psycopg.Connection]:
        """Commit or roll back one operation and always close its connection."""
        connection = self.connect()
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        """Create normalized tables and indexes if this is a fresh database."""
        with self.session() as connection:
            schema = """
                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    is_default BOOLEAN NOT NULL DEFAULT FALSE,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS collections (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    name TEXT NOT NULL,
                    ordinal INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS endpoints (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    collection_id TEXT,
                    ordinal INTEGER NOT NULL,
                    payload_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS endpoint_migrations (
                    project_id TEXT PRIMARY KEY REFERENCES projects(id) ON DELETE CASCADE,
                    migrated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_endpoints_project_order
                    ON endpoints(project_id, ordinal);
                CREATE TABLE IF NOT EXISTS test_cases (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    ordinal INTEGER NOT NULL,
                    payload_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_test_cases_project_order
                    ON test_cases(project_id, ordinal);
                CREATE TABLE IF NOT EXISTS executions (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    test_case_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_executions_project
                    ON executions(project_id, created_at);
                CREATE TABLE IF NOT EXISTS app_state (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                """
            for statement in schema.split(";"):
                if statement.strip():
                    _execute(connection, statement)
            _execute(connection, "ALTER TABLE endpoints ADD COLUMN IF NOT EXISTS collection_id TEXT")
            _execute(connection, "CREATE INDEX IF NOT EXISTS idx_collections_project_order ON collections(project_id, ordinal)")
            _execute(connection, "CREATE INDEX IF NOT EXISTS idx_endpoints_collection_order ON endpoints(collection_id, ordinal)")
            _execute(connection, """
                DO $$ BEGIN
                    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_endpoints_collection') THEN
                        ALTER TABLE endpoints ADD CONSTRAINT fk_endpoints_collection
                            FOREIGN KEY (collection_id) REFERENCES collections(id) ON DELETE CASCADE;
                    END IF;
                END $$;
            """)
        self.ensure_default_project()
        self.migrate_legacy_endpoints()

    def migrate_legacy_endpoints(self) -> None:
        """Move each project's pre-collection endpoints into one saved collection once."""
        with self.session() as connection:
            projects = _execute(connection, "SELECT id FROM projects").fetchall()
            for project in projects:
                project_id = project["id"]
                migrated = _execute(
                    connection,
                    "SELECT 1 FROM endpoint_migrations WHERE project_id=?",
                    (project_id,),
                ).fetchone()
                if migrated:
                    continue
                rows = _execute(
                    connection,
                    "SELECT id, ordinal, payload_json FROM endpoints WHERE project_id=? AND collection_id IS NULL ORDER BY ordinal, id",
                    (project_id,),
                ).fetchall()
                if rows:
                    collection = _execute(
                        connection,
                        "SELECT id FROM collections WHERE project_id=? AND name='Imported Endpoints' ORDER BY ordinal LIMIT 1",
                        (project_id,),
                    ).fetchone()
                    if collection:
                        collection_id = collection["id"]
                    else:
                        collection_id = str(uuid.uuid4())
                        ordinal = _execute(
                            connection,
                            "SELECT COALESCE(MAX(ordinal)+1,0) AS ordinal FROM collections WHERE project_id=?",
                            (project_id,),
                        ).fetchone()["ordinal"]
                        now = _now()
                        _execute(
                            connection,
                            "INSERT INTO collections(id,project_id,name,ordinal,created_at,updated_at) VALUES(?,?,?,?,?,?)",
                            (collection_id, project_id, "Imported Endpoints", ordinal, now, now),
                        )
                    for row in rows:
                        payload = self._decode(row["payload_json"])
                        payload["collection_id"] = collection_id
                        payload.setdefault("include_for_generation", payload.get("include", True))
                        _execute(
                            connection,
                            "UPDATE endpoints SET collection_id=?, payload_json=? WHERE id=?",
                            (collection_id, self._encode(payload), row["id"]),
                        )
                _execute(
                    connection,
                    "INSERT INTO endpoint_migrations(project_id,migrated_at) VALUES(?,?) ON CONFLICT(project_id) DO NOTHING",
                    (project_id, _now()),
                )

    def ensure_default_project(self) -> str:
        """Create the standalone project when none exists and return its ID."""
        with self.session() as connection:
            row = _execute(connection,
                "SELECT id FROM projects WHERE is_default = TRUE ORDER BY created_at LIMIT 1"
            ).fetchone()
            if row:
                return row["id"]
            project_id = str(uuid.uuid4())
            now = _now()
            _execute(connection,
                "INSERT INTO projects(id, name, description, is_default, created_at, updated_at) VALUES(?,?,?,?,?,?)",
                (project_id, "Default Project", "Standalone generated tests and endpoints", True, now, now),
            )
            _execute(connection,
                "INSERT INTO app_state(key, value) VALUES('current_project_id', ?) ON CONFLICT(key) DO NOTHING",
                (project_id,),
            )
            return project_id

    @staticmethod
    def _decode(payload: str) -> dict:
        """Decode a persisted JSON object."""
        return json.loads(payload)

    @staticmethod
    def _encode(payload: dict) -> str:
        """Encode an API payload as compact UTF-8 JSON."""
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

    def list_collections(self, project_id: str) -> list[dict]:
        """Return project collections with their ordered saved requests."""
        with self.session() as connection:
            collections = _execute(
                connection,
                "SELECT * FROM collections WHERE project_id=? ORDER BY ordinal,id",
                (project_id,),
            ).fetchall()
            result = []
            for collection in collections:
                item = dict(collection)
                item["requests"] = [
                    self._decode(row["payload_json"])
                    for row in _execute(
                        connection,
                        "SELECT payload_json FROM endpoints WHERE collection_id=? ORDER BY ordinal,id",
                        (item["id"],),
                    ).fetchall()
                ]
                result.append(item)
            return result

    def get_collection(self, project_id: str, collection_id: str) -> dict | None:
        """Return one collection and its saved requests, scoped to its project."""
        return next(
            (item for item in self.list_collections(project_id) if item["id"] == collection_id),
            None,
        )

    def create_collection(self, project_id: str, name: str) -> dict | None:
        """Create a project collection with a stable UUID and display order."""
        if not self.get_project(project_id):
            return None
        collection_id = str(uuid.uuid4())
        now = _now()
        with self.session() as connection:
            ordinal = _execute(
                connection,
                "SELECT COALESCE(MAX(ordinal)+1,0) AS ordinal FROM collections WHERE project_id=?",
                (project_id,),
            ).fetchone()["ordinal"]
            _execute(
                connection,
                "INSERT INTO collections(id,project_id,name,ordinal,created_at,updated_at) VALUES(?,?,?,?,?,?)",
                (collection_id, project_id, name, ordinal, now, now),
            )
        return self.get_collection(project_id, collection_id)

    def update_collection(self, project_id: str, collection_id: str, updates: dict) -> dict | None:
        """Rename a collection and return its refreshed representation."""
        with self.session() as connection:
            updated = _execute(
                connection,
                "UPDATE collections SET name=?,updated_at=? WHERE id=? AND project_id=?",
                (updates.get("name", "").strip(), _now(), collection_id, project_id),
            ).rowcount
            if not updated:
                return None
            _execute(connection, "UPDATE projects SET updated_at=? WHERE id=?", (_now(), project_id))
        return self.get_collection(project_id, collection_id)

    def delete_collection(self, project_id: str, collection_id: str) -> bool:
        """Delete a collection and cascade-delete its saved requests."""
        with self.session() as connection:
            deleted = _execute(
                connection,
                "DELETE FROM collections WHERE id=? AND project_id=?",
                (collection_id, project_id),
            ).rowcount
            if deleted:
                _execute(connection, "UPDATE projects SET updated_at=? WHERE id=?", (_now(), project_id))
            return bool(deleted)

    def save_request(self, project_id: str, collection_id: str, request: dict) -> dict | None:
        """Create or update a saved request in the requested project collection."""
        item = dict(request)
        if not item.get("id"):
            item["id"] = str(uuid.uuid4())
        request_id = item["id"]
        item["collection_id"] = collection_id
        item.setdefault("name", "Untitled Request")
        item.setdefault("include_for_generation", False)
        with self.session() as connection:
            collection = _execute(
                connection,
                "SELECT id FROM collections WHERE id=? AND project_id=?",
                (collection_id, project_id),
            ).fetchone()
            if not collection:
                return None
            existing = _execute(connection, "SELECT project_id,collection_id,ordinal FROM endpoints WHERE id=?", (request_id,)).fetchone()
            if existing and existing["project_id"] != project_id:
                raise ValueError("Request ID already belongs to another project.")
            ordinal = existing["ordinal"] if existing and existing["collection_id"] == collection_id else _execute(
                connection,
                "SELECT COALESCE(MAX(ordinal)+1,0) AS ordinal FROM endpoints WHERE collection_id=?",
                (collection_id,),
            ).fetchone()["ordinal"]
            item["order"] = ordinal
            _execute(
                connection,
                "INSERT INTO endpoints(id,project_id,collection_id,ordinal,payload_json) VALUES(?,?,?,?,?) "
                "ON CONFLICT(id) DO UPDATE SET collection_id=excluded.collection_id,ordinal=excluded.ordinal,payload_json=excluded.payload_json",
                (request_id, project_id, collection_id, ordinal, self._encode(item)),
            )
            now = _now()
            _execute(connection, "UPDATE collections SET updated_at=? WHERE id=?", (now, collection_id))
            _execute(connection, "UPDATE projects SET updated_at=? WHERE id=?", (now, project_id))
        return item

    def update_request(self, project_id: str, request_id: str, updates: dict) -> dict | None:
        """Merge request fields while keeping the request's collection membership."""
        with self.session() as connection:
            row = _execute(
                connection,
                "SELECT id,collection_id,payload_json FROM endpoints WHERE id=? AND project_id=?",
                (request_id, project_id),
            ).fetchone()
            if not row:
                return None
            item = self._decode(row["payload_json"])
            item.update(updates)
            item["collection_id"] = row["collection_id"]
            _execute(connection, "UPDATE endpoints SET payload_json=? WHERE id=?", (self._encode(item), request_id))
            now = _now()
            _execute(connection, "UPDATE collections SET updated_at=? WHERE id=?", (now, row["collection_id"]))
            _execute(connection, "UPDATE projects SET updated_at=? WHERE id=?", (now, project_id))
            return item

    def delete_request(self, project_id: str, request_id: str) -> bool:
        """Delete a saved request and compact its collection's ordering."""
        with self.session() as connection:
            row = _execute(
                connection,
                "SELECT collection_id FROM endpoints WHERE id=? AND project_id=?",
                (request_id, project_id),
            ).fetchone()
            if not row:
                return False
            collection_id = row["collection_id"]
            _execute(connection, "DELETE FROM endpoints WHERE id=?", (request_id,))
            remaining = _execute(
                connection,
                "SELECT id,payload_json FROM endpoints WHERE collection_id=? ORDER BY ordinal,id",
                (collection_id,),
            ).fetchall()
            for ordinal, endpoint in enumerate(remaining):
                payload = self._decode(endpoint["payload_json"])
                payload["order"] = ordinal
                _execute(
                    connection,
                    "UPDATE endpoints SET ordinal=?,payload_json=? WHERE id=?",
                    (ordinal, self._encode(payload), endpoint["id"]),
                )
            _execute(connection, "UPDATE projects SET updated_at=? WHERE id=?", (_now(), project_id))
            return True

    def _ensure_legacy_collection(self, project_id: str) -> str:
        """Get or create the compatibility collection used by old endpoint routes."""
        with self.session() as connection:
            row = _execute(
                connection,
                "SELECT id FROM collections WHERE project_id=? AND name='Imported Endpoints' ORDER BY ordinal LIMIT 1",
                (project_id,),
            ).fetchone()
            if row:
                return row["id"]
            collection_id = str(uuid.uuid4())
            now = _now()
            ordinal = _execute(
                connection,
                "SELECT COALESCE(MAX(ordinal)+1,0) AS ordinal FROM collections WHERE project_id=?",
                (project_id,),
            ).fetchone()["ordinal"]
            _execute(
                connection,
                "INSERT INTO collections(id,project_id,name,ordinal,created_at,updated_at) VALUES(?,?,?,?,?,?)",
                (collection_id, project_id, "Imported Endpoints", ordinal, now, now),
            )
            return collection_id

    def get_project(self, project_id: str) -> dict | None:
        """Return a project with ordered endpoints, cases, and execution history."""
        with self.session() as connection:
            project = _execute(connection, "SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
            if not project:
                return None
            result = dict(project)
            result.pop("is_default", None)
            result["endpoints"] = [
                self._decode(row["payload_json"])
                for row in _execute(connection,
                    "SELECT e.payload_json FROM endpoints e LEFT JOIN collections c ON c.id=e.collection_id "
                    "WHERE e.project_id = ? ORDER BY COALESCE(c.ordinal,0),e.ordinal,e.id",
                    (project_id,),
                )
            ]
            result["collections"] = []
            for collection_row in _execute(
                connection,
                "SELECT * FROM collections WHERE project_id=? ORDER BY ordinal,id",
                (project_id,),
            ):
                collection = dict(collection_row)
                collection["requests"] = [
                    self._decode(row["payload_json"])
                    for row in _execute(
                        connection,
                        "SELECT payload_json FROM endpoints WHERE collection_id=? ORDER BY ordinal,id",
                        (collection["id"],),
                    )
                ]
                result["collections"].append(collection)
            result["test_cases"] = [
                self._decode(row["payload_json"])
                for row in _execute(connection,
                    "SELECT payload_json FROM test_cases WHERE project_id = ? ORDER BY ordinal, id",
                    (project_id,),
                )
            ]
            result["executions"] = [
                self._decode(row["payload_json"])
                for row in _execute(connection,
                    "SELECT payload_json FROM executions WHERE project_id = ? ORDER BY created_at, id",
                    (project_id,),
                )
            ]
            return result

    def list_projects(self) -> list[dict]:
        """Return project summaries with endpoint and test counts."""
        with self.session() as connection:
            rows = _execute(connection,
                """SELECT p.id, p.name, p.description, p.created_at, p.updated_at,
                          p.is_default,
                          (SELECT COUNT(*) FROM endpoints e WHERE e.project_id=p.id) endpoint_count,
                          (SELECT COUNT(*) FROM test_cases t WHERE t.project_id=p.id) test_case_count
                   FROM projects p ORDER BY p.is_default DESC, p.created_at, p.name"""
            ).fetchall()
            return [dict(row) for row in rows]

    def create_project(self, name: str, description: str = "") -> dict:
        """Create a project and select it as the active project."""
        project_id = str(uuid.uuid4())
        now = _now()
        with self.session() as connection:
            _execute(connection,
                "INSERT INTO projects(id,name,description,created_at,updated_at) VALUES(?,?,?,?,?)",
                (project_id, name, description, now, now),
            )
            _execute(connection,
                "INSERT INTO app_state(key,value) VALUES('current_project_id',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (project_id,),
            )
        return self.get_project(project_id)

    def update_project(self, project_id: str, updates: dict) -> dict | None:
        """Update project metadata and return the refreshed aggregate."""
        project = self.get_project(project_id)
        if not project:
            return None
        name = updates.get("name", project["name"])
        description = updates.get("description", project["description"])
        with self.session() as connection:
            _execute(connection,
                "UPDATE projects SET name=?, description=?, updated_at=? WHERE id=?",
                (name, description, _now(), project_id),
            )
        return self.get_project(project_id)

    def delete_project(self, project_id: str) -> bool:
        """Delete a project and its dependent rows, then select a remaining project."""
        with self.session() as connection:
            deleted = _execute(connection, "DELETE FROM projects WHERE id=?", (project_id,)).rowcount
            if not deleted:
                return False
            active = _execute(connection,
                "SELECT value FROM app_state WHERE key='current_project_id'"
            ).fetchone()
            if active and active["value"] == project_id:
                next_project = _execute(connection,
                    "SELECT id FROM projects ORDER BY is_default DESC, created_at LIMIT 1"
                ).fetchone()
                if next_project:
                    _execute(connection,
                        "UPDATE app_state SET value=? WHERE key='current_project_id'",
                        (next_project["id"],),
                    )
                else:
                    _execute(connection, "DELETE FROM app_state WHERE key='current_project_id'")
        self.ensure_default_project()
        return True

    def set_current_project(self, project_id: str) -> bool:
        """Persist the selected project ID if it exists."""
        with self.session() as connection:
            exists = _execute(connection, "SELECT 1 FROM projects WHERE id=?", (project_id,)).fetchone()
            if not exists:
                return False
            _execute(connection,
                "INSERT INTO app_state(key,value) VALUES('current_project_id',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (project_id,),
            )
            return True

    def current_project_id(self) -> str:
        """Return the saved active project, repairing missing state if necessary."""
        with self.session() as connection:
            row = _execute(connection,
                "SELECT value FROM app_state WHERE key='current_project_id'"
            ).fetchone()
            if row and _execute(connection, "SELECT 1 FROM projects WHERE id=?", (row["value"],)).fetchone():
                return row["value"]
        default_id = self.ensure_default_project()
        self.set_current_project(default_id)
        return default_id

    def replace_endpoints(self, project_id: str, endpoints: list[dict]) -> bool:
        """Replace the compatibility endpoint collection atomically."""
        if not self.get_project(project_id):
            return False
        collection_id = self._ensure_legacy_collection(project_id)
        with self.session() as connection:
            request_ids = [item.get("id") for item in endpoints if item.get("id")]
            for request_id in request_ids:
                existing = _execute(
                    connection,
                    "SELECT project_id,collection_id FROM endpoints WHERE id=?",
                    (request_id,),
                ).fetchone()
                if existing and (
                    existing["project_id"] != project_id
                    or existing["collection_id"] != collection_id
                ):
                    raise ValueError("An endpoint ID already belongs to another saved collection.")
            _execute(connection, "DELETE FROM endpoints WHERE collection_id=?", (collection_id,))
            for ordinal, endpoint in enumerate(endpoints):
                item = dict(endpoint)
                item.setdefault("id", str(uuid.uuid4()))
                item.setdefault("order", ordinal)
                item["collection_id"] = collection_id
                item.setdefault("include_for_generation", item.get("include", True))
                item.setdefault("include", item.get("include_for_generation", True))
                _execute(connection,
                    "INSERT INTO endpoints(id,project_id,collection_id,ordinal,payload_json) VALUES(?,?,?,?,?) "
                    "ON CONFLICT(id) DO UPDATE SET project_id=excluded.project_id,collection_id=excluded.collection_id,ordinal=excluded.ordinal,payload_json=excluded.payload_json",
                    (item["id"], project_id, collection_id, ordinal, self._encode(item)),
                )
            _execute(connection, "UPDATE projects SET updated_at=? WHERE id=?", (_now(), project_id))
            return True

    def add_endpoint(self, project_id: str, endpoint: dict) -> dict | None:
        """Insert or replace an endpoint by ID without creating duplicates."""
        project = self.get_project(project_id)
        if not project:
            return None
        item = dict(endpoint)
        item.setdefault("id", str(uuid.uuid4()))
        collection_id = self._ensure_legacy_collection(project_id)
        existing = next((ep for ep in project["endpoints"] if ep.get("id") == item["id"]), None)
        if existing:
            item = {**existing, **item}
        item["collection_id"] = collection_id
        item.setdefault("include_for_generation", item.get("include", True))
        item.setdefault("include", item.get("include_for_generation", True))
        return self.save_request(project_id, collection_id, item)

    def update_endpoint(self, project_id: str, endpoint_id: str, updates: dict) -> dict | None:
        """Update one endpoint payload and preserve unmodified fields."""
        project = self.get_project(project_id)
        if not project:
            return None
        endpoint = next((item for item in project["endpoints"] if item["id"] == endpoint_id), None)
        if endpoint is None:
            return None
        compatibility_updates = dict(updates)
        if "include" in compatibility_updates:
            compatibility_updates.setdefault("include_for_generation", compatibility_updates["include"])
        return self.update_request(project_id, endpoint_id, compatibility_updates)

    def delete_endpoint(self, project_id: str, endpoint_id: str) -> bool:
        """Delete an endpoint and compact the remaining endpoint order."""
        project = self.get_project(project_id)
        if not project:
            return False
        return self.delete_request(project_id, endpoint_id)

    def save_test_cases(self, project_id: str, test_cases: list[dict]) -> bool:
        """Upsert cases by ID in one transaction, retaining stable display order."""
        with self.session() as connection:
            if not _execute(connection, "SELECT 1 FROM projects WHERE id=?", (project_id,)).fetchone():
                return False
            for testcase in test_cases:
                item = dict(testcase)
                item.setdefault("id", str(uuid.uuid4()))
                row = _execute(connection,
                    "SELECT ordinal FROM test_cases WHERE id=? AND project_id=?",
                    (item["id"], project_id),
                ).fetchone()
                ordinal = row["ordinal"] if row else _execute(connection,
                    "SELECT COALESCE(MAX(ordinal)+1,0) AS ordinal FROM test_cases WHERE project_id=?",
                    (project_id,),
                ).fetchone()["ordinal"]
                _execute(connection,
                    "INSERT INTO test_cases(id,project_id,ordinal,payload_json) VALUES(?,?,?,?) "
                    "ON CONFLICT(id) DO UPDATE SET project_id=excluded.project_id, ordinal=excluded.ordinal, payload_json=excluded.payload_json",
                    (item["id"], project_id, ordinal, self._encode(item)),
                )
            _execute(connection, "UPDATE projects SET updated_at=? WHERE id=?", (_now(), project_id))
            return True

    def delete_test_case(self, project_id: str, test_case_id: str) -> bool:
        """Delete a test case by project and ID."""
        with self.session() as connection:
            deleted = _execute(connection,
                "DELETE FROM test_cases WHERE project_id=? AND id=?", (project_id, test_case_id)
            ).rowcount
            if deleted:
                _execute(connection, "UPDATE projects SET updated_at=? WHERE id=?", (_now(), project_id))
            return bool(deleted)

    def clear_test_cases(self, project_id: str) -> bool:
        """Remove every saved case and its execution history from a project."""
        with self.session() as connection:
            if not _execute(connection, "SELECT 1 FROM projects WHERE id=?", (project_id,)).fetchone():
                return False
            _execute(connection, "DELETE FROM executions WHERE project_id=?", (project_id,))
            _execute(connection, "DELETE FROM test_cases WHERE project_id=?", (project_id,))
            _execute(connection, "UPDATE projects SET updated_at=? WHERE id=?", (_now(), project_id))
            return True

    def update_test_case(self, project_id: str, test_case_id: str, updates: dict) -> dict | None:
        """Merge updates into a saved test case and return the persisted object."""
        project = self.get_project(project_id)
        if not project:
            return None
        testcase = next((item for item in project["test_cases"] if item["id"] == test_case_id), None)
        if testcase is None:
            return None
        testcase.update(updates)
        self.save_test_cases(project_id, [testcase])
        return testcase

    def find_test_case(self, test_case_id: str, project_id: str | None = None) -> tuple[str, dict] | None:
        """Find a test case in the requested project or across all projects."""
        projects = [project_id] if project_id else [item["id"] for item in self.list_projects()]
        for candidate_id in projects:
            project = self.get_project(candidate_id)
            if project:
                testcase = next((item for item in project["test_cases"] if item["id"] == test_case_id), None)
                if testcase:
                    return candidate_id, testcase
        return None

    def append_execution(self, project_id: str, test_case_id: str, result: dict) -> None:
        """Persist an execution result with a creation timestamp."""
        with self.session() as connection:
            _execute(connection,
                "INSERT INTO executions(id,project_id,test_case_id,created_at,payload_json) VALUES(?,?,?,?,?)",
                (str(uuid.uuid4()), project_id, test_case_id, _now(), self._encode(result)),
            )
            _execute(connection, "UPDATE projects SET updated_at=? WHERE id=?", (_now(), project_id))
