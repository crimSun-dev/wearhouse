"""add-wearhouse-accounts §5: friend request lifecycle, removal, blocking and social limits."""
from __future__ import annotations

import multiprocessing
import threading
import time
import uuid
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict

import pytest
from sqlalchemy import text

from _workers import friend_request_in_process
from conftest import Api, admin_engine, befriend, counts, create_test_app, make_settings, onboard, query

pytestmark = pytest.mark.postgres


def send(api, a, b, idem=None):
    return api.post("/api/v2/me/friend-requests", a, json={"handle": b}, idem=idem or "fr-" + uuid.uuid4().hex)


def friends_of(api, sub):
    return sorted(f["handle"] for f in api.get("/api/v2/me/friends", sub).json()["friends"])


def users(api, *subs):
    for s in subs:
        onboard(api, s)


# ------------------------------------------------------------------ 5.1 requests
def test_send_accept_lists_and_mutual_friendship(neon, clean_db):
    users(neon, "ann", "ben")
    r = send(neon, "ann", "ben")
    assert r.status_code == 201 and r.json()["status"] == "pending"
    assert [x["account"]["handle"] for x in neon.get("/api/v2/me/friend-requests", "ben",
                                                     params={"direction": "incoming"}).json()["requests"]] == ["ann"]
    assert [x["account"]["handle"] for x in neon.get("/api/v2/me/friend-requests", "ann",
                                                     params={"direction": "outgoing"}).json()["requests"]] == ["ben"]
    acc = neon.post(f"/api/v2/me/friend-requests/{r.json()['request_id']}/accept", "ben")
    assert acc.json() == {"status": "accepted"}
    again = neon.post(f"/api/v2/me/friend-requests/{r.json()['request_id']}/accept", "ben")
    assert again.json() == {"status": "accepted"}  # idempotent
    assert friends_of(neon, "ann") == ["ben"] and friends_of(neon, "ben") == ["ann"]
    assert counts(clean_db, "friendship") == {"friendship": 1}
    assert neon.get("/api/v2/me/friend-requests", "ben").json()["requests"] == []
    assert send(neon, "ann", "ben").json()["code"] == "ALREADY_FRIENDS"


def test_duplicate_send_and_crossed_requests(neon, clean_db):
    users(neon, "cat", "dan")
    first = send(neon, "cat", "dan").json()
    dup = send(neon, "cat", "dan")
    assert dup.status_code == 200 and dup.json()["request_id"] == first["request_id"]
    assert counts(clean_db, "friend_request") == {"friend_request": 1}
    crossed = send(neon, "dan", "cat")
    assert crossed.status_code == 200 and crossed.json()["status"] == "accepted"
    assert friends_of(neon, "cat") == ["dan"]
    assert query(clean_db, "SELECT status FROM friend_request") == [("accepted",)]
    replay = send(neon, "dan", "cat", idem="same-key-0001")
    assert replay.json()["code"] == "ALREADY_FRIENDS"


def test_decline_cancel_and_non_pending(neon, clean_db):
    users(neon, "eve", "fay")
    rid = send(neon, "eve", "fay").json()["request_id"]
    assert neon.post(f"/api/v2/me/friend-requests/{rid}/decline", "fay").json() == {"status": "declined"}
    assert neon.post(f"/api/v2/me/friend-requests/{rid}/accept", "fay").json()["code"] == "REQUEST_NOT_PENDING"
    rid2 = send(neon, "eve", "fay").json()["request_id"]
    assert neon.post(f"/api/v2/me/friend-requests/{rid2}/accept", "eve").status_code == 404  # only recipient
    assert neon.client.delete(f"/api/v2/me/friend-requests/{rid2}", headers=neon.headers("fay")).status_code == 404
    assert neon.client.delete(f"/api/v2/me/friend-requests/{rid2}",
                              headers=neon.headers("eve")).json() == {"status": "cancelled"}
    assert friends_of(neon, "eve") == []


