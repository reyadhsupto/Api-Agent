"""
FastAPI application entry point with PostgreSQL-backed project storage.

Accepts:
    HTTP requests from the Streamlit frontend.

Returns:
    JSON responses for project, endpoint, test case, and execution management.
"""

import json
import csv
import copy
import io
import time
import uuid
import requests
from urllib.parse import parse_qsl, urlencode, urlsplit
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
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
    TestCaseRevisionRequest,
    GenerationFollowUpRequest,
    ManualTestResultRequest,
)
from app.parser import parse_curl
from app.generator import (
    generate_test_cases, generate_flow_test_cases, generate_discovered_flow_test_cases,
    generate_test_case_revision, generate_general_test_cases, refine_generated_cases,
)
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

GENERAL_CASE_COLLECTION_ID = "__general_scenarios__"
GENERAL_CASE_COLLECTION_NAME = "General scenarios"

def _generate_or_raise(generator, **kwargs):
    """Run an LLM generator and expose malformed output as a useful API error."""
    try:
        return generator(**kwargs)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(
            status_code=502,
            detail=f"LLM returned invalid test-case data: {exc}",
        ) from exc


def _project_endpoint_snapshot(project: dict | None) -> list[dict]:
    """Capture comparable request definitions and collection placement for a project."""
    collections_by_id = {
        str(item.get("id")): item
        for item in (project or {}).get("collections", []) if item.get("id")
    }
    snapshot = []
    for item in (project or {}).get("endpoints", []):
        collection_id = item.get("collection_id")
        collection = collections_by_id.get(str(collection_id))
        snapshot.append({
            "id": str(item.get("id", "")),
            "name": item.get("name", ""),
            "method": str(item.get("method", "GET")).upper(),
            "url": item.get("url", ""),
            "headers": _enabled_values(item.get("headers", {})),
            "query_params": _enabled_values(item.get("query_params", {})),
            "body": None if item.get("include_body") is False else copy.deepcopy(item.get("body")),
            "collection_id": str(collection_id) if collection_id else None,
            "collection_name": collection.get("name", "Unassigned collection") if collection else "Unassigned collection",
        })
    return snapshot


def _drop_unsupported_revision_mappings(test_case: dict) -> list[str]:
    """Remove revision mappings that the flow editor and executor cannot apply.

    Args:
        test_case (dict): Generated test case, possibly a flow.

    Returns:
        list[str]: Human-readable warnings for removed mapping destinations.
    """
    if not (test_case.get("is_flow") or isinstance(test_case.get("steps"), list)):
        return []
    warnings = []
    for step_index, step in enumerate(test_case.get("steps", []), start=1):
        if not isinstance(step, dict):
            continue
        mappings = step.get("variable_mappings", [])
        if not isinstance(mappings, list):
            continue
        retained = []
        for mapping in mappings:
            if not isinstance(mapping, dict):
                retained.append(mapping)
                continue
            target = mapping.get("to")
            if not isinstance(target, str):
                retained.append(mapping)
                continue
            supported = (
                target.startswith("headers.") and len(target) > len("headers.")
                or target.startswith("request.query.") and len(target) > len("request.query.")
                or target.startswith("request.path.") and len(target) > len("request.path.")
                or target == "request.body"
                or target.startswith("request.body.") and len(target) > len("request.body.")
            )
            if supported:
                retained.append(mapping)
            else:
                warnings.append(f"Flow step {step_index}: omitted unsupported mapping destination `{target}`.")
        step["variable_mappings"] = retained
    return warnings


