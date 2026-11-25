"""3.4 / 3.5 / 3.6 explicit migrations, database-enforced invariants and read-only startup."""
from __future__ import annotations

import uuid

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

import wearhouse.catalogue.adapters.tables  # noqa: F401
import wearhouse.commerce.adapters.tables  # noqa: F401
import wearhouse.wardrobe.adapters.tables  # noqa: F401
import wearhouse.weather.adapters.tables  # noqa: F401
import wearhouse.social.adapters.tables  # noqa: F401
import wearhouse.recommendations.adapters.tables  # noqa: F401
import wearhouse.identity.adapters.tables  # noqa: F401
import wearhouse.ownership.adapters.tables  # noqa: F401
import wearhouse.platform.tables  # noqa: F401
from conftest import (RUNTIME_ROLE, admin_engine, counts, create_database, drop_database, issue, make_settings,
                      query, redeem, role_url, RUNTIME_PW)
from wearhouse.bootstrap.cli import alembic_config
from wearhouse.bootstrap.schema import SCHEMA_HEAD
from wearhouse.bootstrap.startup import StartupError
from wearhouse.platform.db import metadata
from wearhouse.testing import create_test_app

pytestmark = pytest.mark.postgres


def test_schema_head_constant_matches_alembic_head(v2_db):
    script = ScriptDirectory.from_config(alembic_config(v2_db.migrator_url, "test", None))
    assert script.get_heads() == [SCHEMA_HEAD]


def test_fresh_upgrade_twice_reaches_head_without_side_effects():
    db = create_database()  # first upgrade
    try:
        before = query(db, "SELECT version_num FROM alembic_version")
        snapshot = counts(db, "wearhouse_environment", "app_user", "product", "garment_unit")
        command.upgrade(alembic_config(db.migrator_url, "test", RUNTIME_ROLE), "head")  # repeat
        assert query(db, "SELECT version_num FROM alembic_version") == before == [(SCHEMA_HEAD,)]
        assert counts(db, "wearhouse_environment", "app_user", "product", "garment_unit") == snapshot
        assert snapshot == {"wearhouse_environment": 1, "app_user": 0, "product": 0, "garment_unit": 0}
    finally:
        drop_database(db.name)


def test_migrations_match_table_metadata(v2_db):
    eng = admin_engine(v2_db.name)
    with eng.connect() as c:
        diff = compare_metadata(MigrationContext.configure(c, opts={"compare_type": True}), metadata)
    eng.dispose()
    assert diff == [], f"metadata drift vs migrations: {diff}"


def test_external_ids_keep_leading_zeros(api, staff, clean_db):
    stored = query(clean_db, "SELECT external_id FROM product")
    assert stored == [("0000000001",)]
    pub = api.get("/api/v2/items/" + issue(api, staff["product_id"])["public_serial"]).json()
    assert pub["source"]["external_id"] == "0000000001"


def test_product_revisions_are_immutable_even_for_the_owner(api, staff, clean_db):
    eng = admin_engine(clean_db.name)
    with pytest.raises(Exception, match="immutable"):
        with eng.connect() as c:
            c.execute(text("UPDATE product_revision SET facts = '{}'::jsonb"))
    eng.dispose()


def test_database_rejects_second_owner_for_a_unit(api, staff, clean_db):
    unit = issue(api, staff["product_id"])
    assert redeem(api, "customer-a", unit["delivery"]["activation_key"]).status_code == 201
    other_user = api.user_id("customer-b")
    rev = query(clean_db, "SELECT acquisition_revision_id FROM garment_unit")[0][0]
    eng = admin_engine(clean_db.name)
    with pytest.raises(IntegrityError, match="uq_owned_item_unit_id"):
        with eng.connect() as c:
            c.execute(text("INSERT INTO owned_item (id, user_id, unit_id, acquisition_revision_id, presentation, "
                           "claimed_at, created_at) VALUES (:i, :u, :unit, :r, '{}'::jsonb, now(), now())"),
                      {"i": uuid.uuid4(), "u": other_user, "unit": uuid.UUID(unit["unit_id"]), "r": rev})
    eng.dispose()


def test_database_rejects_two_live_credentials_for_a_unit(api, staff, clean_db):
    unit = issue(api, staff["product_id"])
    eng = admin_engine(clean_db.name)
    with pytest.raises(IntegrityError, match="uq_activation_credential_one_active_per_unit"):
        with eng.connect() as c:
            c.execute(text("INSERT INTO activation_credential (id, unit_id, key_digest, status, issued_by) "
                           "VALUES (:i, :u, :d, 'active', :u)"),
                      {"i": uuid.uuid4(), "u": uuid.UUID(unit["unit_id"]), "d": "a" * 64})
    with pytest.raises(IntegrityError, match="ck_garment_unit_status"):
        with eng.connect() as c:
            c.execute(text("UPDATE garment_unit SET status = 'owned'"))
    eng.dispose()


def test_runtime_role_cannot_change_schema_or_delete_history(api, staff, clean_db):
    issue(api, staff["product_id"])
    from wearhouse.platform.db import make_engine
    eng = make_engine(role_url(clean_db.name, RUNTIME_ROLE, RUNTIME_PW))
    for stmt in ("CREATE TABLE x (id int)", "DROP TABLE garment_unit", "DELETE FROM audit_event",
                 "UPDATE audit_event SET action = 'x'", "TRUNCATE ownership_event", "DELETE FROM garment_unit"):
        with pytest.raises(Exception, match="permission denied|must be owner"):
            with eng.begin() as c:
                c.execute(text(stmt))
    eng.dispose()


def test_startup_against_stale_schema_fails_without_changes(issuer):
    db = create_database()
    try:
        eng = admin_engine(db.name)
        with eng.connect() as c:
            c.execute(text("UPDATE alembic_version SET version_num = '0002_catalogue'"))
        eng.dispose()
        before = counts(db, "wearhouse_environment", "app_user", "audit_event", "idempotency_record")
        with pytest.raises(StartupError, match="0002_catalogue"):
            create_test_app(make_settings(db, issuer), issuer=issuer)
        assert query(db, "SELECT version_num FROM alembic_version") == [("0002_catalogue",)]
        assert counts(db, "wearhouse_environment", "app_user", "audit_event", "idempotency_record") == before
    finally:
        drop_database(db.name)


def test_startup_performs_no_writes(issuer):
    db = create_database()
    try:
        tables = ("app_user", "audit_event", "outbox_event", "attempt_event", "product", "idempotency_record")
        before = counts(db, *tables)
        xact = query(db, "SELECT xact_commit FROM pg_stat_database WHERE datname = current_database()")
        create_test_app(make_settings(db, issuer), issuer=issuer)
        assert counts(db, *tables) == before
        assert query(db, "SELECT count(*) FROM pg_stat_user_tables WHERE n_tup_ins + n_tup_upd + n_tup_del > 0 "
                         "AND relname NOT IN ('wearhouse_environment', 'alembic_version', "
                         # reference data seeded by migration 0011 (add-wearhouse-sizes), not by startup
                         "'size_system', 'size_value')") == [(0,)]
        assert xact  # stats readable
    finally:
        drop_database(db.name)
