"""Standards-based OAuth2/OIDC resource-server token verification.

- Asymmetric algorithm allowlist: EdDSA (Ed25519, used by Neon Auth) and RS256. `none`/HS* are never
  accepted. Configuration may narrow the allowlist, never widen it. A key only verifies tokens of its own
  algorithm family (an RSA key never verifies an EdDSA token or vice versa).
- Signature, issuer, audience, expiry, not-before and issued-at are verified with bounded clock skew.
- Keys come from an explicit JWKS URL (Neon Auth publishes no discovery document) or from issuer
  discovery -> jwks_uri, with a bounded cache and a rate-limited refresh on an unknown `kid`. A key still
  unknown after refreshing fails closed.
- Tokens are never logged. Only (iss, sub) select the account. Profile claims leave this module as
  frozen *hints* (name, https image, banned), and roles are never read from claims.
"""
from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Protocol

import httpx
import jwt
from jwt import PyJWK

from ..domain import IdentityHints, VerifiedIdentity
from ..ports import InvalidToken

ALLOWED_ALGORITHMS = ("EdDSA", "RS256")
DEFAULT_LEEWAY_S = 60
MAX_KEYS = 20
_KEY_FAMILIES = {"RSA": "RS256", "OKP": "EdDSA"}


class KeySource(Protocol):
    def get(self, kid: str) -> tuple[Any, str] | None:
        """Return (public key, algorithm) for a key id, or None."""


def _parse_jwks(doc: dict) -> dict[str, tuple[Any, str]]:
    keys: dict[str, tuple[Any, str]] = {}
    for jwk in (doc.get("keys") or [])[:MAX_KEYS]:
        if not isinstance(jwk, dict) or not jwk.get("kid"):
            continue
        alg = _KEY_FAMILIES.get(jwk.get("kty"))
        if alg is None or jwk.get("use") not in (None, "sig") or jwk.get("alg") not in (None, alg):
            continue
        if alg == "EdDSA" and jwk.get("crv") != "Ed25519":
            continue
        try:
            keys[jwk["kid"]] = (PyJWK(jwk, algorithm=alg).key, alg)
        except Exception:  # noqa: BLE001 - malformed key entries are ignored, never trusted
            continue
    return keys


class StaticJwks:
    """Fixed key set: tests and the local development issuer only (rejected in deployment config)."""

    def __init__(self, doc: dict):
        self._keys = _parse_jwks(doc)

    @classmethod
    def from_file(cls, path: Path) -> "StaticJwks":
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    def get(self, kid: str):
        return self._keys.get(kid)


class _CachedRemoteJwks:
    """Bounded cache + rate-limited refresh shared by the JWKS-URL and discovery sources."""

    def __init__(self, *, http: httpx.Client | None, cache_ttl_s: float, min_refresh_interval_s: float,
                 timeout_s: float, monotonic: Callable[[], float]):
        self.http = http or httpx.Client(timeout=timeout_s, follow_redirects=False)
        self.cache_ttl_s = cache_ttl_s
        self.min_refresh_interval_s = min_refresh_interval_s
        self.monotonic = monotonic
        self._keys: dict[str, tuple[Any, str]] = {}
        self._fetched_at: float | None = None
        self._last_attempt: float | None = None
        self._lock = threading.Lock()
        self.fetch_count = 0

    def _jwks_url(self) -> str:  # pragma: no cover - overridden
        raise NotImplementedError

    def _refresh(self) -> None:
        self._last_attempt = self.monotonic()
        self.fetch_count += 1
        jwks = self.http.get(self._jwks_url())
        jwks.raise_for_status()
        self._keys = _parse_jwks(jwks.json())
        self._fetched_at = self.monotonic()

    def get(self, kid: str):
        with self._lock:
            now = self.monotonic()
            stale = self._fetched_at is None or now - self._fetched_at > self.cache_ttl_s
            unknown = kid not in self._keys
            may_refresh = self._last_attempt is None or now - self._last_attempt >= self.min_refresh_interval_s
            if (stale or unknown) and (may_refresh or self._fetched_at is None):
                try:
                    self._refresh()
                except InvalidToken:
                    raise
                except Exception:  # noqa: BLE001 - provider unreachable: keep cached keys, else fail closed
                    if self._fetched_at is None:
                        return None
            return self._keys.get(kid)


