"""Typed application errors. The API layer maps these to HTTP responses."""
from __future__ import annotations


class AppError(Exception):
    status_code = 500
    code = "internal_error"

    def __init__(self, message: str = "") -> None:
        super().__init__(message or self.code)
        self.message = message or self.code


class ConfigurationError(AppError):
    code = "configuration_error"


class Unauthorized(AppError):
    status_code = 401
    code = "unauthorized"


class Forbidden(AppError):
    status_code = 403
    code = "forbidden"


class NotFound(AppError):
    status_code = 404
    code = "not_found"


class Conflict(AppError):
    status_code = 409
    code = "conflict"


class ExternalServiceError(AppError):
    status_code = 502
    code = "external_service_error"


class ToolExecutionError(AppError):
    status_code = 502
    code = "tool_execution_error"


class NotAvailableError(AppError):
    """Raised by placeholders for integrations that do not exist yet."""

    status_code = 501
    code = "not_available"
