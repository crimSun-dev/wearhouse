"""Helpers used by Alembic revisions (apps/api/migrations). Migration role only."""
from __future__ import annotations

import re

from sqlalchemy import text

from .schema import RUNTIME_COLUMN_PRIVILEGES, RUNTIME_PRIVILEGES

_ROLE = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")

FORBID_CHANGE_FN = """
CREATE OR REPLACE FUNCTION wearhouse_forbid_change() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'wearhouse: % is immutable (% rejected)', TG_TABLE_NAME, TG_OP
        USING ERRCODE = 'insufficient_privilege';
END $$;
"""


def check_role_name(role: str) -> str:
    if not _ROLE.fullmatch(role):
        raise ValueError(f"invalid runtime role name {role!r}")
    return role


def runtime_role(bind) -> str | None:
    return bind.execute(text("SELECT runtime_role FROM wearhouse_environment WHERE id = 1")).scalar_one_or_none()


def grant_runtime(bind, tables: list[str]) -> None:
    role = runtime_role(bind)
    if not role:
        return
    role = check_role_name(role)
    for t in tables:
        privs = ", ".join(RUNTIME_PRIVILEGES[t])
        bind.execute(text(f'GRANT {privs} ON TABLE "{t}" TO "{role}"'))


def grant_runtime_columns(bind, tables: list[str]) -> None:
    role = runtime_role(bind)
    if not role:
        return
    role = check_role_name(role)
    for t in tables:
        for priv, cols in RUNTIME_COLUMN_PRIVILEGES[t].items():
            collist = ", ".join(f'"{c}"' for c in cols)
            bind.execute(text(f'GRANT {priv} ({collist}) ON TABLE "{t}" TO "{role}"'))


def make_immutable(bind, table: str) -> None:
    bind.execute(text(FORBID_CHANGE_FN))
    bind.execute(text(f'CREATE TRIGGER "{table}_immutable" BEFORE UPDATE OR DELETE ON "{table}" '
                      f"FOR EACH ROW EXECUTE FUNCTION wearhouse_forbid_change()"))
    bind.execute(text(f'CREATE TRIGGER "{table}_no_truncate" BEFORE TRUNCATE ON "{table}" '
                      f"FOR EACH STATEMENT EXECUTE FUNCTION wearhouse_forbid_change()"))