class JwksUrlSource(_CachedRemoteJwks):
    """Explicitly configured JWKS URL (e.g. `<NEON_AUTH_BASE_URL>/.well-known/jwks.json`)."""

    def __init__(self, jwks_url: str, *, http: httpx.Client | None = None, cache_ttl_s: float = 600,
                 min_refresh_interval_s: float = 60, timeout_s: float = 3.0,
                 monotonic: Callable[[], float] = time.monotonic):
        super().__init__(http=http, cache_ttl_s=cache_ttl_s, min_refresh_interval_s=min_refresh_interval_s,
                         timeout_s=timeout_s, monotonic=monotonic)
        self.jwks_url = jwks_url

    def _jwks_url(self) -> str:
        return self.jwks_url


class DiscoveryJwks(_CachedRemoteJwks):
    """`{issuer}/.well-known/openid-configuration` -> `jwks_uri`, cached; refresh bounded in time."""

    def __init__(self, issuer: str, *, http: httpx.Client | None = None, cache_ttl_s: float = 600,
                 min_refresh_interval_s: float = 60, timeout_s: float = 3.0,
                 monotonic: Callable[[], float] = time.monotonic):
        super().__init__(http=http, cache_ttl_s=cache_ttl_s, min_refresh_interval_s=min_refresh_interval_s,
                         timeout_s=timeout_s, monotonic=monotonic)
        self.issuer = issuer.rstrip("/")
        self._discovered: str | None = None

    def _jwks_url(self) -> str:
        disc = self.http.get(self.issuer + "/.well-known/openid-configuration")
        disc.raise_for_status()
        meta = disc.json()
        if meta.get("issuer", "").rstrip("/") != self.issuer:
            raise InvalidToken("discovery_issuer_mismatch")
        return meta["jwks_uri"]


def _hints(claims: dict) -> IdentityHints:
    name = claims.get("name")
    image = claims.get("image")
    return IdentityHints(
        name=name.strip()[:200] if isinstance(name, str) and name.strip() else None,
        image=image if isinstance(image, str) and image.startswith("https://") and len(image) <= 2048 else None,
        banned=claims.get("banned") is True,
    )


class OidcTokenVerifier:
    def __init__(self, *, issuer: str, audience: str, keys: KeySource, leeway_s: int = DEFAULT_LEEWAY_S,
                 algorithms: tuple[str, ...] = ALLOWED_ALGORITHMS):
        if not algorithms or not set(algorithms) <= set(ALLOWED_ALGORITHMS):
            raise ValueError("only asymmetric allowlisted algorithms (EdDSA, RS256) are supported")
        self.issuer = issuer
        self.audience = audience
        self.keys = keys
        self.leeway_s = leeway_s
        self.algorithms = tuple(algorithms)

    def verify(self, token: str) -> VerifiedIdentity:
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError:
            raise InvalidToken("malformed") from None
        alg = header.get("alg")
        if alg not in self.algorithms:
            raise InvalidToken("algorithm")
        kid = header.get("kid")
        if not isinstance(kid, str) or not kid:
            raise InvalidToken("kid")
        found = self.keys.get(kid)
        if found is None:
            raise InvalidToken("unknown_key")
        key, key_alg = found
        if key_alg != alg:
            raise InvalidToken("algorithm")
        try:
            claims = jwt.decode(token, key=key, algorithms=[alg], audience=self.audience,
                                issuer=self.issuer, leeway=self.leeway_s,
                                options={"require": ["exp", "iat", "iss", "aud", "sub"], "verify_signature": True})
        except jwt.ExpiredSignatureError:
            raise InvalidToken("expired") from None
        except jwt.ImmatureSignatureError:
            raise InvalidToken("not_yet_valid") from None
        except jwt.InvalidAudienceError:
            raise InvalidToken("audience") from None
        except jwt.InvalidIssuerError:
            raise InvalidToken("issuer") from None
        except jwt.PyJWTError:
            raise InvalidToken("invalid") from None
        sub = claims.get("sub")
        if not isinstance(sub, str) or not sub or len(sub) > 255:
            raise InvalidToken("subject")
        iat = claims.get("iat")
        if isinstance(iat, bool) or not isinstance(iat, (int, float)):
            raise InvalidToken("invalid")
        return VerifiedIdentity(issuer=self.issuer, subject=sub,
                                issued_at=datetime.fromtimestamp(int(iat), tz=timezone.utc), hints=_hints(claims))
