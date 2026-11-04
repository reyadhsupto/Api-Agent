"""
FastAPI application entry point with routes and in-memory storage.

Accepts:
    HTTP requests from the Streamlit frontend.

Returns:
    JSON responses for curl parsing, test case generation, and execution.
"""

import uuid
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.schemas import (
    CurlParseRequest,
    TestCaseGenerateRequest,
    TestCase,
)
from app.parser import parse_curl
from app.generator import generate_test_cases
from app.executor import execute_test_case

# Load environment variables from .env file
load_dotenv()

# In-memory storage (module-level, cleared on server restart)
_memory = {
    "parsed_curl": None,
    "test_cases": [],
    "executions": [],
}

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
    _memory["parsed_curl"] = parsed
    return parsed


@app.post("/api/v1/test-cases/generate")
def generate_test_cases_endpoint(request: TestCaseGenerateRequest) -> list:
    """
    Generate AI-powered test cases from a parsed cURL.

    Args:
        request (TestCaseGenerateRequest): Parsed cURL and optional requirements.

    Returns:
        list: Generated test cases.
    """
    test_cases = generate_test_cases(
        parsed_curl=request.parsed_curl,
        business_requirements=request.business_requirements,
    )
    for tc in test_cases:
        if not tc.get("id"):
            tc["id"] = str(uuid.uuid4())
    _memory["test_cases"] = test_cases
    return test_cases


@app.post("/api/v1/test-cases/execute")
def execute_test_case_endpoint(request: dict) -> dict:
    """
    Execute a single test case and capture full request/response details.

    Args:
        request (dict): Contains test_case_id and optional base_url.

    Returns:
        dict: Execution result with assertion detail.

    Raises:
        HTTPException: If test case ID is not found.
    """
    test_case_id = request.get("test_case_id")
    base_url = request.get("base_url", "")
    assertions = request.get("assertions", {})

    if not test_case_id:
        raise HTTPException(status_code=400, detail="test_case_id is required")

    test_case = next(
        (tc for tc in _memory["test_cases"] if tc.get("id") == test_case_id),
        None,
    )
    if not test_case:
        raise HTTPException(status_code=404, detail="Test case not found")

    result = execute_test_case(test_case, base_url=base_url, assertions=assertions)
    _memory["executions"].append(result)
    return result


@app.get("/api/v1/memory/state")
def memory_state() -> dict:
    """
    Return current in-memory state for UI hydration.

    Returns:
        dict: parsed_curl, test_cases, executions.
    """
    return _memory