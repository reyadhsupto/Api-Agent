"""
FastAPI application entry point with PostgreSQL-backed project storage.

Accepts:
    HTTP requests from the Streamlit frontend.

Returns:
    JSON responses for project, endpoint, test case, and execution management.
"""

import json
import time
import uuid
import requests
from urllib.parse import parse_qsl, urlencode, urlsplit
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.schemas import (
    CurlParseRequest,
    ApiRequest,
    HttpAssertionExecutionRequest,
    FlowGenerateRequest,
    TestCaseGenerateRequest,
)
from app.parser import parse_curl
from app.generator import generate_test_cases, generate_flow_test_cases
from app.executor import execute_test_case, execute_flow_test_case, evaluate_request_assertions
# Load environment variables from .env file
load_dotenv()
from app.storage import Database

database = Database()

def _generate_or_raise(generator, **kwargs) -> list:
    """Run an LLM generator and expose malformed output as a useful API error."""
    try:
        return generator(**kwargs)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(
            status_code=502,
            detail=f"LLM returned invalid test-case data: {exc}",
        ) from exc


def _get_current_project() -> dict:
    """Get the current project or raise 404."""
    project = database.get_project(database.current_project_id())
    if not project:
        raise HTTPException(status_code=404, detail="No project selected. Create or select a project first.")
    return project


def _enabled_values(values) -> dict:
    """Convert saved row-based values or legacy mappings into enabled key/value pairs."""
    if isinstance(values, dict):
        return values
    if isinstance(values, list):
        return {
            str(row.get("key", "")): row.get("value", "")
            for row in values
            if isinstance(row, dict) and row.get("enabled", True) and row.get("key")
        }
    return {}


def _effective_request(request_data: dict) -> dict:
    """Strip UI-only state and prepare an API request for generation or execution."""
    request = dict(request_data)
    request["headers"] = _enabled_values(request.get("headers", {}))
    request["query_params"] = _enabled_values(request.get("query_params", {}))
    if request.get("include_body") is False:
        request["body"] = None
    for key in ("collection_id", "include_for_generation", "include_body"):
        request.pop(key, None)
    return request


def _postman_rows(values) -> list[dict]:
    """Convert saved header/query values to Postman rows with disabled state."""
    if isinstance(values, dict):
        return [{"key": key, "value": value, "enabled": True} for key, value in values.items()]
    if isinstance(values, list):
        return [row for row in values if isinstance(row, dict) and row.get("key")]
    return []


def _postman_collection(collection: dict) -> dict:
    """Build a Postman Collection v2.1 payload from saved requests."""
    items = []
    for saved in collection.get("requests", []):
        headers = _postman_rows(saved.get("headers", {}))
        query = _postman_rows(saved.get("query_params", {}))
        parts = urlsplit(saved.get("url", ""))
        query.extend(
            {"key": key, "value": value, "enabled": True}
            for key, value in parse_qsl(parts.query, keep_blank_values=True)
            if not any(row.get("key") == key for row in query)
        )
        query_payload = [
            {
                "key": row["key"],
                "value": str(row.get("value", "")),
                "disabled": not row.get("enabled", True),
                **({"description": row["description"]} if row.get("description") else {}),
            }
            for row in query
        ]
        raw_url = saved.get("url", "")
        enabled_query = [row for row in query_payload if not row["disabled"]]
        if query_payload:
            raw_url = f"{parts.scheme}://{parts.netloc}{parts.path}"
            if enabled_query:
                raw_url += f"?{urlencode([(row['key'], row['value']) for row in enabled_query])}"
        url_value = {
            "raw": raw_url,
            "protocol": parts.scheme,
            "host": parts.hostname.split(".") if parts.hostname else [],
            "path": [segment for segment in parts.path.split("/") if segment],
            "query": query_payload,
        }
        if parts.port:
            url_value["port"] = str(parts.port)
        postman_request = {
            "method": saved.get("method", "GET").upper(),
            "header": [
                {
                    "key": row["key"],
                    "value": str(row.get("value", "")),
                    "disabled": not row.get("enabled", True),
                    **({"description": row["description"]} if row.get("description") else {}),
                }
                for row in headers
            ],
            "url": url_value,
        }
        if saved.get("body") is not None:
            body = saved["body"]
            postman_request["body"] = {
                "mode": "raw",
                "raw": body if isinstance(body, str) else json.dumps(body, ensure_ascii=False),
                "disabled": not saved.get("include_body", True),
            }
        items.append({"name": saved.get("name") or "Untitled Request", "request": postman_request, "response": []})
    return {
        "info": {
            "_postman_id": collection["id"],
            "name": collection["name"],
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
        },
        "item": items,
    }


