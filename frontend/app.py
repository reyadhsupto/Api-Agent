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
import uuid
import os
import hashlib
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

try:
    from streamlit_sortables import sort_items
except ImportError:
    sort_items = None

BACKEND_URL = os.getenv("API_BACKEND_URL", "http://localhost:8000")


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
    "DELETE": "red", "HEAD": "gray", "OPTIONS": "gray",
}
TEST_CASE_CSS = """
<style>
div[class*="st-key-tc-card-"] {
    border-left: 4px solid rgba(128,128,128,.38) !important;
    border-radius: .65rem !important;
}
div[class*="st-key-tc-card-passed-"] { border-left-color: #2e9e5b !important; }
div[class*="st-key-tc-card-failed-"] { border-left-color: #e5484d !important; }
div[class*="st-key-tc-card-error-"] { border-left-color: #f5a524 !important; }
div[class*="st-key-tc-step-"] { background: rgba(128,128,128,.035); }
div[class*="st-key-tc-card-"] button[kind="tertiary"] {
    padding: 0 .25rem;
    min-height: 1.9rem;
}
</style>
"""


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


def api_post(path: str, payload: dict) -> dict:
    """Send a POST request to the backend and log to browser console."""
    log_to_console(payload, f"REQUEST {path}")
    response = requests.post(f"{BACKEND_URL}{path}", json=payload, timeout=300)
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        try:
            detail = response.json().get("detail")
        except (ValueError, AttributeError):
            detail = None
        raise RuntimeError(detail or str(exc)) from exc
    result = response.json()
    log_to_console(result, f"RESPONSE {path}")
    return result


def api_get(path: str) -> dict:
    """Send a GET request to the backend and log to browser console."""
    log_to_console({}, f"REQUEST {path}")
    response = requests.get(f"{BACKEND_URL}{path}", timeout=300)
    response.raise_for_status()
    result = response.json()
    log_to_console(result, f"RESPONSE {path}")
    return result


def api_delete(path: str) -> dict:
    """Send a DELETE request to the backend and log to browser console."""
    log_to_console({}, f"REQUEST {path}")
    response = requests.delete(f"{BACKEND_URL}{path}", timeout=300)
    response.raise_for_status()
    result = response.json()
    log_to_console(result, f"RESPONSE {path}")
    return result


def api_put(path: str, payload: dict) -> dict:
    """Send a PUT request to the backend and log to browser console."""
    log_to_console(payload, f"REQUEST {path}")
    response = requests.put(f"{BACKEND_URL}{path}", json=payload, timeout=300)
    response.raise_for_status()
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
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def refresh_project_list() -> None:
    """Fetch the list of projects from the backend."""
    try:
        st.session_state["project_list"] = api_get("/api/v1/projects")
    except Exception:
        st.session_state["project_list"] = []


def load_project(project_id: str) -> None:
    """Load a project and its test cases from the backend."""
    try:
        project = api_get(f"/api/v1/projects/{project_id}")
        st.session_state["current_project"] = project
        st.session_state["endpoints"] = project.get("endpoints", [])
        st.session_state["request_drafts"] = []
        st.session_state["generation_order_ids"] = [
            endpoint["id"] for endpoint in project.get("endpoints", [])
            if endpoint.get("include_for_generation", endpoint.get("include", True))
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
                options=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"],
                index=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"].index(
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
    }
    raw = tc.get("assertions", {}) or {}
    for assertion_type, default in defaults.items():
        value = raw.get(assertion_type, default)
        raw[assertion_type] = value if isinstance(value, list) else [value]
        raw[assertion_type] = [item for item in raw[assertion_type] if isinstance(item, dict)]
    tc["assertions"] = raw
    return raw


def _normalise_flow_steps(tc: dict) -> list[dict]:
    """Sort flow steps by their declared order and normalize step assertions."""
    steps = tc.get("steps", [])
    steps.sort(key=lambda step: step.get("step_order", 0))
    for step in steps:
        step["assertions"] = _normalize_assertions(step)
    return steps


