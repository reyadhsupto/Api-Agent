"""
FastAPI application entry point with PostgreSQL-backed project storage.

Accepts:
    HTTP requests from the Streamlit frontend.

Returns:
    JSON responses for project, endpoint, test case, and execution management.
"""

import json
import copy
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
    ContractPreviewRequest,
    ContractImportRequest,
    FlowDiscoveryRequest,
    DiscoveredFlowGenerateRequest,
)
from app.parser import parse_curl
from app.generator import generate_test_cases, generate_flow_test_cases, generate_discovered_flow_test_cases
from app.contracts import (
    build_dependency_graph,
    fetch_public_document,
    parse_contract_document,
)
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


def _load_generation_examples(
    project_id: str, example_ids: list[str], project: dict | None = None,
) -> list[dict]:
    """Load selected generation examples and ensure every ID belongs to the project.

    Args:
        project_id (str): Project that owns the requested examples.
        example_ids (list[str]): Stable test-case IDs selected by the user.
        project (dict | None): Already loaded project aggregate, if available.

    Returns:
        list[dict]: Selected saved case payloads in the requested order.

    Raises:
        HTTPException: If the project or any selected case does not exist in it.
    """
    if not example_ids:
        return []
    project = project or database.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    cases_by_id = {str(case.get("id")): case for case in project.get("test_cases", [])}
    missing_ids = [case_id for case_id in dict.fromkeys(example_ids) if case_id not in cases_by_id]
    if missing_ids:
        raise HTTPException(
            status_code=404,
            detail=f"Generation example test case(s) not found in project: {', '.join(missing_ids)}",
        )
    return [cases_by_id[case_id] for case_id in dict.fromkeys(example_ids)]


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


@app.get("/api/v1/projects/{project_id}/test-runs")
def list_project_test_runs(project_id: str) -> list:
    """List reusable test runs scoped to one project.

    Args:
        project_id (str): Project whose saved runs should be returned.

    Returns:
        list: Saved run records with ordered case IDs.

    Raises:
        HTTPException: If the project does not exist.
    """
    runs = database.list_test_runs(project_id)
    if runs is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return runs


def _save_project_test_run(project_id: str, request: dict, run_id: str | None = None) -> dict:
    """Validate and persist one named run with ordered case membership.

    Args:
        project_id (str): Project that owns the run.
        request (dict): Request body containing name and case_ids.
        run_id (str | None): Existing run ID to update, if provided.

    Returns:
        dict: Saved run record.

    Raises:
        HTTPException: For invalid input, duplicate names, or missing records.
    """
    name = request.get("name")
    case_ids = request.get("case_ids")
    if not isinstance(name, str):
        raise HTTPException(status_code=422, detail="Test run name is required.")
    if not isinstance(case_ids, list) or not all(isinstance(case_id, str) for case_id in case_ids):
        raise HTTPException(status_code=422, detail="case_ids must be a list of test-case ID strings.")
    try:
        saved = database.save_test_run(project_id, name, case_ids, run_id)
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if saved is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return saved


@app.post("/api/v1/projects/{project_id}/test-runs")
def create_project_test_run(project_id: str, request: dict) -> dict:
    """Create a named reusable selection of project test cases.

    Args:
        project_id (str): Project that owns the new run.
        request (dict): Name and ordered list of case IDs.

    Returns:
        dict: Saved run record.
    """
    return _save_project_test_run(project_id, request)


@app.put("/api/v1/projects/{project_id}/test-runs/{run_id}")
def update_project_test_run(project_id: str, run_id: str, request: dict) -> dict:
    """Update a named run's name or ordered case membership.

    Args:
        project_id (str): Project that owns the run.
        run_id (str): Stable run ID to update.
        request (dict): Replacement name and ordered list of case IDs.

    Returns:
        dict: Updated run record.
    """
    return _save_project_test_run(project_id, request, run_id)


