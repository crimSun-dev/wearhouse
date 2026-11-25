"""6.1-6.4 admission limits, scoped idempotency, uniform invalid-claim contract, races and fault injection."""
from __future__ import annotations

import multiprocessing
import threading
import time
import uuid
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, replace

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from _workers import claim_in_process
from conftest import Api, admin_engine, counts, issue, make_settings, query, redeem
from wearhouse.platform.adapters.sql import SqlAttemptLedger
from wearhouse.testing import create_test_app

pytestmark = [pytest.mark.postgres, pytest.mark.synthetic_only]
CLAIM_TABLES = ("owned_item", "ownership_event", "outbox_event")
POINTS = ("redeem.after_credential", "redeem.after_unit", "redeem.after_item", "redeem.after_event",
          "redeem.after_outbox")


def actor_attempts(db, user_id) -> int:
    return query(db, "SELECT count(*) FROM attempt_event WHERE scope='actor' AND scope_key=:u", u=str(user_id))[0][0]


def seed_attempts(db, user_id, n: int) -> None:
    eng = admin_engine(db.name)
    with eng.connect() as c:
        c.execute(text("INSERT INTO attempt_bucket (scope, scope_key) VALUES ('actor', :u) ON CONFLICT DO NOTHING"),
                  {"u": str(user_id)})
        for _ in range(n):
            c.execute(text("INSERT INTO attempt_event (id, scope, scope_key, reserved_at) "
                           "VALUES (:i, 'actor', :u, now() - interval '5 minutes')"), {"i": uuid.uuid4(), "u": str(user_id)})
    eng.dispose()


def run_processes(jobs: list[dict]) -> list[tuple[int, str | None]]:
    ctx = multiprocessing.get_context("spawn")
    with ProcessPoolExecutor(max_workers=len(jobs), mp_context=ctx) as pool:
        return list(pool.map(claim_in_process, jobs))


# ------------------------------------------------------------------ 6.3 genuine claim + uniform failures
def test_genuine_claim_assigns_one_item_with_source_category(api, staff, clean_db):
    unit = issue(api, staff["product_id"])
    r = redeem(api, "customer-a", unit["delivery"]["activation_key"].lower().replace("-", ""))  # documented forms
    assert r.status_code == 201, r.text
    assert r.json()["product"]["category"] == "T-shirt" and r.headers["cache-control"] == "no-store"
    assert redeem(api, "customer-a", unit["delivery"]["activation_key"]).json()["code"] == "INVALID_ACTIVATION_CODE"
    assert counts(clean_db, *CLAIM_TABLES)["owned_item"] == 1


def test_actor_bound_credential_rejects_other_actor(api, staff, clean_db):
    bound_to = api.user_id("customer-a")
    unit = issue(api, staff["product_id"], audience_user_id=bound_to)
    assert unit["actor_bound"] is True
    wrong = redeem(api, "customer-b", unit["delivery"]["activation_key"])
    assert wrong.status_code == 400 and wrong.json()["code"] == "INVALID_ACTIVATION_CODE"
    assert redeem(api, "customer-a", unit["delivery"]["activation_key"]).status_code == 201


def test_every_invalid_state_is_indistinguishable(api, staff, clean_db):
    used = issue(api, staff["product_id"])
    assert redeem(api, "customer-a", used["delivery"]["activation_key"]).status_code == 201
    revoked = issue(api, staff["product_id"])
    api.post(f"/api/v2/admin/units/{revoked['unit_id']}/reissue", "inventory-1", idem="rv-" + uuid.uuid4().hex)
    bound = issue(api, staff["product_id"], audience_user_id=api.user_id("someone-else"))
    live = issue(api, staff["product_id"])["delivery"]["activation_key"]
    altered = live[:-1] + ("A" if live[-1] != "A" else "B")
    variants = {"malformed": "not a key", "unicode": "ＡＡＡＡ-ＢＢＢＢ-ＣＣＣＣ-ＤＤＤＤ", "spaces": live.replace("-", " "),
                "unknown": "AAAA-BBBB-CCCC-DDDD", "altered": altered, "public": used["public_serial"],
                "revoked": revoked["delivery"]["activation_key"], "reused": used["delivery"]["activation_key"],
                "wrong_actor": bound["delivery"]["activation_key"]}
    shapes = set()
    for name, key in variants.items():
        r = redeem(api, "prober", key)
        assert r.status_code == 400, (name, r.text)
        body = r.json()
        shapes.add((r.status_code, body["code"], body["message"], tuple(sorted(body))))
    assert len(shapes) == 1, shapes
    assert counts(clean_db, "owned_item") == {"owned_item": 1}
    unauth = api.client.post("/api/v2/redemptions", json={"activation_key": live}, headers={"Idempotency-Key": "x-123456"})
    assert unauth.status_code == 401  # distinguishable from invalid-key