def _assign_test_case_ids(project_id: str, test_cases: list[dict]) -> None:
    """Ensure generated case IDs do not overwrite earlier generations."""
    seen = set()
    for test_case in test_cases:
        test_case_id = test_case.get("id")
        if not test_case_id or test_case_id in seen or database.find_test_case(test_case_id):
            test_case["id"] = str(uuid.uuid4())
        seen.add(test_case["id"])


def _ensure_response_schema_defaults(test_cases: list[dict]) -> None:
    """Add an editable disabled schema assertion to generated tests and flow steps.

    Args:
        test_cases (list[dict]): Generated single tests and flow scenarios.

    Returns:
        None: Updates each generated case or step in place.
    """
    for test_case in test_cases:
        if test_case.get("is_flow") or isinstance(test_case.get("steps"), list):
            for step in test_case.get("steps", []):
                if not isinstance(step, dict):
                    continue
                assertions = step.get("assertions")
                if not isinstance(assertions, dict):
                    assertions = {}
                    step["assertions"] = assertions
                assertions.setdefault(
                    "response_schema", {"enabled": False, "schema": "{}"}
                )
        else:
            assertions = test_case.get("assertions")
            if not isinstance(assertions, dict):
                assertions = {}
                test_case["assertions"] = assertions
            assertions.setdefault(
                "response_schema", {"enabled": False, "schema": "{}"}
            )


app = FastAPI(title="Api-Agent", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    """
    Return application health status.

    Returns:
        dict: {"status": "ok"}
    """
    return {"status": "ok"}


# --- Project Management ---

@app.post("/api/v1/projects")
def create_project(request: dict) -> dict:
    """
    Create a new project with a name.

    Args:
        request (dict): Contains 'name' and optional 'description'.

    Returns:
        dict: The created project.
    """
    return database.create_project(
        request.get("name", "Untitled Project"),
        request.get("description", ""),
    )


@app.get("/api/v1/projects")
def list_projects() -> list:
    """
    List all projects.

    Returns:
        list: List of project summaries.
    """
    return database.list_projects()


@app.get("/api/v1/projects/{project_id}")
def get_project(project_id: str) -> dict:
    """
    Get a project by ID.

    Args:
        project_id (str): The project ID.

    Returns:
        dict: The project with all endpoints, test cases, and executions.

    Raises:
        HTTPException: If project not found.
    """
    project = database.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    database.set_current_project(project_id)
    return project


@app.put("/api/v1/projects/{project_id}")
def update_project(project_id: str, request: dict) -> dict:
    """
    Update a project's name or description.

    Args:
        project_id (str): The project ID.
        request (dict): Fields to update (name, description).

    Returns:
        dict: The updated project.

    Raises:
        HTTPException: If project not found.
    """
    project = database.update_project(project_id, request)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@app.put("/api/v1/projects/{project_id}/generation-order")
def update_project_generation_order(project_id: str, request: dict) -> dict:
    """Persist the order used to build flows from saved project requests.

    Args:
        project_id (str): Project whose generation order is being changed.
        request (dict): Payload containing the ordered `request_ids` list.

    Returns:
        dict: Canonical generation-order request IDs.

    Raises:
        HTTPException: If the project is missing or IDs are invalid.
    """
    request_ids = request.get("request_ids", [])
    if not isinstance(request_ids, list) or not all(isinstance(item, str) for item in request_ids):
        raise HTTPException(status_code=422, detail="request_ids must be a list of request ID strings.")
    try:
        saved_order = database.set_generation_order(project_id, request_ids)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if saved_order is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"generation_order_ids": saved_order}


