"""add-wearhouse-accounts §2: Neon Auth (EdDSA) broker tokens, explicit JWKS URL, deny-only claims,
revocation and onboarding state."""
from __future__ import annotations

import time

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ed25519

from wearhouse.bootstrap.config import ConfigError, Settings
from wearhouse.bootstrap.container import build_verifier
from wearhouse.identity.adapters.oidc import JwksUrlSource, OidcTokenVerifier, StaticJwks
from wearhouse.identity.ports import InvalidToken
from wearhouse.platform.crypto import generate_secret
from wearhouse.testing import LocalIssuer

ORIGIN = "https://ep-wearhouse-test.aws.neon.tech"
JWKS_URL = ORIGIN + "/neondb/auth/.well-known/jwks.json"


@pytest.fixture(scope="module")
def neon_iss():
    return LocalIssuer.neon(ORIGIN)


def reason(v, token):
    with pytest.raises(InvalidToken) as e:
        v.verify(token)
    return e.value.reason


# ------------------------------------------------------------------ 2.1 EdDSA allowlist
def test_eddsa_neon_token_accepted_with_hints(neon_iss):
    neon = neon_iss
    ident = neon.verifier().verify(neon.token("user-1", profile={"name": "Ada", "image": "https://lh3.example/p"}))
    assert (ident.issuer, ident.subject) == (ORIGIN, "user-1")
    assert ident.hints.name == "Ada" and ident.hints.image == "https://lh3.example/p" and not ident.hints.banned
    assert ident.issued_at is not None


def test_rejected_algorithms_and_cross_family_keys(neon_iss):
    neon = neon_iss
    v = OidcTokenVerifier(issuer=ORIGIN, audience=ORIGIN, keys=StaticJwks(neon.jwks()), algorithms=("EdDSA",))
    now = time.time()
    base = {"iss": ORIGIN, "aud": ORIGIN, "sub": "u", "iat": int(now), "exp": int(now + 60)}
    hs = jwt.encode(base, "x" * 40, algorithm="HS256", headers={"kid": neon.current_kid})
    none = jwt.encode(base, None, algorithm="none", headers={"kid": neon.current_kid})
    assert reason(v, hs) == "algorithm" and reason(v, none) == "algorithm"
    rsa_issuer = LocalIssuer(issuer=ORIGIN, audience=ORIGIN)  # RSA token while only EdDSA is allowed
    assert reason(v, rsa_issuer.token("u")) == "algorithm"
    both = OidcTokenVerifier(issuer=ORIGIN, audience=ORIGIN, keys=StaticJwks(neon.jwks()))
    spoof = jwt.encode(base, rsa_issuer._keys[0][1], algorithm="RS256", headers={"kid": neon.current_kid})
    assert reason(both, spoof) == "algorithm"  # an RS256 token can't use an Ed25519 key id


def test_malformed_okp_keys_are_ignored():
    good = LocalIssuer.neon(ORIGIN).jwks()["keys"][0]
    bad = [{**good, "crv": "X25519"}, {**good, "x": "not-base64!"}, {**good, "alg": "RS256"},
           {**good, "use": "enc"}, {k: v for k, v in good.items() if k != "kid"}]
    keys = StaticJwks({"keys": bad})
    assert all(keys.get(k.get("kid", "")) is None for k in bad)


def test_iat_is_required(neon_iss):
    neon = neon_iss
    now = time.time()
    token = jwt.encode({"iss": ORIGIN, "aud": ORIGIN, "sub": "u", "exp": int(now + 60)},
                       neon._keys[-1][1], algorithm="EdDSA", headers={"kid": neon.current_kid})
    assert reason(neon.verifier(), token) == "invalid"


def test_algorithm_config_can_only_narrow():
    with pytest.raises(ValueError):
        OidcTokenVerifier(issuer=ORIGIN, audience=ORIGIN, keys=StaticJwks({}), algorithms=("HS256",))
    with pytest.raises(ConfigError, match="narrow"):
        Settings(environment="development", oidc_issuer=ORIGIN, oidc_audience=ORIGIN,
                 oidc_algorithms=("EdDSA", "HS256")).validate(require_database=False)


