"""4.1-4.4 token verification, account mapping, server-owned roles and test-mode isolation."""
from __future__ import annotations

import logging
import threading
import time

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from conftest import Api, counts, query, synthetic_product
from wearhouse.identity.adapters.oidc import DiscoveryJwks, OidcTokenVerifier, StaticJwks
from wearhouse.identity.ports import InvalidToken
from wearhouse.testing import LocalIssuer, create_test_app


# ------------------------------------------------------------------ 4.1 verifier (no DB)
@pytest.fixture(scope="module")
def iss():
    return LocalIssuer()


def reason(verifier, token) -> str:
    with pytest.raises(InvalidToken) as e:
        verifier.verify(token)
    return e.value.reason


def test_valid_rs256_token_yields_only_issuer_and_subject(iss):
    ident = iss.verifier().verify(iss.token("alice", extra={"roles": ["admin"], "owner_id": "x"}))
    assert (ident.issuer, ident.subject) == (iss.issuer, "alice")
    assert not hasattr(ident, "roles")


def test_invalid_token_variants(iss):
    v = iss.verifier(leeway_s=0)
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    hs = jwt.encode({"iss": iss.issuer, "aud": iss.audience, "sub": "a", "exp": time.time() + 60}, "secret" * 8,
                    algorithm="HS256", headers={"kid": iss.current_kid})
    unsigned = jwt.encode({"iss": iss.issuer, "aud": iss.audience, "sub": "a", "exp": time.time() + 60}, None,
                          algorithm="none", headers={"kid": iss.current_kid})
    assert reason(v, iss.token("a", ttl_s=-5)) == "expired"
    assert reason(v, iss.token("a", issuer="https://evil.example")) == "issuer"
    assert reason(v, iss.token("a", audience="other-api")) == "audience"
    assert reason(v, iss.token("a", key=other_key)) == "invalid"  # wrongly signed
    assert reason(v, iss.token("a", kid="unknown-kid")) == "unknown_key"
    assert reason(v, iss.token("a", nbf_offset_s=120)) == "not_yet_valid"
    assert reason(v, hs) == "algorithm"
    assert reason(v, unsigned) == "algorithm"
    assert reason(v, "not-a-jwt") == "malformed"
    no_sub = jwt.encode({"iss": iss.issuer, "aud": iss.audience, "exp": time.time() + 60},
                        dict(iss._keys)[iss.current_kid], algorithm="RS256", headers={"kid": iss.current_kid})
    assert reason(v, no_sub) == "invalid"


def test_bounded_clock_skew(iss):
    assert iss.verifier(leeway_s=60).verify(iss.token("a", ttl_s=-30)).subject == "a"
    assert reason(iss.verifier(leeway_s=60), iss.token("a", ttl_s=-120)) == "expired"


def test_only_asymmetric_allowlist():
    with pytest.raises(ValueError):
        OidcTokenVerifier(issuer="i", audience="a", keys=StaticJwks({"keys": []}), algorithms=("HS256",))


class FakeProvider:
    def __init__(self, issuer: LocalIssuer):
        self.issuer, self.calls = issuer, 0

    def transport(self):
        def handler(request: httpx.Request) -> httpx.Response:
            self.calls += 1
            if request.url.path.endswith("/.well-known/openid-configuration"):
                return httpx.Response(200, json={"issuer": self.issuer.issuer,
                                                 "jwks_uri": self.issuer.issuer + "/jwks"})
            return httpx.Response(200, json=self.issuer.jwks())
        return httpx.MockTransport(handler)


def test_discovery_key_rotation_and_bounded_refresh():
    iss = LocalIssuer()
    provider = FakeProvider(iss)
    clock = {"t": 1000.0}
    keys = DiscoveryJwks(iss.issuer, http=httpx.Client(transport=provider.transport()), cache_ttl_s=600,
                         min_refresh_interval_s=60, monotonic=lambda: clock["t"])
    v = OidcTokenVerifier(issuer=iss.issuer, audience=iss.audience, keys=keys)
    assert v.verify(iss.token("a")).subject == "a"
    assert keys.fetch_count == 1
    v.verify(iss.token("a"))
    assert keys.fetch_count == 1  # cached
    new_kid = iss.rotate()  # provider publishes a new key
    clock["t"] += 61
    assert v.verify(iss.token("a", kid=new_kid)).subject == "a"  # unknown kid -> one bounded refresh
    assert keys.fetch_count == 2
    for _ in range(5):  # flood of unknown kids inside the refresh interval: no further fetches, fail closed
        with pytest.raises(InvalidToken):
            v.verify(iss.token("a", kid="attacker-kid"))
    assert keys.fetch_count == 2
    old_kid = iss._keys[0][0]
    iss.retire_oldest()
    clock["t"] += 601  # cache expiry picks up the retirement
    with pytest.raises(InvalidToken):
        v.verify(_signed_with_retired(iss, old_kid))
    assert keys.fetch_count == 3


