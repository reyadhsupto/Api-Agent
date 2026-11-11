"""
Generates AI-powered test cases from a parsed cURL.

Accepts:
    parsed_curl (dict): Parsed request components.
    business_requirements (str | None): Optional business rules.

Returns:
    list[dict]: Test cases with type, name, description, request, expected values.
"""

import ast
import os
import re
import json
import requests
from urllib.parse import parse_qsl, urlsplit, urlunsplit


_STRICT_JSON_INSTRUCTION = (
    "Output strict JSON using only JSON values. Never use JavaScript or other executable syntax, "
    "including .repeat(), string concatenation with +, template literals, comments, undefined, or NaN. "
    "Represent boundary inputs as ordinary quoted JSON strings or numbers; keep example values concise. "
    "For example, do not write `\"a\".repeat(255) + \"@example.com\"`; use a short literal such as `\"aaa@example.com\"`."
)


def _output_token_limit() -> int:
    """Read a shared configurable generation ceiling for supported providers."""
    try:
        return min(max(int(os.getenv("API_AGENT_LLM_MAX_OUTPUT_TOKENS", "6000")), 256), 16000)
    except ValueError:
        return 6000


def generate_test_cases(
    parsed_curl: dict | None = None,
    business_requirements: str | None = None,
    example_test_cases: list[dict] | None = None,
    endpoints: list[dict] | None = None,
    trace: dict | None = None,
) -> list:
    """
    Generate test cases using free-tier LLM providers with fallback.

    Args:
        parsed_curl (dict | None): One request, retained for older clients.
        business_requirements (str | None): Optional business logic text.
        example_test_cases (list[dict] | None): Existing cases used as generation examples.
        endpoints (list[dict] | None): Requests to cover in one generation action.

    Returns:
        list: Generated test case dictionaries.
    """
    prompt = _build_prompt(
        endpoints if endpoints is not None else (parsed_curl or {}),
        business_requirements,
        example_test_cases,
    )
    generated_text = _call_llm_with_fallback(prompt)
    if trace is not None:
        trace.update({"prompt": prompt, "llm_response": generated_text})
    print("llm response:", generated_text)
    cases, questions = _parse_generation_output(generated_text)
    if trace is not None:
        trace["clarification_questions"] = questions
    return cases


def generate_general_test_cases(
    business_requirements: str,
    trace: dict | None = None,
) -> list[dict]:
    """Generate human-readable scenarios that testers execute and mark manually."""
    prompt = (
        "Create general software test scenarios from the business requirements only. "
        "These are manual scenarios and must not contain HTTP requests, endpoints, assertions, "
        "response mappings, or executable API data. Each case needs name, type, description, "
        "and ordered manual_steps as an array of concise human-readable strings. "
        "Return a JSON object with test_cases and clarification_questions. Ask concise questions "
        "when requirements are ambiguous; otherwise use an empty clarification_questions array. "
        f"{_STRICT_JSON_INSTRUCTION}\nBusiness requirements:\n{business_requirements}"
    )
    raw = _call_llm_with_fallback(prompt)
    cases, questions = _parse_generation_output(raw, validate=False)
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("Each general scenario must be a JSON object.")
        steps = case.get("manual_steps") or case.get("steps")
        if not isinstance(steps, list) or not steps or any(not isinstance(step, str) or not step.strip() for step in steps):
            raise ValueError("Each general scenario needs one or more human-readable manual_steps.")
        case["manual_steps"] = [step.strip() for step in steps]
        case.pop("steps", None)
        case.pop("request", None)
        case.pop("assertions", None)
        case.pop("variable_mappings", None)
        case.pop("expected_status", None)
        case.pop("expected_body_contains", None)
        case.pop("is_flow", None)
        case["case_kind"] = "general"
    _validate_general_cases(cases)
    if trace is not None:
        trace.update({"prompt": prompt, "llm_response": raw, "clarification_questions": questions})
    return cases


