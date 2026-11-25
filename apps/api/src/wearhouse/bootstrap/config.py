"""v2 settings, read only from WEARHOUSE_* environment variables (never from legacy .env files).

Modes cannot be selected by request headers. Deployment environments (staging/production) fail closed
when identity, database or secret configuration is missing, and reject test/development-only adapters.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

from ..platform.crypto import KeyRing, SecretConfigError, decode_secret

ENVIRONMENTS = ("development", "test", "staging", "production")
DEPLOYMENT_ENVIRONMENTS = frozenset({"staging", "production"})
AUTH_ADAPTERS = ("oidc", "test")
APP_FAMILY = "wearhouse-v2"
DEFAULT_PORT = 8100


class ConfigError(RuntimeError):
    """Actionable configuration error raised before the API serves any request."""


@dataclass(frozen=True)
class Settings:
    environment: str
    database_url: str | None = None
    auth_adapter: str = "oidc"
    oidc_issuer: str | None = None
    oidc_audience: str | None = None
    oidc_jwks_file: Path | None = None  # local development issuer only
    oidc_jwks_url: str | None = None  # explicit JWKS (Neon Auth: <NEON_AUTH_BASE_URL>/.well-known/jwks.json)
    oidc_discovery: bool = False  # deployment opt-in to OIDC discovery when no JWKS URL is configured
    oidc_algorithms: tuple[str, ...] = ("EdDSA", "RS256")
    allowed_origins: tuple[str, ...] = ()
    delivery_secret: str | None = field(default=None, repr=False)
    delivery_secret_previous: str | None = field(default=None, repr=False)
    trusted_proxies: tuple[str, ...] = ()
    rate_writes_per_min: int = 120  # edge limits (harden-wearhouse-services-api); per process; 0 disables
    rate_ip_per_min: int = 600
    rate_global_per_min: int = 6000
    redemption_actor_limit: int | None = 10  # per user per hour (thesis 3.4.4); never disabled in deployments
    redemption_ip_limit: int | None = 60
    redemption_global_limit: int | None = 5000
    idempotency_lease_s: float = 15.0
    delivery_ttl_s: int = 86400
    jwks_cache_ttl_s: float = 600.0
    jwks_min_refresh_s: float = 60.0
    token_leeway_s: int = 60

    @property
    def deployment(self) -> bool:
        return self.environment in DEPLOYMENT_ENVIRONMENTS

    def key_ring(self) -> KeyRing:
        if not self.delivery_secret:
            raise ConfigError("WEARHOUSE_DELIVERY_SECRET is required (url-safe base64 of >= 32 random bytes; "
                              "generate one with `wearhouse generate-secret`).")
        try:
            prev = (decode_secret(self.delivery_secret_previous),) if self.delivery_secret_previous else ()
            return KeyRing(decode_secret(self.delivery_secret), prev)
        except SecretConfigError as exc:
            raise ConfigError(f"WEARHOUSE_DELIVERY_SECRET: {exc}") from None

    def validate(self, *, require_database: bool = True) -> "Settings":
        problems: list[str] = []
        if self.environment not in ENVIRONMENTS:
            problems.append(f"WEARHOUSE_ENV must be one of {', '.join(ENVIRONMENTS)}")
        if self.auth_adapter not in AUTH_ADAPTERS:
            problems.append("WEARHOUSE_AUTH_ADAPTER must be 'oidc' (or 'test' inside the test suite only)")
        if self.auth_adapter == "test" and self.environment != "test":
            problems.append("the test identity adapter is only available when WEARHOUSE_ENV=test")
        if require_database and not self.database_url:
            problems.append("WEARHOUSE_DATABASE_URL is required")
        if self.auth_adapter == "oidc":
            if not self.oidc_issuer:
                problems.append("WEARHOUSE_OIDC_ISSUER is required")
            if not self.oidc_audience:
                problems.append("WEARHOUSE_OIDC_AUDIENCE is required")
            if not self.oidc_algorithms or not set(self.oidc_algorithms) <= {"EdDSA", "RS256"}:
                problems.append("WEARHOUSE_OIDC_ALGORITHMS may only narrow the allowlist EdDSA,RS256")
        if self.deployment:
            if min(self.rate_writes_per_min, self.rate_ip_per_min, self.rate_global_per_min) <= 0:
                raise ConfigError("Edge rate limits cannot be disabled in a deployment environment.")
            if self.redemption_actor_limit is None:
                raise ConfigError("The per-user redemption limit cannot be disabled in a deployment environment.")
            if self.auth_adapter != "oidc":
                problems.append("deployment environments must use the OIDC adapter")
            if self.oidc_jwks_file:
                problems.append("WEARHOUSE_OIDC_JWKS_FILE (local issuer) cannot be used in deployment environments")
            if self.oidc_issuer and not self.oidc_issuer.startswith("https://"):
                problems.append("WEARHOUSE_OIDC_ISSUER must be https in deployment environments")
            if self.oidc_audience and not self.oidc_audience.startswith("https://") and "://" in self.oidc_audience:
                problems.append("WEARHOUSE_OIDC_AUDIENCE must be https in deployment environments")
            if self.oidc_jwks_url and not self.oidc_jwks_url.startswith("https://"):
                problems.append("WEARHOUSE_OIDC_JWKS_URL must be https in deployment environments")
            if not self.oidc_jwks_url and not self.oidc_discovery:
                problems.append("WEARHOUSE_OIDC_JWKS_URL is required in deployment environments "
                                "(or set WEARHOUSE_OIDC_DISCOVERY=on for a provider that publishes discovery)")
            if any(not o.startswith("https://") for o in self.allowed_origins):
                problems.append("WEARHOUSE_ALLOWED_ORIGINS must all be https in deployment environments")
            if not self.delivery_secret:
                problems.append("WEARHOUSE_DELIVERY_SECRET is required in deployment environments")
        if problems:
            raise ConfigError("Invalid Wearhouse v2 configuration:\n  - " + "\n  - ".join(problems))
        if self.delivery_secret:
            self.key_ring()  # validates secret encoding/length
        return self

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Settings":
        e = dict(os.environ if env is None else env)

        def opt_int(name: str, default: int | None) -> int | None:
            v = e.get(name)
            if v is None or v == "":
                return default
            return None if v.lower() in ("off", "none", "disabled") else int(v)

        def csv(name: str) -> tuple[str, ...]:
            return tuple(x.strip() for x in (e.get(name) or "").split(",") if x.strip())

        jwks = e.get("WEARHOUSE_OIDC_JWKS_FILE")
        return cls(
            environment=(e.get("WEARHOUSE_ENV") or "").strip().lower(),
            database_url=e.get("WEARHOUSE_DATABASE_URL") or None,
            auth_adapter=(e.get("WEARHOUSE_AUTH_ADAPTER") or "oidc").strip().lower(),
            oidc_issuer=e.get("WEARHOUSE_OIDC_ISSUER") or None,
            oidc_audience=e.get("WEARHOUSE_OIDC_AUDIENCE") or None,
            oidc_jwks_file=Path(jwks) if jwks else None,
            oidc_jwks_url=e.get("WEARHOUSE_OIDC_JWKS_URL") or None,
            oidc_discovery=(e.get("WEARHOUSE_OIDC_DISCOVERY") or "").strip().lower() in ("1", "on", "true", "yes"),
            oidc_algorithms=csv("WEARHOUSE_OIDC_ALGORITHMS") or ("EdDSA", "RS256"),
            allowed_origins=csv("WEARHOUSE_ALLOWED_ORIGINS"),
            delivery_secret=e.get("WEARHOUSE_DELIVERY_SECRET") or None,
            delivery_secret_previous=e.get("WEARHOUSE_DELIVERY_SECRET_PREVIOUS") or None,
            trusted_proxies=csv("WEARHOUSE_TRUSTED_PROXIES"),
            redemption_actor_limit=opt_int("WEARHOUSE_REDEMPTION_ACTOR_LIMIT", 10),
            rate_writes_per_min=int(e.get("WEARHOUSE_RATE_WRITES_PER_MIN", "120")),
            rate_ip_per_min=int(e.get("WEARHOUSE_RATE_IP_PER_MIN", "600")),
            rate_global_per_min=int(e.get("WEARHOUSE_RATE_GLOBAL_PER_MIN", "6000")),
            redemption_ip_limit=opt_int("WEARHOUSE_REDEMPTION_IP_LIMIT", 60),
            redemption_global_limit=opt_int("WEARHOUSE_REDEMPTION_GLOBAL_LIMIT", 5000),
        )
