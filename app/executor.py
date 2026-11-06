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
from typing import Any
from jsonschema import Draft202012Validator


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
    # Supports multiple assertion instances for every assertion type.
    assertions = assertions or {}

    status_cfg_list = _assertion_list(assertions.get("status"))
    body_contains_cfg_list = _assertion_list(assertions.get("body_contains"))
    jsonpath_cfg_list = _assertion_list(assertions.get("jsonpath"))
    response_schema_cfg_list = _assertion_list(assertions.get("response_schema"))

    start_time = time.perf_counter()
    try:
        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            json=body if isinstance(body, (dict, list)) else None,
            data=body if isinstance(body, str) else None,
            timeout=30,
        )
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

        assertion_results, all_passed = _evaluate_assertions(
            response.status_code,
            response.text,
            status_cfg_list,
            body_contains_cfg_list,
            jsonpath_cfg_list,
            test_case,
            response_schema_cfg_list,
        )

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


def _assertion_list(config: dict | list | None) -> list[dict]:
    """Normalize one assertion config or a list of configs to a clean list."""
    if isinstance(config, dict):
        return [config]
    if isinstance(config, list):
        return [item for item in config if isinstance(item, dict)]
    return []


def _evaluate_response_schema(response_text: str, schema_value) -> tuple[bool, str]:
    """Validate a JSON response body against a JSON Schema document.

    Args:
        response_text (str): Raw HTTP response body.
        schema_value (Any): JSON Schema object or serialized JSON text.

    Returns:
        tuple[bool, str]: Validation result and a concise explanation.
    """
    try:
        response_json = json.loads(response_text)
    except (json.JSONDecodeError, TypeError):
        return False, "Response body is not valid JSON."
    try:
        schema = json.loads(schema_value) if isinstance(schema_value, str) else schema_value
        Draft202012Validator.check_schema(schema)
        errors = list(Draft202012Validator(schema).iter_errors(response_json))
    except Exception as exc:
        return False, f"Invalid JSON Schema: {exc}."
    if errors:
        return False, errors[0].message
    return True, "Response matches the JSON Schema."


def _evaluate_assertions(
    response_status: int,
    response_text: str,
    status_configs: list[dict],
    body_configs: list[dict],
    jsonpath_configs: list[dict],
    test_case: dict | None = None,
    response_schema_configs: list[dict] | None = None,
) -> tuple[list[str], bool]:
    """Evaluate all enabled assertion instances and return details plus overall status."""
    test_case = test_case or {}
    details = []
    all_passed = True

    for config in status_configs:
        if not config.get("enabled", True):
            continue
        expected = config.get("expected_status", test_case.get("expected_status"))
        passed = expected is None or response_status == expected
        details.append(f"Status: expected {expected}, got {response_status} -> {'PASS' if passed else 'FAIL'}")
        all_passed = all_passed and passed

    for config in body_configs:
        if not config.get("enabled", False):
            continue
        expected = config.get("value", test_case.get("expected_body_contains"))
        passed = expected in response_text if expected else True
        details.append(f"Body contains '{expected}': {'PASS' if passed else 'FAIL'}")
        all_passed = all_passed and passed

    for config in jsonpath_configs:
        if not config.get("enabled", False):
            continue
        path = config.get("path", test_case.get("jsonpath"))
        expected = config.get("expected_value", test_case.get("expected_field_value"))
        if not path:
            continue
        passed, actual = _check_jsonpath(response_text, path, expected)
        details.append(f"JSONPath '{path}': expected {expected}, got {actual} -> {'PASS' if passed else 'FAIL'}")
        all_passed = all_passed and passed

    for config in response_schema_configs or []:
        if not config.get("enabled", False):
            continue
        passed, detail = _evaluate_response_schema(response_text, config.get("schema", ""))
        details.append(f"Response schema -> {'PASS' if passed else 'FAIL'}: {detail}")
        all_passed = all_passed and passed

    return details, all_passed


