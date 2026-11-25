"""Identity domain: verified principals and server-owned role/capability policy."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from ..platform.errors import forbidden


class Role(str, Enum):
    CATALOGUE_EDITOR = "catalogue_editor"
    INVENTORY_MANAGER = "inventory_manager"
    MODERATOR = "moderator"  # complete-wearhouse-tdd: shared-look moderation only (no keys, orders or wardrobes)
    ADMIN = "admin"


class Capability(str, Enum):
    INGEST_PRODUCTS = "catalogue:ingest"
    ISSUE_UNITS = "inventory:issue"
    REISSUE_CREDENTIALS = "inventory:reissue"
    REDEEM = "ownership:redeem"
    READ_OWN_ITEMS = "ownership:read_own"
    MANAGE_OFFERS = "commerce:offers"
    MANAGE_MEDIA = "catalogue:media"
    MANAGE_ROLES = "identity:manage_roles"
    VIEW_ORDERS = "commerce:orders"
    MODERATE = "social:moderate"
    VIEW_OPS = "ops:read"  # admin only (complete-wearhouse-tdd)


CUSTOMER_CAPABILITIES = frozenset({Capability.REDEEM, Capability.READ_OWN_ITEMS})
ROLE_CAPABILITIES: dict[Role, frozenset[Capability]] = {
    Role.CATALOGUE_EDITOR: frozenset({Capability.INGEST_PRODUCTS, Capability.MANAGE_OFFERS, Capability.MANAGE_MEDIA}),
    Role.INVENTORY_MANAGER: frozenset({Capability.ISSUE_UNITS, Capability.REISSUE_CREDENTIALS, Capability.VIEW_ORDERS}),
    Role.MODERATOR: frozenset({Capability.MODERATE}),
    Role.ADMIN: frozenset(set(Capability) - {Capability.REDEEM, Capability.READ_OWN_ITEMS}),  # every staff capability
}


@dataclass(frozen=True)
class IdentityHints:
    """Broker-supplied profile claims. Never authority: they can seed a display name, offer an avatar, or deny."""

    name: str | None = None
    image: str | None = None  # https only
    banned: bool = False


@dataclass(frozen=True)
class VerifiedIdentity:
    """Output of token verification: only issuer and subject carry authority, never other claims."""

    issuer: str
    subject: str
    issued_at: datetime | None = None
    hints: IdentityHints = field(default_factory=IdentityHints)


@dataclass(frozen=True)
class Principal:
    user_id: uuid.UUID
    issuer: str
    subject: str
    roles: frozenset[Role]
    issued_at: datetime | None = None  # token iat: revocation and recent-authentication checks
    hints: IdentityHints = field(default_factory=IdentityHints)

    @property
    def capabilities(self) -> frozenset[Capability]:
        caps = set(CUSTOMER_CAPABILITIES)
        for r in self.roles:
            caps |= ROLE_CAPABILITIES[r]
        return frozenset(caps)

    def has(self, cap: Capability) -> bool:
        return cap in self.capabilities


def require(principal: Principal, cap: Capability) -> None:
    if not principal.has(cap):
        raise forbidden()


def parse_roles(values: set[str] | frozenset[str]) -> frozenset[Role]:
    return frozenset(Role(v) for v in values if v in Role._value2member_map_)
