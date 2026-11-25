"""SQL implementations of the platform ports and the transactional unit of work."""
from __future__ import annotations

import math
import uuid
from datetime import datetime, timedelta
from typing import Any, Callable

from sqlalchemy import and_, delete, func, insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Connection, Engine

from ..context import current_request_id
from ..ids import new_id
from ..ports import AttemptScope, IdempotencyRecord
from ..tables import attempt_bucket, attempt_event, audit_event, idempotency_record, outbox_event

SCOPE_ORDER = {"actor": 0, "ip": 1, "global": 2, "friend_request": 3, "export": 4}


class SqlIdempotencyStore:
    def __init__(self, conn: Connection):
        self.conn = conn

    @staticmethod
    def _row(r) -> IdempotencyRecord:
        return IdempotencyRecord(id=r.id, actor_id=r.actor_id, route=r.route, idem_key=r.idem_key,
                                 request_fingerprint=r.request_fingerprint, status=r.status,
                                 lease_token=r.lease_token, lease_expires_at=r.lease_expires_at,
                                 attempt_reserved=r.attempt_reserved, response_status=r.response_status,
                                 response_body=r.response_body)

    def acquire(self, *, actor_id, route, key, fingerprint, now):
        new = new_id()
        stmt = (pg_insert(idempotency_record)
                .values(id=new, actor_id=actor_id, route=route, idem_key=key, request_fingerprint=fingerprint,
                        status="processing", created_at=now)
                .on_conflict_do_nothing(index_elements=["actor_id", "route", "idem_key"]))
        self.conn.execute(stmt)
        row = self.conn.execute(
            select(idempotency_record)
            .where(idempotency_record.c.actor_id == actor_id, idempotency_record.c.route == route,
                   idempotency_record.c.idem_key == key)
            .with_for_update()).one()
        return self._row(row), row.id == new

    def lock(self, record_id):
        row = self.conn.execute(select(idempotency_record).where(idempotency_record.c.id == record_id)
                                .with_for_update()).one_or_none()
        return self._row(row) if row else None

    def start_lease(self, record_id, token, expires_at):
        self.conn.execute(update(idempotency_record).where(idempotency_record.c.id == record_id)
                          .values(lease_token=token, lease_expires_at=expires_at))

    def mark_attempt_reserved(self, record_id):
        self.conn.execute(update(idempotency_record).where(idempotency_record.c.id == record_id)
                          .values(attempt_reserved=True))

    def complete(self, record_id, status, body, now):
        self.conn.execute(update(idempotency_record).where(idempotency_record.c.id == record_id)
                          .values(status="completed", response_status=status, response_body=body,
                                  completed_at=now, lease_token=None, lease_expires_at=None))

    def expire_lease(self, record_id, now):
        self.conn.execute(update(idempotency_record)
                          .where(idempotency_record.c.id == record_id, idempotency_record.c.status == "processing")
                          .values(lease_expires_at=now))

    def release(self, record_id):
        self.conn.execute(delete(idempotency_record)
                          .where(idempotency_record.c.id == record_id, idempotency_record.c.status == "processing",
                                 idempotency_record.c.attempt_reserved.is_(False)))


class SqlAttemptLedger:
    def __init__(self, conn: Connection):
        self.conn = conn

    def reserve(self, scopes: list[AttemptScope], *, now: datetime, window: timedelta,
                idempotency_id: uuid.UUID | None) -> int | None:
        ordered = sorted(scopes, key=lambda s: (SCOPE_ORDER[s.scope], s.key))
        if not ordered:  # every limit disabled (RQ3 validation corpus only): nothing to count or record.
            return None  # insert(table) with an EMPTY parameter list would insert one all-defaults row.
        since = now - window
        for s in ordered:  # lock buckets in a fixed order: no deadlocks between workers
            self.conn.execute(pg_insert(attempt_bucket).values(scope=s.scope, scope_key=s.key, created_at=now)
                              .on_conflict_do_nothing(index_elements=["scope", "scope_key"]))
            self.conn.execute(select(attempt_bucket.c.scope)
                              .where(attempt_bucket.c.scope == s.scope, attempt_bucket.c.scope_key == s.key)
                              .with_for_update())
        for s in ordered:
            in_window = and_(attempt_event.c.scope == s.scope, attempt_event.c.scope_key == s.key,
                             attempt_event.c.reserved_at > since)
            used, oldest = self.conn.execute(
                select(func.count(), func.min(attempt_event.c.reserved_at)).where(in_window)).one()
            if used >= s.limit:
                return max(1, math.ceil((oldest + window - now).total_seconds()))
        self.conn.execute(insert(attempt_event), [
            {"id": new_id(), "scope": s.scope, "scope_key": s.key, "reserved_at": now,
             "idempotency_id": idempotency_id} for s in ordered])
        return None


class SqlAuditWriter:
    def __init__(self, conn: Connection):
        self.conn = conn

    def record(self, *, actor_id, action, target_type, target_id, details=None):
        self.conn.execute(insert(audit_event).values(
            id=new_id(), actor_id=actor_id, action=action, target_type=target_type, target_id=str(target_id),
            details=details or {}, request_id=current_request_id()))


class SqlOutboxWriter:
    def __init__(self, conn: Connection):
        self.conn = conn

    def emit(self, *, event_type, aggregate_type, aggregate_id, payload):
        eid = new_id()
        self.conn.execute(insert(outbox_event).values(id=eid, event_type=event_type, aggregate_type=aggregate_type,
                                                      aggregate_id=aggregate_id, payload=payload))
        return eid


RepoFactory = Callable[[Connection], Any]

PLATFORM_REPOS: dict[str, RepoFactory] = {
    "idempotency": SqlIdempotencyStore,
    "attempts": SqlAttemptLedger,
    "audit": SqlAuditWriter,
    "outbox": SqlOutboxWriter,
}


class SqlUnitOfWork:
    """One connection + transaction; repositories are bound to it lazily by attribute name."""

    def __init__(self, engine: Engine, factories: dict[str, RepoFactory]):
        self._engine = engine
        self._factories = factories
        self._conn: Connection | None = None
        self._tx = None
        self._repos: dict[str, Any] = {}

    def __enter__(self):
        self._conn = self._engine.connect()
        self._tx = self._conn.begin()
        return self

    def __getattr__(self, name: str):
        factories = self.__dict__.get("_factories", {})
        if name not in factories:
            raise AttributeError(name)
        if self._conn is None:
            raise RuntimeError("unit of work used outside its `with` block")
        repo = self._repos.get(name)
        if repo is None:
            repo = self._repos[name] = factories[name](self._conn)
        return repo

    def commit(self) -> None:
        assert self._tx is not None
        self._tx.commit()

    def __exit__(self, *exc):
        try:
            if self._tx is not None and self._tx.is_active:
                self._tx.rollback()
        finally:
            if self._conn is not None:
                self._conn.close()
            self._conn = self._tx = None
            self._repos = {}


class SqlUnitOfWorkFactory:
    def __init__(self, engine: Engine, factories: dict[str, RepoFactory]):
        self.engine = engine
        self.factories = {**PLATFORM_REPOS, **factories}

    def __call__(self) -> SqlUnitOfWork:
        return SqlUnitOfWork(self.engine, self.factories)
