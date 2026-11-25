"""HTTP edge: request ids, consistent error bodies, private no-store headers and secret-free logging.

Nothing here logs request bodies, query strings, headers or exception messages that may carry
parameters. The redaction filter is defence in depth, not the primary control.
"""
from __future__ import annotations

import logging
import math
import re
import time
import uuid
from collections import deque

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import InterfaceError, OperationalError
from starlette.exceptions import HTTPException as StarletteHTTPException

from .context import request_id_var
from .errors import ApiError

access_log = logging.getLogger("wearhouse.access")
error_log = logging.getLogger("wearhouse.error")

REQUEST_ID_HEADER = "X-Request-ID"
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9_\-]{8,64}$")
PRIVATE_PREFIXES = ("/api/v2/me", "/api/v2/admin", "/api/v2/redemptions", "/api/v2/profiles",
                    "/api/v2/users")
NO_STORE = {"Cache-Control": "no-store", "Pragma": "no-cache"}


def is_private_path(path: str) -> bool:
    """Whole path segments only: /api/v2/me and /api/v2/me/... are private, /api/v2/media is not."""
    return any(path == p or path.startswith(p + "/") for p in PRIVATE_PREFIXES)

_REDACTIONS = [
    (re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/=\-]+"), "Bearer [REDACTED]"),
    (re.compile(r"eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]*"), "[REDACTED-JWT]"),
    (re.compile(r"\b[A-Za-z2-7]{4}-?[A-Za-z2-7]{4}-?[A-Za-z2-7]{4}-?[A-Za-z2-7]{4}\b"), "[REDACTED-KEY]"),
    (re.compile(r"\b[0-9a-f]{64}\b"), "[REDACTED-DIGEST]"),
]


def redact(text: str) -> str:
    for pattern, repl in _REDACTIONS:
        text = pattern.sub(repl, text)
    return text


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:  # noqa: BLE001
            return True
        cleaned = redact(message)
        if cleaned != message:  # only rewrite records that carried something sensitive; formatters such as
            record.msg, record.args = cleaned, None  # uvicorn's access log still need their original args
        if record.exc_info and record.exc_info[1] is not None:
            record.exc_text = None  # tracebacks re-render without bound parameters (hide_parameters=True)
        return True


def install_log_redaction() -> None:
    f = RedactingFilter()
    for name in ("", "uvicorn", "uvicorn.error", "uvicorn.access", "wearhouse"):
        lg = logging.getLogger(name)
        for h in lg.handlers:
            if not any(isinstance(x, RedactingFilter) for x in h.filters):
                h.addFilter(f)


def error_body(code: str, message: str, field_errors: list | None = None) -> dict:
    body = {"code": code, "message": message, "request_id": request_id_var.get()}
    if field_errors:
        body["field_errors"] = field_errors
    return body