def refine_generated_cases(
    cases: list[dict], answers: dict[str, str], trace: dict | None = None,
) -> list[dict]:
    """Create a new, refined output using user answers while preserving source output."""
    prompt = (
        "Refine the supplied test cases using the user's answers to the clarification questions. "
        "Return a complete refined case set in the same order. For each revised case, copy its input id into source_case_id; set source_case_id null for newly added cases. Preserve each original case kind and structure. "
        "Ask additional clarification_questions only if important ambiguity remains; otherwise return an empty array. "
        "For general cases, retain manual_steps and omit request/assertion/mapping data. For API cases, "
        "retain executable request or flow structure. Return JSON with test_cases and clarification_questions. "
        f"{_STRICT_JSON_INSTRUCTION}\nOriginal cases:\n{json.dumps(cases, ensure_ascii=False)}\n"
        f"Clarification answers:\n{json.dumps(answers, ensure_ascii=False)}"
    )
    raw = _call_llm_with_fallback(prompt)
    refined, questions = _parse_generation_output(raw, validate=False)
    for original, updated in zip(cases, refined):
        if isinstance(original, dict) and isinstance(updated, dict) and original.get("source_case_id"):
            updated.setdefault("source_case_id", original["source_case_id"])
    if any(item.get("case_kind") == "general" for item in cases if isinstance(item, dict)):
        for index, case in enumerate(refined):
            original = cases[index] if index < len(cases) else {}
            if original.get("case_kind") == "general" or case.get("case_kind") == "general" or "manual_steps" in case:
                case["case_kind"] = "general"
                case["manual_steps"] = case.get("manual_steps") or case.get("steps") or original.get("manual_steps", [])
                case.pop("steps", None)
                for key in ("request", "assertions", "variable_mappings", "expected_status", "expected_body_contains", "is_flow"):
                    case.pop(key, None)
        _validate_general_cases([item for item in refined if item.get("case_kind") == "general"])
    if trace is not None:
        trace.update({"prompt": prompt, "llm_response": raw, "clarification_questions": questions})
    return refined


def _validate_general_cases(cases: list[dict]) -> None:
    """Validate the manual-only shape used by requirements-based scenarios."""
    if not cases:
        raise ValueError("LLM response must contain at least one general test scenario.")
    for index, case in enumerate(cases, start=1):
        if not isinstance(case.get("name"), str) or not case["name"].strip():
            raise ValueError(f"General test case {index} needs a name.")
        for field in ("type", "description"):
            if not isinstance(case.get(field), str) or not case[field].strip():
                raise ValueError(f"General test case {index} needs a non-empty {field}.")
        steps = case.get("manual_steps")
        if not isinstance(steps, list) or not steps or any(not isinstance(item, str) or not item.strip() for item in steps):
            raise ValueError(f"General test case {index} needs ordered manual_steps.")


def _parse_generation_output(text: str, validate: bool = True) -> tuple[list, list[str]]:
    """Normalize an envelope or legacy array into test cases and questions."""
    parsed = _parse_generated_json(text)
    if isinstance(parsed, list):
        cases, questions = parsed, []
    elif isinstance(parsed, dict):
        cases = parsed.get("test_cases")
        questions = parsed.get("clarification_questions", [])
        if not isinstance(cases, list):
            raise ValueError("Generation response object must contain a test_cases array.")
        if not isinstance(questions, list) or any(not isinstance(item, str) for item in questions):
            raise ValueError("clarification_questions must be an array of strings.")
    else:
        raise ValueError("Generation response must be a JSON array or object envelope.")
    if validate:
        _validate_generated_cases(cases)
    return cases, [item.strip() for item in questions if item.strip()]


