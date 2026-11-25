"""3.3 / 4.4 environment, configuration and database-role safeguards fail closed."""
from __future__ import annotations

from dataclasses import replace

import pytest
from sqlalchemy import text

from conftest import (RUNTIME_PW, RUNTIME_ROLE, SECRET, admin_engine, counts, create_database, drop_database,
                      make_settings, role_url)
from wearhouse.bootstrap.app import create_app
from wearhouse.bootstrap.config import ConfigError, Settings
from wearhouse.bootstrap.startup import StartupError, verify_database
from wearhouse.platform.db import DatabaseUrlError, make_engine
from wearhouse.testing import StaticTestVerifier, create_test_app

PROD = dict(environment="production", database_url="postgresql://u:p@db.example/wh", oidc_issuer="https://id.example",
            oidc_jwks_url="https://id.example/.well-known/jwks.json",
            oidc_audience="wearhouse-api", delivery_secret=SECRET, allowed_origins=("https://app.example",))


# ---------------------------------------------------------------- configuration (no DB)
def test_valid_production_config_passes():
    Settings(**PROD).validate()


@pytest.mark.parametrize("field,value,needle", [
    ("oidc_issuer", None, "WEARHOUSE_OIDC_ISSUER"),
    ("oidc_audience", None, "WEARHOUSE_OIDC_AUDIENCE"),
    ("database_url", None, "WEARHOUSE_DATABASE_URL"),
    ("delivery_secret", None, "WEARHOUSE_DELIVERY_SECRET"),
    ("oidc_issuer", "http://id.example", "https"),
    ("allowed_origins", ("http://app.example",), "https"),
    ("auth_adapter", "test", "test identity adapter"),
])
def test_deployment_config_missing_or_unsafe_fails(field, value, needle):
    with pytest.raises(ConfigError) as e:
        Settings(**{**PROD, field: value}).validate()
    assert needle in str(e.value)


def test_local_jwks_file_rejected_in_deployment(tmp_path):
    with pytest.raises(ConfigError, match="JWKS_FILE"):
        Settings(**PROD, oidc_jwks_file=tmp_path / "jwks.json").validate()


def test_weak_secret_rejected():
    with pytest.raises(ConfigError, match="at least 32 bytes"):
        Settings(**{**PROD, "delivery_secret": "c2hvcnQ"}).validate()


@pytest.mark.parametrize("env", ["development", "staging", "production"])
def test_test_adapter_only_inside_test_environment(env):
    with pytest.raises(ConfigError):
        Settings(**{**PROD, "environment": env, "auth_adapter": "test"}).validate()


def test_unknown_environment_rejected():
    with pytest.raises(ConfigError, match="WEARHOUSE_ENV"):
        Settings(**{**PROD, "environment": "prod"}).validate()


def test_from_env_reads_only_wearhouse_variables():
    s = Settings.from_env({"WEARHOUSE_ENV": "production", "DATABASE_URL": "sqlite:///demo.db",
                           "DEMO_API_KEY": "demo-key"})
    assert s.database_url is None  # legacy variables confer nothing
    with pytest.raises(ConfigError):
        s.validate()


def test_sqlite_is_not_a_v2_database():
    with pytest.raises(DatabaseUrlError):
        make_engine("sqlite:///demo.db")


def test_test_factory_refuses_deployment_and_create_app_refuses_test_adapter():
    with pytest.raises(ConfigError):
        create_test_app(Settings(**PROD), verifier=StaticTestVerifier())
    with pytest.raises(ConfigError):
        create_app(Settings(**{**PROD, "environment": "test", "auth_adapter": "test"}))


# ---------------------------------------------------------------- database targets
pg = pytest.mark.postgres


