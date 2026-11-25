"""Identity application service: authenticate bearer tokens and manage server-side role grants."""
from __future__ import annotations

import logging
import uuid
from typing import Callable

from ..platform.clock import Clock, utcnow
from ..platform.errors import ApiError, unauthenticated
from .domain import Principal, Role, parse_roles
from .ports import IdentityUoW, InvalidToken, TokenVerifier

MAX_TOKEN_LENGTH = 8192
log = logging.getLogger("wearhouse.identity")


def suspended() -> ApiError:
    return ApiError(403, "ACCOUNT_SUSPENDED", "This account is suspended.")


class IdentityService:
    def __init__(self, uow_factory: Callable[[], IdentityUoW], verifier: TokenVerifier, clock: Clock = utcnow):
        self.uow_factory = uow_factory
        self.verifier = verifier
        self.clock = clock

    def authenticate(self, authorization: str | None) -> Principal:
        """Only the Authorization: Bearer header is consulted. No header, query or body field can
        select a test mode, an owner or a role."""
        if not authorization:
            log.info("request without a bearer token")
            raise unauthenticated()
        scheme, _, token = authorization.partition(" ")
        token = token.strip()
        if scheme.lower() != "bearer" or not token or len(token) > MAX_TOKEN_LENGTH:
            raise unauthenticated()
        try:
            ident = self.verifier.verify(token)
        except InvalidToken as exc:
            log.warning("bearer token rejected: %s", exc.reason)  # the reason only, never the token
            raise unauthenticated() from None
        if ident.hints.banned:  # broker claims may only deny; checked before any account is created
            raise suspended()
        with self.uow_factory() as uow:
            user_id, _created = uow.identity.resolve(ident.issuer, ident.subject, self.clock())
            not_before = uow.identity.tokens_not_before(user_id)
            roles = uow.identity.roles(user_id)
            uow.commit()
        if not_before is not None and (ident.issued_at is None or ident.issued_at <= not_before):
            log.warning("bearer token rejected: revoked")
            raise unauthenticated()  # revoked by sign out everywhere / deletion; same shape as any invalid token
        return Principal(user_id=user_id, issuer=ident.issuer, subject=ident.subject, roles=parse_roles(roles),
                         issued_at=ident.issued_at, hints=ident.hints)

    @staticmethod
    def describe(p: Principal) -> dict:
        return {"user_id": str(p.user_id), "roles": sorted(r.value for r in p.roles),
                "capabilities": sorted(c.value for c in p.capabilities)}

    # --- restricted bootstrap (CLI only; there is no HTTP grant endpoint) ---------------------
    def operator_principal(self, *, issuer: str, subject: str) -> Principal:
        """CLI only: act as an EXISTING account with its server-granted roles (never creates accounts or roles)."""
        with self.uow_factory() as uow:
            user_id = uow.identity.find(issuer, subject)
            roles = uow.identity.roles(user_id) if user_id else frozenset()
        if user_id is None:
            raise LookupError(f"no account for {issuer} / {subject}; sign in once or use grant-role first")
        return Principal(user_id=user_id, issuer=issuer, subject=subject, roles=parse_roles(roles))

    def grant_role(self, *, issuer: str, subject: str, role: str, granted_by: str) -> tuple[uuid.UUID, bool]:
        r = Role(role)
        with self.uow_factory() as uow:
            user_id, _ = uow.identity.resolve(issuer, subject, self.clock())
            changed = uow.identity.grant(user_id, r.value, granted_by, self.clock())
            uow.audit.record(actor_id=None, action="identity.role_granted", target_type="user",
                             target_id=str(user_id), details={"role": r.value, "granted_by": granted_by})
            uow.commit()
        return user_id, changed

    def revoke_role(self, *, issuer: str, subject: str, role: str, revoked_by: str) -> bool:
        r = Role(role)
        with self.uow_factory() as uow:
            user_id = uow.identity.find(issuer, subject)
            if user_id is None:
                return False
            changed = uow.identity.revoke(user_id, r.value)
            uow.audit.record(actor_id=None, action="identity.role_revoked", target_type="user",
                             target_id=str(user_id), details={"role": r.value, "revoked_by": revoked_by})
            uow.commit()
        return changed