def generate_test_case_revision(
    baseline_cases: list[dict],
    endpoints: list[dict],
    previous_requirements: str,
    release_notes: str,
    trace: dict | None = None,
    prior_release_notes: str = "",
) -> list[dict]:
    """Generate a complete release suite from an immutable case baseline."""
    endpoint_context = [{
        "id": str(item.get("id", "")), "name": item.get("name", ""),
        "method": item.get("method", "GET"), "url": item.get("url", ""),
        "headers": item.get("headers", {}), "query_params": item.get("query_params", {}),
        "body": item.get("body"),
    } for item in endpoints]
    baseline_context = []
    for case in baseline_cases:
        clean = {key: case.get(key) for key in (
            "id", "name", "type", "description", "is_flow", "source_endpoint_id",
            "source_endpoint_name", "request", "steps", "manual_steps", "case_kind",
            "assertions", "business_requirements", "case_collection_id", "case_collection_name",
        ) if key in case}
        baseline_context.append(clean)
    prompt = (
        "You are revising a complete API test suite for a new software release. Return every baseline case, "
        "updated where the changed endpoints or release notes require it, and add useful cases for new behavior. "
        "Do not mutate or omit baseline cases merely to reduce output. For every retained/revised baseline case, "
        "copy its exact id into source_case_id. New cases must use source_case_id null. Assign unique temporary ids. "
        "Preserve general/manual cases as case_kind general with ordered human-readable manual_steps and no request, mapping, or assertion data. For each API single case, use a request object. For each API flow, use ordered steps with step_order, endpoint_id, "
        "endpoint, assertions, and variable_mappings. Use selected endpoints for updated behavior and preserve baseline "
        "endpoint definitions for unchanged requests not selected. Preserve useful assertions and mappings, update obsolete "
        "behavior, and include unchanged cases. Flow mappings transfer a prior response value directly into a later "
        "request only: `to` must be `headers.NAME`, `request.query.NAME`, `request.path.NAME`, `request.body`, or "
        "`request.body.FIELD` (nested body fields are allowed). Never use `vars.*`, temporary variables, or any other "
        "destination. The first flow step must have an empty `variable_mappings` list because it has no prior response. "
        "Omit a mapping if its value is not needed by a later request.\n"
        f"{_STRICT_JSON_INSTRUCTION}\n"
        f"Prior business requirements (read-only context):\n{previous_requirements or 'None recorded'}\n"
        f"Previous release notes (carry-forward context):\n{prior_release_notes or 'None recorded'}\n"
        f"New release notes (supplement prior requirements):\n{release_notes or 'None provided'}\n"
        f"Selected current endpoints (optional; this list may be empty):\n{json.dumps(endpoint_context, ensure_ascii=False, separators=(',', ':'))}\n"
        f"Baseline cases:\n{json.dumps(baseline_context, ensure_ascii=False, separators=(',', ':'))}\n"
        "Return a JSON object with test_cases and clarification_questions. Ask concise questions if important requirements remain ambiguous; otherwise questions is empty. Every case must contain id, source_case_id, name, type, description, "
        "case_kind and either an API request plus assertions, an API flow with is_flow true and ordered steps, or a general case with manual_steps and no API data. Flow step_order starts at 1 and is contiguous."
    )
    generated_text = _call_llm_with_fallback(prompt)
    if trace is not None:
        trace.update({"prompt": prompt, "llm_response": generated_text})
    cases, questions = _parse_generation_output(generated_text, validate=False)
    if trace is not None:
        trace["clarification_questions"] = questions
    baseline_by_id = {str(item.get("id")): item for item in baseline_cases}
    endpoint_catalog = {str(item.get("id")): item for item in endpoints if item.get("id") is not None}
    for baseline_case in baseline_cases:
        for step in baseline_case.get("steps", []) if isinstance(baseline_case.get("steps"), list) else []:
            endpoint = step.get("endpoint") if isinstance(step, dict) else None
            if isinstance(endpoint, dict) and endpoint.get("id") is not None:
                endpoint_catalog.setdefault(str(endpoint["id"]), endpoint)
            elif isinstance(step, dict) and step.get("endpoint_id") is not None and isinstance(endpoint, dict):
                endpoint_catalog.setdefault(str(step["endpoint_id"]), endpoint)
        source_endpoint_id = baseline_case.get("source_endpoint_id")
        request_data = baseline_case.get("request")
        if source_endpoint_id and isinstance(request_data, dict):
            endpoint_catalog.setdefault(str(source_endpoint_id), {
                **request_data,
                "id": str(source_endpoint_id),
                "name": baseline_case.get("source_endpoint_name", ""),
            })
    for case_index, case in enumerate(cases, start=1):
        original = baseline_by_id.get(str(case.get("source_case_id"))) if isinstance(case, dict) else None
        if original and original.get("case_kind") == "general":
            case["case_kind"] = "general"
            case["manual_steps"] = case.get("manual_steps") or case.get("steps") or original.get("manual_steps", [])
            case.pop("steps", None)
            for field in ("request", "assertions", "variable_mappings", "expected_status", "expected_body_contains", "is_flow"):
                case.pop(field, None)
            continue
        if not isinstance(case, dict) or not (case.get("is_flow") or isinstance(case.get("steps"), list)):
            continue
        for step_index, step in enumerate(case.get("steps", []), start=1):
            if not isinstance(step, dict):
                continue
            reference = str(step.get("endpoint_id", ""))
            endpoint = endpoint_catalog.get(reference)
            if endpoint is None and isinstance(step.get("endpoint"), dict):
                proposed = step["endpoint"]
                endpoint = next((item for item in endpoint_catalog.values()
                                 if str(item.get("method", "GET")).upper() == str(proposed.get("method", "GET")).upper()
                                 and item.get("url") == proposed.get("url")), None)
            if endpoint is None:
                raise ValueError(f"Revision flow {case_index}, step {step_index} references an unknown baseline or selected endpoint.")
            step["endpoint_id"] = str(endpoint.get("id", reference))
            step["endpoint"] = dict(endpoint)
    _validate_generated_cases(cases)
    return cases