def _render_assertion_instance(assertions: dict, assertion_type: str, instance: int, tc_id: str) -> None:
    """Render and persist one assertion instance in Streamlit session state."""
    config = assertions[assertion_type][instance]
    key_prefix = f"tc_assert_{assertion_type}_{tc_id}_{instance}"
    remove_col, enabled_col, value_col = st.columns([0.5, 1.5, 4])
    with remove_col:
        remove = st.button("-", key=f"{key_prefix}_remove", help="Remove this assertion")
    with enabled_col:
        config["enabled"] = st.checkbox(
            "Enabled",
            value=config.get("enabled", assertion_type == "status"),
            key=f"{key_prefix}_enabled",
            label_visibility="collapsed",
        )
    with value_col:
        if assertion_type == "status":
            config["expected_status"] = st.number_input(
                "Expected status",
                min_value=100,
                max_value=599,
                value=int(config.get("expected_status") or 200),
                key=f"{key_prefix}_value",
                disabled=not config["enabled"],
                label_visibility="collapsed",
            )
        elif assertion_type == "body_contains":
            config["value"] = st.text_input(
                "Body text",
                value=config.get("value", "") or "",
                key=f"{key_prefix}_value",
                placeholder="Text in response body",
                disabled=not config["enabled"],
                label_visibility="collapsed",
            )
        else:
            path_col, expected_col = st.columns(2)
            with path_col:
                config["path"] = st.text_input(
                    "JSONPath",
                    value=config.get("path", "") or "",
                    key=f"{key_prefix}_path",
                    placeholder="e.g. $.token",
                    disabled=not config["enabled"],
                    label_visibility="collapsed",
                )
            with expected_col:
                config["expected_value"] = st.text_input(
                    "Expected value",
                    value=config.get("expected_value", "") or "",
                    key=f"{key_prefix}_expected",
                    placeholder="Expected field value",
                    disabled=not config["enabled"],
                    label_visibility="collapsed",
                )
    if remove:
        assertions[assertion_type].pop(instance)
        st.rerun()


def _render_assertion_group(assertions: dict, assertion_type: str, label: str, tc_id: str) -> None:
    """Render all instances of one assertion type and its add button."""
    st.markdown(f"**{label}**")
    for instance in range(len(assertions[assertion_type])):
        _render_assertion_instance(assertions, assertion_type, instance, tc_id)
    if st.button(f"+ Add {label}", key=f"tc_assert_{assertion_type}_{tc_id}_add"):
        defaults = {
            "status": {"enabled": True, "expected_status": 200},
            "body_contains": {"enabled": True, "value": ""},
            "jsonpath": {"enabled": True, "path": "", "expected_value": ""},
        }
        assertions[assertion_type].append(defaults[assertion_type])
        st.rerun()


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


def _render_request_details(method: str | None, url: str | None, headers: dict | None, body, uid: str) -> None:
    """Render request line and its headers/body in compact detail tabs.

    Args:
        method (str | None): HTTP method.
        url (str | None): Request URL.
        headers (dict | None): Request headers.
        body (Any): Request payload.
        uid (str): Stable identifier for this request view.

    Returns:
        None: Writes request details to the Streamlit page.
    """
    st.code(f"{(method or 'GET').upper()} {url or ''}", language="http", wrap_lines=True)
    headers_tab, body_tab = st.tabs(["Headers", "Body"])
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
        f":gray-badge[{latency_ms or 0} ms] :gray-badge[{size_label}]"
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


def _execute_test_case(tc: dict) -> dict:
    """Persist current edits, execute a test or flow, and retain its result.

    Args:
        tc (dict): Test case with current assertion edits.

    Returns:
        dict: Backend execution result.
    """
    tc_id = tc.get("id")
    project = st.session_state.get("current_project") or {}
    if project:
        api_put(f"/api/v1/projects/{project['id']}/test-cases/{tc_id}", tc)
    assertions = {} if tc.get("is_flow") else _normalize_assertions(tc)
    payload = {kind: [dict(config) for config in configs] for kind, configs in assertions.items()}
    result = api_post("/api/v1/test-cases/execute", {
        "test_case_id": tc_id,
        "project_id": project.get("id"),
        "assertions": payload,
    })
    st.session_state.setdefault("executions", {})[tc_id] = result
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
    st.markdown(f"{_status_badge(status)} :gray-badge[{latency} ms]")
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
        )
    with response_col, st.container(border=True):
        st.markdown("**Response**")
        _render_response_details(
            result.get("response_status"), result.get("latency_ms"),
            result.get("response_body"), result.get("response_headers"), f"{uid}_response",
        )