def test_concurrent_accept_versus_cancel_single_outcome(neon, clean_db):
    users(neon, "gus", "hal")
    for _ in range(5):
        rid = send(neon, "gus", "hal").json()["request_id"]
        out = {}

        def accept():
            out["a"] = neon.post(f"/api/v2/me/friend-requests/{rid}/accept", "hal").status_code

        def cancel():
            out["c"] = neon.client.delete(f"/api/v2/me/friend-requests/{rid}", headers=neon.headers("gus")).status_code

        ts = [threading.Thread(target=accept), threading.Thread(target=cancel)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        status = query(clean_db, "SELECT status FROM friend_request WHERE id = :i", i=uuid.UUID(rid))[0][0]
        fr = counts(clean_db, "friendship")["friendship"]
        assert (status, fr) in (("accepted", 1), ("cancelled", 0)), (status, fr, out)
        assert sorted(out.values()) == [200, 409]
        if fr:
            neon.client.delete("/api/v2/me/friends/hal", headers=neon.headers("gus"))


def test_self_unknown_and_blocked_targets(neon, clean_db):
    users(neon, "ivy", "jon")
    assert send(neon, "ivy", "ivy").status_code == 422
    unknown = send(neon, "ivy", "no_such_user")
    assert unknown.status_code == 404
    neon.client.put("/api/v2/me/blocks/ivy", headers=neon.headers("jon"))
    blocked = send(neon, "ivy", "jon")
    assert blocked.status_code == 404
    assert {k: v for k, v in blocked.json().items() if k != "request_id"} == \
        {k: v for k, v in unknown.json().items() if k != "request_id"}
    assert counts(clean_db, "friend_request") == {"friend_request": 0}


def test_request_lists_are_owner_only(neon, clean_db):
    users(neon, "kim", "lou", "moe")
    for s in ("lou", "moe"):
        send(neon, s, "kim")
    page = neon.get("/api/v2/me/friend-requests", "kim", params={"limit": 1}).json()
    assert len(page["requests"]) == 1 and page["next_cursor"]
    stolen = neon.get("/api/v2/me/friend-requests", "lou", params={"cursor": page["next_cursor"]})
    assert stolen.status_code == 422 and stolen.json()["field_errors"][0]["code"] == "invalid_cursor"


# ------------------------------------------------------------------ 5.2 removal
def test_remove_friend_is_mutual_and_immediate(neon, clean_db):
    users(neon, "nat", "oli")
    befriend(neon, "nat", "oli")
    neon.client.put("/api/v2/me/privacy", json={"profile": "public", "wardrobe": "friends", "friends_list": "friends"},
                    headers=neon.headers("nat"))
    assert neon.get("/api/v2/profiles/nat/friends", "oli").status_code == 200
    assert neon.client.delete("/api/v2/me/friends/nat", headers=neon.headers("oli")).status_code == 204
    assert friends_of(neon, "nat") == [] and friends_of(neon, "oli") == []
    assert neon.get("/api/v2/profiles/nat/friends", "oli").status_code == 404
    assert neon.get("/api/v2/profiles/nat/wardrobe", "oli").status_code == 404


# ------------------------------------------------------------------ 5.3 blocking
def test_block_ends_friendship_and_requests_atomically(neon, clean_db):
    users(neon, "pat", "quin")
    befriend(neon, "pat", "quin")
    send(neon, "quin", "pat")  # can't exist while friends -> ALREADY_FRIENDS; create another pending pair:
    users(neon, "ray")
    send(neon, "ray", "pat")
    assert neon.client.put("/api/v2/me/blocks/quin", headers=neon.headers("pat")).status_code == 204
    assert neon.client.put("/api/v2/me/blocks/ray", headers=neon.headers("pat")).status_code == 204
    assert friends_of(neon, "pat") == [] and counts(clean_db, "friend_request")["friend_request"] == 1  # accepted row
    assert query(clean_db, "SELECT count(*) FROM friend_request WHERE status = 'pending'") == [(0,)]
    assert neon.get("/api/v2/users/search", "quin", params={"q": "@pat"}).json()["results"] == []
    assert send(neon, "quin", "pat").status_code == 404
    assert sorted(b["handle"] for b in neon.get("/api/v2/me/blocks", "pat").json()["blocks"]) == ["quin", "ray"]
    assert neon.client.put("/api/v2/me/blocks/quin", headers=neon.headers("pat")).status_code == 204  # idempotent
    assert neon.client.delete("/api/v2/me/blocks/quin", headers=neon.headers("pat")).status_code == 204
    assert friends_of(neon, "pat") == []  # nothing restored
    assert send(neon, "quin", "pat").status_code == 201


@pytest.mark.parametrize("point", ["block.after_unfriend", "block.after_requests"])
def test_fault_mid_block_leaves_no_partial_state(clean_db, neon_issuer, neon, point):
    users(neon, "sam", "tia")
    befriend(neon, "sam", "tia")

    def fail(p):
        if p == point:
            raise RuntimeError("injected")

    faulty = Api(create_test_app(make_settings(clean_db, neon_issuer), issuer=neon_issuer, faults=fail), neon_issuer)
    assert faulty.client.put("/api/v2/me/blocks/tia", headers=faulty.headers("sam")).status_code == 500
    assert counts(clean_db, "friendship", "user_block") == {"friendship": 1, "user_block": 0}


# ------------------------------------------------------------------ 5.4 limits
def seed_attempts(db, user_id, n):
    eng = admin_engine(db.name)
    with eng.connect() as c:
        c.execute(text("INSERT INTO attempt_bucket (scope, scope_key) VALUES ('friend_request', :u) "
                       "ON CONFLICT DO NOTHING"), {"u": str(user_id)})
        for _ in range(n):
            c.execute(text("INSERT INTO attempt_event (id, scope, scope_key, reserved_at) "
                           "VALUES (:i, 'friend_request', :u, now() - interval '1 hour')"),
                      {"i": uuid.uuid4(), "u": str(user_id)})
    eng.dispose()


def test_fifty_requests_per_day_then_429(neon, clean_db):
    users(neon, "spam", "victim")
    seed_attempts(clean_db, neon.user_id("spam"), 50)
    r = send(neon, "spam", "victim")
    assert r.status_code == 429 and r.json()["code"] == "RATE_LIMITED" and int(r.headers["Retry-After"]) > 3600
    assert counts(clean_db, "friend_request") == {"friend_request": 0}


def test_friend_and_pending_caps(neon, clean_db, monkeypatch):
    import wearhouse.accounts.domain as d
    users(neon, "popular", "one_more", "pend_a", "pend_b")
    monkeypatch.setattr(d, "MAX_FRIENDS", 1)
    monkeypatch.setattr(d, "MAX_PENDING_OUTGOING", 1)
    befriend(neon, "popular", "one_more")
    rid = send(neon, "pend_a", "popular").json()["request_id"]
    full = neon.post(f"/api/v2/me/friend-requests/{rid}/accept", "popular")
    assert full.status_code == 409 and full.json()["code"] == "FRIEND_LIMIT_REACHED"
    assert counts(clean_db, "friendship") == {"friendship": 1}
    assert send(neon, "pend_b", "one_more").status_code == 201  # pend_b's first pending request is fine
    capped = send(neon, "pend_a", "pend_b")
    assert capped.status_code == 409 and capped.json()["code"] == "PENDING_LIMIT_REACHED"


def test_rate_limit_boundary_across_processes(neon, clean_db, neon_issuer):
    users(neon, "burst", *[f"tgt_{i}" for i in range(6)])
    seed_attempts(clean_db, neon.user_id("burst"), 49)
    settings = make_settings(clean_db, neon_issuer)
    start = time.time() + 12
    jobs = [{"settings": asdict(settings), "jwks": neon_issuer.jwks(), "token": neon_issuer.token("burst", ttl_s=600),
             "handle": f"tgt_{i}", "idem": f"burst-{i}-00001", "start_at": start} for i in range(6)]
    with ProcessPoolExecutor(max_workers=6, mp_context=multiprocessing.get_context("spawn")) as pool:
        results = list(pool.map(friend_request_in_process, jobs))
    assert sorted(results) == [201, 429, 429, 429, 429, 429], results
    assert counts(clean_db, "friend_request") == {"friend_request": 1}


def test_block_cap(neon, clean_db, monkeypatch):
    import wearhouse.accounts.domain as d
    users(neon, "cap_owner", "cap_one", "cap_two")
    monkeypatch.setattr(d, "MAX_BLOCKS", 1)
    assert neon.client.put("/api/v2/me/blocks/cap_one", headers=neon.headers("cap_owner")).status_code == 204
    assert neon.client.put("/api/v2/me/blocks/cap_one", headers=neon.headers("cap_owner")).status_code == 204
    over = neon.client.put("/api/v2/me/blocks/cap_two", headers=neon.headers("cap_owner"))
    assert over.status_code == 409 and over.json()["code"] == "BLOCK_LIMIT_REACHED"
