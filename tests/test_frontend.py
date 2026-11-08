"""Frontend data-shape tests that do not require a running Streamlit server."""

import sys
import types


if "streamlit" not in sys.modules:
    streamlit_stub = types.ModuleType("streamlit")
    streamlit_stub.cache_data = lambda **kwargs: (lambda function: function)
    streamlit_stub.components = types.SimpleNamespace(
        v2=types.SimpleNamespace(component=lambda *args, **kwargs: lambda **call_kwargs: None)
    )
    sys.modules["streamlit"] = streamlit_stub

from frontend.app import (
    _generation_requests_in_order,
    _group_test_cases_by_endpoint,
    _normalise_flow_steps,
    _new_request_draft,
    _normalize_assertions,
    _request_query_rows,
    _resolve_curl_url_sync,
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


def test_selected_requests_follow_full_saved_order():
    """Checked requests keep their order from the complete project list."""
    requests_by_id = {key: {"id": key} for key in "abcde"}
    result = _generation_requests_in_order(
        requests_by_id, ["e", "b", "a", "d", "c"], {"a", "c", "e"},
    )

    assert [request["id"] for request in result] == ["e", "a", "c"]


def test_parsed_curl_url_wins_over_stale_component_state_until_synced():
    """The previous cURL text cannot trigger the send guard after parsing succeeds."""
    draft = {"curl_url_sync": {
        "source": "curl -X GET https://api.test/items",
        "url": "https://api.test/items",
    }}

    stale_render = _resolve_curl_url_sync(draft, draft["curl_url_sync"]["source"])
    synced_render = _resolve_curl_url_sync(draft, "https://api.test/items")

    assert stale_render == "https://api.test/items"
    assert synced_render == "https://api.test/items"
    assert "curl_url_sync" not in draft


def test_generated_request_query_params_include_explicit_and_url_values():
    """Request details show stored params and query values embedded in legacy URLs."""
    rows = _request_query_rows(
        {"doctor_id": 17, "date": "today"},
        "https://api.test/doctors?date=ignored&specialty=cardiology",
    )

    assert rows == [
        {"Key": "doctor_id", "Value": "17"},
        {"Key": "date", "Value": "today"},
        {"Key": "specialty", "Value": "cardiology"},
    ]


def test_endpoint_groups_use_metadata_url_fallback_and_separate_flows():
    """New and legacy tests group by their source request while flows stay separate."""
    endpoints = [
        {"id": "named", "name": "Create cart", "method": "POST", "url": "https://api.test/carts"},
        {"id": "unnamed", "name": "", "method": "GET", "url": "https://api.test/carts/{cart_id}"},
    ]
    cases = [
        {"id": "new", "source_endpoint_id": "named", "source_endpoint_name": "Create cart", "request": {"url": "https://api.test/carts"}},
        {"id": "legacy", "request": {"method": "GET", "url": "https://api.test/carts/42"}},
        {"id": "flow", "is_flow": True},
    ]

    groups = _group_test_cases_by_endpoint(cases, endpoints)

    assert [(title, [tc["id"] for tc in grouped]) for _, title, grouped in groups] == [
        ("Create cart", ["new"]),
        ("https://api.test/carts/{cart_id}", ["legacy"]),
        ("Flow scenarios", ["flow"]),
    ]


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


def test_contract_metadata_survives_opening_and_resaving_an_imported_request(monkeypatch):
    """Editing and resaving an imported operation retains graph metadata and source evidence."""
    contract = {
        "source_id": "source-1", "source_format": "openapi3", "path": "/carts",
        "request_fields": [], "response_fields": [{"name": "cart_id", "json_path": "$.cart_id"}],
    }
    draft = _new_request_draft({
        "name": "Create cart", "method": "POST", "url": "https://api.test/carts",
        "contract": contract, "source_excerpt": "Creates a cart.", "deprecated": True,
    })
    captured = {}

    def fake_api_post(path, payload):
        captured.update(payload)
        return {**payload, "id": "saved-request", "collection_id": "collection-1"}

    monkeypatch.setattr("frontend.app.api_post", fake_api_post)
    _save_request_draft(draft, "collection-1", "project-1")

    assert captured["contract"] == contract
    assert captured["source_excerpt"] == "Creates a cart."
    assert captured["deprecated"] is True