@app.delete("/api/v1/projects/{project_id}/test-runs/{run_id}")
def delete_project_test_run(project_id: str, run_id: str) -> dict:
    """Delete a reusable run without deleting its referenced test cases.

    Args:
        project_id (str): Project that owns the run.
        run_id (str): Stable run ID to delete.

    Returns:
        dict: Deletion confirmation.
    """
    if database.get_project(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if not database.delete_test_run(project_id, run_id):
        raise HTTPException(status_code=404, detail="Test run not found")
    return {"message": "Test run deleted"}


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


@app.post("/api/v1/contracts/preview")
def preview_contract(request: ContractPreviewRequest) -> dict:
    """Parse a contract or prose document and return every endpoint for review.

    Args:
        request (ContractPreviewRequest): Source content/URL and parser options.

    Returns:
        dict: Endpoint previews, source metadata, dependencies, and candidates.

    Raises:
        HTTPException: If source fetching, parsing, or LLM extraction fails.
    """
    content = request.content
    content_type = ""
    if request.source_type == "url":
        try:
            content, content_type = fetch_public_document(request.content)
        except (ValueError, requests.RequestException) as exc:
            raise HTTPException(status_code=422, detail=f"Could not fetch documentation: {exc}") from exc
    if len(content.encode("utf-8")) > 5_000_000:
        raise HTTPException(status_code=413, detail="Contract content exceeds the 5 MB import limit.")
    try:
        source_name = request.source_name or (request.content if request.source_type == "url" else "")
        result = parse_contract_document(
            content=content,
            source_name=source_name,
            format_hint=request.format_hint,
            base_url=request.base_url,
            source_id=request.source_id,
            is_html="text/html" in content_type.lower(),
        )
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=f"Could not parse API documentation: {exc}") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=f"Could not extract endpoints with the configured LLM: {exc}") from exc
    if not result["endpoints"]:
        raise HTTPException(status_code=422, detail="The source did not contain any API endpoints.")
    return result


