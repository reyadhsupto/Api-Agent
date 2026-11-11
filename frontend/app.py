# frontend/app.py

"""
Streamlit frontend for Api-Agent.

Tabs:
1. API Workspace - Compose temporary request tabs and manage saved project collections.
2. Test Cases - Select eligible saved requests, generate (single or flow), and execute tests.

Features: Project-scoped request collections, flow test cases,
per-test-case assertions with checkboxes, collapsible cards, console logging,
reorderable endpoints, named endpoints.
"""

import streamlit as st
import requests
import json
import copy
import uuid
import os
import html
import re
import time
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

if __package__:
    from .request_controls import render_curl_aware_url, render_request_order_list
else:
    from request_controls import render_curl_aware_url, render_request_order_list

BACKEND_URL = os.getenv("API_BACKEND_URL", "http://localhost:8000")
GENERAL_CASE_COLLECTION_ID = "__general_scenarios__"
GENERAL_CASE_COLLECTION_NAME = "General scenarios"
NEW_GENERAL_CASE_COLLECTION = "__create_general_collection__"
GLOBAL_CSS = """
<style>
:root {
    --aa-accent: #ff6c37;
    --aa-accent-soft: rgba(255, 108, 55, .12);
    --aa-border: rgba(128, 128, 128, .22);
    --aa-border-strong: rgba(128, 128, 128, .38);
    --aa-surface: rgba(128, 128, 128, .055);
    --aa-surface-hover: rgba(128, 128, 128, .11);
    --aa-radius: 12px;
    --aa-radius-sm: 8px;
}
.block-container { padding-top: 1.5rem !important; padding-bottom: 3rem !important; max-width: 1500px; }
[data-testid="stHeader"] { background: transparent; }
[data-testid="stSidebar"] { border-right: 1px solid var(--aa-border); }
[data-testid="stSidebar"] > div:first-child { padding-top: .85rem; }
h1, h2, h3 { letter-spacing: -.02em; }
.stButton > button, .stDownloadButton > button, .stFormSubmitButton > button {
    border-radius: var(--aa-radius-sm) !important;
    font-weight: 550;
    transition: transform .06s ease, background .15s ease;
}
.stButton > button:active { transform: translateY(1px); }
.stTextInput input, .stTextArea textarea, [data-baseweb="select"] > div {
    border-radius: var(--aa-radius-sm) !important;
}
div[data-baseweb="tab-list"] { gap: .35rem; border-bottom: 1px solid var(--aa-border); }
button[data-baseweb="tab"] { border-radius: var(--aa-radius-sm) var(--aa-radius-sm) 0 0; }
div[data-testid="stExpander"] details { border-radius: var(--aa-radius) !important; }
.aa-hero { display:flex; align-items:center; gap:.8rem; margin:.1rem 0 .35rem; }
.aa-hero-mark {
    width:36px; height:36px; border-radius:10px; background:var(--aa-accent-soft);
    color:var(--aa-accent); display:flex; align-items:center; justify-content:center;
    font-weight:800; font-size:.95rem;
}
.aa-hero-title { font-size:1.45rem; font-weight:700; letter-spacing:-.02em; line-height:1.1; }
.aa-hero-sub { color:rgba(128,128,128,.95); font-size:.85rem; margin-top:.12rem; }
.aa-stats { display:grid; grid-template-columns:repeat(3,1fr); gap:.45rem; margin:.35rem 0 .15rem; }
.aa-stats > div { background:var(--aa-surface); border:1px solid var(--aa-border); border-radius:10px; padding:.5rem .35rem; text-align:center; }
.aa-stats span { display:block; font-size:1.15rem; font-weight:700; line-height:1.15; }
.aa-stats label { font-size:.63rem; text-transform:uppercase; letter-spacing:.05em; opacity:.68; }
.aa-empty { border:1px dashed var(--aa-border-strong); border-radius:var(--aa-radius); padding:1.4rem 1rem; text-align:center; background:var(--aa-surface); }
.aa-empty-title { font-weight:650; }
.aa-empty-body { color:rgba(128,128,128,.95); font-size:.88rem; margin-top:.25rem; }
.aa-inner-divider { margin:.7rem 0 .35rem; padding-top:.45rem; border-top:1px dashed var(--aa-border); font-size:.7rem; text-transform:uppercase; letter-spacing:.07em; opacity:.65; text-align:center; }
</style>
"""


def _toggle_session_state(key: str) -> None:
    """Toggle a boolean session-state value before the next render."""
    st.session_state[key] = not st.session_state.get(key, False)


REQUEST_TAB_CSS = """
<style>
/* A compact Postman-like request strip that keeps tab controls predictable. */
.st-key-request-tabbar {
    display: flex !important;
    flex-direction: row !important;
    flex-wrap: nowrap !important;
    justify-content: flex-start !important;
    align-items: stretch !important;
    gap: 0 !important;
    height: 46px !important;
    min-height: 46px !important;
    max-height: 46px !important;
    overflow-x: auto;
    overflow-y: hidden;
    max-width: 100%;
    border-bottom: 1px solid rgba(128,128,128,.35);
    scrollbar-width: thin;
}

/* Streamlit may insert layout wrappers. They retain their content width. */
.st-key-request-tabbar > * {
    flex: 0 0 auto !important;
    margin: 0 !important;
}
.st-key-request-tabbar > *:has(> [class*="st-key-request-tab-"]),
.st-key-request-tabbar > [class*="st-key-request-tab-"] {
    width: 220px !important;
    min-width: 220px !important;
    max-width: 220px !important;
}

/* One request tab: label fills the available space and close is fixed. */
div[class*="st-key-request-tab-"] {
    display: flex !important;
    flex-direction: row !important;
    flex-wrap: nowrap !important;
    gap: 0 !important;
    align-items: center !important;
    width: 100%;
    height: 44px !important;
    min-height: 44px !important;
    max-height: 44px !important;
    overflow: hidden;
    box-sizing: border-box;
    border-right: 1px solid rgba(128,128,128,.25);
    border-bottom: 2px solid transparent;
    margin-bottom: -1px;
}
div[class*="st-key-request-tab-on-"] {
    border-bottom: 2px solid #ff6c37;
    background: rgba(128,128,128,.12);
}
div[class*="st-key-request-tab-off-"]:hover { background: rgba(128,128,128,.08); }
div[class*="st-key-request-tab-"] > * { min-width: 0 !important; }
div[class*="st-key-request-tab-"] > *:first-child {
    flex: 1 1 0 !important;
    width: auto !important;
    overflow: hidden;
}
div[class*="st-key-request-tab-"] > *:last-child {
    flex: 0 0 34px !important;
    width: 34px !important;
    min-width: 34px !important;
}

/* Flat controls preserve visual hierarchy while keeping the strip compact. */
.st-key-request-tabbar button {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    border-radius: 0 !important;
    min-height: 2.1rem;
    padding: .2rem .6rem;
    font-size: .85rem;
}
.st-key-request-tabbar [data-testid="stButton"] { width: 100%; }
div[class*="st-key-request-tab-"] button {
    width: 100% !important;
    justify-content: flex-start !important;
    overflow: hidden;
}
.st-key-request-tabbar button > div { min-width: 0; overflow: hidden; }
.st-key-request-tabbar button p {
    font-size: .85rem;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
div[class*="st-key-request-close-"] button {
    width: 34px !important;
    min-width: 34px !important;
    max-width: 34px !important;
    height: 42px !important;
    min-height: 42px !important;
    padding: 0 !important;
    justify-content: center !important;
    opacity: .7;
    font-size: 1.25rem !important;
}
div[class*="st-key-request-close-"] {
    display: flex !important;
    flex: 0 0 34px !important;
    width: 34px !important;
    min-width: 34px !important;
    max-width: 34px !important;
    margin-left: 0 !important;
    overflow: visible !important;
}
div[class*="st-key-request-close-"] [data-testid="stButton"] {
    flex: 0 0 34px !important;
    width: 34px !important;
    min-width: 34px !important;
}
div[class*="st-key-request-close-"] button:hover {
    opacity: 1;
    background: rgba(128,128,128,.2) !important;
}

/* The add control follows the final tab at the left edge of the strip. */
.st-key-request-tabbar > *:has(> .st-key-request-add),
.st-key-request-tabbar > .st-key-request-add {
    width: 44px !important;
    min-width: 44px !important;
    max-width: 44px !important;
}
.st-key-request-add {
    display: flex !important;
    flex: 0 0 44px !important;
    width: 44px !important;
    min-width: 44px !important;
    max-width: 44px !important;
    margin-left: 0 !important;
}
.st-key-request-add [data-testid="stButton"] {
    flex: 0 0 44px !important;
    width: 44px !important;
    min-width: 44px !important;
}
.st-key-request-add button {
    width: 44px !important;
    min-width: 44px !important;
    max-width: 44px !important;
    height: 42px !important;
    min-height: 42px !important;
    padding: 0 !important;
    font-size: 1.3rem !important;
}
</style>
"""
METHOD_COLORS = {
    "GET": "green", "POST": "orange", "PUT": "blue", "PATCH": "violet",
    "DELETE": "red", "HEAD": "gray", "OPTIONS": "gray", "TRACE": "gray",
}
TEST_CASE_CSS = """
<style>
.st-key-test-case-toolbar { container-type: inline-size; min-width: 0; }
.st-key-test-run-manager { container-type: inline-size; min-width: 0; }
.st-key-test-case-quick-actions { container-type: inline-size; min-width: 0; }
.st-key-test-cases-workspace { container-type: inline-size; min-width: 0; }
div[class*="st-key-tc-card-"] {
    container-type: inline-size;
    border-left: 4px solid rgba(128,128,128,.38) !important;
    border-radius: .65rem !important;
    min-width: 0;
}
div[class*="st-key-tc-card-passed-"] { border-left-color: #2e9e5b !important; }
div[class*="st-key-tc-card-failed-"] { border-left-color: #e5484d !important; }
div[class*="st-key-tc-card-error-"] { border-left-color: #f5a524 !important; }
div[class*="st-key-manual_pass_"] button {
    background: #2e9e5b !important; border-color: #2e9e5b !important; color: #fff !important;
}
div[class*="st-key-manual_pass_"] button:hover { background: #247c47 !important; border-color: #247c47 !important; }
div[class*="st-key-manual_fail_"] button {
    background: #e5484d !important; border-color: #e5484d !important; color: #fff !important;
}
div[class*="st-key-manual_fail_"] button:hover { background: #bd3439 !important; border-color: #bd3439 !important; }
div[class*="st-key-tc-step-"] { background: rgba(128,128,128,.035); }
div[class*="st-key-tc-card-"] button[kind="tertiary"] {
    padding: 0 .25rem;
    min-height: 1.9rem;
}
@container (max-width: 980px) {
    .st-key-test-case-toolbar [data-testid="stHorizontalBlock"] {
        display: grid !important;
        grid-template-columns: repeat(auto-fit, minmax(145px, 1fr));
        gap: .45rem !important;
    }
    .st-key-test-case-toolbar [data-testid="column"] { width: auto !important; min-width: 0; }
}
@container (max-width: 820px) {
    .st-key-test-cases-workspace [data-testid="stHorizontalBlock"] {
        flex-wrap: wrap !important;
        row-gap: .55rem;
    }
    .st-key-test-cases-workspace [data-testid="column"] {
        min-width: 145px;
    }
}
@container (max-width: 520px) {
    .st-key-test-case-quick-actions [data-testid="stHorizontalBlock"] {
        display: grid !important;
        grid-template-columns: 1fr;
        gap: .4rem !important;
    }
    .st-key-test-case-quick-actions [data-testid="column"] { width: auto !important; min-width: 0; }
}
@container (max-width: 680px) {
    .st-key-test-run-manager [data-testid="stHorizontalBlock"] {
        display: grid !important;
        grid-template-columns: repeat(auto-fit, minmax(135px, 1fr));
        gap: .45rem !important;
    }
    .st-key-test-run-manager [data-testid="column"] { width: auto !important; min-width: 0; }
}
@container (max-width: 680px) {
    div[class*="st-key-tc-card-"] [data-testid="stHorizontalBlock"] {
        flex-wrap: wrap !important;
        row-gap: .45rem;
    }
    div[class*="st-key-tc-card-"] [data-testid="column"] { min-width: 0; }
}
</style>
"""
TEST_CASES_TOPBAR_CSS = """
<style>
.st-key-test-cases-topbar {
    padding-bottom: .7rem;
    border-bottom: 1px solid var(--aa-border);
    margin-bottom: .9rem;
}
.st-key-test-cases-topbar [data-testid="stHorizontalBlock"] { align-items: center; }
.st-key-test-cases-topbar h3 {
    margin: 0 !important; font-size: 1.35rem; letter-spacing: -.02em;
}
.st-key-test-cases-topbar .stCaption p { margin-bottom: 0; font-size: .82rem; }
.st-key-add-manual-test-action [data-testid="stPopover"] > button {
    background: var(--aa-accent) !important;
    color: #fff !important;
    border: 1px solid var(--aa-accent) !important;
    font-weight: 650;
    min-height: 2.5rem;
    box-shadow: 0 2px 10px rgba(255,108,55,.22);
    transition: box-shadow .15s ease, transform .08s ease;
}
.st-key-add-manual-test-action [data-testid="stPopover"] > button:hover {
    box-shadow: 0 3px 16px rgba(255,108,55,.32);
    transform: translateY(-1px);
}
.st-key-add-manual-test-action [data-testid="stPopover"] > button:active { transform: translateY(0); }
.st-key-add-manual-test-action [data-testid="stPopover"] > button p,
.st-key-add-manual-test-action [data-testid="stPopover"] > button span,
.st-key-add-manual-test-action [data-testid="stPopover"] > button svg {
    color: #fff !important; fill: #fff !important;
}
.st-key-reusable-runs-action [data-testid="stPopover"] > button {
    font-weight: 600; min-height: 2.5rem;
    transition: box-shadow .15s ease, transform .08s ease, border-color .15s ease;
}
.st-key-reusable-runs-action [data-testid="stPopover"] > button:hover {
    border-color: var(--aa-accent) !important; transform: translateY(-1px);
}
.aa-popover-section {
    font-size: .68rem; font-weight: 700; text-transform: uppercase;
    letter-spacing: .07em; color: var(--aa-accent); margin: .35rem 0 .1rem;
    opacity: .92;
}
.aa-popover-hint {
    font-size: .78rem; color: rgba(128,128,128,.95);
    margin: -.15rem 0 .45rem; line-height: 1.35;
}
@container (max-width: 980px) {
    .st-key-test-cases-topbar [data-testid="stHorizontalBlock"] {
        display: grid !important; grid-template-columns: minmax(0, 1fr) auto auto;
        gap: .45rem !important;
    }
    .st-key-test-cases-topbar [data-testid="column"] { width: auto !important; min-width: 0; }
}
@container (max-width: 620px) {
    .st-key-test-cases-topbar [data-testid="stHorizontalBlock"] {
        grid-template-columns: repeat(2, minmax(0, 1fr));
    }
    .st-key-test-cases-topbar [data-testid="column"]:first-child { grid-column: 1 / -1; }
    .st-key-test-cases-topbar [data-testid="stPopover"] > button { width: 100%; }
}
@media (prefers-reduced-motion: reduce) {
    .st-key-test-cases-topbar button { transition: none !important; }
}
</style>
"""


def _method_badge(method: str) -> str:
    """Format an HTTP method as a colored Streamlit badge.

    Args:
        method (str): HTTP request method.

    Returns:
        str: Colored markdown badge label.
    """
    method = (method or "GET").upper()
    return f":{METHOD_COLORS.get(method, 'gray')}-badge[{method}]"


def _truncate(value: str, limit: int = 72) -> str:
    """Shorten long labels and URLs without losing their beginning.

    Args:
        value (str): Text to display.
        limit (int): Maximum displayed character count.

    Returns:
        str: Original or truncated text.
    """
    value = value or ""
    return value if len(value) <= limit else f"{value[:limit - 1]}…"


def _hero(title: str, subtitle: str, mark: str = "AA") -> None:
    """Render the product header used above the main workspace tabs.

    Args:
        title (str): Product or workspace title.
        subtitle (str): One-line purpose statement.
        mark (str): Short brand mark displayed in the header.

    Returns:
        None: Writes the branded header to the Streamlit page.
    """
    st.markdown(
        f'<div class="aa-hero"><div class="aa-hero-mark">{mark}</div>'
        f'<div><div class="aa-hero-title">{title}</div>'
        f'<div class="aa-hero-sub">{subtitle}</div></div></div>',
        unsafe_allow_html=True,
    )


def _empty_state(title: str, body: str) -> None:
    """Render a compact, actionable empty state without decorative symbols.

    Args:
        title (str): Short empty-state heading.
        body (str): Guidance for the next user action.

    Returns:
        None: Writes the empty state to the Streamlit page.
    """
    st.markdown(
        f'<div class="aa-empty"><div class="aa-empty-title">{title}</div>'
        f'<div class="aa-empty-body">{body}</div></div>',
        unsafe_allow_html=True,
    )


def _raw_get(path: str) -> dict | list:
    """Fetch backend JSON without logging UI side effects.

    Args:
        path (str): Backend route path.

    Returns:
        dict | list: Decoded JSON response.
    """
    response = requests.get(f"{BACKEND_URL}{path}", timeout=300)
    response.raise_for_status()
    return response.json()


def _fetch_test_case_csv(project_id: str, selected_case_ids: list[str]) -> bytes:
    """Fetch selected saved cases as CSV when the download is requested."""
    response = requests.get(
        f"{BACKEND_URL}/api/v1/projects/{project_id}/test-cases/export",
        params={"limit": 10000, "selected_case_ids": selected_case_ids},
        timeout=300,
    )
    response.raise_for_status()
    return response.content


def _normalise_generation_activity_records(payload) -> list[dict]:
    """Normalize legacy list and paginated activity API responses to records."""
    if isinstance(payload, dict):
        payload = payload.get("activities", payload.get("records", []))
    if not isinstance(payload, list):
        return []
    return [record for record in payload if isinstance(record, dict)]


def _revision_case_signature(test_case: dict) -> str:
    """Serialize editable case content consistently for saved-versus-session checks."""
    case = copy.deepcopy(test_case)

    def normalize_request(request: dict) -> dict:
        """Normalize query strings and editor rows to avoid UI-only differences."""
        normalized = copy.deepcopy(request or {})
        source_url = str(normalized.get("url") or "")
        clean_url, query_rows = _normalise_request_url(
            source_url, _request_rows(normalized.get("query_params", {})),
        )
        normalized["url"] = clean_url
        normalized["method"] = str(normalized.get("method") or "GET").upper()

        def normalize_rows(values):
            rows = []
            for row in values:
                key = str(row.get("key") or "").strip()
                value = "" if row.get("value") is None else str(row.get("value", ""))
                description = str(row.get("description") or "")
                if key or value or description:
                    rows.append({
                        "key": key, "value": value, "description": description,
                        "enabled": bool(row.get("enabled", True)),
                    })
            return rows

        normalized["query_params"] = normalize_rows(query_rows)
        normalized["headers"] = normalize_rows(_request_rows(normalized.get("headers", {})))
        return normalized

    fields = (
        "name", "type", "description", "business_requirements", "release_notes",
        "is_flow", "source_endpoint_id", "source_endpoint_name", "expected_status",
        "expected_body_contains", "request", "assertions", "steps",
    )
    payload = {key: case[key] for key in fields if key in case}
    if isinstance(payload.get("request"), dict):
        payload["request"] = normalize_request(payload["request"])
    if not case.get("is_flow"):
        payload["assertions"] = _normalize_assertions({
            "assertions": payload.get("assertions", {}),
            "expected_status": case.get("expected_status", 200),
            "expected_body_contains": case.get("expected_body_contains"),
        })
    steps = payload.get("steps", []) or []
    if isinstance(steps, list):
        steps.sort(key=lambda item: item.get("step_order", 0) if isinstance(item, dict) else 0)
    for index, step in enumerate(steps):
        if not isinstance(step, dict):
            continue
        step.pop("step_id", None)
        if isinstance(step.get("endpoint"), dict):
            step["endpoint"] = normalize_request(step["endpoint"])
        step["assertions"] = _normalize_assertions({
            "assertions": step.get("assertions", {}),
            "expected_status": step.get("expected_status", 200),
            "expected_body_contains": step.get("expected_body_contains"),
        })
        if index == 0:
            step["variable_mappings"] = []

    def remove_editor_ids(value):
        """Strip IDs used only to keep Streamlit editor widgets stable."""
        if isinstance(value, dict):
            return {
                key: remove_editor_ids(item)
                for key, item in value.items() if key not in {"_ui_id", "mapping_id"}
            }
        if isinstance(value, list):
            return [remove_editor_ids(item) for item in value]
        return value

    payload = remove_editor_ids(payload)
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _revision_endpoint_change(current: dict, original: dict) -> list[str]:
    """Return request-defining fields that differ from a source-action snapshot."""
    fields = (
        ("method", "method"), ("url", "URL"), ("headers", "headers"),
        ("query_params", "query parameters"), ("body", "body"),
    )
    changed = []

    def effective_values(values):
        if isinstance(values, dict):
            return values
        if isinstance(values, list):
            return {
                str(row.get("key")): row.get("value", "")
                for row in values if isinstance(row, dict) and row.get("key") and row.get("enabled", True)
            }
        return {}

    for key, label in fields:
        current_value = current.get(key)
        original_value = original.get(key)
        if key == "method":
            current_value = str(current_value or "GET").upper()
            original_value = str(original_value or "GET").upper()
        elif key in {"headers", "query_params"}:
            current_value = effective_values(current_value)
            original_value = effective_values(original_value)
        elif key == "body" and current.get("include_body") is False:
            current_value = None
        if json.dumps(current_value, sort_keys=True, default=str) != json.dumps(original_value, sort_keys=True, default=str):
            changed.append(label)
    return changed


def _revision_endpoint_status(endpoint: dict, previous: dict, snapshot_available: bool) -> str:
    """Summarize one current endpoint's request-definition change status."""
    if not snapshot_available:
        return "No comparison"
    if previous is None:
        return "Added"
    changed = _revision_endpoint_change(endpoint, previous)
    return "Modified: " + ", ".join(changed) if changed else "Unchanged"


def _revision_case_details(test_case: dict, endpoints_by_id: dict, collections_by_id: dict) -> str:
    """Build a concise baseline option label with case and endpoint provenance."""
    is_flow = bool(test_case.get("is_flow") or isinstance(test_case.get("steps"), list))
    endpoint_ids = []
    if is_flow:
        for step in test_case.get("steps", []):
            if not isinstance(step, dict):
                continue
            endpoint = step.get("endpoint")
            endpoint_ids.append(str(step.get("endpoint_id") or (
                endpoint.get("id") if isinstance(endpoint, dict) else ""
            ) or ""))
    elif test_case.get("source_endpoint_id"):
        endpoint_ids = [str(test_case["source_endpoint_id"])]
    endpoint_ids = list(dict.fromkeys(item for item in endpoint_ids if item))
    collection_names = []
    endpoint_names = []
    deleted = []
    for endpoint_id in endpoint_ids:
        endpoint = endpoints_by_id.get(endpoint_id)
        if not endpoint:
            deleted.append(endpoint_id)
            continue
        endpoint_names.append(
            f"{str(endpoint.get('method') or 'GET').upper()} "
            f"{endpoint.get('name') or endpoint.get('url') or 'Unnamed endpoint'}"
        )
        collection = collections_by_id.get(str(endpoint.get("collection_id")))
        if collection:
            collection_names.append(str(collection.get("name") or "Untitled collection"))
    kind = "Flow" if is_flow else str(test_case.get("type") or "test").title()
    details = [kind]
    if is_flow:
        details.append(f"{len(test_case.get('steps', []) or [])} steps")
    if endpoint_names:
        details.append("Requests: " + ", ".join(dict.fromkeys(endpoint_names)))
    if collection_names:
        details.append(", ".join(dict.fromkeys(collection_names)))
    if deleted:
        details.append(f"references {len(deleted)} deleted endpoint(s)")
    return " · ".join(details)


def _select_revision_collection(project_id: str, collection_id: str, endpoint_ids: list[str]) -> None:
    """Apply a collection-level revision selection to all of its saved requests."""
    selected = bool(st.session_state.get(f"revision_collection_{project_id}_{collection_id}"))
    for endpoint_id in endpoint_ids:
        st.session_state[f"revision_endpoint_{project_id}_{endpoint_id}"] = selected


@st.cache_data(ttl=15, show_spinner=False)
def _fetch_projects_cached() -> list:
    """Cache project summaries for a short interval.

    Returns:
        list: Project summaries, or an empty list when the backend is unavailable.
    """
    try:
        return _raw_get("/api/v1/projects") or []
    except Exception:
        return []


@st.cache_data(ttl=15, show_spinner=False)
def _fetch_collection_export_cached(project_id: str, collection_id: str) -> dict:
    """Fetch and briefly cache a Postman collection export.

    Args:
        project_id (str): Project that owns the collection.
        collection_id (str): Collection to export.

    Returns:
        dict: Postman Collection v2.1 document.
    """
    return _raw_get(f"/api/v1/projects/{project_id}/collections/{collection_id}/export")


def log_to_console(data: dict, label: str = "API") -> None:
    """Inject a JavaScript console.log via st.iframe."""
    safe_json = json.dumps(data, default=str, indent=2)
    html = f"""
    <script>
    console.group("{label}");
    console.log("{label} data:", {safe_json});
    console.groupEnd();
    </script>
    """
    st.iframe(src="data:text/html," + html, height=1, width=1)


def _queue_toast(message: str, kind: str = "success") -> None:
    """Queue a short toast so it can be rendered after a Streamlit rerun."""
    st.session_state.setdefault("_toast_queue", []).append({"message": message, "kind": kind})


def _flush_toasts() -> None:
    """Render queued notices once, including notices created before a rerun."""
    toast = getattr(st, "toast", None)
    notices = st.session_state.pop("_toast_queue", [])
    if not callable(toast):
        return
    for notice in notices:
        message = notice["message"]
        if notice.get("kind") == "error":
            message = f":red[Error] · {message}"
            icon = ":material/error:"
        elif notice.get("kind") == "warning":
            message = f":orange[Warning] · {message}"
            icon = ":material/warning:"
        else:
            message = f":green[Success] · {message}"
            icon = ":material/check_circle:"
        toast(message, icon=icon, duration=5)


def _api_error_message(exc: Exception, response=None) -> str:
    """Extract a useful API error detail and notify the user once."""
    detail = None
    if response is not None:
        try:
            detail = response.json().get("detail")
        except (ValueError, AttributeError):
            pass
    message = str(detail or exc)
    _queue_toast(message, "error")
    return message


def api_post(path: str, payload: dict) -> dict:
    """Send a POST request to the backend and log to browser console."""
    log_to_console(payload, f"REQUEST {path}")
    try:
        response = requests.post(f"{BACKEND_URL}{path}", json=payload, timeout=300)
    except requests.RequestException as exc:
        raise RuntimeError(_api_error_message(exc)) from exc
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        raise RuntimeError(_api_error_message(exc, response)) from exc
    result = response.json()
    log_to_console(result, f"RESPONSE {path}")
    return result


def api_get(path: str) -> dict:
    """Send a GET request to the backend and log to browser console."""
    log_to_console({}, f"REQUEST {path}")
    try:
        response = requests.get(f"{BACKEND_URL}{path}", timeout=300)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(_api_error_message(exc, getattr(exc, "response", None))) from exc
    result = response.json()
    log_to_console(result, f"RESPONSE {path}")
    return result


def api_delete(path: str) -> dict:
    """Send a DELETE request to the backend and log to browser console."""
    log_to_console({}, f"REQUEST {path}")
    try:
        response = requests.delete(f"{BACKEND_URL}{path}", timeout=300)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(_api_error_message(exc, getattr(exc, "response", None))) from exc
    result = response.json()
    log_to_console(result, f"RESPONSE {path}")
    return result


def api_put(path: str, payload: dict) -> dict:
    """Send a PUT request to the backend and log to browser console."""
    log_to_console(payload, f"REQUEST {path}")
    try:
        response = requests.put(f"{BACKEND_URL}{path}", json=payload, timeout=300)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(_api_error_message(exc, getattr(exc, "response", None))) from exc
    result = response.json()
    log_to_console(result, f"RESPONSE {path}")
    return result


def display_request_response(label: str, request_info: dict, response_info: dict) -> None:
    """Display verbose request and response details in a bordered section."""
    with st.container():
        st.markdown(f"**{label}**")
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Request")
            st.code(
                f"{request_info.get('method', '')} {request_info.get('url', '')}\n"
                f"Headers: {json.dumps(request_info.get('headers', {}), indent=2)}\n"
                f"Body: {json.dumps(request_info.get('body', ''), indent=2) if request_info.get('body') else ''}",
                language="http",
            )
        with col2:
            st.subheader("Response")
            status = response_info.get("status")
            status_color = "green" if status and 200 <= status < 300 else "red"
            st.markdown(f"**Status:** <span style='color:{status_color}'>{status}</span>", unsafe_allow_html=True)
            response_body = response_info.get("body", "")
            if response_body:
                try:
                    beautified = json.dumps(json.loads(response_body), indent=2)
                except (json.JSONDecodeError, TypeError):
                    beautified = response_body
            else:
                beautified = ""
            st.code(
                f"Body: {beautified}",
                language="json" if beautified else "http",
            )


