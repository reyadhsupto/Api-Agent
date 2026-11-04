"""
Executes a single API test case using python requests.

Accepts:
    test_case (dict): Test case definition.
    base_url (str): Optional base URL prefix.

Returns:
    dict: Execution result with request, response, latency, assertion.
"""

import time
import json
import requests


def execute_test_case(test_case: dict, base_url: str = "", assertions: dict | None = None) -> dict:
    """
    Execute an API test case and capture full metadata.

    Args:
        test_case (dict): Test case with request, expected_status, expected_body_contains.
        base_url (str): Optional base URL to prepend to relative paths.
        assertions (dict | None): Assertion config from the frontend UI.
            Keys: status, body_contains, jsonpath. Each has enabled + value/path/expected_value.

    Returns:
        dict: Execution result including pass/fail status and detail.
    """
    request = test_case.get("request") or {}
    method = request.get("method", "GET").upper()
    url = request.get("url", "")
    if base_url and url.startswith("/"):
        url = base_url.rstrip("/") + url

    headers = request.get("headers", {}) or {}
    body = request.get("body")

    test_case_id = test_case.get("id", "unknown")

    # Resolve assertion config: frontend overrides take precedence
    assertions = assertions or {}

    status_cfg = assertions.get("status", {})
    status_enabled = status_cfg.get("enabled", True)
    expected_status = status_cfg.get("expected_status", test_case.get("expected_status"))

    body_contains_cfg = assertions.get("body_contains", {})
    body_contains_enabled = body_contains_cfg.get("enabled", False)
    expected_body_contains = body_contains_cfg.get("value", test_case.get("expected_body_contains"))

    jsonpath_cfg = assertions.get("jsonpath", {})
    jsonpath_enabled = jsonpath_cfg.get("enabled", False)
    jsonpath = jsonpath_cfg.get("path", test_case.get("jsonpath"))
    expected_field_value = jsonpath_cfg.get("expected_value", test_case.get("expected_field_value"))

    start_time = time.perf_counter()
    try:
        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            json=body if isinstance(body, dict) else None,
            data=body if isinstance(body, str) else None,
            timeout=30,
        )
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

        # Evaluate each enabled assertion
        assertion_results = []
        all_passed = True

        # 1. Status assertion
        if status_enabled:
            status_ok = expected_status is None or response.status_code == expected_status
            assertion_results.append(
                f"Status: expected {expected_status}, got {response.status_code} -> {'PASS' if status_ok else 'FAIL'}"
            )
            if not status_ok:
                all_passed = False

        # 2. Body Contains assertion
        if body_contains_enabled:
            body_ok = expected_body_contains in response.text if expected_body_contains else True
            assertion_results.append(
                f"Body contains '{expected_body_contains}': {'PASS' if body_ok else 'FAIL'}"
            )
            if not body_ok:
                all_passed = False

        # 3. Exact Field (JSONPath) assertion
        if jsonpath_enabled and jsonpath:
            field_ok, field_actual = _check_jsonpath(response.text, jsonpath, expected_field_value)
            assertion_results.append(
                f"JSONPath '{jsonpath}': expected {expected_field_value}, got {field_actual} -> {'PASS' if field_ok else 'FAIL'}"
            )
            if not field_ok:
                all_passed = False

        passed = all_passed and len(assertion_results) > 0

        return {
            "test_case_id": test_case_id,
            "status": "passed" if passed else "failed",
            "request_url": url,
            "request_method": method,
            "request_headers": headers,
            "request_body": body,
            "response_status": response.status_code,
            "response_headers": dict(response.headers),
            "response_body": response.text,
            "latency_ms": latency_ms,
            "assertion_detail": "; ".join(assertion_results) if assertion_results else "No assertions enabled",
        }
    except requests.RequestException as exc:
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        return {
            "test_case_id": test_case_id,
            "status": "error",
            "request_url": url,
            "request_method": method,
            "request_headers": headers,
            "request_body": body,
            "response_status": None,
            "response_headers": {},
            "response_body": str(exc),
            "latency_ms": latency_ms,
            "assertion_detail": f"Request failed: {exc!s}",
        }


def _check_jsonpath(response_text: str, jsonpath: str, expected_value: str) -> tuple:
    """
    Check a JSONPath field in the response body against an expected value.

    Supports simple JSONPath like $.token, $.user.id, $.data[0].name.

    Args:
        response_text (str): Raw response body text.
        jsonpath (str): JSONPath expression.
        expected_value (str): Expected value to compare against.

    Returns:
        tuple: (bool ok, str actual_value) - whether the field matches and the actual value found.
    """
    try:
        data = json.loads(response_text)
    except (json.JSONDecodeError, TypeError):
        return False, "invalid JSON"

    if not jsonpath.startswith("$"):
        return False, "invalid JSONPath (must start with $)"

    parts = jsonpath[2:].split(".")  # strip "$."
    current = data

    for part in parts:
        if part.endswith("]"):
            key_part = part[: part.index("[")]
            index_part = int(part[part.index("[") + 1 : part.index("]")])
            if key_part:
                if not isinstance(current, dict) or key_part not in current:
                    return False, f"key '{key_part}' not found"
                current = current[key_part]
            if not isinstance(current, list) or index_part >= len(current):
                return False, f"index {index_part} out of range"
            current = current[index_part]
        else:
            if not isinstance(current, dict) or part not in current:
                return False, f"key '{part}' not found"
            current = current[part]

    actual_value = str(current)
    ok = actual_value == str(expected_value)
    return ok, actual_value