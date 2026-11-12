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
    parsed_curl: Optional[dict] = None
    endpoints: list[dict] = Field(default_factory=list)
    business_requirements: Optional[str] = None
    project_id: Optional[str] = None
    source_endpoint_id: Optional[str] = None
    example_test_case_ids: list[str] = Field(default_factory=list)
    mode: Literal["Single", "General"] = "Single"
    case_collection_id: Optional[str] = None
    case_collection_name: Optional[str] = None
    project_chat_thread_id: Optional[str] = None
    project_chat_brief: Optional[str] = None
    project_brief_scope_ids: list[str] = Field(default_factory=list)


class GenerationFollowUpRequest(BaseModel):
    """Answers to clarification questions from a prior generation activity."""

    source_activity_id: str
    answers: dict[str, str] = Field(default_factory=dict)


class ManualTestResultRequest(BaseModel):
    """A tester-recorded outcome for a requirements-only general case."""

    status: Literal["passed", "failed"]
    note: str = ""


class ProjectChatThreadRequest(BaseModel):
    """Create or edit a project chat thread."""

    title: str = "New project chat"
    model: Optional[str] = None
    feature_brief: Optional[str] = None
    context_summary: Optional[str] = None
    archived: Optional[bool] = None


class ProjectChatMessageRequest(BaseModel):
    """A user message to send in a persistent project chat."""

    content: str


class ProjectBriefScopeRequest(BaseModel):
    """Create a named project overview, feature, or microservice brief scope."""

    scope_type: Literal["project", "feature", "microservice"]
    name: str


class ProjectBriefVersionRequest(BaseModel):
    """Save an explicitly reviewed immutable version of a project brief."""

    content: str
    source_thread_id: Optional[str] = None


class ProjectBriefDraftRequest(BaseModel):
    """Request an unsaved brief draft from a project chat transcript."""

    scope_id: Optional[str] = None
    create_scope_type: Optional[Literal["feature", "microservice"]] = None
    create_scope_name: Optional[str] = None


class ProjectKnowledgeEntryRequest(BaseModel):
    """Create or update a project-scoped knowledge entry."""

    id: Optional[str] = None
    title: str
    category: str = "Product knowledge"
    content: str
    source_name: str = "User authored"
    approved: bool = True
    retired: bool = False


class FlowGenerateRequest(BaseModel):
    endpoints: list[dict] = Field(default_factory=list)
    endpoint_ids: list[str] = Field(default_factory=list)
    business_requirements: Optional[str] = None
    project_id: Optional[str] = None
    example_test_case_ids: list[str] = Field(default_factory=list)
    # Accepted for older clients; flow generation now lets the model determine output size.
    scenario_count: Optional[int] = None
    project_chat_thread_id: Optional[str] = None
    project_chat_brief: Optional[str] = None
    project_brief_scope_ids: list[str] = Field(default_factory=list)


class TestCaseRevisionRequest(BaseModel):
    """Inputs for generating a complete new release revision from saved cases."""

    source_activity_id: str
    baseline_case_ids: list[str] = Field(default_factory=list)
    release_label: str
    release_notes: str = ""
    endpoint_ids: list[str] = Field(default_factory=list)
    keep_unchanged_case_ids: list[str] = Field(default_factory=list)
    project_chat_thread_id: Optional[str] = None
    project_chat_brief: Optional[str] = None
    project_brief_scope_ids: list[str] = Field(default_factory=list)


class ContractPreviewRequest(BaseModel):
    """Source text or anonymous URL used to preview imported API requests.

    Attributes:
        source_type: Whether content is pasted/uploaded text or a public URL.
        content: Source document, prose, or URL.
        source_name: Friendly source label shown in review.
        format_hint: Optional parser selection; auto-detect by default.
        base_url: Optional override for relative operation URLs.
        source_id: Existing source ID used to retain identity on re-preview.
    """

    source_type: Literal["text", "url"]
    content: str
    source_name: str = ""
    format_hint: Literal["auto", "openapi", "postman", "text"] = "auto"
    base_url: str = ""
    source_id: Optional[str] = None


class ContractImportRequest(BaseModel):
    """Reviewed requests and destination collection for an atomic import.

    Attributes:
        collection_id: Project collection receiving the requests.
        endpoints: Reviewed endpoint records selected for persistence.
    """

    collection_id: str
    endpoints: list[dict] = Field(default_factory=list)


class FlowDiscoveryRequest(BaseModel):
    """Source contract identifier used to recalculate dependency candidates.

    Attributes:
        source_id: Stable identifier shared by imported contract requests.
    """

    source_id: str


class DiscoveredFlowGenerateRequest(BaseModel):
    """Selected dependency paths and optional business context for LLM generation.

    Attributes:
        source_id: Stable identifier shared by imported contract requests.
        candidate_ids: Ranked dependency paths selected by the user.
        business_requirements: Optional domain context for scenario generation.
    """

    source_id: str
    candidate_ids: list[str] = Field(default_factory=list)
    business_requirements: Optional[str] = None
    project_brief_scope_ids: list[str] = Field(default_factory=list)
    project_chat_thread_id: Optional[str] = None


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
