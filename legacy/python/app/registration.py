"""Garment registration (thesis 3.4.4, FYP RQ3).

* The QR serial and private activation key are alternative one-time registration credentials.
* Either path atomically consumes the same garment_code row. Concurrent QR/key
  redemption can only create one garment; activation keys are stored as hashes.
* Every failure (unknown, already used, someone typed the public serial) returns the
  same generic error; attempts are rate-limited to 10 per user per hour.
"""
from __future__ import annotations

import base64
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, update
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from .models import ActivationAttempt, Garment, GarmentCode, Product

RATE_LIMIT = 10
RATE_WINDOW = timedelta(hours=1)
GENERIC_ERROR = "invalid code"


class ActivationError(Exception):
    """Always rendered as the same generic message."""

    def __init__(self):
        super().__init__(GENERIC_ERROR)


class RateLimited(Exception):
    pass


def new_serial() -> str:
    return secrets.token_hex(16)  # 128 bit


def normalize_code(code: str) -> str:
    return "".join(ch for ch in code.upper() if ch.isalnum())


def hash_code(code: str) -> str:
    return hashlib.sha256(normalize_code(code).encode("ascii", "ignore")).hexdigest()


def new_activation_code() -> tuple[str, str]:
    """(16-char code shown once, SHA-256 hash that is stored). 10 random bytes = 80 bit → 16 base32 chars."""
    raw = base64.b32encode(secrets.token_bytes(10)).decode("ascii")
    display = "-".join(raw[i : i + 4] for i in range(0, 16, 4))
    return display, hash_code(raw)


def issue_codes(s: Session, gtin: str, count: int = 1) -> list[dict]:
    """Retailer side: mint serial + activation code pairs for a product. Codes are returned once."""
    if s.get(Product, gtin) is None:
        raise LookupError("unknown gtin")
    out = []
    for _ in range(count):
        serial = new_serial()
        code, h = new_activation_code()
        s.add(GarmentCode(serial=serial, gtin=gtin, activation_hash=h))
        out.append({"gtin": gtin, "serial": serial, "activation_code": code})
    s.commit()
    return out


def attempts_in_window(s: Session, user_id: uuid.UUID, now: datetime) -> int:
    q = select(func.count()).select_from(ActivationAttempt).where(
        ActivationAttempt.user_id == user_id, ActivationAttempt.at >= now - RATE_WINDOW
    )
    return s.scalar(q) or 0


def _record_attempt(s: Session, user_id: uuid.UUID, now: datetime, ok: bool) -> None:
    s.add(ActivationAttempt(user_id=user_id, at=now, ok=ok))


def activate(s: Session, user_id: uuid.UUID, code: str, now: datetime | None = None,
             *, gtin: str | None = None, serial: str | None = None) -> Garment:
    now = now or datetime.now(timezone.utc)
    if attempts_in_window(s, user_id, now) >= RATE_LIMIT:
        raise RateLimited()
    credential = ((GarmentCode.serial == serial) & (GarmentCode.gtin == gtin)
                  if serial is not None else GarmentCode.activation_hash == hash_code(code))
    stmt = (
        update(GarmentCode)
        .where(credential, GarmentCode.used_at.is_(None))
        .values(owner_id=user_id, used_at=now)
        .returning(GarmentCode.serial, GarmentCode.gtin)
        .execution_options(synchronize_session=False)
    )
    try:
        row = s.execute(stmt).first()
    except OperationalError:  # e.g. SQLite busy under contention: treat as a failed attempt
        row = None
    if row is None:
        s.rollback()
        _record_attempt(s, user_id, now, ok=False)
        s.commit()
        raise ActivationError()
    product = s.get(Product, row.gtin)
    garment = Garment(owner_id=user_id, gtin=row.gtin, serial=row.serial, name=product.name,
                      slot=product.slot, attrs=product.attrs())
    s.add(garment)
    _record_attempt(s, user_id, now, ok=True)
    s.commit()  # code redemption and the new garment commit together
    return garment


def product_page(s: Session, gtin: str, serial: str, base_url: str = "") -> dict | None:
    """Tag metadata. The scan page redeems the tag through POST /garments/scan."""
    code = s.get(GarmentCode, serial)
    if code is None or code.gtin != gtin:
        return None
    p = s.get(Product, gtin)
    return {
        "gtin": p.gtin, "serial": serial, "name": p.name, "category": p.category, "slot": p.slot,
        "color_hex": p.color_hex, "style": p.style, "image_url": p.image_url,
        "digital_link": f"{base_url.rstrip('/')}/01/{gtin}/21/{serial}",
        "wishlist_only": False,
        "ownership": "Scan this QR or enter its activation key to register the garment once.",
    }
