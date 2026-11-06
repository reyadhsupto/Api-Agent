"""
Minimal Pydantic schemas for API validation.

Accepts:
    None.

Returns:
    Pydantic model classes.
"""

from pydantic import BaseModel, Field
from typing import Any, Literal, Optional


class CurlParseRequest(BaseModel):
    curl: str


class TestCaseGenerateRequest(BaseModel):
    parsed_curl: dict
    business_requirements: Optional[str] = None
    project_id: Optional[str] = None


class FlowGenerateRequest(BaseModel):
    endpoints: list[dict] = Field(default_factory=list)
    endpoint_ids: list[str] = Field(default_factory=list)
    business_requirements: Optional[str] = None
    project_id: Optional[str] = None
    # Accepted for older clients; flow generation now lets the model determine output size.
    scenario_count: Optional[int] = None


class ApiRequest(BaseModel):
    method: str = "GET"
    url: str
    headers: dict[str, str] = Field(default_factory=dict)
    query_params: dict[str, Any] = Field(default_factory=dict)
    body: Optional[str | dict | list] = None
    timeout_seconds: int = Field(default=60, ge=1, le=120)


class HttpAssertionExecutionRequest(BaseModel):
    """One temporary HTTP request and the assertions to evaluate on its response."""

    request: ApiRequest
    assertions: list[dict] = Field(default_factory=list)


class TestCase(BaseModel):
    id: str
    type: Literal["positive", "negative", "edge", "race"]
    name: str
    description: str
    request: dict
    expected_status: Optional[int] = None
    expected_body_contains: Optional[str] = None


class ExecutionRequest(BaseModel):
    test_case_id: str
    base_url: str = ""


class ExecutionResult(BaseModel):
    test_case_id: str
    status: Literal["passed", "failed", "error"]
    request_url: str
    request_method: str
    request_headers: dict
    request_body: Optional[dict | str]
    response_status: Optional[int]
    response_headers: dict
    response_body: Optional[str]
    latency_ms: float
    assertion_detail: str
