"""Frontend data-shape tests that do not require a running Streamlit server."""

import sys
import types


if "streamlit" not in sys.modules:
    streamlit_stub = types.ModuleType("streamlit")
    streamlit_stub.cache_data = lambda **kwargs: (lambda function: function)
    streamlit_stub.dialog = lambda *args, **kwargs: (lambda function: function)
    streamlit_stub.components = types.SimpleNamespace(
        v2=types.SimpleNamespace(component=lambda *args, **kwargs: lambda **call_kwargs: None)
    )
    sys.modules["streamlit"] = streamlit_stub

from frontend.app import (
    _generation_requests_in_order,
    _group_test_cases_by_endpoint,
    _filter_test_cases_by_scope,
    _flow_provenance_label,
    _deduplicate_test_cases,
    _merge_generated_test_cases,
    _normalise_flow_steps,
    _new_request_draft,
    _new_flow_step,
    _new_manual_test_case,
    _format_latency,
    _normalize_assertions,
    _request_query_rows,
    _resolve_curl_url_sync,
    _save_request_draft,
    _selected_request_assertions,
    _normalise_generation_activity_records,
    _flaky_summary,
)


def test_flakiness_uses_three_of_latest_ten_and_requires_mixed_outcomes():
    """Flaky classification needs at least three recent runs and both outcome classes."""
    assert _flaky_summary(["passed", "failed"])["flaky"] is False
    assert _flaky_summary(["passed", "passed", "passed"])["flaky"] is False
    assert _flaky_summary(["passed", "error", "passed"])["flaky"] is True
    assert _flaky_summary(["passed"] * 10 + ["failed"])["flaky"] is False
    assert _flaky_summary(["passed", "failed", "error"])["non_passed"] == 2


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


def test_generation_activity_records_accept_paginated_and_legacy_responses():
    """Activity table safely reads wrapped records and ignores malformed entries."""
    records = [{"id": "activity-1", "created_at": "2026-11-10T10:00:00"}]

    assert _normalise_generation_activity_records({"activities": records, "total": 1}) == records
    assert _normalise_generation_activity_records(records) == records
    assert _normalise_generation_activity_records({"activities": ["activity-1", *records]}) == records
    assert _normalise_generation_activity_records("unexpected") == []


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


def test_scope_filters_include_flow_once_when_a_step_matches_any_selected_collection():
    """A cross-collection flow remains one case when one of its steps matches."""
    endpoints = [
        {"id": "login", "method": "POST", "url": "/login", "name": "Login", "collection_id": "auth"},
        {"id": "orders", "method": "GET", "url": "/orders", "name": "Orders", "collection_id": "commerce"},
    ]
    collections = [{"id": "auth", "name": "Auth"}, {"id": "commerce", "name": "Commerce"}]
    case = {
        "id": "flow-1", "is_flow": True, "steps": [
            {"endpoint_id": "login", "endpoint": {"method": "POST", "url": "/login"}},
            {"endpoint_id": "orders", "endpoint": {"method": "GET", "url": "/orders"}},
        ],
    }

    result = _filter_test_cases_by_scope(
        [case], endpoints, [], [], ["commerce"], [],
    )

    assert result == [case]
    assert "Collections: Auth, Commerce" in _flow_provenance_label(case, endpoints, collections)


def test_scope_filters_require_one_flow_step_to_match_endpoint_and_collection():
    """Endpoint and collection facets must match the same flow step."""
    endpoints = [
        {"id": "login", "url": "/login", "method": "POST", "collection_id": "auth"},
        {"id": "orders", "url": "/orders", "method": "GET", "collection_id": "commerce"},
    ]
    case = {"id": "flow-1", "is_flow": True, "steps": [
        {"endpoint_id": "login", "endpoint": {"url": "/login", "method": "POST"}},
        {"endpoint_id": "orders", "endpoint": {"url": "/orders", "method": "GET"}},
    ]}

    assert _filter_test_cases_by_scope([case], endpoints, [], [], ["commerce"], ["login"]) == []