def initialize_session_state() -> None:
    """Initialize Streamlit session state keys if they do not exist."""
    defaults = {
        "endpoints": [],
        "test_cases": [],
        "executions": {},
        "current_project": None,
        "project_list": [],
        "request_drafts": [],
        "generation_order_ids": [],
        "selected_collection_id": None,
        "persisted_project_id": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def refresh_project_list(force: bool = False) -> None:
    """Refresh cached project summaries when explicitly requested.

    Args:
        force (bool): Clear the short-lived cache before fetching.

    Returns:
        None: Updates the project list in session state.
    """
    if force:
        _fetch_projects_cached.clear()
    st.session_state["project_list"] = _fetch_projects_cached()


def load_project(project_id: str) -> None:
    """Load a project and its test cases from the backend."""
    try:
        project = api_get(f"/api/v1/projects/{project_id}")
        st.session_state["current_project"] = project
        st.session_state["persisted_project_id"] = project_id
        st.session_state["endpoints"] = project.get("endpoints", [])
        st.session_state["request_drafts"] = []
        eligible_ids = {
            endpoint["id"] for endpoint in project.get("endpoints", [])
            if endpoint.get("include_for_generation", endpoint.get("include", False))
        }
        saved_order = project.get("generation_order_ids", [])
        st.session_state["generation_order_ids"] = [
            request_id for request_id in saved_order if request_id in eligible_ids
        ] + [
            endpoint["id"] for endpoint in project.get("endpoints", [])
            if endpoint.get("id") in eligible_ids and endpoint["id"] not in saved_order
        ]
        collection_ids = [item["id"] for item in project.get("collections", [])]
        if st.session_state.get("selected_collection_id") not in collection_ids:
            st.session_state["selected_collection_id"] = collection_ids[0] if collection_ids else None
        st.session_state["test_cases"] = project.get("test_cases", [])
        st.session_state["executions"] = {}
        for execution in project.get("executions", []):
            test_case_id = execution.get("test_case_id")
            if test_case_id:
                st.session_state["executions"][test_case_id] = execution
    except Exception as exc:
        st.error(f"Failed to load project: {exc}")


def render_endpoint_card(endpoint: dict, index: int) -> dict:
    """Render a collapsible endpoint card with name, edit fields, and reorder controls."""
    endpoint_id = endpoint.get("id", str(uuid.uuid4()))

    with st.expander(
        f"{index + 1}. [{endpoint.get('method', 'GET').upper()}] {endpoint.get('name', 'Unnamed')}",
        expanded=False,
    ):
        # Endpoint name input
        endpoint_name = st.text_input(
            "Endpoint Name",
            value=endpoint.get("name", ""),
            key=f"ep_name_{endpoint_id}",
            placeholder="e.g. auth, verify-auth, login",
        )

        # Include/Exclude and Remove in same row
        col_include, col_move_up, col_move_down, col_remove = st.columns([1.2, 1, 1, 1])
        with col_include:
            include = st.checkbox(
                "Include",
                value=endpoint.get("include", True),
                key=f"ep_include_{endpoint_id}",
                help="Include this endpoint when generating test cases",
            )
        with col_move_up:
            if st.button("Up", key=f"ep_up_{endpoint_id}", disabled=index == 0):
                eps = st.session_state["endpoints"]
                eps[index], eps[index - 1] = eps[index - 1], eps[index]
                for i, e in enumerate(eps):
                    e["order"] = i
                st.session_state["endpoints"] = eps
                st.rerun()
        with col_move_down:
            if st.button("Down", key=f"ep_down_{endpoint_id}", disabled=index == len(st.session_state["endpoints"]) - 1):
                eps = st.session_state["endpoints"]
                eps[index], eps[index + 1] = eps[index + 1], eps[index]
                for i, e in enumerate(eps):
                    e["order"] = i
                st.session_state["endpoints"] = eps
                st.rerun()
        with col_remove:
            if st.button("Remove", key=f"ep_remove_{endpoint_id}", type="secondary"):
                st.session_state["endpoints"] = [
                    ep for ep in st.session_state["endpoints"]
                    if ep.get("id") != endpoint_id
                ]
                st.rerun()

        st.divider()

        # Method and URL
        col_method, col_url = st.columns([1, 4])
        with col_method:
            method = st.selectbox(
                "Method",
                options=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS", "TRACE"],
                index=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS", "TRACE"].index(
                    endpoint.get("method", "GET").upper()
                ),
                key=f"ep_method_{endpoint_id}",
            )
        with col_url:
            url = st.text_input(
                "URL",
                value=endpoint.get("url", ""),
                key=f"ep_url_{endpoint_id}",
                placeholder="https://api.example.com/resource",
            )

        # Headers
        st.markdown("**Headers**")
        headers = endpoint.get("headers", {}) or {}
        header_keys = list(headers.keys())
        new_headers = {}

        for i, hk in enumerate(header_keys):
            col_hk, col_hv, col_hdel = st.columns([3, 4, 1])
            with col_hk:
                hk_val = st.text_input("Key", value=hk, key=f"ep_hk_{endpoint_id}_{i}")
            with col_hv:
                hv_val = st.text_input("Value", value=headers[hk], key=f"ep_hv_{endpoint_id}_{i}")
            with col_hdel:
                if st.button("X", key=f"ep_hdel_{endpoint_id}_{i}"):
                    pass
            if hk_val:
                new_headers[hk_val] = hv_val

        col_nhk, col_nhv, col_nhadd = st.columns([3, 4, 1])
        with col_nhk:
            new_hk = st.text_input("Add Header Key", key=f"ep_new_hk_{endpoint_id}", placeholder="Key")
        with col_nhv:
            new_hv = st.text_input("Add Header Value", key=f"ep_new_hv_{endpoint_id}", placeholder="Value")
        with col_nhadd:
            if st.button("+", key=f"ep_add_h_{endpoint_id}"):
                if new_hk:
                    new_headers[new_hk] = new_hv or ""

        # Query Params
        st.markdown("**Query Parameters**")
        query_params = endpoint.get("query_params", {}) or {}
        qp_keys = list(query_params.keys())
        new_qp = {}

        for i, qk in enumerate(qp_keys):
            col_qk, col_qv, col_qdel = st.columns([3, 4, 1])
            with col_qk:
                qk_val = st.text_input("Key", value=qk, key=f"ep_qk_{endpoint_id}_{i}")
            with col_qv:
                qv_val = st.text_input("Value", value=query_params[qk], key=f"ep_qv_{endpoint_id}_{i}")
            with col_qdel:
                if st.button("X", key=f"ep_qdel_{endpoint_id}_{i}"):
                    pass
            if qk_val:
                new_qp[qk_val] = qv_val

        col_nqk, col_nqv, col_nqadd = st.columns([3, 4, 1])
        with col_nqk:
            new_qk = st.text_input("Add Query Key", key=f"ep_new_qk_{endpoint_id}", placeholder="Key")
        with col_nqv:
            new_qv = st.text_input("Add Query Value", key=f"ep_new_qv_{endpoint_id}", placeholder="Value")
        with col_nqadd:
            if st.button("+", key=f"ep_add_q_{endpoint_id}"):
                if new_qk:
                    new_qp[new_qk] = new_qv or ""

        # Path Params
        st.markdown("**Path Parameters**")
        path_params = endpoint.get("path_params", {}) or {}
        pp_keys = list(path_params.keys())
        new_pp = {}

        for i, pk in enumerate(pp_keys):
            col_pk, col_pv, col_pdel = st.columns([3, 4, 1])
            with col_pk:
                pk_val = st.text_input("Key", value=pk, key=f"ep_pk_{endpoint_id}_{i}")
            with col_pv:
                pv_val = st.text_input("Value", value=path_params[pk], key=f"ep_pv_{endpoint_id}_{i}")
            with col_pdel:
                if st.button("X", key=f"ep_pdel_{endpoint_id}_{i}"):
                    pass
            if pk_val:
                new_pp[pk_val] = pv_val

        col_npk, col_npv, col_npadd = st.columns([3, 4, 1])
        with col_npk:
            new_pk = st.text_input("Add Path Key", key=f"ep_new_pk_{endpoint_id}", placeholder="Key")
        with col_npv:
            new_pv = st.text_input("Add Path Value", key=f"ep_new_pv_{endpoint_id}", placeholder="Value")
        with col_npadd:
            if st.button("+", key=f"ep_add_p_{endpoint_id}"):
                if new_pk:
                    new_pp[new_pk] = new_pv or ""

        # Body / Payload
        st.markdown("**Body / Payload**")
        body_raw = st.text_area(
            "Body (JSON or raw text)",
            value=endpoint.get("body", "") if endpoint.get("body") else "",
            height=150,
            key=f"ep_body_{endpoint_id}",
        )
        body_parsed = None
        if body_raw and body_raw.strip():
            try:
                body_parsed = json.loads(body_raw)
            except json.JSONDecodeError:
                body_parsed = body_raw

        # Build URL with query params
        full_url = url
        if new_qp:
            query_string = urlencode(new_qp)
            separator = "&" if "?" in full_url else "?"
            full_url = f"{full_url}{separator}{query_string}"

        return {
            "id": endpoint_id,
            "name": endpoint_name,
            "include": include,
            "method": method,
            "url": full_url,
            "headers": new_headers,
            "query_params": new_qp,
            "path_params": new_pp,
            "body": body_parsed,
        }


def _normalize_assertions(tc: dict) -> dict:
    """Return assertion configs as lists while accepting legacy single dictionaries."""
    defaults = {
        "status": [{"enabled": True, "expected_status": tc.get("expected_status", 200)}],
        "body_contains": [{
            "enabled": tc.get("expected_body_contains") is not None,
            "value": tc.get("expected_body_contains", "") or "",
        }],
        "jsonpath": [{"enabled": False, "path": "", "expected_value": ""}],
        "response_schema": [{"enabled": False, "schema": "{}"}],
    }
    raw = tc.get("assertions", {}) or {}
    for assertion_type, default in defaults.items():
        value = raw.get(assertion_type, default)
        raw[assertion_type] = value if isinstance(value, list) else [value]
        raw[assertion_type] = [item for item in raw[assertion_type] if isinstance(item, dict)]
    tc["assertions"] = raw
    return raw


def _normalise_flow_steps(tc: dict) -> list[dict]:
    """Sort flow steps, normalize assertions, and remove impossible first-step mappings."""
    steps = tc.get("steps", [])
    steps.sort(key=lambda step: step.get("step_order", 0))
    for index, step in enumerate(steps):
        step.setdefault("step_id", str(uuid.uuid4()))
        step["assertions"] = _normalize_assertions(step)
        if index == 0:
            step["variable_mappings"] = []
    return steps


def _render_assertion_instance(assertions: dict, assertion_type: str, instance: int, tc_id: str) -> None:
    """Render one enabled, editable assertion row with consistent card styling."""
    config = assertions[assertion_type][instance]
    key_prefix = f"tc_assert_{assertion_type}_{tc_id}_{instance}"
    remove = False
    with st.container(border=True):
        if assertion_type == "status":
            enabled_col, value_col, remove_col = st.columns([0.55, 4.5, 0.7], vertical_alignment="center")
            config["enabled"] = enabled_col.checkbox(
                "Enabled", value=config.get("enabled", True),
                key=f"{key_prefix}_enabled", label_visibility="collapsed",
                help="Include in this test's assertions",
            )
            config["expected_status"] = value_col.number_input(
                "Expected status", min_value=100, max_value=599,
                value=int(config.get("expected_status") or 200), step=1,
                key=f"{key_prefix}_value", disabled=not config["enabled"],
            )
        elif assertion_type == "body_contains":
            enabled_col, value_col, remove_col = st.columns([0.55, 4.5, 0.7], vertical_alignment="center")
            config["enabled"] = enabled_col.checkbox(
                "Enabled", value=config.get("enabled", False),
                key=f"{key_prefix}_enabled", label_visibility="collapsed",
                help="Include in this test's assertions",
            )
            config["value"] = value_col.text_input(
                "Text to find", value=config.get("value", "") or "",
                key=f"{key_prefix}_value", placeholder="Text in response body",
                disabled=not config["enabled"],
            )
        elif assertion_type == "jsonpath":
            enabled_col, path_col, expected_col, remove_col = st.columns(
                [0.5, 2.2, 2.2, 0.7], vertical_alignment="center"
            )
            config["enabled"] = enabled_col.checkbox(
                "Enabled", value=config.get("enabled", False),
                key=f"{key_prefix}_enabled", label_visibility="collapsed",
                help="Include in this test's assertions",
            )
            config["path"] = path_col.text_input(
                "JSONPath", value=config.get("path", "") or "",
                key=f"{key_prefix}_path", placeholder="e.g. $.token",
                disabled=not config["enabled"],
            )
            config["expected_value"] = expected_col.text_input(
                "Expected value", value=config.get("expected_value", "") or "",
                key=f"{key_prefix}_expected", placeholder="Expected field value",
                disabled=not config["enabled"],
            )
        else:
            enabled_col, schema_col, remove_col = st.columns(
                [0.5, 4.5, 0.7], vertical_alignment="top"
            )
            config["enabled"] = enabled_col.checkbox(
                "Enabled", value=config.get("enabled", False),
                key=f"{key_prefix}_enabled", label_visibility="collapsed",
                help="Include in this test's assertions",
            )
            config["schema"] = schema_col.text_area(
                "JSON Schema", value=config.get("schema", "{}") or "{}",
                key=f"{key_prefix}_schema", height=130,
                placeholder='{"type": "object", "required": ["id"]}',
                disabled=not config["enabled"],
            )

        with remove_col:
            remove = st.button(
                " ", key=f"{key_prefix}_remove", icon=":material/delete:",
                help="Remove this assertion", type="tertiary",
            )
    if remove:
        assertions[assertion_type].pop(instance)
        st.rerun()


def _render_assertion_group(assertions: dict, assertion_type: str, label: str, tc_id: str) -> None:
    """Render one expandable assertion type group with repeatable card rows."""
    group = assertions[assertion_type]
    with st.expander(f"{label} · {len(group)}", expanded=assertion_type == "status"):
        for instance in range(len(group)):
            _render_assertion_instance(assertions, assertion_type, instance, tc_id)
        defaults = {
            "status": {"enabled": True, "expected_status": 200},
            "body_contains": {"enabled": True, "value": ""},
            "jsonpath": {"enabled": True, "path": "", "expected_value": ""},
            "response_schema": {"enabled": True, "schema": "{}"},
        }
        if st.button(
            f"Add {label.lower()} assertion", key=f"tc_assert_{assertion_type}_{tc_id}_add",
            icon=":material/add:",
        ):
            group.append({**defaults[assertion_type]})
            st.rerun()


def _render_test_case_assertions(assertions: dict, uid: str) -> None:
    """Render the Playground-style assertion groups for a test or flow step."""
    enabled_count = sum(
        bool(item.get("enabled"))
        for group in assertions.values()
        for item in group
    )
    st.caption(f"{enabled_count} enabled · used when this test runs")
    for assertion_type, label in (
        ("status", "Status code"),
        ("body_contains", "Body contains"),
        ("jsonpath", "Field value"),
        ("response_schema", "Response schema"),
    ):
        _render_assertion_group(assertions, assertion_type, label, uid)


def _toggle_test_case_state(key: str) -> None:
    """Toggle a card's expanded state.

    Args:
        key (str): Session-state key for the card's open state.

    Returns:
        None: Updates Streamlit session state in place.
    """
    st.session_state[key] = not st.session_state.get(key, False)


def _test_case_status(result: dict | None) -> str:
    """Return a normalized execution label for display and filtering.

    Args:
        result (dict | None): Stored execution result, if one exists.

    Returns:
        str: One of passed, failed, error, or not_run.
    """
    if not result:
        return "not_run"
    return str(result.get("status", "error")).lower()


def _status_badge(status: str | None) -> str:
    """Format an execution status as a compact Streamlit colored badge.

    Args:
        status (str | None): Execution status to display.

    Returns:
        str: Streamlit markdown badge for the status.
    """
    normalized = str(status or "not_run").lower()
    colors = {"passed": "green", "failed": "red", "error": "orange", "not_run": "gray"}
    labels = {"passed": "PASSED", "failed": "FAILED", "error": "ERROR", "not_run": "NOT RUN"}
    return f":{colors.get(normalized, 'gray')}-badge[{labels.get(normalized, normalized.upper())}]"


def _format_latency(latency_ms: int | float | None) -> str:
    """Format measured latency in milliseconds or seconds.

    Args:
        latency_ms (int | float | None): Duration measured in milliseconds.

    Returns:
        str: Milliseconds through 1000 ms, otherwise seconds with two decimals.
    """
    latency = float(latency_ms or 0)
    if latency > 1000:
        return f"{latency / 1000:.2f} s"
    return f"{latency:g} ms"


def _pretty_payload(body) -> tuple[str, bool]:
    """Format payloads for display and identify valid JSON.

    Args:
        body (Any): HTTP request or response payload.

    Returns:
        tuple[str, bool]: Display text and whether it is JSON.
    """
    if body is None or body == "":
        return "", False
    if isinstance(body, (dict, list)):
        return json.dumps(body, indent=2, ensure_ascii=False), True
    try:
        return json.dumps(json.loads(body), indent=2, ensure_ascii=False), True
    except (json.JSONDecodeError, TypeError):
        return str(body), False


def _render_headers(headers: dict | list | None) -> None:
    """Render HTTP headers in a compact key/value table.

    Args:
        headers (dict | list | None): Header mapping or empty value.

    Returns:
        None: Writes the header view to the Streamlit page.
    """
    if isinstance(headers, dict) and headers:
        st.dataframe(
            [{"Key": key, "Value": str(value)} for key, value in headers.items()],
            hide_index=True,
            width="stretch",
        )
    else:
        st.caption("No headers")


def _request_query_rows(query_params: dict | list | None, url: str | None) -> list[dict]:
    """Combine explicit request parameters with query values embedded in its URL.

    Args:
        query_params (dict | list | None): Stored parameter mapping or row list.
        url (str | None): Request URL, possibly containing a query string.

    Returns:
        list[dict]: Parameter rows suitable for display, retaining duplicate URL keys.
    """
    if isinstance(query_params, dict):
        rows = [{"Key": str(key), "Value": str(value)} for key, value in query_params.items()]
    elif isinstance(query_params, list):
        rows = [
            {"Key": str(row.get("key", "")), "Value": str(row.get("value", ""))}
            for row in query_params
            if isinstance(row, dict) and row.get("key") and row.get("enabled", True)
        ]
    else:
        rows = []
    present_keys = {row["Key"] for row in rows}
    for key, value in parse_qsl(urlsplit(url or "").query, keep_blank_values=True):
        if key not in present_keys:
            rows.append({"Key": key, "Value": value})
    return rows


def _render_request_details(
    method: str | None, url: str | None, headers: dict | None, body, uid: str,
    query_params: dict | list | None = None,
) -> None:
    """Render request line, query parameters, headers, and body in compact tabs.

    Args:
        method (str | None): HTTP method.
        url (str | None): Request URL.
        headers (dict | None): Request headers.
        body (Any): Request payload.
        uid (str): Stable identifier for this request view.
        query_params (dict | list | None): Explicit query parameter values, if present.

    Returns:
        None: Writes request details to the Streamlit page.
    """
    st.code(f"{(method or 'GET').upper()} {url or ''}", language="http", wrap_lines=True)
    params_tab, headers_tab, body_tab = st.tabs(["Params", "Headers", "Body"])
    with params_tab:
        params = _request_query_rows(query_params, url)
        if params:
            st.dataframe(params, hide_index=True, width="stretch")
        else:
            st.caption("No query parameters")
    with headers_tab:
        _render_headers(headers)
    with body_tab:
        text, is_json = _pretty_payload(body)
        st.code(text or "(empty request body)", language="json" if is_json else "text", wrap_lines=True)


def _render_response_details(status, latency_ms, body, headers, uid: str) -> None:
    """Render response metadata, body, and headers with a raw/pretty switch.

    Args:
        status (Any): HTTP response status code.
        latency_ms (Any): Request duration in milliseconds.
        body (Any): Response payload.
        headers (dict | None): Response headers.
        uid (str): Stable identifier for the format selector.

    Returns:
        None: Writes the response view to the Streamlit page.
    """
    code = status if isinstance(status, int) else 0
    color = "green" if 200 <= code < 300 else "orange" if 300 <= code < 400 else "red"
    body_text, is_json = _pretty_payload(body)
    raw_body = body if isinstance(body, str) else json.dumps(body, ensure_ascii=False) if body is not None else ""
    size = len(raw_body.encode("utf-8"))
    size_label = f"{size} B" if size < 1024 else f"{size / 1024:.1f} KB"
    st.markdown(
        f":{color}-badge[{status if status is not None else '—'}] "
        f":gray-badge[{_format_latency(latency_ms)}] :gray-badge[{size_label}]"
    )
    body_tab, headers_tab = st.tabs(["Body", "Headers"])
    with body_tab:
        view_key = f"response_view_{uid}"
        st.session_state.setdefault(view_key, "Pretty")
        view = st.segmented_control(
            "Response format", ["Pretty", "Raw"], key=view_key,
            label_visibility="collapsed",
        ) or "Pretty"
        if not raw_body:
            st.caption("(empty response body)")
        elif view == "Pretty" and is_json:
            st.code(body_text, language="json", wrap_lines=True)
        else:
            st.code(raw_body, language="text", wrap_lines=True)
    with headers_tab:
        _render_headers(headers)


def _execute_test_case(tc: dict, notify: bool = True) -> dict:
    """Execute current in-memory case data and retain its result.

    Args:
        tc (dict): Test case with current assertion edits.

    Returns:
        dict: Backend execution result.
    """
    tc_id = tc.get("id")
    project = st.session_state.get("current_project") or {}
    assertions = {} if tc.get("is_flow") else _normalize_assertions(tc)
    payload = {kind: [dict(config) for config in configs] for kind, configs in assertions.items()}
    result = api_post("/api/v1/test-cases/execute", {
        "test_case_id": tc_id,
        "project_id": project.get("id"),
        "test_case": tc,
        "assertions": payload,
    })
    st.session_state.setdefault("executions", {})[tc_id] = result
    if project.get("id"):
        st.session_state.pop(f"tc_history_{project['id']}_{tc_id}", None)
    if notify:
        status = _test_case_status(result)
        label = tc.get("name") or "Test case"
        _queue_toast(
            f"{label}: {status.replace('_', ' ')}.",
            "error" if status in {"failed", "error"} else "success",
        )
    return result


def _mark_general_test_case(tc: dict, status: str) -> dict:
    """Persist a manual pass/fail mark and update the saved case's current badge."""
    project = st.session_state.get("current_project") or {}
    if not project.get("id"):
        raise ValueError("Save the project before recording a manual result.")
    result = api_post(
        f"/api/v1/projects/{project['id']}/test-cases/{tc['id']}/manual-result",
        {"status": status},
    )
    tc["manual_status"] = status
    st.session_state.setdefault("executions", {})[str(tc["id"])] = result
    st.session_state.pop(f"tc_history_{project['id']}_{tc['id']}", None)
    saved_cases = st.session_state.get("test_cases", [])
    for item in saved_cases:
        if str(item.get("id")) == str(tc["id"]):
            item["manual_status"] = status
    _queue_toast(f"{tc.get('name') or 'General scenario'} marked {status}.", "success" if status == "passed" else "error")
    return result


def _render_execution_result(result: dict, uid: str) -> None:
    """Render overall result detail with request and response side by side.

    Args:
        result (dict): Backend execution result.
        uid (str): Stable identifier for response controls.

    Returns:
        None: Writes execution results to the Streamlit page.
    """
    status = _test_case_status(result)
    latency = result.get("latency_ms") or sum(
        step.get("latency_ms", 0) for step in result.get("step_results", [])
    )
    st.markdown(f"{_status_badge(status)} :gray-badge[{_format_latency(latency)}]")
    if result.get("assertion_detail"):
        (st.success if status == "passed" else st.error)(result["assertion_detail"])
    if result.get("step_results"):
        return
    request_col, response_col = st.columns(2, gap="medium")
    with request_col, st.container(border=True):
        st.markdown("**Request**")
        _render_request_details(
            result.get("request_method"), result.get("request_url"),
            result.get("request_headers"), result.get("request_body"), f"{uid}_request",
            result.get("request_query_params"),
        )
    with response_col, st.container(border=True):
        st.markdown("**Response**")
        _render_response_details(
            result.get("response_status"), result.get("latency_ms"),
            result.get("response_body"), result.get("response_headers"), f"{uid}_response",
        )


def _render_flow_step(test_case: dict, step: dict, result: dict | None, index: int) -> None:
    """Render an editable flow step with request, mapping, assertion, and result controls."""
    steps = test_case.get("steps", [])
    order = index + 1
    step_id = step.setdefault("step_id", str(uuid.uuid4()))
    tc_id = test_case.get("id", "flow")
    uid = f"{tc_id}_{step_id}"
    open_key = f"step_open_{uid}"
    is_open = st.session_state.get(open_key, False)
    endpoint = step.setdefault("endpoint", {})
    status = _test_case_status(result) if result else "not_run"
    with st.container(border=True, key=f"tc-step-{uid}"):
        toggle_col, title_col, up_col, down_col, remove_col, status_col = st.columns(
            [0.35, 5, 0.45, 0.45, 0.45, 1.6], vertical_alignment="center",
        )
        toggle_col.button(
            " ", icon=":material/expand_more:" if is_open else ":material/chevron_right:",
            key=f"toggle_{uid}", type="tertiary", help="Expand or collapse step",
            on_click=_toggle_test_case_state, args=(open_key,),
        )
        title_col.markdown(
            f"**Step {order}** :blue-badge[{endpoint.get('method', 'GET')}] "
            f"`{_truncate(endpoint.get('url', ''), 68)}`"
        )
        if up_col.button(" ", icon=":material/arrow_upward:", key=f"step_up_{uid}", help="Move step earlier", disabled=index == 0):
            steps[index - 1], steps[index] = steps[index], steps[index - 1]
            for position, item in enumerate(steps, start=1):
                item["step_order"] = position
            st.session_state.get("executions", {}).pop(tc_id, None)
            st.rerun()
        if down_col.button(" ", icon=":material/arrow_downward:", key=f"step_down_{uid}", help="Move step later", disabled=index == len(steps) - 1):
            steps[index], steps[index + 1] = steps[index + 1], steps[index]
            for position, item in enumerate(steps, start=1):
                item["step_order"] = position
            st.session_state.get("executions", {}).pop(tc_id, None)
            st.rerun()
        if remove_col.button(" ", icon=":material/delete:", key=f"step_remove_{uid}", help="Remove step", disabled=len(steps) <= 1):
            steps.pop(index)
            for position, item in enumerate(steps, start=1):
                item["step_order"] = position
            st.session_state.get("executions", {}).pop(tc_id, None)
            st.rerun()
        status_col.markdown(
            f"{_status_badge(status)} :gray-badge[{_format_latency((result or {}).get('latency_ms'))}]"
        )
        if not is_open:
            return
        description_key = f"tc_step_description_{uid}"
        st.session_state.setdefault(description_key, str(step.get("description", "")))
        step["description"] = st.text_input("Step description", key=description_key)
        assertions_tab, request_tab, response_tab = st.tabs(["Assertions", "Request & mappings", "Response"])
        with assertions_tab:
            _render_test_case_assertions(step["assertions"], uid)
        with request_tab:
            _render_editable_test_request(endpoint, f"{uid}_request")
            if index == 0:
                st.caption("The first step starts the flow and has no earlier response to map.")
            else:
                _render_variable_mappings(step, uid)
        with response_tab:
            if result:
                if result.get("assertion_detail"):
                    (st.success if status == "passed" else st.error)(result["assertion_detail"])
                _render_response_details(
                    result.get("response_status"), result.get("latency_ms"),
                    result.get("response_body"), result.get("response_headers"), f"{uid}_response",
                )
            else:
                st.caption("Run the scenario to see this step's response.")


def _new_flow_step(saved_request: dict, order: int) -> dict:
    """Create an editable flow step by copying a saved project request.

    Args:
        saved_request (dict): Saved request configuration to copy.
        order (int): One-based position for the new step.

    Returns:
        dict: Flow step with copied request fields and default assertions.
    """
    endpoint = {
        "id": saved_request.get("id"),
        "name": saved_request.get("name", ""),
        "method": saved_request.get("method", "GET"),
        "url": saved_request.get("url", ""),
        "headers": _clean_request_rows(_request_rows(saved_request.get("headers", {}))),
        "query_params": _clean_request_rows(_request_rows(saved_request.get("query_params", {}))),
        "body": copy.deepcopy(saved_request.get("body")) if saved_request.get("include_body", True) else None,
    }
    step = {
        "step_id": str(uuid.uuid4()),
        "step_order": order,
        "endpoint_id": saved_request.get("id"),
        "endpoint": endpoint,
        "description": "",
        "assertions": {},
        "variable_mappings": [],
    }
    _normalize_assertions(step)
    return step


def _new_manual_test_case(
    saved_requests: list[dict], name: str, is_flow: bool,
) -> dict:
    """Build a manual case by copying one or more saved project requests.

    Args:
        saved_requests (list[dict]): Request(s) used by the new case.
        name (str): Optional user-supplied case name.
        is_flow (bool): Whether to create an ordered multi-step flow.

    Returns:
        dict: New editable case with a stable ID.

    Raises:
        ValueError: No saved requests were supplied.
    """
    if not saved_requests:
        raise ValueError("Choose at least one saved request.")
    display_name = name.strip()
    if is_flow:
        steps = [_new_flow_step(request, index) for index, request in enumerate(saved_requests, 1)]
        title = display_name or "Manual flow"
        case = {
            "id": str(uuid.uuid4()), "type": "manual", "name": title,
            "description": "", "is_flow": True, "steps": steps,
        }
        return case

    saved = saved_requests[0]
    url = str(saved.get("url", ""))
    title = display_name or saved.get("name") or url or "Manual test"
    body = copy.deepcopy(saved.get("body")) if saved.get("include_body", True) else None
    case = {
        "id": str(uuid.uuid4()), "type": "manual", "name": title,
        "description": "", "is_flow": False,
        "source_endpoint_id": saved.get("id"),
        "source_endpoint_name": saved.get("name") or url,
        "request": {
            "method": saved.get("method", "GET"), "url": url,
            "headers": copy.deepcopy(saved.get("headers", {})),
            "query_params": copy.deepcopy(saved.get("query_params", {})),
            "body": body,
        },
    }
    _normalize_assertions(case)
    return case


