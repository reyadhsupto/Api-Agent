"""Regression tests for PostgreSQL project persistence and API integration."""

import os
import uuid

import pytest
from fastapi import HTTPException
from app import main
from app.schemas import TestCaseGenerateRequest as GenerateRequest
from app.storage import Database


@pytest.fixture
def database():
    """Use an explicitly configured test database and clean created projects."""
    dsn = (
        os.getenv("API_AGENT_TEST_DATABASE_URL")
        or os.getenv("DATABASE_URL")
        or main.database.dsn
    )
    db = Database(dsn)
    before_ids = {project["id"] for project in db.list_projects()}
    yield db
    for project in db.list_projects():
        if project["id"] not in before_ids and not project.get("is_default"):
            db.delete_project(project["id"])


def test_postgres_data_survives_reopen_and_project_delete_cascades(database):
    """Projects, endpoints, cases, executions, and active selection persist."""
    project = database.create_project(f"Sample {uuid.uuid4()}", "Persistent project")
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

    reopened = Database(database.dsn)
    restored = reopened.get_project(project_id)
    assert restored["name"].startswith("Sample ")
    assert restored["endpoints"][0]["url"] == "https://example.test"
    assert restored["test_cases"][0]["steps"][0]["assertions"] == {"status": []}
    assert restored["executions"][0]["status"] == "passed"
    assert reopened.current_project_id() == project_id

    assert reopened.delete_project(project_id)
    assert reopened.get_project(project_id) is None
    assert reopened.current_project_id() != project_id
    assert any(item["is_default"] for item in reopened.list_projects())


def test_database_upserts_endpoint_and_test_case_instead_of_duplicating(database):
    """Repeated project saves update records by ID and preserve collection counts."""
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


def test_successful_follow_up_archives_cases_and_prunes_suites_atomically(database):
    """Superseded cases leave suites while their payload and execution history remain."""
    project_id = database.create_project(f"Refinement {uuid.uuid4()}")["id"]
    source = {"id": "source-case", "name": "Old scenario"}
    database.save_test_cases(project_id, [source])
    database.append_execution(project_id, source["id"], {"status": "passed"})
    run = database.save_test_run(project_id, "Regression", [source["id"]])

    activity = database.save_follow_up_generation(
        project_id,
        [{"id": "refined-case", "source_case_id": source["id"], "name": "Updated scenario"}],
        {"mode": "General", "status": "succeeded", "generated_case_ids": ["refined-case"]},
        [source["id"]],
    )

    project = database.get_project(project_id)
    cases = {item["id"]: item for item in project["test_cases"]}
    assert cases[source["id"]]["superseded_by_activity_id"] == activity["id"]
    assert cases["refined-case"]["source_case_id"] == source["id"]
    assert database.list_test_case_executions(project_id, source["id"], 10)[0]["status"] == "passed"
    saved_run = next(item for item in project["test_runs"] if item["id"] == run["id"])
    assert saved_run["case_ids"] == []
    assert database.get_generation_activity(project_id, activity["id"])["archived_case_ids"] == [source["id"]]


def test_legacy_endpoint_migration_is_repeatable_and_preserves_payload(database):
    """Legacy endpoint rows are assigned once without changing IDs, flags, or order."""
    project_id = database.create_project("Legacy migration") ["id"]
    legacy = {
        "id": "legacy-request-1", "name": "Existing", "method": "POST",
        "url": "https://example.test", "include": False, "headers": {"X-Key": "v"},
        "order": 7,
    }
    with database.session() as connection:
        connection.execute(
            "INSERT INTO endpoints(id,project_id,collection_id,ordinal,payload_json) VALUES(%s,%s,NULL,%s,%s)",
            (legacy["id"], project_id, 7, database._encode(legacy)),
        )

    database.migrate_legacy_endpoints()
    database.migrate_legacy_endpoints()
    project = database.get_project(project_id)

    assert len(project["collections"]) == 1
    assert project["collections"][0]["name"] == "Imported Endpoints"
    migrated = project["endpoints"][0]
    assert migrated["id"] == legacy["id"]
    assert migrated["include_for_generation"] is False
    assert migrated["headers"] == legacy["headers"]
    assert migrated["order"] == 7


