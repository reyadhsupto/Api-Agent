"""
Streamlit frontend for Api-Agent.

Tabs:
1. Endpoints - Parse and edit cURL requests (supports multiple endpoints with include/exclude).
2. Test Cases - Generate AI test cases and execute them with per-case assertion editing.

Calls FastAPI backend via python requests (server-side).
API calls and responses are logged to the browser devtools console via st.iframe.
"""

import streamlit as st
import requests
import json
import uuid
from urllib.parse import urlencode

BACKEND_URL = "http://localhost:8000"


def log_to_console(data: dict, label: str = "API") -> None:
    """
    Inject a JavaScript console.log statement via st.iframe so the data
    appears in the browser devtools console.

    Args:
        data (dict): Data to log to the console.
        label (str): Label prefix for the console message.
    """
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
    """
    Send a POST request to the backend and log to browser console.

    Args:
        path (str): API endpoint path.
        payload (dict): Request body.

    Returns:
        dict: JSON response from backend.
    """
    log_to_console(payload, f"REQUEST {path}")
    response = requests.post(f"{BACKEND_URL}{path}", json=payload, timeout=300)
    response.raise_for_status()
    result = response.json()
    log_to_console(result, f"RESPONSE {path}")
    return result


def api_get(path: str) -> dict:
    """
    Send a GET request to the backend and log to browser console.

    Args:
        path (str): API endpoint path.

    Returns:
        dict: JSON response from backend.
    """
    log_to_console({}, f"REQUEST {path}")
    response = requests.get(f"{BACKEND_URL}{path}", timeout=300)
    response.raise_for_status()
    result = response.json()
    log_to_console(result, f"RESPONSE {path}")
    return result


def display_request_response(label: str, request_info: dict, response_info: dict) -> None:
    """
    Display verbose request and response details in an expander.

    Args:
        label (str): Label for the expander header.
        request_info (dict): Request details (url, method, headers, body).
        response_info (dict): Response details (status, body).
    """
    with st.expander(label, expanded=False):
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
    """
    Initialize Streamlit session state keys if they do not exist.
    """
    defaults = {
        "endpoints": [],
        "test_cases": [],
        "executions": {},
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def render_endpoint_editor(endpoint: dict, index: int) -> dict:
    """
    Render an editable form for a single endpoint request.

    Args:
        endpoint (dict): Endpoint dictionary with method, url, headers, params, body.
        index (int): Position of this endpoint in the list (for unique widget keys).

    Returns:
        dict: The (possibly modified) endpoint dictionary.
    """
    endpoint_id = endpoint.get("id", str(uuid.uuid4()))

    with st.container():
        st.subheader(f"Endpoint #{index + 1}")
        col_include, col_del, col_title = st.columns([1.5, 1, 5])
        with col_include:
            include = st.checkbox(
                "Include",
                value=endpoint.get("include", True),
                key=f"ep_include_{endpoint_id}",
                help="Include this endpoint when generating test cases",
            )
        with col_del:
            if st.button("Remove", key=f"remove_ep_{endpoint_id}", type="secondary"):
                st.session_state["endpoints"] = [
                    ep for ep in st.session_state["endpoints"]
                    if ep.get("id") != endpoint_id
                ]
                st.rerun()
        with col_title:
            st.caption(f"Endpoint ID: {endpoint_id}")

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

        # Headers (dynamic key-value)
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
            "include": include,
            "method": method,
            "url": full_url,
            "headers": new_headers,
            "query_params": new_qp,
            "path_params": new_pp,
            "body": body_parsed,
        }


