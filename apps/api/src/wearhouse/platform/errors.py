"""Transport-neutral error types. The HTTP layer maps them to `{code, message, field_errors?, request_id}`."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class FieldError:
    field: str
    code: str
    message: str


@dataclass
class ApiError(Exception):
    status: int
    code: str
    message: str
    field_errors: list[FieldError] = field(default_factory=list)
    headers: dict[str, str] = field(default_factory=dict)

    def __str__(self) -> str:  # never include input values
        return f"{self.status} {self.code}"


def unauthenticated(message: str = "A valid bearer access token is required.") -> ApiError:
    return ApiError(401, "UNAUTHENTICATED", message, headers={"WWW-Authenticate": 'Bearer realm="wearhouse"'})


def forbidden(message: str = "This account does not have the required capability.") -> ApiError:
    return ApiError(403, "FORBIDDEN", message)


def not_found(message: str = "Resource not found.") -> ApiError:
    return ApiError(404, "NOT_FOUND", message)


def conflict(code: str, message: str) -> ApiError:
    return ApiError(409, code, message)


def validation_failed(errors: list[FieldError], message: str = "The request is invalid.") -> ApiError:
    return ApiError(422, "VALIDATION_FAILED", message, field_errors=errors)


def rate_limited(retry_after_s: int, message: str = "Too many activation attempts. Try again later.") -> ApiError:
    return ApiError(429, "RATE_LIMITED", message,
                    headers={"Retry-After": str(max(1, int(retry_after_s)))})


def unavailable(message: str = "The service is temporarily unavailable.", retry_after_s: int = 5) -> ApiError:
    return ApiError(503, "SERVICE_UNAVAILABLE", message, headers={"Retry-After": str(retry_after_s)})