class RequestContextMiddleware:
    """Assigns a request id, enforces no-store on private routes and writes a secret-free access log."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        incoming = None
        for k, v in scope.get("headers", []):
            if k == b"x-request-id":
                incoming = v.decode("latin-1")
        rid = incoming if incoming and _SAFE_REQUEST_ID.fullmatch(incoming) else uuid.uuid4().hex
        token = request_id_var.set(rid)
        path = scope.get("path", "")
        private = is_private_path(path)
        status = {"code": 500}
        t0 = time.perf_counter()

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status["code"] = message["status"]
                headers = [(k, v) for k, v in message.get("headers", [])
                           if not (private and k.lower() in (b"cache-control", b"pragma"))]
                headers.append((b"x-request-id", rid.encode()))
                if private:
                    headers += [(k.lower().encode(), v.encode()) for k, v in NO_STORE.items()]
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            access_log.info("%s %s %s %.1fms rid=%s", scope.get("method"), path, status["code"],
                            (time.perf_counter() - t0) * 1000, rid)
            request_id_var.reset(token)


def _field_errors_from_validation(exc: RequestValidationError) -> list[dict]:
    out = []
    for e in exc.errors():
        loc = ".".join(str(p) for p in e.get("loc", ()))
        out.append({"field": loc, "code": e.get("type", "invalid"), "message": e.get("msg", "Invalid value.")})
    return out  # never includes e["input"] or e["ctx"]: they may hold credentials


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(request: Request, exc: ApiError):
        fe = [{"field": f.field, "code": f.code, "message": f.message} for f in exc.field_errors]
        return JSONResponse(error_body(exc.code, exc.message, fe), status_code=exc.status, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError):
        return JSONResponse(error_body("VALIDATION_FAILED", "The request is invalid.",
                                       _field_errors_from_validation(exc)), status_code=422)

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException):
        codes = {404: ("NOT_FOUND", "Resource not found."), 405: ("METHOD_NOT_ALLOWED", "Method not allowed.")}
        code, message = codes.get(exc.status_code, ("HTTP_ERROR", "Request failed."))
        return JSONResponse(error_body(code, message), status_code=exc.status_code)

    @app.exception_handler(OperationalError)
    @app.exception_handler(InterfaceError)
    async def _db_unavailable(request: Request, exc: Exception):
        error_log.error("database unavailable (%s)", type(exc).__name__)
        return JSONResponse(error_body("SERVICE_UNAVAILABLE", "The service is temporarily unavailable."),
                            status_code=503, headers={"Retry-After": "5"})

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        error_log.error("unhandled %s on %s %s", type(exc).__name__, request.method, request.url.path)
        return JSONResponse(error_body("INTERNAL_ERROR", "An unexpected error occurred."), status_code=500)


# ------------------------------------------------------------------ edge rate limits (harden-wearhouse-services-api)
class SlidingWindow:
    """Per-key sliding window of request timestamps (per process). Returns seconds to wait when over the limit."""

    def __init__(self, limit: int, window_s: float = 60.0, clock=time.monotonic):
        self.limit, self.window, self.clock = limit, window_s, clock
        self.hits: dict[str, "deque[float]"] = {}
        self.calls = 0

    def hit(self, key: str) -> float | None:
        now = self.clock()
        dq = self.hits.get(key)
        if dq is None:
            dq = self.hits[key] = deque()
        while dq and dq[0] <= now - self.window:
            dq.popleft()
        self.calls += 1
        if self.calls % 10_000 == 0:  # bound memory: drop idle keys
            for k in [k for k, v in self.hits.items() if not v or v[-1] <= now - self.window]:
                self.hits.pop(k, None)
        if len(dq) >= self.limit:
            return dq[0] + self.window - now
        dq.append(now)
        return None


EXEMPT_SUFFIXES = ("/health", "/health/ready")


def _client_ip(scope, trusted: frozenset[str]) -> str:
    peer = (scope.get("client") or ("unknown", 0))[0]
    if peer in trusted:
        xff = ""
        for k, v in scope.get("headers", []):
            if k == b"x-forwarded-for":
                xff = v.decode("latin-1")
        for hop in reversed([p.strip() for p in xff.split(",") if p.strip()]):
            if hop not in trusted:
                return hop
    return peer


class RateLimitMiddleware:
    """Edge layers of the limits (pool SYSTEM_DESIGN RULE-033 / TRAP-018): requests per client IP and process-wide.
    The per-user write layer runs after authentication (identity.api.current_principal). 0 disables a layer."""

    def __init__(self, app, *, ip_per_min: int, global_per_min: int, trusted_proxies: frozenset[str] = frozenset(),
                 clock=time.monotonic, counts: dict | None = None):
        self.app = app
        self.ip = SlidingWindow(ip_per_min, clock=clock) if ip_per_min else None
        self.global_ = SlidingWindow(global_per_min, clock=clock) if global_per_min else None
        self.trusted = trusted_proxies
        self.counts: dict[str, int] = counts if counts is not None else {}

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("method") == "OPTIONS" or scope.get("path", "").endswith(EXEMPT_SUFFIXES):
            return await self.app(scope, receive, send)
        retry = self.global_.hit("global") if self.global_ else None
        if retry is None and self.ip:
            retry = self.ip.hit("ip:" + _client_ip(scope, self.trusted))
        if retry is None:
            return await self.app(scope, receive, send)
        wait = max(1, math.ceil(retry))
        counts = self.counts
        counts["edge"] = counts.get("edge", 0) + 1
        response = JSONResponse(error_body("RATE_LIMITED", "Too many requests. Try again shortly."), status_code=429,
                                headers={"Retry-After": str(wait)})
        await response(scope, receive, send)
