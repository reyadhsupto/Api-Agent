"""Generation route tests for persisted source endpoint association."""

from types import SimpleNamespace
import copy
import sys
from uuid import UUID

from app import storage

if "app.main" not in sys.modules:
    _database_class = storage.Database
    storage.Database = lambda: SimpleNamespace()
    from app import main
    storage.Database = _database_class
else:
    from app import main

from app.schemas import (
    FlowGenerateRequest, GenerationFollowUpRequest, ManualTestResultRequest,
    TestCaseGenerateRequest as GenerateRequest,
)


def test_generated_case_ids_are_backend_uuids(monkeypatch):
    """Replace readable model IDs with distinct UUIDs before saving generated cases."""
    class FakeDatabase:
        def find_test_case(self, test_case_id):
            return None

    cases = [{"id": "flow-positive"}, {"id": "flow-negative"}]
    monkeypatch.setattr(main, "database", FakeDatabase())

    main._assign_test_case_ids("project-1", cases)

    assigned_ids = [case["id"] for case in cases]
    assert len(set(assigned_ids)) == 2
    assert all(str(UUID(case_id)) == case_id for case_id in assigned_ids)


def test_single_generation_persists_endpoint_group_metadata(monkeypatch):
    """Generated cases keep the validated saved endpoint identity and label."""
    project = {
        "id": "project-1",
        "test_cases": [{"id": "example-1", "name": "Example negative", "type": "negative"}],
        "endpoints": [{
            "id": "request-1", "name": "", "method": "GET",
            "url": "https://api.test/items",
        }],
    }
    saved = []
    generation_calls = []

    class FakeDatabase:
        def get_project(self, project_id):
            return project if project_id == project["id"] else None

        def save_test_cases(self, project_id, cases):
            saved.extend(cases)
            return True

        def record_generation_activity(self, project_id, activity):
            return {**activity, "id": "activity-generation"}

    monkeypatch.setattr(main, "database", FakeDatabase())
    def generate(**kwargs):
        generation_calls.append(kwargs)
        return [{
            "name": "Returns items", "type": "positive",
            "request": {"method": "GET", "url": "https://api.test/items"},
        }]

    monkeypatch.setattr(main, "generate_test_cases", generate)
    monkeypatch.setattr(main, "_assign_test_case_ids", lambda project_id, cases: None)
    monkeypatch.setattr(main, "_ensure_response_schema_defaults", lambda cases: None)

    generated = main.generate_test_cases_endpoint(GenerateRequest(
        parsed_curl={"method": "GET", "url": "https://api.test/items"},
        project_id="project-1", source_endpoint_id="request-1",
        example_test_case_ids=["example-1"],
    ))

    assert generated["test_cases"][0]["source_endpoint_id"] == "request-1"
    assert generated["test_cases"][0]["source_endpoint_name"] == "https://api.test/items"
    assert saved == generated["test_cases"]
    assert generated["clarification_questions"] == []
    assert generation_calls[0]["example_test_cases"] == project["test_cases"]


def test_generation_examples_are_loaded_in_requested_order_and_project_scoped(monkeypatch):
    """Only saved cases owned by the selected project may become LLM examples."""
    project = {"id": "project-1", "test_cases": [
        {"id": "example-a", "name": "A"},
        {"id": "example-b", "name": "B"},
    ]}

    class FakeDatabase:
        def get_project(self, project_id):
            return project if project_id == "project-1" else None

    monkeypatch.setattr(main, "database", FakeDatabase())

    assert [item["id"] for item in main._load_generation_examples(
        "project-1", ["example-b", "example-a", "example-b"],
    )] == ["example-b", "example-a"]
    try:
        main._load_generation_examples("project-1", ["from-another-project"])
    except main.HTTPException as exc:
        assert exc.status_code == 404
        assert "from-another-project" in exc.detail
    else:
        raise AssertionError("Expected unknown project example to be rejected")


def test_flow_generation_passes_saved_examples_and_requirements_to_generator(monkeypatch):
    """Project flow generation uses validated examples with the selected endpoints."""
    project = {
        "id": "project-1",
        "endpoints": [],
        "test_cases": [{"id": "example-flow", "name": "Existing checkout flow"}],
    }
    calls = []

    class FakeDatabase:
        def get_project(self, project_id):
            return project if project_id == "project-1" else None

        def save_test_cases(self, project_id, cases):
            return True

    def generate(**kwargs):
        calls.append(kwargs)
        return [{"name": "New checkout flow", "steps": [{
            "step_order": 1, "endpoint_id": "request-1",
            "endpoint": {"method": "GET", "url": "https://api.test/items"},
        }]}]

    monkeypatch.setattr(main, "database", FakeDatabase())
    monkeypatch.setattr(main, "generate_flow_test_cases", generate)
    monkeypatch.setattr(main, "_assign_test_case_ids", lambda project_id, cases: None)
    monkeypatch.setattr(main, "_ensure_response_schema_defaults", lambda cases: None)

    result = main.generate_flow_test_cases_project("project-1", FlowGenerateRequest(
        endpoints=[{"id": "request-1", "method": "GET", "url": "https://api.test/items"}],
        business_requirements="Keep authentication mandatory",
        example_test_case_ids=["example-flow"],
    ))

    assert result["test_cases"][0]["is_flow"] is True
    assert result["clarification_questions"] == []
    assert calls[0]["business_requirements"] == "Keep authentication mandatory"
    assert calls[0]["example_test_cases"] == project["test_cases"]
    assert calls[0]["endpoints"][0]["id"] == "request-1"


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


