"""Accounts ports. Other modules are reached only through their ports (identity.AccountDirectory,
ownership.OwnedItemReader); accounts never touches their tables."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from ..identity.ports import AccountDirectory
from ..ownership.ports import OwnedItemReader
from ..platform.pagination import Position
from ..identity.ports import IdentityRepository
from ..platform.ports import AttemptLedger, AuditWriter, IdempotencyStore, OutboxWriter, UnitOfWork


@dataclass(frozen=True)
class ProfileRow:
    user_id: uuid.UUID
    handle: str | None
    display_name: str
    bio: str
    avatar_kind: str
    avatar_preset: str | None
    avatar_url: str | None
    handle_changed_at: datetime | None
    created_at: datetime


@dataclass(frozen=True)
class PrivacyRow:
    profile: str
    wardrobe: str
    friends_list: str


@dataclass(frozen=True)
class Relationship:
    blocked: bool  # either direction
    friends: bool


@dataclass(frozen=True)
class RequestRow:
    id: uuid.UUID
    from_user: uuid.UUID
    to_user: uuid.UUID
    status: str
    created_at: datetime


@dataclass(frozen=True)
class ListedAccount:
    """A row of a social list: the other account's public card plus a keyset position."""

    position: Position
    user_id: uuid.UUID
    handle: str | None
    display_name: str
    avatar_kind: str
    avatar_preset: str | None
    avatar_url: str | None
    request_id: uuid.UUID | None = None


class HandleTaken(Exception):
    pass


class AccountsRepository(Protocol):
    # settings + security events (add-wearhouse-settings-security)
    def settings(self, user_id: uuid.UUID) -> tuple[dict, int, datetime | None]: ...
    def settings_for(self, user_ids: list[uuid.UUID]) -> dict[uuid.UUID, dict]: ...
    def save_settings(self, user_id: uuid.UUID, values: dict, expected_version: int, now: datetime) -> int | None: ...
    def erase_settings(self, user_id: uuid.UUID) -> None: ...
    def security_events(self, user_id: uuid.UUID, actions: tuple[str, ...], limit: int) -> list[dict]: ...
    # profiles
    def ensure_profile(self, user_id: uuid.UUID, display_name: str, now: datetime) -> ProfileRow: ...
    def get_profile(self, user_id: uuid.UUID) -> ProfileRow | None: ...
    def profile_by_handle(self, handle: str) -> ProfileRow | None: ...
    def lock_profiles(self, *user_ids: uuid.UUID) -> dict[uuid.UUID, ProfileRow]: ...
    def update_profile(self, user_id: uuid.UUID, values: dict, now: datetime) -> ProfileRow:
        """Raises HandleTaken when a handle collides with another account."""
    def get_hold(self, handle: str) -> tuple[uuid.UUID | None, datetime] | None: ...
    def put_hold(self, handle: str, held_for: uuid.UUID | None, available_at: datetime) -> None: ...
    def delete_hold(self, handle: str) -> None: ...
    def holds_for(self, user_id: uuid.UUID) -> list[tuple[str, datetime]]: ...
    def search(self, prefix: str, exact: bool, viewer: uuid.UUID, limit: int) -> list[ProfileRow]: ...
    # privacy
    def ensure_privacy(self, user_id: uuid.UUID) -> PrivacyRow: ...
    def set_privacy(self, user_id: uuid.UUID, row: PrivacyRow, now: datetime) -> PrivacyRow: ...
    # relationships
    def relationship(self, a: uuid.UUID, b: uuid.UUID) -> Relationship: ...
    def pending(self, from_user: uuid.UUID, to_user: uuid.UUID) -> RequestRow | None: ...
    def get_request(self, request_id: uuid.UUID, *, lock: bool = False) -> RequestRow | None: ...
    def create_request(self, from_user: uuid.UUID, to_user: uuid.UUID, now: datetime) -> RequestRow: ...
    def set_request_status(self, request_id: uuid.UUID, status: str, now: datetime) -> None: ...
    def count_pending_outgoing(self, user_id: uuid.UUID) -> int: ...
    def list_requests(self, user_id: uuid.UUID, direction: str, after: Position | None,
                      limit: int) -> list[ListedAccount]: ...
    def accepted_outgoing(self, user_id: uuid.UUID, since: datetime, limit: int) -> list[ListedAccount]:
        """Requests the user SENT that were accepted since `since` (newest first; social notifications)."""
    def add_friendship(self, a: uuid.UUID, b: uuid.UUID, now: datetime) -> bool: ...
    def remove_friendship(self, a: uuid.UUID, b: uuid.UUID) -> bool: ...
    def count_friends(self, user_id: uuid.UUID) -> int: ...
    def list_friends(self, user_id: uuid.UUID, after: Position | None, limit: int, *, owner_view: bool,
                     viewer: uuid.UUID | None) -> list[ListedAccount]:
        """owner_view lists everyone; otherwise friends with private profiles and friends in a block
        relationship with `viewer` are omitted."""
    def delete_requests_between(self, a: uuid.UUID, b: uuid.UUID) -> int: ...
    def add_block(self, blocker: uuid.UUID, blocked: uuid.UUID, now: datetime) -> bool: ...
    def remove_block(self, blocker: uuid.UUID, blocked: uuid.UUID) -> bool: ...
    def count_blocks(self, user_id: uuid.UUID) -> int: ...
    def is_blocking(self, blocker: uuid.UUID, blocked: uuid.UUID) -> bool: ...
    def list_blocks(self, user_id: uuid.UUID, after: Position | None, limit: int) -> list[ListedAccount]: ...
    # lifecycle
    def delete_account_data(self, user_id: uuid.UUID) -> None: ...


class AccountsUoW(UnitOfWork, Protocol):
    accounts: AccountsRepository
    identity: IdentityRepository  # role administration (add-wearhouse-object-management)
    owned: OwnedItemReader
    directory: AccountDirectory
    idempotency: IdempotencyStore
    attempts: AttemptLedger
    audit: AuditWriter
    outbox: OutboxWriter