def test_scope_filters_support_run_union_and_legacy_url_provenance():
    """Run membership combines with scope filters and older flows resolve by URL."""
    endpoints = [{
        "id": "items", "method": "GET", "url": "https://api.test/items/{item_id}",
        "collection_id": "catalog",
    }]
    case = {"id": "legacy-flow", "is_flow": True, "steps": [
        {"endpoint": {"method": "GET", "url": "https://api.test/items/42"}},
    ]}
    runs = [{"id": "run-a", "case_ids": ["legacy-flow"]}, {"id": "run-b", "case_ids": []}]

    assert _filter_test_cases_by_scope(
        [case], endpoints, ["run-a", "run-b"], runs, ["catalog"], ["items"],
    ) == [case]


def test_manual_cases_copy_saved_request_fields_and_create_ordered_steps():
    """Manual single and flow cases retain request fields and editable defaults."""
    saved = [
        {
            "id": "saved-1", "name": "Login", "method": "POST", "url": "/login",
            "headers": {"Content-Type": "application/json"},
            "query_params": {"region": "west"}, "body": {"email": "a@example.test"},
        },
        {"id": "saved-2", "name": "Profile", "method": "GET", "url": "/profile"},
    ]

    single = _new_manual_test_case(saved[:1], "", False)
    flow = _new_manual_test_case(saved, "Login then profile", True)

    assert single["name"] == "Login"
    assert single["request"]["headers"] == saved[0]["headers"]
    assert single["request"]["query_params"] == saved[0]["query_params"]
    assert single["request"]["body"] == saved[0]["body"]
    assert [step["endpoint_id"] for step in flow["steps"]] == ["saved-1", "saved-2"]
    assert [step["step_order"] for step in flow["steps"]] == [1, 2]


def test_latency_switches_to_seconds_only_above_one_second():
    """Latency remains in milliseconds at 1000 ms and switches above it."""
    assert _format_latency(1000) == "1000 ms"
    assert _format_latency(1250) == "1.25 s"


def test_duplicate_test_case_ids_keep_the_latest_case_payload_once():
    """Duplicate stable IDs cannot produce duplicate cards or batch targets."""
    cases = [
        {"id": "tc-1", "name": "Old payload"},
        {"id": "tc-2", "name": "Other case"},
        {"id": "tc-1", "name": "Latest payload"},
    ]

    unique = _deduplicate_test_cases(cases)

    assert [case["id"] for case in unique] == ["tc-1", "tc-2"]
    assert unique[0]["name"] == "Latest payload"


def test_generated_cases_append_without_replacing_existing_cases():
    """New generation preserves existing IDs and adds unique generated IDs."""
    existing = [{"id": "saved-1", "name": "Existing"}]
    generated = [{"id": "generated-1", "name": "Additional"}]

    merged = _merge_generated_test_cases(existing, generated)

    assert [(case["id"], case["name"]) for case in merged] == [
        ("saved-1", "Existing"),
        ("generated-1", "Additional"),
    ]


def test_new_flow_step_copies_saved_request_fields_without_editor_state():
    """Added flow steps start with saved request data and clean editable rows."""
    step = _new_flow_step({
        "id": "saved-1", "name": "List items", "method": "GET",
        "url": "https://api.test/items", "headers": {"X-Client": "web"},
        "query_params": {"page": "1"}, "body": {"unused": True},
        "include_body": False,
    }, 2)

    assert step["step_order"] == 2
    assert step["endpoint_id"] == "saved-1"
    assert step["endpoint"]["method"] == "GET"
    assert step["endpoint"]["headers"][0]["key"] == "X-Client"
    assert "_ui_id" not in step["endpoint"]["headers"][0]
    assert step["endpoint"]["query_params"][0]["value"] == "1"
    assert step["endpoint"]["body"] is None
    assert step["variable_mappings"] == []


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
