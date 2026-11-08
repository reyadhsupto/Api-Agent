"""Tests for API contract normalization and schema-derived dependency paths."""

import json

from app.contracts import build_dependency_graph, parse_contract_document


def test_openapi_json_lists_every_operation_and_resolves_schema_references():
    """OpenAPI preview includes deprecated methods and extracts referenced request/response fields."""
    document = {
        "openapi": "3.1.0",
        "info": {"title": "Shop API"},
        "servers": [{"url": "https://api.example.test/v1"}],
        "paths": {
            "/carts": {
                "post": {
                    "operationId": "createCart", "summary": "Create cart",
                    "responses": {"201": {"$ref": "#/components/responses/CartCreated"}},
                },
                "get": {"deprecated": True, "responses": {"200": {"description": "old"}}},
            },
            "/checkout/{cartId}": {
                "post": {
                    "parameters": [{"name": "cartId", "in": "path", "required": True}],
                    "requestBody": {"content": {"application/json": {"schema": {"$ref": "#/components/schemas/Checkout"}}}},
                    "responses": {"200": {"description": "ok"}},
                }
            },
        },
        "components": {
            "responses": {"CartCreated": {"description": "created", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Cart"}}}}},
            "schemas": {
                "Cart": {"type": "object", "properties": {"cart_id": {"type": "string"}}},
                "Checkout": {"type": "object", "properties": {"payment": {"type": "string"}}},
            },
        },
    }

    preview = parse_contract_document(json.dumps(document), source_id="shop")

    assert len(preview["endpoints"]) == 3
    deprecated = next(item for item in preview["endpoints"] if item["method"] == "GET")
    assert deprecated["deprecated"] is True
    create = next(item for item in preview["endpoints"] if item["name"] == "Create cart")
    checkout = next(item for item in preview["endpoints"] if item["method"] == "POST" and "checkout" in item["url"])
    assert create["contract"]["response_fields"][0]["json_path"] == "$.cart_id"
    assert checkout["contract"]["request_fields"] == [
        {"name": "cartId", "path": "cartId", "target": "request.path.cartId", "in": "path"},
        {"name": "payment", "path": "payment", "target": "request.body.payment", "in": "body"},
    ]
    assert preview["dependencies"][0]["evidence"][0]["request_field"] == "request.path.cartId"


def test_openapi_yaml_requires_a_base_url_when_server_is_missing():
    """YAML paths remain listed and request base URL entry when server data is absent."""
    content = "openapi: 3.0.3\ninfo:\n  title: Catalog\npaths:\n  /items:\n    get:\n      responses:\n        '200': {description: ok}\n"
    preview = parse_contract_document(content, format_hint="openapi", source_id="catalog")

    assert preview["base_url_required"] is True
    assert preview["endpoints"][0]["url"] == "/items"
    assert preview["endpoints"][0]["_base_url_required"] is True


def test_missing_pyyaml_does_not_block_json_contracts(monkeypatch):
    """JSON imports remain usable while YAML input explains its missing dependency."""
    import app.contracts as contracts

    monkeypatch.setattr(contracts, "yaml", None)
    json_preview = parse_contract_document(json.dumps({
        "openapi": "3.0.3", "info": {"title": "JSON"},
        "paths": {"/health": {"get": {"responses": {"200": {"description": "ok"}}}}},
    }))

    assert len(json_preview["endpoints"]) == 1
    try:
        parse_contract_document("openapi: 3.0.3\npaths: {}\n")
    except ValueError as exc:
        assert "requires PyYAML" in str(exc)
    else:
        raise AssertionError("Expected a clear error for YAML without PyYAML")


def test_openapi_resolves_path_item_and_request_body_references():
    """Reusable path items and request bodies still produce complete endpoint previews."""
    document = {
        "openapi": "3.0.3", "info": {"title": "Reusable"},
        "servers": [{"url": "https://api.example.test"}],
        "paths": {"/orders": {"$ref": "#/components/pathItems/CreateOrder"}},
        "components": {
            "pathItems": {"CreateOrder": {
                "post": {
                    "requestBody": {"$ref": "#/components/requestBodies/Order"},
                    "responses": {"201": {"description": "created"}},
                },
            }},
            "requestBodies": {"Order": {"content": {"application/json": {
                "schema": {"type": "object", "properties": {"customer_id": {"type": "string"}}},
            }}}},
        },
    }

    preview = parse_contract_document(json.dumps(document), source_id="reusable")

    assert len(preview["endpoints"]) == 1
    assert preview["endpoints"][0]["url"] == "https://api.example.test/orders"
    assert preview["endpoints"][0]["contract"]["request_fields"][0]["name"] == "customer_id"


def test_swagger_2_converts_host_base_path_and_body_schema():
    """Swagger 2 host/schemes/basePath and definitions become executable request details."""
    document = {
        "swagger": "2.0", "info": {"title": "Legacy"}, "host": "legacy.example.test",
        "schemes": ["https"], "basePath": "/api", "definitions": {
            "Payload": {"type": "object", "properties": {"cart_id": {"type": "string", "default": "c-1"}}},
        },
        "paths": {"/orders": {"post": {
            "parameters": [{"name": "body", "in": "body", "schema": {"$ref": "#/definitions/Payload"}}],
            "responses": {"201": {"description": "created"}},
        }}},
    }
    preview = parse_contract_document(json.dumps(document), source_id="legacy")
    endpoint = preview["endpoints"][0]

    assert endpoint["url"] == "https://legacy.example.test/api/orders"
    assert endpoint["body"] == {"cart_id": "c-1"}
    assert endpoint["contract"]["request_fields"][0]["target"] == "request.body.cart_id"


def test_postman_nested_requests_preserve_disabled_headers_and_query_rows():
    """Nested Postman folders flatten requests while preserving disabled row state."""
    document = {
        "info": {"name": "Commerce", "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"},
        "variable": [{"key": "baseUrl", "value": "https://api.example.test"}],
        "item": [{"name": "Cart", "item": [{"name": "Create", "request": {
            "method": "POST", "url": {"raw": "{{baseUrl}}/carts?verbose=true", "query": [
                {"key": "verbose", "value": "true", "disabled": True},
            ]},
            "header": [{"key": "X-Disabled", "value": "x", "disabled": True}],
            "body": {"mode": "raw", "raw": "{\"item\":1}"},
        }}]}],
    }
    preview = parse_contract_document(json.dumps(document), source_id="postman")
    endpoint = preview["endpoints"][0]

    assert endpoint["name"] == "Cart / Create"
    assert endpoint["url"] == "https://api.example.test/carts"
    assert endpoint["headers"][0]["enabled"] is False
    assert endpoint["query_params"][0]["enabled"] is False
    assert endpoint["body"] == {"item": 1}


def _graph_endpoint(endpoint_id, method, path, request_fields, response_fields):
    """Create a small contract-backed endpoint used by dependency graph tests."""
    return {
        "id": endpoint_id, "method": method, "url": path, "name": endpoint_id,
        "contract": {"source_id": "graph", "request_fields": request_fields, "response_fields": response_fields},
    }


def test_dependency_graph_ranks_longer_maximal_paths_and_ignores_generic_id():
    """Normalized field names link across steps while generic IDs do not create edges."""
    endpoints = [
        _graph_endpoint("cart", "POST", "/carts", [], [
            {"name": "cart_id", "json_path": "$.cart_id"}, {"name": "id", "json_path": "$.id"},
        ]),
        _graph_endpoint("checkout", "POST", "/checkout", [
            {"name": "cartId", "target": "request.path.cartId"},
        ], [{"name": "order_id", "json_path": "$.order_id"}]),
        _graph_endpoint("receipt", "GET", "/orders", [
            {"name": "order-id", "target": "request.body.order_id"},
        ], []),
        _graph_endpoint("generic", "GET", "/items", [{"name": "id", "target": "request.path.id"}], []),
    ]
    graph = build_dependency_graph(endpoints)

    assert [(item["from"], item["to"]) for item in graph["dependencies"]] == [
        ("cart", "checkout"), ("checkout", "receipt"),
    ]
    assert [item["endpoint_ids"] for item in graph["candidate_flows"]] == [["cart", "checkout", "receipt"]]
    assert graph["candidate_flows"][0]["dependency_count"] == 2


def test_cycle_edges_are_reported_but_not_used_for_executable_candidates():
    """Cycle evidence remains visible while cyclic edges do not become flow sequences."""
    endpoints = [
        _graph_endpoint("a", "POST", "/a", [{"name": "b_id", "target": "request.body.b_id"}], [{"name": "a_id", "json_path": "$.a_id"}]),
        _graph_endpoint("b", "POST", "/b", [{"name": "a_id", "target": "request.path.a_id"}], [{"name": "b_id", "json_path": "$.b_id"}]),
    ]
    graph = build_dependency_graph(endpoints)

    assert len(graph["dependencies"]) == 2
    assert all(edge["cyclic"] for edge in graph["dependencies"])
    assert graph["candidate_flows"] == []


def test_prose_extraction_uses_llm_proposal_evidence(monkeypatch):
    """Prose extraction normalizes endpoint proposals and preserves the excerpt for review."""
    from app import generator

    monkeypatch.setattr(generator, "_call_llm_with_fallback", lambda prompt: json.dumps([{
        "method": "GET", "path": "/users/{user_id}", "name": "Get user",
        "source_excerpt": "GET /users/{user_id}", "confidence": 0.9,
    }]))
    preview = parse_contract_document(
        "The API exposes GET /users/{user_id} to retrieve a user.",
        format_hint="text", base_url="https://api.example.test", source_id="docs",
    )

    assert len(preview["endpoints"]) == 1
    assert preview["endpoints"][0]["url"] == "https://api.example.test/users/{user_id}"
    assert preview["endpoints"][0]["source_excerpt"] == "GET /users/{user_id}"