def _append_manual_test_case(test_case: dict) -> None:
    """Persist a manual case and open it in the Test Cases editor.

    Args:
        test_case (dict): New single or flow case to save by stable ID.

    Returns:
        None: Updates project state and queues a success toast.

    Raises:
        ValueError: No project is selected.
    """
    project = st.session_state.get("current_project") or {}
    project_id = project.get("id")
    if not project_id:
        raise ValueError("Select a project before creating a test case.")
    api_post(
        f"/api/v1/projects/{project_id}/test-cases/save",
        {"test_cases": [test_case]},
    )
    cases = st.session_state.setdefault("test_cases", [])
    cases.append(test_case)
    project.setdefault("test_cases", []).append(copy.deepcopy(test_case))
    st.session_state.setdefault("executions", {}).pop(test_case["id"], None)
    st.session_state[f"tc_selected_{test_case['id']}"] = True
    st.session_state[f"tc_open_{test_case['id']}"] = True
    st.session_state[f"tc_detail_tabs_{test_case['id']}"] = "Steps (1)" if test_case.get("is_flow") else "Assertions"
    _queue_toast("Manual flow added to the project." if test_case.get("is_flow") else "Manual test case added to the project.")


def _render_manual_case_builder(project: dict) -> None:
    """Render controls for creating manual cases from saved requests.

    Args:
        project (dict): Current project and its saved requests.

    Returns:
        None: Renders single-test and flow creation controls.
    """
    requests = project.get("endpoints", [])
    with st.popover(
        "Add manual test", icon=":material/add:", width="stretch",
        help="Create a single test or a flow from saved requests",
    ):
        st.markdown(
            "<div class='aa-popover-section'>Create from saved requests</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<div class='aa-popover-hint'>Build a request test or ordered flow from "
            "the latest saved request data.</div>",
            unsafe_allow_html=True,
        )
        if not requests:
            st.info(
                "Save a request in API Workspace before creating a manual test.",
                icon=":material/info:",
            )
            return
        st.markdown(
            "<div class='aa-popover-section'>1 · Case type</div>",
            unsafe_allow_html=True,
        )
        mode = st.segmented_control(
            "Case type", ["Single test", "Flow"],
            key=f"manual_case_mode_{project.get('id', 'local')}",
            label_visibility="collapsed",
        ) or "Single test"
        request_by_id = {item["id"]: item for item in requests}
        project_id = project.get("id", "local")
        if mode == "Single test":
            st.markdown(
                "<div class='aa-popover-section'>2 · Choose request</div>",
                unsafe_allow_html=True,
            )
            request_id = st.selectbox(
                "Saved request", list(request_by_id),
                label_visibility="collapsed",
                format_func=lambda item_id: (
                    f"{request_by_id[item_id].get('method', 'GET')} · "
                    f"{request_by_id[item_id].get('name') or request_by_id[item_id].get('url', 'Request')}"
                ),
                key=f"manual_single_request_{project_id}",
            )
            st.markdown(
                "<div class='aa-popover-section'>3 · Name</div>",
                unsafe_allow_html=True,
            )
            test_name = st.text_input(
                "Test case name", key=f"manual_single_name_{project_id}",
                label_visibility="collapsed",
                placeholder="Defaults to the saved request name or URL",
            )
            if st.button(
                "Create single test", key=f"manual_single_create_{project_id}",
                type="primary", icon=":material/add:", width="stretch",
            ):
                try:
                    test_case = _new_manual_test_case([request_by_id[request_id]], test_name, False)
                    _append_manual_test_case(test_case)
                    st.rerun()
                except Exception as exc:
                    st.error(f"Could not create test case: {exc}")
            return

        order_key = f"manual_flow_order_{project_id}"
        selected_key = f"manual_flow_selected_{project_id}"
        request_ids = [item["id"] for item in requests]
        order_ids = [item for item in st.session_state.get(order_key, []) if item in request_by_id]
        order_ids.extend(item for item in request_ids if item not in order_ids)
        selected_ids = set(st.session_state.get(selected_key, [])) & set(request_ids)
        st.session_state[order_key] = order_ids
        st.markdown(
            "<div class='aa-popover-section'>2 · Select and order requests</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<div class='aa-popover-hint'>Drag to reorder. Checked requests run in "
            "the order shown.</div>",
            unsafe_allow_html=True,
        )
        rows = [
            {
                "id": request_id,
                "method": request_by_id[request_id].get("method", "GET"),
                "name": request_by_id[request_id].get("name") or "Untitled request",
                "url": request_by_id[request_id].get("url", ""),
                "selected": request_id in selected_ids,
            }
            for request_id in order_ids
        ]
        order_result = render_request_order_list(
            rows, key=f"manual-flow-request-order-{project_id}",
        )
        changed = getattr(order_result, "rows_change", None)
        if isinstance(changed, dict):
            proposed = changed.get("order_ids", [])
            included = set(changed.get("selected_ids", []))
            if len(proposed) == len(request_ids) and set(proposed) == set(request_ids) and included <= set(request_ids):
                st.session_state[order_key] = proposed
                st.session_state[selected_key] = [item for item in proposed if item in included]
                st.rerun()
        st.markdown(
            "<div class='aa-popover-section'>3 · Name</div>",
            unsafe_allow_html=True,
        )
        flow_name = st.text_input(
            "Flow name", key=f"manual_flow_name_{project_id}",
            label_visibility="collapsed", placeholder="e.g. Create and review cart",
        )
        ordered_selected = [request_by_id[item] for item in order_ids if item in selected_ids]
        st.caption(f"{len(ordered_selected)} request(s) selected in flow order.")
        if st.button(
            "Create flow", key=f"manual_flow_create_{project_id}",
            type="primary", icon=":material/add:", width="stretch",
            disabled=not ordered_selected,
        ):
            try:
                test_case = _new_manual_test_case(ordered_selected, flow_name, True)
                _append_manual_test_case(test_case)
                st.rerun()
            except Exception as exc:
                st.error(f"Could not create flow: {exc}")


def _render_test_run_manager(project: dict, test_cases: list[dict]) -> str | None:
    """Render test-suite selection and persistence controls for the project.

    Args:
        project (dict): Current project and its saved test-suite summaries.
        test_cases (list[dict]): Cases currently displayed in the workspace.

    Returns:
        str | None: ID of the loaded run, if one is selected.
    """
    project_id = project.get("id")
    if not project_id:
        with st.popover(
            "Test suites", icon=":material/playlist_play:", width="stretch",
            help="Save and reuse named groups of test cases",
        ):
            st.info("Create or select a project first.", icon=":material/info:")
        return None
    runs = project.get("test_runs", [])
    run_by_id = {item["id"]: item for item in runs}
    picker_key = f"test_run_picker_{project_id}"
    name_key = f"test_run_name_{project_id}"
    loaded_key = f"test_run_loaded_{project_id}"
    pending_key = f"test_run_pending_picker_{project_id}"
    pending_name_key = f"test_run_pending_name_{project_id}"
    pending = st.session_state.pop(pending_key, None)
    if pending is not None:
        st.session_state[picker_key] = pending
    st.session_state.setdefault(picker_key, "")
    st.session_state.setdefault(loaded_key, st.session_state[picker_key])
    pending_name = st.session_state.pop(pending_name_key, None)
    if pending_name is not None:
        st.session_state[name_key] = pending_name

    with st.popover(
        "Test suites", icon=":material/playlist_play:", width="stretch",
        help="Load, save, update, or delete a named test suite",
    ):
        st.markdown(
            "<div class='aa-popover-section'>Test suite</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<div class='aa-popover-hint'>A suite uses the latest saved version of "
            "each selected case, so saved case updates carry forward.</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<div class='aa-popover-section'>1 · Load a suite</div>",
            unsafe_allow_html=True,
        )
        picker_col, name_col = st.columns([1.1, 2], vertical_alignment="bottom")
        options = [""] + list(run_by_id)
        with picker_col:
            chosen_run = st.selectbox(
                "Load a test suite", options, key=picker_key,
                format_func=lambda run_id: "New suite" if not run_id else run_by_id[run_id]["name"],
            )
        if chosen_run != st.session_state.get(loaded_key):
            included = set(run_by_id.get(chosen_run, {}).get("case_ids", []))
            for case in test_cases:
                st.session_state[f"tc_selected_{case.get('id')}"] = case.get("id") in included
            st.session_state[name_key] = run_by_id.get(chosen_run, {}).get("name", "")
            st.session_state[loaded_key] = chosen_run
        st.markdown(
            "<div class='aa-popover-section'>2 · Save current selection as a suite</div>",
            unsafe_allow_html=True,
        )
        with name_col:
            st.text_input("Suite name", key=name_key, placeholder="e.g. Checkout regression")

        selected_ids = [
            case.get("id") for case in test_cases
            if st.session_state.get(f"tc_selected_{case.get('id')}", True)
        ]
        save_col, delete_col, hint_col = st.columns([1.1, 0.8, 2.2], vertical_alignment="center")
        with save_col:
            save_label = "Update suite" if chosen_run else "Save suite"
            save_clicked = st.button(
                save_label, key=f"test_run_save_{project_id}",
                icon=":material/save:", type="primary", width="stretch",
                disabled=(not selected_ids and not chosen_run)
                or not st.session_state.get(name_key, "").strip(),
            )
        with delete_col:
            delete_clicked = st.button(
                "Delete suite", key=f"test_run_delete_{project_id}",
                icon=":material/delete:", width="stretch", disabled=not chosen_run,
            )
        with hint_col:
            st.caption(f"{len(selected_ids)} case(s) selected")

        if save_clicked:
            payload = {"name": st.session_state[name_key], "case_ids": selected_ids}
            try:
                saved_cases = api_get(f"/api/v1/projects/{project_id}/test-cases")
                saved_case_ids = {item.get("id") for item in saved_cases}
                new_cases = [
                    copy.deepcopy(case) for case in test_cases
                    if case.get("id") in selected_ids and case.get("id") not in saved_case_ids
                ]
                if new_cases:
                    api_post(
                        f"/api/v1/projects/{project_id}/test-cases/save",
                        {"test_cases": new_cases},
                    )
                    project.setdefault("test_cases", []).extend(new_cases)
                path = f"/api/v1/projects/{project_id}/test-runs"
                saved = api_put(f"{path}/{chosen_run}", payload) if chosen_run else api_post(path, payload)
                updated_runs = [item for item in runs if item.get("id") != saved["id"]]
                updated_runs.insert(0, saved)
                project["test_runs"] = updated_runs
                st.session_state[pending_key] = saved["id"]
                saved_note = f" and {len(new_cases)} new case(s)" if new_cases else ""
                _queue_toast(f"Test suite '{saved['name']}'{saved_note} saved.")
                st.rerun()
            except Exception as exc:
                st.error(f"Could not save test run: {exc}")
        if delete_clicked:
            try:
                api_delete(f"/api/v1/projects/{project_id}/test-runs/{chosen_run}")
                project["test_runs"] = [item for item in runs if item.get("id") != chosen_run]
                st.session_state[pending_key] = ""
                st.session_state[pending_name_key] = ""
                st.session_state[loaded_key] = None
                _queue_toast("Test suite deleted.")
                st.rerun()
            except Exception as exc:
                st.error(f"Could not delete test run: {exc}")
    return chosen_run or None


def _test_case_request_snapshot(test_case: dict):
    """Copy request configuration used to invalidate stale execution results."""
    field = "manual_steps" if test_case.get("case_kind") == "general" else "steps" if test_case.get("is_flow") else "request"
    return copy.deepcopy(test_case.get(field))


def _flaky_summary(outcomes: list[str]) -> dict:
    """Classify recent outcomes using the product rule of three of the latest ten."""
    recent = outcomes[:10]
    passed = sum(value == "passed" for value in recent)
    non_passed = sum(value in {"failed", "error"} for value in recent)
    return {"flaky": len(recent) >= 3 and passed > 0 and non_passed > 0,
            "runs": len(recent), "passed": passed, "non_passed": non_passed}


def _render_test_case_history(tc: dict, project_id: str) -> None:
    """Load and display run snapshots and flakiness evidence for a saved case."""
    case_id = str(tc.get("id", ""))
    cache_key = f"tc_history_{project_id}_{case_id}"
    load_col, note_col = st.columns([1, 4], vertical_alignment="center")
    if load_col.button("Load history" if cache_key not in st.session_state else "Refresh history",
                       key=f"load_history_{project_id}_{case_id}", icon=":material/history:"):
        try:
            payload = _raw_get(f"/api/v1/projects/{project_id}/test-cases/{case_id}/history?limit=100")
            st.session_state[cache_key] = payload.get("executions", []) if isinstance(payload, dict) else []
            st.rerun()
        except Exception as exc:
            note_col.error(f"Could not load execution history: {exc}")
    if cache_key not in st.session_state:
        note_col.caption("Execution records include the exact saved or in-session configuration that ran.")
        return
    history = st.session_state[cache_key]
    outcomes = [str(item.get("status", "error")).lower() for item in history]
    summary = _flaky_summary(outcomes)
    badge = "Flaky" if summary["flaky"] else "No flaky pattern detected"
    st.markdown(
        f"**{badge}** · latest {summary['runs']} run(s): {summary['passed']} passed, "
        f"{summary['non_passed']} failed or errored. Flaky requires at least 3 of the latest 10 "
        "with both passing and non-passing outcomes."
    )
    if not history:
        st.caption("No saved executions yet.")
        return
    st.dataframe([{
        "Executed": item.get("created_at", "Unknown"),
        "Outcome": str(item.get("status", "error")).upper(),
        "Latency (ms)": item.get("latency_ms") or sum(
            step.get("latency_ms", 0) for step in item.get("step_results", [])
        ),
        "Assertion details": item.get("assertion_detail", ""),
    } for item in history], hide_index=True, width="stretch")
    if tc.get("is_flow") or isinstance(tc.get("steps"), list):
        step_runs = {}
        for execution in history:
            snapshot = execution.get("test_case_snapshot", {}) or {}
            for index, step in enumerate(snapshot.get("steps", []) or [], start=1):
                step_id = str(step.get("step_id") or f"legacy-{index}")
                outcome = next((item for item in execution.get("step_results", [])
                                if (item.get("step_id") and str(item.get("step_id")) == step_id)
                                or (not item.get("step_id") and item.get("step_order") == index)), None)
                if outcome:
                    step_runs.setdefault(step_id, {"name": step.get("description") or f"Step {index}", "outcomes": []})
                    step_runs[step_id]["outcomes"].append(str(outcome.get("status", "error")).lower())
        if step_runs:
            st.markdown("**Flow step history and flakiness**")
            st.dataframe([{
                "Step": value["name"],
                "Flaky": "Yes" if _flaky_summary(value["outcomes"])["flaky"] else "No",
                "Latest runs": _flaky_summary(value["outcomes"])["runs"],
                "Passed": _flaky_summary(value["outcomes"])["passed"],
                "Failed or errored": _flaky_summary(value["outcomes"])["non_passed"],
            } for value in step_runs.values()], hide_index=True, width="stretch")
    with st.expander("Executed configuration and response details"):
        selected = st.selectbox(
            "Execution", list(range(len(history))),
            format_func=lambda idx: f"{history[idx].get('created_at', 'Unknown')} · {str(history[idx].get('status', 'error')).upper()}",
            key=f"history_detail_{project_id}_{case_id}",
        )
        item = history[selected]
        st.json({
            "test_case_snapshot": item.get("test_case_snapshot"),
            "result": {key: value for key, value in item.items() if key not in {"test_case_snapshot", "execution_id", "created_at"}},
        })


def render_test_case_card(tc: dict, index: int, read_only: bool = False) -> dict:
    """Render a selectable test card with separated detail views.

    Args:
        tc (dict): Test case configuration and editable assertions.
        index (int): Position in the visible test-case list.

    Returns:
        dict: Updated test case containing any assertion edits.
    """
    if read_only:
        tc = copy.deepcopy(tc)
    tc_id = tc.get("id", f"tc_{index}")
    is_flow = bool(tc.get("is_flow"))
    is_general = tc.get("case_kind") == "general"
    result = st.session_state.get("executions", {}).get(tc_id)
    status = _test_case_status(result)
    if is_general and status == "not_run":
        status = str(tc.get("manual_status") or "not_run")
    open_key = f"tc_open_{tc_id}"
    is_open = st.session_state.get(open_key, False)
    selected_key = f"tc_selected_{tc_id}"
    st.session_state.setdefault(selected_key, True)

    if is_general:
        assertions = {}
    elif not is_flow:
        assertions = _normalize_assertions(tc)
    else:
        assertions = {}
        for step in _normalise_flow_steps(tc):
            step["assertions"] = _normalize_assertions(step)
    project = st.session_state.get("current_project") or {}
    snapshot_key = f"tc_saved_request_snapshot_{project.get('id', 'local')}_{tc_id}"
    st.session_state.setdefault(snapshot_key, _test_case_request_snapshot(tc))

    with st.container(border=True, key=f"tc-card-{status}-{tc_id}"):
        toggle_col, select_col, title_col, status_col, run_col = st.columns(
            [0.4, 0.4, 4.8, 1.7, 2.0 if is_general else 1.1], vertical_alignment="center"
        )
        with toggle_col:
            st.button(
                " ", icon=":material/expand_more:" if is_open else ":material/chevron_right:",
                key=f"tc_toggle_{tc_id}", type="tertiary", help="Expand or collapse",
                on_click=_toggle_test_case_state, args=(open_key,),
            )
        with select_col:
            st.checkbox("Select for batch run", key=selected_key, label_visibility="collapsed", help="Include in Run selected")
        with title_col:
            kind = ":violet-badge[FLOW]" if is_flow else ":gray-badge[GENERAL]" if is_general else f":blue-badge[{str(tc.get('type', 'test')).upper()}]"
            st.markdown(f"**{index + 1}. {tc.get('name', 'Unnamed')}** {kind}")
        with status_col:
            latency = (result or {}).get("latency_ms") or sum(
                item.get("latency_ms", 0) for item in (result or {}).get("step_results", [])
            )
            history_key = f"tc_history_{project.get('id', '')}_{tc_id}"
            cached_history = st.session_state.get(history_key)
            cached_flaky = _flaky_summary([
                str(item.get("status", "error")).lower() for item in cached_history
            ]) if cached_history is not None else {"flaky": False}
            flaky_badge = " :orange-badge[FLAKY]" if cached_flaky["flaky"] else ""
            st.markdown(f"{_status_badge(status)} :gray-badge[{_format_latency(latency)}]{flaky_badge}")
        with run_col:
            if is_general:
                passed_col, failed_col = st.columns(2, gap="small")
                passed_clicked = passed_col.button("Passed", key=f"manual_pass_{tc_id}", type="secondary", help="Record a manual pass", width="stretch")
                failed_clicked = failed_col.button("Failed", key=f"manual_fail_{tc_id}", type="secondary", help="Record a manual failure", width="stretch")
                run_clicked = False
            else:
                run_clicked = st.button(
                    "Run", icon=":material/play_arrow:", key=f"exec_{tc_id}",
                    type="primary", width="stretch",
                )

        if tc.get("description"):
            st.caption(tc["description"])
        if is_open:
            requirements_key = f"tc_business_requirements_{tc_id}"
            st.session_state.setdefault(
                requirements_key, str(tc.get("business_requirements") or ""),
            )
            with st.expander(
                "Generation requirements",
                expanded=bool(st.session_state[requirements_key]),
            ):
                tc["business_requirements"] = st.text_area(
                    "Requirements used for this generation",
                    key=requirements_key,
                    height=110,
                    help="Review, update, or extend these requirements. Save changes to keep your edits.",
                    placeholder="No requirements were recorded. Add context for future reference.",
                )
        if is_general and (passed_clicked or failed_clicked):
            try:
                _mark_general_test_case(tc, "passed" if passed_clicked else "failed")
                st.rerun()
            except Exception as exc:
                st.error(f"Could not record manual result: {exc}")
        if run_clicked:
            with st.spinner("Executing scenario sequentially..." if is_flow else "Executing request..."):
                try:
                    _execute_test_case(tc)
                    st.session_state[open_key] = True
                    detail_tab_key = f"tc_detail_tabs_{tc_id}"
                    st.session_state[detail_tab_key] = "Scenario result" if is_flow else "Result"
                    st.rerun()
                except Exception as exc:
                    st.error(f"Execution failed: {exc}")

        if is_open:
            if read_only:
                st.info("This is a historical revision. Its test cases are read only.")
                history_tab, config_tab = st.tabs(["History", "Revision snapshot"])
                with history_tab:
                    _render_test_case_history(tc, project.get("id", ""))
                with config_tab:
                    st.json({key: value for key, value in tc.items() if key not in {"id"}})
                return tc
            if is_general:
                st.markdown("**Manual steps**")
                for step_index, step in enumerate(tc.get("manual_steps", []), start=1):
                    st.markdown(f"{step_index}. {step}")
                if tc.get("manual_status"):
                    st.caption(f"Current manually recorded result: {tc['manual_status'].upper()}")
                with st.expander("History", expanded=False):
                    _render_test_case_history(tc, project.get("id", ""))
                return tc
            save_notice_key = f"tc_save_notice_{project.get('id', 'local')}_{tc_id}"
            if notice := st.session_state.pop(save_notice_key, None):
                _queue_toast(notice)
            name_key = f"tc_name_{tc_id}"
            description_key = f"tc_description_{tc_id}"
            st.session_state.setdefault(name_key, str(tc.get("name", "")))
            st.session_state.setdefault(description_key, str(tc.get("description", "")))
            title_col, description_col = st.columns([1, 2])
            tc["name"] = title_col.text_input("Test case name", key=name_key)
            tc["description"] = description_col.text_input("Description", key=description_key)
            if is_flow:
                step_results = {
                    item.get("step_order"): item
                    for item in (result or {}).get("step_results", [])
                }
                detail_tab_key = f"tc_detail_tabs_{tc_id}"
                steps_tab, summary_tab, history_tab = st.tabs(
                    [f"Steps ({len(tc.get('steps', []))})", "Scenario result", "History"],
                    key=detail_tab_key, on_change="rerun",
                )
                with steps_tab:
                    steps = _normalise_flow_steps(tc)
                    project_requests = project.get("endpoints", [])
                    if project_requests:
                        request_by_id = {item["id"]: item for item in project_requests}
                        add_col, add_button_col = st.columns([4, 1], vertical_alignment="bottom")
                        selected_request_id = add_col.selectbox(
                            "Add saved request as a step",
                            list(request_by_id),
                            format_func=lambda request_id: (
                                f"{request_by_id[request_id].get('method', 'GET')} · "
                                f"{request_by_id[request_id].get('name') or request_by_id[request_id].get('url', 'Request')}"
                            ),
                            key=f"tc_add_step_request_{tc_id}",
                        )
                        if add_button_col.button(
                            "Add step", key=f"tc_add_step_{tc_id}",
                            icon=":material/add:", type="primary", width="stretch",
                        ):
                            steps.append(_new_flow_step(request_by_id[selected_request_id], len(steps) + 1))
                            st.session_state.get("executions", {}).pop(tc_id, None)
                            st.rerun()
                    else:
                        st.info("Save a request in API Workspace before adding it to this flow.")
                    for step_index, step in enumerate(steps):
                        _render_flow_step(
                            tc, step, step_results.get(step.get("step_order")), step_index,
                        )
                with summary_tab:
                    if result:
                        _render_execution_result(result, tc_id)
                        for step in _normalise_flow_steps(tc):
                            step_result = step_results.get(step.get("step_order")) or {}
                            step_col, url_col, result_col = st.columns([0.6, 5, 1.4], vertical_alignment="center")
                            step_col.markdown(f"**{step.get('step_order', '?')}**")
                            endpoint = step.get("endpoint", {}) or {}
                            url_col.markdown(f":blue-badge[{endpoint.get('method', 'GET')}] `{endpoint.get('url', '')[:72]}`")
                            result_col.markdown(_status_badge(step_result.get("status")))
                    else:
                        st.caption("Run this scenario to see the overall and per-step results.")
                with history_tab:
                    _render_test_case_history(tc, project.get("id", ""))
            else:
                request = tc.get("request", {}) or {}
                detail_tab_key = f"tc_detail_tabs_{tc_id}"
                assertion_tab, request_tab, result_tab, history_tab = st.tabs(
                    ["Assertions", "Request", "Result", "History"],
                    key=detail_tab_key, on_change="rerun",
                )
                with assertion_tab:
                    _render_test_case_assertions(assertions, tc_id)
                with request_tab:
                    _render_editable_test_request(request, f"{tc_id}_request")
                with result_tab:
                    if result:
                        _render_execution_result(result, tc_id)
                    else:
                        st.caption("Run this test to inspect its response and assertion results.")
                with history_tab:
                    _render_test_case_history(tc, project.get("id", ""))

            delete_col, save_col, save_hint_col = st.columns([1, 1.35, 4], vertical_alignment="center")
            with delete_col:
                if st.button("Delete", key=f"delete_tc_{tc_id}", icon=":material/delete:", help="Delete test case"):
                    current_project = st.session_state.get("current_project") or {}
                    try:
                        if current_project:
                            api_delete(f"/api/v1/projects/{current_project['id']}/test-cases/{tc_id}")
                        st.session_state["test_cases"] = [item for item in st.session_state["test_cases"] if item.get("id") != tc_id]
                        st.session_state.get("executions", {}).pop(tc_id, None)
                        _queue_toast("Test case deleted.")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Could not delete test case: {exc}")
            with save_col:
                save_case_clicked = st.button(
                    "Save changes", key=f"save_tc_{tc_id}",
                    icon=":material/save:", type="primary", width="stretch",
                    disabled=not project.get("id"),
                )
                if save_case_clicked:
                    try:
                        saved = api_put(
                            f"/api/v1/projects/{project['id']}/test-cases/{tc_id}", tc,
                        )
                        tc.update(saved)
                        new_snapshot = _test_case_request_snapshot(tc)
                        if st.session_state[snapshot_key] != new_snapshot:
                            st.session_state.get("executions", {}).pop(tc_id, None)
                        st.session_state[snapshot_key] = new_snapshot
                        project_cases = project.get("test_cases", [])
                        case_found = False
                        for case_index, saved_case in enumerate(project_cases):
                            if saved_case.get("id") == tc_id:
                                project_cases[case_index] = copy.deepcopy(saved)
                                case_found = True
                                break
                        if not case_found:
                            project_cases.append(copy.deepcopy(saved))
                        _queue_toast("Test case changes saved to the project.")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Could not save test case changes: {exc}")
            with save_hint_col:
                st.caption("Requirements, request, step, mapping, and assertion edits stay in this session until you save changes.")
    return tc


def _select_all_test_cases(test_cases: list[dict], selected: bool) -> None:
    """Set batch-run selection for all supplied test cases.

    Args:
        test_cases (list[dict]): Cases whose selection state to update.
        selected (bool): Whether each case should be selected.

    Returns:
        None: Updates Streamlit session state.
    """
    for tc in test_cases:
        st.session_state[f"tc_selected_{tc.get('id')}"] = selected


def _select_all_generation_requests(endpoints: list[dict], selected: bool) -> None:
    """Set generation selection for every eligible request.

    Args:
        endpoints (list[dict]): Eligible saved requests.
        selected (bool): Whether each request should be selected.

    Returns:
        None: Updates Streamlit session state.
    """
    for endpoint in endpoints:
        st.session_state[f"generation_selected_{endpoint.get('id')}"] = selected


def _test_case_sort_key(tc: dict) -> int:
    """Return the numeric suffix of a generated test-case ID.

    Args:
        tc (dict): Test case to sort.

    Returns:
        int: Numeric ID suffix or zero when the ID has no numeric suffix.
    """
    tc_id = str(tc.get("id", ""))
    try:
        return int(tc_id.rsplit("_", 1)[-1])
    except (ValueError, AttributeError):
        return 0


def _deduplicate_test_cases(test_cases: list[dict]) -> list[dict]:
    """Keep the latest payload for each stable case ID, preserving list order.

    Args:
        test_cases (list[dict]): Cases that may contain repeated IDs.

    Returns:
        list[dict]: One case per ID, with the last payload retained.
    """
    unique_cases = {}
    for index, test_case in enumerate(test_cases):
        case_id = test_case.get("id")
        key = str(case_id) if case_id else f"__missing_id_{index}"
        unique_cases[key] = test_case
    return list(unique_cases.values())


def _merge_generated_test_cases(existing: list[dict], generated: list[dict]) -> list[dict]:
    """Append generated cases while retaining existing cases and deduplicating by ID.

    Args:
        existing (list[dict]): Current project cases in the frontend session.
        generated (list[dict]): Newly generated cases returned by the API.

    Returns:
        list[dict]: Existing and new cases, with the latest payload for each ID.
    """
    return _deduplicate_test_cases([*existing, *generated])


def _url_route_matches(endpoint_url: str, test_url: str) -> bool:
    """Match a generated test URL against a saved endpoint route template.

    Args:
        endpoint_url (str): Saved endpoint URL or OpenAPI path template.
        test_url (str): URL from a generated legacy test case.

    Returns:
        bool: Whether the request path matches the saved route.
    """
    template = (urlsplit(endpoint_url).path or endpoint_url).rstrip("/") or "/"
    candidate = (urlsplit(test_url).path or test_url).rstrip("/") or "/"
    escaped = re.escape(template)
    escaped = re.sub(r"\\\{[^/]+?\\\}", r"[^/]+", escaped)
    return bool(re.fullmatch(escaped, candidate))


def _resolve_saved_endpoint(
    endpoint_id: str | None, url: str, method: str, endpoints: list[dict],
) -> dict | None:
    """Resolve case provenance by saved endpoint ID, then URL route and method.

    Args:
        endpoint_id (str | None): Stable saved request ID, when present.
        url (str): Request URL stored in the case or flow step.
        method (str): HTTP method stored in the case or flow step.
        endpoints (list[dict]): Saved project endpoint records.

    Returns:
        dict | None: Matching saved endpoint or None when provenance is unknown.
    """
    endpoint = next((item for item in endpoints if item.get("id") == endpoint_id), None)
    if endpoint or not url:
        return endpoint
    matches = [item for item in endpoints if _url_route_matches(item.get("url", ""), url)]
    method_matches = [item for item in matches if str(item.get("method", "")).upper() == str(method).upper()]
    return (method_matches or matches or [None])[0]


