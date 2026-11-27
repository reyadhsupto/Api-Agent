"""Unit tests for the single-account JWT helpers."""

from app import auth


def test_access_tokens_are_signed_for_the_configured_account(monkeypatch):
    """Valid credentials authenticate while altered claims and signatures fail."""
    monkeypatch.setenv("AUTH_USERNAME", "local-user")
    monkeypatch.setenv("AUTH_PASSWORD", "local-password")
    monkeypatch.setenv("AUTH_JWT_SECRET", "a-test-secret-with-more-than-thirty-two-characters")

    token, expiry = auth.create_access_token("local-user")
    assert auth.validate_access_token(token) == "local-user"
    assert auth.validate_access_token(token + "x") is None
    assert auth.verify_credentials("local-user", "local-password")
    assert not auth.verify_credentials("local-user", "wrong-password")
    assert expiry > 0


def test_auth_configuration_fails_closed(monkeypatch):
    """Absent credentials or a short signing secret are rejected."""
    monkeypatch.delenv("AUTH_USERNAME", raising=False)
    monkeypatch.delenv("AUTH_PASSWORD", raising=False)
    monkeypatch.delenv("AUTH_JWT_SECRET", raising=False)
    try:
        auth.configured_credentials()
    except RuntimeError as error:
        assert "AUTH_USERNAME" in str(error)
    else:
        raise AssertionError("Authentication must require explicit local credentials.")
