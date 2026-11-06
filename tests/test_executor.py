"""Tests for single and repeated API assertion evaluation."""

from app import executor


class FakeResponse:
    """Minimal requests response replacement for executor tests."""

    status_code = 200
    text = '{"token":"abc","user":{"name":"Ada"}}'
    headers = {"content-type": "application/json"}


def test_execute_test_case_evaluates_multiple_assertions(monkeypatch):
    """All enabled status, body, and JSONPath instances must pass."""
    monkeypatch.setattr(executor.requests, "request", lambda **kwargs: FakeResponse())

    result = executor.execute_test_case(
        {"id": "tc-1", "request": {"method": "GET", "url": "https://example.test"}},
        assertions={
            "status": [{"enabled": True, "expected_status": 200}],
            "body_contains": [
                {"enabled": True, "value": "token"},
                {"enabled": True, "value": "Ada"},
            ],
            "jsonpath": [
                {"enabled": True, "path": "$.token", "expected_value": "abc"},
                {"enabled": True, "path": "$.user.name", "expected_value": "Ada"},
            ],
            "response_schema": [
                {"enabled": True, "schema": '{"type":"object","required":["token"]}'},
                {"enabled": False, "schema": '{"type":"array"}'},
            ],
        },
    )

    assert result["status"] == "passed"
    assert result["assertion_detail"].count("PASS") == 6


def test_execute_test_case_accepts_legacy_assertion_dict(monkeypatch):
    """Existing one-dict assertion payloads must continue to work."""
    monkeypatch.setattr(executor.requests, "request", lambda **kwargs: FakeResponse())

    result = executor.execute_test_case(
        {"id": "tc-legacy", "request": {"method": "GET", "url": "https://example.test"}},
        assertions={"status": {"enabled": True, "expected_status": 200}},
    )

    assert result["status"] == "passed"


def test_execute_flow_test_case_evaluates_multiple_step_assertions(monkeypatch):
    """Flow steps use the same list-based assertion semantics."""
    monkeypatch.setattr(executor.requests, "request", lambda **kwargs: FakeResponse())

    result = executor.execute_flow_test_case(
        {
            "id": "flow-1",
            "steps": [
                {
                    "step_order": 1,
                    "endpoint": {"method": "GET", "url": "https://example.test"},
                    "assertions": {
                        "status": [{"enabled": True, "expected_status": 200}],
                        "body_contains": [{"enabled": True, "value": "token"}],
                        "jsonpath": [{"enabled": True, "path": "$.user.name", "expected_value": "Ada"}],
                        "response_schema": [{"enabled": True, "schema": '{"type":"object","required":["token"]}'}],
                    },
                }
            ],
        }
    )

    assert result["status"] == "passed"
    assert result["steps_executed"] == 1


def test_execute_test_case_fails_on_response_schema_mismatch(monkeypatch):
    """A response that violates an enabled schema check fails the test case."""
    monkeypatch.setattr(executor.requests, "request", lambda **kwargs: FakeResponse())

    result = executor.execute_test_case(
        {"id": "tc-schema", "request": {"method": "GET", "url": "https://example.test"}},
        assertions={
            "status": [{"enabled": True, "expected_status": 200}],
            "response_schema": [{"enabled": True, "schema": '{"type":"array"}'}],
        },
    )

    assert result["status"] == "failed"
    assert "Response schema -> FAIL" in result["assertion_detail"]


def test_flow_mapping_supports_jsonpath_array_wildcards(monkeypatch):
    """Array wildcard mappings preserve extracted values as a JSON array in request bodies."""
    responses = iter([
        type("Response", (), {"status_code": 200, "text": '{"items":[{"id":"one"},{"id":"two"}]}', "headers": {}})(),
        type("Response", (), {"status_code": 200, "text": '{"ok":true}', "headers": {}})(),
    ])
    sent = []

    def fake_request(**kwargs):
        sent.append(kwargs)
        return next(responses)

    monkeypatch.setattr(executor.requests, "request", fake_request)
    result = executor.execute_flow_test_case({
        "id": "flow-wildcard",
        "steps": [
            {"step_order": 1, "endpoint": {"method": "GET", "url": "https://example.test/items"}},
            {
                "step_order": 2,
                "endpoint": {"method": "POST", "url": "https://example.test/submit", "body": {"ids": []}},
                "variable_mappings": [{"from": "$.items[*].id", "to": "request.body.ids"}],
                "assertions": {"status": {"enabled": True, "expected_status": 200}},
            },
        ],
    })

    assert result["status"] == "passed"
    assert sent[1]["json"] == {"ids": ["one", "two"]}


def test_invalid_array_wildcard_mapping_does_not_raise():
    """An unmatched wildcard mapping is skipped instead of crashing flow execution."""
    step = {
        "endpoint": {"method": "POST", "url": "https://example.test/submit", "body": {}},
        "variable_mappings": [{"from": "$.items[*].id", "to": "request.body.ids"}],
    }

    mapped = executor._apply_variable_mappings(['{"items":{}}'], step)

    assert mapped["endpoint"]["body"] == {}


def test_playground_assertions_evaluate_multiple_types_and_instances():
    """The playground reports each selected check and aggregates with AND semantics."""
    result = executor.evaluate_request_assertions(
        200,
        '{"token":"abc","user":{"name":"Ada"}}',
        [
            {"id": "status-1", "type": "status", "expected_status": 200},
            {"id": "body-1", "type": "body_contains", "value": "token"},
            {"id": "body-2", "type": "body_contains", "value": "Ada"},
            {"id": "field-1", "type": "jsonpath", "path": "$.user.name", "expected_value": "Ada"},
            {"id": "schema-1", "type": "response_schema", "schema": '{"type":"object","required":["token"]}'},
        ],
    )

    assert result["passed"] is True
    assert len(result["results"]) == 5
    assert all(item["passed"] for item in result["results"])


def test_playground_assertions_report_invalid_jsonpath_and_schema():
    """Malformed assertion definitions fail as individual results instead of aborting."""
    result = executor.evaluate_request_assertions(
        200,
        '{"items":[]}',
        [
            {"id": "field", "type": "jsonpath", "path": "$.items[abc]", "expected_value": "x"},
            {"id": "schema-json", "type": "response_schema", "schema": "{"},
            {"id": "schema-body", "type": "response_schema", "schema": '{"type":"array"}'},
            {"id": "schema-invalid", "type": "response_schema", "schema": '{"type":"unknown"}'},
        ],
    )

    assert result["passed"] is False
    assert all(not item["passed"] for item in result["results"])
    assert "Invalid JSONPath" in result["results"][0]["detail"]
    assert "Invalid JSON Schema" in result["results"][1]["detail"]
    assert "matches" not in result["results"][2]["detail"]
    assert "Invalid JSON Schema" in result["results"][3]["detail"]
    malformed_response = executor.evaluate_request_assertions(
        200, "not-json", [{"id": "schema", "type": "response_schema", "schema": '{"type":"object"}'}]
    )
    assert "not valid JSON" in malformed_response["results"][0]["detail"]


def test_playground_schema_assertion_fails_on_schema_mismatch():
    """A valid schema that rejects the response returns a useful failure detail."""
    result = executor.evaluate_request_assertions(
        200,
        '{"id":"abc"}',
        [{"id": "schema", "type": "response_schema", "schema": '{"type":"object","required":["name"]}'}],
    )

    assert result["passed"] is False
    assert "name" in result["results"][0]["detail"]