def _case_step_endpoints(test_case: dict, endpoints: list[dict]) -> list[dict]:
    """Return unique saved endpoints represented by a single case or flow steps.

    Args:
        test_case (dict): Single test or flow scenario.
        endpoints (list[dict]): Saved project endpoint records.

    Returns:
        list[dict]: Resolved endpoints in first-seen request order.
    """
    resolved = []
    if test_case.get("is_flow") or isinstance(test_case.get("steps"), list):
        requests = []
        for step in test_case.get("steps", []):
            if not isinstance(step, dict):
                continue
            endpoint = step.get("endpoint") or {}
            requests.append((
                step.get("endpoint_id") or endpoint.get("id"),
                endpoint.get("url", ""), endpoint.get("method", ""),
            ))
    else:
        request = test_case.get("request") or {}
        requests = [(test_case.get("source_endpoint_id"), request.get("url", ""), request.get("method", ""))]

    seen = set()
    for endpoint_id, url, method in requests:
        endpoint = _resolve_saved_endpoint(endpoint_id, str(url or ""), str(method or ""), endpoints)
        if endpoint and endpoint.get("id") not in seen:
            seen.add(endpoint.get("id"))
            resolved.append(endpoint)
    return resolved


def _filter_test_cases_by_scope(
    test_cases: list[dict], endpoints: list[dict], run_ids: list[str],
    runs: list[dict], collection_ids: list[str], endpoint_ids: list[str],
) -> list[dict]:
    """Apply run, collection, and endpoint filters to cases without duplicating flows.

    Args:
        test_cases (list[dict]): All project cases.
        endpoints (list[dict]): Saved project endpoint records.
        run_ids (list[str]): Selected test-suite IDs, combined as alternatives.
        runs (list[dict]): Project test-suite records.
        collection_ids (list[str]): Selected collection IDs, combined as alternatives.
        endpoint_ids (list[str]): Selected endpoint IDs, combined as alternatives.

    Returns:
        list[dict]: Cases satisfying every active filter category.
    """
    selected_run_case_ids = {
        case_id for run in runs if run.get("id") in run_ids
        for case_id in run.get("case_ids", [])
    }
    filtered = []
    for case in test_cases:
        if run_ids and case.get("id") not in selected_run_case_ids:
            continue
        case_endpoints = _case_step_endpoints(case, endpoints)
        if endpoint_ids or collection_ids:
            if case.get("case_kind") == "general":
                case_collection_id = str(
                    case.get("case_collection_id") or GENERAL_CASE_COLLECTION_ID
                )
                if endpoint_ids or (
                    collection_ids
                    and case_collection_id not in collection_ids
                ):
                    continue
                filtered.append(case)
                continue
            matching_endpoints = [
                endpoint for endpoint in case_endpoints
                if (not endpoint_ids or endpoint.get("id") in endpoint_ids)
                and (not collection_ids or endpoint.get("collection_id") in collection_ids)
            ]
            if not matching_endpoints:
                continue
        filtered.append(case)
    return filtered


def _clear_test_case_filters(project_id: str) -> None:
    """Clear project-scoped case filters and the execution-result filter.

    Args:
        project_id (str): Project namespace for the filter widget state.

    Returns:
        None: Resets filter selections in Streamlit session state.
    """
    for name in ("runs", "collections", "endpoints"):
        st.session_state[f"tc_scope_{name}_{project_id}"] = []
    st.session_state["test_case_filter"] = "All"


def _flow_provenance_label(test_case: dict, endpoints: list[dict], collections: list[dict]) -> str:
    """Format every endpoint and collection used by a flow for its visible card group.

    Args:
        test_case (dict): Flow scenario whose steps provide provenance.
        endpoints (list[dict]): Saved project endpoint records.
        collections (list[dict]): Saved project collection records.

    Returns:
        str: Readable endpoint and collection provenance caption.
    """
    case_endpoints = _case_step_endpoints(test_case, endpoints)
    collection_names = {item.get("id"): item.get("name", "Collection") for item in collections}
    endpoint_labels = [
        f"{item.get('method', 'GET')} {item.get('name') or item.get('url') or 'Request'}"
        for item in case_endpoints
    ]
    collection_labels = list(dict.fromkeys(
        collection_names.get(item.get("collection_id"), "Unassigned collection")
        for item in case_endpoints
    ))
    parts = []
    if endpoint_labels:
        parts.append("Endpoints: " + " → ".join(endpoint_labels))
    if collection_labels:
        parts.append("Collections: " + ", ".join(collection_labels))
    return " · ".join(parts) or "No saved endpoint provenance"


def _group_test_cases_by_endpoint(
    test_cases: list[dict], endpoints: list[dict] | None = None,
) -> list[tuple[str, str, list[dict]]]:
    """Group single tests by source endpoint and keep flow scenarios together.

    Args:
        test_cases (list[dict]): Visible tests after status filtering.

    Returns:
        list[tuple[str, str, list[dict]]]: Ordered group key, heading, and cases.
    """
    if endpoints is None:
        project = st.session_state.get("current_project") or {}
        endpoints = project.get("endpoints", [])
    groups: dict[str, tuple[str, list[dict]]] = {}

    for tc in test_cases:
        if tc.get("case_kind") == "general":
            key = f"general:{tc.get('case_collection_id') or GENERAL_CASE_COLLECTION_ID}"
            title = str(tc.get("case_collection_name") or GENERAL_CASE_COLLECTION_NAME)
        elif tc.get("is_flow"):
            key, title = "__flows__", "Flow scenarios"
        else:
            request = tc.get("request") or {}
            test_url = str(request.get("url") or "")
            endpoint = _resolve_saved_endpoint(
                tc.get("source_endpoint_id"), test_url,
                str(request.get("method", "")), endpoints,
            )
            endpoint_id = endpoint.get("id") if endpoint else None

            endpoint_name = (
                tc.get("source_endpoint_name")
                or (endpoint or {}).get("name")
                or (endpoint or {}).get("url")
                or test_url
                or "Unassigned endpoint"
            )
            key = f"endpoint:{endpoint_id}" if endpoint_id else f"endpoint-name:{endpoint_name}"
            title = endpoint_name

        if key not in groups:
            groups[key] = (title, [])
        groups[key][1].append(tc)

    endpoint_group_order = [f"endpoint:{item.get('id')}" for item in endpoints]
    ordered_keys = [key for key in endpoint_group_order if key in groups]
    ordered_keys.extend(
        key for key in groups
        if key not in ordered_keys and key != "__flows__"
    )
    if "__flows__" in groups:
        ordered_keys.append("__flows__")
    return [(key, groups[key][0], groups[key][1]) for key in ordered_keys]


def _generation_requests_in_order(
    endpoints_by_id: dict[str, dict], ordered_ids: list[str], selected_ids: set[str],
) -> list[dict]:
    """Return only selected generation requests in their persisted order.

    Args:
        endpoints_by_id (dict[str, dict]): Eligible requests indexed by stable ID.
        ordered_ids (list[str]): Full project ordering.
        selected_ids (set[str]): IDs checked for this generation run.

    Returns:
        list[dict]: Selected requests ordered as they should be generated.
    """
    return [endpoints_by_id[request_id] for request_id in ordered_ids
            if request_id in endpoints_by_id and request_id in selected_ids]


def _generate_selected_cases(
    mode: str, selected: list[dict], business_req: str,
    example_test_case_ids: list[str] | None = None,
    case_collection_id: str | None = None,
    case_collection_name: str | None = None,
) -> dict:
    """Call the matching generation route for selected requests.

    Args:
        mode (str): Single, Flow, or General generation mode.
        selected (list[dict]): Ordered saved request configurations.
        business_req (str): Optional business requirements text.
        example_test_case_ids (list[str] | None): Existing cases used as generation examples.

    Returns:
        dict: Generation response envelope.
    """
    project = st.session_state.get("current_project") or {}
    if mode == "General":
        return api_post("/api/v1/test-cases/generate", {
            "mode": "General", "business_requirements": business_req,
            "project_id": project.get("id"),
            "case_collection_id": case_collection_id,
            "case_collection_name": case_collection_name,
        })
    if mode == "Flow":
        payload = {
            "endpoints": selected,
            "business_requirements": business_req or None,
            "project_id": project.get("id"),
            "example_test_case_ids": example_test_case_ids or [],
        }
        route = (
            f"/api/v1/projects/{project['id']}/test-cases/generate-flow"
            if project else "/api/v1/test-cases/generate-flow"
        )
        return api_post(route, payload)

    payload = {
        "endpoints": selected,
        "mode": "Single",
        "business_requirements": business_req or None,
        "project_id": project.get("id"),
        "example_test_case_ids": example_test_case_ids or [],
    }
    return api_post("/api/v1/test-cases/generate", payload)


def _accept_generation_response(response, mode: str) -> list[dict]:
    """Merge returned cases and retain any user-actionable clarification round."""
    if isinstance(response, list):
        envelope = {"test_cases": response, "clarification_questions": []}
    elif isinstance(response, dict):
        envelope = response
    else:
        raise ValueError("Generation API returned an unsupported response shape.")
    cases = envelope.get("test_cases", [])
    if not isinstance(cases, list):
        raise ValueError("Generation response did not contain a test_cases list.")
    archived_ids = {str(item) for item in envelope.get("archived_case_ids", [])}
    activity_id = str((envelope.get("activity") or {}).get("id") or "")
    if archived_ids and activity_id:
        for collection in (
            st.session_state.get("test_cases", []),
            (st.session_state.get("current_project") or {}).get("test_cases", []),
        ):
            for case in collection:
                if str(case.get("id")) in archived_ids:
                    case["superseded_by_activity_id"] = activity_id
    st.session_state["test_cases"] = _merge_generated_test_cases(
        st.session_state.get("test_cases", []), cases,
    )
    for case in cases:
        st.session_state[f"tc_selected_{case.get('id')}"] = True
    questions = envelope.get("clarification_questions", [])
    activity = envelope.get("activity") or {}
    if questions and activity.get("id"):
        pending = st.session_state.setdefault("generation_clarification_rounds", [])
        pending[:] = [item for item in pending if item.get("activity_id") != activity["id"]]
        pending.append({
            "activity_id": activity["id"], "questions": questions,
            "mode": mode, "revision": envelope.get("revision"),
        })
    return cases


def _render_generation_clarifications(project_id: str) -> None:
    """Collect answers to prior LLM questions and submit explicit refinement actions."""
    if project_id:
        cache_key = f"generation_clarifications_restored_{project_id}"
        if not st.session_state.get(cache_key):
            try:
                records = _normalise_generation_activity_records(api_get(
                    f"/api/v1/projects/{project_id}/generation-activity?limit=100"
                ))
                followed_ids = {str(item.get("follow_up_of")) for item in records if item.get("follow_up_of")}
                saved_ids = {
                    str(item.get("id")) for item in st.session_state.get("test_cases", [])
                    if item.get("id")
                }
                pending = st.session_state.setdefault("generation_clarification_rounds", [])
                known_ids = {str(item.get("activity_id")) for item in pending}
                for record in records:
                    activity_id = str(record.get("id") or "")
                    generated_ids = {str(item) for item in record.get("generated_case_ids", [])}
                    questions = record.get("clarification_questions", [])
                    if (
                        activity_id and activity_id not in followed_ids and activity_id not in known_ids
                        and record.get("status") == "succeeded" and questions
                        and generated_ids.intersection(saved_ids)
                    ):
                        pending.append({
                            "activity_id": activity_id,
                            "questions": questions,
                            "mode": record.get("mode", "Generation"),
                        })
                st.session_state[cache_key] = True
            except Exception as exc:
                st.caption(f"Could not restore clarification questions: {exc}")
    rounds = st.session_state.get("generation_clarification_rounds", [])
    if not project_id or not rounds:
        return
    for round_item in list(rounds):
        activity_id = round_item.get("activity_id")
        questions = round_item.get("questions") or []
        if not activity_id or not questions:
            continue
        with st.expander(f"Clarifications needed · {round_item.get('mode', 'Generation')}", expanded=True):
            st.caption("Answer the questions and request a refined output. Earlier output stays in activity history.")
            answers = {}
            for index, question in enumerate(questions, start=1):
                answers[str(index)] = st.text_area(
                    str(question), key=f"clarification_{activity_id}_{index}", height=70,
                )
            if st.button("Refine generated cases", key=f"refine_{activity_id}", type="primary"):
                if not any(value.strip() for value in answers.values()):
                    st.warning("Answer at least one clarification question before refining.")
                    continue
                try:
                    with st.spinner("Refining test cases with AI. Please wait…"):
                        response = api_post(
                            f"/api/v1/projects/{project_id}/generation-activity/follow-up",
                            {"source_activity_id": activity_id, "answers": answers},
                        )
                        mode = round_item.get("mode", "Generation")
                        cases = _accept_generation_response(response, mode)
                        if response.get("revision"):
                            project = st.session_state.get("current_project") or {}
                            project.setdefault("test_case_revisions", []).append(response["revision"])
                        rounds[:] = [item for item in rounds if item.get("activity_id") != activity_id]
                        _queue_toast(f"Refined output saved with {len(cases)} case(s).")
                        st.rerun()
                except Exception as exc:
                    st.error(f"Could not refine generated cases: {exc}")


def render_generation_panel() -> None:
    """Render request selection, optional requirements, and generation controls.

    Returns:
        None: Writes the generation workspace to the Streamlit page.
    """
    endpoints = st.session_state.get("endpoints", [])
    st.subheader("Generate test cases")
    st.session_state.setdefault("test_generation_mode", "Single")
    mode = st.segmented_control(
        "Generation mode", ["General", "Single", "Flow"],
        key="test_generation_mode",
        help="General creates manually executed scenarios from requirements. Single creates request tests. Flow executes selected requests in order.",
    ) or "Single"

    project = st.session_state.get("current_project") or {}
    project_id = project.get("id")
    requests_by_id = {endpoint["id"]: endpoint for endpoint in endpoints}
    eligible_ids = [endpoint["id"] for endpoint in endpoints]
    current_order = [
        request_id for request_id in st.session_state.get("generation_order_ids", [])
        if request_id in requests_by_id
    ]
    current_order.extend(request_id for request_id in eligible_ids if request_id not in current_order)
    st.session_state["generation_order_ids"] = current_order

    for endpoint in endpoints:
        st.session_state.setdefault(f"generation_selected_{endpoint.get('id')}", True)

    selected = []
    if mode != "General":
        with st.container(border=True):
            select_col, all_col, clear_col = st.columns([4.5, 1, 1], vertical_alignment="center")
            with select_col:
                st.markdown("**Select requests for this run**")
                st.caption("Drag any request to set the saved order. Checked requests are used for this run.")
            with all_col:
                st.button(
                    "Select all", key="generation_select_all", width="stretch",
                    on_click=_select_all_generation_requests, args=(endpoints, True),
                )
            with clear_col:
                st.button(
                    "Clear", key="generation_select_none", width="stretch",
                    on_click=_select_all_generation_requests, args=(endpoints, False),
                )

            order_rows = [
                {
                    "id": request_id,
                    "method": requests_by_id[request_id].get("method", "GET"),
                    "name": requests_by_id[request_id].get("name") or "Untitled request",
                    "url": requests_by_id[request_id].get("url", ""),
                    "selected": bool(st.session_state.get(f"generation_selected_{request_id}", True)),
                }
                for request_id in current_order
            ]
            order_result = render_request_order_list(
                order_rows, key=f"generation-request-order-{project_id or 'default'}",
            )
            changed = getattr(order_result, "rows_change", None)
            if isinstance(changed, dict):
                proposed_order = changed.get("order_ids", [])
                proposed_selected = set(changed.get("selected_ids", []))
                state_changed = False
                if len(proposed_order) == len(eligible_ids) and set(proposed_order) == set(eligible_ids):
                    if proposed_order != current_order:
                        try:
                            if project_id:
                                _persist_generation_order(project_id, proposed_order)
                            else:
                                st.session_state["generation_order_ids"] = proposed_order
                            state_changed = True
                        except Exception as exc:
                            st.error(f"Could not save request order: {exc}")
                if proposed_selected <= set(eligible_ids):
                    for request_id in eligible_ids:
                        was_selected = st.session_state.get(f"generation_selected_{request_id}", True)
                        st.session_state[f"generation_selected_{request_id}"] = request_id in proposed_selected
                        state_changed = state_changed or was_selected != (request_id in proposed_selected)
                if state_changed:
                    st.rerun()

            ordered_ids = st.session_state.get("generation_order_ids", current_order)
            selected_ids = {
                request_id for request_id in eligible_ids
                if st.session_state.get(f"generation_selected_{request_id}", True)
            }
            selected = _generation_requests_in_order(requests_by_id, ordered_ids, selected_ids)

            if not endpoints:
                st.info("Enable saved requests in API Workspace to start generation.")

    project_test_cases = [
        case for case in _deduplicate_test_cases(st.session_state.get("test_cases", []))
        if not case.get("superseded_by_activity_id")
    ]
    examples_by_id = {str(case.get("id")): case for case in project_test_cases if case.get("id")}
    example_key = f"generation_example_ids_{project_id or 'default'}"
    st.session_state.setdefault(example_key, [])
    st.session_state[example_key] = [
        case_id for case_id in st.session_state[example_key]
        if case_id in examples_by_id
    ]

    example_ids = []
    if mode != "General":
        with st.container(border=True):
            st.markdown("**2 · Use existing cases as examples** · Optional")
            example_ids = st.multiselect(
                "Reference test cases",
                options=list(examples_by_id),
                key=example_key,
                label_visibility="collapsed",
                placeholder="Choose cases whose coverage or style you want more of",
                format_func=lambda case_id: (
                    f"{'Flow' if examples_by_id[case_id].get('is_flow') else str(examples_by_id[case_id].get('type', 'test')).title()} · "
                    f"{examples_by_id[case_id].get('name') or 'Untitled case'}"
                ),
            )
            if not examples_by_id:
                st.caption("Generate or add a test case first to use it as an example.")
            elif example_ids:
                st.caption("Examples guide scenario coverage and style. They remain unchanged; generated cases are added alongside them.")

    general_collection_id = None
    general_collection_name = None
    if mode == "General":
        existing_general_collections = {}
        for case in project_test_cases:
            if case.get("case_kind") != "general":
                continue
            collection_id = str(case.get("case_collection_id") or GENERAL_CASE_COLLECTION_ID)
            collection_name = str(case.get("case_collection_name") or GENERAL_CASE_COLLECTION_NAME)
            existing_general_collections[collection_id] = collection_name
        collection_choice_key = f"general_collection_choice_{project_id or 'default'}"
        pending_choice = st.session_state.pop(f"{collection_choice_key}_pending", None)
        if pending_choice in existing_general_collections:
            st.session_state[collection_choice_key] = pending_choice
        valid_choices = [NEW_GENERAL_CASE_COLLECTION, *existing_general_collections]
        if st.session_state.get(collection_choice_key) not in valid_choices:
            st.session_state[collection_choice_key] = NEW_GENERAL_CASE_COLLECTION
        with st.container(border=True):
            st.markdown("**2 · General scenario collection**")
            collection_choice = st.selectbox(
                "Collection", valid_choices, key=collection_choice_key,
                format_func=lambda value: (
                    "Create a new collection…" if value == NEW_GENERAL_CASE_COLLECTION
                    else existing_general_collections.get(value, value)
                ),
                help=(
                    "Store scenarios in a project collection so cases for different products or business "
                    "contexts stay organized. Choose an existing collection or create a new one."
                ),
            )
            if collection_choice == NEW_GENERAL_CASE_COLLECTION:
                general_collection_name = st.text_input(
                    "New collection name", value="General scenarios",
                    key=f"general_collection_name_{project_id or 'default'}",
                    help="Use a product or business context, such as Checkout or Customer onboarding.",
                ).strip()
                if general_collection_name:
                    general_collection_id = str(uuid.uuid5(
                        uuid.NAMESPACE_URL,
                        f"api-agent:{project_id or 'default'}:general-collection:{general_collection_name.casefold()}",
                    ))
            else:
                general_collection_id = collection_choice
                general_collection_name = existing_general_collections[collection_choice]

    with st.container(border=True):
        st.markdown("**3 · Add business requirements**" + (" · Required for General" if mode == "General" else " · Optional"))
        business_req = st.text_area(
            "Business requirements", height=95, key="generation_business_requirements",
            label_visibility="collapsed",
            placeholder="Rules, edge cases, or expected behavior the tests should cover...",
        )

    if mode == "Flow" and project_id:
        selected_by_id = {endpoint["id"]: endpoint for endpoint in selected}
        ordered_selected = [
            selected_by_id[request_id]
            for request_id in st.session_state.get("generation_order_ids", [])
            if request_id in selected_by_id
        ]
        ordered_selected.extend(
            endpoint for endpoint in selected
            if endpoint["id"] not in {item["id"] for item in ordered_selected}
        )
        selected = ordered_selected

    existing_count = len(st.session_state.get("test_cases", []))
    generation_submit_key = f"generation_last_submit_at_{project_id or 'default'}"
    generation_cooldown = 3.0
    generate_col, clear_col, hint_col = st.columns([1.8, 1.8, 4], vertical_alignment="center")
    with generate_col:
        generate_clicked = st.button(
            "Generate test cases", icon=":material/auto_awesome:", type="primary",
            width="stretch", disabled=(not selected and mode != "General") or (
                mode == "General" and (not business_req.strip() or not general_collection_name)
            ),
        )
    with clear_col:
        with st.popover(
            "Clear test cases", icon=":material/delete_sweep:", width="stretch",
            disabled=existing_count == 0,
        ):
            st.write(f"Remove all {existing_count} test cases from this workspace?")
            if st.button("Confirm clear", key="confirm_clear_test_cases", type="primary"):
                project = st.session_state.get("current_project") or {}
                try:
                    if project:
                        api_delete(f"/api/v1/projects/{project['id']}/test-cases")
                    st.session_state["test_cases"] = []
                    st.session_state["executions"] = {}
                    _queue_toast("All test cases cleared.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Could not clear test cases: {exc}")
    with hint_col:
        if mode == "General":
            st.caption("Requirements-only scenarios · manually marked Passed or Failed")
        elif not selected:
            st.caption(":orange[Select at least one request to generate tests.]")
        elif mode == "Flow" and len(selected) < 2:
            st.caption(":orange[Flows usually need multiple requests; selected order is preserved.]")
        else:
            st.caption(f"{len(selected)} request(s) selected · {mode.lower()} generation")

    if generate_clicked and (selected or mode == "General"):
        now = time.time()
        if now - st.session_state.get(generation_submit_key, 0.0) < generation_cooldown:
            st.info("Generation was just submitted. Please wait before trying again.")
            return
        st.session_state[generation_submit_key] = now
        with st.spinner("Generating with the configured LLM providers..."):
            try:
                response = _generate_selected_cases(
                    mode, selected, business_req, example_ids,
                    general_collection_id, general_collection_name,
                )
                result = _accept_generation_response(response, mode)
                if result:
                    if mode == "General":
                        st.session_state[f"general_collection_choice_{project_id or 'default'}_pending"] = general_collection_id
                    _queue_toast(f"Generated {len(result)} additional test case(s). Existing cases were kept.")
                else:
                    st.warning("The model returned no test cases. Try again or simplify the endpoint requirements.")
            except Exception as exc:
                st.error(f"Failed to generate test cases: {exc}")
            finally:
                st.session_state[generation_submit_key] = time.time()

    _render_generation_clarifications(str(project_id or ""))

    if project_id:
        with st.expander("Create a release revision", expanded=False):
            try:
                saved_project = api_get(f"/api/v1/projects/{project_id}")
                source_payload = api_get(f"/api/v1/projects/{project_id}/generation-activity?limit=500")
                source_actions = [
                    item for item in _normalise_generation_activity_records(source_payload)
                    if item.get("status") == "succeeded" and item.get("business_requirements") is not None
                ]
                source_actions.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
            except Exception as exc:
                saved_project = None
                source_actions = []
                st.error(f"Could not load saved revision context: {exc}")
            if not source_actions:
                st.info("A successful generation action with saved requirements is needed to start a revision.")
            elif saved_project is None:
                st.warning("Revision selection is unavailable until the latest saved project data can be loaded.")
            else:
                action_by_id = {str(item["id"]): item for item in source_actions if item.get("id")}
                source_key = f"revision_source_{project_id}"
                source_options = list(action_by_id)
                default_source = next(
                    (item_id for item_id in source_options
                     if action_by_id[item_id].get("revision_id") or action_by_id[item_id].get("mode") == "Release revision"),
                    source_options[0],
                )
                pending_source = st.session_state.pop(f"{source_key}_pending", None)
                if pending_source in action_by_id:
                    st.session_state[source_key] = pending_source
                if st.session_state.get(source_key) not in action_by_id:
                    st.session_state[source_key] = default_source
                source_id = st.selectbox(
                    "Prior generation action", source_options, key=source_key,
                    format_func=lambda value: (
                        f"{action_by_id[value].get('created_at', 'Unknown')} · "
                        f"{action_by_id[value].get('mode', 'Generation')} · "
                        f"{len(action_by_id[value].get('generated_case_ids', []))} cases"
                    ),
                )
                source_action = action_by_id[source_id]
                saved_cases = [
                    item for item in saved_project.get("test_cases", [])
                    if item.get("id") and not item.get("superseded_by_activity_id")
                ]
                saved_cases_by_id = {str(item["id"]): item for item in saved_cases}
                session_cases_by_id = {
                    str(item.get("id")): item
                    for item in st.session_state.get("test_cases", []) if item.get("id")
                }
                current_endpoints = [item for item in saved_project.get("endpoints", []) if item.get("id")]
                endpoints_by_id = {str(item["id"]): item for item in current_endpoints}
                collections = saved_project.get("collections", [])
                collections_by_id = {str(item.get("id")): item for item in collections if item.get("id")}
                revisions = sorted(
                    saved_project.get("test_case_revisions", []),
                    key=lambda item: int(item.get("ordinal", 0)),
                )
                baseline_key = f"revision_baseline_{project_id}"
                pending_baseline = st.session_state.pop(f"{baseline_key}_pending", None)
                if isinstance(pending_baseline, list):
                    st.session_state[baseline_key] = [
                        str(case_id) for case_id in pending_baseline
                        if str(case_id) in saved_cases_by_id
                    ]
                if baseline_key not in st.session_state:
                    if revisions:
                        suggested = [str(value) for value in revisions[-1].get("case_ids", [])]
                    else:
                        suggested = [str(value) for value in source_action.get("generated_case_ids", [])]
                    st.session_state[baseline_key] = [
                        case_id for case_id in suggested if case_id in saved_cases_by_id
                    ]
                else:
                    st.session_state[baseline_key] = [
                        str(case_id) for case_id in st.session_state[baseline_key]
                        if str(case_id) in saved_cases_by_id
                    ]
                case_options = list(saved_cases_by_id)
                baseline_ids = st.multiselect(
                    "Cases and flows to carry forward", case_options, key=baseline_key,
                    format_func=lambda case_id: (
                        f"{saved_cases_by_id[case_id].get('name') or 'Untitled case'} · "
                        f"{_revision_case_details(saved_cases_by_id[case_id], endpoints_by_id, collections_by_id)}"
                    ),
                    help=(
                        "The baseline is the saved suite context the model will revise. Selected cases are carried "
                        "into the complete new suite; unchecked cases are omitted. Add manual cases that should "
                        "remain in the release. Deleted cases are excluded. Save or revert selected case and flow "
                        "edits before generating; only saved configurations are used."
                    ),
                )
                st.caption(f"{len(baseline_ids)} saved baseline case(s) selected.")
                with st.expander("View selected case details", expanded=False):
                    if baseline_ids:
                        for case_id in baseline_ids:
                            case = saved_cases_by_id[case_id]
                            st.caption(
                                f"{case.get('name') or 'Untitled case'}: "
                                f"{_revision_case_details(case, endpoints_by_id, collections_by_id)}"
                            )
                    else:
                        st.caption("No baseline cases selected.")
                unchanged_key = f"revision_keep_unchanged_{project_id}"
                pending_unchanged = st.session_state.pop(f"{unchanged_key}_pending", None)
                if isinstance(pending_unchanged, list):
                    st.session_state[unchanged_key] = [
                        str(case_id) for case_id in pending_unchanged if str(case_id) in baseline_ids
                    ]
                if unchanged_key not in st.session_state:
                    st.session_state[unchanged_key] = []
                else:
                    st.session_state[unchanged_key] = [
                        str(case_id) for case_id in st.session_state[unchanged_key]
                        if str(case_id) in baseline_ids
                    ]
                keep_unchanged_ids = st.multiselect(
                    "Keep unchanged",
                    options=baseline_ids,
                    key=unchanged_key,
                    format_func=lambda case_id: saved_cases_by_id[case_id].get("name") or "Untitled case",
                    help="Selected cases are copied exactly into the new revision and skipped by AI. Other baseline cases are revised by AI.",
                    placeholder="AI revision for every selected case",
                )
                st.caption(
                    f"{len(baseline_ids) - len(keep_unchanged_ids)} sent to AI · "
                    f"{len(keep_unchanged_ids)} kept unchanged"
                )
                unsaved_case_ids = [
                    case_id for case_id in baseline_ids
                    if case_id in session_cases_by_id
                    and _revision_case_signature(session_cases_by_id[case_id])
                    != _revision_case_signature(saved_cases_by_id[case_id])
                ]
                if unsaved_case_ids:
                    names = [saved_cases_by_id[item].get("name") or item for item in unsaved_case_ids]
                    st.warning("Save or revert these selected case edits before generating: " + ", ".join(names))
                st.text_area(
                    "Previous business requirements (read only)",
                    value=str(source_action.get("business_requirements") or ""),
                    disabled=True, height=100,
                )
                if source_action.get("release_notes"):
                    st.text_area(
                        "Previous release notes (read only)",
                        value=str(source_action["release_notes"]),
                        disabled=True, height=80,
                    )
                revision_notes = st.text_area(
                    "New requirement changes", key=f"revision_notes_{project_id}", height=95,
                    placeholder="Describe changed endpoint behavior, new rules, and additional release coverage.",
                )
                source_snapshot = source_action.get("endpoint_snapshot")
                source_endpoints_by_id = {
                    str(item.get("id")): item for item in source_snapshot or []
                    if isinstance(item, dict) and item.get("id")
                }
                snapshot_available = isinstance(source_snapshot, list)
                selected_endpoint_ids = []
                endpoint_ids_by_collection = {
                    str(collection.get("id")): [
                        str(item["id"]) for item in current_endpoints
                        if str(item.get("collection_id")) == str(collection.get("id"))
                    ] for collection in collections if collection.get("id")
                }
                for endpoint in current_endpoints:
                    endpoint_key = f"revision_endpoint_{project_id}_{endpoint['id']}"
                    st.session_state.setdefault(endpoint_key, True)
                ungrouped_ids = [
                    str(item["id"]) for item in current_endpoints
                    if not any(str(item.get("collection_id")) == collection_id
                               for collection_id in endpoint_ids_by_collection)
                ]
                selected_endpoint_ids = [
                    str(item["id"]) for item in current_endpoints
                    if st.session_state.get(f"revision_endpoint_{project_id}_{item['id']}", True)
                ]
                selected_collection_ids = {
                    str(endpoints_by_id[item_id].get("collection_id"))
                    for item_id in selected_endpoint_ids
                    if endpoints_by_id[item_id].get("collection_id")
                }
                if any(item_id in ungrouped_ids for item_id in selected_endpoint_ids):
                    selected_collection_ids.add("unassigned")
                endpoint_help = (
                    "Choose saved requests across project collections. All current requests start selected; "
                    "collection checkboxes select or clear every request in that collection. Change status "
                    "compares method, URL, headers, query parameters, and body with the source snapshot."
                )
                if not snapshot_available:
                    endpoint_help += (
                        " This source action predates endpoint snapshots, so request change badges cannot be compared."
                    )
                with st.popover(
                    f"Choose endpoints · {len(selected_endpoint_ids)} selected",
                    icon=":material/api:",
                    help=endpoint_help,
                    key=f"revision_endpoint_picker_{project_id}",
                    disabled=not current_endpoints,
                ):
                    st.caption("Search by collection, request name, method, or URL.")
                    search_text = st.text_input(
                        "Search endpoints", key=f"revision_endpoint_search_{project_id}",
                        placeholder="Search saved requests",
                        label_visibility="collapsed",
                    ).strip().lower()
                    for collection in collections:
                        collection_id = str(collection.get("id"))
                        child_ids = endpoint_ids_by_collection.get(collection_id, [])
                        if not child_ids:
                            continue
                        collection_name = str(collection.get("name") or "Untitled collection")
                        collection_matches = bool(search_text and search_text in collection_name.lower())
                        visible_ids = [
                            endpoint_id for endpoint_id in child_ids
                            if collection_matches or not search_text or search_text in " ".join((
                                collection_name,
                                str(endpoints_by_id[endpoint_id].get("name") or ""),
                                str(endpoints_by_id[endpoint_id].get("url") or ""),
                                str(endpoints_by_id[endpoint_id].get("method") or "GET"),
                            )).lower()
                        ]
                        if search_text and not visible_ids:
                            continue
                        collection_key = f"revision_collection_{project_id}_{collection_id}"
                        st.session_state[collection_key] = all(
                            st.session_state.get(f"revision_endpoint_{project_id}_{item}", False)
                            for item in child_ids
                        )
                        st.checkbox(
                            f"{collection_name} · "
                            f"{sum(st.session_state.get(f'revision_endpoint_{project_id}_{item}', False) for item in child_ids)}/{len(child_ids)} selected",
                            key=collection_key,
                            on_change=_select_revision_collection,
                            args=(project_id, collection_id, child_ids),
                            help="Select or clear every saved request in this collection.",
                        )
                        with st.expander(
                            f"Requests · {len(visible_ids)} shown",
                            expanded=bool(search_text),
                            key=f"revision_collection_group_{project_id}_{collection_id}",
                        ):
                            for endpoint_id in visible_ids:
                                endpoint = endpoints_by_id[endpoint_id]
                                previous = source_endpoints_by_id.get(endpoint_id)
                                request_col, status_col = st.columns([4, 2], vertical_alignment="center")
                                with request_col:
                                    st.checkbox(
                                        f"{str(endpoint.get('method') or 'GET').upper()} · "
                                        f"{_truncate(endpoint.get('name') or endpoint.get('url') or 'Unnamed endpoint', 42)}",
                                        key=f"revision_endpoint_{project_id}_{endpoint_id}",
                                        help=f"URL: {endpoint.get('url') or 'No URL saved'}",
                                    )
                                with status_col:
                                    st.caption(_revision_endpoint_status(endpoint, previous, snapshot_available))
                    if ungrouped_ids:
                        group_id = "unassigned"
                        group_name = "Outside collections"
                        collection_matches = bool(search_text and search_text in group_name.lower())
                        visible_ids = [
                            endpoint_id for endpoint_id in ungrouped_ids
                            if collection_matches or not search_text or search_text in " ".join((
                                str(endpoints_by_id[endpoint_id].get("name") or ""),
                                str(endpoints_by_id[endpoint_id].get("url") or ""),
                                str(endpoints_by_id[endpoint_id].get("method") or "GET"),
                            )).lower()
                        ]
                        if visible_ids:
                            collection_key = f"revision_collection_{project_id}_{group_id}"
                            st.session_state[collection_key] = all(
                                st.session_state.get(f"revision_endpoint_{project_id}_{item}", False)
                                for item in ungrouped_ids
                            )
                            st.checkbox(
                                f"{group_name} · "
                                f"{sum(st.session_state.get(f'revision_endpoint_{project_id}_{item}', False) for item in ungrouped_ids)}/{len(ungrouped_ids)} selected",
                                key=collection_key,
                                on_change=_select_revision_collection,
                                args=(project_id, group_id, ungrouped_ids),
                                help="Select or clear every saved request outside a collection.",
                            )
                            with st.expander(
                                f"Requests · {len(visible_ids)} shown",
                                expanded=bool(search_text),
                                key=f"revision_collection_group_{project_id}_{group_id}",
                            ):
                                for endpoint_id in visible_ids:
                                    endpoint = endpoints_by_id[endpoint_id]
                                    previous = source_endpoints_by_id.get(endpoint_id)
                                    request_col, status_col = st.columns([4, 2], vertical_alignment="center")
                                    with request_col:
                                        st.checkbox(
                                            f"{str(endpoint.get('method') or 'GET').upper()} · "
                                            f"{_truncate(endpoint.get('name') or endpoint.get('url') or 'Unnamed endpoint', 42)}",
                                            key=f"revision_endpoint_{project_id}_{endpoint_id}",
                                            help=f"URL: {endpoint.get('url') or 'No URL saved'}",
                                        )
                                    with status_col:
                                        st.caption(_revision_endpoint_status(endpoint, previous, snapshot_available))
                    if not current_endpoints:
                        st.caption("No saved endpoints are available in this project.")
                revision_options = saved_project.get("test_case_revisions", [])
                label_key = f"revision_label_{project_id}"
                pending_label = st.session_state.pop(f"{label_key}_pending", None)
                if pending_label is not None:
                    st.session_state[label_key] = pending_label
                revision_label = st.text_input(
                    "Release label", key=label_key,
                    value=f"Revision {max([int(item.get('ordinal', 0)) for item in revision_options] + [0]) + 1}",
                )
                st.caption(
                    f"Selected {len(baseline_ids)} saved baseline case(s) and {len(selected_endpoint_ids)} "
                    f"current endpoint(s) across {len(selected_collection_ids)} collection(s). "
                    "Endpoint selection is optional; the saved baseline can provide the revision context. "
                    "The previous revision remains unchanged."
                )
                revision_clicked = st.button(
                    "Generate release revision", key=f"generate_revision_{project_id}",
                    type="primary", icon=":material/rebase_edit:",
                    disabled=not baseline_ids or not revision_label.strip() or bool(unsaved_case_ids),
                )
                if revision_clicked:
                    with st.spinner("Generating the complete revised suite..."):
                        try:
                            response = api_post(
                                f"/api/v1/projects/{project_id}/test-case-revisions",
                                {
                                    "source_activity_id": source_id,
                                    "baseline_case_ids": baseline_ids,
                                    "release_label": revision_label.strip(),
                                    "release_notes": revision_notes,
                                    "endpoint_ids": selected_endpoint_ids,
                                    "keep_unchanged_case_ids": keep_unchanged_ids,
                                },
                            )
                            project.setdefault("test_case_revisions", []).append(response["revision"])
                            project.setdefault("test_cases", []).extend(response["test_cases"])
                            st.session_state["test_cases"] = project["test_cases"]
                            st.session_state[f"{source_key}_pending"] = response["activity"]["id"]
                            st.session_state[f"{baseline_key}_pending"] = [
                                str(item.get("id")) for item in response["test_cases"] if item.get("id")
                            ]
                            st.session_state[f"{unchanged_key}_pending"] = []
                            st.session_state[f"{label_key}_pending"] = f"Revision {response['revision'].get('ordinal', 1) + 1}"
                            for warning in response.get("warnings", []):
                                _queue_toast(warning, "warning")
                            _queue_toast(f"{revision_label} created with {len(response['test_cases'])} cases.")
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Could not generate release revision: {exc}")



