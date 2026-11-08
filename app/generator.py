"""
Generates AI-powered test cases from a parsed cURL.

Accepts:
    parsed_curl (dict): Parsed request components.
    business_requirements (str | None): Optional business rules.

Returns:
    list[dict]: Test cases with type, name, description, request, expected values.
"""

import os
import re
import json
import requests
from urllib.parse import parse_qsl, urlsplit, urlunsplit


def _output_token_limit() -> int:
    """Read a shared configurable generation ceiling for supported providers."""
    try:
        return min(max(int(os.getenv("API_AGENT_LLM_MAX_OUTPUT_TOKENS", "6000")), 256), 16000)
    except ValueError:
        return 6000


def generate_test_cases(parsed_curl: dict, business_requirements: str | None = None) -> list:
    """
    Generate test cases using free-tier LLM providers with fallback.

    Args:
        parsed_curl (dict): Parsed cURL request components.
        business_requirements (str | None): Optional business logic text.

    Returns:
        list: Generated test case dictionaries.
    """
    prompt = _build_prompt(parsed_curl, business_requirements)
    generated_text = _call_llm_with_fallback(prompt)
    return _parse_generated_response(generated_text)


def _validate_generated_cases(test_cases: list) -> list:
    """Validate parsed LLM cases and reject malformed output instead of fabricating cases."""
    if not isinstance(test_cases, list) or not test_cases:
        raise ValueError("LLM response must be a non-empty JSON array.")

    for index, test_case in enumerate(test_cases, start=1):
        if not isinstance(test_case, dict):
            raise ValueError(f"LLM test case {index} must be a JSON object.")
        if test_case.get("is_flow") or "steps" in test_case:
            steps = test_case.get("steps")
            if not isinstance(steps, list) or not steps:
                raise ValueError(f"Flow test case {index} must contain a non-empty steps array.")
            step_orders = []
            for step_index, step in enumerate(steps, start=1):
                if not isinstance(step, dict):
                    raise ValueError(f"Flow test case {index}, step {step_index} must be a JSON object.")
                step_order = step.get("step_order")
                if isinstance(step_order, bool) or not isinstance(step_order, int):
                    raise ValueError(
                        f"Flow test case {index}, step {step_index} has invalid step_order; expected integer {step_index}."
                    )
                step_orders.append(step_order)
                if step_order != step_index:
                    raise ValueError(
                        f"Flow test case {index}, step {step_index} has step_order {step_order}; expected {step_index}."
                    )
                endpoint = step.get("endpoint")
                if not isinstance(endpoint, dict) or not endpoint.get("url"):
                    raise ValueError(
                        f"Flow test case {index}, step {step_index} is missing endpoint.url."
                    )
            if len(set(step_orders)) != len(step_orders):
                raise ValueError(f"Flow test case {index} contains duplicate step_order values.")
    return test_cases


def _build_prompt(parsed_curl: dict, business_requirements: str | None) -> str:
    """
    Build the LLM prompt for test case generation.

    Args:
        parsed_curl (dict): Parsed cURL request components.
        business_requirements (str | None): Optional business logic text.

    Returns:
        str: The prompt string.
    """
    req_text = (
        f"Method: {parsed_curl.get('method')}\n"
        f"URL: {parsed_curl.get('url')}\n"
        f"Headers: {parsed_curl.get('headers')}\n"
        f"Body: {parsed_curl.get('body')}\n"
    )
    if business_requirements:
        req_text += f"\nBusiness Requirements: {business_requirements}\n"

    return (
        "You are a Senior software test engineer(SQA). Generate COMPREHENSIVE test cases "
        "covering positive, negative, edge, and race scenarios for the following API "
        "request.\n"
        "Generate AT LEAST 6 test cases covering different scenarios:\n"
        "1. Positive test: valid request, expect success (2xx)\n"
        "2. Negative test: invalid data, expect error (4xx)\n"
        "3. Negative test: missing required fields, expect error (4xx)\n"
        "4. Edge case: boundary values, empty strings, null values\n"
        "5. Edge case: maximum/minimum values, special characters\n"
        "6. Race condition: concurrent requests, consistency checks\n"
        "7. Any additional scenarios relevant to this API endpoint\n"
        f"\n{req_text}\n"
        "Return ONLY a valid JSON array (no markdown, no explanation) where each item has:\n"
        "- id: unique string like \"tc_1\"\n"
        "- type: one of \"positive\", \"negative\", \"edge\", \"race\"\n"
        "- name: descriptive test name\n"
        "- description: what this test validates\n"
        "- request: the full request object with method, url, headers, body\n"
        "- expected_status: expected HTTP status code (integer)\n"
        "- expected_body_contains: string that should appear in response body (optional)\n"
    )