def _validate_generated_cases(test_cases: list) -> list:
    """Validate parsed LLM cases and reject malformed output instead of fabricating cases."""
    if not isinstance(test_cases, list) or not test_cases:
        raise ValueError("LLM response must be a non-empty JSON array.")

    for index, test_case in enumerate(test_cases, start=1):
        if not isinstance(test_case, dict):
            raise ValueError(f"LLM test case {index} must be a JSON object.")
        if test_case.get("case_kind") == "general" or isinstance(test_case.get("manual_steps"), list):
            steps = test_case.get("manual_steps")
            if not isinstance(steps, list) or not steps or any(not isinstance(step, str) or not step.strip() for step in steps):
                raise ValueError(f"General test case {index} needs ordered human-readable manual_steps.")
            test_case["case_kind"] = "general"
            continue
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


def _example_case_summaries(test_cases: list[dict] | None) -> list[dict]:
    """Build compact request, scenario, and assertion context from chosen examples.

    Args:
        test_cases (list[dict] | None): Existing cases selected as generation examples.

    Returns:
        list[dict]: Prompt-safe summaries without execution results or auth headers.
    """
    summaries = []
    for case in test_cases or []:
        summary = {
            "type": case.get("type"),
            "name": case.get("name"),
            "description": case.get("description"),
            "assertions": case.get("assertions", {}),
        }
        if case.get("business_requirements"):
            summary["business_requirements"] = case["business_requirements"]
        if case.get("is_flow") or isinstance(case.get("steps"), list):
            summary["is_flow"] = True
            summary["steps"] = []
            for step in case.get("steps", []):
                endpoint = step.get("endpoint", {}) if isinstance(step, dict) else {}
                summary["steps"].append({
                    "method": endpoint.get("method"),
                    "url": endpoint.get("url"),
                    "description": step.get("description"),
                    "assertions": step.get("assertions", {}),
                    "variable_mappings": step.get("variable_mappings", []),
                })
        else:
            request = case.get("request", {}) or {}
            summary["request"] = {
                "method": request.get("method"),
                "url": request.get("url"),
                "query_params": request.get("query_params", {}),
                "body": request.get("body"),
            }
        summaries.append(summary)
    return summaries


