from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.core.config import get_settings
from app.core.exceptions import UnauthorizedError
from app.schemas.auth import AdminUser

# auto_error=False so we control the response shape (401, not 403).
_bearer = HTTPBearer(auto_error=False)


def create_access_token(email: str) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": email,
        "iat": now,
        "exp": now + timedelta(seconds=settings.admin_jwt_expiry_seconds),
    }
    return jwt.encode(
        payload,
        settings.admin_jwt_secret,
        algorithm=settings.admin_jwt_algorithm,
    )


def require_admin(
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer),
) -> AdminUser:
    if credentials is None:
        raise UnauthorizedError("Authentication required")
    settings = get_settings()
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.admin_jwt_secret,
            algorithms=[settings.admin_jwt_algorithm],
        )
    except JWTError:
        raise UnauthorizedError("Authentication required")

    sub: str | None = payload.get("sub")
    if not sub:
        raise UnauthorizedError("Authentication required")

    return AdminUser(email=sub)