def _record_generation_activity(
    project_id: str,
    mode: str,
    endpoints: list[dict],
    business_requirements: str | None,
    trace: dict,
    status: str,
    test_cases: list[dict] | None = None,
    error: str | None = None,
) -> dict | None:
    """Persist the generation input, outcome, and a comparable project snapshot."""
    endpoint_snapshot = _project_endpoint_snapshot(database.get_project(project_id))
    record = getattr(database, "record_generation_activity", None)
    if not callable(record):
        return None
    return record(project_id, {
        "mode": mode,
        "business_requirements": business_requirements or "",
        "endpoints": [{
            "id": item.get("id"), "name": item.get("name", ""),
            "method": item.get("method", "GET"), "url": item.get("url", ""),
        } for item in endpoints],
        "endpoint_snapshot": endpoint_snapshot,
        "prompt": trace.get("prompt", ""),
        "llm_response": trace.get("llm_response", ""),
        "clarification_questions": trace.get("clarification_questions", []),
        "status": status,
        "error": error or "",
        "generated_case_ids": [str(item.get("id")) for item in (test_cases or []) if item.get("id")],
    })


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
    superseded = [case_id for case_id in dict.fromkeys(example_ids)
                  if cases_by_id[case_id].get("superseded_by_activity_id")]
    if superseded:
        raise HTTPException(
            status_code=422,
            detail=f"Superseded test case(s) cannot be used as examples: {', '.join(superseded)}",
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
    """Replace model-provided IDs with unique UUIDs for newly generated cases."""
    seen = set()
    for test_case in test_cases:
        while True:
            test_case_id = str(uuid.uuid4())
            if test_case_id not in seen and database.find_test_case(test_case_id) is None:
                break
        test_case["id"] = test_case_id
        seen.add(test_case_id)


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


def _attach_generation_requirements(
    test_cases: list[dict], business_requirements: str | None,
) -> None:
    """Store the generation action's requirement text on every resulting case."""
    requirements = business_requirements or ""
    for test_case in test_cases:
        test_case["business_requirements"] = requirements


def _merge_revision_requirements(
    previous_requirements: str, previous_release_notes: str, new_requirement_changes: str,
) -> str:
    """Build the cumulative requirements saved on cases produced by a revision."""
    combined = previous_requirements.strip()
    prior_notes = previous_release_notes.strip()
    new_changes = new_requirement_changes.strip()
    if prior_notes and prior_notes.casefold() not in combined.casefold():
        section = f"Release changes from the previous revision:\n{prior_notes}"
        combined = f"{combined}\n\n{section}" if combined else section
    if new_changes:
        section = f"Release requirement changes:\n{new_changes}"
        combined = f"{combined}\n\n{section}" if combined else section
    return combined


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


@app.get("/api/v1/projects/{project_id}/generation-activity")
def get_generation_activity(project_id: str, limit: int = 100, offset: int = 0) -> dict:
    """List recent generation actions for a project with pagination.

    Args:
        project_id (str): The project ID.
        limit (int): Maximum number of records to return (default 100).
        offset (int): Number of records to skip (default 0).

    Returns:
        dict: {"activities": list, "total": int, "limit": int, "offset": int}
    """
    all_records = database.list_generation_activity(project_id, limit, offset)
    if all_records is None:
        raise HTTPException(status_code=404, detail="Project not found")
    total_records = len(all_records)
    return {
        "activities": all_records,
        "total": total_records,
        "limit": limit,
        "offset": offset,
    }


@app.post("/api/v1/projects/{project_id}/test-case-revisions")
def create_test_case_revision(project_id: str, request: TestCaseRevisionRequest) -> dict:
    """Generate and persist a complete new release suite without changing its baseline."""
    project = database.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    source = database.get_generation_activity(project_id, request.source_activity_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source generation action not found in this project")
    if source.get("status") != "succeeded" or source.get("business_requirements") is None:
        raise HTTPException(status_code=422, detail="Choose a successful generation action with saved requirements.")
    cases_by_id = {str(item.get("id")): item for item in project.get("test_cases", [])}
    baseline_ids = list(dict.fromkeys(request.baseline_case_ids))
    if not baseline_ids:
        raise HTTPException(status_code=422, detail="Select at least one baseline test case.")
    if any(case_id not in cases_by_id for case_id in baseline_ids):
        raise HTTPException(status_code=404, detail="One or more baseline cases do not belong to this project.")
    keep_unchanged_ids = list(dict.fromkeys(request.keep_unchanged_case_ids))
    if any(case_id not in baseline_ids for case_id in keep_unchanged_ids):
        raise HTTPException(status_code=422, detail="Keep-unchanged cases must be part of the selected baseline.")
    if any(cases_by_id[case_id].get("superseded_by_activity_id") for case_id in baseline_ids):
        raise HTTPException(status_code=422, detail="Superseded cases cannot be included in a new revision.")
    endpoints_by_id = {str(item.get("id")): item for item in project.get("endpoints", [])}
    endpoint_ids = list(dict.fromkeys(request.endpoint_ids))
    if any(endpoint_id not in endpoints_by_id for endpoint_id in endpoint_ids):
        raise HTTPException(status_code=404, detail="One or more endpoints do not belong to this project.")

    baseline = [cases_by_id[case_id] for case_id in baseline_ids]
    general_baseline_collections = {
        (str(item.get("case_collection_id") or GENERAL_CASE_COLLECTION_ID),
         str(item.get("case_collection_name") or GENERAL_CASE_COLLECTION_NAME))
        for item in baseline if item.get("case_kind") == "general"
    }
    default_general_collection = (
        next(iter(general_baseline_collections)) if len(general_baseline_collections) == 1
        else (GENERAL_CASE_COLLECTION_ID, GENERAL_CASE_COLLECTION_NAME)
    )
    baseline_endpoints = {}
    for baseline_case in baseline:
        for step in baseline_case.get("steps", []) if isinstance(baseline_case.get("steps"), list) else []:
            if not isinstance(step, dict) or not isinstance(step.get("endpoint"), dict):
                continue
            old_endpoint = step["endpoint"]
            old_id = step.get("endpoint_id", old_endpoint.get("id"))
            if old_id is not None:
                baseline_endpoints[str(old_id)] = old_endpoint
        source_endpoint_id = baseline_case.get("source_endpoint_id")
        request_data = baseline_case.get("request")
        if source_endpoint_id and isinstance(request_data, dict):
            baseline_endpoints.setdefault(str(source_endpoint_id), {
                **copy.deepcopy(request_data),
                "id": str(source_endpoint_id),
                "name": baseline_case.get("source_endpoint_name", ""),
            })
    effective_endpoints_by_id = {
        endpoint_id: _effective_request(endpoints_by_id[endpoint_id])
        for endpoint_id in endpoint_ids
    }
    endpoints = [effective_endpoints_by_id[endpoint_id] for endpoint_id in endpoint_ids]
    endpoint_snapshot = _project_endpoint_snapshot(project)
    previous_requirements = str(source.get("business_requirements") or "")
    previous_release_notes = str(source.get("release_notes") or "")
    cumulative_requirements = _merge_revision_requirements(
        previous_requirements, previous_release_notes, request.release_notes,
    )
    keep_unchanged_set = set(keep_unchanged_ids)
    revision_baseline = [item for item in baseline if str(item.get("id")) not in keep_unchanged_set]
    trace = {}
    try:
        if revision_baseline or endpoints or request.release_notes.strip():
            revised = generate_test_case_revision(
                revision_baseline, endpoints, previous_requirements, request.release_notes, trace,
                prior_release_notes=previous_release_notes,
            )
        else:
            revised = []
        expected_sources = {str(item.get("id")) for item in revision_baseline}
        represented = [str(item.get("source_case_id")) for item in revised if item.get("source_case_id")]
        if set(represented) != expected_sources or len(represented) != len(expected_sources):
            raise ValueError("The returned suite must contain each AI-revised baseline source_case_id exactly once.")
        if any(source_id not in expected_sources for source_id in represented):
            raise ValueError("The model returned a source_case_id outside the AI-revised baseline.")
        revision_id = str(uuid.uuid4())
        generated = []
        normalization_warnings = []
        revised_by_source = {
            str(item["source_case_id"]): item for item in revised if item.get("source_case_id")
        }
        new_cases = []
        kept_cases = []
        for source_case_id in keep_unchanged_ids:
            kept = copy.deepcopy(cases_by_id[source_case_id])
            kept.update({
                "id": str(uuid.uuid4()), "revision_id": revision_id,
                "source_case_id": source_case_id,
            })
            kept_cases.append(kept)
        for case in revised:
            item = copy.deepcopy(case)
            normalization_warnings.extend(_drop_unsupported_revision_mappings(item))
            source_case_id = item.get("source_case_id")
            if source_case_id is not None and str(source_case_id) not in expected_sources:
                raise ValueError(f"Unknown source_case_id: {source_case_id}")
            item.update({
                "id": str(uuid.uuid4()), "revision_id": revision_id,
                "source_case_id": str(source_case_id) if source_case_id is not None else None,
                "business_requirements": cumulative_requirements,
                "release_notes": request.release_notes,
            })
            if item.get("case_kind") == "general":
                source_case = cases_by_id.get(str(source_case_id)) if source_case_id else None
                item["case_collection_id"] = (
                    (source_case or {}).get("case_collection_id") or default_general_collection[0]
                )
                item["case_collection_name"] = (
                    (source_case or {}).get("case_collection_name") or default_general_collection[1]
                )
            if item.get("is_flow") or isinstance(item.get("steps"), list):
                item["is_flow"] = True
                for step_index, step in enumerate(item["steps"], start=1):
                    endpoint_id = str(step.get("endpoint_id", ""))
                    if endpoint_id in endpoint_ids:
                        step["endpoint"] = copy.deepcopy(effective_endpoints_by_id[endpoint_id])
                    elif endpoint_id in baseline_endpoints:
                        step["endpoint"] = copy.deepcopy(baseline_endpoints[endpoint_id])
                    else:
                        raise ValueError(f"Flow step {step_index} must reference a selected current or baseline endpoint.")
                    step["step_id"] = str(uuid.uuid4())
                    step["step_order"] = step_index
            _validate_editable_test_case(item)
            if item.get("source_case_id"):
                revised_by_source[str(item["source_case_id"])] = item
            else:
                new_cases.append(item)
        for baseline_case in baseline:
            source_case_id = str(baseline_case.get("id"))
            if source_case_id in keep_unchanged_set:
                generated.append(next(item for item in kept_cases if item["source_case_id"] == source_case_id))
            else:
                generated.append(revised_by_source[source_case_id])
        generated.extend(new_cases)
        new_case_ids = [str(item["id"]) for item in new_cases]

        revision = database.save_test_case_revision(project_id, {
            "id": revision_id, "label": request.release_label.strip() or "Release revision",
            "source_activity_id": request.source_activity_id,
            "previous_requirements": previous_requirements,
            "previous_release_notes": previous_release_notes,
            "release_notes": request.release_notes,
            "endpoint_snapshot": endpoint_snapshot,
        }, generated)
        if revision is None:
            raise HTTPException(status_code=404, detail="Project not found")
        activity = database.record_generation_activity(project_id, {
            "mode": "Release revision", "business_requirements": cumulative_requirements,
            "previous_requirements": previous_requirements,
            "previous_release_notes": previous_release_notes, "release_notes": request.release_notes,
            "endpoints": [{"id": e.get("id"), "name": e.get("name", ""), "method": e.get("method", "GET"), "url": e.get("url", "")} for e in endpoints],
            "endpoint_snapshot": endpoint_snapshot,
            "prompt": trace.get("prompt", ""), "llm_response": trace.get("llm_response", ""),
            "status": "succeeded", "error": "", "generated_case_ids": [item["id"] for item in generated],
            "revision_id": revision_id, "revision_label": revision["label"],
            "source_activity_id": request.source_activity_id, "source_case_ids": baseline_ids,
            "kept_unchanged_case_ids": [item["id"] for item in kept_cases],
            "kept_unchanged_source_case_ids": keep_unchanged_ids,
            "revised_source_case_ids": [item for item in baseline_ids if item not in keep_unchanged_set],
            "new_case_ids": new_case_ids,
            "warnings": normalization_warnings,
            "clarification_questions": trace.get("clarification_questions", []),
        })
        return {
            "revision": revision, "test_cases": generated, "activity": activity,
            "warnings": normalization_warnings,
            "clarification_questions": trace.get("clarification_questions", []),
        }
    except HTTPException:
        raise
    except Exception as exc:
        database.record_generation_activity(project_id, {
            "mode": "Release revision", "business_requirements": cumulative_requirements,
            "previous_requirements": previous_requirements,
            "previous_release_notes": previous_release_notes, "release_notes": request.release_notes,
            "endpoints": [{"id": e.get("id"), "name": e.get("name", ""), "method": e.get("method", "GET"), "url": e.get("url", "")} for e in endpoints],
            "endpoint_snapshot": endpoint_snapshot,
            "prompt": trace.get("prompt", ""), "llm_response": trace.get("llm_response", ""),
            "status": "failed", "error": str(exc), "generated_case_ids": [],
            "source_activity_id": request.source_activity_id,
        })
        raise HTTPException(status_code=502, detail=f"Could not generate complete release suite: {exc}") from exc


@app.post("/api/v1/projects/{project_id}/generation-activity/follow-up")
def follow_up_generation(project_id: str, request: GenerationFollowUpRequest) -> dict:
    """Create linked refined cases and supersede prior output only after success."""
    project = database.get_project(project_id)
    source = database.get_generation_activity(project_id, request.source_activity_id)
    if not project or not source:
        raise HTTPException(status_code=404, detail="Project or source generation activity not found")
    if source.get("status") != "succeeded":
        raise HTTPException(status_code=422, detail="Only successful generation actions can be refined.")
    case_by_id = {str(item.get("id")): item for item in project.get("test_cases", [])}
    source_cases = [case_by_id[item_id] for item_id in source.get("generated_case_ids", []) if item_id in case_by_id]
    if not source_cases:
        raise HTTPException(status_code=422, detail="The source action has no remaining saved cases to refine.")
    is_revision_follow_up = source.get("mode") == "Release revision"
    if not is_revision_follow_up and any(item.get("superseded_by_activity_id") for item in source_cases):
        raise HTTPException(status_code=422, detail="This generation output was already refined.")
    protected_ids = {str(item) for item in source.get("kept_unchanged_case_ids", [])} if is_revision_follow_up else set()
    source_cases_to_refine = [item for item in source_cases if str(item.get("id")) not in protected_ids]
    answers = {str(key): str(value).strip() for key, value in request.answers.items() if str(value).strip()}
    if not answers:
        raise HTTPException(status_code=422, detail="Provide at least one clarification answer.")
    source_general_collections = {
        (str(item.get("case_collection_id") or GENERAL_CASE_COLLECTION_ID),
         str(item.get("case_collection_name") or GENERAL_CASE_COLLECTION_NAME))
        for item in source_cases if item.get("case_kind") == "general"
    }
    default_general_collection = (
        next(iter(source_general_collections)) if len(source_general_collections) == 1
        else (GENERAL_CASE_COLLECTION_ID, GENERAL_CASE_COLLECTION_NAME)
    )
    trace = {}
    try:
        refined_output = (
            refine_generated_cases(source_cases_to_refine, answers, trace)
            if source_cases_to_refine else []
        )
        source_cases_by_id = {str(item.get("id")): item for item in source_cases_to_refine}
        represented_sources = []
        refined_by_source = {}
        new_cases = []
        for index, case in enumerate(refined_output):
            if not isinstance(case, dict):
                raise ValueError(f"Refined test case {index + 1} must be an object.")
            raw_source_ref = case.get("source_case_id")
            source_ref = str(raw_source_ref or case.get("id") or "")
            original = source_cases_by_id.get(source_ref) if raw_source_ref or source_ref else None
            if original:
                case["source_case_id"] = original.get("id")
                represented_sources.append(str(original.get("id")))
            elif raw_source_ref:
                raise ValueError(f"Refined output references an unknown source case: {raw_source_ref}")
            case["id"] = str(uuid.uuid4())
            case["follow_up_of"] = request.source_activity_id
            if source.get("business_requirements"):
                case.setdefault("business_requirements", source["business_requirements"])
            if (
                (original and original.get("case_kind") == "general")
                or case.get("case_kind") == "general"
                or isinstance(case.get("manual_steps"), list)
            ):
                case["case_kind"] = "general"
                case["case_collection_id"] = (
                    (original or {}).get("case_collection_id") or default_general_collection[0]
                )
                case["case_collection_name"] = (
                    (original or {}).get("case_collection_name") or default_general_collection[1]
                )
                case["manual_steps"] = (
                    case.get("manual_steps") or case.get("steps")
                    or (original or {}).get("manual_steps", [])
                )
                case.pop("steps", None)
                _validate_editable_test_case(case)
            else:
                if case.get("is_flow") or isinstance(case.get("steps"), list):
                    case["is_flow"] = True
                    for step_index, step in enumerate(case.get("steps", []), start=1):
                        step["step_id"] = str(uuid.uuid4())
                        step["step_order"] = step_index
                _validate_editable_test_case(case)
            if original:
                refined_by_source[str(original.get("id"))] = case
            else:
                new_cases.append(case)
        if (
            len(represented_sources) != len(source_cases_to_refine)
            or len(set(represented_sources)) != len(source_cases_to_refine)
            or set(represented_sources) != set(source_cases_by_id)
        ):
            raise ValueError("The refined output must retain each unlocked source case once and may add new cases.")
        refined = []
        revision_id = str(uuid.uuid4()) if is_revision_follow_up else None
        for original in source_cases:
            original_id = str(original.get("id"))
            if original_id in protected_ids:
                preserved = copy.deepcopy(original)
                preserved.update({
                    "id": str(uuid.uuid4()), "source_case_id": original_id,
                    "follow_up_of": request.source_activity_id,
                })
                if revision_id:
                    preserved["revision_id"] = revision_id
                refined.append(preserved)
            elif original_id in refined_by_source:
                refined.append(refined_by_source[original_id])
        refined.extend(new_cases)
        _assign_test_case_ids(project_id, refined)
        revision = None
        if source.get("mode") == "Release revision":
            for case in refined:
                case["revision_id"] = revision_id
            revision = database.save_test_case_revision(project_id, {
                "id": revision_id,
                "label": f"{source.get('revision_label') or 'Revision'} clarification",
                "source_activity_id": request.source_activity_id,
                "previous_requirements": source.get("previous_requirements", ""),
                "previous_release_notes": source.get("previous_release_notes", ""),
                "release_notes": source.get("release_notes", ""),
                "endpoint_snapshot": _project_endpoint_snapshot(project),
            }, refined)
        activity_payload = {
            "mode": source.get("mode", "Generation"),
            "business_requirements": source.get("business_requirements", ""),
            "previous_requirements": source.get("previous_requirements", ""),
            "previous_release_notes": source.get("previous_release_notes", ""),
            "release_notes": source.get("release_notes", ""),
            "endpoints": source.get("endpoints", []),
            "endpoint_snapshot": _project_endpoint_snapshot(project),
            "prompt": trace.get("prompt", ""), "llm_response": trace.get("llm_response", ""),
            "status": "succeeded", "error": "",
            "generated_case_ids": [case["id"] for case in refined],
            "clarification_questions": trace.get("clarification_questions", []),
            "questions_answered": source.get("clarification_questions", []),
            "clarification_answers": answers,
            "follow_up_of": request.source_activity_id,
            "revision_id": revision_id,
            "revision_label": revision.get("label") if revision else source.get("revision_label"),
            "supersedes_activity_id": None if is_revision_follow_up else request.source_activity_id,
            "archived_case_ids": [] if is_revision_follow_up else [str(item["id"]) for item in source_cases],
            "archived_case_summaries": [] if is_revision_follow_up else [{
                "id": str(item.get("id")), "name": item.get("name", "Untitled case"),
                "type": item.get("type", "test"), "description": item.get("description", ""),
                "is_flow": bool(item.get("is_flow") or isinstance(item.get("steps"), list)),
                "case_kind": item.get("case_kind", "api"),
            } for item in source_cases],
            "kept_unchanged_case_ids": [
                str(item["id"]) for item in refined if str(item.get("source_case_id")) in protected_ids
            ],
            "kept_unchanged_source_case_ids": [
                str(item["id"]) for item in source_cases if str(item.get("id")) in protected_ids
            ],
            "revised_source_case_ids": [str(item["id"]) for item in source_cases_to_refine],
        }
        if is_revision_follow_up:
            activity = database.record_generation_activity(project_id, activity_payload)
        else:
            activity = database.save_follow_up_generation(
                project_id, refined, activity_payload,
                [str(item["id"]) for item in source_cases],
            )
            if activity is None:
                raise HTTPException(status_code=404, detail="Project not found")
        return {
            "test_cases": refined,
            "clarification_questions": trace.get("clarification_questions", []),
            "activity": activity,
            "revision": revision,
            "archived_case_ids": activity_payload["archived_case_ids"],
        }
    except HTTPException:
        raise
    except Exception as exc:
        database.record_generation_activity(project_id, {
            "mode": source.get("mode", "Generation"), "status": "failed", "error": str(exc),
            "follow_up_of": request.source_activity_id,
            "questions_answered": source.get("clarification_questions", []),
            "clarification_answers": answers, "prompt": trace.get("prompt", ""),
            "llm_response": trace.get("llm_response", ""), "generated_case_ids": [],
        })
        raise HTTPException(status_code=502, detail=f"Could not refine generated cases: {exc}") from exc


@app.get("/api/v1/projects/{project_id}/test-cases/{test_case_id}/history")
def get_test_case_history(project_id: str, test_case_id: str, limit: int = 100) -> dict:
    """Return project-scoped execution history for one saved test case."""
    found = database.find_test_case(test_case_id, project_id)
    if not found:
        if database.get_project(project_id) is None:
            raise HTTPException(status_code=404, detail="Project not found")
        raise HTTPException(status_code=404, detail="Test case not found")
    return {
        "test_case_id": test_case_id,
        "executions": database.list_test_case_executions(project_id, test_case_id, limit) or [],
    }


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
def generate_contract_flows(project_id: str, request: DiscoveredFlowGenerateRequest) -> dict:
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
    trace = {}
    try:
        test_cases = generate_discovered_flow_test_cases(
            endpoints=endpoints,
            candidates=candidates,
            business_requirements=request.business_requirements,
            trace=trace,
        )
    except (ValueError, RuntimeError) as exc:
        _record_generation_activity(
            project_id, "Discovered Flow", endpoints, request.business_requirements,
            trace, "failed", error=str(exc),
        )
        raise HTTPException(status_code=502, detail=f"LLM returned invalid flow data: {exc}") from exc
    if not isinstance(test_cases, list) or not test_cases:
        raise HTTPException(status_code=502, detail="LLM returned no usable flow scenarios.")
    _attach_generation_requirements(test_cases, request.business_requirements)
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
    activity = _record_generation_activity(
        project_id, "Discovered Flow", endpoints, request.business_requirements,
        trace, "succeeded", test_cases=test_cases,
    )
    return {"test_cases": test_cases, "clarification_questions": trace.get("clarification_questions", []), "activity": activity}


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
def generate_test_cases_endpoint(request: TestCaseGenerateRequest) -> dict:
    """
    Generate test cases for one or more request definitions in one LLM action.

    Args:
        request (TestCaseGenerateRequest): One legacy request or a request batch.

    Returns:
        list: Generated test cases.
    """
    project_id = request.project_id or database.current_project_id()
    if request.mode == "General":
        requirements = (request.business_requirements or "").strip()
        if not requirements:
            raise HTTPException(status_code=422, detail="Business requirements are required for general scenarios.")
        project = database.get_project(project_id) if project_id else None
        if project_id and project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        trace = {}
        try:
            test_cases = _generate_or_raise(
                generate_general_test_cases, business_requirements=requirements, trace=trace,
            )
        except HTTPException as exc:
            activity = _record_generation_activity(
                project_id, "General", [], requirements, trace, "failed", error=str(exc.detail),
            ) if project_id else None
            raise
        _attach_generation_requirements(test_cases, requirements)
        collection_id = str(request.case_collection_id or GENERAL_CASE_COLLECTION_ID)
        collection_name = str(request.case_collection_name or "").strip() or GENERAL_CASE_COLLECTION_NAME
        for case in test_cases:
            case["case_kind"] = "general"
            case["case_collection_id"] = collection_id
            case["case_collection_name"] = collection_name
            case["id"] = str(uuid.uuid4())
            case["manual_steps"] = [str(step) for step in case["manual_steps"]]
        _assign_test_case_ids(project_id, test_cases)
        if project_id and not database.save_test_cases(project_id, test_cases):
            raise HTTPException(status_code=404, detail="Project not found")
        activity = _record_generation_activity(
            project_id, "General", [], requirements, trace, "succeeded", test_cases=test_cases,
        ) if project_id else None
        return {"test_cases": test_cases, "clarification_questions": trace.get("clarification_questions", []), "activity": activity}

    supplied_endpoints = request.endpoints or (
        [request.parsed_curl] if request.parsed_curl is not None else []
    )
    if not supplied_endpoints:
        raise HTTPException(status_code=400, detail="Provide at least one endpoint to generate tests.")
    if request.endpoints and len(supplied_endpoints) > 1 and any(not item.get("id") for item in supplied_endpoints):
        raise HTTPException(status_code=422, detail="Each endpoint in a batch must include its saved endpoint ID.")

    should_load_project = bool(
        request.project_id or request.source_endpoint_id or request.example_test_case_ids
        or any(item.get("id") for item in supplied_endpoints)
    )
    project = database.get_project(project_id) if project_id and should_load_project else None
    if request.project_id and project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    saved_endpoints_by_id = {
        str(item.get("id")): item
        for item in (project or {}).get("endpoints", []) if item.get("id") is not None
    }
    endpoints = []
    for item in supplied_endpoints:
        source_id = item.get("id") or request.source_endpoint_id
        source_endpoint = saved_endpoints_by_id.get(str(source_id)) if source_id else None
        if source_id and project and source_endpoint is None:
            raise HTTPException(status_code=404, detail=f"Source endpoint {source_id} not found in project")
        endpoint = _effective_request(source_endpoint or item)
        if source_id:
            endpoint["id"] = str(source_id)
        endpoints.append(endpoint)

    examples = _load_generation_examples(project_id, request.example_test_case_ids, project)
    generation_args = {
        "business_requirements": request.business_requirements,
        "example_test_cases": examples,
    }
    trace = {}
    generation_args["trace"] = trace
    if request.endpoints:
        generation_args["endpoints"] = endpoints
    else:
        generation_args["parsed_curl"] = endpoints[0]
    try:
        test_cases = _generate_or_raise(generate_test_cases, **generation_args)
    except HTTPException as exc:
        _record_generation_activity(
            project_id, "Single", endpoints, request.business_requirements,
            trace, "failed", error=str(exc.detail),
        )
        raise
    _attach_generation_requirements(test_cases, request.business_requirements)

    endpoints_by_id = {
        str(item["id"]): item for item in endpoints if item.get("id") is not None
    }
    assigned_endpoint_ids = set()
    for tc in test_cases:
        source_id = str(tc.get("source_endpoint_id") or "")
        source_endpoint = endpoints_by_id.get(source_id)
        if source_endpoint is None and len(endpoints) == 1:
            source_endpoint = endpoints[0]
        if source_endpoint is None:
            request_data = tc.get("request") or {}
            matches = [
                item for item in endpoints
                if str(item.get("method", "GET")).upper() == str(request_data.get("method", "GET")).upper()
                and item.get("url") == request_data.get("url")
            ]
            if len(matches) == 1:
                source_endpoint = matches[0]
        if source_endpoint is None:
            raise HTTPException(
                status_code=502,
                detail="LLM cases must identify a selected source_endpoint_id for every endpoint.",
            )
        if source_endpoint.get("id") is not None:
            source_id = str(source_endpoint["id"])
            tc["source_endpoint_id"] = source_id
            tc["source_endpoint_name"] = (
                source_endpoint.get("name") or source_endpoint.get("url") or "Unnamed endpoint"
            )
            assigned_endpoint_ids.add(source_id)
        if not tc.get("id"):
            tc["id"] = str(uuid.uuid4())
        if "assertions" not in tc:
            tc["assertions"] = {
                "status": {"enabled": True, "expected_status": tc.get("expected_status", 200)},
                "body_contains": {"enabled": tc.get("expected_body_contains") is not None, "value": tc.get("expected_body_contains", "") or ""},
                "jsonpath": {"enabled": False, "path": "", "expected_value": ""},
            }
    _ensure_response_schema_defaults(test_cases)
    expected_endpoint_ids = set(endpoints_by_id)
    if len(expected_endpoint_ids) > 1 and assigned_endpoint_ids != expected_endpoint_ids:
        missing_ids = sorted(expected_endpoint_ids - assigned_endpoint_ids)
        raise HTTPException(
            status_code=502,
            detail=f"LLM did not generate cases for every selected endpoint: {', '.join(missing_ids)}",
        )
    _assign_test_case_ids(project_id, test_cases)
    if not database.save_test_cases(project_id, test_cases):
        raise HTTPException(status_code=404, detail="Project not found")
    activity = _record_generation_activity(
        project_id, "Single", endpoints, request.business_requirements,
        trace, "succeeded", test_cases=test_cases,
    )
    return {"test_cases": test_cases, "clarification_questions": trace.get("clarification_questions", []), "activity": activity}


@app.post("/api/v1/test-cases/generate-flow")
def generate_flow_test_cases_standalone(request: FlowGenerateRequest) -> dict:
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

    trace = {}
    try:
        test_cases = _generate_or_raise(
            generate_flow_test_cases,
            endpoints=endpoints,
            business_requirements=business_requirements,
            example_test_cases=examples,
            trace=trace,
        )
    except HTTPException as exc:
        _record_generation_activity(
            project_id, "Flow", endpoints, business_requirements, trace,
            "failed", error=str(exc.detail),
        )
        raise
    _attach_generation_requirements(test_cases, business_requirements)
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
    activity = _record_generation_activity(
        project_id, "Flow", endpoints, business_requirements, trace,
        "succeeded", test_cases=test_cases,
    )
    return {"test_cases": test_cases, "clarification_questions": trace.get("clarification_questions", []), "activity": activity}


@app.post("/api/v1/projects/{project_id}/test-cases/generate-flow")
def generate_flow_test_cases_project(project_id: str, request: FlowGenerateRequest) -> dict:
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

    trace = {}
    try:
        test_cases = _generate_or_raise(
            generate_flow_test_cases,
            endpoints=ordered,
            business_requirements=business_requirements,
            example_test_cases=examples,
            trace=trace,
        )
    except HTTPException as exc:
        _record_generation_activity(
            project_id, "Flow", ordered, business_requirements, trace,
            "failed", error=str(exc.detail),
        )
        raise
    _attach_generation_requirements(test_cases, business_requirements)
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
    activity = _record_generation_activity(
        project_id, "Flow", ordered, business_requirements, trace,
        "succeeded", test_cases=test_cases,
    )
    return {"test_cases": test_cases, "clarification_questions": trace.get("clarification_questions", []), "activity": activity}


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
        existing = database.find_test_case(str(tc["id"]), project_id)
        if existing and existing[1].get("superseded_by_activity_id"):
            raise HTTPException(status_code=409, detail="Superseded test cases cannot be reactivated or edited.")
    if not database.save_test_cases(project_id, new_tcs):
        raise HTTPException(status_code=404, detail="Project not found")
    updated = database.get_project(project_id)
    return {"message": f"Saved {len(new_tcs)} test case(s)", "count": len(updated["test_cases"])}


@app.get("/api/v1/projects/{project_id}/test-cases")
def get_test_cases(project_id: str, limit: int = 50, offset: int = 0) -> dict:
    """
    Get paginated test cases for a project.

    Args:
        project_id (str): The project ID.
        limit (int): Maximum number of test cases to return (default 50).
        offset (int): Number of test cases to skip (default 0).

    Returns:
        dict: {"test_cases": list, "total": int, "limit": int, "offset": int}

    Raises:
        HTTPException: If project not found.
    """
    project = database.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    all_cases = project.get("test_cases", [])
    total = len(all_cases)
    paginated = all_cases[offset:offset + limit]
    return {
        "test_cases": paginated,
        "total": total,
        "limit": limit,
        "offset": offset,
    }

@app.get("/api/v1/projects/{project_id}/test-cases/export")
def export_test_cases(
    project_id: str,
    limit: int = 1000,
    offset: int = 0,
    selected_case_ids: list[str] | None = Query(default=None),
) -> StreamingResponse:
    """
    Export test cases as CSV for a project.

    Args:
        project_id (str): The project ID.
        limit (int): Maximum number of test cases to export (default 1000).
        offset (int): Number of test cases to skip (default 0).
        selected_case_ids (list[str] | None): Optional case IDs to export.

    Returns:
        StreamingResponse: CSV containing test case definitions; flow steps are JSON in one cell.

    Raises:
        HTTPException: If project not found.
    """
    project = database.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    all_cases = project.get("test_cases", [])
    if selected_case_ids is not None:
        selected_ids = set(selected_case_ids)
        all_cases = [case for case in all_cases if str(case.get("id", "")) in selected_ids]
    paginated = all_cases[offset:offset + limit]

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "test_case_id", "name", "type", "description", "business_requirements",
        "is_flow", "source_endpoint_id", "source_endpoint_name",
        "request_method", "request_url", "request_headers_json",
        "request_query_params_json", "request_body_json", "assertions_json", "steps_json",
    ])

    def json_cell(value) -> str:
        """Serialize structured CSV cells without losing nested request data."""
        if value is None:
            return ""
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))

    for tc in paginated:
        is_flow = bool(tc.get("is_flow") or isinstance(tc.get("steps"), list))
        is_general = tc.get("case_kind") == "general"
        request = (tc.get("request") or {}) if not is_flow else {}
        writer.writerow([
            tc.get("id", ""),
            tc.get("name", ""),
            tc.get("type", ""),
            tc.get("description", ""),
            tc.get("business_requirements", ""),
            is_flow,
            tc.get("source_endpoint_id", ""),
            tc.get("source_endpoint_name", ""),
            request.get("method", "GET") if request else "",
            request.get("url", ""),
            json_cell(request.get("headers")),
            json_cell(request.get("query_params")),
            json_cell(request.get("body")),
            json_cell(tc.get("assertions")) if not is_general else "",
            json_cell(tc.get("steps") if is_flow else tc.get("manual_steps")) if is_flow or is_general else "",
        ])

    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="test_cases_{project_id}.csv"'},
    )




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
    if existing[1].get("superseded_by_activity_id"):
        raise HTTPException(status_code=409, detail="Superseded test cases are read-only.")
    merged = copy.deepcopy(existing[1])
    merged.update(request)
    merged["id"] = test_case_id
    _validate_editable_test_case(merged)
    return database.update_test_case(project_id, test_case_id, merged)


