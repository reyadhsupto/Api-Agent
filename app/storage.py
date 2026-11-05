"""SQLite persistence for projects, endpoints, test cases, and executions."""

import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator


def _now() -> str:
    """Return a local ISO timestamp for persisted records."""
    return datetime.now().isoformat()


class Database:
    """Small SQLite repository that keeps the API's nested JSON payloads intact."""

    def __init__(self, path: str | Path | None = None):
        """Create the database wrapper and initialize tables at the selected path."""
        if path is None:
            path = os.getenv("API_AGENT_DB_PATH") or Path(__file__).resolve().parents[1] / ".data" / "api_agent.sqlite3"
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def connect(self) -> sqlite3.Connection:
        """Open a connection with foreign-key enforcement and row access by name."""
        connection = sqlite3.connect(self.path, timeout=15)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 15000")
        return connection

    @contextmanager
    def session(self) -> Iterator[sqlite3.Connection]:
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
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    is_default INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS endpoints (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    ordinal INTEGER NOT NULL,
                    payload_json TEXT NOT NULL
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
            )
        self.ensure_default_project()

    def ensure_default_project(self) -> str:
        """Create the standalone project when none exists and return its ID."""
        with self.session() as connection:
            row = connection.execute(
                "SELECT id FROM projects WHERE is_default = 1 ORDER BY created_at LIMIT 1"
            ).fetchone()
            if row:
                return row["id"]
            project_id = str(uuid.uuid4())
            now = _now()
            connection.execute(
                "INSERT INTO projects(id, name, description, is_default, created_at, updated_at) VALUES(?,?,?,?,?,?)",
                (project_id, "Default Project", "Standalone generated tests and endpoints", 1, now, now),
            )
            connection.execute(
                "INSERT OR IGNORE INTO app_state(key, value) VALUES('current_project_id', ?)",
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

    def get_project(self, project_id: str) -> dict | None:
        """Return a project with ordered endpoints, cases, and execution history."""
        with self.session() as connection:
            project = connection.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
            if not project:
                return None
            result = dict(project)
            result.pop("is_default", None)
            result["endpoints"] = [
                self._decode(row["payload_json"])
                for row in connection.execute(
                    "SELECT payload_json FROM endpoints WHERE project_id = ? ORDER BY ordinal, rowid",
                    (project_id,),
                )
            ]
            result["test_cases"] = [
                self._decode(row["payload_json"])
                for row in connection.execute(
                    "SELECT payload_json FROM test_cases WHERE project_id = ? ORDER BY ordinal, rowid",
                    (project_id,),
                )
            ]
            result["executions"] = [
                self._decode(row["payload_json"])
                for row in connection.execute(
                    "SELECT payload_json FROM executions WHERE project_id = ? ORDER BY created_at, rowid",
                    (project_id,),
                )
            ]
            return result

    def list_projects(self) -> list[dict]:
        """Return project summaries with endpoint and test counts."""
        with self.session() as connection:
            rows = connection.execute(
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
            connection.execute(
                "INSERT INTO projects(id,name,description,created_at,updated_at) VALUES(?,?,?,?,?)",
                (project_id, name, description, now, now),
            )
            connection.execute(
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
            connection.execute(
                "UPDATE projects SET name=?, description=?, updated_at=? WHERE id=?",
                (name, description, _now(), project_id),
            )
        return self.get_project(project_id)

    def delete_project(self, project_id: str) -> bool:
        """Delete a project and its dependent rows, then select a remaining project."""
        with self.session() as connection:
            deleted = connection.execute("DELETE FROM projects WHERE id=?", (project_id,)).rowcount
            if not deleted:
                return False
            active = connection.execute(
                "SELECT value FROM app_state WHERE key='current_project_id'"
            ).fetchone()
            if active and active["value"] == project_id:
                next_project = connection.execute(
                    "SELECT id FROM projects ORDER BY is_default DESC, created_at LIMIT 1"
                ).fetchone()
                if next_project:
                    connection.execute(
                        "UPDATE app_state SET value=? WHERE key='current_project_id'",
                        (next_project["id"],),
                    )
                else:
                    connection.execute("DELETE FROM app_state WHERE key='current_project_id'")
        self.ensure_default_project()
        return True

    def set_current_project(self, project_id: str) -> bool:
        """Persist the selected project ID if it exists."""
        with self.session() as connection:
            exists = connection.execute("SELECT 1 FROM projects WHERE id=?", (project_id,)).fetchone()
            if not exists:
                return False
            connection.execute(
                "INSERT INTO app_state(key,value) VALUES('current_project_id',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (project_id,),
            )
            return True

    def current_project_id(self) -> str:
        """Return the saved active project, repairing missing state if necessary."""
        with self.session() as connection:
            row = connection.execute(
                "SELECT value FROM app_state WHERE key='current_project_id'"
            ).fetchone()
            if row and connection.execute("SELECT 1 FROM projects WHERE id=?", (row["value"],)).fetchone():
                return row["value"]
        default_id = self.ensure_default_project()
        self.set_current_project(default_id)
        return default_id

    def replace_endpoints(self, project_id: str, endpoints: list[dict]) -> bool:
        """Replace a project's ordered endpoint collection atomically."""
        with self.session() as connection:
            if not connection.execute("SELECT 1 FROM projects WHERE id=?", (project_id,)).fetchone():
                return False
            connection.execute("DELETE FROM endpoints WHERE project_id=?", (project_id,))
            for ordinal, endpoint in enumerate(endpoints):
                item = dict(endpoint)
                item.setdefault("id", str(uuid.uuid4()))
                item.setdefault("order", ordinal)
                connection.execute(
                    "INSERT INTO endpoints(id,project_id,ordinal,payload_json) VALUES(?,?,?,?)",
                    (item["id"], project_id, ordinal, self._encode(item)),
                )
            connection.execute("UPDATE projects SET updated_at=? WHERE id=?", (_now(), project_id))
            return True

    def add_endpoint(self, project_id: str, endpoint: dict) -> dict | None:
        """Insert or replace an endpoint by ID without creating duplicates."""
        project = self.get_project(project_id)
        if not project:
            return None
        item = dict(endpoint)
        item.setdefault("id", str(uuid.uuid4()))
        ordinal = next((i for i, ep in enumerate(project["endpoints"]) if ep.get("id") == item["id"]), len(project["endpoints"]))
        item.setdefault("order", ordinal)
        with self.session() as connection:
            connection.execute(
                "INSERT INTO endpoints(id,project_id,ordinal,payload_json) VALUES(?,?,?,?) "
                "ON CONFLICT(id) DO UPDATE SET project_id=excluded.project_id, ordinal=excluded.ordinal, payload_json=excluded.payload_json",
                (item["id"], project_id, ordinal, self._encode(item)),
            )
            connection.execute("UPDATE projects SET updated_at=? WHERE id=?", (_now(), project_id))
        return item

    def update_endpoint(self, project_id: str, endpoint_id: str, updates: dict) -> dict | None:
        """Update one endpoint payload and preserve unmodified fields."""
        project = self.get_project(project_id)
        if not project:
            return None
        endpoint = next((item for item in project["endpoints"] if item["id"] == endpoint_id), None)
        if endpoint is None:
            return None
        endpoint.update(updates)
        self.replace_endpoints(project_id, project["endpoints"])
        return endpoint

    def delete_endpoint(self, project_id: str, endpoint_id: str) -> bool:
        """Delete an endpoint and compact the remaining endpoint order."""
        project = self.get_project(project_id)
        if not project:
            return False
        remaining = [item for item in project["endpoints"] if item["id"] != endpoint_id]
        if len(remaining) == len(project["endpoints"]):
            return False
        return self.replace_endpoints(project_id, remaining)

    def save_test_cases(self, project_id: str, test_cases: list[dict]) -> bool:
        """Upsert cases by ID in one transaction, retaining stable display order."""
        with self.session() as connection:
            if not connection.execute("SELECT 1 FROM projects WHERE id=?", (project_id,)).fetchone():
                return False
            for testcase in test_cases:
                item = dict(testcase)
                item.setdefault("id", str(uuid.uuid4()))
                row = connection.execute(
                    "SELECT ordinal FROM test_cases WHERE id=? AND project_id=?",
                    (item["id"], project_id),
                ).fetchone()
                ordinal = row["ordinal"] if row else connection.execute(
                    "SELECT COALESCE(MAX(ordinal)+1,0) FROM test_cases WHERE project_id=?",
                    (project_id,),
                ).fetchone()[0]
                connection.execute(
                    "INSERT INTO test_cases(id,project_id,ordinal,payload_json) VALUES(?,?,?,?) "
                    "ON CONFLICT(id) DO UPDATE SET project_id=excluded.project_id, ordinal=excluded.ordinal, payload_json=excluded.payload_json",
                    (item["id"], project_id, ordinal, self._encode(item)),
                )
            connection.execute("UPDATE projects SET updated_at=? WHERE id=?", (_now(), project_id))
            return True

    def delete_test_case(self, project_id: str, test_case_id: str) -> bool:
        """Delete a test case by project and ID."""
        with self.session() as connection:
            deleted = connection.execute(
                "DELETE FROM test_cases WHERE project_id=? AND id=?", (project_id, test_case_id)
            ).rowcount
            if deleted:
                connection.execute("UPDATE projects SET updated_at=? WHERE id=?", (_now(), project_id))
            return bool(deleted)

    def clear_test_cases(self, project_id: str) -> bool:
        """Remove every saved case and its execution history from a project."""
        with self.session() as connection:
            if not connection.execute("SELECT 1 FROM projects WHERE id=?", (project_id,)).fetchone():
                return False
            connection.execute("DELETE FROM executions WHERE project_id=?", (project_id,))
            connection.execute("DELETE FROM test_cases WHERE project_id=?", (project_id,))
            connection.execute("UPDATE projects SET updated_at=? WHERE id=?", (_now(), project_id))
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
            connection.execute(
                "INSERT INTO executions(id,project_id,test_case_id,created_at,payload_json) VALUES(?,?,?,?,?)",
                (str(uuid.uuid4()), project_id, test_case_id, _now(), self._encode(result)),
            )
            connection.execute("UPDATE projects SET updated_at=? WHERE id=?", (_now(), project_id))


database = Database()
