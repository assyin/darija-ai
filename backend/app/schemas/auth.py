from __future__ import annotations

from pydantic import BaseModel


class AdminUser(BaseModel):
    email: str


class AdminLoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
