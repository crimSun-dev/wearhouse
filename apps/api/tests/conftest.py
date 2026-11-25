"""v2 test fixtures.

PostgreSQL tests need WEARHOUSE_TEST_ADMIN_URL: a superuser connection to a DISPOSABLE server (CI service
container, or a throwaway local cluster). Each test module gets its own freshly migrated database owned by a
migration role; the API connects as a separate least-privilege runtime role, exactly like deployment.
Nothing here can target the legacy demo database: the guard in `_admin_url` refuses names that
contain 'demo', and migrations refuse legacy schemas.
"""
from __future__ import annotations

import json
import os
import uuid
import warnings
from dataclasses import dataclass, replace
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

warnings.filterwarnings("ignore", message=".*httpx.*starlette.testclient.*")
from fastapi.testclient import TestClient  # noqa: E402

from wearhouse.bootstrap.cli import alembic_config  # noqa: E402
from wearhouse.bootstrap.config import Settings  # noqa: E402
from wearhouse.platform.crypto import generate_secret  # noqa: E402
from wearhouse.testing import LocalIssuer, create_test_app  # noqa: E402

HERE = Path(__file__).resolve().parent
ADMIN_URL = os.environ.get("WEARHOUSE_TEST_ADMIN_URL")
RUNTIME_ROLE, RUNTIME_PW = "wh_test_runtime", "wh-test-runtime-pw"
MIGRATOR_ROLE, MIGRATOR_PW = "wh_test_migrator", "wh-test-migrator-pw"
SECRET = generate_secret()
DATA_TABLES = ["inspiration", "share_report", "recommendation_choice", "recommendation_exposure", "recommendation_run", "account_setting", "user_size_preference", "product_size", "sandbox_offer_size", "item_neighbour", "recommendation_artifact", "product_media", "look_share", "plan_share_setting", "notification_state", "profile_showcase", "wear_entry_item", "wear_entry", "plan_entry", "look_revision", "look", "wardrobe_shelf_item",
               "wardrobe_shelf", "wardrobe_item_state", "wardrobe_declared_item", "weather_cache",
               "user_weather_location", "sandbox_order_unit", "sandbox_order_line", "sandbox_order", "cart_line", "wishlist_item",
               "sandbox_offer", "catalogue_collection_item", "catalogue_collection", "catalogue_import_row", "catalogue_import_job",
               "friend_request", "friendship", "user_block", "privacy_setting", "handle_hold", "account_profile",
               "ownership_event", "owned_item", "issuance_delivery", "activation_credential", "garment_unit",
               "media_reference", "product_variant", "product_revision", "product", "source_snapshot",
               "catalogue_source", "role_grant", "user_subject", "app_user", "idempotency_record", "attempt_event",
               "attempt_bucket", "audit_event", "outbox_delivery", "outbox_event"]


def _admin_url() -> str:
    if not ADMIN_URL:
        pytest.skip("set WEARHOUSE_TEST_ADMIN_URL to a disposable PostgreSQL superuser URL")
    if "demo" in (make_url(ADMIN_URL).database or ""):
        raise RuntimeError("refusing to use a database named like the legacy demo for v2 tests")
    return ADMIN_URL


def admin_engine(database: str | None = None):
    url = make_url(_admin_url().replace("postgresql://", "postgresql+psycopg://", 1))
    if database:
        url = url.set(database=database)
    return create_engine(url, isolation_level="AUTOCOMMIT", hide_parameters=True)


def role_url(database: str, user: str, password: str) -> str:
    base = make_url(_admin_url())
    return str(base.set(username=user, password=password, database=database).render_as_string(hide_password=False))


@dataclass(frozen=True)
class V2Database:
    name: str
    runtime_url: str
    migrator_url: str


def ensure_roles() -> None:
    eng = admin_engine()
    with eng.connect() as c:
        for role, pw, extra in ((RUNTIME_ROLE, RUNTIME_PW, ""), (MIGRATOR_ROLE, MIGRATOR_PW, " CREATEDB")):
            if not c.execute(text("SELECT 1 FROM pg_roles WHERE rolname = :r"), {"r": role}).first():
                c.execute(text(f"CREATE ROLE {role} LOGIN PASSWORD '{pw}'{extra}"))
    eng.dispose()


