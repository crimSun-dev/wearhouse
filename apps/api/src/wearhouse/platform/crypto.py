"""Server-side secrets: HKDF subkeys from the issuance-delivery secret, AES-GCM envelopes and HMACs.

One configured secret (WEARHOUSE_DELIVERY_SECRET, optional *_PREVIOUS for rotation) derives independent
subkeys per purpose, so a digest for one purpose can never be replayed as another.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
from dataclasses import dataclass

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

MIN_SECRET_BYTES = 32
PURPOSE_DELIVERY = b"wearhouse/v2/issuance-delivery"
PURPOSE_FINGERPRINT = b"wearhouse/v2/idempotency-fingerprint"
PURPOSE_CURSOR = b"wearhouse/v2/cursor-signing"
PURPOSE_CURSOR_SEAL = b"wearhouse/v2/cursor-sealing"


class SecretConfigError(ValueError):
    pass


def decode_secret(value: str) -> bytes:
    """Secrets are url-safe base64 (padding optional) of >= 32 random bytes."""
    try:
        raw = base64.urlsafe_b64decode(value.strip() + "=" * (-len(value.strip()) % 4))
    except (ValueError, TypeError) as exc:
        raise SecretConfigError("secret must be url-safe base64") from exc
    if len(raw) < MIN_SECRET_BYTES:
        raise SecretConfigError(f"secret must decode to at least {MIN_SECRET_BYTES} bytes")
    return raw


def generate_secret() -> str:
    return base64.urlsafe_b64encode(os.urandom(32)).decode().rstrip("=")


def _derive(secret: bytes, purpose: bytes) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=purpose).derive(secret)


@dataclass(frozen=True)
class _Key:
    key_id: str
    material: bytes


class KeyRing:
    """Current key signs/encrypts; previous keys only verify/decrypt (rotation window)."""

    def __init__(self, current: bytes, previous: tuple[bytes, ...] = ()):
        self._secrets = (current, *previous)

    def _keys(self, purpose: bytes) -> list[_Key]:
        out = []
        for s in self._secrets:
            k = _derive(s, purpose)
            out.append(_Key(hashlib.sha256(k).hexdigest()[:16], k))
        return out

    # --- HMAC ------------------------------------------------------------
    def mac(self, purpose: bytes, data: bytes) -> str:
        return hmac.new(self._keys(purpose)[0].material, data, hashlib.sha256).hexdigest()

    def mac_matches(self, purpose: bytes, data: bytes, expected: str) -> bool:
        return any(hmac.compare_digest(hmac.new(k.material, data, hashlib.sha256).hexdigest(), expected)
                   for k in self._keys(purpose))

    # --- AES-GCM envelope ---------------------------------------------------
    def seal(self, plaintext: bytes, aad: bytes, purpose: bytes = PURPOSE_DELIVERY) -> tuple[str, bytes, bytes]:
        key = self._keys(purpose)[0]
        nonce = os.urandom(12)
        return key.key_id, nonce, AESGCM(key.material).encrypt(nonce, plaintext, aad)

    def open(self, key_id: str, nonce: bytes, ciphertext: bytes, aad: bytes,
             purpose: bytes = PURPOSE_DELIVERY) -> bytes | None:
        for key in self._keys(purpose):
            if key.key_id == key_id:
                try:
                    return AESGCM(key.material).decrypt(nonce, ciphertext, aad)
                except Exception:  # noqa: BLE001 - tampered/unknown envelope is simply unavailable
                    return None
        return None
