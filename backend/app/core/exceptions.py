from __future__ import annotations


class AppError(Exception):
    status_code: int = 500
    error_code: str = "INTERNAL_ERROR"
    message: str = "An unexpected error occurred"

    def __init__(
        self,
        message: str | None = None,
        *,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message or self.message)
        self.message = message or self.message
        self.details = details or {}


class NotFoundError(AppError):
    status_code = 404
    error_code = "NOT_FOUND"
    message = "Resource not found"


class ValidationError(AppError):
    status_code = 422
    error_code = "VALIDATION_ERROR"
    message = "Invalid input"


class UnauthorizedError(AppError):
    status_code = 401
    error_code = "UNAUTHORIZED"
    message = "Authentication required"


class ForbiddenError(AppError):
    status_code = 403
    error_code = "FORBIDDEN"
    message = "Access denied"


class ConflictError(AppError):
    status_code = 409
    error_code = "CONFLICT"
    message = "Resource conflict"


class RateLimitError(AppError):
    status_code = 429
    error_code = "RATE_LIMITED"
    message = "Too many requests"


class ExternalServiceError(AppError):
    status_code = 502
    error_code = "EXTERNAL_SERVICE_ERROR"
    message = "An external service failed"


class AIQualityError(AppError):
    status_code = 422
    error_code = "AI_QUALITY_FAILED"
    message = "AI output did not meet quality standards"
