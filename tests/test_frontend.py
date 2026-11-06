"""Frontend data-shape tests that do not require a running Streamlit server."""

import sys
import types


if "streamlit" not in sys.modules:
    streamlit_stub = types.ModuleType("streamlit")
    streamlit_stub.cache_data = lambda **kwargs: (lambda function: function)
    sys.modules["streamlit"] = streamlit_stub

from frontend.app import (
    _merge_selected_generation_order,
    _normalise_flow_steps,
    _new_request_draft,
    _normalize_assertions,
    _save_request_draft,
    _selected_request_assertions,
)


def test_flow_step_normalization_keeps_order_and_edits_multiple_assertions():
    """Each flow step gets editable list configs without losing request data."""
    testcase = {
        "id": "flow-1",
        "steps": [
            {
                "step_order": 2,
                "endpoint": {"method": "GET", "url": "/profile"},
                "assertions": {
                    "status": {"enabled": True, "expected_status": 200},
                    "jsonpath": [
                        {"enabled": True, "path": "$.id", "expected_value": "7"},
                        {"enabled": True, "path": "$.name", "expected_value": "Ada"},
                    ],
                },
                "variable_mappings": [{"from": "$.token", "to": "headers.Authorization"}],
            },
            {
                "step_order": 1,
                "endpoint": {"method": "POST", "url": "/login"},
                "assertions": {"status": [{"enabled": True, "expected_status": 200}]},
            },
        ],
    }

    steps = _normalise_flow_steps(testcase)

    assert [step["step_order"] for step in steps] == [1, 2]
    assert steps[1]["assertions"]["jsonpath"] == [
        {"enabled": True, "path": "$.id", "expected_value": "7"},
        {"enabled": True, "path": "$.name", "expected_value": "Ada"},
    ]
    assert steps[1]["variable_mappings"][0]["from"] == "$.token"
    assert steps[1]["endpoint"]["url"] == "/profile"
    assert steps[0]["assertions"]["response_schema"] == [
        {"enabled": False, "schema": "{}"}
    ]


def test_single_case_assertions_normalize_legacy_dicts():
    """Existing single-dictionary assertion payloads become editable lists."""
    testcase = {
        "assertions": {
            "status": {"enabled": True, "expected_status": 201},
        }
    }

    assertions = _normalize_assertions(testcase)

    assert assertions["status"] == [{"enabled": True, "expected_status": 201}]
    assert assertions["body_contains"][0]["enabled"] is False
    assert assertions["response_schema"] == [{"enabled": False, "schema": "{}"}]


def test_generation_order_rearranges_selected_requests_and_keeps_unselected_slots():
    """Selected request order changes without moving unselected eligible requests."""
    result = _merge_selected_generation_order(
        current_order=["a", "b", "c", "d"],
        eligible_ids=["a", "b", "c", "d", "e"],
        selected_ids=["a", "c", "e"],
        reordered_selected_ids=["e", "a", "c"],
    )

    assert result == ["e", "b", "a", "d", "c"]


def test_request_assertion_selection_excludes_disabled_checks_from_run_all():
    """Run All includes enabled assertions while a single run can target a disabled one."""
    assertions = {
        "status": [{"id": "status", "enabled": True, "expected_status": 200}],
        "body_contains": [{"id": "body", "enabled": False, "value": "ready"}],
    }

    assert [item["id"] for item in _selected_request_assertions(assertions)] == ["status"]
    individual = _selected_request_assertions(assertions, "body")
    assert len(individual) == 1
    assert individual[0]["id"] == "body"
    assert individual[0]["enabled"] is False


def test_request_assertions_persist_with_saved_request(monkeypatch):
    """Saving and reopening a collection request preserves configured checks."""
    assertion_config = {
        "status": [{"id": "status-1", "enabled": True, "expected_status": 202}],
        "response_schema": [{"id": "schema-1", "enabled": True, "schema": '{"type":"object"}'}],
    }
    draft = _new_request_draft({
        "name": "Create item", "method": "POST", "url": "https://example.test/items",
        "assertions": assertion_config,
    })
    captured = {}

    def fake_api_post(path, payload):
        captured["path"] = path
        captured["payload"] = payload
        return {**payload, "id": "saved-request", "collection_id": "collection-1"}

    monkeypatch.setattr("frontend.app.api_post", fake_api_post)
    _save_request_draft(draft, "collection-1", "project-1")

    restored = _new_request_draft(captured["payload"])
    assert captured["payload"]["assertions"]["status"] == assertion_config["status"]
    assert captured["payload"]["assertions"]["response_schema"] == assertion_config["response_schema"]
    assert restored["assertions"]["status"][0]["expected_status"] == 202
    assert restored["assertions"]["response_schema"][0]["schema"] == '{"type":"object"}'
