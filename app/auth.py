"""Small single-account JWT and rotating refresh-token helpers."""

import base64
import hashlib
import hmac
import json
import os
import secrets
import time


ACCESS_TTL_SECONDS = 15 * 60
REFRESH_TTL_SECONDS = 30 * 24 * 60 * 60


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def configured_credentials() -> tuple[str, str, bytes]:
    """Read the single-account credentials and signing secret or fail closed."""
    username = os.getenv("AUTH_USERNAME", "").strip()
    password = os.getenv("AUTH_PASSWORD", "")
    secret = os.getenv("AUTH_JWT_SECRET", "")
    if not username or not password or len(secret) < 32:
        raise RuntimeError(
            "Configure AUTH_USERNAME, AUTH_PASSWORD, and an AUTH_JWT_SECRET of at least 32 characters."
        )
    return username, password, secret.encode("utf-8")


def verify_credentials(username: str, password: str) -> bool:
    """Compare submitted credentials to the locally configured account."""
    expected_user, expected_password, _ = configured_credentials()
    return hmac.compare_digest(username.encode(), expected_user.encode()) and hmac.compare_digest(
        password.encode(), expected_password.encode()
    )


def create_access_token(username: str) -> tuple[str, int]:
    """Create a signed HS256 JWT and return its expiration timestamp."""
    _, _, secret = configured_credentials()
    now = int(time.time())
    header = _encode(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _encode(json.dumps({"sub": username, "iat": now, "exp": now + ACCESS_TTL_SECONDS}, separators=(",", ":")).encode())
    signing_input = f"{header}.{payload}".encode()
    signature = _encode(hmac.new(secret, signing_input, hashlib.sha256).digest())
    return f"{header}.{payload}.{signature}", now + ACCESS_TTL_SECONDS


def validate_access_token(token: str) -> str | None:
    """Verify signature and expiry, returning the account name when valid."""
    try:
        expected_username, _, secret = configured_credentials()
        header, payload, signature = token.split(".")
        header_data = json.loads(_decode(header))
        if not isinstance(header_data, dict) or header_data.get("alg") != "HS256":
            return None
        expected = _encode(hmac.new(secret, f"{header}.{payload}".encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            return None
        decoded = json.loads(_decode(payload))
        if not isinstance(decoded, dict):
            return None
        now = int(time.time())
        if (
            int(decoded.get("exp", 0)) <= now
            or int(decoded.get("iat", now + 1)) > now
            or not hmac.compare_digest(str(decoded.get("sub") or ""), expected_username)
        ):
            return None
        return str(decoded.get("sub") or "") or None
    except (RuntimeError, ValueError, TypeError, AttributeError, json.JSONDecodeError):
        return None


def new_refresh_token() -> str:
    """Create an opaque, high-entropy refresh token."""
    return secrets.token_urlsafe(48)


def refresh_token_hash(token: str) -> str:
    """Hash a refresh token for storage so raw credentials are never persisted."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def refresh_expiry() -> int:
    """Return the refresh-token expiry as a Unix timestamp."""
    return int(time.time()) + REFRESH_TTL_SECONDS