def evaluate_request_assertions(response_status: int, response_text: str, assertions: list[dict]) -> dict:
    """Evaluate request-playground assertions against one already received response.

    Args:
        response_status (int): HTTP status code returned by the request.
        response_text (str): Raw response body text.
        assertions (list[dict]): Assertion instances selected for this execution.

    Returns:
        dict: Per-assertion results and the aggregate pass/fail status.
    """
    results = []
    for assertion in assertions:
        assertion_type = assertion.get("type")
        assertion_id = assertion.get("id")
        passed = False
        if assertion_type == "status":
            expected = assertion.get("expected_status")
            passed = expected is not None and response_status == expected
            detail = f"Expected status {expected}, received {response_status}."
        elif assertion_type == "body_contains":
            expected = assertion.get("value", "")
            passed = bool(expected) and expected in response_text
            detail = f"Response body {'contains' if passed else 'does not contain'} {expected!r}."
        elif assertion_type == "jsonpath":
            path = assertion.get("path", "")
            expected = assertion.get("expected_value", "")
            try:
                passed, actual = _check_jsonpath(response_text, path, expected)
                detail = f"{path}: expected {expected!r}, received {actual!r}."
            except (ValueError, IndexError) as exc:
                detail = f"Invalid JSONPath: {exc}."
        elif assertion_type == "response_schema":
            passed, detail = _evaluate_response_schema(response_text, assertion.get("schema", ""))
        else:
            detail = f"Unsupported assertion type: {assertion_type!r}."

        results.append({
            "id": assertion_id,
            "type": assertion_type,
            "passed": bool(passed),
            "detail": detail,
        })

    all_passed = bool(results) and all(result["passed"] for result in results)
    return {"results": results, "passed": all_passed}


def execute_flow_test_case(test_case: dict, base_url: str = "", assertions: dict | None = None) -> dict:
    """
    Execute a flow test case by running all steps sequentially with variable substitution.

    Args:
        test_case (dict): Flow test case with steps, each containing endpoint, assertions, variable_mappings.
        base_url (str): Optional base URL to prepend to relative URLs.
        assertions (dict | None): Not used for flow execution (assertions are per-step).

    Returns:
        dict: Execution result with per-step details and overall pass/fail status.
    """
    test_case_id = test_case.get("id", "unknown")
    steps = test_case.get("steps", [])

    if not steps:
        return {
            "test_case_id": test_case_id,
            "status": "error",
            "assertion_detail": "No steps in flow test case",
            "steps_executed": [],
        }

    step_results = []
    response_texts = []
    all_passed = True

    for step in steps:
        step_order = step.get("step_order", len(step_results) + 1)
        endpoint = step.get("endpoint", {})

        # Apply variable mappings from previous responses
        step = _apply_variable_mappings(response_texts, step)
        endpoint = step.get("endpoint", {})

        method = endpoint.get("method", "GET").upper()
        url = endpoint.get("url", "")
        if base_url and url.startswith("/"):
            url = base_url.rstrip("/") + url

        headers = endpoint.get("headers", {}) or {}
        body = endpoint.get("body")

        step_start = time.perf_counter()
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                json=body if isinstance(body, (dict, list)) else None,
                data=body if isinstance(body, str) else None,
                timeout=30,
            )
            latency_ms = round((time.perf_counter() - step_start) * 1000, 2)
            response_texts.append(response.text)

            # Evaluate every enabled assertion instance. Legacy dict configs remain valid.
            step_assertions = step.get("assertions", {}) or {}
            status_configs = _assertion_list(
                step_assertions.get("status", {"enabled": True, "expected_status": 200})
            )
            assertion_details, step_passed = _evaluate_assertions(
                response.status_code,
                response.text,
                status_configs,
                _assertion_list(step_assertions.get("body_contains")),
                _assertion_list(step_assertions.get("jsonpath")),
                response_schema_configs=_assertion_list(step_assertions.get("response_schema")),
            )

            step_results.append({
                "step_order": step_order,
                "endpoint": endpoint.get("name", endpoint.get("url", "")),
                "method": method,
                "url": url,
                "request_headers": headers,
                "request_body": body,
                "response_status": response.status_code,
                "response_headers": dict(response.headers),
                "response_body": response.text,
                "latency_ms": latency_ms,
                "status": "passed" if step_passed else "failed",
                "assertion_detail": "; ".join(assertion_details) if assertion_details else "No assertions enabled",
            })

            if not step_passed:
                all_passed = False
                # Stop on first failed step for flow execution
                break

        except requests.RequestException as exc:
            latency_ms = round((time.perf_counter() - step_start) * 1000, 2)
            step_results.append({
                "step_order": step_order,
                "endpoint": endpoint.get("name", endpoint.get("url", "")),
                "method": method,
                "url": url,
                "request_headers": headers,
                "request_body": body,
                "response_status": None,
                "response_headers": {},
                "response_body": str(exc),
                "latency_ms": latency_ms,
                "status": "error",
                "assertion_detail": f"Request failed: {exc!s}",
            })
            all_passed = False
            break

    overall_status = "passed" if all_passed and len(step_results) == len(steps) else "failed"

    return {
        "test_case_id": test_case_id,
        "status": overall_status,
        "steps_executed": len(step_results),
        "total_steps": len(steps),
        "assertion_detail": f"Flow executed {len(step_results)}/{len(steps)} steps. Overall: {'PASSED' if all_passed else 'FAILED'}",
        "step_results": step_results,
    }