@app.delete("/api/v1/projects/{project_id}")
def delete_project(project_id: str) -> dict:
    """
    Delete a project and all its data.

    Args:
        project_id (str): The project ID.

    Returns:
        dict: Confirmation message.

    Raises:
        HTTPException: If project not found.
    """
    if not database.delete_project(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    return {"message": "Project deleted"}


@app.get("/api/v1/projects/current")
def get_current_project() -> dict:
    """
    Get the currently selected project.

    Returns:
        dict: The current project.

    Raises:
        HTTPException: If no project selected.
    """
    return _get_current_project()


# --- Endpoint Management ---

@app.post("/api/v1/curl/parse")
def parse_curl_endpoint(request: CurlParseRequest) -> dict:
    """
    Parse a raw cURL command into structured request components.

    Args:
        request (CurlParseRequest): Contains the raw cURL string.

    Returns:
        dict: Parsed request components.
    """
    parsed = parse_curl(request.curl)
    return parsed


@app.get("/api/v1/projects/{project_id}/collections")
def list_collections(project_id: str) -> list:
    """List a project's saved request collections."""
    if not database.get_project(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    return database.list_collections(project_id)


@app.post("/api/v1/projects/{project_id}/collections")
def create_collection(project_id: str, request: dict) -> dict:
    """Create a named request collection in a project."""
    name = str(request.get("name", "")).strip()
    if not name:
        raise HTTPException(status_code=422, detail="Collection name is required")
    if len(name) > 100:
        raise HTTPException(status_code=422, detail="Collection name must be 100 characters or fewer")
    collection = database.create_collection(project_id, name)
    if collection is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return collection


@app.put("/api/v1/projects/{project_id}/collections/{collection_id}")
def update_collection(project_id: str, collection_id: str, request: dict) -> dict:
    """Rename a saved collection."""
    name = str(request.get("name", "")).strip()
    if not name:
        raise HTTPException(status_code=422, detail="Collection name is required")
    collection = database.update_collection(project_id, collection_id, {"name": name})
    if collection is None:
        raise HTTPException(status_code=404, detail="Collection not found")
    return collection


@app.delete("/api/v1/projects/{project_id}/collections/{collection_id}")
def delete_collection(project_id: str, collection_id: str) -> dict:
    """Delete a collection and its requests."""
    if not database.delete_collection(project_id, collection_id):
        raise HTTPException(status_code=404, detail="Collection not found")
    return {"message": "Collection deleted"}


@app.post("/api/v1/projects/{project_id}/collections/{collection_id}/requests")
def save_collection_request(project_id: str, collection_id: str, request: dict) -> dict:
    """Save or update a request in a collection."""
    try:
        saved = database.save_request(project_id, collection_id, request)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if saved is None:
        raise HTTPException(status_code=404, detail="Project or collection not found")
    return saved


@app.put("/api/v1/projects/{project_id}/collections/{collection_id}/requests/{request_id}")
def update_collection_request(project_id: str, collection_id: str, request_id: str, request: dict) -> dict:
    """Update a saved request without changing its collection membership."""
    collection = database.get_collection(project_id, collection_id)
    if collection is None:
        raise HTTPException(status_code=404, detail="Collection not found")
    saved = database.update_request(project_id, request_id, request)
    if saved is None or saved.get("collection_id") != collection_id:
        raise HTTPException(status_code=404, detail="Request not found")
    return saved


@app.delete("/api/v1/projects/{project_id}/collections/{collection_id}/requests/{request_id}")
def delete_collection_request(project_id: str, collection_id: str, request_id: str) -> dict:
    """Delete a saved request from its collection."""
    collection = database.get_collection(project_id, collection_id)
    if collection is None:
        raise HTTPException(status_code=404, detail="Collection not found")
    request = next((item for item in collection["requests"] if item["id"] == request_id), None)
    if not request or not database.delete_request(project_id, request_id):
        raise HTTPException(status_code=404, detail="Request not found")
    return {"message": "Request deleted"}


@app.get("/api/v1/projects/{project_id}/collections/{collection_id}/export")
def export_collection(project_id: str, collection_id: str) -> dict:
    """Export a saved collection in Postman Collection v2.1 format."""
    collection = database.get_collection(project_id, collection_id)
    if collection is None:
        raise HTTPException(status_code=404, detail="Collection not found")
    return _postman_collection(collection)


@app.post("/api/v1/http/send")
def send_api_request(request: ApiRequest) -> dict:
    """Send one ad hoc HTTP request and return response details without persistence."""
    if not request.url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="Enter an absolute http:// or https:// URL.")
    method = request.method.upper()
    if method not in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}:
        raise HTTPException(status_code=400, detail="Unsupported HTTP method.")
    started = time.perf_counter()
    try:
        response = requests.request(
            method,
            request.url,
            headers=request.headers,
            params=request.query_params,
            json=request.body if isinstance(request.body, (dict, list)) else None,
            data=request.body if isinstance(request.body, str) else None,
            timeout=request.timeout_seconds,
        )
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Request failed: {exc}") from exc
    return {
        "status": response.status_code,
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
        "headers": dict(response.headers),
        "body": response.text,
        "url": response.url,
    }