def _build_prompt(
    parsed_curl: dict | list[dict],
    business_requirements: str | None,
    example_test_cases: list[dict] | None = None,
) -> str:
    """
    Build the LLM prompt for test case generation.

    Args:
        parsed_curl (dict | list[dict]): One request or a list of requests.
        business_requirements (str | None): Optional business logic text.
        example_test_cases (list[dict] | None): Existing cases used as examples.

    Returns:
        str: The prompt string.
    """
    endpoint_context = []
    for endpoint in parsed_curl if isinstance(parsed_curl, list) else [parsed_curl]:
        summary = {
            "method": endpoint.get("method", "GET"),
            "url": endpoint.get("url", ""),
            "headers": endpoint.get("headers", {}),
            "query_params": endpoint.get("query_params", {}),
            "body": endpoint.get("body"),
        }
        if endpoint.get("id") is not None:
            summary["source_endpoint_id"] = str(endpoint["id"])
        if endpoint.get("name"):
            summary["name"] = endpoint["name"]
        endpoint_context.append(summary)

    examples = _example_case_summaries(example_test_cases)
    examples_text = (
        "\nExisting test cases to use as examples of scenario style and coverage. "
        "Generate additional cases for the target request; do not copy or return these examples:\n"
        f"{json.dumps(examples, ensure_ascii=False, separators=(',', ':'))}\n"
        if examples else ""
    )

    return (
        "You are a senior software test engineer specializing in backend application testing. Generate independent single-request test cases "
        "for every endpoint in the supplied list. Cover positive, negative, edge, and race scenarios "
        "for each endpoint.\n"
        f"{_STRICT_JSON_INSTRUCTION}\n"
        "Generate at least 6 concise cases per endpoint, and do not omit any endpoint. When an "
        "endpoint has source_endpoint_id, copy that exact ID into every case for it. Keep the "
        "request method and URL aligned with the endpoint; vary request data only as needed by the scenario.\n"
        "1. Positive test: valid request, expect success (2xx)\n"
        "2. Negative test: invalid data, expect error (4xx)\n"
        "3. Negative test: missing required fields, expect error (4xx)\n"
        "4. Edge case: boundary values, empty strings, null values\n"
        "5. Edge case: maximum/minimum values, special characters\n"
        "6. Race condition: concurrent requests, consistency checks\n"
        "7. Any additional scenarios relevant to the endpoint\n"
        f"\nEndpoints:\n{json.dumps(endpoint_context, ensure_ascii=False, separators=(',', ':'))}\n"
        f"Business Requirements: {business_requirements or 'None provided'}\n"
        f"{examples_text}\n"
        "Return a JSON object with test_cases and clarification_questions. Ask concise questions for important ambiguity in requirements or endpoint behavior while still providing the best draft; otherwise use an empty questions array. Each test case has:\n"
        "- id: unique string like \"tc_1\"\n"
        "- source_endpoint_id: exact endpoint ID when one is supplied\n"
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
        str: Generated text from the first provider whose request succeeds.

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
                generated_text = _groq_call(prompt, api_key, url)
            elif name == "openrouter":
                generated_text = _openrouter_call(prompt, api_key, url)
            elif name == "cohere":
                generated_text = _cohere_call(prompt, api_key, url)
            elif name == "huggingface":
                generated_text = _huggingface_call(prompt, api_key, url)
            else:
                continue
            return generated_text
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
    # print("output token limit:", _output_token_limit())
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": _output_token_limit(),
    }
    response = requests.post(url, headers=headers, json=payload, timeout=600)
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
    example_test_cases: list[dict] | None = None,
    trace: dict | None = None,
) -> list:
    """
    Generate flow test cases for a sequence of endpoints.

    Each test case represents a step in the flow where data from a previous
    endpoint's response may be used in the next endpoint's request.

    Args:
        endpoints (list): Ordered list of endpoint dicts.
        business_requirements (str | None): Optional business logic text.
        scenario_count (int | None): Deprecated compatibility argument; ignored.
        example_test_cases (list[dict] | None): Existing cases used as generation examples.

    Returns:
        list: Generated flow test case dictionaries.
    """
    prompt = _build_flow_prompt(
        endpoints, business_requirements, example_test_cases=example_test_cases,
    )
    generated_text = _call_llm_with_fallback(prompt)
    if trace is not None:
        trace.update({"prompt": prompt, "llm_response": generated_text})
    cases, questions = _parse_generation_output(generated_text, validate=False)
    _attach_flow_endpoints(cases, endpoints)
    if trace is not None:
        trace["clarification_questions"] = questions
    return _validate_generated_cases(cases)


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


def _validate_flow_response(text: str, endpoints: list[dict]) -> list[dict]:
    """Parse and validate flow output, attaching canonical endpoint data."""
    cases = _parse_generated_response(text, validate=False)
    _attach_flow_endpoints(cases, endpoints)
    return _validate_generated_cases(cases)


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
            "contains no endpoint. "
            f"{_STRICT_JSON_INSTRUCTION} "
            "Each item must contain method, path, name, description, "
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
    trace: dict | None = None,
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
        "Use only the endpoint IDs and order supplied in each candidate. Return a JSON object with test_cases and clarification_questions; ask only questions needed to resolve important ambiguity. "
        f"{_STRICT_JSON_INSTRUCTION} "
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
    generated_text = _call_llm_with_fallback(prompt)
    if trace is not None:
        trace.update({"prompt": prompt, "llm_response": generated_text})
    cases, questions = _parse_generation_output(generated_text, validate=False)
    if trace is not None:
        trace["clarification_questions"] = questions
    return cases