def render_test_case_list(loaded_run_id: str | None = None) -> None:
    """Render status counts, filters, batch execution, and test-case cards.

    Args:
        loaded_run_id (str | None): Currently loaded named run, if any.

    Returns:
        None: Writes test-case results to the Streamlit page.
    """
    raw_test_cases = st.session_state.get("test_cases", [])
    deduplicated_cases = _deduplicate_test_cases(raw_test_cases)
    if len(deduplicated_cases) != len(raw_test_cases):
        st.session_state["test_cases"] = deduplicated_cases
        st.warning("Duplicate test-case IDs were found and collapsed to the latest copy.")
    test_cases = [case for case in deduplicated_cases if not case.get("superseded_by_activity_id")]
    test_cases.sort(key=_test_case_sort_key)
    project = st.session_state.get("current_project") or {}
    revisions = sorted(project.get("test_case_revisions", []), key=lambda item: int(item.get("ordinal", 0)))
    project_id = project.get("id", "default")
    revision_by_id = {str(item.get("id")): item for item in revisions}
    latest_revision_id = str(revisions[-1].get("id")) if revisions else None
    if revisions:
        revision_key = f"tc_revision_view_{project_id}"
        st.session_state.setdefault(revision_key, "All revisions")
        view_options = ["Latest revision", "All revisions"] + list(revision_by_id)

    endpoints = project.get("endpoints", [])
    collections = project.get("collections", [])
    runs = project.get("test_runs", [])
    scope_keys = {
        name: f"tc_scope_{name}_{project_id}"
        for name in ("runs", "collections", "endpoints")
    }
    options_by_name = {
        "runs": [item.get("id") for item in runs if item.get("id")],
        "collections": [item.get("id") for item in collections if item.get("id")],
        "endpoints": [item.get("id") for item in endpoints if item.get("id")],
    }
    general_collection_names = {}
    for case in test_cases:
        if case.get("case_kind") != "general":
            continue
        collection_id = str(case.get("case_collection_id") or GENERAL_CASE_COLLECTION_ID)
        general_collection_names[collection_id] = str(
            case.get("case_collection_name") or GENERAL_CASE_COLLECTION_NAME
        )
    options_by_name["collections"].extend(
        item for item in general_collection_names
        if item not in options_by_name["collections"]
    )
    for name, key in scope_keys.items():
        st.session_state.setdefault(key, [])
        st.session_state[key] = [value for value in st.session_state[key] if value in options_by_name[name]]
    st.session_state.setdefault("test_case_filter", "All")

    with st.container(key="test-case-scope-filters"):
        if revisions:
            filter_cols = st.columns([1.45, 1.15, 1.15, 1.6, 0.6], vertical_alignment="bottom")
            with filter_cols[0]:
                view_value = st.selectbox(
                    "Test case revision", view_options, key=revision_key,
                    format_func=lambda value: value if value in {"Latest revision", "All revisions"}
                    else revision_by_id[value].get("label", value),
                )
            filter_offset = 1
        else:
            filter_cols = st.columns([1.2, 1.2, 1.6, 0.65], vertical_alignment="bottom")
            view_value = "All revisions"
            filter_offset = 0
        with filter_cols[filter_offset]:
            selected_run_ids = st.multiselect(
                "Test suites", options_by_name["runs"], key=scope_keys["runs"],
                placeholder="All suites", format_func=lambda run_id: next(
                    (item.get("name", "Untitled run") for item in runs if item.get("id") == run_id), run_id,
                ),
            )
        with filter_cols[filter_offset + 1]:
            selected_collection_ids = st.multiselect(
                "Collections", options_by_name["collections"], key=scope_keys["collections"],
                placeholder="All collections", format_func=lambda collection_id: next(
                    (item.get("name", "Untitled collection") for item in collections if item.get("id") == collection_id),
                    general_collection_names.get(collection_id, collection_id),
                ),
            )
        with filter_cols[filter_offset + 2]:
            selected_endpoint_ids = st.multiselect(
                "Endpoints", options_by_name["endpoints"], key=scope_keys["endpoints"],
                placeholder="All endpoints", format_func=lambda endpoint_id: next(
                    (f"{item.get('method', 'GET')} · {item.get('name') or item.get('url') or 'Untitled request'}"
                     for item in endpoints if item.get("id") == endpoint_id), endpoint_id,
                ),
            )
        with filter_cols[filter_offset + 3]:
            st.button(
                "Clear", key=f"tc_clear_scope_filters_{project_id}",
                help="Clear run, collection, endpoint, and result filters",
                on_click=_clear_test_case_filters, args=(project_id,), width="stretch",
            )

    if revisions:
        if view_value == "Latest revision":
            visible_ids = set(revisions[-1].get("case_ids", []))
            test_cases = [item for item in test_cases if str(item.get("id")) in visible_ids]
        elif view_value != "All revisions":
            visible_ids = set(revision_by_id[view_value].get("case_ids", []))
            test_cases = [item for item in test_cases if str(item.get("id")) in visible_ids]
    if not test_cases:
        st.info("No test cases in this revision view. Choose All revisions to browse the full project suite.")
        return

    scoped_cases = _filter_test_cases_by_scope(
        test_cases, endpoints, selected_run_ids, runs,
        selected_collection_ids, selected_endpoint_ids,
    )
    executions = st.session_state.get("executions", {})
    statuses = {
        tc.get("id"): (
            _test_case_status(executions.get(tc.get("id")))
            if executions.get(tc.get("id")) else str(tc.get("manual_status") or "not_run")
        )
        for tc in test_cases
    }
    counts = {
        "passed": sum(statuses.get(tc.get("id")) == "passed" for tc in scoped_cases),
        "failed": sum(statuses.get(tc.get("id")) == "failed" for tc in scoped_cases),
        "error": sum(statuses.get(tc.get("id")) == "error" for tc in scoped_cases),
        "not_run": sum(statuses.get(tc.get("id")) == "not_run" for tc in scoped_cases),
    }

    st.divider()
    st.subheader(
        f"Test cases · {len(scoped_cases)} of {len(test_cases)}"
        if selected_run_ids or selected_collection_ids or selected_endpoint_ids
        else f"Test cases · {len(test_cases)}"
    )
    st.markdown(
        f":gray-badge[{len(scoped_cases)} in scope] :green-badge[{counts['passed']} passed] "
        f":red-badge[{counts['failed']} failed] :orange-badge[{counts['error']} error] "
        f":gray-badge[{counts['not_run']} not run]"
    )

    with st.container(key="test-case-toolbar"):
        filter_col, selection_col, expand_col, collapse_col, run_col, save_col = st.columns(
            [2.5, 1.1, 1.1, 1.2, 1.35, 1.4], vertical_alignment="center"
        )
        with filter_col:
            st.session_state.setdefault("test_case_filter", "All")
            chosen_filter = st.segmented_control(
                "Result filter", ["All", "Passed", "Failed", "Error", "Not run"],
                key="test_case_filter", label_visibility="collapsed",
            ) or "All"
        all_selected = all(
            st.session_state.get(f"tc_selected_{case.get('id')}", True)
            for case in test_cases
        )
        selected_case_ids = [
            str(case["id"])
            for case in test_cases
            if case.get("id") and st.session_state.get(f"tc_selected_{case['id']}", True)
        ]
        with selection_col:
            st.button(
                "Deselect all" if all_selected else "Select all",
                key="tc_toggle_all_selection", width="stretch",
                on_click=_select_all_test_cases, args=(test_cases, not all_selected),
            )
        with expand_col:
            # Improved state management for expand/collapse all
            tc_ids_with_state = [tc for tc in test_cases if tc.get('id')]
            if tc_ids_with_state:
                open_count = sum(1 for tc in tc_ids_with_state
                                 if st.session_state.get(f"tc_open_{tc['id']}", False))
                total_count = len(tc_ids_with_state)
                all_expanded = open_count == total_count
                at_least_one_expanded = open_count > 0
            else:
                all_expanded = False
                at_least_one_expanded = False
                total_count = 0

            # Determine button label and icon based on state
            if all_expanded:
                # All sections are expanded → show Collapse all
                label = "Collapse all"
                icon = ":material/unfold_less:"
            elif at_least_one_expanded:
                # Mixed state (some expanded, some collapsed) → show Collapse all
                label = "Collapse all"
                icon = ":material/unfold_less:"
            else:
                # Nothing expanded → show Expand all
                label = "Expand all"
                icon = ":material/unfold_more:"

            if st.button(label, key="tc_toggle_all", icon=icon, width="stretch"):
                # Toggle all sections to opposite state
                if all_expanded:
                    _set_all_test_cases_open(test_cases, False)
                else:
                    _set_all_test_cases_open(test_cases, True)
                st.rerun()
        with collapse_col:
            st.download_button(
                "Export CSV",
                data=lambda: _fetch_test_case_csv(project_id, selected_case_ids),
                file_name=f"test_cases_{project_id}.csv",
                mime="text/csv",
                key=f"export_test_cases_{project_id}",
                icon=":material/download:",
                width="stretch",
                on_click="ignore",
                disabled=not selected_case_ids,
                help=f"Export {len(selected_case_ids)} selected test case(s)",
            )
        with run_col:
            run_selected = st.button(
                "Run selected", key="tc_run_selected", icon=":material/play_arrow:",
                type="primary", width="stretch", help="Execute checked test cases",
            )
        with save_col:
            save_clicked = st.button(
                "Save to project", key="tc_save_project", icon=":material/save:",
                width="stretch",
                disabled=(
                    not project
                    or view_value == "All revisions" and bool(revisions)
                    or view_value in revision_by_id and view_value != latest_revision_id
                ),
            )

    if run_selected:
        targets = [tc for tc in test_cases if st.session_state.get(f"tc_selected_{tc.get('id')}", True)]
        errors = []
        if targets and loaded_run_id and project.get("id"):
            try:
                saved_cases = api_get(f"/api/v1/projects/{project['id']}/test-cases")
                saved_by_id = {case.get("id"): case for case in saved_cases}
                targets = [saved_by_id[case.get("id")] for case in targets if case.get("id") in saved_by_id]
                if not targets:
                    st.warning("This suite has no remaining saved test cases. Update the suite to change its selection.")
            except Exception as exc:
                st.error(f"Could not load the latest saved test cases: {exc}")
                targets = []
        if not targets:
            st.warning("Select at least one test case to run.")
        else:
            general_targets = [tc for tc in targets if tc.get("case_kind") == "general"]
            http_targets = [tc for tc in targets if tc.get("case_kind") != "general"]
            if general_targets:
                st.info(f"Skipped {len(general_targets)} general scenario(s); mark them Passed or Failed manually on their cards.")
            if not http_targets:
                st.warning("No HTTP-executable cases are selected.")
            progress = st.progress(0.0, text="Preparing execution...") if http_targets else None
            for number, tc in enumerate(http_targets, start=1):
                progress.progress(
                    (number - 1) / len(http_targets),
                    text=f"Running {tc.get('name', tc.get('id'))} ({number}/{len(http_targets)})",
                )
                try:
                    _execute_test_case(tc, notify=False)
                except Exception as exc:
                    errors.append(f"{tc.get('name', tc.get('id'))}: {exc}")
            if progress:
                progress.progress(1.0, text="Execution complete")
            batch_results = [
                st.session_state.get("executions", {}).get(tc.get("id")) for tc in http_targets
            ]
            passed = sum(_test_case_status(result) == "passed" for result in batch_results)
            failed = sum(_test_case_status(result) == "failed" for result in batch_results)
            errored = sum(_test_case_status(result) == "error" for result in batch_results) + len(errors)
            _queue_toast(
                f"Ran {len(http_targets)} HTTP case(s): {passed} passed, {failed} failed, {errored} errors.",
                "error" if failed or errored else "success",
            )
            focus_case = next(
                (
                    tc for tc in http_targets
                    if _test_case_status(st.session_state.get("executions", {}).get(tc.get("id")))
                    in {"failed", "error"}
                ),
                http_targets[-1] if http_targets else general_targets[-1],
            )
            focus_id = focus_case.get("id")
            st.session_state[f"tc_open_{focus_id}"] = True
            st.session_state[f"tc_detail_tabs_{focus_id}"] = (
                "Scenario result" if focus_case.get("is_flow") else "Result"
            )
            st.session_state["tc_run_errors"] = errors
            st.rerun()

    if save_clicked and project:
        try:
            result = api_post(
                f"/api/v1/projects/{project['id']}/test-cases/save",
                {"test_cases": test_cases},
            )
            _queue_toast(result.get("message", "Test cases saved."))
        except Exception as exc:
            st.error(f"Could not save test cases: {exc}")

    for message in st.session_state.pop("tc_run_errors", []):
        st.error(message)

    filter_status = {
        "All": None, "Passed": "passed", "Failed": "failed",
        "Error": "error", "Not run": "not_run",
    }[chosen_filter]
    visible_cases = [
        tc for tc in scoped_cases
        if not filter_status or statuses.get(tc.get("id")) == filter_status
    ]
    shown = 0
    for _, heading, grouped_cases in _group_test_cases_by_endpoint(visible_cases, endpoints):
        st.markdown(f"#### {heading}")
        for tc in grouped_cases:
            shown += 1
            if tc.get("is_flow") or isinstance(tc.get("steps"), list):
                st.caption(_flow_provenance_label(tc, endpoints, collections))
            revision_id = str(tc.get("revision_id", ""))
            read_only = revision_id in revision_by_id and revision_id != latest_revision_id
            render_test_case_card(tc, test_cases.index(tc), read_only=read_only)
    if shown == 0:
        st.caption("No test cases match the selected filters.")


def _set_all_test_cases_open(test_cases: list[dict], is_open: bool) -> None:
    """Expand or collapse every test case and its flow steps.

    Args:
        test_cases (list[dict]): Cases and steps whose state to update.
        is_open (bool): Whether the cards should be expanded.

    Returns:
        None: Updates Streamlit session state.
    """
    for tc in test_cases:
        tc_id = tc.get("id")
        st.session_state[f"tc_open_{tc_id}"] = is_open
        for step in tc.get("steps", []) if tc.get("is_flow") else []:
            st.session_state[f"step_open_{tc_id}_step_{step.get('step_order', '?')}"] = is_open


def render_test_cases_tab() -> None:
    """Render generation controls and execution results in one workspace.

    Returns:
        None: Writes the Test Cases page to the Streamlit app.
    """
    st.markdown(TEST_CASE_CSS, unsafe_allow_html=True)
    st.markdown(TEST_CASES_TOPBAR_CSS, unsafe_allow_html=True)
    with st.container(key="test-cases-workspace"):
        raw_test_cases = st.session_state.get("test_cases", [])
        deduplicated_cases = _deduplicate_test_cases(raw_test_cases)
        if len(deduplicated_cases) != len(raw_test_cases):
            st.session_state["test_cases"] = deduplicated_cases
            st.warning("Duplicate test-case IDs were found and collapsed to the latest copy.")
        test_cases = [case for case in deduplicated_cases if not case.get("superseded_by_activity_id")]
        project = st.session_state.get("current_project") or {}
        test_cases.sort(key=_test_case_sort_key)
        with st.container(key="test-cases-topbar"):
            title_col, add_col, runs_col = st.columns(
                [6, 1.5, 1.6], vertical_alignment="center",
            )
            with title_col:
                st.markdown("### Test Cases")
                st.caption("Generate, review, and run test cases across your saved requests.")
            with add_col:
                with st.container(key="add-manual-test-action"):
                    _render_manual_case_builder(project)
            with runs_col:
                with st.container(key="reusable-runs-action"):
                    loaded_run_id = _render_test_run_manager(project, test_cases)
        render_generation_panel()
        render_test_case_list(loaded_run_id)


def render_generation_activity_tab() -> None:
    """Render project generation history, including exact prompts and responses."""
    st.header("Generation activity")
    st.caption("Review generation runs by time, type, outcome, and project. Open a row for its full record.")
    project = st.session_state.get("current_project") or {}
    project_id = project.get("id")
    if not project_id:
        st.info("Select a project to view its generation history.")
        return
    cache_key = f"generation_activity_{project_id}"
    refresh_key = f"refresh_generation_activity_{project_id}"
    refresh_clicked = st.button("Refresh logs", key=refresh_key, icon=":material/refresh:")
    if cache_key not in st.session_state or refresh_clicked:
        try:
            st.session_state[cache_key] = api_get(
                f"/api/v1/projects/{project_id}/generation-activity?limit=100"
            )
        except Exception as exc:
            st.error(f"Could not load generation history: {exc}")
    records = _normalise_generation_activity_records(st.session_state.get(cache_key))
    if not records:
        st.info("No generation activity is recorded for this project yet.")
        return

    project_name = project.get("name") or "Unnamed project"
    superseded_activity_ids = {
        str(item.get("supersedes_activity_id")) for item in records
        if item.get("supersedes_activity_id")
    }
    with st.container(key=f"generation-activity-table-{project_id}"):
        header = st.columns([2.2, 1.2, 1.0, 1.7, 1.0], vertical_alignment="center")
        for column, title in zip(header, ("Execution time", "Generation type", "State", "Project", "Action")):
            with column:
                st.markdown(f"**{title}**")
        for record in records:
            with st.container(border=True):
                columns = st.columns([2.2, 1.2, 1.0, 1.7, 1.0], vertical_alignment="center")
                with columns[0]:
                    raw_time = str(record.get("created_at") or "Unknown")
                    st.write(raw_time.replace("T", " ")[:19])
                with columns[1]:
                    st.write(record.get("mode") or "Generation")
                with columns[2]:
                    state = str(record.get("status") or "unknown").capitalize()
                    if str(record.get("id")) in superseded_activity_ids:
                        state = "Superseded"
                    state_color = "#16834a" if state == "Succeeded" else "#c0393b" if state == "Failed" else "#777"
                    st.markdown(
                        f"<span style='color:{state_color};font-weight:650'>{html.escape(state)}</span>",
                        unsafe_allow_html=True,
                    )
                with columns[3]:
                    st.write(project_name)
                    st.caption(str(record.get("project_id") or project_id))
                with columns[4]:
                    if st.button(
                        "View details", key=f"view_generation_activity_{record['id']}",
                        width="stretch",
                    ):
                        _show_generation_activity_details(record)