def test_collection_request_crud_and_project_cascade(database):
    """Saved requests remain ordered in collections and cascade with their project."""
    project_id = database.create_project("Collection CRUD") ["id"]
    collection = database.create_collection(project_id, "Auth")
    saved = database.save_request(project_id, collection["id"], {
        "name": "Login", "method": "POST", "url": "/login",
        "include_for_generation": True,
        "assertions": {
            "status": [{"id": "status-1", "enabled": True, "expected_status": 201}],
            "response_schema": [{"id": "schema-1", "enabled": False, "schema": '{"type":"object"}'}],
        },
    })

    assert saved["id"]
    assert saved["assertions"]["status"][0]["expected_status"] == 201
    assert database.update_request(project_id, saved["id"], {"name": "Create session"})["name"] == "Create session"
    assert database.get_collection(project_id, collection["id"])["requests"][0]["id"] == saved["id"]
    assert database.delete_project(project_id)
    assert database.get_collection(project_id, collection["id"]) is None


def test_generation_order_persists_independently_of_collection_order(database):
    """Project flow order survives reopen and remains separate from collection order."""
    project_id = database.create_project("Generation order") ["id"]
    first_collection = database.create_collection(project_id, "First")
    second_collection = database.create_collection(project_id, "Second")
    first = database.save_request(project_id, first_collection["id"], {
        "name": "First request", "url": "/first", "include_for_generation": True,
    })
    second = database.save_request(project_id, second_collection["id"], {
        "name": "Second request", "url": "/second", "include_for_generation": True,
    })

    assert database.set_generation_order(project_id, [second["id"], first["id"]]) == [second["id"], first["id"]]
    reopened = Database(database.dsn).get_project(project_id)

    assert [item["id"] for item in reopened["endpoints"]] == [first["id"], second["id"]]
    assert reopened["generation_order_ids"] == [second["id"], first["id"]]


def test_generation_order_api_validates_project_owned_unique_ids(database, monkeypatch):
    """Generation-order route accepts valid requests and rejects invalid IDs."""
    monkeypatch.setattr(main, "database", database)
    project_id = database.create_project("Generation order route") ["id"]
    request = database.add_endpoint(project_id, {
        "id": "order-route-request", "include_for_generation": True,
    })

    assert main.update_project_generation_order(project_id, {"request_ids": [request["id"]]}) == {
        "generation_order_ids": [request["id"]]
    }
    with pytest.raises(HTTPException) as duplicate_error:
        main.update_project_generation_order(project_id, {"request_ids": [request["id"], request["id"]]})
    assert duplicate_error.value.status_code == 422
    with pytest.raises(HTTPException) as unknown_error:
        main.update_project_generation_order(project_id, {"request_ids": ["missing"]})
    assert unknown_error.value.status_code == 422
    with pytest.raises(HTTPException) as missing_project_error:
        main.update_project_generation_order("missing-project", {"request_ids": []})
    assert missing_project_error.value.status_code == 404


def test_named_test_runs_upsert_unique_names_and_validate_project_cases(database):
    """Named runs preserve ordered IDs, update by ID, and stay project-scoped."""
    project_id = database.create_project("Named runs") ["id"]
    other_project_id = database.create_project("Other named runs") ["id"]
    database.save_test_cases(project_id, [
        {"id": "run-case-a", "name": "A"},
        {"id": "run-case-b", "name": "B"},
    ])
    database.save_test_cases(other_project_id, [{"id": "foreign-case", "name": "Foreign"}])

    created = database.save_test_run(project_id, "Smoke", ["run-case-b", "run-case-a"])
    updated = database.save_test_run(
        project_id, "Smoke updated", ["run-case-a"], created["id"],
    )

    assert updated["id"] == created["id"]
    assert updated["case_ids"] == ["run-case-a"]
    assert database.get_project(project_id)["test_runs"][0]["name"] == "Smoke updated"
    cleared = database.save_test_run(project_id, "Smoke updated", [], created["id"])
    assert cleared["case_ids"] == []
    with pytest.raises(FileExistsError):
        database.save_test_run(project_id, "SMOKE UPDATED", ["run-case-b"])
    with pytest.raises(ValueError, match="belong to the selected project"):
        database.save_test_run(project_id, "Foreign", ["foreign-case"])
    assert database.list_test_runs(other_project_id) == []
    assert database.delete_test_run(project_id, created["id"])
    assert database.list_test_runs(project_id) == []


