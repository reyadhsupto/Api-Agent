"""Tests for request-playground assertion execution."""

import app.storage as storage


_Database = storage.Database


class _ImportOnlyDatabase:
    """Avoid connecting to PostgreSQL while importing route definitions."""

    def __init__(self):
        pass


storage.Database = _ImportOnlyDatabase
from app import main
storage.Database = _Database
from app.schemas import ApiRequest, HttpAssertionExecutionRequest


class FakeResponse:
    """Minimal HTTP response double used by route tests."""

    status_code = 201
    text = '{"id":"item-1"}'
    headers = {"content-type": "application/json"}
    url = "https://example.test/items"


def test_execute_http_assertions_sends_once_and_returns_assertion_results(monkeypatch):
    """The route makes one outbound request and returns every selected check."""
    calls = []

    def fake_request(*args, **kwargs):
        calls.append((args, kwargs))
        return FakeResponse()

    monkeypatch.setattr(main.requests, "request", fake_request)
    request = HttpAssertionExecutionRequest(
        request=ApiRequest(method="POST", url="https://example.test/items", body={"name": "item"}),
        assertions=[
            {"id": "status", "type": "status", "expected_status": 201},
            {"id": "field", "type": "jsonpath", "path": "$.id", "expected_value": "item-1"},
        ],
    )

    result = main.execute_http_assertions(request)

    assert len(calls) == 1
    assert calls[0][0][0] == "POST"
    assert result["status"] == 201
    assert result["assertions_passed"] is True
    assert [item["id"] for item in result["assertion_results"]] == ["status", "field"]


def test_generated_cases_get_disabled_schema_assertion_defaults():
    """Generated single and flow cases receive editable blank schemas without replacing checks."""
    cases = [
        {"id": "single", "assertions": {"status": {"enabled": True, "expected_status": 201}}},
        {
            "id": "flow", "is_flow": True,
            "steps": [{"assertions": {"status": {"enabled": True, "expected_status": 200}}}],
        },
    ]

    main._ensure_response_schema_defaults(cases)

    assert cases[0]["assertions"]["status"]["expected_status"] == 201
    assert cases[0]["assertions"]["response_schema"] == {"enabled": False, "schema": "{}"}
    assert cases[1]["steps"][0]["assertions"]["response_schema"] == {
        "enabled": False, "schema": "{}"
    }