def _signed_with_retired(iss: LocalIssuer, kid: str) -> str:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return iss.token("a", kid=kid, key=key)


def test_discovery_issuer_mismatch_fails_closed():
    iss = LocalIssuer()

    def handler(request):
        return httpx.Response(200, json={"issuer": "https://other.example", "jwks_uri": iss.issuer + "/jwks"})

    keys = DiscoveryJwks(iss.issuer, http=httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(InvalidToken):
        OidcTokenVerifier(issuer=iss.issuer, audience=iss.audience, keys=keys).verify(iss.token("a"))


def test_unreachable_provider_without_cache_fails_closed():
    iss = LocalIssuer()

    def handler(request):
        raise httpx.ConnectError("down")

    keys = DiscoveryJwks(iss.issuer, http=httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(InvalidToken):
        OidcTokenVerifier(issuer=iss.issuer, audience=iss.audience, keys=keys).verify(iss.token("a"))


# ------------------------------------------------------------------ HTTP-level outcomes (DB)
pg = pytest.mark.postgres


@pg
@pytest.mark.parametrize("auth", [None, "Basic abc", "Bearer ", "Bearer not-a-jwt", "bearer_expired",
                                  "bearer_wrong_aud", "bearer_wrong_iss", "bearer_wrong_key"])
def test_invalid_credentials_return_401_without_mutation(api, staff, clean_db, auth):
    tokens = {"bearer_expired": api.issuer.token("x", ttl_s=-3600),
              "bearer_wrong_aud": api.issuer.token("x", audience="other"),
              "bearer_wrong_iss": api.issuer.token("x", issuer="https://evil.example"),
              "bearer_wrong_key": api.issuer.token("x", key=rsa.generate_private_key(public_exponent=65537,
                                                                                    key_size=2048))}
    header = {"Authorization": "Bearer " + tokens[auth]} if auth in tokens else ({"Authorization": auth} if auth else {})
    before = counts(clean_db, "app_user", "product_revision", "garment_unit", "owned_item", "audit_event")
    for method, path, body in (("GET", "/api/v2/me", None),
                               ("POST", "/api/v2/admin/source-products", synthetic_product("0000000009")),
                               ("POST", "/api/v2/admin/unit-batches", {"product_id": staff["product_id"]}),
                               ("POST", "/api/v2/redemptions", {"activation_key": "AAAA-BBBB-CCCC-DDDD"})):
        r = api.client.request(method, path, json=body, headers={**header, "Idempotency-Key": "k-12345678"})
        assert r.status_code == 401, (path, r.text)
        assert r.json()["code"] == "UNAUTHENTICATED" and r.headers["www-authenticate"].startswith("Bearer")
    assert counts(clean_db, "app_user", "product_revision", "garment_unit", "owned_item", "audit_event") == before


# ------------------------------------------------------------------ 4.2 account mapping
@pg
def test_concurrent_first_access_creates_one_account(api, clean_db, settings, issuer):
    token = issuer.token("new-subject")
    results, errors = [], []

    def call():
        try:
            results.append(api.client.get("/api/v2/me", headers={"Authorization": "Bearer " + token}).json())
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=call) for _ in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert not errors
    assert len({r["user_id"] for r in results}) == 1
    assert counts(clean_db, "app_user", "user_subject") == {"app_user": 1, "user_subject": 1}
    assert results[0]["roles"] == [] and results[0]["capabilities"] == ["ownership:read_own", "ownership:redeem"]
    restarted = Api(create_test_app(settings, issuer=issuer), issuer)
    assert restarted.get("/api/v2/me", "new-subject").json()["user_id"] == results[0]["user_id"]
    assert counts(clean_db, "app_user") == {"app_user": 1}


@pg
def test_token_role_claims_and_profile_fields_grant_nothing(api, clean_db):
    token = api.issuer.token("claims-user", extra={"roles": ["admin"], "wearhouse_roles": ["inventory_manager"],
                                                   "groups": ["catalogue_editor"]})
    me = api.client.get("/api/v2/me", headers={"Authorization": "Bearer " + token}).json()
    assert me["roles"] == []
    r = api.client.post("/api/v2/admin/source-products", json=synthetic_product(),
                        headers={"Authorization": "Bearer " + token})
    assert r.status_code == 403
    assert counts(clean_db, "role_grant") == {"role_grant": 0}


# ------------------------------------------------------------------ 4.3 roles
@pg
def test_editor_ingests_but_cannot_issue(api, clean_db):
    api.grant("ed", "catalogue_editor")
    r = api.post("/api/v2/admin/source-products", "ed", json=synthetic_product())
    assert r.status_code == 201
    audit = query(clean_db, "SELECT action, actor_id::text FROM audit_event WHERE action LIKE 'catalogue.%'")
    assert audit == [("catalogue.source_product_ingested", api.user_id("ed"))]
    i = api.post("/api/v2/admin/unit-batches", "ed", json={"product_id": r.json()["product_id"]}, idem="ed-issue-01")
    assert i.status_code == 403 and i.json()["code"] == "FORBIDDEN"
    assert counts(clean_db, "garment_unit", "activation_credential") == {"garment_unit": 0, "activation_credential": 0}


@pg
def test_inventory_manager_issues_but_cannot_edit_products(api, staff, clean_db):
    api.grant("inv-only", "inventory_manager")
    r = api.post("/api/v2/admin/source-products", "inv-only", json=synthetic_product("0000000002"))
    assert r.status_code == 403
    assert counts(clean_db, "product") == {"product": 1}
    ok = api.post("/api/v2/admin/unit-batches", "inv-only", json={"product_id": staff["product_id"]}, idem="inv-only-1")
    assert ok.status_code == 201


@pg
def test_customer_gets_403_for_every_staff_operation(api, staff, clean_db):
    from conftest import issue
    unit = issue(api, staff["product_id"])
    before = counts(clean_db, "product", "product_revision", "garment_unit", "activation_credential")
    for path, body in (("/api/v2/admin/source-products", synthetic_product("0000000003")),
                       ("/api/v2/admin/unit-batches", {"product_id": staff["product_id"]}),
                       (f"/api/v2/admin/units/{unit['unit_id']}/reissue", None)):
        r = api.post(path, "customer-z", json=body, idem="cust-staff-1")
        assert r.status_code == 403, (path, r.text)
    assert counts(clean_db, "product", "product_revision", "garment_unit", "activation_credential") == before


@pg
def test_admin_has_both_capabilities_and_grants_are_audited(api, clean_db):
    api.grant("boss", "admin")
    assert api.post("/api/v2/admin/source-products", "boss", json=synthetic_product()).status_code == 201
    me = api.get("/api/v2/me", "boss").json()
    assert me["roles"] == ["admin"] and "inventory:issue" in me["capabilities"]
    assert query(clean_db, "SELECT count(*) FROM audit_event WHERE action = 'identity.role_granted'") == [(1,)]


# ------------------------------------------------------------------ 4.4 test-mode isolation
@pg
def test_headers_query_and_body_cannot_select_identity(api, staff, clean_db):
    victim = api.user_id("victim")
    tricks = {"X-Test-User": "victim", "X-Debug": "1", "X-Wearhouse-Env": "test", "X-User-Id": victim,
              "X-Forwarded-User": "victim", "X-API-Key": "demo-key"}
    r = api.client.get("/api/v2/me?test_user=victim&debug=1", headers=tricks)
    assert r.status_code == 401
    r = api.client.get("/api/v2/me?user_id=" + victim, headers={**tricks, "Authorization": "Bearer test-principal:victim"})
    assert r.status_code == 401  # the fixed-principal adapter is not loaded by the OIDC app
    attacker = api.get("/api/v2/me", "attacker", headers=tricks).json()
    assert attacker["user_id"] != victim
    claim = api.post("/api/v2/redemptions", "attacker", json={"activation_key": "AAAA-BBBB-CCCC-DDDD",
                                                              "owner_id": victim}, idem="owner-trick-1")
    assert claim.status_code == 422  # unknown field rejected, actor cannot be overridden
    assert any(e["field"] == "body.owner_id" for e in claim.json()["field_errors"])


@pg
def test_request_ids_are_sanitised_and_tokens_never_logged(api, clean_db, caplog):
    caplog.set_level(logging.DEBUG)
    token = api.issuer.token("logged-user")
    r = api.client.get("/api/v2/me", headers={"Authorization": "Bearer " + token, "X-Request-ID": "client-req-0001"})
    assert r.headers["x-request-id"] == "client-req-0001"
    bad = api.client.get("/api/v2/me", headers={"X-Request-ID": "evil\nlog-injection"})
    assert bad.headers["x-request-id"] != "evil\nlog-injection" and len(bad.headers["x-request-id"]) == 32
    assert token not in caplog.text and token.split(".")[1] not in caplog.text


@pg
def test_fixed_principal_adapter_only_via_explicit_test_factory(clean_db, issuer):
    from dataclasses import replace as dc_replace

    from conftest import make_settings
    from wearhouse.testing import StaticTestVerifier

    settings = dc_replace(make_settings(clean_db, issuer), auth_adapter="test")
    app = create_test_app(settings, verifier=StaticTestVerifier())
    from fastapi.testclient import TestClient
    c = TestClient(app)
    assert c.get("/api/v2/me", headers={"Authorization": "Bearer test-principal:fixture-user"}).status_code == 200
    assert c.get("/api/v2/me", headers={"Authorization": "Bearer " + issuer.token("x")}).status_code == 401
