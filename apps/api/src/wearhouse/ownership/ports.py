from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from ..catalogue.ports import RevisionReader
from ..platform.pagination import Position
from ..catalogue.ports import SizeRepository
from ..platform.ports import AttemptLedger, AuditWriter, IdempotencyStore, OutboxWriter, UnitOfWork


@dataclass(frozen=True)
class UnitRow:
    id: uuid.UUID
    product_id: uuid.UUID
    acquisition_revision_id: uuid.UUID
    public_serial: str
    status: str
    size: dict | None = None  # {system, code, label} snapshot (add-wearhouse-sizes)


@dataclass(frozen=True)
class CredentialRow:
    id: uuid.UUID
    unit_id: uuid.UUID
    status: str
    audience_user_id: uuid.UUID | None


@dataclass(frozen=True)
class DeliveryRow:
    id: uuid.UUID
    unit_id: uuid.UUID
    credential_id: uuid.UUID
    actor_id: uuid.UUID
    key_id: str | None
    nonce: bytes | None
    ciphertext: bytes | None
    expires_at: datetime
    erased_at: datetime | None
    erase_reason: str | None


@dataclass(frozen=True)
class OwnedItemRow:
    id: uuid.UUID
    user_id: uuid.UUID
    unit_id: uuid.UUID
    public_serial: str
    acquisition_revision_id: uuid.UUID
    presentation: dict
    claimed_at: datetime
    created_at: datetime
    revoked_at: datetime | None = None      # sandbox entitlement revoked (complete-wearhouse-tdd)
    revoked_reason: str | None = None


class OwnershipRepository(Protocol):
    def revoke_item_by_unit(self, unit_id: uuid.UUID, reason: str, now: datetime): ...
    def insert_unit(self, *, unit_id: uuid.UUID, product_id: uuid.UUID, revision_id: uuid.UUID, serial: str,
                    issued_by: uuid.UUID, now: datetime, size: dict | None = None) -> None: ...

    def insert_credential(self, *, credential_id: uuid.UUID, unit_id: uuid.UUID, digest: str,
                          audience_user_id: uuid.UUID | None, issued_by: uuid.UUID, now: datetime) -> None: ...

    def insert_delivery(self, *, delivery_id: uuid.UUID, unit_id: uuid.UUID, credential_id: uuid.UUID,
                        actor_id: uuid.UUID, key_id: str, nonce: bytes, ciphertext: bytes, expires_at: datetime,
                        now: datetime) -> None: ...

    def get_delivery(self, delivery_id: uuid.UUID) -> DeliveryRow | None: ...

    def erase_deliveries(self, unit_id: uuid.UUID, reason: str, now: datetime) -> int: ...

    def erase_expired_deliveries(self, now: datetime) -> int: ...

    def lock_unit(self, unit_id: uuid.UUID) -> UnitRow | None: ...

    def unit_by_serial(self, serial: str) -> UnitRow | None: ...

    def active_credential(self, unit_id: uuid.UUID) -> CredentialRow | None: ...

    def revoke_credential(self, credential_id: uuid.UUID, now: datetime) -> None: ...

    def lock_credential_by_digest(self, digest: str) -> CredentialRow | None: ...

    def mark_credential_redeemed(self, credential_id: uuid.UUID, now: datetime) -> bool: ...

    def mark_unit_claimed(self, unit_id: uuid.UUID, now: datetime) -> bool: ...

    # add-wearhouse-sandbox-commerce: fulfilment / cancellation (lock order: credentials, then units)
    def lock_active_credentials(self, unit_ids: list[uuid.UUID]) -> list[CredentialRow]: ...

    def lock_units(self, unit_ids: list[uuid.UUID]) -> list[UnitRow]: ...

    def units(self, unit_ids: list[uuid.UUID]) -> list[UnitRow]: ...

    def mark_unit_retired(self, unit_id: uuid.UUID) -> bool: ...

    def units_of_product(self, product_id: uuid.UUID, after: Position | None, limit: int) -> list[dict]:
        """Staff unit list: serial, status, times. Never keys or owners."""

    def insert_owned_item(self, *, item_id: uuid.UUID, user_id: uuid.UUID, unit_id: uuid.UUID,
                          revision_id: uuid.UUID, presentation: dict, now: datetime) -> None: ...

    def insert_event(self, *, unit_id: uuid.UUID, item_id: uuid.UUID | None, user_id: uuid.UUID | None,
                     event_type: str, details: dict, now: datetime) -> None: ...

    def list_items(self, user_id: uuid.UUID, after: Position | None, limit: int) -> list[OwnedItemRow]: ...

    def get_item(self, user_id: uuid.UUID, item_id: uuid.UUID) -> OwnedItemRow | None: ...


@dataclass(frozen=True)
class ItemPresentation:
    """What other viewers may see of an owned item: product presentation only (no serial/ids/exact times)."""

    position: Position  # keyset position, only ever placed inside sealed cursors
    product: dict


class OwnedItemReader(Protocol):
    """Ownership's read interface for other modules (accounts)."""

    def presentations(self, user_id: uuid.UUID, after: Position | None, limit: int) -> list[ItemPresentation]: ...

    def private_items(self, user_id: uuid.UUID) -> list[OwnedItemRow]: ...

    def active_items(self, user_id: uuid.UUID) -> list[OwnedItemRow]: ...


class UserDirectory(Protocol):
    def exists(self, user_id: uuid.UUID) -> bool: ...


class OwnershipUoW(UnitOfWork, Protocol):
    ownership: OwnershipRepository
    revisions: RevisionReader
    sizes: SizeRepository
    users: UserDirectory
    idempotency: IdempotencyStore
    attempts: AttemptLedger
    audit: AuditWriter
    outbox: OutboxWriter