def _call_llm_with_fallback(prompt: str) -> str:
    """
    Call LLM providers in order with automatic fallback.

    Args:
        prompt (str): The prompt to send.

    Returns:
        str: Generated text from the first successful provider.

    Raises:
        RuntimeError: If all providers fail, with the first provider's error.
    """
    providers = [
        ("openrouter", os.getenv("OPENROUTER_API_KEY"), "https://openrouter.ai/api/v1/chat/completions"),
        ("groq", os.getenv("GROQ_API_KEY"), "https://api.groq.com/openai/v1/chat/completions"),
        ("cohere", os.getenv("COHERE_API_KEY"), "https://api.cohere.ai/v1/generate"),
        ("huggingface", os.getenv("HUGGINGFACE_API_KEY"), "https://api-inference.huggingface.co/models/meta-llama/Llama-3.1-8B-Instruct"),
    ]

    first_error = None
    for name, api_key, url in providers:
        if not api_key:
            continue
        try:
            if name == "groq":
                return _groq_call(prompt, api_key, url)
            elif name == "openrouter":
                return _openrouter_call(prompt, api_key, url)
            elif name == "cohere":
                return _cohere_call(prompt, api_key, url)
            elif name == "huggingface":
                return _huggingface_call(prompt, api_key, url)
        except Exception as exc:
            if first_error is None:
                first_error = f"{name}: {exc!s}"
            continue

    if first_error:
        raise RuntimeError(f"LLM generation failed. First provider error: {first_error}")
    raise RuntimeError("No LLM providers are configured. Set at least one API key in .env")


def _groq_get_best_model(api_key: str, url: str) -> str:
    """
    Fetch available Groq models and return the one with the largest context window.

    Args:
        api_key (str): Groq API key.
        url (str): Groq chat completions endpoint URL.

    Returns:
        str: Model ID with the largest context window, or fallback default.
    """
    headers = {"Authorization": f"Bearer {api_key}"}
    models_url = url.replace("/chat/completions", "/models")
    response = requests.get(models_url, headers=headers, timeout=30)
    response.raise_for_status()
    models = response.json().get("data", [])

    best_model = "llama-3.1-8b-instant"
    best_context = 0

    for model in models:
        context = model.get("context_window", 0)
        if context > best_context and model.get("active", False):
            best_context = context
            best_model = model.get("id", best_model)

    return best_model


def _groq_call(prompt: str, api_key: str, url: str) -> str:
    """
    Call Groq API using the model with the largest context window.

    Args:
        prompt (str): Input prompt.
        api_key (str): Groq API key.
        url (str): Groq chat completions endpoint URL.

    Returns:
        str: Generated completion text.
    """
    model = _groq_get_best_model(api_key, url)
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": _output_token_limit(),
    }
    response = requests.post(url, headers=headers, json=payload, timeout=30)
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


def _openrouter_call(prompt: str, api_key: str, url: str) -> str:
    """
    Call OpenRouter API.

    Args:
        prompt (str): Input prompt.
        api_key (str): OpenRouter API key.
        url (str): OpenRouter chat completions endpoint URL.

    Returns:
        str: Generated completion text.
    """
    model = os.getenv("OPENROUTER_MODEL", "nvidia/nemotron-3-ultra-550b-a55b:free")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": _output_token_limit(),
    }
    response = requests.post(url, headers=headers, json=payload, timeout=60)
    response.raise_for_status()
    print(response.json()["choices"][0]["message"]["content"])
    return response.json()["choices"][0]["message"]["content"]