def render_test_case_card(tc: dict, index: int) -> dict:
    """
    Render a single test case as a collapsible card with per-assertion checkboxes.

    Each test case is wrapped in st.expander for expand/retract visibility.
    Assertions have individual checkboxes and are sent to the backend on execute.

    Args:
        tc (dict): Test case dictionary.
        index (int): Position in the list (for unique widget keys).

    Returns:
        dict: The (possibly modified) test case dictionary.
    """
    tc_id = tc.get("id", f"tc_{index}")
    tc_type = tc.get("type", "unknown").upper()
    tc_name = tc.get("name", "Unnamed")

    # Ensure assertion config exists
    if "assertions" not in tc:
        tc["assertions"] = {
            "status": {"enabled": True, "expected_status": tc.get("expected_status", 200)},
            "body_contains": {"enabled": tc.get("expected_body_contains") is not None, "value": tc.get("expected_body_contains", "") or ""},
            "jsonpath": {"enabled": tc.get("jsonpath") is not None, "path": tc.get("jsonpath", "") or "", "expected_value": tc.get("expected_field_value", "") or ""},
        }

    assertions = tc["assertions"]

    # Collapsible test case card
    expander_title = f"{index + 1}. [{tc_type}] {tc_name}"
    with st.expander(expander_title, expanded=False):
        # Description
        st.caption(tc.get("description", ""))

        # Assertion Editor (individual checkboxes per assertion)
        st.markdown("**Assertions**")

        # Status assertion
        col_status_chk, col_status_val = st.columns([1, 3])
        with col_status_chk:
            assertions["status"]["enabled"] = st.checkbox(
                "Status",
                value=assertions["status"]["enabled"],
                key=f"tc_assert_status_enabled_{tc_id}",
            )
        with col_status_val:
            assertions["status"]["expected_status"] = st.number_input(
                "Expected Status",
                min_value=100,
                max_value=599,
                value=int(assertions["status"]["expected_status"] or 200),
                key=f"tc_assert_status_val_{tc_id}",
                disabled=not assertions["status"]["enabled"],
                label_visibility="collapsed",
            )

        # Body Contains assertion
        col_body_chk, col_body_val = st.columns([1, 4])
        with col_body_chk:
            assertions["body_contains"]["enabled"] = st.checkbox(
                "Body Contains",
                value=assertions["body_contains"]["enabled"],
                key=f"tc_assert_body_enabled_{tc_id}",
            )
        with col_body_val:
            assertions["body_contains"]["value"] = st.text_input(
                "Text",
                value=assertions["body_contains"]["value"] or "",
                key=f"tc_assert_body_val_{tc_id}",
                placeholder="Text in response body",
                disabled=not assertions["body_contains"]["enabled"],
                label_visibility="collapsed",
            )

        # Exact Field (JSONPath) assertion
        col_jsonpath_chk = st.columns([1])[0]
        with col_jsonpath_chk:
            assertions["jsonpath"]["enabled"] = st.checkbox(
                "Exact Field (JSONPath)",
                value=assertions["jsonpath"]["enabled"],
                key=f"tc_assert_jsonpath_enabled_{tc_id}",
            )

        col_jsonpath_val, col_expected_val = st.columns(2)
        with col_jsonpath_val:
            assertions["jsonpath"]["path"] = st.text_input(
                "JSONPath",
                value=assertions["jsonpath"]["path"] or "",
                key=f"tc_assert_jsonpath_val_{tc_id}",
                placeholder="e.g. $.token",
                disabled=not assertions["jsonpath"]["enabled"],
                label_visibility="collapsed",
            )
        with col_expected_val:
            assertions["jsonpath"]["expected_value"] = st.text_input(
                "Expected Value",
                value=assertions["jsonpath"]["expected_value"] or "",
                key=f"tc_assert_expected_val_{tc_id}",
                placeholder="Expected field value",
                disabled=not assertions["jsonpath"]["enabled"],
                label_visibility="collapsed",
            )

        # Execute button (prominent, full width)
        execute_btn = st.button("Execute Test Case", key=f"exec_{tc_id}", type="primary", use_container_width=True)

        # Request details expander (nested)
        with st.expander("Test Case Request Details", expanded=False):
            st.json(tc.get("request", {}))

        # Execute button handler
        if execute_btn:
            with st.spinner("Executing..."):
                try:
                    # Build assertions payload from individual checkboxes
                    assertions_payload = {}
                    if assertions["status"]["enabled"]:
                        assertions_payload["status"] = {
                            "enabled": True,
                            "expected_status": assertions["status"]["expected_status"],
                        }
                    if assertions["body_contains"]["enabled"]:
                        assertions_payload["body_contains"] = {
                            "enabled": True,
                            "value": assertions["body_contains"]["value"],
                        }
                    if assertions["jsonpath"]["enabled"]:
                        assertions_payload["jsonpath"] = {
                            "enabled": True,
                            "path": assertions["jsonpath"]["path"],
                            "expected_value": assertions["jsonpath"]["expected_value"],
                        }

                    result = api_post(
                        "/api/v1/test-cases/execute",
                        {
                            "test_case_id": tc_id,
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

            st.markdown(
                f"**Execution Result:** "
                f"<span style='color:{status_color}; font-weight:bold'>{status.upper()}</span>  "
                f"| Latency: {latency} ms",
                unsafe_allow_html=True,
            )
            st.caption(result.get("assertion_detail", ""))

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
    """
    Main Streamlit application entry point.
    """
    initialize_session_state()

    st.set_page_config(page_title="Api-Agent", layout="wide")
    st.title("Api-Agent - API Test Case Generator & Executor")

    tab1, tab2 = st.tabs(["1. Endpoints", "2. Test Cases"])

    # Tab 1: Endpoints
    with tab1:
        st.header("Endpoints")
        st.caption("Parse cURL commands and edit request components. Supports multiple endpoints with include/exclude toggle.")

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
                edited = render_endpoint_editor(ep, i)
                updated_endpoints.append(edited)
                st.divider()

            st.session_state["endpoints"] = updated_endpoints

            # Select endpoint for test case generation
            included_endpoints = [ep for ep in st.session_state["endpoints"] if ep.get("include", True)]

            if included_endpoints:
                st.subheader("Select Endpoint for Test Cases")
                endpoint_options = {
                    f"#{i+1} - {ep.get('method', 'GET')} {ep.get('url', '')[:60]}": ep.get("id")
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
                f"Using endpoint: {selected_endpoint.get('method', 'GET')} "
                f"{selected_endpoint.get('url', '')}"
            )

            business_req = st.text_area("Business Requirements (optional)", height=100)

            col_gen, col_clear = st.columns([1, 1])
            with col_gen:
                if st.button("Generate Test Cases", type="primary"):
                    with st.spinner("Generating test cases with AI..."):
                        try:
                            payload = {
                                "parsed_curl": selected_endpoint,
                                "business_requirements": business_req or None,
                            }
                            result = api_post("/api/v1/test-cases/generate", payload)
                            st.session_state["test_cases"] = result
                            st.session_state["executions"] = {}
                            st.success(f"Generated {len(result)} test case(s).")
                        except Exception as exc:
                            st.error(f"Failed to generate test cases: {exc}")

            with col_clear:
                if st.button("Clear Test Cases"):
                    st.session_state["test_cases"] = []
                    st.session_state["executions"] = {}
                    st.rerun()

            test_cases = st.session_state.get("test_cases", [])

            if test_cases:
                st.subheader(f"Test Cases ({len(test_cases)})")

                # Sort test cases by their id number (tc_1, tc_2, etc.)
                def sort_key(tc):
                    tc_id = tc.get("id", "tc_0")
                    try:
                        num = int(tc_id.replace("tc_", ""))
                    except (ValueError, AttributeError):
                        num = 0
                    return num

                sorted_test_cases = sorted(test_cases, key=sort_key)

                # Render each test case as a collapsible card with per-assertion checkboxes
                updated_test_cases = []
                for i, tc in enumerate(sorted_test_cases):
                    edited_tc = render_test_case_card(tc, i)
                    updated_test_cases.append(edited_tc)

                st.session_state["test_cases"] = updated_test_cases


if __name__ == "__main__":
    main()
