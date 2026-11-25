"""publish-wearhouse-catalogue 1.1: migration 0005 backfills existing products as published and stays issuable."""
from __future__ import annotations

import uuid

import pytest
from alembic import command
from sqlalchemy import text

from conftest import RUNTIME_ROLE, Api, admin_engine, create_database, drop_database, issue, make_settings, query
from wearhouse.bootstrap.cli import alembic_config
from wearhouse.testing import LocalIssuer, create_test_app

pytestmark = pytest.mark.postgres


def test_upgrade_from_0004_publishes_existing_active_products():
    db = create_database(migrate=False)
    try:
        cfg = alembic_config(db.migrator_url, "test", RUNTIME_ROLE)
        command.upgrade(cfg, "0004_accounts")
        src, snap, prod, rev, user = (uuid.uuid4() for _ in range(5))
        eng = admin_engine(db.name)
        with eng.connect() as c:
            c.execute(text("INSERT INTO app_user (id) VALUES (:u)"), {"u": user})
            c.execute(text("INSERT INTO catalogue_source (id, namespace, name, url) VALUES (:i, 'legacy-src', 'S', "
                           "'https://s.example')"), {"i": src})
            c.execute(text("INSERT INTO source_snapshot (id, source_id, sha256, file_name, acquired_on, permission) "
                           "VALUES (:i, :s, :h, 'f.csv', '2026-11-25', '{}'::jsonb)"), {"i": snap, "s": src, "h": "a" * 64})
            c.execute(text("INSERT INTO product (id, source_id, external_id) VALUES (:p, :s, '0001')"), {"p": prod, "s": src})
            c.execute(text("INSERT INTO product_revision (id, product_id, revision_no, snapshot_id, content_digest, "
                           "original_fields, facts, annotations, created_by) VALUES (:r, :p, 1, :n, 'd', '{}'::jsonb, "
                           "'{\"product_name\": {\"value\": \"Old Tee\", \"source_field\": \"n\"}, "
                           "\"category\": {\"value\": \"T-shirt\", \"source_field\": \"c\"}}'::jsonb, "
                           "'{\"slot\": {\"value\": \"top\", \"origin\": \"rule\"}}'::jsonb, :u)"),
                      {"r": rev, "p": prod, "n": snap, "u": user})
            c.execute(text("UPDATE product SET current_revision_id = :r WHERE id = :p"), {"r": rev, "p": prod})
        eng.dispose()
        command.upgrade(cfg, "head")
        command.upgrade(cfg, "head")
        assert query(db, "SELECT publication_state, published_revision_id = current_revision_id, browse_name, "
                         "browse_category, browse_slot, browse_text FROM product") == \
            [("published", True, "Old Tee", "T-shirt", "top", "old tee ")]
        issuer = LocalIssuer.neon()
        api = Api(create_test_app(make_settings(db, issuer), issuer=issuer), issuer)  # privilege check passes
        api.grant("inv", "inventory_manager")
        assert issue(api, str(prod), sub="inv")["unit_id"]  # backfilled product stays issuable
    finally:
        drop_database(db.name)
