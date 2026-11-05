"""Tests for generated test-case parsing and validation."""

import pytest

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


def test_flow_prompt_uses_requested_scenario_count():
    """The generated instructions use the caller's configurable scenario count."""
    prompt = _build_flow_prompt([], None, scenario_count=12)

    assert "Generate exactly 12 flow scenarios" in prompt


def test_parser_rejects_truncated_response_instead_of_partial_cases():
    """Incomplete JSON must produce an error instead of silently returning a subset."""
    with pytest.raises(ValueError, match="malformed or truncated"):
        _parse_generated_response('[{"id":"flow_1","type":"positive"}')
