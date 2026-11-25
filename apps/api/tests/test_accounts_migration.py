"""add-wearhouse-accounts 3.1: migration 0004 upgrades a 0003 database safely and least-privilege."""
from __future__ import annotations

import uuid

import pytest
from alembic import command
from sqlalchemy import text

from conftest import (RUNTIME_PW, RUNTIME_ROLE, RUNTIME_ROLE as ROLE, admin_engine, create_database, drop_database,
                      make_settings, query, role_url)
from wearhouse.bootstrap.cli import alembic_config
from wearhouse.bootstrap.startup import StartupError
from wearhouse.platform.db import make_engine
from wearhouse.testing import LocalIssuer, create_test_app

pytestmark = pytest.mark.postgres


def test_upgrade_from_0003_backfills_and_is_repeatable():
    db = create_database(migrate=False)
    try:
        cfg = alembic_config(db.migrator_url, "test", ROLE)
        command.upgrade(cfg, "0003_ownership")
        uid = uuid.uuid4()
        eng = admin_engine(db.name)
        with eng.connect() as c:
            c.execute(text("INSERT INTO app_user (id) VALUES (:u)"), {"u": uid})
        eng.dispose()
        issuer = LocalIssuer.neon()
        with pytest.raises(StartupError, match="0003_ownership"):
            create_test_app(make_settings(db, issuer), issuer=issuer)
        command.upgrade(cfg, "head")
        command.upgrade(cfg, "head")  # repeat: no-op
        from wearhouse.bootstrap.schema import SCHEMA_HEAD
        assert query(db, "SELECT version_num FROM alembic_version") == [(SCHEMA_HEAD,)]
        assert query(db, "SELECT display_name, handle FROM account_profile WHERE user_id = :u", u=uid) == \
            [("Wearhouse user", None)]
        assert query(db, "SELECT profile, wardrobe, friends_list FROM privacy_setting WHERE user_id = :u", u=uid) == \
            [("public", "private", "friends")]
        create_test_app(make_settings(db, issuer), issuer=issuer)  # runtime privilege check passes
    finally:
        drop_database(db.name)


def test_widened_attempt_scopes_and_column_level_app_user_grant(v2_db):
    eng = make_engine(role_url(v2_db.name, RUNTIME_ROLE, RUNTIME_PW))
    with eng.begin() as c:
        for scope in ("friend_request", "export"):
            c.execute(text("INSERT INTO attempt_bucket (scope, scope_key) VALUES (:s, 'x') ON CONFLICT DO NOTHING"),
                      {"s": scope})
        uid = uuid.uuid4()
        c.execute(text("INSERT INTO app_user (id) VALUES (:u)"), {"u": uid})
        c.execute(text("UPDATE app_user SET tokens_not_before = now(), deleted_at = now() WHERE id = :u"), {"u": uid})
    with pytest.raises(Exception, match="permission denied"):
        with eng.begin() as c:
            c.execute(text("UPDATE app_user SET created_at = now() WHERE id = :u"), {"u": uid})
    with pytest.raises(Exception, match="ck_attempt_bucket_scope"):
        with eng.begin() as c:
            c.execute(text("INSERT INTO attempt_bucket (scope, scope_key) VALUES ('nope', 'x')"))
    eng.dispose()


def test_social_constraints_hold(v2_db):
    eng = admin_engine(v2_db.name)
    a, b = uuid.uuid4(), uuid.uuid4()
    with eng.connect() as c:
        c.execute(text("INSERT INTO app_user (id) VALUES (:a), (:b)"), {"a": a, "b": b})
        lo, hi = sorted([a, b])
        for bad, sql, params in (
            ("ck_friendship_ordered_pair", "INSERT INTO friendship VALUES (:h, :l, now())", {"h": hi, "l": lo}),
            ("ck_user_block_not_self", "INSERT INTO user_block VALUES (:a, :a, now())", {"a": a}),
            ("ck_friend_request_not_self",
             "INSERT INTO friend_request (id, from_user, to_user, status, created_at) VALUES (:i, :a, :a, 'pending', now())",
             {"i": uuid.uuid4(), "a": a}),
            ("ck_account_profile_handle_format",
             "INSERT INTO account_profile (user_id, handle, display_name) VALUES (:a, 'Bad-Handle', 'x')", {"a": a}),
        ):
            with pytest.raises(Exception, match=bad):
                c.execute(text(sql), params)
        c.execute(text("INSERT INTO friend_request (id, from_user, to_user, status, created_at) "
                       "VALUES (:i, :a, :b, 'pending', now())"), {"i": uuid.uuid4(), "a": a, "b": b})
        with pytest.raises(Exception, match="uq_friend_request_one_pending"):
            c.execute(text("INSERT INTO friend_request (id, from_user, to_user, status, created_at) "
                           "VALUES (:i, :a, :b, 'pending', now())"), {"i": uuid.uuid4(), "a": a, "b": b})
    eng.dispose()