def _cohere_call(prompt: str, api_key: str, url: str) -> str:
    """
    Call Cohere API.

    Args:
        prompt (str): Input prompt.
        api_key (str): Cohere API key.
        url (str): Cohere API endpoint.

    Returns:
        str: Generated completion text.
    """
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"model": "command-r", "prompt": prompt, "temperature": 0.3, "max_tokens": _output_token_limit()}
    response = requests.post(url, headers=headers, json=payload, timeout=30)
    response.raise_for_status()
    return response.json()["text"]


def _huggingface_call(prompt: str, api_key: str, url: str) -> str:
    """
    Call HuggingFace Inference API.

    Args:
        prompt (str): Input prompt.
        api_key (str): HuggingFace API key.
        url (str): HuggingFace model endpoint.

    Returns:
        str: Generated completion text.
    """
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"inputs": prompt, "parameters": {"max_new_tokens": _output_token_limit(), "temperature": 0.3}}
    response = requests.post(url, headers=headers, json=payload, timeout=30)
    response.raise_for_status()
    return response.json()[0]["generated_text"]


def generate_flow_test_cases(
    endpoints: list,
    business_requirements: str | None = None,
    scenario_count: int | None = None,
) -> list:
    """
    Generate flow test cases for a sequence of endpoints.

    Each test case represents a step in the flow where data from a previous
    endpoint's response may be used in the next endpoint's request.

    Args:
        endpoints (list): Ordered list of endpoint dicts.
        business_requirements (str | None): Optional business logic text.
        scenario_count (int | None): Deprecated compatibility argument; ignored.

    Returns:
        list: Generated flow test case dictionaries.
    """
    prompt = _build_flow_prompt(endpoints, business_requirements)
    generated_text = _call_llm_with_fallback(prompt)
    test_cases = _parse_generated_response(generated_text, validate=False)
    _attach_flow_endpoints(test_cases, endpoints)
    return _validate_generated_cases(test_cases)


def _attach_flow_endpoints(test_cases: list[dict], endpoints: list[dict]) -> None:
    """Attach canonical request data to compact generated flow steps.

    Args:
        test_cases (list[dict]): Parsed cases containing compact endpoint references.
        endpoints (list[dict]): Ordered endpoint data supplied to the LLM.

    Returns:
        None: Updates each step with its canonical endpoint and stable ID.

    Raises:
        ValueError: If a generated step cannot be matched to an input endpoint.
    """
    by_id = {
        str(endpoint.get("id")): endpoint
        for endpoint in endpoints if endpoint.get("id") is not None
    }
    by_url = {
        (str(endpoint.get("method", "GET")).upper(), str(endpoint.get("url", ""))): endpoint
        for endpoint in endpoints
    }

    for case_index, case in enumerate(test_cases, start=1):
        if not isinstance(case, dict):
            raise ValueError(f"Flow test case {case_index} must be a JSON object.")
        steps = case.get("steps")
        if not isinstance(steps, list):
            raise ValueError(f"Flow test case {case_index} must contain a steps array.")
        for step_index, step in enumerate(steps, start=1):
            if not isinstance(step, dict):
                raise ValueError(f"Flow test case {case_index}, step {step_index} must be a JSON object.")
            reference = step.get("endpoint_id")
            endpoint = by_id.get(str(reference)) if reference is not None else None
            if endpoint is None and isinstance(reference, int) and not isinstance(reference, bool):
                if 1 <= reference <= len(endpoints):
                    endpoint = endpoints[reference - 1]
            if endpoint is None and isinstance(reference, str) and reference.isdigit():
                position = int(reference)
                if 1 <= position <= len(endpoints):
                    endpoint = endpoints[position - 1]
            if endpoint is None and isinstance(step.get("endpoint"), dict):
                llm_endpoint = step["endpoint"]
                endpoint = by_url.get((
                    str(llm_endpoint.get("method", "GET")).upper(),
                    str(llm_endpoint.get("url", "")),
                ))
            if endpoint is None:
                raise ValueError(
                    f"Flow test case {case_index}, step {step_index} references an unknown endpoint."
                )
            step["endpoint_id"] = endpoint.get("id", reference or step_index)
            step["endpoint"] = dict(endpoint)
            step.setdefault("description", "")
            step.setdefault("assertions", {})
            step.setdefault("variable_mappings", [])


