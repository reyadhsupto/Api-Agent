"""Tests for the temporary API Client request endpoint."""

import asyncio
import csv
import io
import json

from app import main
from app.schemas import ApiRequest


def test_api_client_sends_request_and_returns_response_metadata(monkeypatch):
    """The route forwards request fields and returns non-persisted response data."""
    captured = {}

    class FakeResponse:
        status_code = 418
        headers = {"Content-Type": "application/json"}
        text = '{"message":"teapot"}'
        url = "https://example.test/search?q=tea"

    def fake_request(method, url, **kwargs):
        captured.update(method=method, url=url, **kwargs)
        return FakeResponse()

    monkeypatch.setattr(main.requests, "request", fake_request)
    result = main.send_api_request(ApiRequest(
        method="POST",
        url="https://example.test/search",
        headers={"X-Test": "yes"},
        query_params={"q": "tea"},
        body={"cup": 1},
    ))

    assert captured["method"] == "POST"
    assert captured["params"] == {"q": "tea"}
    assert captured["json"] == {"cup": 1}
    assert result["status"] == 418
    assert result["body"] == '{"message":"teapot"}'
    assert result["headers"]["Content-Type"] == "application/json"


def test_request_rows_respect_enabled_flags_and_postman_export_preserves_disabled_state():
    """Generation sends enabled rows while export retains disabled rows for editing."""
    request = {
        "name": "Search", "method": "GET", "url": "https://example.test/items",
        "headers": [
            {"key": "X-On", "value": "yes", "enabled": True},
            {"key": "X-Off", "value": "no", "enabled": False},
        ],
        "query_params": [
            {"key": "page", "value": "2", "enabled": True},
            {"key": "draft", "value": "x", "enabled": False},
        ],
        "body": "ignored", "include_body": False, "include_for_generation": True,
    }

    effective = main._effective_request(request)
    assert effective["headers"] == {"X-On": "yes"}
    assert effective["query_params"] == {"page": "2"}
    assert effective["body"] is None

    exported = main._postman_collection({"id": "c-1", "name": "Searches", "requests": [request]})
    item = exported["item"][0]["request"]
    assert exported["info"]["schema"].endswith("collection/v2.1.0/collection.json")
    assert item["header"][1]["disabled"] is True
    assert item["url"]["query"][1]["disabled"] is True
    assert item["body"]["disabled"] is True


def test_test_case_csv_export_contains_only_requested_cases_and_preserves_flow_steps(monkeypatch):
    """CSV export filters by selected IDs and retains flow structure in its JSON cell."""
    project = {"id": "project-1", "test_cases": [
        {"id": "single-1", "name": "Single", "request": {"method": "GET", "url": "/items"}},
        {"id": "not-selected", "name": "Omit me", "request": {"url": "/ignored"}},
        {"id": "flow-1", "name": "Flow", "is_flow": True, "steps": [{
            "step_order": 1,
            "endpoint_id": "endpoint-1",
            "endpoint": {"method": "POST", "url": "/items", "body": {"name": "A\nB"}},
            "assertions": {"status": [{"enabled": True, "expected_status": 201}]},
            "variable_mappings": [{"from": "$.id", "to": "request.path.item_id"}],
        }]},
    ]}

    class FakeDatabase:
        def get_project(self, project_id):
            return project if project_id == project["id"] else None

    monkeypatch.setattr(main, "database", FakeDatabase())
    response = main.export_test_cases(
        "project-1", selected_case_ids=["single-1", "flow-1"],
    )

    async def read_response():
        return b"".join([chunk async for chunk in response.body_iterator])

    payload = asyncio.run(read_response()).decode("utf-8")
    rows = list(csv.DictReader(io.StringIO(payload)))

    assert [row["test_case_id"] for row in rows] == ["single-1", "flow-1"]
    assert len(rows[0]) == 15
    flow_steps = json.loads(rows[1]["steps_json"])
    assert flow_steps[0]["endpoint_id"] == "endpoint-1"
    assert flow_steps[0]["endpoint"]["body"]["name"] == "A\nB"
    assert flow_steps[0]["variable_mappings"][0]["to"] == "request.path.item_id"
