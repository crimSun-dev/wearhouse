"""SQLAlchemy engine/metadata primitives (PostgreSQL only for v2)."""
from __future__ import annotations

from sqlalchemy import MetaData, create_engine
from sqlalchemy.engine import Engine, make_url

NAMING = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}
metadata = MetaData(naming_convention=NAMING)


class DatabaseUrlError(ValueError):
    pass


def normalize_url(url: str) -> str:
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    parsed = make_url(url)
    if parsed.get_backend_name() != "postgresql":
        raise DatabaseUrlError("Wearhouse v2 requires PostgreSQL (SQLite is legacy/offline only)")
    return url


def make_engine(url: str, *, pool_size: int = 5) -> Engine:
    """Lazy engine: creating it opens no connection (OpenAPI export relies on this)."""
    return create_engine(normalize_url(url), pool_pre_ping=True, hide_parameters=True, pool_size=pool_size, max_overflow=5,
                         connect_args={"prepare_threshold": None, "application_name": "wearhouse-api"})
