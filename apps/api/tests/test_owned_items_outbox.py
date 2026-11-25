"""6.5 owner-scoped reads with stable bounded cursors; 6.6 outbox dispatch/retry with idempotent event ids."""
from __future__ import annotations

import pytest
from sqlalchemy import text

from conftest import admin_engine, counts, issue, query, redeem
from wearhouse.platform.db import make_engine
from wearhouse.platform.outbox import OutboxDispatcher

pytestmark = [pytest.mark.postgres, pytest.mark.synthetic_only]


def claim_many(api, staff, db, sub: str, n: int) -> list[str]:
    ids = []
    for i in range(n):
        if i and i % 9 == 0:  # stay under the hourly attempt budget while building read fixtures
            eng = admin_engine(db.name)
            with eng.connect() as c:
                c.execute(text("DELETE FROM attempt_event"))
            eng.dispose()
        key = issue(api, staff["product_id"])["delivery"]["activation_key"]
        r = redeem(api, sub, key)
        assert r.status_code == 201, r.text
        ids.append(r.json()["id"])
    return ids


# ------------------------------------------------------------------ 6.5
def test_stable_pagination_default_24_and_cursor(api, staff, clean_db):
    ids = claim_many(api, staff, clean_db, "collector", 30)
    page1 = api.get("/api/v2/me/items", "collector")
    assert page1.status_code == 200 and page1.headers["cache-control"] == "no-store"
    body1 = page1.json()
    assert len(body1["items"]) == 24 and body1["next_cursor"]
    page2 = api.get("/api/v2/me/items", "collector", params={"cursor": body1["next_cursor"]}).json()
    assert len(page2["items"]) == 6 and page2["next_cursor"] is None
    got = [i["id"] for i in body1["items"] + page2["items"]]
    assert sorted(got) == sorted(ids) and len(set(got)) == 30
    claim_many(api, staff, clean_db, "collector", 1)  # new items do not reshuffle earlier pages
    again = api.get("/api/v2/me/items", "collector", params={"cursor": body1["next_cursor"]}).json()
    assert [i["id"] for i in again["items"]][:6] == [i["id"] for i in page2["items"]]
    small = api.get("/api/v2/me/items", "collector", params={"limit": 100}).json()
    assert len(small["items"]) == 31
    for bad in (0, 101):
        assert api.get("/api/v2/me/items", "collector", params={"limit": bad}).status_code == 422


def test_cross_user_isolation_and_uniform_404(api, staff, clean_db):
    [item_id] = claim_many(api, staff, clean_db, "owner-a", 1)
    assert api.get("/api/v2/me/items", "intruder-b").json() == {"items": [], "next_cursor": None}
    probe = api.get(f"/api/v2/me/items/{item_id}", "intruder-b")
    absent = api.get("/api/v2/me/items/00000000-0000-4000-8000-000000000000", "intruder-b")
    garbage = api.get("/api/v2/me/items/not-a-uuid", "intruder-b")
    for r in (probe, absent, garbage):
        assert r.status_code == 404
        assert {k: v for k, v in r.json().items() if k != "request_id"} == \
            {"code": "NOT_FOUND", "message": "Item not found."}
    assert item_id not in probe.text
    mine = api.get(f"/api/v2/me/items/{item_id}", "owner-a").json()
    acq = mine["acquisition"]
    assert acq["source_namespace"] == "wearhouse-synthetic-test" and acq["external_id"] == "0000000001"
    assert acq["revision_no"] == 1 and len(acq["snapshot_sha256"]) == 64


def test_cursor_is_bound_to_actor_and_tamper_evident(api, staff, clean_db):
    claim_many(api, staff, clean_db, "owner-a", 3)
    cursor = api.get("/api/v2/me/items", "owner-a", params={"limit": 1}).json()["next_cursor"]
    replay = api.get("/api/v2/me/items", "intruder-b", params={"cursor": cursor})
    assert replay.status_code == 422 and replay.json()["field_errors"][0]["code"] == "invalid_cursor"
    b64, tag = cursor.split(".")
    for forged in (b64 + "." + "0" * len(tag), b64[:-2] + "." + tag, "garbage", "a.b"):
        assert api.get("/api/v2/me/items", "owner-a", params={"cursor": forged}).status_code == 422


# ------------------------------------------------------------------ 6.6
def test_rolled_back_claim_creates_no_deliverable_event(clean_db, issuer, api, staff):
    from conftest import Api, make_settings
    from wearhouse.testing import create_test_app

    key = issue(api, staff["product_id"])["delivery"]["activation_key"]

    def fail(point):
        if point == "redeem.after_outbox":
            raise RuntimeError("fail after the outbox insert")

    faulty = Api(create_test_app(make_settings(clean_db, issuer), issuer=issuer, faults=fail), issuer)
    assert redeem(faulty, "customer-a", key).status_code == 500
    assert query(clean_db, "SELECT count(*) FROM outbox_event WHERE event_type = 'ownership.item_claimed'") == [(0,)]


def test_dispatch_is_idempotent_and_retries_failures(api, staff, clean_db):
    key = issue(api, staff["product_id"])["delivery"]["activation_key"]
    assert redeem(api, "customer-a", key).status_code == 201
    engine = make_engine(clean_db.runtime_url)
    seen: list = []
    flaky = {"fail": True}

    def downstream(msg):
        if msg.id in {m.id for m in seen}:
            raise AssertionError("duplicate delivery")
        seen.append(msg)

    def sometimes(msg):
        if flaky["fail"]:
            raise ConnectionError("downstream unavailable")

    d = OutboxDispatcher(engine, {"a-downstream": downstream, "b-flaky": sometimes})
    first = d.dispatch_once()
    total = counts(clean_db, "outbox_event")["outbox_event"]
    assert first["events"] == total and first["failed"] == total  # b-flaky failed for every event
    assert len(seen) == total
    assert query(clean_db, "SELECT count(*) FROM outbox_event WHERE dispatched_at IS NULL AND attempts = 1 "
                           "AND last_error LIKE 'b-flaky: ConnectionError'") == [(total,)]
    assert d.dispatch_once()["events"] == 0  # backoff: not yet available again
    eng = admin_engine(clean_db.name)
    with eng.connect() as c:
        c.execute(text("UPDATE outbox_event SET available_at = now() - interval '1 second'"))
    eng.dispose()
    flaky["fail"] = False
    second = d.dispatch_once()
    assert second["failed"] == 0 and second["delivered"] == total  # only b-flaky ran; a-downstream not repeated
    assert len(seen) == total
    assert d.dispatch_once() == {"delivered": 0, "failed": 0, "events": 0}
    assert query(clean_db, "SELECT count(*) FROM outbox_event WHERE dispatched_at IS NULL") == [(0,)]
    payloads = " ".join(str(p) for (p,) in query(clean_db, "SELECT payload::text FROM outbox_event"))
    assert key not in payloads and key.replace("-", "") not in payloads
    engine.dispose()