def _flow_endpoint_summary(endpoint: dict, fallback_id: int) -> dict:
    """Create compact, non-secret request context for a flow-generation prompt.

    Args:
        endpoint (dict): Canonical request definition.
        fallback_id (int): Stable positional reference for unsaved requests.

    Returns:
        dict: Method, URL, parameter names, and a bounded body preview.
    """
    query_params = endpoint.get("query_params", {}) or {}
    if isinstance(query_params, dict):
        query_names = list(query_params)
    elif isinstance(query_params, list):
        query_names = [
            row.get("key") for row in query_params
            if isinstance(row, dict) and row.get("key") and row.get("enabled", True)
        ]
    else:
        query_names = []
    raw_url = str(endpoint.get("url", ""))
    url_parts = urlsplit(raw_url)
    query_names = list(dict.fromkeys(query_names + [
        key for key, _ in parse_qsl(url_parts.query, keep_blank_values=True)
    ]))
    body = endpoint.get("body")
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except json.JSONDecodeError:
            body = "<raw text omitted>"

    def value_shape(value):
        if isinstance(value, dict):
            return {key: value_shape(item) for key, item in value.items()}
        if isinstance(value, list):
            return [value_shape(value[0])] if value else []
        if isinstance(value, bool):
            return "<boolean>"
        if isinstance(value, (int, float)):
            return "<number>"
        if isinstance(value, str):
            return "<string>"
        return None

    body_preview = json.dumps(value_shape(body), ensure_ascii=False, separators=(",", ":"))[:1200]
    headers = endpoint.get("headers", {}) or {}
    header_names = list(headers) if isinstance(headers, dict) else [
        row.get("key") for row in headers if isinstance(row, dict) and row.get("key")
    ] if isinstance(headers, list) else []
    safe_url = urlunsplit((url_parts.scheme, url_parts.netloc, url_parts.path, "", ""))
    return {
        "endpoint_id": endpoint.get("id", fallback_id),
        "method": endpoint.get("method", "GET"),
        "url": safe_url,
        "path_parameters": re.findall(r"\{([^{}]+)\}", safe_url),
        "query_parameter_names": query_names,
        "header_names": header_names,
        "body_shape": body_preview,
    }