@app.post("/api/v1/projects/{project_id}/contracts/import")
def import_contract_requests(project_id: str, request: ContractImportRequest) -> dict:
    """Persist reviewed endpoints and return their dependency candidates.

    Args:
        project_id (str): Project receiving the imported requests.
        request (ContractImportRequest): Destination collection and reviewed endpoints.

    Returns:
        dict: Imported requests, dependency evidence, and candidate paths.

    Raises:
        HTTPException: If the project/collection is missing or data is invalid.
    """
    if not database.get_project(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    endpoints = []
    for raw_endpoint in request.endpoints:
        endpoint = dict(raw_endpoint)
        endpoint.pop("_base_url_required", None)
        url = str(endpoint.get("url", ""))
        method = str(endpoint.get("method", "GET")).upper()
        if not url.startswith(("http://", "https://")):
            raise HTTPException(status_code=422, detail=f"Endpoint {endpoint.get('name', '')!r} needs an absolute URL. Set an API base URL and preview again.")
        if method not in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS", "TRACE"}:
            raise HTTPException(status_code=422, detail=f"Unsupported HTTP method: {method}")
        endpoint["method"] = method
        if method in {"GET", "DELETE"}:
            endpoint["body"] = None
            endpoint["include_body"] = False
            contract = endpoint.get("contract")
            if isinstance(contract, dict):
                contract["request_fields"] = [
                    field for field in contract.get("request_fields", [])
                    if not str(field.get("target", "")).startswith("request.body.")
                ]
        endpoints.append(endpoint)
    if not endpoints:
        raise HTTPException(status_code=422, detail="Select at least one endpoint to import.")
    try:
        saved = database.import_requests(project_id, request.collection_id, endpoints)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if saved is None:
        raise HTTPException(status_code=404, detail="Destination collection not found")
    project = database.get_project(project_id)
    source_ids = {item.get("contract", {}).get("source_id") for item in saved}
    source_id = next(iter(source_ids)) if len(source_ids) == 1 else None
    graph = build_dependency_graph(project.get("endpoints", []))
    candidates = [item for item in graph["candidate_flows"] if item.get("source_id") == source_id]
    source_endpoint_ids = {item["id"] for item in saved}
    dependencies = [
        item for item in graph["dependencies"]
        if item.get("from") in source_endpoint_ids and item.get("to") in source_endpoint_ids
    ]
    return {"imported": saved, "source_id": source_id, "dependencies": dependencies, "candidate_flows": candidates}


@app.post("/api/v1/projects/{project_id}/contracts/flow-candidates")
def discover_contract_flows(project_id: str, request: FlowDiscoveryRequest) -> dict:
    """Rebuild graph edges and ranked paths from saved contract metadata.

    Args:
        project_id (str): Project owning the imported contract operations.
        request (FlowDiscoveryRequest): Source ID to analyze.

    Returns:
        dict: Dependency evidence and ranked candidate flows.

    Raises:
        HTTPException: If the project or imported source is missing.
    """
    project = database.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    endpoints = [
        item for item in project.get("endpoints", [])
        if item.get("contract", {}).get("source_id") == request.source_id
    ]
    if not endpoints:
        raise HTTPException(status_code=404, detail="No imported contract endpoints found for this source.")
    graph = build_dependency_graph(endpoints)
    return {"source_id": request.source_id, **graph}


@app.post("/api/v1/projects/{project_id}/contracts/generate-flows")
def generate_contract_flows(project_id: str, request: DiscoveredFlowGenerateRequest) -> list:
    """Generate flow cases from selected dependency paths and persist them.

    Args:
        project_id (str): Project where generated cases are stored.
        request (DiscoveredFlowGenerateRequest): Selected candidates and business context.

    Returns:
        list: Validated, persisted flow test cases.

    Raises:
        HTTPException: If candidates are invalid or LLM output cannot form valid flows.
    """
    project = database.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    endpoints = [
        item for item in project.get("endpoints", [])
        if item.get("contract", {}).get("source_id") == request.source_id
    ]
    if not endpoints:
        raise HTTPException(status_code=404, detail="No imported contract endpoints found for this source.")
    graph = build_dependency_graph(endpoints)
    candidates_by_id = {item["id"]: item for item in graph["candidate_flows"]}
    selected_ids = list(dict.fromkeys(request.candidate_ids))
    if not selected_ids or any(candidate_id not in candidates_by_id for candidate_id in selected_ids):
        raise HTTPException(status_code=422, detail="Choose one or more valid dependency flow candidates.")
    candidates = [candidates_by_id[item] for item in selected_ids]
    try:
        test_cases = generate_discovered_flow_test_cases(
            endpoints=endpoints,
            candidates=candidates,
            business_requirements=request.business_requirements,
        )
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=502, detail=f"LLM returned invalid flow data: {exc}") from exc
    if not isinstance(test_cases, list) or not test_cases:
        raise HTTPException(status_code=502, detail="LLM returned no usable flow scenarios.")
    candidates_by_id = {item["id"]: item for item in candidates}
    endpoints_by_id = {item["id"]: _effective_request(item) for item in endpoints}
    for test_case in test_cases:
        if not isinstance(test_case, dict):
            raise HTTPException(status_code=502, detail="LLM flow scenarios must be JSON objects.")
        candidate = candidates_by_id.get(test_case.get("candidate_id"))
        if candidate is None:
            raise HTTPException(status_code=502, detail="LLM flow references an unknown candidate.")
        steps = test_case.get("steps")
        if not isinstance(steps, list) or len(steps) != len(candidate["endpoint_ids"]):
            raise HTTPException(status_code=502, detail="LLM flow steps do not match the selected dependency path.")
        edges = {(edge["from"], edge["to"]): edge for edge in candidate["dependencies"]}
        for index, (step, endpoint_id) in enumerate(zip(steps, candidate["endpoint_ids"]), start=1):
            if not isinstance(step, dict):
                raise HTTPException(status_code=502, detail="LLM flow steps must be JSON objects.")
            if step.get("endpoint_id") != endpoint_id:
                raise HTTPException(status_code=502, detail="LLM flow endpoint order does not match its selected dependency path.")
            step["step_order"] = index
            step["endpoint"] = endpoints_by_id[endpoint_id]
            step.setdefault("assertions", {})
            mappings = step.get("variable_mappings", [])
            if not isinstance(mappings, list) or any(not isinstance(mapping, dict) for mapping in mappings):
                raise HTTPException(status_code=502, detail="LLM variable mappings must be an array of JSON objects.")
            if index > 1:
                edge = edges[(candidate["endpoint_ids"][index - 2], endpoint_id)]
                allowed = {(item["response_field"], item["request_field"]) for item in edge["evidence"]}
                step["variable_mappings"] = [
                    mapping for mapping in mappings
                    if (mapping.get("from"), mapping.get("to")) in allowed
                ]
            else:
                step["variable_mappings"] = []
        test_case["is_flow"] = True
        test_case.setdefault("id", str(uuid.uuid4()))
    _ensure_response_schema_defaults(test_cases)
    _assign_test_case_ids(project_id, test_cases)
    if not database.save_test_cases(project_id, test_cases):
        raise HTTPException(status_code=404, detail="Project not found")
    return test_cases


