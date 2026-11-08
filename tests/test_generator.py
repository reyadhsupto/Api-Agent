"""Tests for generated test-case parsing and validation."""

import pytest

from app import generator
from app.generator import _build_flow_prompt, _parse_generated_response


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
    monkeypatch.setattr(generator, "_call_llm_with_fallback", lambda prompt: compact_response)

    result = generator.generate_flow_test_cases([endpoint])

    assert result[0]["steps"][0]["endpoint_id"] == "saved-doctors"
    assert result[0]["steps"][0]["endpoint"] == endpoint


def test_parser_rejects_truncated_response_instead_of_partial_cases():
    """Incomplete JSON must produce an error instead of silently returning a subset."""
    with pytest.raises(ValueError, match="malformed or truncated"):
        _parse_generated_response('[{"id":"flow_1","type":"positive"}')