@st.dialog("Generation activity details", width="large")
def _show_generation_activity_details(record: dict) -> None:
    """Show the complete selected generation record in a modal dialog."""
    st.caption(f"{record.get('created_at', 'Unknown time')} · {record.get('mode', 'Generation')} · {record.get('status', 'unknown')}")
    st.caption(f"Activity ID: {record.get('id', 'Unknown')}")
    st.markdown("**Project**")
    st.write(record.get("project_id", "Unknown project"))
    if record.get("mode") == "Release revision":
        previous_requirements = record.get("previous_requirements")
        if previous_requirements is None:
            previous_requirements = record.get("business_requirements")
        st.markdown("**Previous business requirements**")
        st.write(previous_requirements or "None recorded")
        st.markdown("**Previous release notes**")
        st.write(record.get("previous_release_notes") or "None recorded")
        st.markdown("**New requirement changes**")
        st.write(record.get("release_notes") or "None provided")
        st.markdown("**Cumulative requirements saved on revised cases**")
        st.write(record.get("business_requirements") or "None provided")
    else:
        st.markdown("**Business requirements**")
        st.write(record.get("business_requirements") or "None provided")
    st.markdown("**Included endpoints**")
    endpoints = record.get("endpoints", [])
    if endpoints:
        st.dataframe(
            [{
                "Name": item.get("name") or "Unnamed endpoint",
                "Method": item.get("method", "GET"),
                "URL": item.get("url", ""),
                "Endpoint ID": item.get("id") or "",
            } for item in endpoints],
            hide_index=True,
            width="stretch",
        )
    else:
        st.caption("No endpoint details recorded.")
    if record.get("generated_case_ids"):
        st.markdown("**Generated test case IDs**")
        st.write(", ".join(record["generated_case_ids"]))
    if record.get("follow_up_of"):
        st.markdown("**Refined from activity**")
        st.write(record["follow_up_of"])
    if record.get("supersedes_activity_id"):
        st.markdown("**Replaces active output from activity**")
        st.write(record["supersedes_activity_id"])
    if record.get("archived_case_ids"):
        st.markdown("**Archived case IDs (retained in history)**")
        st.write(", ".join(str(item) for item in record["archived_case_ids"]))
    archived_summaries = record.get("archived_case_summaries") or []
    if archived_summaries:
        st.markdown("**Archived output**")
        st.dataframe([{
            "Name": item.get("name") or "Untitled case",
            "Kind": "General" if item.get("case_kind") == "general" else "Flow" if item.get("is_flow") else "API test",
            "Type": item.get("type") or "test",
            "Description": item.get("description") or "",
            "Case ID": item.get("id") or "",
        } for item in archived_summaries], hide_index=True, width="stretch")
        project_id = str(record.get("project_id") or "")
        for archived_case in archived_summaries:
            case_id = str(archived_case.get("id") or "")
            if not project_id or not case_id:
                continue
            history_key = f"activity_archived_history_{record.get('id')}_{case_id}"
            with st.expander(f"History · {archived_case.get('name') or case_id}", expanded=False):
                if st.button("Load execution history", key=f"{history_key}_load"):
                    try:
                        st.session_state[history_key] = api_get(
                            f"/api/v1/projects/{project_id}/test-cases/{case_id}/history?limit=100"
                        ).get("executions", [])
                    except Exception as exc:
                        st.error(f"Could not load archived case history: {exc}")
                history = st.session_state.get(history_key)
                if history is not None:
                    if history:
                        st.dataframe([{
                            "Executed": item.get("created_at", "Unknown"),
                            "Outcome": str(item.get("status", "error")).upper(),
                            "Latency (ms)": item.get("latency_ms", ""),
                            "Details": item.get("assertion_detail", ""),
                        } for item in history], hide_index=True, width="stretch")
                        st.json(history[0])
                    else:
                        st.caption("No execution history is recorded for this archived case.")
    if record.get("kept_unchanged_source_case_ids"):
        st.markdown("**Cases copied unchanged from baseline**")
        st.write(", ".join(str(item) for item in record["kept_unchanged_source_case_ids"]))
        copied_ids = record.get("kept_unchanged_case_ids", [])
        if copied_ids:
            st.caption("New revision case IDs: " + ", ".join(str(item) for item in copied_ids))
    if record.get("questions_answered"):
        st.markdown("**Clarification questions**")
        for question in record["questions_answered"]:
            st.markdown(f"- {question}")
    if record.get("clarification_answers"):
        st.markdown("**User answers**")
        st.json(record["clarification_answers"])
    if record.get("clarification_questions"):
        st.markdown("**Questions for the user**")
        for question in record["clarification_questions"]:
            st.markdown(f"- {question}")
    if record.get("error"):
        st.error(record["error"])
    with st.expander("Prompt sent to the LLM", expanded=False):
        st.code(record.get("prompt") or "No prompt was captured.", language="text")
    with st.expander("Raw LLM response", expanded=False):
        st.code(record.get("llm_response") or "No response was captured.", language="text")


def _request_rows(values) -> list[dict]:
    """Return editor rows from saved row data or a legacy key/value mapping."""
    if isinstance(values, list):
        rows = [dict(row) for row in values if isinstance(row, dict)]
    elif isinstance(values, dict):
        rows = [{"key": key, "value": value, "enabled": True} for key, value in values.items()]
    else:
        rows = []
    for row in rows:
        row.setdefault("enabled", True)
        row.setdefault("description", "")
        row["_ui_id"] = row.get("_ui_id") or str(uuid.uuid4())
    return rows


def _contract_editor_rows(values) -> list[dict]:
    """Normalize contract headers or query parameters for a review editor.

    Args:
        values (Any): Mapping or list of key/value rows from a contract parser.

    Returns:
        list[dict]: Editable rows with send, key, value, and description fields.
    """
    if isinstance(values, dict):
        rows = [
            {"send": True, "key": str(key), "value": "" if value is None else str(value), "description": ""}
            for key, value in values.items()
        ]
    elif isinstance(values, list):
        rows = [
            {
                "send": bool(row.get("enabled", not row.get("disabled", False))),
                "key": str(row.get("key") or ""),
                "value": "" if row.get("value") is None else str(row.get("value")),
                "description": str(row.get("description") or ""),
            }
            for row in values if isinstance(row, dict)
        ]
    else:
        rows = []
    return rows


def _render_contract_rows(label: str, rows: list[dict], key: str) -> list[dict]:
    """Render editable header or query parameter rows for a contract request.

    Args:
        label (str): Section label displayed above the table.
        rows (list[dict]): Initial editable key/value rows.
        key (str): Stable Streamlit widget key for this endpoint and section.

    Returns:
        list[dict]: Edited rows in the saved-request row format.
    """
    st.markdown(f"**{label}**")
    editor_rows = rows or [{"send": True, "key": "", "value": "", "description": ""}]
    edited = st.data_editor(
        editor_rows,
        key=key,
        num_rows="dynamic",
        hide_index=True,
        width="stretch",
        height=170,
        column_order=["send", "key", "value", "description"],
        column_config={
            "send": st.column_config.CheckboxColumn("Send", width="small", default=True),
            "key": st.column_config.TextColumn("Key", width="medium"),
            "value": st.column_config.TextColumn("Value", width="large"),
            "description": st.column_config.TextColumn("Description", width="medium"),
        },
        placeholder="Add a row",
    )
    return [
        {
            "enabled": True if row.get("send") is None else bool(row.get("send")),
            "key": str(row.get("key") or "").strip(),
            "value": "" if row.get("value") is None else str(row.get("value")),
            "description": str(row.get("description") or ""),
        }
        for row in edited
        if row.get("key") or row.get("value") or row.get("description")
    ]


def _render_contract_import_panel(project_id: str, collections: list[dict]) -> None:
    """Render contract source input, endpoint review/import, and flow discovery controls.

    Args:
        project_id (str): Current project receiving imported requests.
        collections (list[dict]): Existing collections available as destinations.

    Returns:
        None: Writes the import and discovery UI and updates session state.
    """
    notice = st.session_state.pop("contract_import_notice", None)
    if notice:
        _queue_toast(notice)
    preview_key = "contract_import_preview"
    if st.session_state.get(preview_key, {}).get("project_id") not in (None, project_id):
        st.session_state.pop(preview_key, None)
    active_panel = st.session_state.get("workspace_contract_panel")
    if active_panel not in {"import", "discover"}:
        return
    with st.container(key="contract-import-expander"):
        title_col, close_col = st.columns([8, .5], vertical_alignment="center")
        title_col.markdown("### Import API docs or contract")
        with close_col:
            if st.button(
                "Close import", key=f"close_contract_import_{project_id}",
                icon=":material/close:", help="Close the contract import panel",
                type="tertiary",
            ):
                st.session_state["workspace_contract_panel"] = None
                st.rerun()
        source_col, format_col = st.columns([1.3, 1], gap="small")
        source_kind = source_col.selectbox(
            "Source", ["Paste text or contract", "Upload file", "Public documentation URL"],
            key=f"contract_source_kind_{project_id}",
        )
        format_label = format_col.selectbox(
            "Format", ["Auto detect", "OpenAPI / Swagger", "Postman v2.1", "Prose / Markdown"],
            key=f"contract_format_{project_id}",
        )
        format_hint = {
            "Auto detect": "auto", "OpenAPI / Swagger": "openapi",
            "Postman v2.1": "postman", "Prose / Markdown": "text",
        }[format_label]
        source_content, source_name = "", ""
        source_type = "text"
        if source_kind == "Public documentation URL":
            source_type = "url"
            source_content = st.text_input(
                "Public docs URL", key=f"contract_url_{project_id}",
                placeholder="https://docs.example.com/api",
            )
            source_name = source_content
            st.caption("URL imports are anonymous and limited to publicly reachable pages up to 5 MB.")
        elif source_kind == "Upload file":
            uploaded = st.file_uploader(
                "Choose a contract or documentation file",
                type=["json", "yaml", "yml", "md", "txt"],
                key=f"contract_file_{project_id}",
            )
            if uploaded:
                source_name = uploaded.name
                source_content = uploaded.getvalue().decode("utf-8", errors="replace")
        else:
            source_content = st.text_area(
                "Paste OpenAPI, Postman, or API documentation text", height=100,
                key=f"contract_text_{project_id}",
                placeholder="Paste a JSON/YAML contract or Markdown/plain text API documentation...",
            )
            source_name = "Pasted API documentation"

        preview_clicked = st.button(
            "Discover endpoints", type="primary", icon=":material/search:",
            key=f"contract_preview_button_{project_id}", disabled=not source_content,
        )
        if preview_clicked:
            try:
                with st.spinner("Reading contract and discovering endpoints..."):
                    preview = api_post("/api/v1/contracts/preview", {
                        "source_type": source_type, "content": source_content,
                        "source_name": source_name, "format_hint": format_hint,
                    })
                st.session_state[preview_key] = {
                    "project_id": project_id, "source": {
                        "source_type": source_type, "content": source_content,
                        "source_name": source_name, "format_hint": format_hint,
                    },
                    "data": preview,
                }
                st.rerun()
            except Exception as exc:
                st.error(f"Could not discover endpoints: {exc}")

    preview_state = st.session_state.get(preview_key)
    if not preview_state or preview_state.get("project_id") != project_id:
        preview_state = None
    if preview_state:
        preview = preview_state["data"]
        with st.container(border=True):
            heading_col, source_col = st.columns([3, 2], vertical_alignment="center")
            heading_col.subheader(f"Review endpoints · {len(preview['endpoints'])}")
            source_col.caption(f"{preview.get('source_name')} · {preview.get('source_format', '').upper()}")
            if preview.get("base_url_required"):
                base_col, apply_col = st.columns([4, 1], vertical_alignment="bottom")
                with base_col:
                    base_url = st.text_input(
                        "API base URL", key=f"contract_base_url_{project_id}",
                        placeholder="https://api.example.com/v1",
                        help="Used to turn relative contract paths into executable request URLs.",
                    )
                with apply_col:
                    apply_base = st.button(
                        "Apply", key=f"contract_apply_base_{project_id}",
                        disabled=not base_url.strip(), width="stretch",
                    )
                if apply_base:
                    try:
                        with st.spinner("Applying the API base URL..."):
                            updated = api_post("/api/v1/contracts/preview", {
                                **preview_state["source"], "base_url": base_url.strip(),
                                "source_id": preview["source_id"],
                            })
                        preview_state["data"] = updated
                        st.session_state[preview_key] = preview_state
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Could not apply the API base URL: {exc}")
                st.info("Provide a base URL before importing endpoints with relative or unresolved URLs.")

            st.caption("Every discovered endpoint is listed below. Uncheck entries you do not want to import.")
            reviewed_endpoints = {}
            for index, endpoint in enumerate(preview["endpoints"]):
                endpoint_id = endpoint.get("id", str(index))
                checkbox_key = f"contract_import_{preview['source_id']}_{endpoint_id}"
                method_key = f"contract_method_{preview['source_id']}_{endpoint_id}"
                st.session_state.setdefault(checkbox_key, True)
                path = (endpoint.get("contract") or {}).get("path") or endpoint.get("url", "")
                method = str(st.session_state.get(method_key, endpoint.get("method", "GET"))).upper()
                include_col, method_col, name_col, path_col = st.columns(
                    [0.45, 0.8, 2.4, 4.35], vertical_alignment="center"
                )
                include_col.checkbox("Import endpoint", key=checkbox_key, label_visibility="collapsed")
                method_col.markdown(f":{METHOD_COLORS.get(method, 'gray')}-badge[{method}]")
                name_col.markdown(f"**{_truncate(endpoint.get('name') or 'Untitled endpoint', 38)}**")
                path_col.code(path, language="text", wrap_lines=True)
                with st.expander(f"Edit request · {endpoint.get('name') or path}", expanded=False):
                    if endpoint.get("deprecated"):
                        st.caption("Deprecated operation is included from the source contract.")
                    if endpoint.get("source_excerpt"):
                        st.caption(endpoint["source_excerpt"])

                    method_options = ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS", "TRACE"]
                    st.session_state.setdefault(method_key, method if method in method_options else "GET")
                    endpoint_method = st.selectbox(
                        "Request type", method_options, key=method_key,
                    )

                    header_rows = _contract_editor_rows(endpoint.get("headers", {}))
                    query_rows = _contract_editor_rows(endpoint.get("query_params", []))
                    headers_col, query_col = st.columns(2, gap="small")
                    with headers_col:
                        headers = _render_contract_rows(
                            "Headers", header_rows,
                            f"contract_headers_{preview['source_id']}_{endpoint_id}",
                        )
                    with query_col:
                        query_params = _render_contract_rows(
                            "Query parameters", query_rows,
                            f"contract_query_{preview['source_id']}_{endpoint_id}",
                        )

                    body_key = f"contract_body_{preview['source_id']}_{endpoint_id}"
                    body_included_key = f"contract_body_enabled_{preview['source_id']}_{endpoint_id}"
                    body_allowed = endpoint_method not in {"GET", "DELETE"}
                    if body_key not in st.session_state:
                        initial_body = endpoint.get("body")
                        st.session_state[body_key] = (
                            json.dumps(initial_body, ensure_ascii=False, indent=2)
                            if isinstance(initial_body, (dict, list))
                            else str(initial_body or "")
                        )
                    st.session_state.setdefault(
                        body_included_key,
                        bool(endpoint.get("include_body", endpoint.get("body") is not None)),
                    )
                    if body_allowed:
                        include_body = st.checkbox(
                            "Include payload", key=body_included_key,
                            help="Send this payload with the imported request.",
                        )
                        body_text = st.text_area(
                            "Payload", key=body_key, height=100,
                            disabled=not include_body,
                            placeholder='{"key": "value"}',
                        )
                        if include_body and body_text.strip():
                            try:
                                body = json.loads(body_text)
                            except json.JSONDecodeError:
                                body = body_text
                        else:
                            body = None
                    else:
                        st.session_state[body_included_key] = False
                        st.session_state[body_key] = ""
                        body = None
                        st.caption(f"{endpoint_method} requests are imported without a payload.")

                    endpoint.update({
                        "method": endpoint_method,
                        "headers": headers,
                        "query_params": query_params,
                        "body": body,
                        "include_body": body_allowed and bool(st.session_state[body_included_key]),
                    })
                    reviewed_endpoints[endpoint_id] = endpoint

            collection_options = {item["id"]: item["name"] for item in collections}
            create_new_value = "__create_contract_collection__"
            option_ids = list(collection_options) + [create_new_value]
            default_collection = st.session_state.get("selected_collection_id")
            default_index = option_ids.index(default_collection) if default_collection in option_ids else 0
            destination = st.selectbox(
                "Save imported requests to", option_ids,
                index=default_index,
                format_func=lambda value: "Create a new collection" if value == create_new_value else collection_options[value],
                key=f"contract_destination_{project_id}_{preview['source_id']}",
            )
            new_collection_name = ""
            if destination == create_new_value:
                new_collection_name = st.text_input(
                    "New collection name", value=preview.get("title") or "Imported API",
                    key=f"contract_collection_name_{project_id}_{preview['source_id']}",
                )
            selected_endpoints = [
                reviewed_endpoints.get(endpoint.get("id"), endpoint) for endpoint in preview["endpoints"]
                if st.session_state.get(f"contract_import_{preview['source_id']}_{endpoint.get('id')}", True)
            ]
            blocked_by_url = any(endpoint.get("_base_url_required") for endpoint in selected_endpoints)
            import_col, clear_col = st.columns([1.3, 5], vertical_alignment="center")
            with import_col:
                import_clicked = st.button(
                    f"Import {len(selected_endpoints)} endpoint(s)",
                    type="primary", icon=":material/download:",
                    key=f"contract_import_button_{project_id}_{preview['source_id']}",
                    disabled=not selected_endpoints or blocked_by_url,
                )
            with clear_col:
                if st.button("Discard preview", key=f"contract_discard_{project_id}_{preview['source_id']}"):
                    st.session_state.pop(preview_key, None)
                    st.rerun()
            if import_clicked:
                try:
                    if destination == create_new_value:
                        if not new_collection_name.strip():
                            raise ValueError("Enter a name for the destination collection.")
                        created = api_post(
                            f"/api/v1/projects/{project_id}/collections",
                            {"name": new_collection_name.strip()},
                        )
                        destination = created["id"]
                    payload_endpoints = []
                    for endpoint in selected_endpoints:
                        clean = dict(endpoint)
                        clean.pop("_base_url_required", None)
                        if clean.get("method") in {"GET", "DELETE"}:
                            clean["body"] = None
                            clean["include_body"] = False
                        payload_endpoints.append(clean)
                    with st.spinner("Saving reviewed endpoints to the project..."):
                        result = api_post(
                            f"/api/v1/projects/{project_id}/contracts/import",
                            {"collection_id": destination, "endpoints": payload_endpoints},
                        )
                    _refresh_project_preserving_drafts(project_id)
                    st.session_state["selected_collection_id"] = destination
                    st.session_state.setdefault("contract_flow_discoveries", {})[result["source_id"]] = {
                        "dependencies": result.get("dependencies", []),
                        "candidate_flows": result.get("candidate_flows", []),
                    }
                    st.session_state.pop(preview_key, None)
                    st.session_state["contract_import_notice"] = (
                        f"Imported {len(result['imported'])} endpoint(s). "
                        "They remain excluded from test generation until enabled."
                    )
                    st.rerun()
                except Exception as exc:
                    st.error(f"Could not import endpoints: {exc}")

    project = st.session_state.get("current_project") or {}
    contract_sources = {}
    for endpoint in project.get("endpoints", []):
        contract = endpoint.get("contract") or {}
        if contract.get("source_id"):
            contract_sources[contract["source_id"]] = contract.get("source_name") or contract["source_id"]
    if not contract_sources:
        return
    with st.container(key="contract-discovery-expander"):
        title_col, close_col = st.columns([8, .5], vertical_alignment="center")
        title_col.markdown("### Discover flows from imported contracts")
        with close_col:
            if st.button(
                "Close discovery", key=f"close_contract_discovery_{project_id}",
                icon=":material/close:", help="Close contract flow discovery",
                type="tertiary",
            ):
                st.session_state["workspace_contract_panel"] = None
                st.rerun()
        labels = {source_id: f"{name} · {source_id[:8]}" for source_id, name in contract_sources.items()}
        source_ids = list(labels)
        source_id = st.selectbox(
            "Imported contract", source_ids,
            format_func=lambda value: labels[value],
            key=f"contract_flow_source_{project_id}",
        )
        discoveries = st.session_state.setdefault("contract_flow_discoveries", {})
        if source_id not in discoveries:
            if st.button("Analyze dependencies", key=f"contract_discover_{project_id}_{source_id}", type="primary"):
                try:
                    with st.spinner("Analyzing response and request schemas..."):
                        discoveries[source_id] = api_post(
                            f"/api/v1/projects/{project_id}/contracts/flow-candidates",
                            {"source_id": source_id},
                        )
                    candidate_count = len(discoveries[source_id].get("candidate_flows", []))
                    _queue_toast(f"Contract analysis complete · {candidate_count} flow candidate(s).")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Could not discover contract flows: {exc}")
            return
        discovery = discoveries[source_id]
        dependencies = discovery.get("dependencies", [])
        candidates = discovery.get("candidate_flows", [])
        if not dependencies:
            st.info("No response-to-request field dependencies were found in this contract.")
            return
        endpoint_by_id = {item["id"]: item for item in project.get("endpoints", [])}
        st.markdown(f"**{len(dependencies)} dependency link(s) · {len(candidates)} candidate flow(s)**")
        with st.expander("Dependency evidence", expanded=False):
            for edge in dependencies:
                producer = endpoint_by_id.get(edge["from"], {})
                consumer = endpoint_by_id.get(edge["to"], {})
                evidence = ", ".join(
                    f"{item.get('response_field')} → {item.get('request_field')}"
                    for item in edge.get("evidence", [])
                )
                cycle_label = " · cycle edge" if edge.get("cyclic") else ""
                st.caption(
                    f"{producer.get('method')} {producer.get('name')} → "
                    f"{consumer.get('method')} {consumer.get('name')} · {evidence}{cycle_label}"
                )
        selected_candidates = []
        with st.container(key="contract-candidate-list"):
            for candidate in candidates:
                candidate_id = candidate["id"]
                ordered = [endpoint_by_id.get(item, {}) for item in candidate["endpoint_ids"]]
                path_label = " → ".join(
                    f"{item.get('method', 'GET')} {item.get('name') or item.get('url')}" for item in ordered
                )
                selected = st.checkbox(
                    path_label, value=True,
                    key=f"contract_candidate_{project_id}_{candidate_id}",
                )
                for edge in candidate.get("dependencies", []):
                    evidence_text = ", ".join(
                        f"{item.get('response_field')} → {item.get('request_field')}"
                        for item in edge.get("evidence", [])
                    )
                    st.caption(evidence_text)
                if selected:
                    selected_candidates.append(candidate_id)
        if not candidates:
            st.caption("The dependency graph has no acyclic multi-endpoint paths to execute.")
            return
        business_requirements = st.text_area(
            "Business meaning or rules for these flows (optional)", height=90,
            key=f"contract_flow_requirements_{project_id}_{source_id}",
            placeholder="For example, describe what makes a checkout complete or which outcomes should be asserted.",
        )
        if st.button(
            "Generate flow test cases", type="primary", icon=":material/auto_awesome:",
            key=f"contract_generate_flows_{project_id}_{source_id}",
            disabled=not selected_candidates,
        ):
            try:
                with st.spinner("Generating business-named flow scenarios..."):
                    generated_response = api_post(
                        f"/api/v1/projects/{project_id}/contracts/generate-flows",
                        {"source_id": source_id, "candidate_ids": selected_candidates,
                         "business_requirements": business_requirements or None},
                    )
                generated = _accept_generation_response(generated_response, "Discovered Flow")
                st.session_state["executions"] = {}
                _queue_toast(f"Generated {len(generated)} flow test case(s). Review them in Test Cases.")
            except Exception as exc:
                st.error(f"Could not generate flow test cases: {exc}")


def _new_request_draft(saved: dict | None = None) -> dict:
    """Create independent editor state, optionally initialized from a saved request."""
    saved = dict(saved or {})
    assertions = _normalise_request_assertions(saved.get("assertions"))
    return {
        "tab_id": str(uuid.uuid4()),
        "id": saved.get("id"),
        "collection_id": saved.get("collection_id"),
        "name": saved.get("name", "New Request"),
        "method": saved.get("method", "GET"),
        "url": saved.get("url", ""),
        "headers": _request_rows(saved.get("headers", {})),
        "query_params": _request_rows(saved.get("query_params", {})),
        "body": saved.get("body") if isinstance(saved.get("body"), str) else json.dumps(saved.get("body"), ensure_ascii=False) if saved.get("body") is not None else "",
        "include_body": saved.get("include_body", True),
        "include_for_generation": saved.get("include_for_generation", saved.get("include", False)),
        "contract": saved.get("contract"),
        "source_excerpt": saved.get("source_excerpt", ""),
        "deprecated": saved.get("deprecated", False),
        "assertions": assertions,
        "response": None,
    }


def _normalise_request_assertions(assertions: dict | None) -> dict:
    """Normalize saved playground assertions and provide defaults for each type.

    Args:
        assertions (dict | None): Stored assertion groups, if present.

    Returns:
        dict: Repeatable assertion lists with stable UI identifiers.
    """
    source = assertions if isinstance(assertions, dict) else {}
    defaults = {
        "status": [{"enabled": True, "expected_status": 200}],
        "body_contains": [{"enabled": False, "value": ""}],
        "jsonpath": [{"enabled": False, "path": "", "expected_value": ""}],
        "response_schema": [{"enabled": False, "schema": "{}"}],
    }
    normalized = {}
    for assertion_type, default_values in defaults.items():
        values = source.get(assertion_type, default_values)
        values = values if isinstance(values, list) else [values]
        normalized[assertion_type] = []
        for value in values:
            if isinstance(value, dict):
                item = dict(value)
                item["id"] = item.get("id") or str(uuid.uuid4())
                item.setdefault("enabled", assertion_type == "status")
                normalized[assertion_type].append(item)
    return normalized


def _request_http_payload(draft: dict) -> dict:
    """Build the effective HTTP payload shared by quick send and assertion runs.

    Args:
        draft (dict): Current request playground draft.

    Returns:
        dict: Request fields accepted by the HTTP API.

    Raises:
        ValueError: If the URL is not absolute HTTP(S).
        json.JSONDecodeError: If a JSON content type has an invalid body.
    """
    if not draft["url"].startswith(("http://", "https://")):
        raise ValueError("Enter an absolute http:// or https:// URL.")
    url, query_rows = _normalise_request_url(draft["url"], draft["query_params"])
    headers = _effective_rows(draft["headers"])
    body = draft["body"] if draft["include_body"] and draft["body"] else None
    content_type = next((value for key, value in headers.items() if key.lower() == "content-type"), "")
    if isinstance(body, str) and body.strip() and content_type.lower().split(";")[0] == "application/json":
        body = json.loads(body)
    return {
        "method": draft["method"], "url": url, "headers": headers,
        "query_params": _effective_rows(query_rows), "body": body,
    }


def _selected_request_assertions(assertions: dict, assertion_id: str | None = None) -> list[dict]:
    """Select enabled checks for a batch or one check for an individual run.

    Args:
        assertions (dict): Request assertion groups keyed by assertion type.
        assertion_id (str | None): Specific assertion ID, including disabled checks.

    Returns:
        list[dict]: Flattened assertion payload accepted by the execution API.
    """
    selected = []
    for assertion_type, group in assertions.items():
        for item in group:
            if assertion_id is not None and item.get("id") != assertion_id:
                continue
            if assertion_id is None and not item.get("enabled"):
                continue
            selected.append({
                "id": item.get("id"), "type": assertion_type,
                **{key: value for key, value in item.items() if key != "id"},
            })
            if assertion_id is not None:
                return selected
    return selected


def _clean_request_rows(rows: list[dict]) -> list[dict]:
    """Remove editor-only identifiers before saving request rows."""
    return [{key: value for key, value in row.items() if key != "_ui_id"} for row in rows]


def _effective_rows(rows: list[dict]) -> dict:
    """Return enabled editor rows as a request mapping."""
    return {row["key"]: row.get("value", "") for row in rows if row.get("key") and row.get("enabled", True)}


def _normalise_request_url(url: str, query_rows: list[dict]) -> tuple[str, list[dict]]:
    """Move URL query values into the query editor while avoiding duplicate keys."""
    parts = urlsplit(url)
    existing = parse_qsl(parts.query, keep_blank_values=True)
    rows = list(query_rows)
    present = {row.get("key") for row in rows}
    rows.extend(
        {"key": key, "value": value, "enabled": True, "_ui_id": str(uuid.uuid4())}
        for key, value in existing if key not in present
    )
    clean_url = urlunsplit((parts.scheme, parts.netloc, parts.path, "", parts.fragment))
    return clean_url, rows


def _refresh_project_preserving_drafts(project_id: str) -> None:
    """Refresh project data and caches while preserving temporary request tabs.

    Args:
        project_id (str): Project to reload from the backend.

    Returns:
        None: Updates project data, generation order, and cache state.
    """
    project = api_get(f"/api/v1/projects/{project_id}")
    st.session_state["current_project"] = project
    st.session_state["endpoints"] = project.get("endpoints", [])
    st.session_state["generation_order_ids"] = project.get("generation_order_ids", [])
    _fetch_projects_cached.clear()
    _fetch_collection_export_cached.clear()


def _persist_generation_order(project_id: str, request_ids: list[str]) -> list[str]:
    """Save and synchronize the project flow order.

    Args:
        project_id (str): Project that owns the request order.
        request_ids (list[str]): Ordered saved-request IDs.

    Returns:
        list[str]: Canonical order returned by the backend.
    """
    result = api_put(
        f"/api/v1/projects/{project_id}/generation-order",
        {"request_ids": request_ids},
    )
    saved_order = result.get("generation_order_ids", request_ids)
    st.session_state["generation_order_ids"] = saved_order
    project = st.session_state.get("current_project") or {}
    if project.get("id") == project_id:
        project["generation_order_ids"] = saved_order
    return saved_order


def _set_generation_eligibility(
    project_id: str, endpoints: list[dict], eligible: bool,
) -> None:
    """Persist generation eligibility for requests and synchronize their order.

    Args:
        project_id (str): Project owning the saved requests.
        endpoints (list[dict]): Requests whose generation eligibility changes.
        eligible (bool): Whether requests should be available for generation.

    Returns:
        None: Updates request records, saved order, project data, and widget state.
    """
    order = list(st.session_state.get("generation_order_ids", []))
    for endpoint in endpoints:
        request_id = endpoint["id"]
        was_eligible = bool(endpoint.get(
            "include_for_generation", endpoint.get("include", False)
        ))
        if was_eligible != eligible:
            api_put(
                f"/api/v1/projects/{project_id}/collections/{endpoint['collection_id']}/requests/{request_id}",
                {"include_for_generation": eligible, "include": eligible},
            )
        if eligible and request_id not in order:
            order.append(request_id)
        elif not eligible:
            order = [item for item in order if item != request_id]

    _persist_generation_order(project_id, order)
    _refresh_project_preserving_drafts(project_id)


def _toggle_collection_expanded(collection_id: str) -> None:
    """Toggle one collection in the API Workspace request browser.

    Args:
        collection_id (str): Collection whose request list should be shown or hidden.

    Returns:
        None: Updates the expanded collection IDs in session state.
    """
    expanded = set(st.session_state.get("workspace_expanded_collections", []))
    if collection_id in expanded:
        expanded.remove(collection_id)
    else:
        expanded.add(collection_id)
    st.session_state["workspace_expanded_collections"] = list(expanded)


def _sync_generation_eligibility_widget(
    widget_key: str, revision_key: str, enabled: bool, revision: int,
) -> None:
    """Refresh a keyed eligibility checkbox after a persisted bulk update.

    Args:
        widget_key (str): Session-state key assigned to the checkbox.
        revision_key (str): Key storing the revision last seen by that checkbox.
        enabled (bool): Current persisted eligibility value.
        revision (int): Current project eligibility revision.

    Returns:
        None: Seeds or refreshes widget state before the checkbox is rendered.
    """
    if widget_key not in st.session_state or st.session_state.get(revision_key) != revision:
        st.session_state[widget_key] = enabled
        st.session_state[revision_key] = revision


