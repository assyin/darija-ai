from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest
from fastapi.security import HTTPAuthorizationCredentials
from jose import jwt

from app.core.exceptions import UnauthorizedError
from app.core.security import create_access_token, require_admin

TEST_SECRET = "unit-test-jwt-secret-key-at-least-32-chars"
TEST_ALGORITHM = "HS256"
TEST_EXPIRY = 3600
TEST_EMAIL = "admin@test.darija-ai.ma"


def _mock_settings() -> MagicMock:
    s = MagicMock()
    s.admin_jwt_secret = TEST_SECRET
    s.admin_jwt_algorithm = TEST_ALGORITHM
    s.admin_jwt_expiry_seconds = TEST_EXPIRY
    return s


def _creds(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


@pytest.fixture(autouse=True)
def patch_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.core.security.get_settings", _mock_settings)


def test_create_access_token_payload_is_correct() -> None:
    token = create_access_token(TEST_EMAIL)
    payload = jwt.decode(token, TEST_SECRET, algorithms=[TEST_ALGORITHM])
    assert payload["sub"] == TEST_EMAIL
    assert "exp" in payload
    assert "iat" in payload


def test_create_access_token_expiry_is_respected() -> None:
    token = create_access_token(TEST_EMAIL)
    payload = jwt.decode(token, TEST_SECRET, algorithms=[TEST_ALGORITHM])
    delta = payload["exp"] - payload["iat"]
    assert delta == TEST_EXPIRY


def test_require_admin_valid_token_returns_admin_user() -> None:
    token = create_access_token(TEST_EMAIL)
    user = require_admin(_creds(token))
    assert user.email == TEST_EMAIL


def test_require_admin_no_credentials_raises_unauthorized() -> None:
    with pytest.raises(UnauthorizedError, match="Authentication required"):
        require_admin(None)


def test_require_admin_expired_token_raises_unauthorized() -> None:
    payload = {
        "sub": TEST_EMAIL,
        "iat": datetime.now(UTC) - timedelta(seconds=7200),
        "exp": datetime.now(UTC) - timedelta(seconds=1),
    }
    token = jwt.encode(payload, TEST_SECRET, algorithm=TEST_ALGORITHM)
    with pytest.raises(UnauthorizedError, match="Authentication required"):
        require_admin(_creds(token))


def test_require_admin_tampered_signature_raises_unauthorized() -> None:
    token = create_access_token(TEST_EMAIL)
    tampered = token[:-6] + "XXXXXX"
    with pytest.raises(UnauthorizedError, match="Authentication required"):
        require_admin(_creds(tampered))


def test_require_admin_wrong_secret_raises_unauthorized() -> None:
    payload = {
        "sub": TEST_EMAIL,
        "exp": datetime.now(UTC) + timedelta(hours=1),
    }
    token = jwt.encode(payload, "completely-different-secret-key-xxxx", algorithm=TEST_ALGORITHM)
    with pytest.raises(UnauthorizedError, match="Authentication required"):
        require_admin(_creds(token))


def test_require_admin_missing_sub_raises_unauthorized() -> None:
    payload = {"exp": datetime.now(UTC) + timedelta(hours=1)}
    token = jwt.encode(payload, TEST_SECRET, algorithm=TEST_ALGORITHM)
    with pytest.raises(UnauthorizedError, match="Authentication required"):
        require_admin(_creds(token))