@app.post("/api/v1/http/execute-assertions")
def execute_http_assertions(request: HttpAssertionExecutionRequest) -> dict:
    """Send one temporary HTTP request and evaluate supplied assertions.

    Args:
        request (HttpAssertionExecutionRequest): HTTP request and selected assertions.

    Returns:
        dict: Response metadata and per-assertion plus aggregate results.

    Raises:
        HTTPException: If the URL or method is invalid, or the request fails.
    """
    api_request = request.request
    if not api_request.url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="Enter an absolute http:// or https:// URL.")
    method = api_request.method.upper()
    if method not in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}:
        raise HTTPException(status_code=400, detail="Unsupported HTTP method.")

    started = time.perf_counter()
    try:
        response = requests.request(
            method,
            api_request.url,
            headers=api_request.headers,
            params=api_request.query_params,
            json=api_request.body if isinstance(api_request.body, (dict, list)) else None,
            data=api_request.body if isinstance(api_request.body, str) else None,
            timeout=api_request.timeout_seconds,
        )
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Request failed: {exc}") from exc

    assertion_result = evaluate_request_assertions(
        response.status_code, response.text, request.assertions
    )
    return {
        "status": response.status_code,
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
        "headers": dict(response.headers),
        "body": response.text,
        "url": response.url,
        "assertion_results": assertion_result["results"],
        "assertions_passed": assertion_result["passed"],
    }


@app.post("/api/v1/projects/{project_id}/endpoints")
def add_endpoint(project_id: str, request: dict) -> dict:
    """
    Add an endpoint to a project.

    Args:
        project_id (str): The project ID.
        request (dict): The endpoint data.

    Returns:
        dict: The added endpoint.

    Raises:
        HTTPException: If project not found.
    """
    endpoint = {
        **request,
        "id": request.get("id", str(uuid.uuid4())),
        "include": request.get("include", True),
        "method": request.get("method", "GET"),
        "url": request.get("url", ""),
        "headers": request.get("headers", {}),
        "query_params": request.get("query_params", {}),
        "path_params": request.get("path_params", {}),
        "body": request.get("body"),
    }
    saved = database.add_endpoint(project_id, endpoint)
    if not saved:
        raise HTTPException(status_code=404, detail="Project not found")
    return saved


@app.put("/api/v1/projects/{project_id}/endpoints")
def replace_endpoints(project_id: str, request: dict) -> dict:
    """Replace the project's endpoints with the supplied ordered collection."""
    endpoints = request.get("endpoints", [])
    try:
        if not database.replace_endpoints(project_id, endpoints):
            raise HTTPException(status_code=404, detail="Project not found")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"message": f"Saved {len(endpoints)} endpoint(s)", "endpoints": endpoints}


@app.put("/api/v1/projects/{project_id}/endpoints/{endpoint_id}")
def update_endpoint(project_id: str, endpoint_id: str, request: dict) -> dict:
    """
    Update an endpoint in a project.

    Args:
        project_id (str): The project ID.
        endpoint_id (str): The endpoint ID.
        request (dict): Fields to update.

    Returns:
        dict: The updated endpoint.

    Raises:
        HTTPException: If project or endpoint not found.
    """
    endpoint = database.update_endpoint(project_id, endpoint_id, request)
    if endpoint is None:
        if database.get_project(project_id) is None:
            raise HTTPException(status_code=404, detail="Project not found")
        raise HTTPException(status_code=404, detail="Endpoint not found")
    return endpoint