# ------------------------------------------------------------------ 2.2 explicit JWKS URL source
class Provider:
    def __init__(self, issuer: LocalIssuer):
        self.issuer, self.paths = issuer, []

    def client(self):
        def handler(request: httpx.Request):
            self.paths.append(request.url.path)
            if request.url.path.endswith("/.well-known/jwks.json"):
                return httpx.Response(200, json=self.issuer.jwks())
            return httpx.Response(404)
        return httpx.Client(transport=httpx.MockTransport(handler))


def test_jwks_url_rotation_bounded_refresh_and_fail_closed():
    neon = LocalIssuer.neon(ORIGIN)
    provider = Provider(neon)
    clock = {"t": 0.0}
    src = JwksUrlSource(JWKS_URL, http=provider.client(), min_refresh_interval_s=60, monotonic=lambda: clock["t"])
    v = OidcTokenVerifier(issuer=ORIGIN, audience=ORIGIN, keys=src, algorithms=("EdDSA",))
    v.verify(neon.token("a"))
    assert src.fetch_count == 1 and provider.paths == ["/neondb/auth/.well-known/jwks.json"]  # no discovery call
    new_kid = neon.rotate()
    clock["t"] += 61
    assert v.verify(neon.token("a", kid=new_kid)).subject == "a"
    assert src.fetch_count == 2  # exactly one refresh for the new kid
    for _ in range(5):
        with pytest.raises(InvalidToken):
            v.verify(neon.token("a", kid="attacker", key=ed25519.Ed25519PrivateKey.generate()))
    assert src.fetch_count == 2


def test_unreachable_jwks_without_cache_fails_closed():
    def down(request):
        raise httpx.ConnectError("down")

    src = JwksUrlSource(JWKS_URL, http=httpx.Client(transport=httpx.MockTransport(down)))
    with pytest.raises(InvalidToken):
        OidcTokenVerifier(issuer=ORIGIN, audience=ORIGIN, keys=src).verify(LocalIssuer.neon(ORIGIN).token("a"))


DEPLOY = dict(environment="production", database_url="postgresql://u:p@db.example/wh", oidc_issuer=ORIGIN,
              oidc_audience=ORIGIN, oidc_jwks_url=JWKS_URL, delivery_secret=generate_secret(),
              oidc_algorithms=("EdDSA",))


def test_deployment_broker_config():
    Settings(**DEPLOY).validate()
    with pytest.raises(ConfigError, match="JWKS_URL is required"):
        Settings(**{**DEPLOY, "oidc_jwks_url": None}).validate()
    with pytest.raises(ConfigError, match="JWKS_URL must be https"):
        Settings(**{**DEPLOY, "oidc_jwks_url": "http://ep.example/jwks.json"}).validate()
    with pytest.raises(ConfigError, match="AUDIENCE must be https"):
        Settings(**{**DEPLOY, "oidc_audience": "http://ep.example"}).validate()
    Settings(**{**DEPLOY, "oidc_jwks_url": None, "oidc_discovery": True}).validate()  # explicit opt-in


def test_build_verifier_prefers_file_then_url_then_discovery(tmp_path):
    from wearhouse.identity.adapters.oidc import DiscoveryJwks
    neon = LocalIssuer.neon(ORIGIN)
    base = dict(environment="development", oidc_issuer=ORIGIN, oidc_audience=ORIGIN)
    f = neon.write_jwks(tmp_path / "jwks.json")
    assert isinstance(build_verifier(Settings(**base, oidc_jwks_file=f, oidc_jwks_url=JWKS_URL)).keys, StaticJwks)
    assert isinstance(build_verifier(Settings(**base, oidc_jwks_url=JWKS_URL)).keys, JwksUrlSource)
    assert isinstance(build_verifier(Settings(**base)).keys, DiscoveryJwks)
    s = Settings.from_env({"WEARHOUSE_ENV": "production", "WEARHOUSE_OIDC_JWKS_URL": JWKS_URL,
                           "WEARHOUSE_OIDC_ALGORITHMS": "EdDSA"})
    assert s.oidc_jwks_url == JWKS_URL and s.oidc_algorithms == ("EdDSA",)