def create_database(environment: str = "test", runtime_role: str | None = RUNTIME_ROLE, migrate: bool = True) -> V2Database:
    from alembic import command

    ensure_roles()
    name = "wh_t_" + uuid.uuid4().hex[:12]
    eng = admin_engine()
    with eng.connect() as c:
        c.execute(text(f"CREATE DATABASE {name} OWNER {MIGRATOR_ROLE}"))
    eng.dispose()
    db = V2Database(name, role_url(name, RUNTIME_ROLE, RUNTIME_PW), role_url(name, MIGRATOR_ROLE, MIGRATOR_PW))
    if migrate:
        command.upgrade(alembic_config(db.migrator_url, environment, runtime_role), "head")
    return db


def drop_database(name: str) -> None:
    eng = admin_engine()
    with eng.connect() as c:
        c.execute(text(f"DROP DATABASE IF EXISTS {name} WITH (FORCE)"))
    eng.dispose()


@pytest.fixture(scope="module")
def v2_db():
    db = create_database()
    yield db
    drop_database(db.name)


def truncate_all(db: V2Database) -> None:
    eng = admin_engine(db.name)
    with eng.connect() as c:
        c.execute(text("SET session_replication_role = replica"))  # bypass immutability triggers (test cleanup only)
        c.execute(text("TRUNCATE " + ", ".join(DATA_TABLES) + " CASCADE"))
        _reseed_sizes(c)  # the size registry is reference data tests may edit: back to the 0011 seed
    eng.dispose()


