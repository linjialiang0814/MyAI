from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping


class ErrorCategory(str, Enum):
    VALIDATION = "validation"
    AUTHORIZATION = "authorization"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    DEPENDENCY = "dependency"
    CANCELLED = "cancelled"
    INTERNAL = "internal"


class ErrorCode(str, Enum):
    INVALID_ARGUMENT = "invalid_argument"
    FORBIDDEN = "forbidden"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    OPERATION_TIMEOUT = "operation_timeout"
    RATE_LIMITED = "rate_limited"
    DEPENDENCY_UNAVAILABLE = "dependency_unavailable"
    CIRCUIT_OPEN = "circuit_open"
    CANCELLED = "cancelled"
    TOOL_EXECUTION_FAILED = "tool_execution_failed"
    INTERNAL_ERROR = "internal_error"


_DEFAULT_CATEGORIES: dict[ErrorCode, ErrorCategory] = {
    ErrorCode.INVALID_ARGUMENT: ErrorCategory.VALIDATION,
    ErrorCode.FORBIDDEN: ErrorCategory.AUTHORIZATION,
    ErrorCode.NOT_FOUND: ErrorCategory.NOT_FOUND,
    ErrorCode.CONFLICT: ErrorCategory.CONFLICT,
    ErrorCode.IDEMPOTENCY_CONFLICT: ErrorCategory.CONFLICT,
    ErrorCode.OPERATION_TIMEOUT: ErrorCategory.TIMEOUT,
    ErrorCode.RATE_LIMITED: ErrorCategory.RATE_LIMIT,
    ErrorCode.DEPENDENCY_UNAVAILABLE: ErrorCategory.DEPENDENCY,
    ErrorCode.CIRCUIT_OPEN: ErrorCategory.DEPENDENCY,
    ErrorCode.CANCELLED: ErrorCategory.CANCELLED,
    ErrorCode.TOOL_EXECUTION_FAILED: ErrorCategory.INTERNAL,
    ErrorCode.INTERNAL_ERROR: ErrorCategory.INTERNAL,
}

_HTTP_STATUS_BY_CODE: dict[ErrorCode, int] = {
    ErrorCode.INVALID_ARGUMENT: 400,
    ErrorCode.FORBIDDEN: 403,
    ErrorCode.NOT_FOUND: 404,
    ErrorCode.CONFLICT: 409,
    ErrorCode.IDEMPOTENCY_CONFLICT: 409,
    ErrorCode.CANCELLED: 409,
    ErrorCode.RATE_LIMITED: 429,
    ErrorCode.DEPENDENCY_UNAVAILABLE: 503,
    ErrorCode.CIRCUIT_OPEN: 503,
    ErrorCode.OPERATION_TIMEOUT: 504,
    ErrorCode.TOOL_EXECUTION_FAILED: 500,
    ErrorCode.INTERNAL_ERROR: 500,
}


@dataclass(frozen=True)
class ErrorInfo:
    """Stable, serializable error data shared by APIs, runs, and tools."""

    code: ErrorCode
    message: str
    retryable: bool = False
    category: ErrorCategory | None = None
    operation: str | None = None
    dependency: str | None = None
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not str(self.message).strip():
            raise ValueError("error message cannot be blank")
        if self.category is None:
            object.__setattr__(self, "category", _DEFAULT_CATEGORIES[self.code])

    @property
    def http_status(self) -> int:
        return _HTTP_STATUS_BY_CODE[self.code]

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "code": self.code.value,
            "category": self.category.value if self.category else ErrorCategory.INTERNAL.value,
            "message": self.message,
            "retryable": self.retryable,
            "http_status": self.http_status,
        }
        if self.operation:
            payload["operation"] = self.operation
        if self.dependency:
            payload["dependency"] = self.dependency
        if self.details:
            payload["details"] = dict(self.details)
        return payload


class AppError(Exception):
    """Exception carrying a safe public error and an optional private cause."""

    def __init__(self, info: ErrorInfo, *, cause: BaseException | None = None):
        super().__init__(info.message)
        self.info = info
        self.cause = cause


