from __future__ import annotations

from sqlalchemy import insert, select, tuple_, update
from sqlalchemy.engine import Connection

from ...platform.ids import new_id
from ..domain import CRED_ACTIVE, CRED_REDEEMED, CRED_REVOKED, UNIT_CLAIMED, UNIT_ISSUED, UNIT_RETIRED
from ...platform.pagination import Position
from ..ports import CredentialRow, DeliveryRow, ItemPresentation, OwnedItemRow, UnitRow
from .tables import activation_credential, garment_unit, issuance_delivery, owned_item, ownership_event


def _unit(r) -> UnitRow:
    size = ({"system": r.size_system, "code": r.size_code, "label": r.size_label}
            if r.size_code else None)
    return UnitRow(r.id, r.product_id, r.acquisition_revision_id, r.public_serial, r.status, size)


class SqlOwnershipRepository:
    def __init__(self, conn: Connection):
        self.conn = conn

    # --- issuance -------------------------------------------------------------
    def insert_unit(self, *, unit_id, product_id, revision_id, serial, issued_by, now, size=None):
        size = size or {}
        self.conn.execute(insert(garment_unit).values(id=unit_id, product_id=product_id,
                                                      acquisition_revision_id=revision_id, public_serial=serial,
                                                      status=UNIT_ISSUED, issued_by=issued_by, created_at=now,
                                                      size_system=size.get("system"), size_code=size.get("code"),
                                                      size_label=size.get("label")))

    def insert_credential(self, *, credential_id, unit_id, digest, audience_user_id, issued_by, now):
        self.conn.execute(insert(activation_credential).values(
            id=credential_id, unit_id=unit_id, key_digest=digest, status=CRED_ACTIVE,
            audience_user_id=audience_user_id, issued_by=issued_by, created_at=now))

    def insert_delivery(self, *, delivery_id, unit_id, credential_id, actor_id, key_id, nonce, ciphertext,
                        expires_at, now):
        self.conn.execute(insert(issuance_delivery).values(
            id=delivery_id, unit_id=unit_id, credential_id=credential_id, actor_id=actor_id, key_id=key_id,
            nonce=nonce, ciphertext=ciphertext, expires_at=expires_at, created_at=now))

    def get_delivery(self, delivery_id):
        r = self.conn.execute(select(issuance_delivery).where(issuance_delivery.c.id == delivery_id)).one_or_none()
        if r is None:
            return None
        return DeliveryRow(r.id, r.unit_id, r.credential_id, r.actor_id, r.key_id,
                           bytes(r.nonce) if r.nonce is not None else None,
                           bytes(r.ciphertext) if r.ciphertext is not None else None,
                           r.expires_at, r.erased_at, r.erase_reason)

    def erase_deliveries(self, unit_id, reason, now):
        return self.conn.execute(update(issuance_delivery)
                                 .where(issuance_delivery.c.unit_id == unit_id, issuance_delivery.c.erased_at.is_(None))
                                 .values(ciphertext=None, nonce=None, erased_at=now, erase_reason=reason)).rowcount

    def erase_expired_deliveries(self, now):
        return self.conn.execute(update(issuance_delivery)
                                 .where(issuance_delivery.c.erased_at.is_(None), issuance_delivery.c.expires_at <= now)
                                 .values(ciphertext=None, nonce=None, erased_at=now, erase_reason="expired")).rowcount

    # --- units & credentials -----------------------------------------------------
    def lock_unit(self, unit_id):
        r = self.conn.execute(select(garment_unit).where(garment_unit.c.id == unit_id).with_for_update()).one_or_none()
        return _unit(r) if r else None

    def unit_by_serial(self, serial):
        r = self.conn.execute(select(garment_unit).where(garment_unit.c.public_serial == serial)).one_or_none()
        return _unit(r) if r else None

    def active_credential(self, unit_id):
        r = self.conn.execute(select(activation_credential).where(
            activation_credential.c.unit_id == unit_id, activation_credential.c.status == CRED_ACTIVE)
            .with_for_update()).one_or_none()
        return CredentialRow(r.id, r.unit_id, r.status, r.audience_user_id) if r else None

    def revoke_credential(self, credential_id, now):
        self.conn.execute(update(activation_credential)
                          .where(activation_credential.c.id == credential_id,
                                 activation_credential.c.status == CRED_ACTIVE)
                          .values(status=CRED_REVOKED, revoked_at=now))

    def lock_credential_by_digest(self, digest):
        r = self.conn.execute(select(activation_credential).where(activation_credential.c.key_digest == digest)
                              .with_for_update()).one_or_none()
        return CredentialRow(r.id, r.unit_id, r.status, r.audience_user_id) if r else None

    def mark_credential_redeemed(self, credential_id, now):
        return self.conn.execute(update(activation_credential)
                                 .where(activation_credential.c.id == credential_id,
                                        activation_credential.c.status == CRED_ACTIVE)
                                 .values(status=CRED_REDEEMED, redeemed_at=now)).rowcount == 1

    def mark_unit_claimed(self, unit_id, now):
        return self.conn.execute(update(garment_unit)
                                 .where(garment_unit.c.id == unit_id, garment_unit.c.status == UNIT_ISSUED)
                                 .values(status=UNIT_CLAIMED, claimed_at=now)).rowcount == 1

    # --- sandbox commerce fulfilment / cancellation (lock order: credentials, then units) ---------
    def lock_active_credentials(self, unit_ids):
        if not unit_ids:
            return []
        rows = self.conn.execute(select(activation_credential).where(
            activation_credential.c.unit_id.in_(unit_ids), activation_credential.c.status == CRED_ACTIVE)
            .order_by(activation_credential.c.id).with_for_update()).all()
        return [CredentialRow(r.id, r.unit_id, r.status, r.audience_user_id) for r in rows]

    def lock_units(self, unit_ids):
        if not unit_ids:
            return []
        rows = self.conn.execute(select(garment_unit).where(garment_unit.c.id.in_(unit_ids))
                                 .order_by(garment_unit.c.id).with_for_update()).all()
        return [_unit(r) for r in rows]

    def units(self, unit_ids):
        if not unit_ids:
            return []
        return [_unit(r) for r in self.conn.execute(select(garment_unit).where(garment_unit.c.id.in_(unit_ids))).all()]

    def mark_unit_retired(self, unit_id):
        return self.conn.execute(update(garment_unit)
                                 .where(garment_unit.c.id == unit_id, garment_unit.c.status == UNIT_ISSUED)
                                 .values(status=UNIT_RETIRED)).rowcount == 1

    def units_of_product(self, product_id, after, limit):
        q = select(garment_unit.c.id, garment_unit.c.public_serial, garment_unit.c.status, garment_unit.c.created_at,
                   garment_unit.c.claimed_at, garment_unit.c.size_system, garment_unit.c.size_code,
                   garment_unit.c.size_label).where(garment_unit.c.product_id == product_id)
        if after is not None:
            q = q.where(tuple_(garment_unit.c.created_at, garment_unit.c.id) < tuple_(after.created_at, after.id))
        rows = self.conn.execute(q.order_by(garment_unit.c.created_at.desc(), garment_unit.c.id.desc()).limit(limit))
        return [dict(r._mapping) for r in rows]

    # --- owned items ---------------------------------------------------------------
    def insert_owned_item(self, *, item_id, user_id, unit_id, revision_id, presentation, now):
        self.conn.execute(insert(owned_item).values(id=item_id, user_id=user_id, unit_id=unit_id,
                                                    acquisition_revision_id=revision_id, presentation=presentation,
                                                    claimed_at=now, created_at=now))

    def insert_event(self, *, unit_id, item_id, user_id, event_type, details, now):
        self.conn.execute(insert(ownership_event).values(id=new_id(), unit_id=unit_id, item_id=item_id,
                                                         user_id=user_id, event_type=event_type, details=details,
                                                         created_at=now))

    def revoke_item_by_unit(self, unit_id, reason, now):
        """Flag the claimed item of a unit as a revoked sandbox entitlement (column grant: revoked_* only)."""
        return self.conn.execute(update(owned_item).where(owned_item.c.unit_id == unit_id,
                                                          owned_item.c.revoked_at.is_(None))
                                 .values(revoked_at=now, revoked_reason=reason)
                                 .returning(owned_item.c.id, owned_item.c.user_id)).first()

    def _items(self):
        return (select(owned_item, garment_unit.c.public_serial)
                .select_from(owned_item.join(garment_unit, garment_unit.c.id == owned_item.c.unit_id)))

    @staticmethod
    def _item(r) -> OwnedItemRow:
        return OwnedItemRow(r.id, r.user_id, r.unit_id, r.public_serial, r.acquisition_revision_id, r.presentation,
                            r.claimed_at, r.created_at, r.revoked_at, r.revoked_reason)

    def list_items(self, user_id, after, limit):
        q = self._items().where(owned_item.c.user_id == user_id)
        if after is not None:
            q = q.where(tuple_(owned_item.c.created_at, owned_item.c.id) > tuple_(after.created_at, after.id))
        rows = self.conn.execute(q.order_by(owned_item.c.created_at, owned_item.c.id).limit(limit)).all()
        return [self._item(r) for r in rows]

    def get_item(self, user_id, item_id):
        r = self.conn.execute(self._items().where(owned_item.c.user_id == user_id,
                                                  owned_item.c.id == item_id)).one_or_none()
        return self._item(r) if r else None


class SqlOwnedItemReader:
    def __init__(self, conn: Connection):
        self.conn = conn

    def presentations(self, user_id, after, limit):
        q = select(owned_item.c.id, owned_item.c.created_at, owned_item.c.presentation).where(
            owned_item.c.user_id == user_id, owned_item.c.revoked_at.is_(None))
        if after is not None:
            q = q.where(tuple_(owned_item.c.created_at, owned_item.c.id) > tuple_(after.created_at, after.id))
        rows = self.conn.execute(q.order_by(owned_item.c.created_at, owned_item.c.id).limit(limit)).all()
        return [ItemPresentation(Position(r.created_at, r.id), dict(r.presentation["product"])) for r in rows]

    def private_items(self, user_id):
        """Every owned item, revoked ones included (export, private item view)."""
        return SqlOwnershipRepository(self.conn).list_items(user_id, None, 10_000)

    def active_items(self, user_id):
        """Owned items that still count: revoked sandbox entitlements are excluded (wardrobe, looks, suggestions)."""
        return [r for r in self.private_items(user_id) if r.revoked_at is None]
