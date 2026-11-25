"""Ports for platform infrastructure. Implemented in platform/adapters, composed in bootstrap."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Protocol


@dataclass(frozen=True)
class IdempotencyRecord:
    id: uuid.UUID
    actor_id: uuid.UUID
    route: str
    idem_key: str
    request_fingerprint: str
    status: str  # processing | completed
    lease_token: uuid.UUID | None
    lease_expires_at: datetime | None
    attempt_reserved: bool
    response_status: int | None
    response_body: dict | None


class IdempotencyStore(Protocol):
    def acquire(self, *, actor_id: uuid.UUID, route: str, key: str, fingerprint: str,
                now: datetime) -> tuple[IdempotencyRecord, bool]:
        """Insert-if-absent then lock the (actor, route, key) record. Returns (record, created)."""

    def lock(self, record_id: uuid.UUID) -> IdempotencyRecord | None: ...

    def start_lease(self, record_id: uuid.UUID, token: uuid.UUID, expires_at: datetime) -> None: ...

    def mark_attempt_reserved(self, record_id: uuid.UUID) -> None: ...

    def complete(self, record_id: uuid.UUID, status: int, body: dict, now: datetime) -> None: ...

    def expire_lease(self, record_id: uuid.UUID, now: datetime) -> None: ...

    def release(self, record_id: uuid.UUID) -> None:
        """Remove a processing record that produced no effect (e.g. rate limited)."""


@dataclass(frozen=True)
class AttemptScope:
    scope: str  # actor | ip | global
    key: str
    limit: int


class AttemptLedger(Protocol):
    def reserve(self, scopes: list[AttemptScope], *, now: datetime, window: timedelta,
                idempotency_id: uuid.UUID | None) -> int | None:
        """Lock each scope bucket (fixed order) and reserve one attempt in all of them.

        Returns None when reserved, else the Retry-After seconds of the first exhausted scope
        (in which case nothing is reserved)."""


class AuditWriter(Protocol):
    def record(self, *, actor_id: uuid.UUID | None, action: str, target_type: str, target_id: str,
               details: dict[str, Any] | None = None) -> None: ...


class OutboxWriter(Protocol):
    def emit(self, *, event_type: str, aggregate_type: str, aggregate_id: uuid.UUID,
             payload: dict[str, Any]) -> uuid.UUID: ...


class UnitOfWork(Protocol):
    """One database transaction. Leaving the block without commit() rolls everything back."""

    idempotency: IdempotencyStore
    attempts: AttemptLedger
    audit: AuditWriter
    outbox: OutboxWriter

    def __enter__(self) -> "UnitOfWork": ...

    def __exit__(self, *exc: object) -> None: ...

    def commit(self) -> None: ...


class UnitOfWorkFactory(Protocol):
    def __call__(self) -> UnitOfWork: ...


class FaultHook(Protocol):
    """Called at named points inside transactions. Production uses a no-op; only the test factory injects one."""

    def __call__(self, point: str) -> None: ...


def no_faults(point: str) -> None:  # noqa: ARG001 - deliberate no-op
    return None
