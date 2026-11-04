"""
Minimal Pydantic schemas for API validation.

Accepts:
    None.

Returns:
    Pydantic model classes.
"""

from pydantic import BaseModel
from typing import Literal, Optional


class CurlParseRequest(BaseModel):
    curl: str


class TestCaseGenerateRequest(BaseModel):
    parsed_curl: dict
    business_requirements: Optional[str] = None


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