def classify_exception(
    exc: BaseException,
    *,
    operation: str | None = None,
    dependency: str | None = None,
) -> ErrorInfo:
    if isinstance(exc, AppError):
        return exc.info
    exception_name = type(exc).__name__
    if exception_name == "IdempotencyConflictError":
        return ErrorInfo(
            code=ErrorCode.IDEMPOTENCY_CONFLICT,
            message="The idempotency key is already bound to a different request.",
            operation=operation,
            dependency=dependency,
        )
    if exception_name == "IdempotencyInProgressError":
        return ErrorInfo(
            code=ErrorCode.CONFLICT,
            message="An equivalent request is already in progress.",
            retryable=True,
            operation=operation,
            dependency=dependency,
        )
    if exception_name == "RunLinkMismatchError":
        return ErrorInfo(
            code=ErrorCode.CONFLICT,
            message="The run ownership or conversation link is inconsistent.",
            operation=operation,
            dependency=dependency,
        )
    if isinstance(exc, TimeoutError):
        return ErrorInfo(
            code=ErrorCode.OPERATION_TIMEOUT,
            message="The operation timed out.",
            retryable=True,
            operation=operation,
            dependency=dependency,
        )
    if isinstance(exc, PermissionError):
        return ErrorInfo(
            code=ErrorCode.FORBIDDEN,
            message="The operation is not permitted.",
            operation=operation,
            dependency=dependency,
        )
    if isinstance(exc, FileNotFoundError):
        return ErrorInfo(
            code=ErrorCode.NOT_FOUND,
            message="The requested resource was not found.",
            operation=operation,
            dependency=dependency,
        )
    if isinstance(exc, ValueError):
        return ErrorInfo(
            code=ErrorCode.INVALID_ARGUMENT,
            # ValueError messages can embed the rejected input (including tokens
            # and local paths). Public boundaries should construct AppError when
            # they intentionally want to expose a specific validation message.
            message="The request contains an invalid value.",
            operation=operation,
            dependency=dependency,
        )
    if isinstance(exc, (ConnectionError, OSError)):
        return ErrorInfo(
            code=ErrorCode.DEPENDENCY_UNAVAILABLE,
            message="A required dependency is unavailable.",
            retryable=True,
            operation=operation,
            dependency=dependency,
        )
    status_code = getattr(exc, "status_code", None)
    if status_code == 429:
        return ErrorInfo(
            code=ErrorCode.RATE_LIMITED,
            message="The dependency rate limit was reached.",
            retryable=True,
            operation=operation,
            dependency=dependency,
        )
    if isinstance(status_code, int) and 500 <= status_code <= 599:
        return ErrorInfo(
            code=ErrorCode.DEPENDENCY_UNAVAILABLE,
            message="A required dependency is unavailable.",
            retryable=True,
            operation=operation,
            dependency=dependency,
        )
    legacy = error_info_from_message(
        str(exc),
        operation=operation,
        dependency=dependency,
    )
    if legacy.retryable:
        return legacy
    return ErrorInfo(
        code=ErrorCode.INTERNAL_ERROR,
        message="The operation failed unexpectedly.",
        operation=operation,
        dependency=dependency,
    )


def error_info_from_message(
    message: str,
    *,
    operation: str | None = None,
    dependency: str | None = None,
) -> ErrorInfo:
    """Classify legacy string failures while callers migrate to typed errors."""

    normalized = str(message or "").strip().lower()
    if "rate limit" in normalized or "429" in normalized:
        code, public_message, retryable = ErrorCode.RATE_LIMITED, "The dependency rate limit was reached.", True
    elif "timeout" in normalized or "timed out" in normalized:
        code, public_message, retryable = ErrorCode.OPERATION_TIMEOUT, "The operation timed out.", True
    elif "circuit" in normalized and "open" in normalized:
        code, public_message, retryable = ErrorCode.CIRCUIT_OPEN, "The dependency circuit is open.", True
    elif any(token in normalized for token in ("connection", "network", "temporarily", "502", "503", "504")):
        code, public_message, retryable = (
            ErrorCode.DEPENDENCY_UNAVAILABLE,
            "A required dependency is unavailable.",
            True,
        )
    elif any(token in normalized for token in ("permission", "forbidden", "requires confirmation", "not permitted")):
        code, public_message, retryable = ErrorCode.FORBIDDEN, "The operation is not permitted.", False
    elif "not found" in normalized:
        code, public_message, retryable = ErrorCode.NOT_FOUND, "The requested resource was not found.", False
    elif any(token in normalized for token in ("invalid", "validation", "unsupported", "required")):
        code, public_message, retryable = ErrorCode.INVALID_ARGUMENT, "The request is invalid.", False
    else:
        code, public_message, retryable = ErrorCode.TOOL_EXECUTION_FAILED, "Tool execution failed.", False
    return ErrorInfo(
        code=code,
        message=public_message,
        retryable=retryable,
        operation=operation,
        dependency=dependency,
    )
