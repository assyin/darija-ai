from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

import sentry_sdk
import structlog
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sentry_sdk.integrations.fastapi import FastApiIntegration

from app.api.deps import public_rate_limit
from app.api.v1.ai_logs import router as ai_logs_admin_router
from app.api.v1.articles import admin_router as articles_admin_router
from app.api.v1.articles import public_router as articles_public_router
from app.api.v1.auth import router as auth_router
from app.api.v1.ere import router as ere_admin_router
from app.api.v1.health_dashboard import router as health_admin_router
from app.api.v1.settings import admin_router as settings_admin_router
from app.api.v1.settings import router as settings_router
from app.core.config import Settings, get_settings
from app.core.db import check_db_health
from app.core.exceptions import AppError
from app.core.logging import configure_logging, get_logger
from app.core.redis import check_redis_health


def _check_prod_secrets(settings: Settings) -> None:
    if not settings.is_prod:
        return
    if settings.admin_jwt_secret == "dev-only-change-me":  # noqa: S105
        raise RuntimeError("Set ADMIN_JWT_SECRET to a strong random value in production")
    if settings.admin_password.get_secret_value() == "changeme-in-prod":
        raise RuntimeError("Set ADMIN_PASSWORD to a strong value in production")


def _init_sentry(settings: Settings) -> None:
    if not settings.sentry_dsn:
        return
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        integrations=[FastApiIntegration()],
        traces_sample_rate=0.1 if settings.is_prod else 1.0,
        send_default_pii=False,
        release=f"{settings.app_name}@{settings.app_version}",
        environment=settings.environment,
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging()
    _init_sentry(settings)
    _check_prod_secrets(settings)
    logger = get_logger("app.lifespan")
    logger.info(
        "app.starting",
        environment=settings.environment,
        version=settings.app_version,
    )
    yield
    logger.info("app.shutting_down")


def create_app() -> FastAPI:
    settings = get_settings()

    docs_url = None if settings.is_prod else "/docs"
    redoc_url = None if settings.is_prod else "/redoc"
    openapi_url = None if settings.is_prod else "/openapi.json"

    app = FastAPI(
        title="DarijaAI Backend",
        version=settings.app_version,
        lifespan=lifespan,
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_context_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[JSONResponse]],
    ) -> JSONResponse:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        logger = get_logger("app.error")
        logger.warning(
            "app.error",
            error_code=exc.error_code,
            message=exc.message,
            details=exc.details,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.error_code,
                    "message": exc.message,
                    "request_id": getattr(request.state, "request_id", None),
                    "details": exc.details,
                }
            },
        )

    @app.get("/health")
    async def health() -> dict[str, object]:
        db_ok = await check_db_health()
        redis_ok = await check_redis_health()
        all_ok = db_ok and redis_ok
        return {
            "status": "ok" if all_ok else "degraded",
            "version": settings.app_version,
            "environment": settings.environment,
            "checks": {
                "database": "ok" if db_ok else "error",
                "redis": "ok" if redis_ok else "error",
            },
        }

    @app.get("/")
    async def root() -> dict[str, str]:
        return {
            "name": settings.app_name,
            "version": settings.app_version,
            "docs": "/docs",
        }

    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(settings_router, prefix="/api/v1", dependencies=[Depends(public_rate_limit)])
    app.include_router(settings_admin_router, prefix="/api/v1")
    app.include_router(articles_admin_router, prefix="/api/v1")
    app.include_router(ai_logs_admin_router, prefix="/api/v1")
    app.include_router(ere_admin_router, prefix="/api/v1")
    app.include_router(health_admin_router, prefix="/api/v1")
    app.include_router(
        articles_public_router,
        prefix="/api/v1",
        dependencies=[Depends(public_rate_limit)],
    )

    return app


app = create_app()
