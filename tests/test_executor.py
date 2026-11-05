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
        },
    )

    assert result["status"] == "passed"
    assert result["assertion_detail"].count("PASS") == 5


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
                    },
                }
            ],
        }
    )

    assert result["status"] == "passed"
    assert result["steps_executed"] == 1