# ------------------------------------------------------------------ 6.1 admission
def test_ten_attempts_per_rolling_hour_then_429_and_survives_restart(api, staff, clean_db, settings, issuer):
    for i in range(10):
        assert redeem(api, "guesser", f"AAAA-BBBB-CCCC-{chr(65 + i)}AAA").status_code == 400
    r = redeem(api, "guesser", "ZZZZ-ZZZZ-ZZZZ-ZZZZ")
    assert r.status_code == 429 and r.json()["code"] == "RATE_LIMITED"
    assert 3000 < int(r.headers["Retry-After"]) <= 3600
    genuine = issue(api, staff["product_id"])["delivery"]["activation_key"]
    restarted = Api(create_test_app(settings, issuer=issuer), issuer)
    assert redeem(restarted, "guesser", genuine).status_code == 429  # failed attempts were not erased
    assert actor_attempts(clean_db, api.user_id("guesser")) == 10
    assert redeem(restarted, "other-user", genuine).status_code == 201  # per-actor budget


def test_concurrent_limit_boundary_across_processes(api, staff, clean_db, settings, issuer):
    user = api.user_id("racer")
    seed_attempts(clean_db, user, 9)
    start = time.time() + 12
    jobs = [{"settings": asdict(settings), "jwks": issuer.jwks(), "token": issuer.token("racer", ttl_s=600),
             "key": f"AAAA-BBBB-CCCC-DD{c}{c}", "idem": f"boundary-{c}-0001", "start_at": start} for c in "ABCDEF"]
    results = run_processes(jobs)
    statuses = sorted(s for s, _ in results)
    assert statuses.count(429) == 5 and statuses.count(400) == 1, results
    assert actor_attempts(clean_db, user) == 10


def test_ip_and_global_budgets_are_configurable(clean_db, issuer, staff, api):
    tight = Api(create_test_app(make_settings(clean_db, issuer, redemption_ip_limit=2, trusted_proxies=("testclient",)),
                                issuer=issuer), issuer)
    hdr = {"X-Forwarded-For": "203.0.113.9"}
    for sub in ("ip-a", "ip-b"):
        assert tight.post("/api/v2/redemptions", sub, json={"activation_key": "AAAA-AAAA-AAAA-AAAA"},
                          idem="ip-" + sub + "-0001", headers=hdr).status_code == 400
    third = tight.post("/api/v2/redemptions", "ip-c", json={"activation_key": "AAAA-AAAA-AAAA-AAAA"},
                       idem="ip-c-00001", headers=hdr)
    assert third.status_code == 429
    assert query(clean_db, "SELECT count(*) FROM attempt_event WHERE scope='ip' AND scope_key='203.0.113.9'") == [(2,)]
    glob = Api(create_test_app(make_settings(clean_db, issuer, redemption_global_limit=0), issuer=issuer), issuer)
    assert redeem(glob, "g-user", "AAAA-AAAA-AAAA-AAAA").status_code == 429


