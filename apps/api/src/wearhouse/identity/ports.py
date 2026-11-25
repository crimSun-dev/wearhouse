from __future__ import annotations

import uuid
from datetime import datetime
from typing import Protocol

from ..platform.ports import AuditWriter, UnitOfWork
from .domain import VerifiedIdentity


class InvalidToken(Exception):
    """Token failed verification. Carries a coarse reason for tests/metrics, never token contents."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class TokenVerifier(Protocol):
    def verify(self, token: str) -> VerifiedIdentity: ...


class IdentityRepository(Protocol):
    def resolve(self, issuer: str, subject: str, now: datetime) -> tuple[uuid.UUID, bool]:
        """Return the local user for (issuer, subject), creating exactly one if absent."""

    def find(self, issuer: str, subject: str) -> uuid.UUID | None: ...

    def roles(self, user_id: uuid.UUID) -> frozenset[str]: ...

    def grant(self, user_id: uuid.UUID, role: str, granted_by: str, now: datetime) -> bool: ...

    def revoke(self, user_id: uuid.UUID, role: str) -> bool: ...

    def staff(self) -> dict[uuid.UUID, frozenset[str]]:
        """Every account holding at least one role (role administration)."""

    def lock_admins(self) -> list[uuid.UUID]:
        """Admin user ids, row-locked (last-admin protection)."""

    def tokens_not_before(self, user_id: uuid.UUID) -> datetime | None: ...


class AccountDirectory(Protocol):
    """Identity's account-lifecycle interface for other modules (accounts): revocation and tombstoning."""

    def lock(self, user_id: uuid.UUID) -> dict | None:
        """Lock the live account row; returns {"created_at"} or None if absent/deleted."""

    def timeline(self, user_id: uuid.UUID) -> dict | None:
        """Read-only (no lock): {"created_at", "tokens_not_before"} of a live account."""

    def revoke_tokens(self, user_id: uuid.UUID, now: datetime) -> None: ...

    def tombstone(self, user_id: uuid.UUID, now: datetime) -> None:
        """Remove subject mappings and role grants, mark deleted, clear personal data, revoke tokens."""


class IdentityUoW(UnitOfWork, Protocol):
    identity: IdentityRepository
    audit: AuditWriter
