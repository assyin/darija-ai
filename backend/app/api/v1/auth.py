from __future__ import annotations

import secrets

from fastapi import APIRouter, Request

from app.core.config import get_settings
from app.core.exceptions import UnauthorizedError
from app.core.logging import get_logger
from app.core.rate_limit import check_rate_limit
from app.core.redis import get_redis_client
from app.core.security import create_access_token
from app.schemas.auth import AdminLoginRequest, TokenResponse

logger = get_logger("api.v1.auth")

router = APIRouter(prefix="/auth", tags=["auth"])


def _extract_ip(request: Request) -> str:
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


@router.post("/token", response_model=TokenResponse)
async def login(request: Request, body: AdminLoginRequest) -> TokenResponse:
    settings = get_settings()
    await check_rate_limit(
        get_redis_client(),
        f"auth:login:{_extract_ip(request)}",
        settings.auth_login_rate_limit_max_requests,
        settings.auth_login_rate_limit_window_seconds,
    )
    email_ok = secrets.compare_digest(body.email, settings.admin_email)
    password_ok = secrets.compare_digest(
        body.password,
        settings.admin_password.get_secret_value(),
    )
    if not (email_ok and password_ok):
        raise UnauthorizedError("Authentication required")

    token = create_access_token(settings.admin_email)
    logger.info("admin.login.success")
    return TokenResponse(
        access_token=token,
        token_type="bearer",  # noqa: S106
        expires_in=settings.admin_jwt_expiry_seconds,
    )
