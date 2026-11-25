"""Read-only startup/readiness checks. Startup never creates schemas, migrates, seeds or resets.

Order: connectivity -> legacy-target rejection -> environment marker -> schema version -> role privileges.
Every failure is an actionable StartupError raised before the API serves requests.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from .config import APP_FAMILY, Settings
from .schema import (LEGACY_MARKER_TABLE, LEGACY_TABLES, RUNTIME_COLUMN_PRIVILEGES, RUNTIME_PRIVILEGES,
                     SCHEMA_HEAD)


class StartupError(RuntimeError):
    pass


@dataclass(frozen=True)
class Readiness:
    ok: bool
    checks: dict[str, str]


def verify_database(engine: Engine, settings: Settings) -> dict[str, str]:
    checks: dict[str, str] = {}
    try:
        with engine.connect() as conn:
            conn.execute(text("SET TRANSACTION READ ONLY"))
            tables = set(inspect(conn).get_table_names())
            checks["connect"] = "ok"
            if "wearhouse_environment" not in tables:
                if tables & LEGACY_TABLES or LEGACY_MARKER_TABLE in tables:
                    raise StartupError("WEARHOUSE_DATABASE_URL points at a legacy v1 demo database. "
                                       "Configure a dedicated v2 database; v2 never uses legacy demo state.")
                raise StartupError("Database is not a migrated Wearhouse v2 database (no environment marker). "
                                   "Run the release migration: `wearhouse migrate --environment <env>`.")
            for t in ("wearhouse_environment", "alembic_version"):
                if t in tables and not conn.execute(text("SELECT has_table_privilege(current_user, :t, 'SELECT')"),
                                                    {"t": t}).scalar():
                    raise StartupError(f"The runtime database role lacks required privileges: SELECT on {t}")
            marker = conn.execute(text("SELECT app_family, environment FROM wearhouse_environment WHERE id = 1")).one_or_none()
            if marker is None or marker.app_family != APP_FAMILY:
                raise StartupError("Environment marker is missing or not a Wearhouse v2 database.")
            if marker.environment != settings.environment:
                raise StartupError(f"Database is registered for environment '{marker.environment}' but "
                                   f"WEARHOUSE_ENV is '{settings.environment}'. Refusing to start.")
            checks["environment"] = marker.environment
            version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one_or_none() \
                if "alembic_version" in tables else None
            if version != SCHEMA_HEAD:
                raise StartupError(f"Schema version is {version!r}; this build requires {SCHEMA_HEAD!r}. "
                                   "Run the release migration before starting (startup never migrates).")
            checks["schema"] = version
            role = conn.execute(text(
                "SELECT r.rolsuper, has_schema_privilege(current_user, 'public', 'CREATE') AS can_create, "
                "has_database_privilege(current_user, current_database(), 'CREATE') AS can_create_schema "
                "FROM pg_roles r WHERE r.rolname = current_user")).one()
            over_privileged = role.rolsuper or role.can_create or role.can_create_schema
            if over_privileged and settings.environment != "development":
                raise StartupError("The runtime database role can create schemas/objects (or is a superuser). "
                                   "Use the least-privilege runtime role; migrations use a separate role.")
            checks["role"] = "over_privileged(development)" if over_privileged else "least_privilege"
            missing = []
            for table, privs in RUNTIME_PRIVILEGES.items():
                for p in privs:
                    if not conn.execute(text("SELECT has_table_privilege(current_user, :t, :p)"),
                                        {"t": table, "p": p}).scalar():
                        missing.append(f"{p} on {table}")
            for table, privs in RUNTIME_COLUMN_PRIVILEGES.items():
                for p, cols in privs.items():
                    for col in cols:
                        if not conn.execute(text("SELECT has_column_privilege(current_user, :t, :c, :p)"),
                                            {"t": table, "c": col, "p": p}).scalar():
                            missing.append(f"{p}({col}) on {table}")
            if missing:
                raise StartupError("The runtime database role lacks required privileges: " + ", ".join(missing))
            checks["privileges"] = "ok"
            conn.rollback()
    except StartupError:
        raise
    except SQLAlchemyError as exc:
        raise StartupError(f"Database unavailable or unreadable ({type(exc).__name__}).") from None
    return checks


def readiness(engine: Engine, settings: Settings) -> Readiness:
    try:
        return Readiness(True, verify_database(engine, settings))
    except StartupError as exc:
        return Readiness(False, {"error": str(exc)})
