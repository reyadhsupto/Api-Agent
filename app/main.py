"""
FastAPI application entry point with SQLite-backed project storage.

Accepts:
    HTTP requests from the Streamlit frontend.

Returns:
    JSON responses for project, endpoint, test case, and execution management.
"""

import uuid
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.schemas import (
    CurlParseRequest,
    TestCaseGenerateRequest,
)
from app.parser import parse_curl
from app.generator import generate_test_cases, generate_flow_test_cases
from app.executor import execute_test_case, execute_flow_test_case
# Load environment variables from .env file
load_dotenv()
from app.storage import Database

database = Database()

def _generate_or_raise(generator, **kwargs) -> list:
    """Run an LLM generator and expose malformed output as a useful API error."""
    try:
        return generator(**kwargs)
    except ValueError as exc:
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


def _assign_test_case_ids(project_id: str, test_cases: list[dict]) -> None:
    """Ensure generated case IDs do not overwrite earlier generations."""
    seen = set()
    for test_case in test_cases:
        test_case_id = test_case.get("id")
        if not test_case_id or test_case_id in seen or database.find_test_case(test_case_id):
            test_case["id"] = str(uuid.uuid4())
        seen.add(test_case["id"])


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
    if not database.replace_endpoints(project_id, endpoints):
        raise HTTPException(status_code=404, detail="Project not found")
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
        parsed_curl=request.parsed_curl,
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
    project_id = request.project_id or database.current_project_id()
    _assign_test_case_ids(project_id, test_cases)
    if not database.save_test_cases(project_id, test_cases):
        raise HTTPException(status_code=404, detail="Project not found")
    return test_cases


@app.post("/api/v1/test-cases/generate-flow")
def generate_flow_test_cases_standalone(request: dict) -> list:
    """
    Generate flow test cases without a project (standalone mode).

    Args:
        request (dict): Contains 'endpoints' (list of endpoint dicts) and optional 'business_requirements'.

    Returns:
        list: Generated flow test cases.
    """
    endpoints = request.get("endpoints", [])
    business_requirements = request.get("business_requirements")
    project_id = request.get("project_id") or database.current_project_id()

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
    _assign_test_case_ids(project_id, test_cases)
    if not database.save_test_cases(project_id, test_cases):
        raise HTTPException(status_code=404, detail="Project not found")
    return test_cases


@app.post("/api/v1/projects/{project_id}/test-cases/generate-flow")
def generate_flow_test_cases_project(project_id: str, request: dict) -> list:
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
    endpoint_ids = request.get("endpoint_ids", [])
    endpoints_data = request.get("endpoints", [])
    business_requirements = request.get("business_requirements")

    # Use full endpoint data if provided, otherwise look up from project
    if endpoints_data:
        ordered = endpoints_data
    else:
        endpoints = [ep for ep in project["endpoints"] if ep["id"] in endpoint_ids]
        ordered = []
        for eid in endpoint_ids:
            ep = next((e for e in endpoints if e["id"] == eid), None)
            if ep:
                ordered.append(ep)

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
