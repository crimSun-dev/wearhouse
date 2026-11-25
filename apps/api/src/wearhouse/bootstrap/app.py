"""Application factory.

- `build_app(settings, services)` assembles routes/middleware only (no DB connection): used by OpenAPI export.
- `create_app(settings)` validates configuration, runs read-only startup checks against the database and
  composes production adapters. It never migrates or seeds. Test principals cannot be selected here.
"""
from __future__ import annotations

from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .. import __version__
from ..accounts import api as accounts_api
from ..catalogue import api as catalogue_api
from ..commerce import api as commerce_api
from ..recommendations import api as reco_api
from . import about as about_api
from . import ops as ops_api
from ..social import api as social_api
from ..wardrobe import api as wardrobe_api
from ..weather import api as weather_api
from ..ownership import api as ownership_api
from ..platform.db import make_engine
from ..platform.http import RateLimitMiddleware, RequestContextMiddleware, SlidingWindow, install_error_handlers, install_log_redaction
from .config import Settings
from .container import Services, build_services, build_verifier
from .startup import readiness, verify_database

API_PREFIX = "/api/v2"


def _health_router() -> APIRouter:
    r = APIRouter(tags=["health"])

    @r.get("/health", summary="Liveness (no secrets, no database details)")
    def health() -> dict:
        return {"status": "ok", "service": "wearhouse-api", "version": __version__}

    @r.get("/health/ready", summary="Readiness: environment marker, schema version and runtime role checks",
           responses={503: {"description": "Not ready"}})
    def ready(request: Request):
        state = request.app.state
        if state.engine is None:
            return JSONResponse({"status": "not_ready"}, status_code=503)
        res = readiness(state.engine, state.settings)
        body = {"status": "ready" if res.ok else "not_ready",
                "checks": {k: v for k, v in res.checks.items() if k != "error"}}
        return JSONResponse(body, status_code=200 if res.ok else 503)

    return r


def build_app(settings: Settings, services: Services | None = None, engine=None) -> FastAPI:
    app = FastAPI(
        title="Wearhouse API",
        version=__version__,
        description="Wearhouse v2: verified identity, source-backed products, serialized units and private "
                    "one-time redemption. Public tags are discovery-only. Errors use "
                    "{code, message, field_errors?, request_id}.",
        openapi_url=f"{API_PREFIX}/openapi.json",
        docs_url=f"{API_PREFIX}/docs",
        redoc_url=None,
    )
    app.state.settings = settings
    app.state.services = services
    app.state.engine = engine
    install_error_handlers(app)
    for router in (_health_router(), accounts_api.account_router, accounts_api.social_router,
                   accounts_api.profiles_router, accounts_api.staff_router, catalogue_api.router, catalogue_api.public_router, catalogue_api.me_router, commerce_api.admin_router, commerce_api.public_router,
                   commerce_api.me_router, wardrobe_api.public_router, wardrobe_api.router,
                   weather_api.router, social_api.me_router, social_api.public_router, social_api.admin_router, reco_api.public_router, reco_api.me_router, about_api.router, ops_api.router, ownership_api.public_router,
                   ownership_api.private_router, ownership_api.admin_router):
        app.include_router(router, prefix=API_PREFIX)
    # innermost of the edge stack: a 429 still gets CORS headers and a request id
    app.state.rate_limited = {}  # refusal counts for GET /admin/ops (per process)
    app.add_middleware(RateLimitMiddleware, ip_per_min=settings.rate_ip_per_min,
                       global_per_min=settings.rate_global_per_min, trusted_proxies=frozenset(settings.trusted_proxies),
                       counts=app.state.rate_limited)
    app.state.write_limiter = SlidingWindow(settings.rate_writes_per_min) if settings.rate_writes_per_min else None
    if settings.allowed_origins:
        app.add_middleware(CORSMiddleware, allow_origins=list(settings.allowed_origins),
                           allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
                           allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-Request-ID"],
                           expose_headers=["X-Request-ID", "Retry-After", "Idempotent-Replayed"])
    app.add_middleware(RequestContextMiddleware)
    return app


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = (settings or Settings.from_env()).validate()
    install_log_redaction()
    verifier = build_verifier(settings)  # rejects the test adapter before any database access
    engine = make_engine(settings.database_url)
    verify_database(engine, settings)
    services = build_services(settings, engine, verifier)
    return build_app(settings, services, engine)