def test_named_test_run_routes_return_project_scoped_crud(database, monkeypatch):
    """Run routes create, update, list, reject duplicate names, and delete."""
    monkeypatch.setattr(main, "database", database)
    project_id = database.create_project("Named run routes") ["id"]
    database.save_test_cases(project_id, [{"id": "route-run-case", "name": "Case"}])

    created = main.create_project_test_run(project_id, {
        "name": "Quick check", "case_ids": ["route-run-case"],
    })
    updated = main.update_project_test_run(project_id, created["id"], {
        "name": "Quick check v2", "case_ids": ["route-run-case"],
    })

    assert main.list_project_test_runs(project_id)[0]["id"] == created["id"]
    assert updated["name"] == "Quick check v2"
    with pytest.raises(HTTPException) as duplicate_error:
        main.create_project_test_run(project_id, {
            "name": "quick CHECK V2", "case_ids": ["route-run-case"],
        })
    assert duplicate_error.value.status_code == 409
    with pytest.raises(HTTPException) as invalid_case_error:
        main.create_project_test_run(project_id, {
            "name": "Invalid", "case_ids": ["missing-case"],
        })
    assert invalid_case_error.value.status_code == 422
    assert main.delete_project_test_run(project_id, created["id"]) == {"message": "Test run deleted"}


def test_generated_cases_are_persisted_to_selected_project(database, monkeypatch):
    """The existing generation API stores results and avoids generated ID collisions."""
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


def test_generated_cases_keep_source_endpoint_group_metadata(database, monkeypatch):
    """Generation validates and persists its originating endpoint label and ID."""
    project = database.create_project("Endpoint grouping")
    monkeypatch.setattr(main, "database", database)
    database.add_endpoint(project["id"], {
        "id": "source-request", "name": "", "method": "GET",
        "url": "https://example.test/items",
    })
    monkeypatch.setattr(main, "generate_test_cases", lambda **kwargs: [{
        "type": "positive", "name": "Returns items",
        "request": {"method": "GET", "url": "https://example.test/items"},
    }])

    generated = main.generate_test_cases_endpoint(GenerateRequest(
        parsed_curl={"method": "GET", "url": "https://example.test/items"},
        project_id=project["id"], source_endpoint_id="source-request",
    ))

    assert generated[0]["source_endpoint_id"] == "source-request"
    assert generated[0]["source_endpoint_name"] == "https://example.test/items"
    assert database.get_project(project["id"])["test_cases"][0]["source_endpoint_id"] == "source-request"


def test_project_and_execution_routes_read_and_write_postgres(database, monkeypatch):
    """API CRUD operations and execution history use the PostgreSQL repository."""
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


def test_editing_saved_flow_keeps_old_execution_history(database, monkeypatch):
    """Flow edits update the same case row while retaining earlier execution results."""
    monkeypatch.setattr(main, "database", database)
    project_id = database.create_project("Editable flow") ["id"]
    original = {
        "id": "editable-flow", "is_flow": True, "name": "Before",
        "steps": [{
            "step_order": 1,
            "endpoint": {"method": "GET", "url": "https://example.test/old"},
            "variable_mappings": [],
        }],
    }
    database.save_test_cases(project_id, [original])
    database.append_execution(project_id, "editable-flow", {"status": "passed"})
    updated = {
        **original,
        "name": "After",
        "steps": [
            original["steps"][0],
            {
                "step_order": 2,
                "endpoint_id": "saved-request",
                "endpoint": {"method": "POST", "url": "https://example.test/new"},
                "variable_mappings": [{
                    "from": "1:$.token", "to": "headers.Authorization",
                    "transform": "Bearer {value}",
                }],
            },
        ],
    }

    response = main.update_test_case(project_id, "editable-flow", updated)
    project = database.get_project(project_id)

    assert response["id"] == "editable-flow"
    assert len(project["test_cases"]) == 1
    assert len(project["test_cases"][0]["steps"]) == 2
    assert project["test_cases"][0]["steps"][1]["variable_mappings"][0]["to"] == "headers.Authorization"
    assert len(project["executions"]) == 1
    assert project["executions"][0]["status"] == "passed"


