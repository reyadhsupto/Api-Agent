"""Regression tests for SQLite project persistence and API integration."""

from app import main
from app.schemas import TestCaseGenerateRequest as GenerateRequest
from app.storage import Database


def test_sqlite_data_survives_reopen_and_project_delete_cascades(tmp_path):
    """Projects, endpoints, cases, executions, and active selection persist."""
    database_path = tmp_path / "api-agent.sqlite3"
    database = Database(database_path)
    project = database.create_project("Sample", "Persistent project")
    project_id = project["id"]
    endpoint = database.add_endpoint(
        project_id,
        {"id": "endpoint-1", "method": "GET", "url": "https://example.test"},
    )
    testcase = {
        "id": "flow-1",
        "is_flow": True,
        "steps": [{"step_order": 1, "endpoint": endpoint, "assertions": {"status": []}}],
    }
    database.save_test_cases(project_id, [testcase])
    database.append_execution(project_id, "flow-1", {"test_case_id": "flow-1", "status": "passed"})
    database.set_current_project(project_id)

    reopened = Database(database_path)
    restored = reopened.get_project(project_id)
    assert restored["name"] == "Sample"
    assert restored["endpoints"][0]["url"] == "https://example.test"
    assert restored["test_cases"][0]["steps"][0]["assertions"] == {"status": []}
    assert restored["executions"][0]["status"] == "passed"
    assert reopened.current_project_id() == project_id

    assert reopened.delete_project(project_id)
    assert reopened.get_project(project_id) is None
    assert reopened.current_project_id() != project_id
    assert any(item["is_default"] for item in reopened.list_projects())


def test_database_upserts_endpoint_and_test_case_instead_of_duplicating(tmp_path):
    """Repeated project saves update records by ID and preserve collection counts."""
    database = Database(tmp_path / "upsert.sqlite3")
    project_id = database.create_project("Upsert") ["id"]

    database.replace_endpoints(project_id, [{"id": "ep-1", "url": "/old"}])
    database.replace_endpoints(project_id, [{"id": "ep-1", "url": "/new"}])
    testcase = {"id": "tc-1", "name": "Before"}
    database.save_test_cases(project_id, [testcase])
    database.save_test_cases(project_id, [{"id": "tc-1", "name": "After"}])

    project = database.get_project(project_id)
    assert len(project["endpoints"]) == 1
    assert project["endpoints"][0]["url"] == "/new"
    assert len(project["test_cases"]) == 1
    assert project["test_cases"][0]["name"] == "After"


def test_generated_cases_are_persisted_to_selected_project(tmp_path, monkeypatch):
    """The existing generation API stores results and avoids generated ID collisions."""
    database = Database(tmp_path / "generation.sqlite3")
    project = database.create_project("Generated")
    monkeypatch.setattr(main, "database", database)
    monkeypatch.setattr(
        main,
        "generate_test_cases",
        lambda **kwargs: [{
            "id": "tc_1",
            "type": "positive",
            "name": "Generated case",
            "request": {"method": "GET", "url": "https://example.test"},
        }],
    )
    request = GenerateRequest(
        parsed_curl={"method": "GET", "url": "https://example.test"},
        project_id=project["id"],
    )

    first = main.generate_test_cases_endpoint(request)
    second = main.generate_test_cases_endpoint(request)
    saved = database.get_project(project["id"])["test_cases"]

    assert len(first) == len(second) == 1
    assert first[0]["id"] != second[0]["id"]
    assert len(saved) == 2


def test_project_and_execution_routes_read_and_write_sqlite(tmp_path, monkeypatch):
    """API CRUD operations and execution history use the SQLite repository."""
    database = Database(tmp_path / "routes.sqlite3")
    monkeypatch.setattr(main, "database", database)

    project = main.create_project({"name": "Route Project", "description": "CRUD"})
    project_id = project["id"]
    endpoint = main.add_endpoint(
        project_id,
        {"id": "route-ep", "method": "GET", "url": "https://example.test"},
    )
    assert endpoint["id"] == "route-ep"
    assert main.update_endpoint(project_id, "route-ep", {"url": "https://updated.test"})["url"] == "https://updated.test"
    assert main.replace_endpoints(project_id, {"endpoints": [endpoint]})["message"] == "Saved 1 endpoint(s)"

    testcase = {"id": "route-tc", "name": "Before", "request": {"url": "https://updated.test"}}
    main.save_test_cases(project_id, {"test_cases": [testcase]})
    main.update_test_case(project_id, "route-tc", {"name": "After"})
    assert main.get_test_cases(project_id)[0]["name"] == "After"

    monkeypatch.setattr(
        main,
        "execute_test_case",
        lambda testcase, assertions=None: {
            "test_case_id": testcase["id"],
            "status": "passed",
        },
    )
    result = main.execute_test_case_endpoint({"test_case_id": "route-tc", "project_id": project_id})
    assert result["status"] == "passed"
    assert main.get_project(project_id)["executions"][0]["test_case_id"] == "route-tc"

    main.delete_test_case(project_id, "route-tc")
    main.delete_endpoint(project_id, "route-ep")
    assert main.get_test_cases(project_id) == []
    assert database.get_project(project_id)["endpoints"] == []
    assert main.list_projects()[0]["name"] == "Default Project"