@app.delete("/api/v1/projects/{project_id}/endpoints/{endpoint_id}")
def delete_endpoint(project_id: str, endpoint_id: str) -> dict:
    """
    Delete an endpoint from a project.

    Args:
        project_id (str): The project ID.
        endpoint_id (str): The endpoint ID.

    Returns:
        dict: Confirmation message.

    Raises:
        HTTPException: If project not found.
    """
    if database.get_project(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    database.delete_endpoint(project_id, endpoint_id)
    return {"message": "Endpoint deleted"}


# --- Test Case Management ---

@app.post("/api/v1/test-cases/generate")
def generate_test_cases_endpoint(request: TestCaseGenerateRequest) -> list:
    """
    Generate AI-powered test cases from a parsed cURL.

    Args:
        request (TestCaseGenerateRequest): Parsed cURL and optional requirements.

    Returns:
        list: Generated test cases.
    """
    test_cases = _generate_or_raise(
        generate_test_cases,
        parsed_curl=_effective_request(request.parsed_curl),
        business_requirements=request.business_requirements,
    )
    for tc in test_cases:
        if not tc.get("id"):
            tc["id"] = str(uuid.uuid4())
        if "assertions" not in tc:
            tc["assertions"] = {
                "status": {"enabled": True, "expected_status": tc.get("expected_status", 200)},
                "body_contains": {"enabled": tc.get("expected_body_contains") is not None, "value": tc.get("expected_body_contains", "") or ""},
                "jsonpath": {"enabled": False, "path": "", "expected_value": ""},
            }
    _ensure_response_schema_defaults(test_cases)
    project_id = request.project_id or database.current_project_id()
    _assign_test_case_ids(project_id, test_cases)
    if not database.save_test_cases(project_id, test_cases):
        raise HTTPException(status_code=404, detail="Project not found")
    return test_cases


@app.post("/api/v1/test-cases/generate-flow")
def generate_flow_test_cases_standalone(request: FlowGenerateRequest) -> list:
    """
    Generate flow test cases without a project (standalone mode).

    Args:
        request (dict): Contains 'endpoints' (list of endpoint dicts) and optional 'business_requirements'.

    Returns:
        list: Generated flow test cases.
    """
    endpoints = [_effective_request(item) for item in request.endpoints]
    business_requirements = request.business_requirements
    project_id = request.project_id or database.current_project_id()

    if not endpoints:
        raise HTTPException(status_code=400, detail="No endpoints provided")

    test_cases = _generate_or_raise(
        generate_flow_test_cases,
        endpoints=endpoints,
        business_requirements=business_requirements,
    )
    for tc in test_cases:
        if not tc.get("id"):
            tc["id"] = str(uuid.uuid4())
        tc["is_flow"] = True
        if "assertions" not in tc:
            tc["assertions"] = {
                "status": {"enabled": True, "expected_status": tc.get("expected_status", 200)},
                "body_contains": {"enabled": tc.get("expected_body_contains") is not None, "value": tc.get("expected_body_contains", "") or ""},
                "jsonpath": {"enabled": False, "path": "", "expected_value": ""},
            }
    _ensure_response_schema_defaults(test_cases)
    _assign_test_case_ids(project_id, test_cases)
    if not database.save_test_cases(project_id, test_cases):
        raise HTTPException(status_code=404, detail="Project not found")
    return test_cases


@app.post("/api/v1/projects/{project_id}/test-cases/generate-flow")
def generate_flow_test_cases_project(project_id: str, request: FlowGenerateRequest) -> list:
    """
    Generate flow test cases for a project (sequence of endpoints).

    Args:
        project_id (str): The project ID.
        request (dict): Contains endpoint_ids (ordered list), endpoints (full data), and optional business_requirements.

    Returns:
        list: Generated flow test cases.

    Raises:
        HTTPException: If project not found.
    """
    project = database.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    endpoint_ids = request.endpoint_ids
    endpoints_data = [_effective_request(item) for item in request.endpoints]
    business_requirements = request.business_requirements

    # Use full endpoint data if provided, otherwise look up from project
    if endpoints_data:
        ordered = endpoints_data
    else:
        endpoints = [ep for ep in project["endpoints"] if ep["id"] in endpoint_ids]
        ordered = []
        for eid in endpoint_ids:
            ep = next((e for e in endpoints if e["id"] == eid), None)
            if ep:
                ordered.append(_effective_request(ep))

    if not ordered:
        raise HTTPException(status_code=400, detail="No valid endpoints found. Please add and save endpoints to the project first, or select at least one endpoint.")

    test_cases = _generate_or_raise(
        generate_flow_test_cases,
        endpoints=ordered,
        business_requirements=business_requirements,
    )
    for tc in test_cases:
        if not tc.get("id"):
            tc["id"] = str(uuid.uuid4())
        tc["is_flow"] = True
        if "assertions" not in tc:
            tc["assertions"] = {
                "status": {"enabled": True, "expected_status": tc.get("expected_status", 200)},
                "body_contains": {"enabled": tc.get("expected_body_contains") is not None, "value": tc.get("expected_body_contains", "") or ""},
                "jsonpath": {"enabled": False, "path": "", "expected_value": ""},
            }
    _ensure_response_schema_defaults(test_cases)
    _assign_test_case_ids(project_id, test_cases)
    if not database.save_test_cases(project_id, test_cases):
        raise HTTPException(status_code=404, detail="Project not found")
    return test_cases


@app.post("/api/v1/projects/{project_id}/test-cases/save")
def save_test_cases(project_id: str, request: dict) -> dict:
    """
    Save generated test cases to a project.

    Args:
        project_id (str): The project ID.
        request (dict): Contains 'test_cases' list.

    Returns:
        dict: Confirmation with count.

    Raises:
        HTTPException: If project not found.
    """
    project = database.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    new_tcs = request.get("test_cases", [])
    for tc in new_tcs:
        if not tc.get("id"):
            tc["id"] = str(uuid.uuid4())
    if not database.save_test_cases(project_id, new_tcs):
        raise HTTPException(status_code=404, detail="Project not found")
    updated = database.get_project(project_id)
    return {"message": f"Saved {len(new_tcs)} test case(s)", "count": len(updated["test_cases"])}


@app.get("/api/v1/projects/{project_id}/test-cases")
def get_test_cases(project_id: str) -> list:
    """
    Get all test cases for a project.

    Args:
        project_id (str): The project ID.

    Returns:
        list: List of test cases.

    Raises:
        HTTPException: If project not found.
    """
    project = database.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project["test_cases"]


@app.delete("/api/v1/projects/{project_id}/test-cases")
def clear_test_cases(project_id: str) -> dict:
    """Clear saved test cases and their execution history from a project."""
    if not database.clear_test_cases(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    return {"message": "Test cases cleared"}


@app.delete("/api/v1/projects/{project_id}/test-cases/{test_case_id}")
def delete_test_case(project_id: str, test_case_id: str) -> dict:
    """
    Delete a test case from a project.

    Args:
        project_id (str): The project ID.
        test_case_id (str): The test case ID.

    Returns:
        dict: Confirmation message.

    Raises:
        HTTPException: If project not found.
    """
    if database.get_project(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    database.delete_test_case(project_id, test_case_id)
    return {"message": "Test case deleted"}


@app.put("/api/v1/projects/{project_id}/test-cases/{test_case_id}")
def update_test_case(project_id: str, test_case_id: str, request: dict) -> dict:
    """
    Update a test case in a project.

    Args:
        project_id (str): The project ID.
        test_case_id (str): The test case ID.
        request (dict): Fields to update.

    Returns:
        dict: The updated test case.

    Raises:
        HTTPException: If project or test case not found.
    """
    if database.get_project(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    tc = database.update_test_case(project_id, test_case_id, request)
    if not tc:
        raise HTTPException(status_code=404, detail="Test case not found")
    return tc


# --- Test Case Execution ---

@app.post("/api/v1/test-cases/execute")
def execute_test_case_endpoint(request: dict) -> dict:
    """
    Execute a single test case and capture full request/response details.

    Args:
        request (dict): Contains test_case_id, project_id, and optional assertions.

    Returns:
        dict: Execution result with assertion detail.

    Raises:
        HTTPException: If test case or project not found.
    """
    test_case_id = request.get("test_case_id")
    project_id = request.get("project_id")
    assertions = request.get("assertions", {})

    if not test_case_id:
        raise HTTPException(status_code=400, detail="test_case_id is required")

    found = database.find_test_case(test_case_id, project_id)
    if not found:
        raise HTTPException(status_code=404, detail="Test case not found")
    owning_project_id, test_case = found

    # Detect flow test cases and execute sequentially with variable substitution
    if test_case.get("is_flow"):
        result = execute_flow_test_case(test_case, assertions=assertions)
    else:
        result = execute_test_case(test_case, assertions=assertions)
    database.append_execution(owning_project_id, test_case_id, result)
    return result


@app.get("/api/v1/memory/state")
def memory_state() -> dict:
    """
    Return persisted state for UI hydration.

    Returns:
        dict: projects, current_project_id.
    """
    return {
        "projects": [project["id"] for project in database.list_projects()],
        "current_project_id": database.current_project_id(),
    }
