"""Per-request context (request id) shared by HTTP middleware, audit and logging."""
from __future__ import annotations

from contextvars import ContextVar

request_id_var: ContextVar[str | None] = ContextVar("wearhouse_request_id", default=None)


def current_request_id() -> str | None:
    return request_id_var.get()