def test_unavailable_admission_store_fails_closed(api, staff, clean_db, monkeypatch):
    key = issue(api, staff["product_id"])["delivery"]["activation_key"]

    def broken(self, *a, **k):
        raise OperationalError("SELECT ... FOR UPDATE", {}, Exception("connection lost"))

    monkeypatch.setattr(SqlAttemptLedger, "reserve", broken)
    r = redeem(api, "customer-a", key, idem="unavail-0001")
    assert r.status_code == 503 and r.json()["code"] == "SERVICE_UNAVAILABLE"
    assert counts(clean_db, "owned_item") == {"owned_item": 0}
    assert query(clean_db, "SELECT count(*) FROM idempotency_record WHERE route = 'POST /api/v2/redemptions'") == [(0,)]
    monkeypatch.undo()
    assert redeem(api, "customer-a", key, idem="unavail-0001").status_code == 201


# ------------------------------------------------------------------ 6.2 idempotency
def test_identical_retry_reserves_no_new_attempt_and_changed_body_409(api, staff, clean_db):
    key = issue(api, staff["product_id"])["delivery"]["activation_key"]
    user = api.user_id("customer-a")
    first = redeem(api, "customer-a", key, idem="retry-0001")
    for _ in range(3):
        again = redeem(api, "customer-a", key, idem="retry-0001")
        assert again.status_code == 201 and again.json() == first.json()
    assert actor_attempts(clean_db, user) == 1
    other = redeem(api, "customer-a", "AAAA-BBBB-CCCC-DDDD", idem="retry-0001")
    assert other.status_code == 409 and other.json()["code"] == "IDEMPOTENCY_KEY_REUSED"
    assert actor_attempts(clean_db, user) == 1  # the new credential was not evaluated or admitted
    invalid_again = [redeem(api, "customer-a", "AAAA-BBBB-CCCC-DDDD", idem=f"fresh-{i}-0001") for i in range(2)]
    assert all(r.status_code == 400 for r in invalid_again)
    assert actor_attempts(clean_db, user) == 3  # invalid key under new operation keys = fresh attempts


def test_missing_or_bad_idempotency_key_is_422(api, staff):
    r = api.post("/api/v2/redemptions", "customer-a", json={"activation_key": "AAAA-BBBB-CCCC-DDDD"})
    assert r.status_code == 422 and r.json()["field_errors"][0]["field"] == "header.Idempotency-Key"
    r = api.post("/api/v2/redemptions", "customer-a", json={"activation_key": "AAAA-BBBB-CCCC-DDDD"}, idem="short")
    assert r.status_code == 422