def extract_endpoints_from_document(document_text: str) -> list[dict]:
    """Extract explicit endpoints from prose in overlapping document sections.

    Args:
        document_text (str): Plain-text or Markdown API documentation.

    Returns:
        list[dict]: Deduplicated endpoint proposals with source evidence.

    Raises:
        ValueError: If model output is invalid or contains no endpoints.
        RuntimeError: If all configured LLM providers fail.
    """
    max_chunk = 24000
    overlap = 500
    chunks = [document_text] if len(document_text) <= max_chunk else [
        document_text[offset:offset + max_chunk]
        for offset in range(0, len(document_text), max_chunk - overlap)
    ]
    endpoints_by_key = {}
    for chunk in chunks:
        prompt = (
            "Extract every API endpoint explicitly described in this documentation section. "
            "Do not invent paths or methods. Return only a JSON array; return [] if this section "
            "contains no endpoint. Each item must contain method, path, name, description, "
            "source_excerpt, confidence (0 to 1), headers, query_params, and body. Use null for a "
            "body when none is explicitly documented. For query_params return an object of parameter "
            "names to documented example/default values. Preserve path placeholders as {name}. "
            "source_excerpt must be a short verbatim excerpt supporting the endpoint.\n\nDOCUMENTATION SECTION:\n"
            f"{chunk}"
        )
        generated_text = _call_llm_with_fallback(prompt).strip()
        if generated_text.startswith("```"):
            generated_text = re.sub(r"^```(?:json)?\s*|\s*```$", "", generated_text)
        match = re.search(r"\[.*\]", generated_text, re.DOTALL)
        if not match:
            raise ValueError("LLM endpoint extraction must return a JSON array.")
        try:
            result = json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            raise ValueError("LLM endpoint extraction returned malformed JSON.") from exc
        if not isinstance(result, list):
            raise ValueError("LLM endpoint extraction must return a JSON array.")
        for item in result:
            if not isinstance(item, dict):
                continue
            method = str(item.get("method", "")).upper()
            path = str(item.get("path") or item.get("url") or "").strip()
            if method not in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS", "TRACE"} or not path:
                continue
            item["method"] = method
            item["path"] = path
            endpoints_by_key.setdefault((method, path), item)
    endpoints = list(endpoints_by_key.values())
    if not endpoints:
        raise ValueError("No explicit HTTP endpoints could be extracted from the documentation.")
    return endpoints


def generate_discovered_flow_test_cases(
    endpoints: list[dict],
    candidates: list[dict],
    business_requirements: str | None = None,
) -> list[dict]:
    """Generate named flow scenarios for selected dependency paths.

    Args:
        endpoints (list[dict]): Persisted endpoint definitions for one imported source.
        candidates (list[dict]): User-selected dependency path records with edge evidence.
        business_requirements (str | None): Optional domain context for scenario meaning.

    Returns:
        list[dict]: LLM-proposed flow case objects awaiting backend validation.

    Raises:
        ValueError: If the model response is not a JSON array.
        RuntimeError: If all configured LLM providers fail.
    """
    endpoint_by_id = {item["id"]: item for item in endpoints}
    candidate_data = []
    for candidate in candidates:
        candidate_endpoints = [endpoint_by_id[item_id] for item_id in candidate["endpoint_ids"]]
        candidate_data.append({
            "candidate_id": candidate["id"],
            "steps": [
                _flow_endpoint_summary(endpoint, index)
                for index, endpoint in enumerate(candidate_endpoints, start=1)
            ],
            "dependencies": candidate.get("dependencies", []),
        })
    context = f"\nBusiness requirements:\n{business_requirements}" if business_requirements else ""
    prompt = (
        "Create executable API flow test scenarios for the selected dependency paths. "
        "Use only the endpoint IDs and order supplied in each candidate. Return JSON only as an array. "
        "Each result must include id, type (positive, negative, edge, or race), name, description, "
        "is_flow true, candidate_id, and steps. Each step must include step_order (1-based), "
        "endpoint_id copied exactly, description, assertions, and variable_mappings. Include one or "
        "more concise useful scenarios for every candidate. Do not repeat endpoint request data. "
        "A mapping must use `from` as a JSONPath in the "
        "producer response and `to` as `request.path.PARAM` or `request.body.FIELD`; only create "
        "mappings supported by the dependency evidence. Use the exact matched response JSONPath and "
        "request target. Use status assertions and JSONPath assertions only when grounded in the "
        "supplied schema evidence. Add body_contains only for documented literals. Do not invent "
        "response schemas or expected values. Each step must contain only step_order, endpoint_id, "
        "description, assertions, and variable_mappings; do not include an endpoint object, headers, "
        "cookies, URL, or request body. The application attaches canonical endpoint data. Keep names "
        "and descriptions short.\n\nSelected candidates:\n"
        f"{json.dumps(candidate_data, ensure_ascii=False)}{context}\n"
        "Expected step shape: {\"step_order\":1,\"endpoint_id\":\"...\",\"description\":\"...\","
        "\"assertions\":{\"status\":[{\"enabled\":true,\"expected_status\":200}]},"
        "\"variable_mappings\":[{\"from\":\"$.cart_id\",\"to\":\"request.path.cart_id\"}]}"
    )
    return _parse_generated_response(_call_llm_with_fallback(prompt), validate=False)


