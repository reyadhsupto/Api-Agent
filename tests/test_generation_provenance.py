"""Generation route tests for persisted source endpoint association."""

from types import SimpleNamespace
import sys

from app import storage

if "app.main" not in sys.modules:
    _database_class = storage.Database
    storage.Database = lambda: SimpleNamespace()
    from app import main
    storage.Database = _database_class
else:
    from app import main

from app.schemas import TestCaseGenerateRequest as GenerateRequest


def test_single_generation_persists_endpoint_group_metadata(monkeypatch):
    """Generated cases keep the validated saved endpoint identity and label."""
    project = {
        "id": "project-1",
        "endpoints": [{
            "id": "request-1", "name": "", "method": "GET",
            "url": "https://api.test/items",
        }],
    }
    saved = []

    class FakeDatabase:
        def get_project(self, project_id):
            return project if project_id == project["id"] else None

        def save_test_cases(self, project_id, cases):
            saved.extend(cases)
            return True

    monkeypatch.setattr(main, "database", FakeDatabase())
    monkeypatch.setattr(main, "generate_test_cases", lambda **kwargs: [{
        "name": "Returns items", "type": "positive",
        "request": {"method": "GET", "url": "https://api.test/items"},
    }])
    monkeypatch.setattr(main, "_assign_test_case_ids", lambda project_id, cases: None)
    monkeypatch.setattr(main, "_ensure_response_schema_defaults", lambda cases: None)

    generated = main.generate_test_cases_endpoint(GenerateRequest(
        parsed_curl={"method": "GET", "url": "https://api.test/items"},
        project_id="project-1", source_endpoint_id="request-1",
    ))

    assert generated[0]["source_endpoint_id"] == "request-1"
    assert generated[0]["source_endpoint_name"] == "https://api.test/items"
    assert saved == generated


def test_single_generation_rejects_endpoint_outside_project(monkeypatch):
    """A source request ID must belong to the requested project."""

    class FakeDatabase:
        def get_project(self, project_id):
            return {"id": project_id, "endpoints": []}

    monkeypatch.setattr(main, "database", FakeDatabase())
    request = GenerateRequest(
        parsed_curl={"method": "GET", "url": "https://api.test/items"},
        project_id="project-1", source_endpoint_id="unknown",
    )

    try:
        main.generate_test_cases_endpoint(request)
    except main.HTTPException as exc:
        assert exc.status_code == 404
    else:
        raise AssertionError("Expected unknown source endpoint to be rejected")