def test_concurrent_identical_requests_produce_one_effect(api, staff, clean_db):
    key = issue(api, staff["product_id"])["delivery"]["activation_key"]
    token = api.issuer.token("customer-a")
    out = []

    def go():
        out.append(api.client.post("/api/v2/redemptions", json={"activation_key": key},
                                   headers={"Authorization": "Bearer " + token, "Idempotency-Key": "same-op-0001"}))

    ts = [threading.Thread(target=go) for _ in range(6)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert {r.status_code for r in out} == {201}
    assert len({r.json()["id"] for r in out}) == 1
    assert counts(clean_db, "owned_item", "ownership_event") == {"owned_item": 1, "ownership_event": 1}
    assert actor_attempts(clean_db, api.user_id("customer-a")) == 1


def test_abandoned_processing_recovers_via_lease(clean_db, issuer, api, staff, monkeypatch):
    key = issue(api, staff["product_id"])["delivery"]["activation_key"]
    def crash(p):
        if p == "redeem.after_item":
            raise RuntimeError("process died here")

    crashy = Api(create_test_app(make_settings(clean_db, issuer, idempotency_lease_s=1.0), issuer=issuer,
                                 faults=crash), issuer)
    monkeypatch.setattr(type(crashy.services.redemption.executor), "_abandon", lambda *a: None)  # hard crash: no cleanup
    assert redeem(crashy, "customer-a", key, idem="crash-op-0001").status_code == 500
    monkeypatch.undo()
    assert query(clean_db, "SELECT status, attempt_reserved FROM idempotency_record "
                           "WHERE route = 'POST /api/v2/redemptions'") == [("processing", True)]
    healthy = Api(create_test_app(make_settings(clean_db, issuer, idempotency_lease_s=1.0), issuer=issuer), issuer)
    t0 = time.monotonic()
    r = redeem(healthy, "customer-a", key, idem="crash-op-0001")
    assert r.status_code == 201 and time.monotonic() - t0 >= 0.5  # waited for the lease, then took over
    assert counts(clean_db, "owned_item") == {"owned_item": 1}
    assert actor_attempts(clean_db, api.user_id("customer-a")) == 1  # takeover did not reserve again


# ------------------------------------------------------------------ 6.4 races and fault injection
def test_two_users_race_one_bearer_key_across_processes(api, staff, clean_db, settings, issuer):
    key = issue(api, staff["product_id"])["delivery"]["activation_key"]
    start = time.time() + 12
    jobs = [{"settings": asdict(settings), "jwks": issuer.jwks(), "token": issuer.token(sub, ttl_s=600), "key": key,
             "idem": f"race-{sub}-0001", "start_at": start} for sub in ("racer-a", "racer-b", "racer-c", "racer-d")]
    results = run_processes(jobs)
    assert sorted(results) == sorted([(201, None)] + [(400, "INVALID_ACTIVATION_CODE")] * 3), results
    assert counts(clean_db, "owned_item", "ownership_event") == {"owned_item": 1, "ownership_event": 1}
    assert query(clean_db, "SELECT count(*) FROM outbox_event WHERE event_type='ownership.item_claimed'") == [(1,)]


@pytest.mark.parametrize("point", POINTS)
def test_failure_between_claim_effects_leaves_no_partial_state(clean_db, issuer, api, staff, point):
    unit = issue(api, staff["product_id"])
    key = unit["delivery"]["activation_key"]

    def fail(p):
        if p == point:
            raise RuntimeError("injected failure at " + p)

    faulty = Api(create_test_app(make_settings(clean_db, issuer), issuer=issuer, faults=fail), issuer)
    before = counts(clean_db, *CLAIM_TABLES)
    r = redeem(faulty, "customer-a", key, idem="fault-op-0001")
    assert r.status_code == 500 and r.json()["code"] == "INTERNAL_ERROR"
    assert counts(clean_db, *CLAIM_TABLES) == before
    assert query(clean_db, "SELECT status FROM activation_credential") == [("active",)]
    assert query(clean_db, "SELECT status FROM garment_unit") == [("issued",)]
    assert query(clean_db, "SELECT ciphertext IS NOT NULL FROM issuance_delivery") == [(True,)]
    user = api.user_id("customer-a")
    assert actor_attempts(clean_db, user) == 1  # reservation committed independently and retained
    retry = redeem(api, "customer-a", key, idem="fault-op-0001")
    assert retry.status_code == 201
    assert counts(clean_db, "owned_item", "ownership_event") == {"owned_item": 1, "ownership_event": 1}
    assert actor_attempts(clean_db, user) == 1


def test_lost_response_retry_after_restart_has_one_effect(api, staff, clean_db, settings, issuer):
    key = issue(api, staff["product_id"])["delivery"]["activation_key"]
    first = redeem(api, "customer-a", key, idem="lost-claim-0001").json()
    snapshot = counts(clean_db, *CLAIM_TABLES, "attempt_event", "audit_event")
    restarted = Api(create_test_app(settings, issuer=issuer), issuer)
    again = redeem(restarted, "customer-a", key, idem="lost-claim-0001")
    assert again.status_code == 201 and again.json() == first
    assert counts(clean_db, *CLAIM_TABLES, "attempt_event", "audit_event") == snapshot


def test_redemption_with_every_admission_limit_disabled(clean_db, issuer):
    """RQ3 validation-corpus mode (never deployable): no scopes -> no attempt rows, and no crash."""
    import dataclasses

    from conftest import Api, make_settings
    from wearhouse.testing import create_test_app
    s = dataclasses.replace(make_settings(clean_db, issuer), redemption_actor_limit=None, redemption_ip_limit=None,
                            redemption_global_limit=None)
    api = Api(create_test_app(s, issuer=issuer), issuer)
    for _ in range(12):  # beyond the production per-user limit
        assert redeem(api, "free-user", "AAAA-BBBB-CCCC-DDDD").status_code == 400
    assert counts(clean_db, "attempt_event")["attempt_event"] == 0