def _validate_editable_test_case(test_case: dict) -> None:
    """Validate editable request and flow-step data before persistence or execution."""
    if test_case.get("case_kind") == "general":
        steps = test_case.get("manual_steps")
        if not isinstance(steps, list) or not steps or any(not isinstance(item, str) or not item.strip() for item in steps):
            raise HTTPException(status_code=422, detail="A general test case needs ordered human-readable manual steps.")
        for field in ("request", "assertions", "variable_mappings", "expected_status", "expected_body_contains", "is_flow"):
            test_case.pop(field, None)
        test_case.setdefault("case_collection_id", GENERAL_CASE_COLLECTION_ID)
        test_case.setdefault("case_collection_name", GENERAL_CASE_COLLECTION_NAME)
        return
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
            step.setdefault(
                "step_id",
                str(uuid.uuid5(uuid.NAMESPACE_URL, f"api-agent:{test_case.get('id')}:{index}")),
            )
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

@app.post("/api/v1/projects/{project_id}/test-cases/{test_case_id}/manual-result")
def mark_manual_test_result(
    project_id: str, test_case_id: str, request: ManualTestResultRequest,
) -> dict:
    """Append a tester-marked pass/fail outcome for a general scenario."""
    found = database.find_test_case(test_case_id, project_id)
    if not found:
        raise HTTPException(status_code=404, detail="Test case not found")
    _, test_case = found
    if test_case.get("superseded_by_activity_id"):
        raise HTTPException(status_code=409, detail="Superseded test cases are read-only.")
    if test_case.get("case_kind") != "general":
        raise HTTPException(status_code=422, detail="Manual outcomes are available only for general test cases.")
    result = {
        "status": request.status,
        "manual_result": True,
        "note": request.note.strip(),
        "assertion_detail": request.note.strip() or f"Marked {request.status} manually.",
        "test_case_snapshot": copy.deepcopy(test_case),
    }
    database.append_execution(project_id, test_case_id, result)
    updated = database.update_test_case(project_id, test_case_id, {"manual_status": request.status})
    if updated is None:
        raise HTTPException(status_code=404, detail="Test case not found")
    return {"test_case_id": test_case_id, "status": request.status, "manual_result": True}

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
    if test_case.get("superseded_by_activity_id"):
        raise HTTPException(status_code=409, detail="Superseded test cases cannot be executed.")
    if test_case.get("case_kind") == "general":
        raise HTTPException(status_code=422, detail="General scenarios are manual and cannot be HTTP executed.")
    supplied_case = request.get("test_case")
    if supplied_case is not None:
        if not isinstance(supplied_case, dict) or supplied_case.get("id") != test_case_id:
            raise HTTPException(status_code=422, detail="Execution test case must match the saved test-case ID.")
        test_case = copy.deepcopy(supplied_case)
    _validate_editable_test_case(test_case)
    execution_snapshot = copy.deepcopy(test_case)

    # Detect flow test cases and execute sequentially with variable substitution
    if test_case.get("is_flow"):
        result = execute_flow_test_case(test_case, assertions=assertions)
    else:
        result = execute_test_case(test_case, assertions=assertions)
    database.append_execution(owning_project_id, test_case_id, {
        **result, "test_case_snapshot": execution_snapshot,
        "execution_assertions": copy.deepcopy(assertions),
    })
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
