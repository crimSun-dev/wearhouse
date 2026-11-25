"""TEST-ONLY composition: explicit principal adapters and a local RS256/EdDSA issuer.

`create_test_app` is the only way to inject a non-OIDC verifier or fault hooks. It refuses any environment
except WEARHOUSE_ENV=test, and deployment configuration rejects the test adapter independently
(Settings.validate). Nothing here is reachable through request headers or query parameters.
"""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

import jwt
from cryptography.hazmat.primitives.asymmetric import ed25519, rsa
from jwt.algorithms import OKPAlgorithm, RSAAlgorithm

from ..bootstrap.app import build_app
from ..bootstrap.config import ConfigError, Settings
from ..bootstrap.container import build_services
from ..bootstrap.startup import verify_database
from ..identity.adapters.oidc import OidcTokenVerifier, StaticJwks
from ..identity.domain import VerifiedIdentity
from ..identity.ports import InvalidToken, TokenVerifier
from ..platform.clock import Clock, utcnow
from ..platform.db import make_engine
from ..platform.ports import FaultHook, no_faults

TEST_PRINCIPAL_ISSUER = "urn:wearhouse:test-principal"


class StaticTestVerifier:
    """Fixed-principal adapter: bearer `test-principal:<subject>` -> that subject. Test factory only."""

    PREFIX = "test-principal:"

    def verify(self, token: str) -> VerifiedIdentity:
        if not token.startswith(self.PREFIX) or len(token) <= len(self.PREFIX):
            raise InvalidToken("invalid")
        return VerifiedIdentity(TEST_PRINCIPAL_ISSUER, token[len(self.PREFIX):])


class LocalIssuer:
    """Self-contained signed-token/JWKS issuer for integration tests and local development.

    `algorithm="RS256"` (default) is a generic OIDC issuer. `LocalIssuer.neon(origin)` reproduces the documented
    Neon Auth (Managed Better Auth) token shape: EdDSA/Ed25519 with `kid`, `iss` == `aud` == the Auth URL
    origin, 15-minute lifetime and profile claims (name, email, image, role, banned) that are hints only.
    """

    NEON_TTL_S = 900

    def __init__(self, issuer: str = "https://issuer.wearhouse.test", audience: str = "wearhouse-api",
                 algorithm: str = "RS256"):
        if algorithm not in ("RS256", "EdDSA"):
            raise ValueError("LocalIssuer supports RS256 and EdDSA only")
        self.issuer, self.audience, self.algorithm = issuer, audience, algorithm
        self._keys: list[tuple[str, Any]] = []
        self.rotate()

    @classmethod
    def neon(cls, origin: str = "https://ep-wearhouse-test.aws.neon.tech") -> "LocalIssuer":
        return cls(issuer=origin, audience=origin, algorithm="EdDSA")

    @property
    def jwks_path(self) -> str:
        return "/.well-known/jwks.json"

    def _new_key(self):
        if self.algorithm == "EdDSA":
            return ed25519.Ed25519PrivateKey.generate()
        return rsa.generate_private_key(public_exponent=65537, key_size=2048)

    def rotate(self) -> str:
        kid = uuid.uuid4().hex[:16]
        self._keys.append((kid, self._new_key()))
        return kid

    def retire_oldest(self) -> None:
        self._keys.pop(0)

    @property
    def current_kid(self) -> str:
        return self._keys[-1][0]

    def jwks(self) -> dict:
        keys = []
        for kid, k in self._keys:
            alg = OKPAlgorithm if self.algorithm == "EdDSA" else RSAAlgorithm
            jwk = json.loads(alg.to_jwk(k.public_key()))
            jwk.update(kid=kid, use="sig", alg=self.algorithm)
            keys.append(jwk)
        return {"keys": keys}

    def write_jwks(self, path: Path) -> Path:
        path.write_text(json.dumps(self.jwks(), indent=2), encoding="utf-8")
        return path

    def token(self, subject: str, *, audience: str | None = None, issuer: str | None = None, ttl_s: int | None = None,
              nbf_offset_s: int | None = None, kid: str | None = None, key: Any = None,
              extra: dict | None = None, now: float | None = None, profile: dict | None = None) -> str:
        """Mint a token. For the Neon shape, `profile` adds name/email/image/role/banned like Neon Auth."""
        now = time.time() if now is None else now
        if ttl_s is None:
            ttl_s = self.NEON_TTL_S if self.algorithm == "EdDSA" else 300
        claims = {"iss": issuer or self.issuer, "aud": audience or self.audience, "sub": subject,
                  "iat": int(now), "exp": int(now + ttl_s)}
        if self.algorithm == "EdDSA":  # documented Neon Auth default user claims
            claims.update({"id": subject, "name": f"Test {subject}", "email": f"{subject}@example.test",
                           "emailVerified": True, "image": None, "role": "authenticated", "banned": False})
        claims.update(profile or {})
        claims.update(extra or {})
        if nbf_offset_s is not None:
            claims["nbf"] = int(now + nbf_offset_s)
        kid = kid or self.current_kid
        signing = key or dict(self._keys).get(kid) or self._keys[-1][1]
        return jwt.encode(claims, signing, algorithm=self.algorithm, headers={"kid": kid})

    def verifier(self, leeway_s: int = 60) -> OidcTokenVerifier:
        return OidcTokenVerifier(issuer=self.issuer, audience=self.audience, keys=StaticJwks(self.jwks()),
                                 leeway_s=leeway_s)


def create_test_app(settings: Settings, *, verifier: TokenVerifier | None = None, issuer: LocalIssuer | None = None,
                    clock: Clock = utcnow, faults: FaultHook = no_faults, engine=None):
    if settings.environment != "test" or settings.deployment:
        raise ConfigError("create_test_app only runs with WEARHOUSE_ENV=test; deployment never loads test principals")
    settings.validate()
    engine = engine or make_engine(settings.database_url)
    verify_database(engine, settings)
    if verifier is None:
        if issuer is None:
            raise ConfigError("create_test_app needs a verifier or a LocalIssuer")
        verifier = issuer.verifier(settings.token_leeway_s)
    services = build_services(settings, engine, verifier, clock=clock, faults=faults)
    return build_app(settings, services, engine)