def _extract_jsonpath(response_text: str, jsonpath: str) -> Any:
    """
    Extract a value from the response body using a JSONPath expression.

    Args:
        response_text (str): Raw response body text.
        jsonpath (str): JSONPath expression, including array wildcards such as $.items[*].id.

    Returns:
        Any: Extracted scalar text or wildcard result list; empty string if not found.
    """
    try:
        data = json.loads(response_text)
    except (json.JSONDecodeError, TypeError):
        return ""

    if not isinstance(jsonpath, str) or not jsonpath.startswith("$"):
        return ""

    if jsonpath == "$":
        return str(data)

    parts = jsonpath[2:].strip(".").split(".")
    current = data
    wildcard_used = False

    for part in parts:
        key_part, has_index, index_part = part.partition("[")
        if key_part:
            if isinstance(current, list):
                current = [item[key_part] for item in current if isinstance(item, dict) and key_part in item]
                if not current:
                    return ""
            elif isinstance(current, dict) and key_part in current:
                current = current[key_part]
            else:
                return ""

        if has_index:
            if not part.endswith("]"):
                return ""
            index_token = index_part[:-1]
            if index_token == "*":
                if not isinstance(current, list):
                    return ""
                wildcard_used = True
            else:
                try:
                    index = int(index_token)
                except ValueError:
                    return ""
                if not isinstance(current, list) or not -len(current) <= index < len(current):
                    return ""
                current = current[index]

    if current is None:
        return ""
    return current if wildcard_used and isinstance(current, list) else str(current)


def _apply_variable_mappings(response_texts: list, step: dict) -> dict:
    """
    Apply variable mappings from previous step responses to the current step's request.

    For each variable_mapping in the step, extracts a value from a previous response
    using JSONPath and injects it into the current request (headers or body).

    Args:
        response_texts (list): List of response body strings from previous steps.
        step (dict): The current flow step with variable_mappings.

    Returns:
        dict: Modified step with updated request headers/body.
    """
    import copy

    step = copy.deepcopy(step)
    endpoint = step.get("endpoint", {})
    mappings = step.get("variable_mappings", [])

    if not mappings or not response_texts:
        return step

    headers = endpoint.get("headers", {}) or {}
    body = endpoint.get("body")

    for mapping in mappings:
        if not isinstance(mapping, dict):
            continue
        from_path = mapping.get("from", "")
        to_path = mapping.get("to", "")
        transform = mapping.get("transform", "")
        if not isinstance(from_path, str) or not isinstance(to_path, str):
            continue

        # Extract value from previous response
        # from_path references the step index and JSONPath, e.g., "1:$.token"
        # or just "$.token" for the most recent response
        extracted_value = ""
        if ":" in from_path:
            step_idx_str, jsonpath = from_path.split(":", 1)
            try:
                step_idx = int(step_idx_str) - 1  # 1-based to 0-based
                if 0 <= step_idx < len(response_texts):
                    extracted_value = _extract_jsonpath(response_texts[step_idx], jsonpath)
            except (ValueError, IndexError):
                extracted_value = ""
        else:
            # Use most recent response
            if response_texts:
                extracted_value = _extract_jsonpath(response_texts[-1], from_path)

        if not extracted_value:
            continue

        # Apply transform if specified
        mapped_value = extracted_value
        if transform:
            value_text = (
                extracted_value if isinstance(extracted_value, str)
                else json.dumps(extracted_value, ensure_ascii=False, separators=(",", ":"))
            )
            mapped_value = transform.replace("{value}", value_text) if isinstance(transform, str) else value_text

        # Inject into request
        if to_path.startswith("headers."):
            header_name = to_path[len("headers."):]
            headers[header_name] = (
                mapped_value if isinstance(mapped_value, str)
                else json.dumps(mapped_value, ensure_ascii=False, separators=(",", ":"))
            )
        elif to_path.startswith("request.body"):
            if body is None:
                body = {}
            if isinstance(body, dict):
                # Support nested like request.body.userId
                field_path = to_path[len("request.body"):].strip(".")
                if not field_path:
                    body = mapped_value
                else:
                    parts = field_path.split(".")
                    target = body
                    for part in parts[:-1]:
                        if not isinstance(target.get(part), dict):
                            target[part] = {}
                        target = target[part]
                    target[parts[-1]] = mapped_value
            elif isinstance(body, str):
                # If body is a string, try to inject as JSON
                try:
                    import json as _json
                    body_dict = _json.loads(body)
                    field_path = to_path[len("request.body"):].strip(".")
                    parts = field_path.split(".")
                    target = body_dict
                    for p in parts[:-1]:
                        if p not in target:
                            target[p] = {}
                        target = target[p]
                    target[parts[-1]] = extracted_value
                    body = _json.dumps(body_dict)
                except _json.JSONDecodeError:
                    body = extracted_value

    step["endpoint"] = {
        **endpoint,
        "headers": headers,
        "body": body,
    }
    return step
