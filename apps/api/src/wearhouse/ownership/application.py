"""Ownership application services: issuance, reissue, public discovery, private redemption, owned reads."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import timedelta
from typing import Callable

from ..catalogue.application import SizeIndex
from ..catalogue.ports import RevisionSummary
from ..identity.domain import Capability, Principal, require
from ..platform.clock import Clock, utcnow
from ..platform.crypto import KeyRing
from ..platform.errors import ApiError, FieldError, conflict, not_found, rate_limited, validation_failed
from ..platform.idempotency import IdempotentExecutor, Outcome
from ..platform.ids import new_id
from ..platform.pagination import Position, check_limit, decode, encode
from ..platform.ports import AttemptScope, FaultHook, no_faults
from .domain import (CRED_ACTIVE, INVALID_ACTIVATION_CODE, INVALID_ACTIVATION_MESSAGE, UNIT_CLAIMED, UNIT_ISSUED, key_digest,
                     new_activation_key, new_public_serial, normalize_key, valid_serial)
from .ports import DeliveryRow, OwnedItemRow, OwnershipUoW

ROUTE_ISSUE = "POST /api/v2/admin/unit-batches"
ROUTE_REISSUE = "POST /api/v2/admin/units/{id}/reissue"
ROUTE_REDEEM = "POST /api/v2/redemptions"
ACTOR_ATTEMPTS_PER_HOUR = 10
ATTEMPT_WINDOW = timedelta(hours=1)
ITEMS_SCOPE = "me.items"


@dataclass(frozen=True)
class AdmissionPolicy:
    actor_limit: int | None = ACTOR_ATTEMPTS_PER_HOUR  # None only for the RQ3 validation corpus (never deployed)
    ip_limit: int | None = 60
    global_limit: int | None = 5000


def _invalid_body() -> dict:
    return {"code": INVALID_ACTIVATION_CODE, "message": INVALID_ACTIVATION_MESSAGE}


def _aad(delivery_id: uuid.UUID, actor_id: uuid.UUID, credential_id: uuid.UUID) -> bytes:
    return b"|".join(x.bytes for x in (delivery_id, actor_id, credential_id))


def _product_view(rev: RevisionSummary) -> dict:
    return {"id": str(rev.product_id), "name": rev.product_name, "category": rev.category, "facts": rev.facts}


class _CredentialMinter:
    def __init__(self, ring: KeyRing, clock: Clock, delivery_ttl: timedelta):
        self.ring, self.clock, self.ttl = ring, clock, delivery_ttl

    def mint(self, uow: OwnershipUoW, *, unit_id, actor_id, audience_user_id) -> tuple[uuid.UUID, uuid.UUID]:
        now = self.clock()
        key = new_activation_key()
        credential_id, delivery_id = new_id(), new_id()
        uow.ownership.insert_credential(credential_id=credential_id, unit_id=unit_id,
                                        digest=key_digest(normalize_key(key)), audience_user_id=audience_user_id,
                                        issued_by=actor_id, now=now)
        key_id, nonce, ct = self.ring.seal(key.encode("ascii"), _aad(delivery_id, actor_id, credential_id))
        uow.ownership.insert_delivery(delivery_id=delivery_id, unit_id=unit_id, credential_id=credential_id,
                                      actor_id=actor_id, key_id=key_id, nonce=nonce, ciphertext=ct,
                                      expires_at=now + self.ttl, now=now)
        return credential_id, delivery_id

    def open(self, d: DeliveryRow | None, actor_id: uuid.UUID) -> dict:
        now = self.clock()
        if d is None or d.actor_id != actor_id:
            return {"status": "unavailable", "reason": "not_found"}
        if d.erased_at is not None:
            return {"status": "unavailable", "reason": d.erase_reason or "erased"}
        if d.expires_at <= now:
            return {"status": "expired", "expired_at": d.expires_at.isoformat()}
        plaintext = self.ring.open(d.key_id or "", d.nonce or b"", d.ciphertext or b"",
                                   _aad(d.id, actor_id, d.credential_id))
        if plaintext is None:
            return {"status": "unavailable", "reason": "key_rotated"}
        return {"status": "available", "activation_key": plaintext.decode("ascii"),
                "expires_at": d.expires_at.isoformat()}


class IssuanceService:
    def __init__(self, uow_factory: Callable[[], OwnershipUoW], ring: KeyRing, *, clock: Clock = utcnow,
                 delivery_ttl_s: int = 86400, lease_s: float = 15.0, faults: FaultHook = no_faults):
        self.uow_factory = uow_factory
        self.ring = ring
        self.clock = clock
        self.faults = faults
        self.minter = _CredentialMinter(ring, clock, timedelta(seconds=delivery_ttl_s))
        self.executor = IdempotentExecutor(uow_factory, ring, clock, lease_s=lease_s)

    def issue(self, principal: Principal, *, product_id: uuid.UUID, audience_user_id: uuid.UUID | None,
              idem_key: str, size: str | None = None) -> Outcome:
        require(principal, Capability.ISSUE_UNITS)
        body = {"product_id": str(product_id), "quantity": 1,
                "audience_user_id": str(audience_user_id) if audience_user_id else None}
        if size is not None:
            body["size"] = size

        def execute(uow: OwnershipUoW, rec):
            rev = uow.revisions.current_for_product(product_id)
            if rev is None:
                raise not_found("Product not found.")
            if rev.catalogue_status != "active":
                raise conflict("PRODUCT_RETIRED", "Units cannot be issued for a retired product.")
            if audience_user_id is not None and not uow.users.exists(audience_user_id):
                raise validation_failed([FieldError("body.audience_user_id", "unknown_user", "Unknown user.")])
            unit_size = None
            if size is not None:  # optional: one of the product's sizes (add-wearhouse-sizes)
                offered = {x.code: x for x in uow.sizes.product_sizes([product_id]).get(product_id, [])}
                if size not in offered:
                    raise validation_failed([FieldError("body.size", "unknown_size",
                                                        f"This product does not come in size {size}.")])
                unit_size = SizeIndex.load(uow.sizes).out(offered[size].system, size)
                unit_size = {k: unit_size[k] for k in ("system", "code", "label")}
            now = self.clock()
            unit_id, serial = new_id(), new_public_serial()
            uow.ownership.insert_unit(unit_id=unit_id, product_id=product_id, revision_id=rev.revision_id,
                                      serial=serial, issued_by=principal.user_id, now=now, size=unit_size)
            self.faults("issue.after_unit")
            credential_id, delivery_id = self.minter.mint(uow, unit_id=unit_id, actor_id=principal.user_id,
                                                          audience_user_id=audience_user_id)
            uow.audit.record(actor_id=principal.user_id, action="ownership.unit_issued", target_type="garment_unit",
                             target_id=str(unit_id), details={"product_id": str(product_id),
                                                              "revision_no": rev.revision_no,
                                                              "actor_bound": audience_user_id is not None})
            uow.outbox.emit(event_type="ownership.unit_issued", aggregate_type="garment_unit", aggregate_id=unit_id,
                            payload={"product_id": str(product_id), "revision_id": str(rev.revision_id)})
            return 201, {"unit_id": str(unit_id), "public_serial": serial, "product_id": str(product_id),
                         "acquisition_revision_id": str(rev.revision_id), "revision_no": rev.revision_no,
                         "actor_bound": audience_user_id is not None,
                         "_credential_id": str(credential_id), "_delivery_id": str(delivery_id)}

        out = self.executor.run(actor_id=principal.user_id, route=ROUTE_ISSUE, key=idem_key, body=body,
                                execute=execute)
        return self._render(principal, out)

    def reissue(self, principal: Principal, *, unit_id: uuid.UUID, idem_key: str) -> Outcome:
        require(principal, Capability.REISSUE_CREDENTIALS)

        def execute(uow: OwnershipUoW, rec):
            unit = uow.ownership.lock_unit(unit_id)
            if unit is None:
                raise not_found("Unit not found.")
            if unit.status != UNIT_ISSUED:
                raise conflict("UNIT_ALREADY_CLAIMED", "A claimed unit's credential cannot be reissued.")
            now = self.clock()
            old = uow.ownership.active_credential(unit_id)
            if old is not None:
                uow.ownership.revoke_credential(old.id, now)
            uow.ownership.erase_deliveries(unit_id, "revoked", now)
            credential_id, delivery_id = self.minter.mint(
                uow, unit_id=unit_id, actor_id=principal.user_id,
                audience_user_id=old.audience_user_id if old else None)
            uow.ownership.insert_event(unit_id=unit_id, item_id=None, user_id=None, event_type="credential_reissued",
                                       details={"revoked_credential_id": str(old.id) if old else None,
                                                "credential_id": str(credential_id)}, now=now)
            uow.audit.record(actor_id=principal.user_id, action="ownership.credential_reissued",
                             target_type="garment_unit", target_id=str(unit_id),
                             details={"revoked_credential_id": str(old.id) if old else None})
            uow.outbox.emit(event_type="ownership.credential_reissued", aggregate_type="garment_unit",
                            aggregate_id=unit_id, payload={"credential_id": str(credential_id)})
            return 201, {"unit_id": str(unit_id), "public_serial": unit.public_serial,
                         "product_id": str(unit.product_id), "acquisition_revision_id": str(unit.acquisition_revision_id),
                         "actor_bound": bool(old and old.audience_user_id),
                         "_credential_id": str(credential_id), "_delivery_id": str(delivery_id)}

        out = self.executor.run(actor_id=principal.user_id, route=ROUTE_REISSUE.replace("{id}", str(unit_id)),
                                key=idem_key, body={"unit_id": str(unit_id)}, execute=execute)
        return self._render(principal, out)

    def _render(self, principal: Principal, out: Outcome) -> Outcome:
        """Attach the restricted delivery (decrypted only for the issuing actor) to the stored result."""
        if out.status >= 400:
            return out
        body = {k: v for k, v in out.body.items() if not k.startswith("_")}
        with self.uow_factory() as uow:
            d = uow.ownership.get_delivery(uuid.UUID(out.body["_delivery_id"]))
            body["delivery"] = self.minter.open(d, principal.user_id)
            uow.audit.record(actor_id=principal.user_id, action="ownership.delivery_accessed",
                             target_type="issuance_delivery", target_id=out.body["_delivery_id"],
                             details={"outcome": body["delivery"]["status"], "replayed": out.replayed})
            uow.commit()
        return Outcome(out.status, body, out.replayed)

    def units(self, principal: Principal, *, product_id: uuid.UUID, limit: int | None, cursor: str | None) -> dict:
        """Staff unit list (inventory:issue): serial, status and times only, never keys or owners."""
        require(principal, Capability.ISSUE_UNITS)
        n = check_limit(limit)
        scope = f"admin.units.{product_id}"
        after = decode(self.ring, cursor, principal=principal.user_id, scope=scope, filter_key="") if cursor else None
        with self.uow_factory() as uow:
            rows = uow.ownership.units_of_product(product_id, after, n + 1)
        more, rows = len(rows) > n, rows[:n]
        nxt = encode(self.ring, principal=principal.user_id, scope=scope, filter_key="",
                     pos=Position(rows[-1]["created_at"], rows[-1]["id"])) if more else None
        return {"items": [{"unit_id": str(r["id"]), "public_serial": r["public_serial"], "status": r["status"],
                           "created_at": r["created_at"].isoformat(),
                           "claimed_at": r["claimed_at"].isoformat() if r["claimed_at"] else None,
                           "size": ({"system": r["size_system"], "code": r["size_code"], "label": r["size_label"]}
                                    if r["size_code"] else None)} for r in rows],
                "next_cursor": nxt}

    def purge_expired_deliveries(self) -> int:
        with self.uow_factory() as uow:
            n = uow.ownership.erase_expired_deliveries(self.clock())
            uow.commit()
        return n


class DiscoveryService:
    """Anonymous public tag lookup. Read-only: never creates or changes ownership state."""

    def __init__(self, uow_factory: Callable[[], OwnershipUoW]):
        self.uow_factory = uow_factory

    def lookup(self, serial: str) -> dict:
        if not valid_serial(serial):
            raise not_found("Item not found.")
        with self.uow_factory() as uow:
            unit = uow.ownership.unit_by_serial(serial)
            rev = ((uow.revisions.published_for_product(unit.product_id)
                    or uow.revisions.current_for_product(unit.product_id)) if unit else None)
        if unit is None or rev is None:
            raise not_found("Item not found.")
        return {"public_serial": unit.public_serial, "product": _product_view(rev),
                "catalogue_status": rev.catalogue_status,
                "source": {"namespace": rev.source_namespace, "external_id": rev.external_id}}


class RedemptionService:
    def __init__(self, uow_factory: Callable[[], OwnershipUoW], ring: KeyRing, *, clock: Clock = utcnow,
                 policy: AdmissionPolicy = AdmissionPolicy(), lease_s: float = 15.0, faults: FaultHook = no_faults):
        self.uow_factory = uow_factory
        self.clock = clock
        self.policy = policy
        self.faults = faults
        self.executor = IdempotentExecutor(uow_factory, ring, clock, lease_s=lease_s)

    def _scopes(self, principal: Principal, client_ip: str | None) -> list[AttemptScope]:
        scopes = ([AttemptScope("actor", str(principal.user_id), self.policy.actor_limit)]
                  if self.policy.actor_limit is not None else [])
        if self.policy.ip_limit is not None and client_ip:
            scopes.append(AttemptScope("ip", client_ip, self.policy.ip_limit))
        if self.policy.global_limit is not None:
            scopes.append(AttemptScope("global", "redemptions", self.policy.global_limit))
        return scopes

    def redeem(self, principal: Principal, *, activation_key: str, idem_key: str,
               client_ip: str | None) -> Outcome:
        require(principal, Capability.REDEEM)
        actor = principal.user_id
        scopes = self._scopes(principal, client_ip)

        def admit(uow: OwnershipUoW, rec) -> ApiError | None:
            if rec.attempt_reserved:  # lease takeover of an already-admitted attempt
                return None
            retry_after = uow.attempts.reserve(scopes, now=self.clock(), window=ATTEMPT_WINDOW,
                                               idempotency_id=rec.id)
            if retry_after is not None:
                return rate_limited(retry_after)
            uow.idempotency.mark_attempt_reserved(rec.id)
            return None

        def execute(uow: OwnershipUoW, rec):
            canonical = normalize_key(activation_key)
            if canonical is None:
                return 400, _invalid_body()
            cred = uow.ownership.lock_credential_by_digest(key_digest(canonical))
            if cred is None or cred.status != CRED_ACTIVE:
                return 400, _invalid_body()
            unit = uow.ownership.lock_unit(cred.unit_id)
            if unit is None or unit.status != UNIT_ISSUED:
                return 400, _invalid_body()
            if cred.audience_user_id is not None and cred.audience_user_id != actor:
                return 400, _invalid_body()
            rev = uow.revisions.by_revision(unit.acquisition_revision_id)
            now = self.clock()
            if rev is None or not uow.ownership.mark_credential_redeemed(cred.id, now):
                return 400, _invalid_body()
            self.faults("redeem.after_credential")
            uow.ownership.mark_unit_claimed(unit.id, now)
            self.faults("redeem.after_unit")
            item_id = new_id()
            presentation = {"product": _product_view(rev), "size": unit.size,
                            "acquisition": {"revision_id": str(rev.revision_id), "revision_no": rev.revision_no,
                                            "source_namespace": rev.source_namespace, "external_id": rev.external_id,
                                            "snapshot_sha256": rev.snapshot_sha256}}
            uow.ownership.insert_owned_item(item_id=item_id, user_id=actor, unit_id=unit.id,
                                            revision_id=rev.revision_id, presentation=presentation, now=now)
            self.faults("redeem.after_item")
            uow.ownership.insert_event(unit_id=unit.id, item_id=item_id, user_id=actor, event_type="claimed",
                                       details={"credential_id": str(cred.id)}, now=now)
            self.faults("redeem.after_event")
            uow.ownership.erase_deliveries(unit.id, "claimed", now)
            uow.outbox.emit(event_type="ownership.item_claimed", aggregate_type="owned_item", aggregate_id=item_id,
                            payload={"unit_id": str(unit.id), "user_id": str(actor)})
            self.faults("redeem.after_outbox")
            return 201, item_view(item_id=item_id, serial=unit.public_serial, presentation=presentation,
                                  claimed_at=now)

        return self.executor.run(actor_id=actor, route=ROUTE_REDEEM, key=idem_key,
                                 body={"activation_key": activation_key}, admit=admit, execute=execute)


def item_view(*, item_id, serial, presentation, claimed_at, revoked_at=None, revoked_reason=None) -> dict:
    return {"id": str(item_id), "public_serial": serial, "product": presentation["product"],
            "state": "revoked_sandbox" if revoked_at else "owned",
            "revoked_at": revoked_at.isoformat() if revoked_at else None, "revoked_reason": revoked_reason,
            "size": presentation.get("size"),
            "acquisition": presentation["acquisition"], "claimed_at": claimed_at.isoformat()}


def _row_view(r: OwnedItemRow) -> dict:
    return item_view(item_id=r.id, serial=r.public_serial, presentation=r.presentation, claimed_at=r.claimed_at,
                     revoked_at=r.revoked_at, revoked_reason=r.revoked_reason)


class OwnedItemsService:
    def owned_product_ids(self, principal: Principal) -> set[uuid.UUID]:
        """Products the caller currently owns (active items only), for "hide owned" filters."""
        with self.uow_factory() as uow:
            return {uuid.UUID(o.presentation["product"]["id"]) for o in uow.owned.active_items(principal.user_id)
                    if o.presentation.get("product", {}).get("id")}

    def __init__(self, uow_factory: Callable[[], OwnershipUoW], ring: KeyRing):
        self.uow_factory = uow_factory
        self.ring = ring

    def list(self, principal: Principal, *, limit: int | None, cursor: str | None) -> dict:
        require(principal, Capability.READ_OWN_ITEMS)
        n = check_limit(limit)
        after = decode(self.ring, cursor, principal=principal.user_id, scope=ITEMS_SCOPE, filter_key="") \
            if cursor else None
        with self.uow_factory() as uow:
            rows = uow.ownership.list_items(principal.user_id, after, n + 1)
        page, more = rows[:n], len(rows) > n
        nxt = encode(self.ring, principal=principal.user_id, scope=ITEMS_SCOPE, filter_key="",
                     pos=Position(page[-1].created_at, page[-1].id)) if more else None
        return {"items": [_row_view(r) for r in page], "next_cursor": nxt}

    def get(self, principal: Principal, item_id: uuid.UUID | None) -> dict:
        require(principal, Capability.READ_OWN_ITEMS)
        if item_id is None:
            raise not_found("Item not found.")
        with self.uow_factory() as uow:
            row = uow.ownership.get_item(principal.user_id, item_id)
        if row is None:  # absent and other-owner items are indistinguishable
            raise not_found("Item not found.")
        return _row_view(row)


class UnitFulfilment:
    """Operations other modules (sandbox commerce) run INSIDE their own unit of work. Credential rules stay here:
    a purchased unit gets a buyer-bound credential whose encrypted delivery only the buyer can open.
    Lock order is always credentials first, then units (the same order redemption uses), so a cancel and a claim
    racing on one unit cannot deadlock and exactly one wins."""

    def __init__(self, ring: KeyRing, clock: Clock = utcnow, delivery_ttl_s: int = 86400):
        self.clock = clock
        self.minter = _CredentialMinter(ring, clock, timedelta(seconds=delivery_ttl_s))

    def fulfil(self, uow: OwnershipUoW, *, product_id: uuid.UUID, revision_id: uuid.UUID, buyer_id: uuid.UUID,
               reference: dict, size: dict | None = None) -> dict:
        now = self.clock()
        unit_id, serial = new_id(), new_public_serial()
        uow.ownership.insert_unit(unit_id=unit_id, product_id=product_id, revision_id=revision_id, serial=serial,
                                  issued_by=buyer_id, now=now, size=size)
        _, delivery_id = self.minter.mint(uow, unit_id=unit_id, actor_id=buyer_id, audience_user_id=buyer_id)
        uow.ownership.insert_event(unit_id=unit_id, item_id=None, user_id=buyer_id, event_type="unit_purchased",
                                   details=reference, now=now)
        return {"unit_id": unit_id, "public_serial": serial, "delivery_id": delivery_id}

    def renew_key(self, uow: OwnershipUoW, *, unit_id: uuid.UUID, buyer_id: uuid.UUID) -> uuid.UUID:
        creds = uow.ownership.lock_active_credentials([unit_id])
        units = uow.ownership.lock_units([unit_id])
        if not units or units[0].status != UNIT_ISSUED:
            raise conflict("UNIT_ALREADY_CLAIMED", "Only an unclaimed unit can get a new key.")
        now = self.clock()
        for c in creds:
            uow.ownership.revoke_credential(c.id, now)
        uow.ownership.erase_deliveries(unit_id, "revoked", now)
        credential_id, delivery_id = self.minter.mint(uow, unit_id=unit_id, actor_id=buyer_id,
                                                      audience_user_id=buyer_id)
        uow.ownership.insert_event(unit_id=unit_id, item_id=None, user_id=buyer_id, event_type="credential_reissued",
                                   details={"revoked_credential_ids": [str(c.id) for c in creds],
                                            "credential_id": str(credential_id), "by": "buyer"}, now=now)
        return delivery_id

    def retire_unclaimed(self, uow: OwnershipUoW, *, unit_ids: list[uuid.UUID], actor_id: uuid.UUID,
                         reason: str) -> bool:
        """All-or-nothing: returns False (and changes nothing) when any unit is already claimed."""
        creds = uow.ownership.lock_active_credentials(unit_ids)
        units = uow.ownership.lock_units(unit_ids)
        if any(u.status == UNIT_CLAIMED for u in units):
            return False
        now = self.clock()
        for c in creds:
            uow.ownership.revoke_credential(c.id, now)
        for u in units:
            uow.ownership.erase_deliveries(u.id, "revoked", now)
            if uow.ownership.mark_unit_retired(u.id):
                uow.ownership.insert_event(unit_id=u.id, item_id=None, user_id=actor_id, event_type="unit_retired",
                                           details={"reason": reason}, now=now)
        return True

    def cancel_units(self, uow: OwnershipUoW, *, unit_ids: list[uuid.UUID], actor_id: uuid.UUID,
                     reason: str) -> dict:
        """Sandbox cancellation (TDD §10.2): revoke every live key; retire unclaimed units; mark claimed items
        `revoked_sandbox` (audited ownership event + outbox). Same lock order as redemption (credentials, then units),
        so a racing claim and cancel resolve to one consistent outcome."""
        creds = uow.ownership.lock_active_credentials(unit_ids)
        units = uow.ownership.lock_units(unit_ids)
        now = self.clock()
        for c in creds:
            uow.ownership.revoke_credential(c.id, now)
        retired = revoked = 0
        for u in units:
            if u.status == UNIT_CLAIMED:
                row = uow.ownership.revoke_item_by_unit(u.id, "sandbox_order_cancelled", now)
                if row is not None:
                    revoked += 1
                    uow.ownership.insert_event(unit_id=u.id, item_id=row.id, user_id=actor_id, event_type="sandbox_revoked",
                                               details={"reason": reason}, now=now)
                    uow.outbox.emit(event_type="ownership.item_revoked", aggregate_type="owned_item", aggregate_id=row.id,
                                    payload={"reason": "sandbox_order_cancelled"})
                continue
            uow.ownership.erase_deliveries(u.id, "revoked", now)
            if uow.ownership.mark_unit_retired(u.id):
                retired += 1
                uow.ownership.insert_event(unit_id=u.id, item_id=None, user_id=actor_id, event_type="unit_retired",
                                           details={"reason": reason}, now=now)
        return {"retired": retired, "revoked": revoked}

    def unit_states(self, uow: OwnershipUoW, unit_ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
        return {u.id: u.status for u in uow.ownership.units(unit_ids)}

    def delivery_state(self, uow: OwnershipUoW, *, delivery_id: uuid.UUID | None, buyer_id: uuid.UUID) -> dict:
        """Delivery status WITHOUT the key (receipts, lists): nothing secret leaves, so nothing is audited."""
        d = uow.ownership.get_delivery(delivery_id) if delivery_id else None
        if d is None or d.actor_id != buyer_id:
            return {"status": "unavailable", "reason": "not_found"}
        if d.erased_at is not None:
            return {"status": "unavailable", "reason": d.erase_reason or "erased"}
        if d.expires_at <= self.clock():
            return {"status": "expired", "expired_at": d.expires_at.isoformat()}
        return {"status": "available", "expires_at": d.expires_at.isoformat()}

    def open_delivery(self, uow: OwnershipUoW, *, delivery_id: uuid.UUID | None, buyer_id: uuid.UUID) -> dict:
        d = uow.ownership.get_delivery(delivery_id) if delivery_id else None
        out = self.minter.open(d, buyer_id)
        if d is not None:
            uow.audit.record(actor_id=buyer_id, action="ownership.delivery_accessed", target_type="issuance_delivery",
                             target_id=str(delivery_id), details={"outcome": out["status"], "via": "order_receipt"})
        return out


class StarterKit:
    """Grants a new account a few official catalogue pieces when onboarding completes.

    Each piece is a real unit, issued and claimed in the onboarding transaction, so it is an ordinary owned,
    verified item (serial, provenance, acquisition revision) with no activation key ever minted for it.
    Retired or unknown products are skipped; at most twelve pieces are granted. The pieces are WEARHOUSE_STARTER_KIT
    when set, otherwise the catalogue collection with slug 'starter-kit' (editable in the staff workspace).
    A piece the account has already received from the kit is never granted again, so a grown kit tops accounts up.
    """
    MAX = 12
    COLLECTION = "starter-kit"

    def __init__(self, product_ids: tuple[str, ...] = ()):
        self.product_ids = tuple(uuid.UUID(p) for p in product_ids[: self.MAX])

    def products(self, uow: OwnershipUoW) -> tuple[uuid.UUID, ...]:
        return self.product_ids or tuple(uow.ownership.collection_products(self.COLLECTION, self.MAX))

    def grant(self, uow: OwnershipUoW, user_id: uuid.UUID, now) -> int:
        granted = 0
        received = uow.ownership.starter_products_granted(user_id)
        for product_id in self.products(uow):
            if product_id in received:
                continue
            rev = uow.revisions.current_for_product(product_id)
            if rev is None or rev.catalogue_status != "active":
                continue
            unit_id, serial = new_id(), new_public_serial()
            uow.ownership.insert_unit(unit_id=unit_id, product_id=product_id, revision_id=rev.revision_id,
                                      serial=serial, issued_by=user_id, now=now)
            uow.ownership.mark_unit_claimed(unit_id, now)
            item_id = new_id()
            presentation = {"product": _product_view(rev), "size": None,
                            "acquisition": {"revision_id": str(rev.revision_id), "revision_no": rev.revision_no,
                                            "source_namespace": rev.source_namespace, "external_id": rev.external_id,
                                            "snapshot_sha256": rev.snapshot_sha256}}
            uow.ownership.insert_owned_item(item_id=item_id, user_id=user_id, unit_id=unit_id,
                                            revision_id=rev.revision_id, presentation=presentation, now=now)
            uow.ownership.insert_event(unit_id=unit_id, item_id=item_id, user_id=user_id, event_type="claimed",
                                       details={"source": "starter_kit"}, now=now)
            uow.audit.record(actor_id=user_id, action="ownership.starter_granted", target_type="owned_item",
                             target_id=str(item_id), details={"product_id": str(product_id), "serial": serial})
            uow.outbox.emit(event_type="ownership.item_claimed", aggregate_type="owned_item", aggregate_id=item_id,
                            payload={"unit_id": str(unit_id), "user_id": str(user_id)})
            granted += 1
        return granted


def backfill_starter_kit(uow_factory: Callable, engine, product_ids: tuple[str, ...] = (), *, clock: Clock = utcnow) -> dict:
    """Gives every onboarded account the starter-kit pieces it has not received yet (idempotent per piece: a piece
    counts as received once a claim event marked source=starter_kit exists for it, so growing the kit tops existing
    accounts up). One transaction per account. `accounts` counts the accounts that received at least one piece.
    `engine` is unused (kept for the CLI's call signature)."""
    kit = StarterKit(product_ids)
    with uow_factory() as uow:
        users = uow.ownership.onboarded_accounts()
    accounts = granted = 0
    for user_id in users:
        with uow_factory() as uow:
            n = kit.grant(uow, user_id, clock())
            uow.commit()
        accounts += 1 if n else 0
        granted += n
    return {"accounts": accounts, "pieces": granted}
