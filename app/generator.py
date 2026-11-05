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
    return _parse_generated_response(generated_text)


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
    endpoints_text = ""
    for i, ep in enumerate(endpoints):
        endpoints_text += (
            f"Step {i + 1}: {ep.get('method', 'GET')} {ep.get('url', '')}\n"
            f"  Headers: {ep.get('headers', {})}\n"
            f"  Body: {ep.get('body')}\n"
        )

    if business_requirements:
        endpoints_text += f"\nBusiness Requirements: {business_requirements}\n"

    return (
        "You are a Senior API test engineer(SQA). Generate COMPREHENSIVE flow test scenarios "
        "for the following API sequence where each step may depend on the previous step's "
        "response data.\n"
        "Generate as many useful, distinct flow scenarios as you can while staying within your output limit. "
        "Prioritize complete, valid scenarios over an incomplete final scenario. Cover these flow types when relevant:\n"
        "1. Positive flow: all steps succeed in sequence\n"
        "2. Negative flow: one step fails, verify error handling\n"
        "3. Edge flow: boundary/null values propagated between steps\n"
        "4. Race condition flow: concurrent access patterns\n"
        f"\nEndpoints in sequence:\n{endpoints_text}\n"
        "Return ONLY a valid JSON array (no markdown, no explanation) where each item has:\n"
        "- id: unique string like \"flow_1\"\n"
        "- type: one of \"positive\", \"negative\", \"edge\", \"race\"\n"
        "- name: descriptive flow test name\n"
        "- description: what this flow test validates\n"
        "- is_flow: true\n"
        "- steps: array of step objects, each with:\n"
        "  - step_order: integer (1-based)\n"
        "  - endpoint_id: reference to endpoint position (1-based index into endpoints array)\n"
        "  - endpoint: the full endpoint dict (method, url, headers, body)\n"
        "  - assertions: {\n"
        "      status: {enabled: bool, expected_status: int},\n"
        "      body_contains: {enabled: bool, value: string},\n"
        "      jsonpath: {enabled: bool, path: string, expected_value: string}\n"
        "    }\n"
        "  - variable_mappings: array of mappings from previous response to this request:\n"
        "    - {from: \"response.body.field\", to: \"headers.Authorization\",\n"
        "      transform: \"Bearer {value}\", description: \"Pass auth token to next request\"}\n"
        "  - description: what this step does\n"
        "IMPORTANT: For variable_mappings, 'from' references a JSONPath in the previous step's "
        "response (e.g., \"$.token\", \"$.user.id\"). 'to' specifies where to inject it "
        "(e.g., \"headers.Authorization\", \"request.body.userId\"). 'transform' is optional "
        "and can format the value (e.g., \"Bearer {value}\").\n"
    )

def _parse_generated_response(text: str) -> list:
    """
    Parse the LLM response into a list of test case dicts.

    Handles common non-JSON patterns LLMs produce (e.g. JavaScript .repeat(),
    template literals) by preprocessing before json.loads.

    Args:
        text (str): Raw LLM output (expected JSON array).

    Returns:
        list: List of test case dictionaries.
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
            return _validate_generated_cases(result)
    except json.JSONDecodeError:
        pass

    raise ValueError(
        "LLM response is malformed or truncated; the complete JSON array could not be parsed. "
        "Reduce endpoint or requirement complexity, or use a provider with a larger output limit."
    )
