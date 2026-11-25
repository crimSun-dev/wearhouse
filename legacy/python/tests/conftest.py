"""Shared fixtures. Integration tests run on SQLite always, and also on PostgreSQL
when TEST_POSTGRES_URL is set (CI sets it; locally point it at a throwaway database)."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.db import assert_legacy_target, make_engine, register_legacy_environment
from app.main import create_app
from app.models import Base

API_KEY = "test-key"
PG_URL = os.environ.get("TEST_POSTGRES_URL")
DB_PARAMS = ["sqlite"] + (["postgres"] if PG_URL else [])
FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "bmkg_real_sample.json"


class Clock:
    """Controllable UTC clock for cache-age tests."""

    def __init__(self, now: datetime | None = None):
        self.now = now or datetime(2026, 11, 24, 5, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kw):
        from datetime import timedelta

        self.now += timedelta(**kw)


def _fresh_pg(url: str) -> str:
    engine = make_engine(url)
    register_legacy_environment(engine)  # throwaway test DB, explicitly registered as legacy
    assert_legacy_target(engine, destructive=True)
    Base.metadata.drop_all(engine)
    engine.dispose()
    return url


@pytest.fixture(params=DB_PARAMS)
def db_url(request, tmp_path) -> str:
    if request.param == "sqlite":
        return "sqlite:///" + (tmp_path / "test.db").as_posix()
    return _fresh_pg(PG_URL)


@pytest.fixture
def settings(db_url) -> Settings:
    return Settings(database_url=db_url, weather_mode="mock", api_key=API_KEY, auto_seed=True)


@pytest.fixture
def app(settings):
    application = create_app(settings)
    yield application
    application.state.engine.dispose()


@pytest.fixture
def client(app):
    with TestClient(app, headers={"X-API-Key": API_KEY}) as c:
        yield c


@pytest.fixture
def anon_client(app):
    with TestClient(app) as c:
        yield c