def test_manual_general_result_is_appended_with_case_snapshot(monkeypatch):
    """Manual marks persist history and update the current general-case status."""
    case = {"id": "general-1", "case_kind": "general", "manual_steps": ["Review the screen"]}
    appended = []
    updates = []

    class FakeDatabase:
        def find_test_case(self, test_case_id, project_id):
            return project_id, case

        def append_execution(self, project_id, test_case_id, result):
            appended.append(result)

        def update_test_case(self, project_id, test_case_id, changes):
            updates.append(changes)
            return {**case, **changes}

    monkeypatch.setattr(main, "database", FakeDatabase())
    result = main.mark_manual_test_result("project-1", "general-1", ManualTestResultRequest(status="failed"))

    assert result["status"] == "failed"
    assert appended[0]["manual_result"] is True
    assert appended[0]["test_case_snapshot"]["manual_steps"] == ["Review the screen"]
    assert updates == [{"manual_status": "failed"}]


def test_general_generation_persists_selected_case_collection(monkeypatch):
    """General generation stores its named context collection on every case."""
    project = {"id": "project-1", "test_cases": [], "endpoints": [], "collections": []}
    saved = []

    class FakeDatabase:
        def get_project(self, project_id):
            return project

        def save_test_cases(self, project_id, cases):
            saved.extend(cases)
            return True

        def record_generation_activity(self, project_id, activity):
            return {**activity, "id": "activity-general"}

    monkeypatch.setattr(main, "database", FakeDatabase())
    monkeypatch.setattr(main, "_assign_test_case_ids", lambda project_id, cases: None)
    monkeypatch.setattr(main, "generate_general_test_cases", lambda business_requirements, trace: [{
        "name": "Checkout works", "type": "positive", "description": "Complete checkout",
        "manual_steps": ["Add an item", "Complete checkout"],
    }])

    response = main.generate_test_cases_endpoint(GenerateRequest(
        mode="General", project_id="project-1", business_requirements="Checkout requirements",
        case_collection_id="checkout-context", case_collection_name="Checkout · Web",
    ))

    assert response["test_cases"][0]["case_collection_id"] == "checkout-context"
    assert response["test_cases"][0]["case_collection_name"] == "Checkout · Web"
    assert saved == response["test_cases"]


def test_follow_up_saves_linked_output_and_clarification_answers(monkeypatch):
    """A clarification round creates new cases and a linked activity record."""
    source_case = {
        "id": "general-source", "case_kind": "general", "manual_steps": ["Start reset"],
        "case_collection_id": "identity-context", "case_collection_name": "Identity",
    }
    project = {"id": "project-1", "test_cases": [source_case], "endpoints": []}
    source_activity = {
        "id": "activity-source", "status": "succeeded", "mode": "General",
        "business_requirements": "Password reset works", "generated_case_ids": ["general-source"],
        "clarification_questions": ["Should the link expire?"],
    }
    saved = []
    activities = []

    class FakeDatabase:
        def get_project(self, project_id):
            return project

        def get_generation_activity(self, project_id, activity_id):
            return source_activity if activity_id == "activity-source" else None

        def save_follow_up_generation(self, project_id, cases, activity, superseded_case_ids):
            saved.extend(cases)
            record = {**activity, "id": "activity-follow-up"}
            for item in project["test_cases"]:
                if item["id"] in superseded_case_ids:
                    item["superseded_by_activity_id"] = record["id"]
            activities.append(record)
            return record

        def record_generation_activity(self, project_id, activity):
            record = {**activity, "id": "activity-follow-up"}
            activities.append(record)
            return record

    monkeypatch.setattr(main, "database", FakeDatabase())
    monkeypatch.setattr(main, "_assign_test_case_ids", lambda project_id, cases: None)
    monkeypatch.setattr(main, "refine_generated_cases", lambda cases, answers, trace: [{
        "source_case_id": "general-source",
        "name": "Reset link expires", "case_kind": "general",
        "manual_steps": ["Request a reset link", "Wait for expiry", "Open the link"],
    }, {
        "name": "Reset link can be resent", "case_kind": "general",
        "manual_steps": ["Request a reset link", "Request another link", "Use the newest link"],
    }])
    response = main.follow_up_generation("project-1", GenerationFollowUpRequest(
        source_activity_id="activity-source", answers={"1": "Yes, after 15 minutes"},
    ))

    assert response["test_cases"][0]["source_case_id"] == "general-source"
    assert response["test_cases"][0]["case_collection_id"] == "identity-context"
    assert response["test_cases"][1].get("source_case_id") is None
    assert saved[0]["case_kind"] == "general"
    assert source_case["superseded_by_activity_id"] == "activity-follow-up"
    assert response["archived_case_ids"] == ["general-source"]
    assert activities[0]["follow_up_of"] == "activity-source"
    assert activities[0]["supersedes_activity_id"] == "activity-source"
    assert activities[0]["archived_case_ids"] == ["general-source"]
    assert activities[0]["clarification_answers"] == {"1": "Yes, after 15 minutes"}
    assert activities[0]["questions_answered"] == ["Should the link expire?"]