# ------------------------------------------------------------------ 2.3-2.5 through the API (PostgreSQL)
import threading  # noqa: E402

from conftest import Api, counts, create_test_app, make_settings, synthetic_product  # noqa: E402

pg = pytest.mark.postgres


def bearer(api, sub, **kw):
    return {"Authorization": "Bearer " + api.issuer.token(sub, **kw)}


@pg
def test_broker_role_and_profile_claims_grant_nothing(neon, clean_db):
    h = bearer(neon, "claims-user", profile={"role": "admin", "o": {"role": "owner"}})
    me = neon.client.get("/api/v2/me", headers=h).json()
    assert me["roles"] == [] and "inventory:issue" not in me["capabilities"]
    r = neon.client.post("/api/v2/admin/source-products", json=synthetic_product(), headers=h)
    assert r.status_code == 403
    assert counts(clean_db, "role_grant", "product") == {"role_grant": 0, "product": 0}


@pg
def test_banned_first_sign_in_creates_nothing_and_public_routes_still_work(neon, clean_db):
    h = bearer(neon, "banned-user", profile={"banned": True})
    for method, path in (("GET", "/api/v2/me"), ("GET", "/api/v2/me/items"), ("GET", "/api/v2/me/profile")):
        r = neon.client.request(method, path, headers=h)
        assert r.status_code == 403 and r.json()["code"] == "ACCOUNT_SUSPENDED", path
    assert counts(clean_db, "app_user", "account_profile") == {"app_user": 0, "account_profile": 0}
    assert neon.client.get("/api/v2/health", headers=h).status_code == 200
    assert neon.client.get("/api/v2/profiles/someone", headers=h).status_code == 404  # browses as anonymous


@pg
def test_revocation_rejects_earlier_tokens_and_survives_restart(neon, clean_db, settings, neon_issuer):
    t0 = time.time()
    old = neon_issuer.token("revoker", now=t0 - 5)
    assert neon.client.get("/api/v2/me", headers={"Authorization": "Bearer " + old}).status_code == 200
    assert neon.client.post("/api/v2/me/sessions/revoke-all",
                            headers={"Authorization": "Bearer " + old}).status_code == 204
    r = neon.client.get("/api/v2/me", headers={"Authorization": "Bearer " + old})
    assert r.status_code == 401 and r.json()["code"] == "UNAUTHENTICATED"
    fresh = neon_issuer.token("revoker", now=t0 + 2)
    assert neon.client.get("/api/v2/me", headers={"Authorization": "Bearer " + fresh}).status_code == 200
    restarted = Api(create_test_app(make_settings(clean_db, neon_issuer), issuer=neon_issuer), neon_issuer)
    assert restarted.client.get("/api/v2/me", headers={"Authorization": "Bearer " + old}).status_code == 401
    assert restarted.client.get("/api/v2/me", headers={"Authorization": "Bearer " + fresh}).status_code == 200


@pg
def test_concurrent_first_sign_in_one_account_needing_onboarding(neon, clean_db):
    token = neon.issuer.token("google-newbie", profile={"name": "Newbie Person"})
    out = []

    def go():
        out.append(neon.client.get("/api/v2/me", headers={"Authorization": "Bearer " + token}).json())

    ts = [threading.Thread(target=go) for _ in range(8)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert len({o["user_id"] for o in out}) == 1
    assert all(o["needs_onboarding"] is True and o["handle"] is None and o["roles"] == [] for o in out)
    assert counts(clean_db, "app_user", "account_profile", "privacy_setting") == \
        {"app_user": 1, "account_profile": 1, "privacy_setting": 1}
    prof = neon.client.get("/api/v2/me/profile", headers={"Authorization": "Bearer " + token}).json()
    assert prof["display_name"] == "Newbie Person" and "email" not in str(prof)
