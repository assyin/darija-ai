from __future__ import annotations

import secrets

from fastapi import APIRouter

from app.core.config import get_settings
from app.core.exceptions import UnauthorizedError
from app.core.logging import get_logger
from app.core.security import create_access_token
from app.schemas.auth import AdminLoginRequest, TokenResponse

logger = get_logger("api.v1.auth")

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/token", response_model=TokenResponse)
async def login(body: AdminLoginRequest) -> TokenResponse:
    settings = get_settings()
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
        token_type="bearer",
        expires_in=settings.admin_jwt_expiry_seconds,
    )
