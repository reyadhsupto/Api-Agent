"""
Streamlit frontend for Api-Agent.

Tabs:
1. Endpoints - Parse and edit cURL requests (supports multiple endpoints with include/exclude).
2. Test Cases - Generate (single or flow) and execute test cases with per-case assertion editing.

Features: Project management, multi-endpoint collections, flow test cases,
per-test-case assertions with checkboxes, collapsible cards, console logging,
reorderable endpoints, named endpoints.
"""

import streamlit as st
import requests
import json
import uuid
from urllib.parse import urlencode

BACKEND_URL = "http://localhost:8000"


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
        st.session_state["test_cases"] = project.get("test_cases", [])
        st.session_state["executions"] = {}
        for execution in project.get("executions", []):
            test_case_id = execution.get("test_case_id")
            if test_case_id:
                st.session_state["executions"][test_case_id] = execution
        st.session_state["parsed_curl"] = next(
            (ep for ep in st.session_state["endpoints"] if ep.get("include", True)),
            None,
        )
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


def render_test_case_card(tc: dict, index: int) -> dict:
    """Render a single test case as a collapsible card with repeatable assertions."""
    tc_id = tc.get("id", f"tc_{index}")
    tc_type = tc.get("type", "unknown").upper()
    tc_name = tc.get("name", "Unnamed")
    is_flow = tc.get("is_flow", False)

    assertions = _normalize_assertions(tc) if not is_flow else {}

    # Collapsible test case card
    flow_badge = " [FLOW]" if is_flow else ""
    expander_title = f"{index + 1}. [{tc_type}] {tc_name}{flow_badge}"
    with st.expander(expander_title, expanded=False):
        # Description
        st.caption(tc.get("description", ""))

        if is_flow:
            # Flow assertions belong to each step; top-level flow assertions are not executable.
            steps = _normalise_flow_steps(tc)
            st.markdown(f"**Flow steps ({len(steps)})**")
            execution = st.session_state.get("executions", {}).get(tc_id, {})
            step_results = {
                item.get("step_order"): item
                for item in execution.get("step_results", [])
            }
            for step in steps:
                step_order = step.get("step_order", "?")
                endpoint = step.get("endpoint", {}) or {}
                method = endpoint.get("method", "GET")
                url = endpoint.get("url", "")
                with st.container(border=True):
                    st.markdown(f"**Step {step_order}: {method} {url}")
                    if step.get("description"):
                        st.caption(step["description"])
                    step_assertions = step["assertions"]
                    for assertion_type, label in (
                        ("status", "Status assertions"),
                        ("body_contains", "Body contains assertions"),
                        ("jsonpath", "JSONPath assertions"),
                    ):
                        _render_assertion_group(
                            step_assertions,
                            assertion_type,
                            label,
                            f"{tc_id}_step_{step_order}",
                        )
                    st.caption("Request and variable mappings")
                    st.json({
                        "endpoint": endpoint,
                        "variable_mappings": step.get("variable_mappings", []),
                    })
                    step_result = step_results.get(step_order)
                    if step_result:
                        result_color = "green" if step_result.get("status") == "passed" else "red"
                        st.markdown(
                            f"Step result: <span style='color:{result_color};font-weight:bold'>"
                            f"{step_result.get('status', 'unknown').upper()}</span> "
                            f"| {step_result.get('latency_ms', 0)} ms",
                            unsafe_allow_html=True,
                        )
                        st.caption(step_result.get("assertion_detail", ""))
                        st.json({
                            "response_status": step_result.get("response_status"),
                            "response_headers": step_result.get("response_headers", {}),
                            "response_body": step_result.get("response_body", ""),
                        })
        else:
            # Assertion editor. All enabled instances use AND semantics during execution.
            st.markdown("**Assertions**")
            _render_assertion_group(assertions, "status", "Status assertions", tc_id)
            _render_assertion_group(assertions, "body_contains", "Body contains assertions", tc_id)
            _render_assertion_group(assertions, "jsonpath", "JSONPath assertions", tc_id)

        # Delete test case button
        if st.button("Delete Test Case", key=f"delete_tc_{tc_id}", type="secondary"):
            current_project = st.session_state.get("current_project") or {}
            if current_project:
                try:
                    api_delete(
                        f"/api/v1/projects/{current_project['id']}/test-cases/{tc_id}"
                    )
                except Exception as exc:
                    st.error(f"Could not delete saved test case: {exc}")
                    return tc
            st.session_state["test_cases"] = [
                t for t in st.session_state["test_cases"] if t.get("id") != tc_id
            ]
            if tc_id in st.session_state.get("executions", {}):
                del st.session_state["executions"][tc_id]
            st.rerun()

        # Execute button
        execute_btn = st.button("Execute Test Case", key=f"exec_{tc_id}", type="primary", use_container_width=True)

        if not is_flow:
            st.markdown("**Test Case Request Details**")
            st.json(tc.get("request", {}))

        # Execute button handler
        if execute_btn:
            with st.spinner("Executing..."):
                try:
                    current_project = st.session_state.get("current_project") or {}
                    if current_project:
                        api_put(
                            f"/api/v1/projects/{current_project['id']}/test-cases/{tc_id}",
                            tc,
                        )
                    assertions_payload = {
                        assertion_type: [config.copy() for config in configs]
                        for assertion_type, configs in assertions.items()
                    }

                    result = api_post(
                        "/api/v1/test-cases/execute",
                        {
                            "test_case_id": tc_id,
                            "project_id": current_project.get("id"),
                            "assertions": assertions_payload,
                        },
                    )
                    if "executions" not in st.session_state:
                        st.session_state["executions"] = {}
                    st.session_state["executions"][tc_id] = result
                    st.rerun()
                except Exception as exc:
                    st.error(f"Execution failed: {exc}")

        # Show execution result if available
        executions = st.session_state.get("executions", {})
        if tc_id in executions:
            result = executions[tc_id]
            status = result.get("status", "unknown")
            status_color = "green" if status == "passed" else "red"
            latency = result.get("latency_ms", 0)
            if is_flow and not latency:
                latency = sum(
                    step.get("latency_ms", 0)
                    for step in result.get("step_results", [])
                )

            st.markdown(
                f"**Execution Result:** "
                f"<span style='color:{status_color}; font-weight:bold'>{status.upper()}</span>  "
                f"| Latency: {latency} ms",
                unsafe_allow_html=True,
            )
            st.caption(result.get("assertion_detail", ""))

            if not is_flow:
                display_request_response(
                    f"Request/Response Details for {tc_name}",
                    {
                        "method": result.get("request_method", ""),
                        "url": result.get("request_url", ""),
                        "headers": result.get("request_headers", {}),
                        "body": result.get("request_body", ""),
                    },
                    {
                        "status": result.get("response_status"),
                        "body": result.get("response_body", ""),
                    },
                )

    return tc


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
                st.session_state["test_cases"] = []
                st.session_state["executions"] = {}
                refresh_project_list()
                st.rerun()

        current_project = st.session_state.get("current_project")
        if current_project:
            st.divider()
            st.caption(f"Endpoints: {len(current_project.get('endpoints', []))}")
            st.caption(f"Test Cases: {len(current_project.get('test_cases', []))}")

            if st.button("Save Endpoints to Project", type="secondary"):
                st.session_state["_save_endpoints_requested"] = True

            if st.button("Fetch Last Test Cases", type="secondary"):
                tcs = api_get(f"/api/v1/projects/{current_project['id']}/test-cases")
                st.session_state["test_cases"] = tcs
                st.session_state["executions"] = {}
                st.success(f"Fetched {len(tcs)} test case(s)")
                st.rerun()

    tab1, tab2 = st.tabs(["1. Endpoints", "2. Test Cases"])

    # Tab 1: Endpoints
    with tab1:
        st.header("Endpoints")
        st.caption("Parse cURL commands and edit request components. Supports multiple endpoints with include/exclude, reordering, and naming.")

        # Add new endpoint from cURL
        st.subheader("Add Endpoint from cURL")
        curl_input = st.text_area(
            "Paste cURL command",
            height=120,
            key="new_curl_input",
            placeholder="curl -X POST https://api.example.com/users -H 'Content-Type: application/json' -d '{\"name\":\"test\"}'",
        )
        col_add, col_clear = st.columns([1, 1])
        with col_add:
            if st.button("Parse and Add Endpoint", type="primary"):
                if not curl_input.strip():
                    st.error("Please enter a cURL command.")
                else:
                    with st.spinner("Parsing cURL..."):
                        try:
                            result = api_post("/api/v1/curl/parse", {"curl": curl_input})
                            endpoint = {
                                "id": str(uuid.uuid4()),
                                "name": "",
                                "include": True,
                                "method": result.get("method", "GET"),
                                "url": result.get("url", ""),
                                "headers": result.get("headers", {}),
                                "query_params": {},
                                "path_params": {},
                                "body": result.get("body"),
                            }
                            st.session_state["endpoints"].append(endpoint)
                            st.success("Endpoint added from cURL.")
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Failed to parse cURL: {exc}")
        with col_clear:
            if st.button("Clear All Endpoints"):
                st.session_state["endpoints"] = []
                st.session_state["test_cases"] = []
                st.session_state["executions"] = {}
                st.session_state["parsed_curl"] = None
                current_project = st.session_state.get("current_project") or {}
                if current_project:
                    api_put(
                        f"/api/v1/projects/{current_project['id']}/endpoints",
                        {"endpoints": []},
                    )
                    api_delete(f"/api/v1/projects/{current_project['id']}/test-cases")
                st.rerun()

        # Display and edit existing endpoints
        if st.session_state["endpoints"]:
            st.divider()
            st.subheader("Configured Endpoints")

            included_count = sum(1 for ep in st.session_state["endpoints"] if ep.get("include", True))
            total_count = len(st.session_state["endpoints"])
            st.info(f"{included_count} of {total_count} endpoint(s) included for test generation")

            updated_endpoints = []
            for i, ep in enumerate(st.session_state["endpoints"]):
                edited = render_endpoint_card(ep, i)
                updated_endpoints.append(edited)

            st.session_state["endpoints"] = updated_endpoints

            if st.session_state.pop("_save_endpoints_requested", False):
                current_project = st.session_state.get("current_project") or {}
                if current_project:
                    result = api_put(
                        f"/api/v1/projects/{current_project['id']}/endpoints",
                        {"endpoints": updated_endpoints},
                    )
                    st.success(result.get("message", "Endpoints saved"))
                    load_project(current_project["id"])
                    st.rerun()

            # Select endpoint for test case generation
            included_endpoints = [ep for ep in st.session_state["endpoints"] if ep.get("include", True)]

            if included_endpoints:
                st.subheader("Select Endpoint for Test Cases")
                endpoint_options = {
                    f"#{i+1} - {ep.get('name', '')} ({ep.get('method', 'GET')}) {ep.get('url', '')[:60]}": ep.get("id")
                    for i, ep in enumerate(included_endpoints)
                }
                selected_label = st.selectbox(
                    "Select endpoint",
                    options=list(endpoint_options.keys()),
                    key="selected_endpoint",
                )
                selected_id = endpoint_options[selected_label]
                selected_endpoint = next(
                    (ep for ep in included_endpoints if ep.get("id") == selected_id),
                    None,
                )

                if selected_endpoint:
                    st.session_state["parsed_curl"] = selected_endpoint
                    with st.expander("Selected Endpoint Preview", expanded=False):
                        st.json(selected_endpoint)
            else:
                st.warning("No endpoints are included. Check the 'Include' checkbox on at least one endpoint.")

    # Tab 2: Test Cases (generate + execute merged)
    with tab2:
        st.header("Test Cases")

        if "parsed_curl" not in st.session_state or not st.session_state["parsed_curl"]:
            st.warning("Please add and select an endpoint in tab 1 first.")
        else:
            selected_endpoint = st.session_state["parsed_curl"]
            st.caption(
                f"Using endpoint: {selected_endpoint.get('name', '')} "
                f"({selected_endpoint.get('method', 'GET')} {selected_endpoint.get('url', '')})"
            )

            # Generation mode selection
            gen_mode = st.radio(
                "Generation Mode",
                options=["Single Endpoint", "Flow (Multiple Endpoints in Sequence)"],
                horizontal=True,
            )

            business_req = st.text_area("Business Requirements (optional)", height=100)

            # Endpoint selection for generation (both modes support multiple)
            included_endpoints = [ep for ep in st.session_state["endpoints"] if ep.get("include", True)]

            single_endpoints = []
            if gen_mode == "Single Endpoint":
                if included_endpoints:
                    st.subheader("Select Endpoints to Generate Test Cases For")
                    for i, ep in enumerate(included_endpoints):
                        if st.checkbox(
                            f"#{i+1} - {ep.get('name', ep.get('method', 'GET'))} {ep.get('url', '')[:50]}",
                            key=f"single_ep_{ep.get('id')}",
                            value=True,
                        ):
                            single_endpoints.append(ep)
                else:
                    st.warning("No included endpoints. Check the 'Include' checkbox on at least one endpoint.")

            # Flow endpoint selection (if flow mode)
            flow_endpoints = []
            if gen_mode == "Flow (Multiple Endpoints in Sequence)":
                if included_endpoints:
                    st.subheader("Select Endpoints for Flow (in order)")
                    for i, ep in enumerate(included_endpoints):
                        if st.checkbox(
                            f"#{i+1} - {ep.get('name', ep.get('method', 'GET'))} {ep.get('url', '')[:50]}",
                            key=f"flow_ep_{ep.get('id')}",
                            value=True,
                        ):
                            flow_endpoints.append(ep)
                else:
                    st.warning("No included endpoints for flow.")

            col_gen, col_clear = st.columns([1, 1])
            with col_gen:
                if st.button("Generate Test Cases", type="primary"):
                    with st.spinner("Generating test cases with AI..."):
                        try:
                            if gen_mode == "Flow (Multiple Endpoints in Sequence)" and flow_endpoints:
                                current_project = st.session_state.get("current_project")
                                if current_project:
                                    result = api_post(
                                        f"/api/v1/projects/{current_project['id']}/test-cases/generate-flow",
                                        {
                                            "endpoints": flow_endpoints,
                                            "business_requirements": business_req or None,
                                            "project_id": (st.session_state.get("current_project") or {}).get("id"),
                                        },
                                    )
                                else:
                                    # No project - generate flow without project
                                    result = api_post(
                                        "/api/v1/test-cases/generate-flow",
                                        {
                                            "endpoints": flow_endpoints,
                                            "business_requirements": business_req or None,
                                        },
                                    )
                            elif gen_mode == "Single Endpoint" and single_endpoints:
                                # Generate test cases for each selected endpoint
                                all_results = []
                                for ep in single_endpoints:
                                    payload = {
                                        "parsed_curl": ep,
                                        "business_requirements": business_req or None,
                                        "project_id": (st.session_state.get("current_project") or {}).get("id"),
                                    }
                                    ep_result = api_post("/api/v1/test-cases/generate", payload)
                                    if ep_result:
                                        all_results.extend(ep_result)
                                result = all_results if all_results else None

                            if result:
                                st.session_state["test_cases"] = result
                                st.session_state["executions"] = {}
                                st.success(f"Generated {len(result)} test case(s).")
                        except Exception as exc:
                            st.error(f"Failed to generate test cases: {exc}")

            with col_clear:
                if st.button("Clear Test Cases"):
                    current_project = st.session_state.get("current_project") or {}
                    if current_project:
                        api_delete(f"/api/v1/projects/{current_project['id']}/test-cases")
                    st.session_state["test_cases"] = []
                    st.session_state["executions"] = {}
                    st.rerun()

            test_cases = st.session_state.get("test_cases", [])

            if test_cases:
                st.subheader(f"Test Cases ({len(test_cases)})")

                # Sort test cases by their id number
                def sort_key(tc):
                    tc_id = tc.get("id", "tc_0")
                    try:
                        num = int(tc_id.split("_")[-1]) if "_" in tc_id else int(tc_id.replace("tc", ""))
                    except (ValueError, AttributeError):
                        num = 0
                    return num

                sorted_test_cases = sorted(test_cases, key=sort_key)

                # Render each test case as a collapsible card
                updated_test_cases = []
                for i, tc in enumerate(sorted_test_cases):
                    edited_tc = render_test_case_card(tc, i)
                    updated_test_cases.append(edited_tc)

                st.session_state["test_cases"] = updated_test_cases

                # Save test cases to project
                current_project = st.session_state.get("current_project")
                if current_project:
                    if st.button("Save Test Cases to Project", type="secondary"):
                        try:
                            result = api_post(
                                f"/api/v1/projects/{current_project['id']}/test-cases/save",
                                {"test_cases": st.session_state["test_cases"]},
                            )
                            st.success(result.get("message", "Saved"))
                            load_project(current_project["id"])
                        except Exception as exc:
                            st.error(f"Failed to save: {exc}")


if __name__ == "__main__":
    main()