def _build_flow_prompt(
    endpoints: list,
    business_requirements: str | None,
    scenario_count: int | None = None,
    example_test_cases: list[dict] | None = None,
) -> str:
    """
    Build the LLM prompt for flow test case generation.

    Args:
        endpoints (list): Ordered list of endpoint dicts.
        business_requirements (str | None): Optional business logic text.
        scenario_count (int | None): Deprecated compatibility argument; ignored.
        example_test_cases (list[dict] | None): Existing cases used as generation examples.

    Returns:
        str: The prompt string.
    """
    endpoint_summaries = [
        _flow_endpoint_summary(endpoint, index)
        for index, endpoint in enumerate(endpoints, start=1)
    ]
    requirements_text = f"\nBusiness Requirements:\n{business_requirements}\n" if business_requirements else ""
    examples = _example_case_summaries(example_test_cases)
    examples_text = (
        "\nExisting test cases to use as examples of scenario style, assertions, and mappings. "
        "Generate additional flows for the selected ordered endpoints; do not copy or return these examples:\n"
        f"{json.dumps(examples, ensure_ascii=False, separators=(',', ':'))}\n"
        if examples else ""
    )
    return (
        "You are a Senior SQA Engineer specializing in Backend application testing. Propose a set of distinct, useful executable flow "
        "scenarios for the ordered requests. Prefer complete valid JSON over many scenarios; cover "
        "positive, negative, race and edge behavior when supported by the request context.\n"
        f"{_STRICT_JSON_INSTRUCTION}\n"
        f"\nOrdered endpoint summaries:\n{json.dumps(endpoint_summaries, ensure_ascii=False, separators=(',', ':'))}\n"
        f"{requirements_text}{examples_text}"
        "Return a JSON object with test_cases and clarification_questions. Ask concise questions for important ambiguity in requirements or endpoint behavior; otherwise use an empty questions array. Each item has id, type (positive/negative/edge/race), "
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
    """Parse generated cases while accepting both envelope and legacy array output."""
    cases, _ = _parse_generation_output(text, validate=validate)
    return cases


def _parse_generated_json(text: str):
    """
    Parse the LLM response into its JSON array or standardized object envelope.

    Handles common non-JSON patterns LLMs produce (e.g. JavaScript .repeat(),
    template literals) by preprocessing before json.loads.

    Args:
        text (str): Raw LLM output (expected JSON array).
    Returns:
        Any: Parsed JSON response.
    """
    
    if not isinstance(text, str) or not text.strip():
        raise ValueError("LLM response was empty or did not contain text.")

    # Remove markdown code fences if present
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\n", "", cleaned)
        cleaned = re.sub(r"\n```$", "", cleaned)

    # Preserve an object envelope; older models may still return a bare array.
    if not cleaned.startswith("{"):
        match = re.search(r"\[.*\]", cleaned, re.DOTALL)
        if match:
            cleaned = match.group(0)

    # Normalize the limited JS string.repeat(N) expression sometimes emitted
    # for boundary examples, optionally followed by a literal string concat.
    string_literal = r'''(?:"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')'''
    repeat_expression = re.compile(
        rf'(?P<base>{string_literal})\.repeat\((?P<count>\d+)\)'
        rf'(?:\s*\+\s*(?P<suffix>{string_literal}))?'
    )

    def _decode_string_literal(literal):
        """Decode one quoted JSON or Python-style string literal safely."""
        return json.loads(literal) if literal.startswith('"') else ast.literal_eval(literal)

    def _replace_repeat(match):
        try:
            base = _decode_string_literal(match.group("base"))
            suffix_literal = match.group("suffix")
            suffix = _decode_string_literal(suffix_literal) if suffix_literal else ""
        except (ValueError, SyntaxError) as exc:
            raise ValueError("LLM response contains an unsupported JavaScript string expression.") from exc
        if not isinstance(base, str) or not isinstance(suffix, str):
            raise ValueError("LLM response contains a non-string .repeat() expression.")
        repeated = base * min(int(match.group("count")), 10000)
        return json.dumps(repeated + suffix, ensure_ascii=False)

    cleaned = repeat_expression.sub(_replace_repeat, cleaned)

    # Try direct JSON parse
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    raise ValueError(
        "LLM response is malformed or truncated; the complete JSON array could not be parsed. "
        "Reduce endpoint or requirement complexity, or use a provider with a larger output limit."
    )
