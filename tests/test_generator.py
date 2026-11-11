"""Tests for generated test-case parsing and validation."""

import pytest

from app import generator
from app.generator import (
    _build_flow_prompt, _parse_generated_response, _parse_generation_output,
    generate_general_test_cases, generate_test_case_revision,
)


def test_generation_envelope_retains_questions_and_legacy_arrays_default_empty():
    """Normalize the shared response envelope and preserve array compatibility."""
    envelope = '{"test_cases":[{"id":"case-1","name":"A"}],"clarification_questions":["Which account?"]}'
    cases, questions = _parse_generation_output(envelope, validate=False)
    assert cases[0]["id"] == "case-1"
    assert questions == ["Which account?"]
    assert _parse_generation_output('[{"id":"case-2"}]', validate=False) == ([{"id": "case-2"}], [])


def test_general_generation_produces_manual_only_scenarios(monkeypatch):
    """Requirements-only output uses manual steps and exposes model questions."""
    captured = {}
    response = '{"test_cases":[{"id":"tmp","name":"Password reset","type":"positive",' \
        '"description":"Verify reset","manual_steps":["Request reset","Use the emailed link"]}],' \
        '"clarification_questions":["Should links expire?"]}'

    def fake_call(prompt):
        captured["prompt"] = prompt
        return response

    monkeypatch.setattr(generator, "_call_llm_with_fallback", fake_call)
    trace = {}
    cases = generate_general_test_cases("Users can reset forgotten passwords.", trace)

    assert cases[0]["case_kind"] == "general"
    assert cases[0]["manual_steps"] == ["Request reset", "Use the emailed link"]
    assert not {"request", "assertions", "variable_mappings"} & cases[0].keys()
    assert trace["clarification_questions"] == ["Should links expire?"]
    assert "business requirements only" in captured["prompt"]


def test_revision_prompt_separates_old_requirements_from_release_notes(monkeypatch):
    """Revision generation sends baseline, old requirements, and release notes in one prompt."""
    captured = {}
    response = '[{"id":"tmp","source_case_id":"old-case","name":"Updated",' \
        '"type":"positive","request":{"method":"GET","url":"/v2"}}]'

    def fake_call(prompt):
        captured["prompt"] = prompt
        return response

    monkeypatch.setattr(generator, "_call_llm_with_fallback", fake_call)
    cases = generate_test_case_revision(
        [{"id": "old-case", "name": "Old", "request": {"url": "/v1"}}],
        [{"id": "endpoint-v2", "method": "GET", "url": "/v2"}],
        "Existing business rules", "Release changes", {},
    )

    assert cases[0]["source_case_id"] == "old-case"
    assert "Prior business requirements (read-only context):\nExisting business rules" in captured["prompt"]
    assert "New release notes (supplement prior requirements):\nRelease changes" in captured["prompt"]


def test_parser_rejects_malformed_flow_instead_of_returning_fallback():
    """A flow step without an endpoint must produce an explicit error."""
    response = '[{"id":"flow_1","is_flow":true,"steps":[{"step_order":1}]}]'

    with pytest.raises(ValueError, match="missing endpoint.url"):
        _parse_generated_response(response)


def test_parser_accepts_valid_flow():
    """Valid flow JSON remains available to the application."""
    response = (
        '[{"id":"flow_1","is_flow":true,"steps":['
        '{"step_order":1,"endpoint":{"url":"https://example.test"}}]}]'
    )

    result = _parse_generated_response(response)

    assert result[0]["id"] == "flow_1"


def test_parser_rejects_non_sequential_step_order():
    """Flow steps must use consecutive one-based step_order values."""
    response = (
        '[{"id":"flow_1","is_flow":true,"steps":['
        '{"step_order":2,"endpoint":{"url":"https://example.test"}}]}]'
    )

    with pytest.raises(ValueError, match="expected 1"):
        _parse_generated_response(response)


def test_flow_prompt_uses_compact_endpoint_context_without_headers_or_cookies():
    """Flow prompts avoid duplicating sensitive, verbose request headers."""
    endpoint = {
        "id": "saved-doctors", "method": "GET",
        "url": "https://example.test/doctors?api_key=query-secret",
        "headers": {"Cookie": "device_id=secret", "User-Agent": "long browser string"},
        "query_params": {"date": "today"},
        "body": {"username": "reyad", "password": "body-secret"},
    }
    prompt = _build_flow_prompt([endpoint], None)

    assert '"endpoint_id":"saved-doctors"' in prompt
    assert "query_parameter_names" in prompt
    assert "device_id=secret" not in prompt
    assert "long browser string" not in prompt
    assert "query-secret" not in prompt
    assert "body-secret" not in prompt
    assert "password" in prompt and "<string>" in prompt


def test_generation_prompts_use_examples_as_context_without_copying_results():
    """Single and flow prompts include selected examples but omit execution data."""
    example = {
        "name": "Rejects missing token", "type": "negative",
        "description": "Checks unauthenticated access", "request": {
            "method": "GET", "url": "https://example.test/profile",
            "headers": {"Authorization": "Bearer secret"},
            "body": None,
        },
        "assertions": {"status": [{"enabled": True, "expected_status": 401}]},
        "execution": {"response_body": "private response"},
    }

    single_prompt = generator._build_prompt(
        {"method": "GET", "url": "https://example.test/profile"},
        "Require authentication", [example],
    )
    flow_prompt = _build_flow_prompt(
        [{"id": "profile", "method": "GET", "url": "https://example.test/profile"}],
        "Require authentication", example_test_cases=[example],
    )

    for prompt in (single_prompt, flow_prompt):
        assert "Rejects missing token" in prompt
        assert "401" in prompt
        assert "Generate additional" in prompt
        assert "Bearer secret" not in prompt
        assert "private response" not in prompt


def test_flow_generation_restores_full_endpoint_after_compact_llm_output(monkeypatch):
    """Compact endpoint references are hydrated with canonical saved request data."""
    endpoint = {
        "id": "saved-doctors", "method": "GET", "url": "https://example.test/doctors",
        "headers": {"Cookie": "device_id=secret"}, "query_params": {"date": "today"},
        "body": None,
    }
    compact_response = (
        '[{"id":"flow_1","is_flow":true,"steps":[{"step_order":1,'
        '"endpoint_id":"saved-doctors","description":"List doctors",'
        '"assertions":{"status":[{"enabled":true,"expected_status":200}]},'
        '"variable_mappings":[]}]}]'
    )
    prompt_calls = []

    def generate(prompt):
        prompt_calls.append(prompt)
        return compact_response

    monkeypatch.setattr(generator, "_call_llm_with_fallback", generate)

    result = generator.generate_flow_test_cases(
        [endpoint], example_test_cases=[{"name": "Example checkout", "type": "positive"}],
    )

    assert result[0]["steps"][0]["endpoint_id"] == "saved-doctors"
    assert result[0]["steps"][0]["endpoint"] == endpoint
    assert "Example checkout" in prompt_calls[0]


def test_parser_rejects_truncated_response_instead_of_partial_cases():
    """Incomplete JSON must produce an error instead of silently returning a subset."""
    with pytest.raises(ValueError, match="malformed or truncated"):
        _parse_generated_response('[{"id":"flow_1","type":"positive"}')