def _render_flow_step(tc_id: str, step: dict, result: dict | None) -> None:
    """Render an expandable flow step with assertion, request, and response views.

    Args:
        tc_id (str): Parent flow test-case identifier.
        step (dict): Flow step configuration.
        result (dict | None): Execution result for this step.

    Returns:
        None: Writes the step card to the Streamlit page.
    """
    order = step.get("step_order", "?")
    uid = f"{tc_id}_step_{order}"
    open_key = f"step_open_{uid}"
    is_open = st.session_state.get(open_key, False)
    endpoint = step.get("endpoint", {}) or {}
    status = _test_case_status(result) if result else "not_run"
    with st.container(border=True, key=f"tc-step-{uid}"):
        toggle_col, title_col, status_col = st.columns([0.45, 6, 2], vertical_alignment="center")
        with toggle_col:
            st.button(
                " ", icon=":material/expand_more:" if is_open else ":material/chevron_right:",
                key=f"toggle_{uid}", type="tertiary", help="Expand or collapse step",
                on_click=_toggle_test_case_state, args=(open_key,),
            )
        with title_col:
            url = endpoint.get("url", "")
            st.markdown(f"**Step {order}** :blue-badge[{endpoint.get('method', 'GET')}] `{url[:76]}`")
        with status_col:
            st.markdown(
                f"{_status_badge(status)} :gray-badge[{(result or {}).get('latency_ms', 0)} ms]"
            )
        if not is_open:
            return
        if step.get("description"):
            st.caption(step["description"])
        assertions_tab, request_tab, response_tab = st.tabs(["Assertions", "Request", "Response"])
        with assertions_tab:
            assertions = step["assertions"]
            for assertion_type, label in (
                ("status", "Status"),
                ("body_contains", "Body contains"),
                ("jsonpath", "JSONPath"),
            ):
                _render_assertion_group(assertions, assertion_type, label, uid)
        with request_tab:
            _render_request_details(
                endpoint.get("method"), endpoint.get("url"), endpoint.get("headers"),
                endpoint.get("body"), f"{uid}_request",
            )
            mappings = step.get("variable_mappings", [])
            if mappings:
                st.markdown("**Variable mappings**")
                st.json(mappings)
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


