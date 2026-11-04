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
        ("groq", os.getenv("GROQ_API_KEY"), "https://api.groq.com/openai/v1/chat/completions"),
        ("openrouter", os.getenv("OPENROUTER_API_KEY"), "https://openrouter.ai/api/v1/chat/completions"),
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
    payload = {"model": "command-r", "prompt": prompt, "temperature": 0.3}
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
    payload = {"inputs": prompt, "parameters": {"max_new_tokens": 2000, "temperature": 0.3}}
    response = requests.post(url, headers=headers, json=payload, timeout=30)
    response.raise_for_status()
    return response.json()[0]["generated_text"]


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
            return result
    except json.JSONDecodeError:
        pass

    # Fallback: try to parse individual test case objects from the array
    # Find objects that start with { and contain "type" key
    try:
        # Use a more robust approach: find balanced-brace objects
        objects = _extract_json_objects(text)
        if objects:
            parsed = []
            for obj_str in objects:
                try:
                    # Preprocess each object too
                    obj_str = re.sub(
                        r'"([^"]+)"\.repeat\((\d+)\)', _replace_repeat, obj_str
                    )
                    obj = json.loads(obj_str)
                    if isinstance(obj, dict) and "type" in obj:
                        parsed.append(obj)
                except json.JSONDecodeError:
                    continue
            if parsed:
                return parsed
    except Exception:
        pass

    # Last resort fallback: generate 4 basic test cases
    return [
        {
            "id": "tc_1",
            "type": "positive",
            "name": "Valid request test",
            "description": "Test with valid request data expecting success.",
            "request": {},
            "expected_status": 200,
        },
        {
            "id": "tc_2",
            "type": "negative",
            "name": "Invalid data test",
            "description": "Test with invalid data expecting client error.",
            "request": {},
            "expected_status": 400,
        },
        {
            "id": "tc_3",
            "type": "negative",
            "name": "Missing required fields test",
            "description": "Test with missing required fields expecting error.",
            "request": {},
            "expected_status": 400,
        },
        {
            "id": "tc_4",
            "type": "edge",
            "name": "Boundary values test",
            "description": "Test with boundary/edge case values.",
            "request": {},
            "expected_status": 400,
        },
    ]


def _extract_json_objects(text: str) -> list:
    """
    Extract balanced-brace JSON objects from text.

    Handles nested objects (e.g. request inside test case) by tracking
    brace depth rather than using a naive regex.

    Args:
        text (str): Text containing JSON objects.

    Returns:
        list: List of JSON object strings found.
    """
    objects = []
    depth = 0
    start = -1
    in_string = False
    escape = False

    for i, ch in enumerate(text):
        if escape:
            escape = False
            continue
        if ch == "\\" and in_string:
            escape = True
            continue
        if ch == '"' and not escape:
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start >= 0:
                objects.append(text[start : i + 1])
                start = -1

    return objects
