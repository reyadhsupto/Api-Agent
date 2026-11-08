"""Route tests for contract import persistence and discovered-flow generation."""

from types import SimpleNamespace
import sys

from app import storage

if "app.main" not in sys.modules:
    _database_class = storage.Database
    storage.Database = lambda: SimpleNamespace()
    from app import main
    storage.Database = _database_class
else:
    from app import main


def _contract_endpoints(source_id="source-1"):
    """Return a response producer and request consumer linked by cart_id."""
    return [
        {
            "id": "producer", "name": "Create cart", "method": "POST", "url": "https://api.test/carts",
            "headers": {}, "query_params": [], "body": None, "include_for_generation": False,
            "contract": {"source_id": source_id, "source_name": "Shop", "source_format": "openapi3",
                "request_fields": [], "response_fields": [{"name": "cart_id", "json_path": "$.cart_id"}]},
        },
        {
            "id": "consumer", "name": "Checkout", "method": "POST", "url": "https://api.test/carts/{cart_id}/checkout",
            "headers": {}, "query_params": [], "body": {}, "include_for_generation": False,
            "contract": {"source_id": source_id, "source_name": "Shop", "source_format": "openapi3",
                "request_fields": [{"name": "cart_id", "target": "request.path.cart_id"}], "response_fields": []},
        },
    ]


def test_contract_import_saves_reviewed_requests_excluded_by_default(monkeypatch):
    """Import route saves reviewed endpoint metadata and returns source graph candidates."""
    project = {"id": "project-1", "endpoints": [], "collections": [{"id": "collection-1"}]}

    class FakeDatabase:
        def get_project(self, project_id):
            return project if project_id == "project-1" else None

        def import_requests(self, project_id, collection_id, requests_data):
            assert project_id == "project-1"
            assert collection_id == "collection-1"
            project["endpoints"] = [dict(item, collection_id=collection_id) for item in requests_data]
            return project["endpoints"]

    monkeypatch.setattr(main, "database", FakeDatabase())
    result = main.import_contract_requests("project-1", SimpleNamespace(
        collection_id="collection-1",
        endpoints=[dict(item, _base_url_required=False) for item in _contract_endpoints()],
    ))

    assert len(result["imported"]) == 2
    assert all(item["include_for_generation"] is False for item in result["imported"])
    assert len(result["dependencies"]) == 1
    assert len(result["candidate_flows"]) == 1
    assert "_base_url_required" not in result["imported"][0]


def test_discovered_flow_generation_attaches_saved_requests_and_filters_mappings(monkeypatch):
    """Generated steps use persisted endpoint data and only schema-evidenced mappings."""
    endpoints = _contract_endpoints()
    project = {"id": "project-1", "endpoints": endpoints, "collections": []}
    saved_cases = []

    class FakeDatabase:
        def get_project(self, project_id):
            return project if project_id == "project-1" else None

        def save_test_cases(self, project_id, cases):
            saved_cases.extend(cases)
            return True

    monkeypatch.setattr(main, "database", FakeDatabase())
    monkeypatch.setattr(main, "_assign_test_case_ids", lambda project_id, cases: None)
    monkeypatch.setattr(main, "_ensure_response_schema_defaults", lambda cases: None)

    def fake_generate(endpoints, candidates, business_requirements):
        candidate = candidates[0]
        return [{
            "id": "generated-flow", "candidate_id": candidate["id"], "name": "Checkout",
            "type": "positive", "is_flow": True,
            "steps": [
                {"step_order": 1, "endpoint_id": "producer", "assertions": {}, "variable_mappings": []},
                {"step_order": 2, "endpoint_id": "consumer", "assertions": {}, "variable_mappings": [
                    {"from": "$.cart_id", "to": "request.path.cart_id"},
                    {"from": "$.unrelated", "to": "request.path.cart_id"},
                ]},
            ],
        }]

    monkeypatch.setattr(main, "generate_discovered_flow_test_cases", fake_generate)
    graph = main.discover_contract_flows("project-1", SimpleNamespace(source_id="source-1"))
    result = main.generate_contract_flows("project-1", SimpleNamespace(
        source_id="source-1", candidate_ids=[graph["candidate_flows"][0]["id"]],
        business_requirements="A successful cart checkout",
    ))

    assert result[0]["steps"][1]["endpoint"]["url"].endswith("/{cart_id}/checkout")
    assert result[0]["steps"][1]["variable_mappings"] == [
        {"from": "$.cart_id", "to": "request.path.cart_id"},
    ]
    assert saved_cases == result


def test_discovered_flow_generation_reports_malformed_llm_steps(monkeypatch):
    """Malformed step values become a controlled upstream error instead of a 500."""
    endpoints = _contract_endpoints()
    project = {"id": "project-1", "endpoints": endpoints, "collections": []}

    class FakeDatabase:
        def get_project(self, project_id):
            return project if project_id == "project-1" else None

    monkeypatch.setattr(main, "database", FakeDatabase())
    monkeypatch.setattr(main, "generate_discovered_flow_test_cases", lambda **kwargs: [{
        "candidate_id": kwargs["candidates"][0]["id"], "steps": [None, {}],
    }])
    graph = main.discover_contract_flows("project-1", SimpleNamespace(source_id="source-1"))

    try:
        main.generate_contract_flows("project-1", SimpleNamespace(
            source_id="source-1", candidate_ids=[graph["candidate_flows"][0]["id"]],
            business_requirements=None,
        ))
    except main.HTTPException as exc:
        assert exc.status_code == 502
        assert "JSON objects" in exc.detail
    else:
        raise AssertionError("Expected malformed LLM steps to be rejected")
