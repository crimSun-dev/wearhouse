"""FastAPI application factory: wires DB (I3), Weather Gateway (I2), interface log, routers.

    uvicorn app.main:app --reload        (from legacy/python/)
"""
from __future__ import annotations

import os
import re
import time
from datetime import datetime
from pathlib import Path

import anyio
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from .config import REPO_DIR, Settings
from .db import assert_legacy_target, init_db, make_engine, make_sessionmaker
from .models import InterfaceLog
from .routers import admin, registration, wardrobe, weather
from .seeding import has_garments, seed
from .services import DomainError
from .weather import (
    BMKG_URL,
    BMKGClient,
    FaultInjectingClient,
    FaultState,
    HttpBMKGClient,
    MockBMKGClient,
    WeatherGateway,
    _rebase_payload,
    utcnow,
)

STATIC_DIR = Path(__file__).resolve().parent / "static"
GS1_PATH = re.compile(r"^/01/\d{14}/21/[0-9A-Za-z]+$")
UNLOGGED = {"/api/v1/metrics/interface-log"}


class InterfaceLogMiddleware:
    """Writes one interface_log row per API call: interface id, route, status, latency, weather source.
    I5 = QR scans, I6 = measure.py traffic (header X-Interface: I6), everything else on /api = I1."""

    def __init__(self, app, writer):
        self.app = app
        self.writer = writer

    async def __call__(self, scope, receive, send):
        path = scope.get("path", "")
        if scope["type"] != "http" or path in UNLOGGED or not (path.startswith("/api/") or GS1_PATH.match(path)):
            await self.app(scope, receive, send)
            return
        scope["dw_log"] = {}
        status = {"code": 500}

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status["code"] = message["status"]
            await send(message)

        t0 = time.perf_counter()
        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            latency = (time.perf_counter() - t0) * 1000
            headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
            if headers.get("x-interface", "").upper() == "I6":
                iface = "I6"
            elif "/scan/" in path or path == "/api/v1/garments/scan" or GS1_PATH.match(path):
                iface = "I5"
            else:
                iface = "I1"
            extra = scope.get("dw_log", {})
            row = dict(interface=iface, route=f"{scope['method']} {path}", status=status["code"], latency_ms=latency,
                       weather_source=extra.get("weather_source"), note=extra.get("note"))
            await anyio.to_thread.run_sync(self.writer, row)


def build_weather_client(settings: Settings, fault: FaultState, clock, base: BMKGClient | None = None) -> BMKGClient:
    """mock → frozen real sample (re-dated); live → api.bmkg.go.id; `base` overrides both (measure.py).
    Always wrapped by the fault injector so the I6 fault switch works in every mode."""
    mock = MockBMKGClient(settings.fixture_path, clock)
    if base is None:
        base = mock if settings.weather_mode == "mock" else HttpBMKGClient()
    return FaultInjectingClient(base, fault, healthy_payload=lambda: _rebase_payload(mock.payload, clock()))


def create_app(settings: Settings | None = None, bmkg_base: BMKGClient | None = None, clock=utcnow) -> FastAPI:
    settings = settings or Settings.from_env()
    engine = make_engine(settings.database_url)
    assert_legacy_target(engine, destructive=False)  # refuse a Wearhouse v2 database before any write
    init_db(engine)
    SessionLocal = make_sessionmaker(engine)
    if settings.auto_seed:
        with SessionLocal() as s:
            if not has_garments(s):
                seed(s)

    def write_log(row: dict) -> None:
        try:
            with Session(engine) as s:
                s.add(InterfaceLog(**row))
                s.commit()
        except Exception:  # the log must never take the API down
            pass

    if bmkg_base is not None:
        i2_route = f"GET {type(bmkg_base).__name__}"
    elif settings.weather_mode == "mock":
        i2_route = "GET mock-bmkg (frozen real sample)"
    else:
        i2_route = f"GET {BMKG_URL}"

    def log_i2(adm4: str, status: int | None, latency_ms: float, note: str) -> None:
        write_log(dict(interface="I2", route=f"{i2_route}?adm4={adm4}", status=status, latency_ms=latency_ms,
                       weather_source=None, note=note))

    fault = FaultState()
    client = build_weather_client(settings, fault, clock, bmkg_base)
    gateway = WeatherGateway(client, ttl_s=settings.cache_ttl_s, stale_max_s=settings.cache_stale_max_s,
                             timeout_s=settings.bmkg_timeout_s, clock=clock, on_call=log_i2)

    app = FastAPI(
        title="Digital Wardrobe Live Demo API",
        version="0.1.0",
        description="INFS4305 System Integration demo: wardrobe + BMKG weather gateway + garment registration. "
                    "Interfaces I1–I6 per the TDD. Writes need the X-API-Key header.",
    )
    app.state.settings = settings
    app.state.engine = engine
    app.state.Session = SessionLocal
    app.state.fault = fault
    app.state.gateway = gateway
    app.state.started_at = datetime.now()

    @app.exception_handler(DomainError)
    async def _domain_error(request: Request, exc: DomainError):
        return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})

    app.include_router(wardrobe.router, prefix="/api/v1")
    app.include_router(weather.router, prefix="/api/v1")
    app.include_router(registration.router, prefix="/api/v1")
    app.include_router(admin.router, prefix="/api/v1")
    app.include_router(registration.gs1_router)

    @app.get("/config.js", include_in_schema=False)
    def frontend_config():
        return FileResponse(STATIC_DIR / "config.js", media_type="application/javascript")

    frontend_dist = Path(os.environ.get("LEGACY_WEB_DIST") or REPO_DIR / "legacy" / "web" / "dist")
    if frontend_dist.is_dir():
        app.mount("/LIVE-DEMO", StaticFiles(directory=frontend_dist, html=True), name="pages-frontend")
        app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
    else:
        @app.get("/", include_in_schema=False)
        def index():
            return FileResponse(STATIC_DIR / "index.html")

    app.add_middleware(InterfaceLogMiddleware, writer=write_log)
    if settings.cors_origins:
        app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins), allow_methods=["*"],
                           allow_headers=["*"])
    return app


def _lazy_app() -> FastAPI:  # pragma: no cover - used by `uvicorn app.main:app`
    return create_app()


def __getattr__(name):  # pragma: no cover
    if name == "app":
        global app
        app = _lazy_app()
        return app
    raise AttributeError(name)
