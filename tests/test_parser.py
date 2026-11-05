"""
Unit tests for the cURL parser.

Accepts:
    None.

Returns:
    None (test assertions).
"""

from app.parser import parse_curl


def test_parse_simple_get_curl() -> None:
    """
    Test parsing a simple GET cURL command.

    Returns:
        None
    """
    curl = "curl https://api.example.com/users"
    result = parse_curl(curl)
    assert result["method"] == "GET"
    assert result["url"] == "https://api.example.com/users"
    assert result["headers"] == {}


def test_parse_post_with_header_and_body() -> None:
    """
    Test parsing a POST cURL with header and JSON body.

    Returns:
        None
    """
    curl = "curl -X POST https://api.example.com/users -H 'Content-Type: application/json' -d '{\"name\":\"test\"}'"
    result = parse_curl(curl)
    assert result["method"] == "POST"
    assert result["url"] == "https://api.example.com/users"
    assert result["headers"]["Content-Type"] == "application/json"
    assert '{"name":"test"}' in result["body"]


def test_parse_curl_get_data_auth_and_query():
    """Common Postman-style cURL options map to request fields."""
    result = parse_curl(
        "curl -G --data-urlencode 'q=two words' --user 'api:secret' "
        "'https://api.example.test/search?active=true'"
    )

    assert result["method"] == "GET"
    assert result["url"] == "https://api.example.test/search"
    assert result["query_params"] == {"active": "true", "q": "two words"}
    assert result["headers"]["Authorization"].startswith("Basic ")