@app.post("/api/v1/http/send")
def send_api_request(request: ApiRequest) -> dict:
    """Send one ad hoc HTTP request and return response details without persistence."""
    if not request.url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="Enter an absolute http:// or https:// URL.")
    method = request.method.upper()
    if method not in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS", "TRACE"}:
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
    if method not in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS", "TRACE"}:
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
    project_id = request.project_id or database.current_project_id()
    source_endpoint = None
    project = None
    if request.source_endpoint_id or request.example_test_case_ids:
        project = database.get_project(project_id) if project_id else None
    if request.source_endpoint_id:
        source_endpoint = next(
            (endpoint for endpoint in (project or {}).get("endpoints", [])
             if endpoint.get("id") == request.source_endpoint_id),
            None,
        )
        if source_endpoint is None:
            raise HTTPException(status_code=404, detail="Source endpoint not found in project")
    examples = _load_generation_examples(project_id, request.example_test_case_ids, project)

    test_cases = _generate_or_raise(
        generate_test_cases,
        parsed_curl=_effective_request(request.parsed_curl),
        business_requirements=request.business_requirements,
        example_test_cases=examples,
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
    if source_endpoint:
        display_name = source_endpoint.get("name") or source_endpoint.get("url") or "Unnamed endpoint"
        for tc in test_cases:
            tc["source_endpoint_id"] = source_endpoint["id"]
            tc["source_endpoint_name"] = display_name
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
    examples = _load_generation_examples(project_id, request.example_test_case_ids)

    test_cases = _generate_or_raise(
        generate_flow_test_cases,
        endpoints=endpoints,
        business_requirements=business_requirements,
        example_test_cases=examples,
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
    examples = _load_generation_examples(project_id, request.example_test_case_ids, project)
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
        example_test_cases=examples,
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
    if not isinstance(request, dict):
        raise HTTPException(status_code=422, detail="Test case payload must be a JSON object.")
    if request.get("id") not in (None, test_case_id):
        raise HTTPException(status_code=422, detail="Test case ID cannot be changed during an update.")
    existing = database.find_test_case(test_case_id, project_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Test case not found")
    merged = copy.deepcopy(existing[1])
    merged.update(request)
    merged["id"] = test_case_id
    _validate_editable_test_case(merged)
    request_data_changed = (
        existing[1].get("request") != merged.get("request")
        or existing[1].get("steps") != merged.get("steps")
    )
    tc = database.update_test_case(project_id, test_case_id, merged)
    if request_data_changed:
        database.clear_test_case_executions(project_id, test_case_id)
    return tc


def _validate_editable_test_case(test_case: dict) -> None:
    """Validate editable request and flow-step data before persistence or execution."""
    if test_case.get("is_flow"):
        steps = test_case.get("steps")
        if not isinstance(steps, list) or not steps:
            raise HTTPException(status_code=422, detail="A flow must contain at least one request step.")
        for index, step in enumerate(steps, start=1):
            if not isinstance(step, dict):
                raise HTTPException(status_code=422, detail=f"Flow step {index} must be a JSON object.")
            endpoint = step.get("endpoint")
            if not isinstance(endpoint, dict) or not isinstance(endpoint.get("url"), str) or not endpoint["url"].strip():
                raise HTTPException(status_code=422, detail=f"Flow step {index} needs a request URL.")
            method = endpoint.get("method", "GET")
            if not isinstance(method, str) or not method.strip() or not method.replace("-", "").isalnum():
                raise HTTPException(status_code=422, detail=f"Flow step {index} has an invalid request method.")
            step["step_order"] = index
            mappings = step.get("variable_mappings", [])
            if not isinstance(mappings, list):
                raise HTTPException(status_code=422, detail=f"Flow step {index} mappings must be a list.")
            # A first step has no earlier response. Drop any stale or LLM-added
            # mappings there so generated legacy flows remain executable.
            if index == 1:
                step["variable_mappings"] = []
                continue
            normalized_mappings = []
            for mapping in mappings:
                if not isinstance(mapping, dict):
                    raise HTTPException(status_code=422, detail=f"Flow step {index} mappings must contain JSON objects.")
                source = mapping.get("from")
                target = mapping.get("to")
                if not str(source or "").strip() and not str(target or "").strip():
                    continue
                mapping_index = len(normalized_mappings) + 1
                if not isinstance(source, str) or not isinstance(target, str) or not source.strip() or not target.strip():
                    raise HTTPException(status_code=422, detail=f"Flow step {index} mapping {mapping_index} needs a source and destination.")
                json_path = source.split(":", 1)[1] if ":" in source and source.split(":", 1)[0].isdigit() else source
                if not json_path.startswith("$"):
                    raise HTTPException(status_code=422, detail=f"Flow step {index} mapping {mapping_index} source must be a JSONPath, optionally prefixed with a step number.")
                if ":" in source and source.split(":", 1)[0].isdigit():
                    source_step = int(source.split(":", 1)[0])
                    if source_step < 1 or source_step >= index:
                        raise HTTPException(status_code=422, detail=f"Flow step {index} mapping {mapping_index} must reference an earlier step.")
                target_supported = (
                    target.startswith("headers.") and len(target) > len("headers.")
                    or target.startswith("request.query.") and len(target) > len("request.query.")
                    or target.startswith("request.path.") and len(target) > len("request.path.")
                    or target == "request.body"
                    or target.startswith("request.body.")
                )
                if not target_supported:
                    raise HTTPException(status_code=422, detail=f"Flow step {index} mapping {mapping_index} has an unsupported destination.")
                if mapping.get("transform") is not None and not isinstance(mapping.get("transform"), str):
                    raise HTTPException(status_code=422, detail=f"Flow step {index} mapping {mapping_index} transform must be text.")
                normalized_mappings.append(mapping)
            step["variable_mappings"] = normalized_mappings
    else:
        request = test_case.get("request")
        if not isinstance(request, dict):
            raise HTTPException(status_code=422, detail="A single test case needs a request object.")
        if not isinstance(request.get("url"), str) or not request["url"].strip():
            raise HTTPException(status_code=422, detail="Request URL is required.")
        method = request.get("method", "GET")
        if not isinstance(method, str) or not method.strip() or not method.replace("-", "").isalnum():
            raise HTTPException(status_code=422, detail="Request method is invalid.")


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
    supplied_case = request.get("test_case")
    if supplied_case is not None:
        if not isinstance(supplied_case, dict) or supplied_case.get("id") != test_case_id:
            raise HTTPException(status_code=422, detail="Execution test case must match the saved test-case ID.")
        test_case = copy.deepcopy(supplied_case)
        _validate_editable_test_case(test_case)
        persist_execution = _execution_inputs_match(found[1], test_case)
    else:
        persist_execution = True

    # Detect flow test cases and execute sequentially with variable substitution
    if test_case.get("is_flow"):
        result = execute_flow_test_case(test_case, assertions=assertions)
    else:
        result = execute_test_case(test_case, assertions=assertions)
    if persist_execution:
        database.append_execution(owning_project_id, test_case_id, result)
    return result


def _execution_inputs_match(saved_case: dict, executed_case: dict) -> bool:
    """Check whether executed request inputs match the saved case inputs.

    The frontend normalizes assertion defaults and flow editor metadata in memory.
    These presentation changes should not prevent recording a result for an
    otherwise unchanged saved request. Unsaved endpoint or flow mapping edits
    still remain session-only and do not create misleading saved-case history.
    """
    def request_inputs(request_data: dict) -> dict:
        """Normalize request editor rows to the values actually sent over HTTP."""
        def enabled_values(values) -> dict:
            if isinstance(values, dict):
                return dict(values)
            if isinstance(values, list):
                return {
                    str(row.get("key")): row.get("value", "")
                    for row in values
                    if isinstance(row, dict) and row.get("key") and row.get("enabled", True)
                }
            return {}

        return {
            "method": str(request_data.get("method", "GET")).upper(),
            "url": request_data.get("url", ""),
            "headers": enabled_values(request_data.get("headers", {})),
            "query_params": enabled_values(request_data.get("query_params", {})),
            "body": request_data.get("body"),
        }

    is_flow = bool(saved_case.get("is_flow") or executed_case.get("is_flow"))
    if not is_flow:
        return request_inputs(saved_case.get("request") or {}) == request_inputs(
            executed_case.get("request") or {}
        )

    def flow_inputs(test_case: dict) -> list[dict]:
        inputs = []
        ordered_steps = sorted(
            test_case.get("steps", []),
            key=lambda step: step.get("step_order", 0) if isinstance(step, dict) else 0,
        )
        for index, step in enumerate(ordered_steps, start=1):
            if not isinstance(step, dict):
                return []
            mappings = step.get("variable_mappings", [])
            normalized_mappings = [
                {
                    "from": mapping.get("from", ""),
                    "to": mapping.get("to", ""),
                    "transform": mapping.get("transform") or None,
                }
                for mapping in mappings
                if isinstance(mapping, dict)
                and (mapping.get("from") or mapping.get("to"))
            ] if isinstance(mappings, list) else []
            inputs.append({
                "request": request_inputs(step.get("endpoint") or {}),
                "variable_mappings": [] if index == 1 else normalized_mappings,
            })
        return inputs

    saved_inputs = flow_inputs(saved_case)
    executed_inputs = flow_inputs(executed_case)
    return bool(saved_inputs) and saved_inputs == executed_inputs


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
