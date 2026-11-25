"""Opaque, signed keyset cursors bound to principal, filter and cursor version."""
from __future__ import annotations

import base64
import json
import uuid
from dataclasses import dataclass
from datetime import datetime

from .crypto import PURPOSE_CURSOR, PURPOSE_CURSOR_SEAL, KeyRing
from .errors import FieldError, validation_failed

CURSOR_VERSION = 1
DEFAULT_LIMIT = 24
MAX_LIMIT = 100


@dataclass(frozen=True)
class Position:
    created_at: datetime
    id: uuid.UUID


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def invalid_cursor() -> Exception:
    return validation_failed([FieldError("query.cursor", "invalid_cursor", "The cursor is invalid or expired.")])


def check_limit(limit: int | None) -> int:
    if limit is None:
        return DEFAULT_LIMIT
    if not 1 <= limit <= MAX_LIMIT:
        raise validation_failed([FieldError("query.limit", "out_of_range", f"limit must be 1-{MAX_LIMIT}.")])
    return limit


def encode(ring: KeyRing, *, principal: uuid.UUID, scope: str, filter_key: str, pos: Position) -> str:
    body = json.dumps({"v": CURSOR_VERSION, "p": str(principal), "s": scope, "f": filter_key,
                       "c": pos.created_at.isoformat(), "i": str(pos.id)}, separators=(",", ":")).encode()
    return _b64(body) + "." + ring.mac(PURPOSE_CURSOR, body)


def decode(ring: KeyRing, token: str, *, principal: uuid.UUID, scope: str, filter_key: str) -> Position:
    try:
        b64, tag = token.split(".", 1)
        body = _unb64(b64)
    except (ValueError, TypeError):
        raise invalid_cursor() from None
    if len(token) > 512 or not ring.mac_matches(PURPOSE_CURSOR, body, tag):
        raise invalid_cursor()
    try:
        data = json.loads(body)
        ok = (data["v"] == CURSOR_VERSION and data["p"] == str(principal) and data["s"] == scope
              and data["f"] == filter_key)
        pos = Position(datetime.fromisoformat(data["c"]), uuid.UUID(data["i"]))
    except (ValueError, KeyError, TypeError):
        raise invalid_cursor() from None
    if not ok:
        raise invalid_cursor()
    return pos


def encode_sealed(ring: KeyRing, *, principal: uuid.UUID | None, scope: str, pos: Position) -> str:
    """Encrypted cursor: the position (ids, timestamps) is unreadable by the client.

    Use this when the listed rows belong to someone other than the viewer.
    """
    body = json.dumps({"v": CURSOR_VERSION, "c": pos.created_at.isoformat(), "i": str(pos.id)},
                      separators=(",", ":")).encode()
    aad = f"{principal or 'anonymous'}|{scope}".encode()
    key_id, nonce, ct = ring.seal(body, aad, purpose=PURPOSE_CURSOR_SEAL)
    return ".".join((key_id, _b64(nonce), _b64(ct)))


def decode_sealed(ring: KeyRing, token: str, *, principal: uuid.UUID | None, scope: str) -> Position:
    try:
        if len(token) > 512:
            raise ValueError
        key_id, nonce, ct = token.split(".")
        body = ring.open(key_id, _unb64(nonce), _unb64(ct), f"{principal or 'anonymous'}|{scope}".encode(),
                         purpose=PURPOSE_CURSOR_SEAL)
        if body is None:
            raise ValueError
        data = json.loads(body)
        if data["v"] != CURSOR_VERSION:
            raise ValueError
        return Position(datetime.fromisoformat(data["c"]), uuid.UUID(data["i"]))
    except (ValueError, KeyError, TypeError):
        raise invalid_cursor() from None


def encode_keyset(ring: KeyRing, *, scope: str, filter_key: str, values: list) -> str:
    """Signed cursor over an arbitrary sort key (e.g. [name, id] or [published_at, id]) for PUBLIC lists."""
    body = json.dumps({"v": CURSOR_VERSION, "s": scope, "f": filter_key, "k": values}, separators=(",", ":"),
                      default=str).encode()
    return _b64(body) + "." + ring.mac(PURPOSE_CURSOR, body)


def decode_keyset(ring: KeyRing, token: str, *, scope: str, filter_key: str) -> list:
    try:
        b64, tag = token.split(".", 1)
        body = _unb64(b64)
    except (ValueError, TypeError):
        raise invalid_cursor() from None
    if len(token) > 1024 or not ring.mac_matches(PURPOSE_CURSOR, body, tag):
        raise invalid_cursor()
    try:
        data = json.loads(body)
        if data["v"] != CURSOR_VERSION or data["s"] != scope or data["f"] != filter_key:
            raise ValueError
        values = data["k"]
        if not isinstance(values, list):
            raise ValueError
        return values
    except (ValueError, KeyError, TypeError):
        raise invalid_cursor() from None
