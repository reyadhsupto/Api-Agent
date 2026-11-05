"""Tests for the temporary API Client request endpoint."""

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