def _reseed_sizes(c) -> None:
    import importlib.util
    spec = importlib.util.spec_from_file_location("m0011", HERE.parent / "migrations" / "versions" / "0011_sizes.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    c.execute(text("DELETE FROM size_value"))
    c.execute(text("DELETE FROM size_system"))
    for code, label, position, slots, sizes, common in mod.SYSTEMS:
        c.execute(text("INSERT INTO size_system (code, label, position, slots) VALUES (:c, :l, :p, :s)"),
                  {"c": code, "l": label, "p": position, "s": slots})
        for i, sc in enumerate(sizes):
            c.execute(text("INSERT INTO size_value (system_code, code, label, rank, common) VALUES (:s, :c, :c, :r, :m)"),
                      {"s": code, "c": sc, "r": (i + 1) * 10, "m": sc in common})


def counts(db: V2Database, *tables: str) -> dict[str, int]:
    eng = admin_engine(db.name)
    with eng.connect() as c:
        out = {t: c.execute(text(f"SELECT count(*) FROM {t}")).scalar() for t in tables}
    eng.dispose()
    return out


def query(db: V2Database, sql: str, **params):
    eng = admin_engine(db.name)
    with eng.connect() as c:
        rows = c.execute(text(sql), params).all()
    eng.dispose()
    return rows


@pytest.fixture
def clean_db(v2_db):
    truncate_all(v2_db)
    return v2_db


@pytest.fixture(scope="module")
def issuer() -> LocalIssuer:
    return LocalIssuer()


def make_settings(db: V2Database, issuer: LocalIssuer, **overrides) -> Settings:
    base = Settings(environment="test", database_url=db.runtime_url, oidc_issuer=issuer.issuer,
                    oidc_audience=issuer.audience, delivery_secret=SECRET, idempotency_lease_s=5.0,
                    rate_writes_per_min=0, rate_ip_per_min=0, rate_global_per_min=0)  # edge limits tested explicitly
    return replace(base, **overrides)


@pytest.fixture
def settings(clean_db, issuer) -> Settings:
    return make_settings(clean_db, issuer)


class Api:
    """Thin client: signed-token auth per call, never retries silently."""

    def __init__(self, app, issuer: LocalIssuer):
        self.app, self.issuer = app, issuer
        self.client = TestClient(app, raise_server_exceptions=False)
        self.services = app.state.services

    def headers(self, sub: str | None, idem: str | None = None, profile: dict | None = None, **extra) -> dict:
        h = dict(extra)
        if sub is not None:
            h["Authorization"] = "Bearer " + self.issuer.token(sub, profile=profile)
        if idem is not None:
            h["Idempotency-Key"] = idem
        return h

    def get(self, path, sub=None, **kw):
        return self.client.get(path, headers=self.headers(sub, **kw.pop("headers", {})), **kw)

    def post(self, path, sub=None, json=None, idem=None, **kw):
        return self.client.post(path, json=json, headers=self.headers(sub, idem, **kw.pop("headers", {})), **kw)

    def grant(self, sub: str, role: str) -> uuid.UUID:
        user_id, _ = self.services.identity.grant_role(issuer=self.issuer.issuer, subject=sub, role=role,
                                                       granted_by="pytest")
        return user_id

    def user_id(self, sub: str) -> str:
        return self.get("/api/v2/me", sub).json()["user_id"]


@pytest.fixture
def api(settings, issuer) -> Api:
    return Api(create_test_app(settings, issuer=issuer), issuer)


def synthetic_product(external_id: str = "0000000001", **fact_changes) -> dict:
    """DATA-FREE SYNTHETIC fixture (tests/fixtures/synthetic_product.json). Never the source-backed proof."""
    body = json.loads((HERE / "fixtures" / "synthetic_product.json").read_text(encoding="utf-8"))["request"]
    body["external_id"] = external_id
    body["original_fields"]["article_id"] = external_id
    for k, v in fact_changes.items():
        body["original_fields"][body["facts"][k]["source_field"]] = v
        body["facts"][k]["value"] = v
    return body


@pytest.fixture
def staff(api):
    """Editor + inventory manager subjects with server-side grants, and a product ready for issuance."""
    api.grant("editor-1", "catalogue_editor")
    api.grant("inventory-1", "inventory_manager")
    r = api.post("/api/v2/admin/source-products", "editor-1", json=synthetic_product())
    assert r.status_code == 201, r.text
    return {"editor": "editor-1", "inventory": "inventory-1", "product_id": r.json()["product_id"]}


def issue(api: Api, product_id: str, idem: str | None = None, sub: str = "inventory-1", **body):
    r = api.post("/api/v2/admin/unit-batches", sub, json={"product_id": product_id, **body},
                 idem=idem or ("issue-" + uuid.uuid4().hex))
    assert r.status_code == 201, r.text
    return r.json()


def redeem(api: Api, sub: str, key: str, idem: str | None = None):
    return api.post("/api/v2/redemptions", sub, json={"activation_key": key}, idem=idem or ("claim-" + uuid.uuid4().hex))


# ------------------------------------------------------------------ add-wearhouse-accounts fixtures
@pytest.fixture(scope="module")
def neon_issuer() -> LocalIssuer:
    """Neon Auth-shaped issuer: EdDSA, iss == aud == Auth origin, 15-minute tokens, profile hint claims."""
    return LocalIssuer.neon()


@pytest.fixture
def neon(clean_db, neon_issuer) -> Api:
    return Api(create_test_app(make_settings(clean_db, neon_issuer), issuer=neon_issuer), neon_issuer)


def onboard(api: Api, sub: str, handle: str | None = None) -> str:
    handle = handle or sub.replace("-", "_")
    r = api.client.patch("/api/v2/me/profile", json={"handle": handle}, headers=api.headers(sub))
    assert r.status_code == 200, r.text
    return handle


def befriend(api: Api, a: str, b: str) -> None:
    r = api.post("/api/v2/me/friend-requests", a, json={"handle": b.replace("-", "_")},
                 idem="fr-" + uuid.uuid4().hex)
    assert r.status_code == 201, r.text
    acc = api.post(f"/api/v2/me/friend-requests/{r.json()['request_id']}/accept", b)
    assert acc.status_code == 200, acc.text