@pg
def test_legacy_demo_database_is_refused_without_mutation(issuer):
    db = create_database(migrate=False)
    try:
        eng = admin_engine(db.name)
        with eng.connect() as c:
            c.execute(text("CREATE TABLE garment (id text primary key)"))
            c.execute(text("CREATE TABLE interface_log (id serial primary key)"))
            c.execute(text("INSERT INTO garment VALUES ('g1')"))
            c.execute(text(f"GRANT SELECT ON ALL TABLES IN SCHEMA public TO {RUNTIME_ROLE}"))
        eng.dispose()
        with pytest.raises(StartupError, match="legacy v1 demo database"):
            create_test_app(make_settings(db, issuer), issuer=issuer)
        assert counts(db, "garment") == {"garment": 1}
        from alembic import command
        from wearhouse.bootstrap.cli import alembic_config
        with pytest.raises(Exception, match="legacy v1 demo database"):
            command.upgrade(alembic_config(db.migrator_url, "test", RUNTIME_ROLE), "head")
        tables = {r[0] for r in admin_engine(db.name).connect().execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname='public'"))}
        assert tables == {"garment", "interface_log"}  # migration refused before creating anything
    finally:
        drop_database(db.name)


@pg
def test_unmarked_database_is_refused(issuer):
    db = create_database(migrate=False)
    try:
        with pytest.raises(StartupError, match="not a migrated Wearhouse v2 database"):
            create_test_app(make_settings(db, issuer), issuer=issuer)
    finally:
        drop_database(db.name)


@pg
def test_database_registered_for_other_environment_is_refused(issuer):
    db = create_database(environment="staging")
    try:
        with pytest.raises(StartupError, match="registered for environment 'staging'"):
            create_test_app(make_settings(db, issuer), issuer=issuer)
        from alembic import command
        from wearhouse.bootstrap.cli import alembic_config
        with pytest.raises(Exception, match="registered as 'staging'"):
            command.upgrade(alembic_config(db.migrator_url, "test", None), "head")
    finally:
        drop_database(db.name)


@pg
def test_runtime_role_without_grants_fails_closed(issuer):
    db = create_database(runtime_role=None)  # migrated, but nothing granted to the runtime role
    try:
        with pytest.raises(StartupError, match="lacks required privileges"):
            create_test_app(make_settings(db, issuer), issuer=issuer)
    finally:
        drop_database(db.name)


@pg
def test_over_privileged_runtime_role_fails_closed(v2_db, issuer):
    from conftest import _admin_url
    settings = replace(make_settings(v2_db, issuer), database_url=_admin_url().rsplit("/", 1)[0] + "/" + v2_db.name)
    with pytest.raises(StartupError, match="superuser"):
        verify_database(make_engine(settings.database_url), settings)


@pg
def test_environment_marker_is_immutable(v2_db):
    eng = make_engine(role_url(v2_db.name, RUNTIME_ROLE, RUNTIME_PW))
    with pytest.raises(Exception):
        with eng.begin() as c:
            c.execute(text("UPDATE wearhouse_environment SET environment = 'production'"))
    eng2 = admin_engine(v2_db.name)
    with pytest.raises(Exception, match="immutable"):
        with eng2.connect() as c:
            c.execute(text("UPDATE wearhouse_environment SET environment = 'production'"))
    eng.dispose()
    eng2.dispose()


def test_actor_redemption_limit_cannot_be_disabled_in_deployments():
    """complete-wearhouse-research-intelligence D3: only the RQ3 validation corpus may run without the per-user
    limit, and only in non-deployment environments."""
    import dataclasses

    import pytest

    from wearhouse.bootstrap.config import ConfigError, Settings
    base = Settings(environment="production", database_url="postgresql://x@h/db", auth_adapter="oidc",
                    oidc_issuer="https://issuer.example", oidc_audience="https://issuer.example",
                    oidc_jwks_url="https://issuer.example/jwks", delivery_secret="s" * 44)
    with pytest.raises(ConfigError, match="per-user redemption limit"):
        dataclasses.replace(base, redemption_actor_limit=None).validate()