def test_general_release_revision_allows_no_selected_endpoints(monkeypatch):
    """A general-only baseline can be revised without selecting API endpoints."""
    baseline = {
        "id": "general-baseline", "case_kind": "general",
        "manual_steps": ["Submit a reset request"],
        "case_collection_id": "identity-context", "case_collection_name": "Identity",
    }
    project = {"id": "project-1", "test_cases": [baseline], "endpoints": [], "collections": []}
    source = {
        "id": "activity-source", "status": "succeeded", "business_requirements": "Password reset",
        "generated_case_ids": [baseline["id"]],
    }
    captured = {}

    class FakeDatabase:
        def get_project(self, project_id):
            return project

        def get_generation_activity(self, project_id, activity_id):
            return source

        def save_test_case_revision(self, project_id, revision, cases):
            captured["saved_cases"] = cases
            return {**revision, "case_ids": [case["id"] for case in cases], "ordinal": 1}

        def record_generation_activity(self, project_id, activity):
            return {**activity, "id": "activity-revision"}

    monkeypatch.setattr(main, "database", FakeDatabase())

    def fake_revision(cases, endpoints, previous, notes, trace, prior_release_notes=""):
        captured["endpoints"] = endpoints
        return [{
            "source_case_id": "general-baseline", "case_kind": "general",
            "name": "Reset request works", "type": "positive", "description": "Check reset",
            "manual_steps": ["Submit a reset request", "Verify confirmation"],
        }]

    monkeypatch.setattr(main, "generate_test_case_revision", fake_revision)
    response = main.create_test_case_revision("project-1", main.TestCaseRevisionRequest(
        source_activity_id="activity-source", baseline_case_ids=["general-baseline"],
        release_label="Release 2", endpoint_ids=[],
    ))

    assert captured["endpoints"] == []
    assert response["test_cases"][0]["case_collection_id"] == "identity-context"


def test_release_revision_copies_kept_cases_without_sending_them_to_model(monkeypatch):
    """Kept baseline cases retain configuration while receiving new revision IDs."""
    keep = {
        "id": "keep-source", "case_kind": "general", "name": "Manual review",
        "manual_steps": ["Review the profile"], "business_requirements": "Keep this requirement",
    }
    revise = {
        "id": "revise-source", "case_kind": "general", "name": "Old scenario",
        "manual_steps": ["Check old behavior"],
    }
    project = {"id": "project-1", "test_cases": [keep, revise], "endpoints": [], "collections": []}
    source = {
        "id": "activity-source", "status": "succeeded", "business_requirements": "Core requirement",
        "generated_case_ids": [keep["id"], revise["id"]],
    }
    captured = {}

    class FakeDatabase:
        def get_project(self, project_id):
            return project

        def get_generation_activity(self, project_id, activity_id):
            return source

        def save_test_case_revision(self, project_id, revision, cases):
            captured["saved_cases"] = copy.deepcopy(cases)
            return {**revision, "case_ids": [case["id"] for case in cases], "ordinal": 2}

        def record_generation_activity(self, project_id, activity):
            captured["activity"] = activity
            return {**activity, "id": "activity-revision"}

    monkeypatch.setattr(main, "database", FakeDatabase())

    def fake_revision(cases, endpoints, previous, notes, trace, prior_release_notes=""):
        captured["model_input"] = copy.deepcopy(cases)
        return [{
            "source_case_id": "revise-source", "case_kind": "general",
            "name": "Revised scenario", "type": "positive", "description": "Updated",
            "manual_steps": ["Check current behavior"],
        }]

    monkeypatch.setattr(main, "generate_test_case_revision", fake_revision)
    response = main.create_test_case_revision("project-1", main.TestCaseRevisionRequest(
        source_activity_id="activity-source", baseline_case_ids=["keep-source", "revise-source"],
        keep_unchanged_case_ids=["keep-source"], release_label="Release 2", endpoint_ids=[],
    ))

    kept_copy, revised_copy = response["test_cases"]
    assert [case["id"] for case in captured["model_input"]] == ["revise-source"]
    assert kept_copy["id"] != "keep-source"
    assert kept_copy["source_case_id"] == "keep-source"
    assert kept_copy["manual_steps"] == keep["manual_steps"]
    assert kept_copy["business_requirements"] == keep["business_requirements"]
    assert revised_copy["source_case_id"] == "revise-source"
    assert captured["activity"]["kept_unchanged_source_case_ids"] == ["keep-source"]
