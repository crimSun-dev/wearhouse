"""Legacy v1 refuses Wearhouse v2 databases (and unregistered remote targets for destructive use)."""
from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, inspect, text

import measure
import seed
from app.config import Settings
from app.db import LegacyTargetError, assert_legacy_target, make_engine, register_legacy_environment
from app.main import create_app


def _v2_marked_sqlite(tmp_path):
    url = "sqlite:///" + (tmp_path / "looks_like_v2.db").as_posix()
    eng = create_engine(url)
    with eng.begin() as c:
        c.execute(text("CREATE TABLE wearhouse_environment (id INTEGER PRIMARY KEY, app_family TEXT)"))
        c.execute(text("CREATE TABLE owned_item (id TEXT PRIMARY KEY)"))
        c.execute(text("INSERT INTO owned_item VALUES ('claimed-item')"))
    eng.dispose()
    return url


def _tables(url):
    eng = create_engine(url)
    try:
        return set(inspect(eng).get_table_names())
    finally:
        eng.dispose()


def test_startup_refuses_v2_database_before_writing(tmp_path):
    url = _v2_marked_sqlite(tmp_path)
    with pytest.raises(LegacyTargetError, match="Wearhouse v2"):
        create_app(Settings(database_url=url, weather_mode="mock"))
    assert _tables(url) == {"wearhouse_environment", "owned_item"}  # init_db never ran


def test_seed_reset_refuses_v2_database(tmp_path, monkeypatch):
    url = _v2_marked_sqlite(tmp_path)
    monkeypatch.setenv("DATABASE_URL", url)
    with pytest.raises(LegacyTargetError):
        seed.main(["--reset"])
    assert _tables(url) == {"wearhouse_environment", "owned_item"}


def test_measure_refuses_v2_database(tmp_path):
    url = _v2_marked_sqlite(tmp_path)
    with pytest.raises(LegacyTargetError):
        measure.run_measurement(db_url=url, runs=2, cold_runs=1)
    eng = create_engine(url)
    with eng.connect() as c:
        assert c.execute(text("SELECT count(*) FROM owned_item")).scalar() == 1
    eng.dispose()


def test_local_sqlite_is_allowed_and_registered_by_seed(tmp_path, monkeypatch):
    url = "sqlite:///" + (tmp_path / "demo.db").as_posix()
    monkeypatch.setenv("DATABASE_URL", url)
    assert seed.main([]) == 0
    assert "dw_legacy_environment" in _tables(url)


@pytest.mark.skipif(not os.environ.get("TEST_POSTGRES_URL"), reason="needs TEST_POSTGRES_URL (throwaway DB)")
def test_unregistered_remote_database_refuses_destructive_use():
    eng = make_engine(os.environ["TEST_POSTGRES_URL"])
    with eng.begin() as c:
        c.execute(text("DROP TABLE IF EXISTS dw_legacy_environment"))
    try:
        assert_legacy_target(eng, destructive=False)  # plain startup is fine
        with pytest.raises(LegacyTargetError, match="register-legacy-environment"):
            assert_legacy_target(eng, destructive=True)
        register_legacy_environment(eng)
        assert_legacy_target(eng, destructive=True)
    finally:
        eng.dispose()
