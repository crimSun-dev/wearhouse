"""Alembic environment for Wearhouse v2 (migration role only; never run by API startup).

Required: -x environment=<development|test|staging|production>. Optional: -x runtime_role=<role> (first run).
Refuses to operate on a legacy v1 demo database or on a v2 database registered for another environment.
"""
from __future__ import annotations

from alembic import context
from sqlalchemy import create_engine, inspect, pool, text

import wearhouse.accounts.adapters.tables  # noqa: F401 - populate metadata
import wearhouse.catalogue.adapters.tables  # noqa: F401
import wearhouse.commerce.adapters.tables  # noqa: F401
import wearhouse.wardrobe.adapters.tables  # noqa: F401
import wearhouse.weather.adapters.tables  # noqa: F401
import wearhouse.social.adapters.tables  # noqa: F401
import wearhouse.recommendations.adapters.tables  # noqa: F401
import wearhouse.identity.adapters.tables  # noqa: F401
import wearhouse.ownership.adapters.tables  # noqa: F401
import wearhouse.platform.tables  # noqa: F401
from wearhouse.bootstrap.config import APP_FAMILY, ENVIRONMENTS
from wearhouse.bootstrap.schema import LEGACY_MARKER_TABLE, LEGACY_TABLES
from wearhouse.platform.db import metadata, normalize_url

config = context.config
x = context.get_x_argument(as_dictionary=True)


class MigrationTargetError(RuntimeError):
    pass


def _guard(conn, environment: str) -> None:
    tables = set(inspect(conn).get_table_names())
    if "wearhouse_environment" not in tables:
        if tables & LEGACY_TABLES or LEGACY_MARKER_TABLE in tables:
            raise MigrationTargetError("Refusing to migrate: this is a legacy v1 demo database.")
        return
    row = conn.execute(text("SELECT app_family, environment FROM wearhouse_environment WHERE id = 1")).one_or_none()
    if row is None or row.app_family != APP_FAMILY:
        raise MigrationTargetError("Refusing to migrate: environment marker is not Wearhouse v2.")
    if row.environment != environment:
        raise MigrationTargetError(f"Refusing to migrate: database is registered as '{row.environment}', "
                                   f"not '{environment}'.")


def run_migrations_online() -> None:
    environment = x.get("environment")
    if environment not in ENVIRONMENTS:
        raise MigrationTargetError("Pass -x environment=<development|test|staging|production>.")
    engine = create_engine(normalize_url(config.get_main_option("sqlalchemy.url")), poolclass=pool.NullPool)
    with engine.connect() as conn:
        _guard(conn, environment)
        conn.commit()
        context.configure(connection=conn, target_metadata=metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    raise MigrationTargetError("Offline SQL generation is not supported; run against the target database.")
run_migrations_online()