def _render_collection_navigator(project: dict, project_id: str) -> str | None:
    """Render Postman-style collection navigator with request tree.

    Args:
        project (dict): Current project and its collections and requests.
        project_id (str): Stable identifier of the active project.

    Returns:
        str | None: Selected collection ID used as the default save destination.
    """
    collections = project.get("collections", [])
    all_requests = project.get("endpoints", [])
    collection_ids = {item["id"] for item in collections}
    selected_id = st.session_state.get("selected_collection_id")
    if selected_id not in collection_ids:
        selected_id = collections[0]["id"] if collections else None
        st.session_state["selected_collection_id"] = selected_id

    expanded_ids = st.session_state.setdefault(
        "workspace_expanded_collections", [selected_id] if selected_id else [],
    )
    expanded_ids = [item for item in expanded_ids if item in collection_ids]
    st.session_state["workspace_expanded_collections"] = expanded_ids

    with st.container(key="collection-browser-header"):
        project_name = html.escape(str(project.get("name") or "Workspace"), quote=True)
        st.markdown(
            f"<div class='aa-navigator-title'>{project_name}</div>"
            "<div class='aa-navigator-subtitle'>API Workspace</div>",
            unsafe_allow_html=True,
        )
        import_col, discover_col = st.columns(
            [1, 1], vertical_alignment="center",
        )
        if import_col.button(
            "Import", key=f"navigator_import_contract_{project_id}",
            icon=":material/file_upload:", type="primary", width="stretch",
        ):
            st.session_state["workspace_contract_panel"] = "import"
            st.rerun()
        contract_sources = {
            (endpoint.get("contract") or {}).get("source_id")
            for endpoint in all_requests
            if (endpoint.get("contract") or {}).get("source_id")
        }
        if discover_col.button(
            "Discover", key=f"navigator_discover_flows_{project_id}",
            icon=":material/account_tree:", disabled=not contract_sources, width="stretch",
        ):
            st.session_state["workspace_contract_panel"] = "discover"
            st.rerun()

    with st.container(key="navigator-search-row"):
        create_col, search_col = st.columns([.48, 4.3], vertical_alignment="center")
        with create_col:
            with st.popover(
                "Create collection", icon=":material/add:",
                key=f"navigator_create_collection_{project_id}",
            ):
                with st.form(f"create_request_collection_{project_id}", clear_on_submit=True):
                    collection_name = st.text_input("Collection name", placeholder="e.g. Authentication")
                    create_clicked = st.form_submit_button(
                        "Create collection", type="primary", width="stretch",
                    )
                if create_clicked:
                    if not collection_name.strip():
                        st.error("Enter a collection name.")
                    else:
                        try:
                            created = api_post(
                                f"/api/v1/projects/{project_id}/collections",
                                {"name": collection_name.strip()},
                            )
                            _refresh_project_preserving_drafts(project_id)
                            _queue_toast("Collection created.")
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Could not create collection: {exc}")
        with search_col:
            search_text = st.text_input(
                "Search collections and requests",
                key=f"navigator_search_{project_id}",
                placeholder="Search collections and requests",
                label_visibility="collapsed",
            ).strip().casefold()
    # Render collections as a Postman-style tree
    with st.container(key="collection-browser-scroll"):
        st.markdown("#### Collections")
        if not collections:
            _empty_state("No collections yet", "Create a collection here or import an API contract.")
            return selected_id

        visible_collection_count = 0
        for collection in collections:
            collection_id = collection["id"]
            saved_requests = collection.get("requests", [])
            collection_name = str(collection.get("name") or "Untitled collection")
            collection_matches = search_text in collection_name.casefold() if search_text else True
            matching_requests = [
                request for request in saved_requests
                if not search_text or collection_matches or any(
                    search_text in str(request.get(field) or "").casefold()
                    for field in ("name", "url", "method")
                )
            ]
            if search_text and not collection_matches and not matching_requests:
                continue
            visible_collection_count += 1
            is_expanded = collection_id in expanded_ids or bool(search_text)
            collection_eligible = bool(saved_requests) and all(
                bool(request.get("include_for_generation", request.get("include", False)))
                for request in saved_requests
            )
            collection_eligibility_key = f"collection_generation_{collection_id}"
            revision = st.session_state.get("generation_eligibility_revision", 0)
            _sync_generation_eligibility_widget(
                collection_eligibility_key,
                f"collection_generation_revision_{collection_id}",
                collection_eligible,
                revision,
            )

            # Collection header row
            selected_collection_class = "selected-" if collection_id == selected_id else ""
            expanded_collection_class = "expanded-" if is_expanded else "collapsed-"
            with st.container(
                key=f"collection-tree-row-{selected_collection_class}{expanded_collection_class}{collection_id}"
            ):
                col_check, col_title, col_menu = st.columns(
                    [0.45, 5, 0.9], vertical_alignment="center",
                )
                with col_check:
                    is_collection_selected = st.checkbox(
                        f"Include all {collection_name} requests for generation",
                        key=collection_eligibility_key,
                        label_visibility="collapsed",
                        disabled=not saved_requests,
                    )
                    if is_collection_selected != collection_eligible:
                        try:
                            _set_generation_eligibility(
                                project_id, saved_requests, is_collection_selected,
                            )
                            st.session_state["generation_eligibility_revision"] = revision + 1
                            _queue_toast(
                                f"All requests in {collection_name} enabled for generation."
                                if is_collection_selected
                                else f"All requests in {collection_name} excluded from generation."
                            )
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Could not update collection eligibility: {exc}")
                with col_title:
                    expand_label = f"{'▾' if is_expanded else '▸'}  {collection_name}  ·  {len(saved_requests)}"
                    if st.button(
                        expand_label, key=f"toggle_collection_{collection_id}",
                        type="tertiary", width="stretch",
                    ):
                        _toggle_collection_expanded(collection_id)
                        st.session_state["selected_collection_id"] = collection_id
                        st.rerun()
                with col_menu:
                    with st.popover(
                        "Collection actions", icon=":material/more_vert:",
                        key=f"collection_menu_{collection_id}",
                    ):
                        rename_key = f"rename_collection_value_{collection_id}"
                        st.text_input(
                            "Rename collection", value=collection_name, key=rename_key,
                        )
                        if st.button("Rename", key=f"rename_collection_button_{collection_id}", width="stretch"):
                            try:
                                new_name = st.session_state[rename_key].strip()
                                if not new_name:
                                    raise ValueError("Collection name is required.")
                                api_put(
                                    f"/api/v1/projects/{project_id}/collections/{collection_id}",
                                    {"name": new_name},
                                )
                                _refresh_project_preserving_drafts(project_id)
                                _queue_toast("Collection renamed.")
                                st.rerun()
                            except Exception as exc:
                                st.error(f"Could not rename collection: {exc}")
                        export_payload = _fetch_collection_export_cached(project_id, collection_id)
                        st.download_button(
                            "Export Postman collection",
                            data=json.dumps(export_payload, ensure_ascii=False, indent=2),
                            file_name=f"{collection_name}.postman_collection.json",
                            mime="application/json", key=f"export_collection_{collection_id}",
                            width="stretch",
                        )
                        confirm_delete = st.checkbox(
                            "Confirm delete collection and its requests",
                            key=f"confirm_delete_collection_{collection_id}",
                        )
                        if st.button("Delete collection", key=f"delete_collection_{collection_id}", type="secondary", width="stretch", disabled=not confirm_delete):
                            try:
                                api_delete(f"/api/v1/projects/{project_id}/collections/{collection_id}")
                                _refresh_project_preserving_drafts(project_id)
                                st.session_state["selected_collection_id"] = [
                                    cid for cid in st.session_state.get("selected_collection_id", [])
                                    if cid != collection_id
                                ] if isinstance(st.session_state.get("selected_collection_id"), list) else (
                                    None if st.session_state.get("selected_collection_id") == collection_id else st.session_state.get("selected_collection_id")
                                )
                                _queue_toast("Collection deleted.")
                                st.rerun()
                            except Exception as exc:
                                st.error(f"Could not delete collection: {exc}")

            if not is_expanded:
                continue
            if not matching_requests:
                if not saved_requests:
                    st.caption("This collection is empty. Save a request here from the playground.")
                continue

            # Render individual request rows under the collection
            for saved in matching_requests:
                request_id = saved["id"]
                method = str(saved.get("method") or "GET").upper()
                display_name = str(saved.get("name") or saved.get("url") or "Untitled request")
                request_url = str(saved.get("url") or "No URL configured")
                eligible = bool(saved.get("include_for_generation", saved.get("include", False)))
                is_active_request = any(
                    draft.get("id") == request_id
                    and draft.get("tab_id") == st.session_state.get("active_request_tab_id")
                    for draft in st.session_state["request_drafts"]
                )
                eligibility_key = f"request_generation_{request_id}"
                revision = st.session_state.get("generation_eligibility_revision", 0)
                _sync_generation_eligibility_widget(
                    eligibility_key,
                    f"request_generation_revision_{request_id}",
                    eligible,
                    revision,
                )
                selected_request_class = "selected-" if is_active_request else ""

                with st.container(key=f"browser-request-row-{selected_request_class}{request_id}"):
                    col_check, col_method, col_name, col_menu = st.columns(
                        [0.45, 0.9, 3.2, 0.85], vertical_alignment="center",
                    )

                    # Individual request checkbox
                    with col_check:
                        is_selected = eligible
                        new_selected = st.checkbox(
                            f"Include {display_name} in generation",
                            key=eligibility_key,
                            label_visibility="collapsed",
                        )
                        if new_selected != is_selected:
                            _set_generation_eligibility(project_id, [saved], new_selected)
                            st.session_state["generation_eligibility_revision"] = revision + 1
                            st.rerun()

                    with col_method:
                        st.markdown(_method_badge(method))

                    with col_name:
                        if st.button(
                            display_name, key=f"open_saved_{request_id}",
                            type="tertiary", width="stretch",
                            help=f"{request_url} · Open request in playground",
                        ):
                            existing = next(
                                (d for drafts in [st.session_state["request_drafts"]] for d in drafts if d.get("id") == request_id),
                                None,
                            )
                            if not existing:
                                existing = _new_request_draft(saved)
                                st.session_state["request_drafts"].append(existing)
                            st.session_state["active_request_tab_id"] = existing["tab_id"]
                            st.session_state["selected_collection_id"] = collection_id
                            st.rerun()

                    with col_menu:
                        with st.popover("Request actions", icon=":material/more_vert:", key=f"request_menu_{request_id}"):
                            rename_key = f"rename_request_value_{request_id}"
                            st.text_input(
                                "Rename request", value=display_name, key=rename_key,
                            )
                            if st.button("Rename", key=f"rename_request_button_{request_id}", width="stretch"):
                                try:
                                    new_name = st.session_state[rename_key].strip()
                                    if not new_name:
                                        raise ValueError("Request name is required.")
                                    api_put(
                                        f"/api/v1/projects/{project_id}/collections/{collection_id}/requests/{request_id}",
                                        {"name": new_name},
                                    )
                                    for d in st.session_state["request_drafts"]:
                                        if d.get("id") == request_id:
                                            d["name"] = new_name
                                            st.session_state[f"name_{d['tab_id']}"] = new_name
                                    _refresh_project_preserving_drafts(project_id)
                                    _queue_toast("Request renamed.")
                                    st.rerun()
                                except Exception as exc:
                                    st.error(f"Could not rename request: {exc}")
                            if st.button("Duplicate", key=f"duplicate_request_{request_id}", icon=":material/content_copy:", width="stretch"):
                                try:
                                    duplicate = copy.deepcopy(saved)
                                    duplicate.pop("id", None)
                                    duplicate["name"] = f"{display_name} Copy"
                                    duplicate["include_for_generation"] = False
                                    duplicate["include"] = False
                                    api_post(
                                        f"/api/v1/projects/{project_id}/collections/{collection_id}/requests",
                                        duplicate,
                                    )
                                    _refresh_project_preserving_drafts(project_id)
                                    st.session_state["selected_collection_id"] = collection_id
                                    _queue_toast("Request duplicated.")
                                    st.rerun()
                                except Exception as exc:
                                    st.error(f"Could not duplicate request: {exc}")
                            confirm_delete = st.checkbox(
                                "Confirm delete request", key=f"confirm_delete_request_{request_id}",
                            )
                            if st.button("Delete request", key=f"delete_request_{request_id}", icon=":material/delete:", type="secondary", width="stretch", disabled=not confirm_delete):
                                try:
                                    api_delete(f"/api/v1/projects/{project_id}/collections/{collection_id}/requests/{request_id}")
                                    _refresh_project_preserving_drafts(project_id)
                                    _persist_generation_order(
                                        project_id, st.session_state.get("generation_order_ids", []),
                                    )
                                    _queue_toast("Saved request deleted.")
                                    st.rerun()
                                except Exception as exc:
                                    st.error(f"Could not delete request: {exc}")

    return selected_id



def _render_request_rows(rows: list[dict], kind: str, tab_id: str) -> list[dict]:
    """Render a Postman-like editable table and retain disabled key/value rows."""
    editor_rows = [
        {
            "send": bool(row.get("enabled", True)),
            "key": str(row.get("key", "")),
            "value": "" if row.get("value") is None else str(row.get("value", "")),
            "description": str(row.get("description", "")),
        }
        for row in rows
    ]
    if not editor_rows:
        editor_rows = [{"send": True, "key": "", "value": "", "description": ""}]

    edited_rows = st.data_editor(
        editor_rows,
        key=f"{kind}_editor_{tab_id}",
        num_rows="dynamic",
        hide_index=True,
        width="stretch",
        column_order=["send", "key", "value", "description"],
        column_config={
            "send": st.column_config.CheckboxColumn(
                "Send", width="small", default=True,
                help="Include this row in the outgoing request",
            ),
            "key": st.column_config.TextColumn("Key", width="medium"),
            "value": st.column_config.TextColumn("Value", width="large"),
            "description": st.column_config.TextColumn("Description", width="medium"),
        },
        placeholder=f"Add {kind[:-1] if kind.endswith('s') else kind}",
    )

    stored_rows = []
    for row in edited_rows:
        key = str(row.get("key") or "").strip()
        value = "" if row.get("value") is None else str(row.get("value", ""))
        description = str(row.get("description") or "")
        if not key and not value and not description:
            continue
        stored_rows.append({
            "enabled": True if row.get("send") is None else bool(row["send"]),
            "key": key,
            "value": value,
            "description": description,
        })
    return stored_rows


def _render_editable_test_request(request: dict, uid: str) -> None:
    """Render and apply editable request method, URL, params, headers, and body."""
    method_options = ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]
    method = str(request.get("method", "GET")).upper()
    if method not in method_options:
        method_options.append(method)
    method_key = f"tc_request_method_{uid}"
    url_key = f"tc_request_url_{uid}"
    st.session_state.setdefault(method_key, method)
    st.session_state.setdefault(url_key, str(request.get("url", "")))

    # Keep query values in the editable Params table instead of duplicating them in the URL.
    source_url = st.session_state[url_key]
    clean_url, query_rows = _normalise_request_url(
        source_url, _request_rows(request.get("query_params", {})),
    )
    st.session_state[url_key] = clean_url

    method_col, url_col = st.columns([1, 5], vertical_alignment="bottom")
    request["method"] = method_col.selectbox(
        "Request type", method_options, key=method_key,
    )
    request["url"] = url_col.text_input("URL", key=url_key, placeholder="https://api.example.com/resource")

    params_tab, headers_tab, body_tab = st.tabs(["Params", "Headers", "Body"])
    with params_tab:
        request["query_params"] = _render_request_rows(query_rows, "tc_params", uid)
    with headers_tab:
        request["headers"] = _render_request_rows(
            _request_rows(request.get("headers", {})), "tc_headers", uid,
        )
    with body_tab:
        body_key = f"tc_request_body_{uid}"
        body = request.get("body")
        if isinstance(body, (dict, list)):
            body_text = json.dumps(body, ensure_ascii=False, indent=2)
        else:
            body_text = str(body or "")
        st.session_state.setdefault(body_key, body_text)
        edited_body = st.text_area(
            "Body / payload", key=body_key, height=180,
            placeholder='{"key": "value"}',
        )
        if edited_body.strip():
            try:
                request["body"] = json.loads(edited_body)
            except json.JSONDecodeError:
                request["body"] = edited_body
        else:
            request["body"] = None


def _render_variable_mappings(step: dict, uid: str) -> None:
    """Render repeatable response-to-request mappings for one flow step."""
    st.markdown("**Variable mappings**")
    mappings = step.setdefault("variable_mappings", [])
    if not mappings:
        st.caption("No variable mappings. Sources can use `$.field` or `1:$.field` for a specific earlier step.")
    remove_index = None
    for index, mapping in enumerate(mappings):
        if not isinstance(mapping, dict):
            mappings[index] = mapping = {"from": "", "to": "", "transform": ""}
        mapping_id = mapping.setdefault("mapping_id", str(uuid.uuid4()))
        with st.container(border=True):
            source_col, target_col, transform_col, remove_col = st.columns(
                [2.2, 2.5, 2.5, 0.45], vertical_alignment="center",
            )
            mapping["from"] = source_col.text_input(
                "Response source", value=str(mapping.get("from", "")),
                key=f"tc_mapping_from_{uid}_{mapping_id}", placeholder="1:$.access_token",
                help="JSONPath in a prior response; prefix with a 1-based step number to select one.",
            )
            mapping["to"] = target_col.text_input(
                "Request destination", value=str(mapping.get("to", "")),
                key=f"tc_mapping_to_{uid}_{mapping_id}", placeholder="headers.Authorization",
                help="Use headers.NAME, request.query.NAME, request.path.NAME, or request.body.FIELD.",
            )
            mapping["transform"] = transform_col.text_input(
                "Transform", value=str(mapping.get("transform", "")),
                key=f"tc_mapping_transform_{uid}_{mapping_id}", placeholder="Bearer {value}",
                help="Optional template; {value} is replaced by the extracted response value.",
            )
            if remove_col.button(" ", icon=":material/delete:", key=f"tc_mapping_remove_{uid}_{mapping_id}", help="Remove mapping"):
                remove_index = index
    if remove_index is not None:
        mappings.pop(remove_index)
        st.rerun()
    if st.button("Add mapping", key=f"tc_mapping_add_{uid}", icon=":material/add:"):
        mappings.append({"from": "", "to": "", "transform": ""})
        st.rerun()


def _save_request_draft(draft: dict, collection_id: str, project_id: str) -> dict:
    """Persist a request draft in the selected collection and return its saved form."""
    url, query_rows = _normalise_request_url(draft["url"], draft["query_params"])
    payload = {
        "id": draft.get("id"),
        "name": draft["name"].strip() or "Untitled Request",
        "method": draft["method"],
        "url": url,
        "headers": _clean_request_rows(draft["headers"]),
        "query_params": _clean_request_rows(query_rows),
        "body": draft["body"],
        "include_body": bool(draft["include_body"]),
        "include_for_generation": bool(draft.get("include_for_generation", False)),
        "assertions": draft.get("assertions", {}),
        **({"contract": draft["contract"]} if draft.get("contract") else {}),
        **({"source_excerpt": draft["source_excerpt"]} if draft.get("source_excerpt") else {}),
        **({"deprecated": True} if draft.get("deprecated") else {}),
    }
    saved = api_post(
        f"/api/v1/projects/{project_id}/collections/{collection_id}/requests",
        payload,
    )
    draft.update(saved)
    draft["response"] = draft.get("response")
    draft["headers"] = _request_rows(saved.get("headers", []))
    draft["query_params"] = _request_rows(saved.get("query_params", []))
    return saved


def _resolve_curl_url_sync(draft: dict, control_text: str) -> str:
    """Use the parsed URL while the browser component replaces stale cURL state.

    Args:
        draft (dict): Active request draft with an optional cURL synchronization marker.
        control_text (str): Current text reported by the browser component.

    Returns:
        str: Parsed URL during synchronization, otherwise the current component text.
    """
    sync_state = draft.get("curl_url_sync")
    if not sync_state:
        return control_text
    if control_text == sync_state["source"]:
        return sync_state["url"]
    draft.pop("curl_url_sync", None)
    return control_text


def _render_request_assertions(draft: dict, tab_id: str) -> tuple[bool, dict | None]:
    """Render repeatable request assertions and return the requested run action.

    Args:
        draft (dict): Current request draft containing assertion groups.
        tab_id (str): Stable request tab identifier for widget keys.

    Returns:
        tuple[bool, dict | None]: Run All flag and one explicitly selected assertion.
    """
    assertions = draft["assertions"]
    enabled_count = sum(
        bool(item.get("enabled"))
        for group in assertions.values()
        for item in group
    )
    run_all_col, summary_col = st.columns([1.8, 4], vertical_alignment="center")
    with run_all_col:
        run_all = st.button(
            "Run all enabled", key=f"assertions_run_all_{tab_id}",
            icon=":material/rule:", type="primary", width="stretch",
            disabled=enabled_count == 0,
        )
    with summary_col:
        st.caption(f"{enabled_count} enabled · checks run against a fresh response")

    labels = {
        "status": "Status code",
        "body_contains": "Body contains",
        "jsonpath": "Field value",
        "response_schema": "Response schema",
    }
    single_run = None
    for assertion_type, label in labels.items():
        group = assertions[assertion_type]
        with st.expander(f"{label} · {len(group)}", expanded=assertion_type == "status"):
            for index, config in enumerate(group):
                assertion_id = config["id"]
                with st.container(border=True):
                    if assertion_type == "status":
                        enabled_col, value_col, run_col, remove_col = st.columns(
                            [0.55, 4.5, 1, 0.7], vertical_alignment="center"
                        )
                        config["enabled"] = enabled_col.checkbox(
                            "Enabled", value=config.get("enabled", True),
                            key=f"request_assert_enabled_{tab_id}_{assertion_id}",
                            label_visibility="collapsed", help="Include in Run all enabled",
                        )
                        config["expected_status"] = value_col.number_input(
                            "Expected status", min_value=100, max_value=599,
                            value=int(config.get("expected_status", 200)), step=1,
                            key=f"request_assert_status_{tab_id}_{assertion_id}",
                        )
                    elif assertion_type == "body_contains":
                        enabled_col, value_col, run_col, remove_col = st.columns(
                            [0.55, 4.5, 1, 0.7], vertical_alignment="center"
                        )
                        config["enabled"] = enabled_col.checkbox(
                            "Enabled", value=config.get("enabled", False),
                            key=f"request_assert_enabled_{tab_id}_{assertion_id}",
                            label_visibility="collapsed", help="Include in Run all enabled",
                        )
                        config["value"] = value_col.text_input(
                            "Text to find", value=config.get("value", ""),
                            key=f"request_assert_body_{tab_id}_{assertion_id}",
                            placeholder="Text in response body",
                        )
                    elif assertion_type == "jsonpath":
                        enabled_col, path_col, expected_col, run_col, remove_col = st.columns(
                            [0.5, 2.2, 2.2, 1, 0.7], vertical_alignment="center"
                        )
                        config["enabled"] = enabled_col.checkbox(
                            "Enabled", value=config.get("enabled", False),
                            key=f"request_assert_enabled_{tab_id}_{assertion_id}",
                            label_visibility="collapsed", help="Include in Run all enabled",
                        )
                        config["path"] = path_col.text_input(
                            "JSONPath", value=config.get("path", ""),
                            key=f"request_assert_path_{tab_id}_{assertion_id}", placeholder="$.user.id",
                        )
                        config["expected_value"] = expected_col.text_input(
                            "Expected value", value=config.get("expected_value", ""),
                            key=f"request_assert_expected_{tab_id}_{assertion_id}",
                        )
                    else:
                        enabled_col, content_col, run_col, remove_col = st.columns(
                            [0.5, 4.5, 1, 0.7], vertical_alignment="top"
                        )
                        config["enabled"] = enabled_col.checkbox(
                            "Enabled", value=config.get("enabled", False),
                            key=f"request_assert_enabled_{tab_id}_{assertion_id}",
                            label_visibility="collapsed", help="Include in Run all enabled",
                        )
                        config["schema"] = content_col.text_area(
                            "JSON Schema", value=config.get("schema", "{}"), height=130,
                            key=f"request_assert_schema_{tab_id}_{assertion_id}",
                            placeholder='{"type": "object", "required": ["id"]}',
                            label_visibility="collapsed",
                        )

                    if run_col.button(
                        "Run", key=f"request_assert_run_{tab_id}_{assertion_id}",
                        icon=":material/play_arrow:", help="Send a fresh request and run this assertion",
                        width="stretch",
                    ):
                        single_run = {"id": assertion_id, "type": assertion_type, **{
                            key: value for key, value in config.items() if key != "id"
                        }}
                    if remove_col.button(
                        " ", key=f"request_assert_remove_{tab_id}_{assertion_id}",
                        icon=":material/delete:", help="Remove assertion",
                    ):
                        group.pop(index)
                        st.rerun()

            add_defaults = {
                "status": {"enabled": True, "expected_status": 200},
                "body_contains": {"enabled": True, "value": ""},
                "jsonpath": {"enabled": True, "path": "", "expected_value": ""},
                "response_schema": {"enabled": True, "schema": "{}"},
            }
            if st.button(f"Add {label.lower()} assertion", key=f"request_assert_add_{tab_id}_{assertion_type}"):
                group.append({"id": str(uuid.uuid4()), **add_defaults[assertion_type]})
                st.rerun()
    return run_all, single_run