def render_test_case_card(tc: dict, index: int) -> dict:
    """Render a selectable test card with separated detail views.

    Args:
        tc (dict): Test case configuration and editable assertions.
        index (int): Position in the visible test-case list.

    Returns:
        dict: Updated test case containing any assertion edits.
    """
    tc_id = tc.get("id", f"tc_{index}")
    is_flow = bool(tc.get("is_flow"))
    result = st.session_state.get("executions", {}).get(tc_id)
    status = _test_case_status(result)
    open_key = f"tc_open_{tc_id}"
    is_open = st.session_state.get(open_key, False)
    selected_key = f"tc_selected_{tc_id}"
    st.session_state.setdefault(selected_key, True)

    if not is_flow:
        assertions = _normalize_assertions(tc)
    else:
        assertions = {}
        for step in _normalise_flow_steps(tc):
            step["assertions"] = _normalize_assertions(step)

    with st.container(border=True, key=f"tc-card-{status}-{tc_id}"):
        toggle_col, select_col, title_col, status_col, run_col = st.columns(
            [0.4, 0.4, 5.3, 1.8, 1.1], vertical_alignment="center"
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
            kind = ":violet-badge[FLOW]" if is_flow else f":blue-badge[{str(tc.get('type', 'test')).upper()}]"
            st.markdown(f"**{index + 1}. {tc.get('name', 'Unnamed')}** {kind}")
        with status_col:
            latency = (result or {}).get("latency_ms") or sum(
                item.get("latency_ms", 0) for item in (result or {}).get("step_results", [])
            )
            st.markdown(f"{_status_badge(status)} :gray-badge[{latency} ms]")
        with run_col:
            run_clicked = st.button(
                "Run", icon=":material/play_arrow:", key=f"exec_{tc_id}",
                type="primary", width="stretch",
            )

        if tc.get("description"):
            st.caption(tc["description"])
        if run_clicked:
            with st.spinner("Executing scenario sequentially..." if is_flow else "Executing request..."):
                try:
                    _execute_test_case(tc)
                    st.rerun()
                except Exception as exc:
                    st.error(f"Execution failed: {exc}")

        if is_open:
            if is_flow:
                step_results = {
                    item.get("step_order"): item
                    for item in (result or {}).get("step_results", [])
                }
                steps_tab, summary_tab = st.tabs([f"Steps ({len(tc.get('steps', []))})", "Scenario result"])
                with steps_tab:
                    for step in _normalise_flow_steps(tc):
                        _render_flow_step(tc_id, step, step_results.get(step.get("step_order")))
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
            else:
                request = tc.get("request", {}) or {}
                assertion_tab, request_tab, result_tab = st.tabs(["Assertions", "Request", "Result"])
                with assertion_tab:
                    for assertion_type, label in (
                        ("status", "Status"),
                        ("body_contains", "Body contains"),
                        ("jsonpath", "JSONPath"),
                    ):
                        _render_assertion_group(assertions, assertion_type, label, tc_id)
                with request_tab:
                    _render_request_details(
                        request.get("method"), request.get("url"), request.get("headers"),
                        request.get("body"), f"{tc_id}_request",
                    )
                with result_tab:
                    if result:
                        _render_execution_result(result, tc_id)
                    else:
                        st.caption("Run this test to inspect its response and assertion results.")

            delete_col, save_hint_col = st.columns([1, 5], vertical_alignment="center")
            with delete_col:
                if st.button("Delete", key=f"delete_tc_{tc_id}", icon=":material/delete:", help="Delete test case"):
                    current_project = st.session_state.get("current_project") or {}
                    try:
                        if current_project:
                            api_delete(f"/api/v1/projects/{current_project['id']}/test-cases/{tc_id}")
                        st.session_state["test_cases"] = [item for item in st.session_state["test_cases"] if item.get("id") != tc_id]
                        st.session_state.get("executions", {}).pop(tc_id, None)
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Could not delete test case: {exc}")
            with save_hint_col:
                st.caption("Assertion edits are saved with the scenario when you save test cases or run it.")
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


def _generate_selected_cases(mode: str, selected: list[dict], business_req: str) -> list[dict]:
    """Call the matching generation route for selected requests.

    Args:
        mode (str): Single or Flow generation mode.
        selected (list[dict]): Ordered saved request configurations.
        business_req (str): Optional business requirements text.

    Returns:
        list[dict]: Generated test cases.
    """
    project = st.session_state.get("current_project") or {}
    if mode == "Flow":
        payload = {
            "endpoints": selected,
            "business_requirements": business_req or None,
            "project_id": project.get("id"),
        }
        route = (
            f"/api/v1/projects/{project['id']}/test-cases/generate-flow"
            if project else "/api/v1/test-cases/generate-flow"
        )
        return api_post(route, payload)

    generated = []
    for endpoint in selected:
        payload = {
            "parsed_curl": endpoint,
            "business_requirements": business_req or None,
            "project_id": project.get("id"),
        }
        generated.extend(api_post("/api/v1/test-cases/generate", payload) or [])
    return generated


def render_generation_panel() -> None:
    """Render request selection, optional requirements, and generation controls.

    Returns:
        None: Writes the generation workspace to the Streamlit page.
    """
    endpoints = st.session_state.get("endpoints", [])
    st.subheader("Generate test cases")
    st.session_state.setdefault("test_generation_mode", "Single")
    mode = st.segmented_control(
        "Generation mode", ["Single", "Flow"],
        key="test_generation_mode",
        help="Single creates independent request tests. Flow executes selected requests in order.",
    ) or "Single"

    with st.container(border=True):
        select_col, all_col, clear_col = st.columns([4.5, 1, 1], vertical_alignment="center")
        with select_col:
            st.markdown("**1 · Choose saved requests**")
            st.caption(
                "Selected requests run in the order configured in API Workspace."
                if mode == "Flow" else "Each selected request gets its own set of test cases."
            )
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

        selected = []
        for index, endpoint in enumerate(endpoints, start=1):
            endpoint_id = endpoint.get("id", str(index))
            selected_key = f"generation_selected_{endpoint_id}"
            st.session_state.setdefault(selected_key, True)
            number_col, checkbox_col, method_col, name_col = st.columns(
                [0.5, 0.45, 1, 6], vertical_alignment="center"
            )
            number_col.caption(f"{index:02d}")
            checkbox_col.checkbox(
                "Select request", key=selected_key, label_visibility="collapsed",
                help="Include this request in generation",
            )
            method = str(endpoint.get("method", "GET")).upper()
            method_col.markdown(f":{METHOD_COLORS.get(method, 'gray')}-badge[{method}]")
            name_col.markdown(
                f"**{endpoint.get('name') or 'Untitled request'}** · "
                f"`{(endpoint.get('url') or '')[:78]}`"
            )
            if st.session_state[selected_key]:
                selected.append(endpoint)

        if not endpoints:
            st.info("Enable saved requests in API Workspace to start generation.")

    with st.container(border=True):
        st.markdown("**2 · Add business requirements** · Optional")
        business_req = st.text_area(
            "Business requirements", height=95, key="generation_business_requirements",
            label_visibility="collapsed",
            placeholder="Rules, edge cases, or expected behavior the tests should cover...",
        )

    existing_count = len(st.session_state.get("test_cases", []))
    generate_col, clear_col, hint_col = st.columns([1.8, 1.8, 4], vertical_alignment="center")
    with generate_col:
        generate_clicked = st.button(
            "Generate test cases", icon=":material/auto_awesome:", type="primary",
            width="stretch", disabled=not selected,
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
                    st.rerun()
                except Exception as exc:
                    st.error(f"Could not clear test cases: {exc}")
    with hint_col:
        if not selected:
            st.caption(":orange[Select at least one request to generate tests.]")
        elif mode == "Flow" and len(selected) < 2:
            st.caption(":orange[Flows usually need multiple requests; selected order is preserved.]")
        else:
            st.caption(f"{len(selected)} request(s) selected · {mode.lower()} generation")

    if generate_clicked and selected:
        with st.spinner("Generating with the configured LLM providers..."):
            try:
                result = _generate_selected_cases(mode, selected, business_req)
                if result:
                    st.session_state["test_cases"] = result
                    st.session_state["executions"] = {}
                    for tc in result:
                        st.session_state[f"tc_selected_{tc.get('id')}"] = True
                    st.success(f"Generated {len(result)} test case(s).")
                else:
                    st.warning("The model returned no test cases. Try again or simplify the endpoint requirements.")
            except Exception as exc:
                st.error(f"Failed to generate test cases: {exc}")


def render_test_case_list() -> None:
    """Render status counts, filters, batch execution, and test-case cards.

    Returns:
        None: Writes test-case results to the Streamlit page.
    """
    test_cases = sorted(st.session_state.get("test_cases", []), key=_test_case_sort_key)
    if not test_cases:
        st.info("No test cases yet. Choose requests above and generate a set.")
        return

    executions = st.session_state.get("executions", {})
    statuses = {tc.get("id"): _test_case_status(executions.get(tc.get("id"))) for tc in test_cases}
    counts = {
        "passed": sum(status == "passed" for status in statuses.values()),
        "failed": sum(status == "failed" for status in statuses.values()),
        "error": sum(status == "error" for status in statuses.values()),
        "not_run": sum(status == "not_run" for status in statuses.values()),
    }

    st.divider()
    st.subheader(f"Test cases · {len(test_cases)}")
    st.markdown(
        f":gray-badge[{len(test_cases)} total] :green-badge[{counts['passed']} passed] "
        f":red-badge[{counts['failed']} failed] :orange-badge[{counts['error']} error] "
        f":gray-badge[{counts['not_run']} not run]"
    )

    filter_col, all_col, none_col, expand_col, collapse_col, run_col, save_col = st.columns(
        [2.5, 0.9, 0.8, 1.1, 1.2, 1.35, 1.4], vertical_alignment="center"
    )
    with filter_col:
        st.session_state.setdefault("test_case_filter", "All")
        chosen_filter = st.segmented_control(
            "Result filter", ["All", "Passed", "Failed", "Error", "Not run"],
            key="test_case_filter", label_visibility="collapsed",
        ) or "All"
    with all_col:
        st.button("Select all", key="tc_select_all", width="stretch",
                  on_click=_select_all_test_cases, args=(test_cases, True))
    with none_col:
        st.button("Clear", key="tc_select_none", width="stretch",
                  on_click=_select_all_test_cases, args=(test_cases, False))
    with expand_col:
        st.button("Expand all", key="tc_expand_all", icon=":material/unfold_more:", width="stretch",
                  on_click=_set_all_test_cases_open, args=(test_cases, True))
    with collapse_col:
        st.button("Collapse all", key="tc_collapse_all", icon=":material/unfold_less:", width="stretch",
                  on_click=_set_all_test_cases_open, args=(test_cases, False))
    with run_col:
        run_selected = st.button(
            "Run selected", key="tc_run_selected", icon=":material/play_arrow:",
            type="primary", width="stretch", help="Execute checked test cases",
        )
    with save_col:
        project = st.session_state.get("current_project") or {}
        save_clicked = st.button(
            "Save to project", key="tc_save_project", icon=":material/save:",
            width="stretch", disabled=not project,
        )

    if run_selected:
        targets = [tc for tc in test_cases if st.session_state.get(f"tc_selected_{tc.get('id')}", True)]
        errors = []
        if not targets:
            st.warning("Select at least one test case to run.")
        else:
            progress = st.progress(0.0, text="Preparing execution...")
            for number, tc in enumerate(targets, start=1):
                progress.progress(
                    (number - 1) / len(targets),
                    text=f"Running {tc.get('name', tc.get('id'))} ({number}/{len(targets)})",
                )
                try:
                    _execute_test_case(tc)
                except Exception as exc:
                    errors.append(f"{tc.get('name', tc.get('id'))}: {exc}")
            progress.progress(1.0, text="Execution complete")
            st.session_state["tc_run_errors"] = errors
            st.rerun()

    if save_clicked and project:
        try:
            result = api_post(
                f"/api/v1/projects/{project['id']}/test-cases/save",
                {"test_cases": test_cases},
            )
            st.success(result.get("message", "Test cases saved."))
        except Exception as exc:
            st.error(f"Could not save test cases: {exc}")

    for message in st.session_state.pop("tc_run_errors", []):
        st.error(message)

    filter_status = {
        "All": None, "Passed": "passed", "Failed": "failed",
        "Error": "error", "Not run": "not_run",
    }[chosen_filter]
    shown = 0
    for index, tc in enumerate(test_cases):
        if filter_status and statuses.get(tc.get("id")) != filter_status:
            continue
        shown += 1
        render_test_case_card(tc, index)
    if shown == 0:
        st.caption("No test cases match this result filter.")


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
    st.header("Test Cases")
    if st.session_state.get("endpoints"):
        render_generation_panel()
    else:
        st.warning("Save a request in API Workspace and enable it for generation first.")
    render_test_case_list()


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


def _new_request_draft(saved: dict | None = None) -> dict:
    """Create independent editor state, optionally initialized from a saved request."""
    saved = dict(saved or {})
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
        "response": None,
    }


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
    """Refresh persisted project state without discarding open request tabs."""
    project = api_get(f"/api/v1/projects/{project_id}")
    st.session_state["current_project"] = project
    st.session_state["endpoints"] = project.get("endpoints", [])


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


def _render_request_draft(draft: dict, collections: list[dict], project_id: str) -> None:
    """Render one request editor tab, send/save actions, and its response panel."""
    tab_id = draft["tab_id"]
    method_options = ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]

    # Apply imported values before creating keyed widgets on this rerun.
    parsed = st.session_state.pop(f"pending_curl_{tab_id}", None)
    if parsed:
        draft["method"] = parsed.get("method", "GET")
        draft["url"] = parsed.get("url", "")
        draft["headers"] = _request_rows(parsed.get("headers", {}))
        draft["query_params"] = _request_rows(parsed.get("query_params", {}))
        draft["body"] = parsed.get("body") or ""
        draft["include_body"] = True
        draft["response"] = None
        st.session_state[f"method_{tab_id}"] = draft["method"] if draft["method"] in method_options else "GET"
        st.session_state[f"url_{tab_id}"] = draft["url"]
        st.session_state[f"body_{tab_id}"] = draft["body"]
        st.session_state[f"body_mode_{tab_id}"] = "raw"
        st.session_state.pop(f"header_editor_{tab_id}", None)
        st.session_state.pop(f"query_editor_{tab_id}", None)

    # Seed keyed widget values before construction. Keyed widgets read these
    # values directly, so passing a second default value would conflict.
    st.session_state.setdefault(f"method_{tab_id}", draft.get("method", "GET"))
    st.session_state.setdefault(f"url_{tab_id}", draft.get("url", ""))
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

    method_col, request_url_col, curl_col, send_col = st.columns([1.15, 5.2, 1.1, 1.2], vertical_alignment="bottom")
    with method_col:
        if draft["method"] not in method_options:
            draft["method"] = "GET"
        st.session_state.setdefault(f"method_{tab_id}", draft["method"])
        draft["method"] = st.selectbox("Method", method_options, key=f"method_{tab_id}")
    with request_url_col:
        draft["url"] = st.text_input("URL", key=f"url_{tab_id}", placeholder="https://api.example.com/resource")
    with curl_col:
        with st.popover("cURL", icon=":material/code:", help="Import a cURL command", use_container_width=True):
            curl = st.text_area("Paste cURL", height=120, key=f"curl_{tab_id}", placeholder="curl -X POST 'https://api.example.com/items' -H 'Content-Type: application/json' -d '{\"name\":\"item\"}'")
            if st.button("Apply to request", key=f"parse_curl_{tab_id}", type="primary", use_container_width=True):
                try:
                    parsed = api_post("/api/v1/curl/parse", {"curl": curl})
                    st.session_state[f"pending_curl_{tab_id}"] = parsed
                    st.rerun()
                except Exception as exc:
                    st.error(f"Could not apply cURL: {exc}")
    with send_col:
        send_clicked = st.button("Send", type="primary", key=f"send_{tab_id}", use_container_width=True, icon=":material/send:")

    params_tab, headers_tab, payload_tab = st.tabs(["Params", "Headers", "Body"])
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

    if save_clicked and selected_collection:
        try:
            _save_request_draft(draft, selected_collection, project_id)
            _refresh_project_preserving_drafts(project_id)
            st.success("Request saved to collection.")
            st.rerun()
        except Exception as exc:
            st.error(f"Could not save request: {exc}")
    if send_clicked:
        try:
            if not draft["url"].startswith(("http://", "https://")):
                raise ValueError("Enter an absolute http:// or https:// URL.")
            url, query_rows = _normalise_request_url(draft["url"], draft["query_params"])
            headers = _effective_rows(draft["headers"])
            query_params = _effective_rows(query_rows)
            body: str | dict | list | None = draft["body"] if draft["include_body"] and draft["body"] else None
            content_type = next((value for key, value in headers.items() if key.lower() == "content-type"), "")
            if isinstance(body, str) and body.strip() and content_type.lower().split(";")[0] == "application/json":
                body = json.loads(body)
            draft["response"] = api_post("/api/v1/http/send", {
                "method": draft["method"], "url": url, "headers": headers,
                "query_params": query_params, "body": body,
            })
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
        div[data-baseweb="tab-list"] { gap: 0.35rem; }
        div[data-baseweb="tab"] { padding: 0.45rem 0.9rem; font-size: 0.92rem; }
        div[data-testid="stSelectbox"] div[data-baseweb="select"] > div { font-weight: 650; }
        div[data-testid="stDataEditor"] { border-radius: 0.5rem; }
        </style>""",
        unsafe_allow_html=True,
    )
    st.header("API Workspace")
    st.caption("Build requests, run quick checks, and save reusable requests in project collections.")
    project = st.session_state.get("current_project") or {}
    project_id = project.get("id")
    if not project_id:
        st.warning("Select or create a project to manage request collections.")
        return

    left, editor = st.columns([1.15, 3.7], gap="large")
    with left:
        st.subheader("Collections")
        with st.form("create_request_collection", clear_on_submit=True):
            collection_name = st.text_input("New collection name", placeholder="e.g. Authentication")
            create_collection_clicked = st.form_submit_button("Create collection", type="primary")
        if create_collection_clicked:
            if not collection_name.strip():
                st.error("Enter a collection name.")
            else:
                try:
                    created = api_post(f"/api/v1/projects/{project_id}/collections", {"name": collection_name.strip()})
                    _refresh_project_preserving_drafts(project_id)
                    st.session_state["selected_collection_id"] = created["id"]
                    st.rerun()
                except Exception as exc:
                    st.error(f"Could not create collection: {exc}")

        collections = project.get("collections", [])
        collection_by_id = {item["id"]: item for item in collections}
        if collections:
            selected_id = st.selectbox(
                "Collection", list(collection_by_id),
                index=list(collection_by_id).index(st.session_state["selected_collection_id"])
                if st.session_state.get("selected_collection_id") in collection_by_id else 0,
                format_func=lambda collection_id: collection_by_id[collection_id]["name"],
                key=f"workspace_collection_select_{project_id}",
            )
            st.session_state["selected_collection_id"] = selected_id
            selected_collection = collection_by_id[selected_id]
            with st.expander("Collection actions", expanded=False):
                rename_value = st.text_input("Rename collection", value=selected_collection["name"], key=f"rename_collection_{selected_id}")
                rename_col, delete_col = st.columns(2)
                with rename_col:
                    if st.button("Rename", key=f"rename_collection_button_{selected_id}"):
                        try:
                            api_put(f"/api/v1/projects/{project_id}/collections/{selected_id}", {"name": rename_value})
                            _refresh_project_preserving_drafts(project_id)
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Could not rename collection: {exc}")
                with delete_col:
                    if st.button("Delete", key=f"delete_collection_{selected_id}"):
                        api_delete(f"/api/v1/projects/{project_id}/collections/{selected_id}")
                        _refresh_project_preserving_drafts(project_id)
                        st.session_state["selected_collection_id"] = None
                        st.rerun()
            export_payload = api_get(f"/api/v1/projects/{project_id}/collections/{selected_id}/export")
            st.download_button(
                "Export Postman collection",
                data=json.dumps(export_payload, ensure_ascii=False, indent=2),
                file_name=f"{selected_collection['name']}.postman_collection.json",
                mime="application/json",
                key=f"export_collection_{selected_id}",
                use_container_width=True,
            )
        else:
            selected_id = None
            st.info("Create a collection to save requests.")

        st.divider()
        st.subheader("Requests for generation")
        st.caption("Select saved requests eligible for test generation. This setting does not change which rows are sent in a quick request.")
        requests_by_id = {item["id"]: item for item in project.get("endpoints", [])}
        selected_generation = [
            request_id for request_id in st.session_state.get("generation_order_ids", [])
            if request_id in requests_by_id and requests_by_id[request_id].get("include_for_generation", requests_by_id[request_id].get("include", False))
        ]
        for saved in project.get("endpoints", []):
            request_id = saved["id"]
            eligible = bool(saved.get("include_for_generation", saved.get("include", False)))
            label = f"{saved.get('method', 'GET')} · {saved.get('name') or 'Untitled Request'}"
            selected = st.checkbox(
                f"{label}",
                value=eligible,
                key=f"eligible_{request_id}",
            )
            if selected != eligible:
                api_put(
                    f"/api/v1/projects/{project_id}/collections/{saved['collection_id']}/requests/{request_id}",
                    {"include_for_generation": selected, "include": selected},
                )
                order = st.session_state.get("generation_order_ids", [])
                if selected and request_id not in order:
                    order.append(request_id)
                if not selected:
                    order = [item for item in order if item != request_id]
                st.session_state["generation_order_ids"] = order
                _refresh_project_preserving_drafts(project_id)
                st.rerun()

        selected_generation = [
            request_id for request_id in st.session_state.get("generation_order_ids", [])
            if request_id in requests_by_id
            and requests_by_id[request_id].get("include_for_generation", requests_by_id[request_id].get("include", False))
        ]
        if selected_generation and sort_items:
            st.caption("Drag requests to set their flow order.")
            labels_by_id = {}
            ids_by_label = {}
            for request_id in selected_generation:
                saved = requests_by_id[request_id]
                base_label = f"{saved.get('method', 'GET').upper()} · {saved.get('name') or 'Untitled Request'}"
                label = base_label
                prefix_length = 4
                while label in ids_by_label:
                    label = f"{base_label} · {request_id[:prefix_length]}"
                    prefix_length += 2
                labels_by_id[request_id] = label
                ids_by_label[label] = request_id

            drag_style = """
            .sortable-component { background: transparent; border: 0; padding: 0; }
            .sortable-container { background: transparent; }
            .sortable-item {
                background: rgba(128,128,128,.10);
                color: inherit;
                border: 1px solid rgba(128,128,128,.25);
                border-radius: 8px;
                margin: 4px 0;
                cursor: grab;
            }
            .sortable-item:hover { border-color: #ff6c37; }
            """
            selection_hash = hashlib.sha1(
                ",".join(sorted(selected_generation)).encode("utf-8")
            ).hexdigest()[:10]
            sorted_labels = sort_items(
                [labels_by_id[request_id] for request_id in selected_generation],
                direction="vertical",
                custom_style=drag_style,
                key=f"generation-order-{project_id}-{selection_hash}",
            )
            if sorted_labels and set(sorted_labels) == set(ids_by_label):
                sorted_ids = [ids_by_label[label] for label in sorted_labels]
                if sorted_ids != selected_generation:
                    st.session_state["generation_order_ids"] = sorted_ids
        elif selected_generation:
            st.warning("Drag-and-drop ordering is unavailable. Install frontend requirements to enable it.")

        if not project.get("endpoints"):
            st.caption("Save requests to a collection, then choose which ones test generation can use.")

        st.divider()
        st.subheader("Saved requests")
        for collection in collections:
            with st.expander(f"{collection['name']} · {len(collection.get('requests', []))}", expanded=collection["id"] == selected_id):
                for saved in collection.get("requests", []):
                    cols = st.columns([3, 1, 1])
                    with cols[0]:
                        st.caption(f"{saved.get('method', 'GET')}  {saved.get('name') or 'Untitled'}")
                    with cols[1]:
                        if st.button(
                            " ", icon=":material/open_in_new:", help="Open in request playground",
                            key=f"open_saved_{saved['id']}",
                        ):
                            existing = next((draft for draft in st.session_state["request_drafts"] if draft.get("id") == saved["id"]), None)
                            if not existing:
                                existing = _new_request_draft(saved)
                                st.session_state["request_drafts"].append(existing)
                            st.session_state["active_request_tab_id"] = existing["tab_id"]
                            st.rerun()
                    with cols[2]:
                        if st.button(
                            " ", icon=":material/delete:", help="Delete saved request",
                            key=f"delete_saved_{saved['id']}",
                        ):
                            api_delete(f"/api/v1/projects/{project_id}/collections/{collection['id']}/requests/{saved['id']}")
                            st.session_state["generation_order_ids"] = [item for item in st.session_state["generation_order_ids"] if item != saved["id"]]
                            _refresh_project_preserving_drafts(project_id)
                            st.rerun()

    with editor:
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
    st.title("Api-Agent - API Test Case Generator & Executor")

    # Compact project controls remain available behind Streamlit's sidebar toggle.
    with st.sidebar:
        st.header("Workspace")
        refresh_project_list()
        project_list = st.session_state.get("project_list", [])
        project_by_id = {project["id"]: project for project in project_list}
        try:
            persisted_id = api_get("/api/v1/memory/state").get("current_project_id")
        except Exception:
            persisted_id = None
        current_project = st.session_state.get("current_project") or {}
        current_id = current_project.get("id") or persisted_id
        if current_id not in project_by_id and project_list:
            current_id = project_list[0]["id"]
        if project_list:
            selected_pid = st.selectbox(
                "Project",
                options=list(project_by_id),
                index=list(project_by_id).index(current_id),
                format_func=lambda project_id: (
                    f"{project_by_id[project_id]['name']} · {project_id[:8]}"
                ),
                key="project_selector_" + "_".join(sorted(project_by_id)),
            )
            if current_project.get("id") != selected_pid:
                load_project(selected_pid)
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
                    refresh_project_list()
                    load_project(project["id"])
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
                refresh_project_list()
                st.rerun()

        current_project = st.session_state.get("current_project")
        if current_project:
            st.divider()
            st.caption(f"Collections: {len(current_project.get('collections', []))}")
            st.caption(f"Saved requests: {len(current_project.get('endpoints', []))}")
            st.caption(f"Test Cases: {len(current_project.get('test_cases', []))}")

            if st.button("Fetch Last Test Cases", type="secondary"):
                tcs = api_get(f"/api/v1/projects/{current_project['id']}/test-cases")
                st.session_state["test_cases"] = tcs
                st.session_state["executions"] = {}
                st.success(f"Fetched {len(tcs)} test case(s)")
                st.rerun()

    workspace_tab, test_tab = st.tabs(["API Workspace", "Test Cases"])

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

if __name__ == "__main__":
    main()