def test_execution_persists_unsaved_configuration_snapshot(database, monkeypatch):
    """Runs of unsaved edits persist their exact case snapshot without saving the case."""
    monkeypatch.setattr(main, "database", database)
    project_id = database.create_project("Unsaved execution") ["id"]
    database.save_test_cases(project_id, [{
        "id": "unsaved-edit", "request": {"method": "GET", "url": "https://example.test/old"},
    }])
    captured = {}

    def fake_execute(test_case, assertions=None):
        captured.update(test_case)
        return {"test_case_id": test_case["id"], "status": "passed"}

    monkeypatch.setattr(main, "execute_test_case", fake_execute)
    main.execute_test_case_endpoint({
        "test_case_id": "unsaved-edit",
        "project_id": project_id,
        "test_case": {
            "id": "unsaved-edit",
            "request": {"method": "POST", "url": "https://example.test/edited", "query_params": {"q": "yes"}},
        },
    })

    project = database.get_project(project_id)
    assert captured["request"]["method"] == "POST"
    assert project["test_cases"][0]["request"]["url"] == "https://example.test/old"
    assert project["executions"][0]["test_case_snapshot"]["request"]["url"] == "https://example.test/edited"
    assert database.list_test_case_executions(project_id, "unsaved-edit")[0]["status"] == "passed"


def test_release_revision_keeps_baseline_and_links_new_case_ids(database, monkeypatch):
    """A revision stores a separate complete suite with source linkage and membership."""
    monkeypatch.setattr(main, "database", database)
    project = database.create_project("Release revisions")
    project_id = project["id"]
    endpoint = database.add_endpoint(project_id, {
        "id": "release-ep", "method": "GET", "url": "https://example.test/v2",
    })
    baseline = {
        "id": "baseline-case", "name": "Old case", "request": {"method": "GET", "url": "https://example.test/v1"},
    }
    database.save_test_cases(project_id, [baseline])
    source = database.record_generation_activity(project_id, {
        "business_requirements": "Previous rules", "generated_case_ids": ["baseline-case"],
    })
    captured = {}

    def fake_revision(cases, endpoints, previous, notes, trace, prior_release_notes=""):
        captured.update({"previous": previous, "notes": notes, "endpoints": endpoints})
        return [
            {"id": "temp-1", "source_case_id": "baseline-case", "name": "Updated", "type": "positive",
             "request": {"method": "GET", "url": endpoint["url"]}},
            {"id": "temp-new", "source_case_id": None, "name": "Added", "type": "negative",
             "request": {"method": "GET", "url": endpoint["url"]}},
        ]

    monkeypatch.setattr(main, "generate_test_case_revision", fake_revision)
    response = main.create_test_case_revision(project_id, main.TestCaseRevisionRequest(
        source_activity_id=source["id"], baseline_case_ids=["baseline-case"],
        release_label="Release 2", release_notes="Changed endpoint behavior", endpoint_ids=["release-ep"],
    ))
    stored = database.get_project(project_id)
    old_case = next(item for item in stored["test_cases"] if item["id"] == "baseline-case")

    assert captured == {"previous": "Previous rules", "notes": "Changed endpoint behavior", "endpoints": [endpoint]}
    assert old_case == baseline
    assert response["revision"]["label"] == "Release 2"
    assert len(response["revision"]["case_ids"]) == 2
    revised_cases = [item for item in stored["test_cases"] if item.get("revision_id") == response["revision"]["id"]]
    assert len(revised_cases) == 2
    assert next(item for item in revised_cases if item.get("source_case_id"))["source_case_id"] == "baseline-case"


def test_test_case_update_rejects_invalid_mapping_target(database, monkeypatch):
    """Unsupported mapping destinations return an actionable API validation error."""
    monkeypatch.setattr(main, "database", database)
    project_id = database.create_project("Invalid mapping") ["id"]
    testcase = {
        "id": "invalid-map", "is_flow": True,
        "steps": [
            {
                "step_order": 1,
                "endpoint": {"method": "POST", "url": "https://example.test/login"},
                "variable_mappings": [],
            },
            {
                "step_order": 2,
                "endpoint": {"method": "GET", "url": "https://example.test/profile"},
                "variable_mappings": [{"from": "$.token", "to": "unknown.target"}],
            },
        ],
    }
    database.save_test_cases(project_id, [testcase])

    with pytest.raises(HTTPException) as error:
        main.update_test_case(project_id, "invalid-map", testcase)
    assert "unsupported destination" in error.value.detail