def _build_flow_prompt(
    endpoints: list,
    business_requirements: str | None,
    scenario_count: int | None = None,
) -> str:
    """
    Build the LLM prompt for flow test case generation.

    Args:
        endpoints (list): Ordered list of endpoint dicts.
        business_requirements (str | None): Optional business logic text.
        scenario_count (int | None): Deprecated compatibility argument; ignored.

    Returns:
        str: The prompt string.
    """
    endpoint_summaries = [
        _flow_endpoint_summary(endpoint, index)
        for index, endpoint in enumerate(endpoints, start=1)
    ]
    requirements_text = f"\nBusiness Requirements:\n{business_requirements}\n" if business_requirements else ""
    return (
        "You are an API test engineer. Propose a small set of distinct, useful executable flow "
        "scenarios for the ordered requests. Prefer complete valid JSON over many scenarios; cover "
        "positive, negative, and edge behavior when supported by the request context.\n"
        f"\nOrdered endpoint summaries:\n{json.dumps(endpoint_summaries, ensure_ascii=False, separators=(',', ':'))}\n"
        f"{requirements_text}"
        "Return ONLY a valid compact JSON array. Each item has id, type (positive/negative/edge/race), "
        "name, description, is_flow:true, and steps. Each step contains step_order, endpoint_id copied "
        "exactly from a summary, concise description, assertions, and variable_mappings. Use only "
        "provided endpoint IDs and preserve the supplied order. A mapping uses from as a response "
        "JSONPath and to as request.query.PARAM, request.path.PARAM, request.body.FIELD, or headers.NAME. "
        "Only add mappings and assertions grounded in the supplied request context. Keep descriptions "
        "short. Do not include endpoint objects, URLs, headers, cookies, or request bodies in output; "
        "the application restores canonical request data. Omit unnecessary optional fields.\n"
        "Example step: {\"step_order\":1,\"endpoint_id\":\"saved-id\",\"description\":\"List doctors\","
        "\"assertions\":{\"status\":[{\"enabled\":true,\"expected_status\":200}]},"
        "\"variable_mappings\":[]}\n"
    )

def _parse_generated_response(text: str, validate: bool = True) -> list:
    """
    Parse the LLM response into a list of test case dicts.

    Handles common non-JSON patterns LLMs produce (e.g. JavaScript .repeat(),
    template literals) by preprocessing before json.loads.

    Args:
        text (str): Raw LLM output (expected JSON array).
        validate (bool): Whether to validate test/flow response shape.

    Returns:
        list: Parsed dictionaries, optionally validated as test cases.
    """
    
    # Remove markdown code fences if present
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\n", "", cleaned)
        cleaned = re.sub(r"\n```$", "", cleaned)

    # Extract JSON array from response
    match = re.search(r"\[.*\]", cleaned, re.DOTALL)
    if match:
        text = match.group(0)

    # Preprocess: replace JavaScript .repeat(N) patterns with actual strings
    # e.g. "a".repeat(300) -> "aaa...a" (300 a's)
    def _replace_repeat(match):
        char = match.group(1).strip('"').strip("'")
        count = int(match.group(2))
        return '"' + char * min(count, 10000) + '"'

    text = re.sub(r'"([^"]+)"\.repeat\((\d+)\)', _replace_repeat, text)
    text = re.sub(r"'([^']+)'\.repeat\((\d+)\)", _replace_repeat, text)

    # Try direct JSON parse
    try:
        result = json.loads(text)
        if isinstance(result, list) and len(result) > 0:
            return _validate_generated_cases(result) if validate else result
    except json.JSONDecodeError:
        pass

    raise ValueError(
        "LLM response is malformed or truncated; the complete JSON array could not be parsed. "
        "Reduce endpoint or requirement complexity, or use a provider with a larger output limit."
    )
