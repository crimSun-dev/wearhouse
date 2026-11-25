"""Ownership domain: public serials, private activation keys and the generic invalid-claim contract.

- Public serial: 128 CSPRNG bits, lowercase RFC 4648 base32 without padding (26 chars). Discovery only.
- Activation key: 80 CSPRNG bits = 16 base32 chars, displayed as XXXX-XXXX-XXXX-XXXX.
  Accepted input is strict ASCII: the 16 characters in either case, either contiguous or with a single
  hyphen between each group of four. Nothing else is normalised away (no spaces, no Unicode look-alikes).
- Stored form: SHA-256 hex of the canonical uppercase key (80 bits of entropy make offline search
  infeasible); the plaintext exists only inside the encrypted delivery envelope.
"""
from __future__ import annotations

import base64
import hashlib
import re
import secrets

from ..platform.errors import ApiError

SERIAL_BYTES = 16  # 128 bits
KEY_BYTES = 10  # 80 bits
SERIAL_PATTERN = re.compile(r"^[a-z2-7]{26}$")
_KEY_INPUT = re.compile(r"^(?:[A-Za-z2-7]{16}|[A-Za-z2-7]{4}-[A-Za-z2-7]{4}-[A-Za-z2-7]{4}-[A-Za-z2-7]{4})$")
MAX_KEY_INPUT = 64

INVALID_ACTIVATION_CODE = "INVALID_ACTIVATION_CODE"
INVALID_ACTIVATION_MESSAGE = "This activation code cannot be redeemed."


def new_public_serial() -> str:
    return base64.b32encode(secrets.token_bytes(SERIAL_BYTES)).decode().rstrip("=").lower()


def new_activation_key() -> str:
    raw = base64.b32encode(secrets.token_bytes(KEY_BYTES)).decode()  # exactly 16 chars, no padding
    return "-".join(raw[i:i + 4] for i in range(0, 16, 4))


def valid_serial(serial: str) -> bool:
    return isinstance(serial, str) and bool(SERIAL_PATTERN.fullmatch(serial))


def normalize_key(text: str) -> str | None:
    """Canonical 16-char uppercase key, or None for anything outside the documented format."""
    if not isinstance(text, str) or len(text) > MAX_KEY_INPUT or not text.isascii():
        return None
    if not _KEY_INPUT.fullmatch(text):
        return None
    return text.replace("-", "").upper()


def key_digest(canonical_key: str) -> str:
    return hashlib.sha256(canonical_key.encode("ascii")).hexdigest()


def invalid_activation() -> ApiError:
    """One response for unknown, malformed, altered, revoked, wrong-actor and already-used keys."""
    return ApiError(400, INVALID_ACTIVATION_CODE, INVALID_ACTIVATION_MESSAGE)


UNIT_ISSUED, UNIT_CLAIMED, UNIT_RETIRED = "issued", "claimed", "retired"
CRED_ACTIVE, CRED_REDEEMED, CRED_REVOKED = "active", "redeemed", "revoked"