def _render_request_draft(draft: dict, collections: list[dict], project_id: str) -> None:
    """Render one request editor tab, send/save actions, and its response panel."""
    tab_id = draft["tab_id"]
    method_options = ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS", "TRACE"]

    # Apply imported values before creating keyed widgets on this rerun.
    pending_curl = st.session_state.pop(f"pending_curl_{tab_id}", None)
    if pending_curl:
        parsed = pending_curl["parsed"]
        draft["method"] = parsed.get("method", "GET")
        draft["url"] = parsed.get("url", "")
        draft["curl_url_sync"] = {
            "source": pending_curl["source"],
            "url": draft["url"],
        }
        draft["url_control_sync_id"] = str(uuid.uuid4())
        draft["headers"] = _request_rows(parsed.get("headers", {}))
        draft["query_params"] = _request_rows(parsed.get("query_params", {}))
        draft["body"] = parsed.get("body") or ""
        draft["include_body"] = True
        draft["response"] = None
        st.session_state[f"method_{tab_id}"] = draft["method"] if draft["method"] in method_options else "GET"
        st.session_state[f"request-url-control-{tab_id}"] = {"text": draft["url"]}
        st.session_state.pop(f"curl_error_{tab_id}", None)
        st.session_state[f"body_{tab_id}"] = draft["body"]
        st.session_state[f"body_mode_{tab_id}"] = "raw"
        st.session_state.pop(f"header_editor_{tab_id}", None)
        st.session_state.pop(f"query_editor_{tab_id}", None)

    # Seed keyed widget values before construction. Keyed widgets read these
    # values directly, so passing a second default value would conflict.
    st.session_state.setdefault(f"method_{tab_id}", draft.get("method", "GET"))
    st.session_state.setdefault(f"body_{tab_id}", draft.get("body", ""))

    name_col, collection_col, save_col = st.columns([3.2, 2.2, 1.1], vertical_alignment="bottom")
    with name_col:
        draft["name"] = st.text_input("Request name", value=draft["name"], key=f"name_{tab_id}", placeholder="e.g. Create session")
    with collection_col:
        collection_by_id = {item["id"]: item for item in collections}
        collection_ids = list(collection_by_id)
        preferred_collection = draft.get("collection_id") or st.session_state.get("selected_collection_id")
        if preferred_collection not in collection_by_id and collection_ids:
            preferred_collection = collection_ids[0]
        selected_collection = st.selectbox(
            "Collection", collection_ids,
            index=collection_ids.index(preferred_collection) if preferred_collection else 0,
            format_func=lambda collection_id: collection_by_id[collection_id]["name"],
            key=f"save_collection_{tab_id}", disabled=not collections,
        ) if collections else None
        if not collections:
            st.caption("Create a collection to save requests")
    with save_col:
        save_clicked = st.button("Save", key=f"save_{tab_id}", disabled=not collections, icon=":material/save:", use_container_width=True)

    method_col, request_url_col, send_col = st.columns([1.15, 6.3, 1.2], vertical_alignment="bottom")
    with method_col:
        if draft["method"] not in method_options:
            draft["method"] = "GET"
        st.session_state.setdefault(f"method_{tab_id}", draft["method"])
        draft["method"] = st.selectbox("Method", method_options, key=f"method_{tab_id}")
    with request_url_col:
        url_control = render_curl_aware_url(
            draft.get("url", ""), tab_id,
            draft.get("url_control_sync_id", ""),
        )
        control_text = getattr(url_control, "text", draft.get("url", ""))
        draft["url"] = _resolve_curl_url_sync(draft, control_text)
        curl_ready = getattr(url_control, "curl_ready", None)
        curl_error_key = f"curl_error_{tab_id}"
        if curl_ready:
            try:
                parsed = api_post("/api/v1/curl/parse", {"curl": curl_ready})
                st.session_state[f"pending_curl_{tab_id}"] = {
                    "parsed": parsed,
                    "source": curl_ready,
                }
                st.session_state.pop(curl_error_key, None)
                _queue_toast("cURL parsed into the request.")
                st.rerun()
            except Exception as exc:
                st.session_state[curl_error_key] = {"text": curl_ready, "message": str(exc)}
        curl_error = st.session_state.get(curl_error_key)
        if curl_error and curl_error.get("text") == draft["url"]:
            st.error(f"Could not parse cURL: {curl_error['message']}")
    with send_col:
        send_clicked = st.button("Send", type="primary", key=f"send_{tab_id}", use_container_width=True, icon=":material/send:")

    params_tab, headers_tab, payload_tab, assertions_tab = st.tabs(
        ["Params", "Headers", "Body", "Assertions"]
    )
    with params_tab:
        st.caption("Query parameters")
        draft["query_params"] = _render_request_rows(draft["query_params"], "query", tab_id)
    with headers_tab:
        draft["headers"] = _render_request_rows(draft["headers"], "header", tab_id)
    with payload_tab:
        body_mode_key = f"body_mode_{tab_id}"
        if body_mode_key not in st.session_state:
            st.session_state[body_mode_key] = "raw" if draft["include_body"] else "none"
        body_mode = st.radio(
            "Body type", ["none", "raw"], horizontal=True,
            key=body_mode_key, label_visibility="collapsed",
        )
        draft["include_body"] = body_mode == "raw"
        if body_mode == "none":
            st.caption("This request does not include a body.")
        else:
            payload_title_col, beautify_col = st.columns([5, 1], vertical_alignment="bottom")
            with payload_title_col:
                st.markdown("**Body**")
            with beautify_col:
                if st.button("Beautify", key=f"beautify_request_{tab_id}", icon=":material/auto_awesome:", help="Format JSON body"):
                    payload = st.session_state.get(f"body_{tab_id}", draft["body"])
                    try:
                        draft["body"] = json.dumps(json.loads(payload), indent=2, ensure_ascii=False)
                        st.session_state[f"body_{tab_id}"] = draft["body"]
                    except (json.JSONDecodeError, TypeError):
                        st.info("Body is not valid JSON, so it was left unchanged.")
            draft["body"] = st.text_area("Body", height=220, key=f"body_{tab_id}", placeholder='{"key": "value"}', label_visibility="collapsed")

    with assertions_tab:
        run_all_assertions, single_assertion = _render_request_assertions(draft, tab_id)

    if save_clicked and selected_collection:
        try:
            if re.match(r"^\s*curl(?:\.exe)?(?:\s|$)", draft.get("url", ""), re.IGNORECASE):
                raise ValueError("Wait for cURL parsing to finish before saving the request.")
            _save_request_draft(draft, selected_collection, project_id)
            _refresh_project_preserving_drafts(project_id)
            _queue_toast("Request saved to collection.")
            st.rerun()
        except Exception as exc:
            st.error(f"Could not save request: {exc}")
    if send_clicked or run_all_assertions or single_assertion:
        try:
            if re.match(r"^\s*curl(?:\.exe)?(?:\s|$)", draft.get("url", ""), re.IGNORECASE):
                raise ValueError("Wait for cURL parsing to finish before sending the request.")
            request_payload = _request_http_payload(draft)
            if run_all_assertions or single_assertion:
                selected_assertions = _selected_request_assertions(
                    draft["assertions"], single_assertion.get("id") if single_assertion else None
                )
                if selected_assertions:
                    draft["response"] = api_post("/api/v1/http/execute-assertions", {
                        "request": request_payload,
                        "assertions": selected_assertions,
                    })
            else:
                draft["response"] = api_post("/api/v1/http/send", request_payload)
                _queue_toast(f"Response received · status {draft['response'].get('status', 'unknown')}.")
            if run_all_assertions or single_assertion:
                assertion_results = draft["response"].get("assertion_results", [])
                if assertion_results:
                    passed_count = sum(bool(item.get("passed")) for item in assertion_results)
                    all_passed = passed_count == len(assertion_results)
                    summary = (
                        f"Assertions complete · {passed_count}/{len(assertion_results)} passed."
                    )
                    _queue_toast(summary, "success" if all_passed else "error")
                else:
                    _queue_toast("Response received. Review the assertion results below.")
            st.session_state[f"response_pretty_{tab_id}"] = False
        except (ValueError, json.JSONDecodeError) as exc:
            st.error(f"Request is invalid: {exc}")
        except Exception as exc:
            st.error(f"Request failed: {exc}")

    response = draft.get("response")
    if response:
        st.divider()
        st.subheader("Response")
        status = response.get("status", 0)
        state = "Success" if 200 <= status < 300 else "Redirect" if 300 <= status < 400 else "Error"
        status_col, state_col, elapsed_col = st.columns([1, 1, 1])
        status_col.metric("Status code", status)
        state_col.metric("Status", state)
        elapsed_col.metric("Time", f"{response.get('elapsed_ms', 0)} ms")
        if "assertion_results" in response:
            assertion_results = response.get("assertion_results", [])
            passed_count = sum(bool(item.get("passed")) for item in assertion_results)
            overall = "passed" if response.get("assertions_passed") else "failed"
            st.markdown(
                f"{_status_badge(overall)} :gray-badge[{passed_count}/{len(assertion_results)} assertions passed]"
            )
            for assertion_result in assertion_results:
                result_col, detail_col = st.columns([1.5, 5], vertical_alignment="center")
                result_col.markdown(
                    f":{'green' if assertion_result.get('passed') else 'red'}-badge["
                    f"{'PASS' if assertion_result.get('passed') else 'FAIL'}] "
                    f":gray-badge[{assertion_result.get('type', '').replace('_', ' ').title()}]"
                )
                detail_col.caption(assertion_result.get("detail", ""))
        body_tab, response_headers_tab = st.tabs(["Response body", "Response headers"])
        with body_tab:
            response_body = response.get("body", "") or ""
            pretty_key = f"response_pretty_{tab_id}"
            if pretty_key not in st.session_state:
                st.session_state[pretty_key] = False
            language = "text"
            if st.session_state[pretty_key]:
                try:
                    response_body = json.dumps(json.loads(response_body), indent=2, ensure_ascii=False)
                    language = "json"
                except (json.JSONDecodeError, TypeError):
                    st.info("Response body is not valid JSON, so it cannot be formatted.")
            response_title_col, response_format_col = st.columns([5.6, 1], vertical_alignment="bottom")
            with response_title_col:
                st.markdown("**Response body**")
            with response_format_col:
                st.button(
                    "Raw" if st.session_state[pretty_key] else "Beautify",
                    key=f"beautify_response_{tab_id}",
                    icon=":material/format_align_left:",
                    help="Toggle formatted JSON and raw response",
                    on_click=_toggle_session_state,
                    args=(pretty_key,),
                )
            st.code(response_body or "(empty response body)", language=language)
        with response_headers_tab:
            st.json(response.get("headers", {}))


def render_api_workspace() -> None:
    """Render saved project collections, generation selection, and request tabs."""
    st.markdown(REQUEST_TAB_CSS, unsafe_allow_html=True)
    st.markdown(
        """<style>
        input[aria-label="URL"], textarea[aria-label="Body"] {
            font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
        }
        div[data-baseweb="tab-list"] { gap: .35rem; }
        div[data-baseweb="tab"] { padding: .45rem .9rem; font-size: .92rem; }
        div[data-testid="stSelectbox"] div[data-baseweb="select"] > div { font-weight: 650; }
        div[data-testid="stDataEditor"] { border-radius: .5rem; }
        .st-key-request-playground-sticky {
            position: sticky; top: .5rem; align-self: flex-start; z-index: 3;
        }

        /* Keep the navigator and playground side by side until the page is narrow. */
        .st-key-api-workspace-layout {
            --aa-panel-bg: color-mix(in srgb, var(--st-secondary-background-color) 72%, transparent);
            --aa-panel-border: color-mix(in srgb, var(--st-border-color) 82%, transparent);
        }
        .st-key-api-workspace-layout [data-testid="stHorizontalBlock"]:has(.st-key-collection-browser-header),
        .st-key-api-workspace-layout > [data-testid="stHorizontalBlock"],
        .st-key-api-workspace-layout > [data-testid="stVerticalBlock"] > [data-testid="stHorizontalBlock"] {
            display: grid !important;
            grid-template-columns: clamp(270px, 17vw, 320px) minmax(0, 1fr) !important;
            align-items: start; gap: 1rem !important;
        }
        .st-key-api-workspace-layout [data-testid="stHorizontalBlock"]:has(.st-key-collection-browser-header) > :is([data-testid="column"], [data-testid="stColumn"]),
        .st-key-api-workspace-layout > [data-testid="stHorizontalBlock"] > :is([data-testid="column"], [data-testid="stColumn"]),
        .st-key-api-workspace-layout > [data-testid="stVerticalBlock"] > [data-testid="stHorizontalBlock"] > :is([data-testid="column"], [data-testid="stColumn"]) {
            width: auto !important; min-width: 0 !important; flex: initial !important;
        }

        /* One shared panel surface frames the project heading, search, and tree. */
        .st-key-collection-browser-header {
            box-sizing: border-box; width: 100%; max-width: 100%;
            padding: .7rem .65rem .55rem;
            border: 1px solid var(--aa-panel-border);
            border-radius: 12px 12px 0 0;
            background: var(--aa-panel-bg);
        }
        .aa-navigator-title {
            overflow: hidden; font-size: 1.02rem; font-weight: 720;
            letter-spacing: -.025em; text-overflow: ellipsis; white-space: nowrap;
        }
        .aa-navigator-subtitle {
            margin-top: .12rem; font-size: .68rem; font-weight: 600;
            letter-spacing: .075em; text-transform: uppercase; opacity: .62;
        }
        .st-key-collection-browser-header [data-testid="stButton"] button {
            min-height: 2rem; padding-inline: .3rem; border-radius: 7px !important;
            font-size: .76rem; font-weight: 650;
        }
        .st-key-navigator-search-row {
            box-sizing: border-box; width: 100%; max-width: 100%;
            padding: .45rem .65rem;
            border-left: 1px solid var(--aa-panel-border);
            border-right: 1px solid var(--aa-panel-border);
            background: var(--aa-panel-bg);
        }
        .st-key-navigator-search-row [data-testid="stHorizontalBlock"] {
            align-items: center; gap: .35rem;
        }
        .st-key-navigator-search-row :is([data-testid="column"], [data-testid="stColumn"]) { min-width: 0; padding: 0; }
        .st-key-navigator-search-row :is([data-testid="column"], [data-testid="stColumn"]):first-child {
            flex: 0 0 2.25rem !important; width: 2.25rem !important;
        }
        .st-key-navigator-search-row [data-testid="stTextInput"] input {
            min-height: 2.25rem; border-radius: 8px !important; font-size: .8rem;
        }

        /* Compact tree rows keep eligibility at the left and actions at the right. */
        .st-key-collection-browser-scroll {
            box-sizing: border-box; width: 100%; max-width: 100%;
            max-height: min(70vh, 760px); overflow-x: hidden; overflow-y: auto; overscroll-behavior: contain;
            padding: .45rem .65rem .65rem;
            border: 1px solid var(--aa-panel-border); border-top: 0;
            border-radius: 0 0 12px 12px; background: var(--aa-panel-bg);
            scrollbar-gutter: stable;
        }
        .st-key-collection-browser-header > [data-testid="stVerticalBlock"],
        .st-key-navigator-search-row > [data-testid="stVerticalBlock"],
        .st-key-collection-browser-scroll > [data-testid="stVerticalBlock"] {
            box-sizing: border-box; width: 100%; max-width: 100%; min-width: 0;
        }
        .st-key-collection-browser-scroll > [data-testid="stVerticalBlock"] { gap: .1rem; }
        .st-key-collection-browser-scroll::-webkit-scrollbar { width: 7px; }
        .st-key-collection-browser-scroll::-webkit-scrollbar-thumb {
            border-radius: 20px; background: rgba(128,128,128,.28);
        }
        div[class*="st-key-collection-tree-row-"] {
            box-sizing: border-box; width: 100%; max-width: 100%; min-width: 0;
            margin: 2px 0; padding: 2px 3px;
            border: 1px solid transparent; border-radius: 8px;
            transition: background .14s ease, border-color .14s ease;
        }
        div[class*="st-key-collection-tree-row-expanded-"] { position: relative; }
        div[class*="st-key-collection-tree-row-expanded-"]::after {
            content: ""; position: absolute; z-index: 0; left: 1.25rem;
            bottom: -.55rem; height: .55rem; border-left: 1px solid var(--aa-border);
            pointer-events: none;
        }
        div[class*="st-key-collection-tree-row-"]:hover,
        div[class*="st-key-browser-request-row-"]:hover,
        div[class*="st-key-browser-request-row-"]:focus-within {
            background: var(--aa-surface-hover); border-color: var(--aa-border);
        }
        div[class*="st-key-collection-tree-row-selected-"] {
            background: var(--aa-accent-soft); border-color: rgba(255,108,55,.22);
        }
        div[class*="st-key-collection-tree-row-"] [data-testid="stHorizontalBlock"],
        div[class*="st-key-browser-request-row-"] [data-testid="stHorizontalBlock"] {
            box-sizing: border-box; width: 100%; max-width: 100%; min-width: 0;
            align-items: center; gap: .25rem;
        }
        div[class*="st-key-collection-tree-row-"] :is([data-testid="column"], [data-testid="stColumn"]),
        div[class*="st-key-browser-request-row-"] :is([data-testid="column"], [data-testid="stColumn"]) {
            box-sizing: border-box; min-width: 0; padding: 0;
        }
        div[class*="st-key-collection-tree-row-"] :is([data-testid="column"], [data-testid="stColumn"]) > [data-testid="stVerticalBlock"],
        div[class*="st-key-browser-request-row-"] :is([data-testid="column"], [data-testid="stColumn"]) > [data-testid="stVerticalBlock"] {
            min-width: 0; min-height: 2.2rem; justify-content: center; gap: 0;
        }
        div[class*="st-key-collection-tree-row-"] :is([data-testid="column"], [data-testid="stColumn"]):first-child {
            flex: 0 0 1.3rem !important; width: 1.3rem !important;
        }
        div[class*="st-key-collection-tree-row-"] :is([data-testid="column"], [data-testid="stColumn"]):last-child {
            flex: 0 0 2rem !important; width: 2rem !important;
        }
        div[class*="st-key-collection-tree-row-"] [data-testid="stButton"] button {
            min-height: 2.25rem; justify-content: flex-start !important;
            padding-inline: .35rem; border-radius: 7px !important;
            font-size: .82rem; font-weight: 620; text-align: left;
        }
        div[class*="st-key-collection-tree-row-"] [data-testid="stButton"] button p {
            overflow: hidden; text-align: left; text-overflow: ellipsis; white-space: nowrap;
        }
        div[class*="st-key-browser-request-row-"] {
            box-sizing: border-box; width: 100%; max-width: 100%; min-width: 0;
            margin: 2px 0; padding: 2px 3px;
            border: 1px solid transparent; border-radius: 8px;
            position: relative;
            transition: background .14s ease, border-color .14s ease;
        }
        div[class*="st-key-browser-request-row-"]::before {
            content: ""; position: absolute; z-index: 0; left: 1.55rem;
            top: -.2rem; bottom: -.2rem; border-left: 1px solid var(--aa-border);
            pointer-events: none;
        }
        div[class*="st-key-browser-request-row-"]::after {
            content: ""; position: absolute; z-index: 0; left: 1.55rem;
            top: 50%; width: .45rem; border-top: 1px solid var(--aa-border);
            pointer-events: none;
        }
        div[class*="st-key-browser-request-row-selected-"] {
            background: var(--aa-accent-soft); border-color: rgba(255,108,55,.22);
        }
        div[class*="st-key-browser-request-row-"] :is([data-testid="column"], [data-testid="stColumn"]):nth-child(1) {
            flex: 0 0 1.3rem !important; width: 1.3rem !important;
        }
        div[class*="st-key-browser-request-row-"] :is([data-testid="column"], [data-testid="stColumn"]):nth-child(2) {
            flex: 0 0 3.8rem !important; width: 3.8rem !important;
        }
        div[class*="st-key-browser-request-row-"] :is([data-testid="column"], [data-testid="stColumn"]):nth-child(3) {
            flex: 1 1 0% !important; width: 0 !important;
        }
        div[class*="st-key-browser-request-row-"] :is([data-testid="column"], [data-testid="stColumn"]):last-child {
            flex: 0 0 2rem !important; width: 2rem !important;
        }
        div[class*="st-key-collection-tree-row-"] [data-testid="stCheckbox"],
        div[class*="st-key-browser-request-row-"] [data-testid="stCheckbox"] {
            display: flex; justify-content: center; margin: 0;
        }
        div[class*="st-key-collection-tree-row-"] [data-testid="stCheckbox"] label,
        div[class*="st-key-browser-request-row-"] [data-testid="stCheckbox"] label {
            padding: 0; gap: 0; justify-content: center;
        }
        div[class*="st-key-browser-request-row-"] [data-testid="stButton"] button {
            box-sizing: border-box; min-height: 2.2rem; width: 100%; justify-content: flex-start !important;
            align-items: center !important; line-height: 1.2;
            padding-inline: .35rem; border-radius: 6px !important; text-align: left;
        }
        div[class*="st-key-browser-request-row-"] [data-testid="stButton"] button > div {
            width: 100%; justify-content: flex-start !important;
        }
        div[class*="st-key-browser-request-row-"] [data-testid="stButton"] button p {
            max-width: 100%; margin: 0; overflow: hidden; text-align: left;
            text-overflow: ellipsis; white-space: nowrap;
        }
        div[class*="st-key-browser-request-row-"] [data-testid="stMarkdown"],
        div[class*="st-key-browser-request-row-"] [data-testid="stMarkdown"] p {
            margin: 0; line-height: 1.2;
        }
        div[class*="st-key-close_contract_import_"] button,
        div[class*="st-key-close_contract_discovery_"] button {
            width: 2rem; min-width: 2rem; height: 2rem; min-height: 2rem;
            padding: 0; border-radius: 7px !important;
        }
        div[class*="st-key-close_contract_import_"] button p,
        div[class*="st-key-close_contract_discovery_"] button p {
            position: absolute !important; width: 1px !important; height: 1px !important;
            margin: -1px !important; padding: 0 !important; overflow: hidden !important;
            clip: rect(0, 0, 0, 0) !important; white-space: nowrap !important; border: 0 !important;
        }
        /* Keep the navigator kebab triggers as plain, unboxed three-dot icons. */
        .st-key-navigator-search-row [data-testid="stPopover"] button,
        div[class*="st-key-collection-tree-row-"] [data-testid="stPopover"] button,
        div[class*="st-key-browser-request-row-"] [data-testid="stPopover"] button {
            display: inline-flex; box-sizing: border-box; width: 1.75rem; min-width: 1.75rem;
            height: 2rem; min-height: 2rem; align-items: center; justify-content: center;
            padding: 0 !important; border: 0 !important; border-radius: 0 !important;
            background: transparent !important; box-shadow: none !important;
            color: inherit; opacity: .68; appearance: none;
            transition: opacity .14s ease, color .14s ease;
        }
        .st-key-navigator-search-row [data-testid="stPopover"] button p,
        div[class*="st-key-collection-tree-row-"] [data-testid="stPopover"] button p,
        div[class*="st-key-browser-request-row-"] [data-testid="stPopover"] button p {
            position: absolute !important; width: 1px !important; height: 1px !important;
            margin: -1px !important; padding: 0 !important; overflow: hidden !important;
            clip: rect(0, 0, 0, 0) !important; white-space: nowrap !important; border: 0 !important;
        }
        .st-key-navigator-search-row [data-testid="stPopover"] button:hover,
        div[class*="st-key-collection-tree-row-"]:hover [data-testid="stPopover"] button,
        div[class*="st-key-browser-request-row-"]:hover [data-testid="stPopover"] button,
        .st-key-navigator-search-row [data-testid="stPopover"] button:focus-visible,
        div[class*="st-key-collection-tree-row-"] [data-testid="stPopover"] button:focus-visible,
        div[class*="st-key-browser-request-row-"] [data-testid="stPopover"] button:focus-visible {
            opacity: 1; color: var(--aa-accent) !important;
            background: transparent !important; border: 0 !important; box-shadow: none !important;
        }
        .st-key-navigator-search-row [data-testid="stPopover"] button:focus-visible,
        div[class*="st-key-collection-tree-row-"] [data-testid="stPopover"] button:focus-visible,
        div[class*="st-key-browser-request-row-"] [data-testid="stPopover"] button:focus-visible {
            outline: 2px solid var(--aa-accent); outline-offset: 1px;
        }
        div[class*="st-key-browser-request-row-"] [data-testid="stPopoverBody"] { min-width: 225px; }

        .st-key-contract-import-panel [data-testid="stDataEditor"] { max-height: 185px; }
        .st-key-contract-candidate-list {
            max-height: 220px; overflow-y: auto; overscroll-behavior: contain;
            padding: .35rem .55rem; border: 1px solid var(--aa-border);
            border-radius: var(--aa-radius-sm); background: var(--aa-surface);
        }
        @media (max-width: 760px) {
            .st-key-collection-browser-scroll { max-height: 46vh; }
            .st-key-api-workspace-layout [data-testid="stHorizontalBlock"]:has(.st-key-collection-browser-header),
            .st-key-api-workspace-layout > [data-testid="stHorizontalBlock"],
            .st-key-api-workspace-layout > [data-testid="stVerticalBlock"] > [data-testid="stHorizontalBlock"] {
                grid-template-columns: minmax(0, 1fr) !important;
            }
            .st-key-request-playground-sticky { position: static; }
        }
        @media (prefers-reduced-motion: reduce) {
            div[class*="st-key-collection-tree-row-"],
            div[class*="st-key-browser-request-row-"] { transition: none; }
        }
        </style>""",
        unsafe_allow_html=True,
    )
    project = st.session_state.get("current_project") or {}
    collections = project.get("collections", [])
    project_id = project.get("id")
    if not project_id:
        st.header("API Workspace")
        st.warning("Select or create a project to manage request collections.")
        return

    with st.container(key="api-workspace-layout"):
        left, editor = st.columns([1, 5], gap="small")
        with left:
            selected_id = _render_collection_navigator(project, project_id)

        with editor:
            active_contract_panel = st.session_state.get("workspace_contract_panel")
            if active_contract_panel == "import":
                st.markdown("<style>.st-key-contract-discovery-expander { display: none !important; }</style>", unsafe_allow_html=True)
            elif active_contract_panel == "discover":
                st.markdown("<style>.st-key-contract-import-expander { display: none !important; }</style>", unsafe_allow_html=True)
            with st.container(key="contract-import-panel"):
                _render_contract_import_panel(project_id, project.get("collections", []))

        with editor, st.container(key="request-playground-sticky"):
            drafts = st.session_state["request_drafts"]
            if not drafts:
                st.info("Start by creating a request, or open one from Saved requests.")
                if st.button("New Request", type="primary", key="new_request_tab_empty"):
                    draft = _new_request_draft()
                    draft["collection_id"] = selected_id
                    st.session_state["request_drafts"].append(draft)
                    st.session_state["active_request_tab_id"] = draft["tab_id"]
                    st.rerun()
            else:
                active_id = st.session_state.get("active_request_tab_id")
                if active_id not in {draft["tab_id"] for draft in drafts}:
                    active_id = drafts[0]["tab_id"]
                    st.session_state["active_request_tab_id"] = active_id

                with st.container(horizontal=True, key="request-tabbar", wrap=False):
                    for index, draft in enumerate(drafts):
                        request_name = draft.get("name") or "New Request"
                        method_label = draft.get("method", "GET").upper()
                        full_label = f"{method_label} {request_name}"
                        tab_label = request_name if len(request_name) <= 22 else f"{request_name[:19]}…"
                        method_color = METHOD_COLORS.get(method_label, "gray")
                        is_active = draft["tab_id"] == active_id
                        with st.container(
                            horizontal=True,
                            key=f"request-tab-{'on' if is_active else 'off'}-{draft['tab_id']}",
                        ):
                            if st.button(
                                f":{method_color}[**{method_label}**]  {tab_label}",
                                key=f"select_request_tab_{draft['tab_id']}",
                                type="tertiary",
                                help=f"Switch to {full_label}",
                                width="stretch",
                            ):
                                st.session_state["active_request_tab_id"] = draft["tab_id"]
                                st.rerun()
                            with st.container(key=f"request-close-{draft['tab_id']}"):
                                if st.button(
                                    "×", key=f"close_request_tab_{draft['tab_id']}",
                                    type="tertiary", help="Close request",
                                ):
                                    st.session_state["request_drafts"] = [
                                        item for item in drafts if item["tab_id"] != draft["tab_id"]
                                    ]
                                    if is_active:
                                        remaining = st.session_state["request_drafts"]
                                        previous_index = max(index - 1, 0)
                                        st.session_state["active_request_tab_id"] = (
                                            remaining[previous_index]["tab_id"] if remaining else None
                                        )
                                    st.rerun()
                    with st.container(key="request-add"):
                        if st.button("+", key="new_request_tab_plus", type="tertiary", help="Add request"):
                            draft = _new_request_draft()
                            draft["collection_id"] = selected_id
                            st.session_state["request_drafts"].append(draft)
                            st.session_state["active_request_tab_id"] = draft["tab_id"]
                            st.rerun()

                active_draft = next(draft for draft in drafts if draft["tab_id"] == active_id)
                st.caption("Request tabs are temporary drafts. Save a request to keep it in a collection.")
                _render_request_draft(active_draft, collections, project_id)

def main() -> None:
    """Main Streamlit application entry point."""
    st.set_page_config(
        page_title="Api-Agent",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    initialize_session_state()
    _flush_toasts()
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
    current_project = st.session_state.get("current_project") or {}
    _hero("Api-Agent", "Compose API requests, generate test cases, and inspect execution results.")
    if current_project:
        st.caption(
            f"Project: **{current_project.get('name', 'Untitled')}** · "
            f"{len(current_project.get('collections', []))} collections · "
            f"{len(current_project.get('endpoints', []))} saved requests · "
            f"{len(current_project.get('test_cases', []))} test cases"
        )

    with st.sidebar:
        _hero("Workspace", "Project and saved test data", mark="AA")
        refresh_project_list()
        project_list = st.session_state.get("project_list", [])
        project_by_id = {project["id"]: project for project in project_list}
        short_ids = [project_id[:8] for project_id in project_by_id]
        project_labels = {
            project_id: f"{project['name']} · {project_id[:8] if short_ids.count(project_id[:8]) == 1 else project_id}"
            for project_id, project in project_by_id.items()
        }
        if st.session_state.get("persisted_project_id") is None:
            try:
                st.session_state["persisted_project_id"] = api_get("/api/v1/memory/state").get("current_project_id")
            except Exception:
                st.session_state["persisted_project_id"] = None
        current_project = st.session_state.get("current_project") or {}
        current_id = current_project.get("id") or st.session_state.get("persisted_project_id")
        if current_id not in project_by_id and project_list:
            current_id = project_list[0]["id"]
        if project_list:
            selected_pid = st.selectbox(
                "Project",
                options=list(project_by_id),
                index=list(project_by_id).index(current_id),
                format_func=lambda project_id: project_labels[project_id],
                key="project_selector_" + "_".join(sorted(project_by_id)),
            )
            if current_project.get("id") != selected_pid:
                load_project(selected_pid)
                st.rerun()
            st.session_state["persisted_project_id"] = selected_pid
        else:
            selected_pid = None
            st.info("No projects available.")

        with st.expander("Project actions", expanded=False):
            with st.form("create_project_form", clear_on_submit=True):
                new_project_name = st.text_input("Project name", placeholder="Enter project name")
                new_project_desc = st.text_input("Description", placeholder="Optional description")
                create_project_clicked = st.form_submit_button("Create project", type="primary")
            if create_project_clicked:
                if new_project_name.strip():
                    project = api_post("/api/v1/projects", {
                        "name": new_project_name.strip(),
                        "description": new_project_desc.strip(),
                    })
                    st.session_state["current_project"] = None
                    refresh_project_list(force=True)
                    load_project(project["id"])
                    _queue_toast("Project created.")
                    st.rerun()
                else:
                    st.error("Project name is required")
            if selected_pid and st.button("Delete selected project", type="secondary"):
                api_delete(f"/api/v1/projects/{selected_pid}")
                st.session_state["current_project"] = None
                st.session_state["endpoints"] = []
                st.session_state["request_drafts"] = []
                st.session_state["test_cases"] = []
                st.session_state["executions"] = {}
                st.session_state["persisted_project_id"] = None
                refresh_project_list(force=True)
                _queue_toast("Project deleted.")
                st.rerun()

        current_project = st.session_state.get("current_project")
        if current_project:
            st.markdown(
                "<div class='aa-stats'>"
                f"<div><span>{len(current_project.get('collections', []))}</span><label>Collections</label></div>"
                f"<div><span>{len(current_project.get('endpoints', []))}</span><label>Requests</label></div>"
                f"<div><span>{len(current_project.get('test_cases', []))}</span><label>Tests</label></div>"
                "</div>",
                unsafe_allow_html=True,
            )

            if st.button("Fetch saved test cases", type="secondary", icon=":material/refresh:", use_container_width=True):
                tcs = api_get(f"/api/v1/projects/{current_project['id']}/test-cases")
                st.session_state["test_cases"] = tcs
                st.session_state["executions"] = {}
                _queue_toast(f"Fetched {len(tcs)} test case(s).")
                st.rerun()

    workspace_tab, test_tab, activity_tab = st.tabs(
        ["API Workspace", "Test Cases", "Generation Activity"],
    )

    with workspace_tab:
        render_api_workspace()

    current_project = st.session_state.get("current_project") or {}
    all_saved_requests = current_project.get("endpoints", [])
    generation_eligible = [
        item for item in all_saved_requests
        if item.get("include_for_generation", item.get("include", False))
    ]
    generation_by_id = {item["id"]: item for item in generation_eligible}
    ordered_ids = [
        item for item in st.session_state.get("generation_order_ids", [])
        if item in generation_by_id
    ]
    ordered_ids.extend(item["id"] for item in generation_eligible if item["id"] not in ordered_ids)
    st.session_state["generation_order_ids"] = ordered_ids
    st.session_state["endpoints"] = [generation_by_id[item] for item in ordered_ids]
    st.session_state["parsed_curl"] = st.session_state["endpoints"][0] if st.session_state["endpoints"] else None

    with test_tab:
        render_test_cases_tab()
    with activity_tab:
        render_generation_activity_tab()
    _flush_toasts()

if __name__ == "__main__":
    main()
