"""add-wearhouse-accounts §6: sign out everywhere, export, deletion with an ownership-preserving tombstone."""
from __future__ import annotations

import json
import time

import pytest

from conftest import Api, befriend, counts, create_test_app, issue, make_settings, onboard, query, redeem, synthetic_product
from wearhouse.ownership.domain import key_digest, normalize_key

pytestmark = pytest.mark.postgres


def token_headers(api, sub, **kw):
    return {"Authorization": "Bearer " + api.issuer.token(sub, **kw)}


def set_privacy(api, sub, **kw):
    cur = api.get("/api/v2/me/privacy", sub).json()
    api.client.put("/api/v2/me/privacy", json={**cur, **kw}, headers=api.headers(sub))


def give_item(api, sub):
    api.grant("ed", "catalogue_editor")
    api.grant("inv", "inventory_manager")
    pid = api.post("/api/v2/admin/source-products", "ed", json=synthetic_product()).json()["product_id"]
    unit = issue(api, pid, sub="inv")
    assert redeem(api, sub, unit["delivery"]["activation_key"]).status_code == 201
    return unit


# ------------------------------------------------------------------ 6.1
def test_sign_out_everywhere(neon, clean_db):
    stolen = token_headers(neon, "victim", now=time.time() - 30)
    assert neon.client.get("/api/v2/me/items", headers=stolen).status_code == 200
    assert neon.client.post("/api/v2/me/sessions/revoke-all", headers=stolen).status_code == 204
    assert neon.client.get("/api/v2/me/items", headers=stolen).status_code == 401
    fresh = token_headers(neon, "victim", now=time.time() + 2)
    assert neon.client.get("/api/v2/me/items", headers=fresh).status_code == 200
    assert query(clean_db, "SELECT count(*) FROM audit_event WHERE action = 'account.sessions_revoked'") == [(1,)]


# ------------------------------------------------------------------ 6.2
def test_export_contents_privacy_and_limit(neon, clean_db):
    onboard(neon, "exporter")
    onboard(neon, "friend_x")
    onboard(neon, "requester")
    onboard(neon, "blockee")
    unit = give_item(neon, "exporter")
    befriend(neon, "exporter", "friend_x")
    neon.post("/api/v2/me/friend-requests", "requester", json={"handle": "exporter"}, idem="req-to-exporter-1")
    neon.client.put("/api/v2/me/blocks/blockee", headers=neon.headers("exporter"))
    give_item(neon, "friend_x")  # someone else's private data must not leak into the export
    r = neon.get("/api/v2/me/export", "exporter")
    assert r.status_code == 200 and r.headers["cache-control"] == "no-store"
    assert "attachment" in r.headers["content-disposition"]
    doc = r.json()
    for k in ("account", "profile", "handle_holds", "friends", "requests", "blocks", "owned_items"):
        assert k in doc
    assert [f["handle"] for f in doc["friends"]] == ["friend_x"]
    assert [x["account"]["handle"] for x in doc["requests"]["incoming"]] == ["requester"]
    assert [b["handle"] for b in doc["blocks"]] == ["blockee"]
    assert [i["public_serial"] for i in doc["owned_items"]] == [unit["public_serial"]]
    text = json.dumps(doc)
    key = unit["delivery"]["activation_key"]
    assert key not in text and key_digest(normalize_key(key)) not in text and "exporter@example.test" not in text
    friend_serials = [s for (s,) in query(clean_db, "SELECT public_serial FROM garment_unit")]
    assert sum(s in text for s in friend_serials) == 1
    for _ in range(4):
        assert neon.get("/api/v2/me/export", "exporter").status_code == 200
    sixth = neon.get("/api/v2/me/export", "exporter")
    assert sixth.status_code == 429 and sixth.json()["code"] == "RATE_LIMITED"


# ------------------------------------------------------------------ 6.3
def delete(api, sub, confirm, **kw):
    return api.client.request("DELETE", "/api/v2/me", json={"confirm": confirm}, headers=token_headers(api, sub, **kw))


def test_delete_guards_change_nothing(neon, clean_db):
    onboard(neon, "careful")
    before = counts(clean_db, "account_profile", "user_subject", "app_user")
    stale = delete(neon, "careful", "careful", now=time.time() - 400)
    assert stale.status_code == 401 and stale.json()["code"] == "REAUTHENTICATION_REQUIRED"
    wrong = delete(neon, "careful", "not-my-handle")
    assert wrong.status_code == 422
    assert counts(clean_db, "account_profile", "user_subject", "app_user") == before
    neon.get("/api/v2/me", "nohandle")
    assert delete(neon, "nohandle", "nohandle").status_code == 422
    assert delete(neon, "nohandle", "DELETE").status_code == 204


def test_delete_then_sign_in_again(neon, clean_db, neon_issuer):
    onboard(neon, "leaver")
    onboard(neon, "buddy")
    unit = give_item(neon, "leaver")
    befriend(neon, "leaver", "buddy")
    neon.client.put("/api/v2/me/blocks/leaver", headers=neon.headers("buddy"))  # also ends the friendship
    neon.client.delete("/api/v2/me/blocks/leaver", headers=neon.headers("buddy"))
    befriend(neon, "leaver", "buddy")
    old_id = neon.user_id("leaver")
    assert delete(neon, "leaver", "leaver").status_code == 204
    assert counts(clean_db, "friendship", "friend_request")["friendship"] == 0
    assert query(clean_db, "SELECT count(*) FROM user_block WHERE blocker = :u OR blocked = :u", u=old_id) == [(0,)]
    tomb = query(clean_db, "SELECT deleted_at IS NOT NULL, display_name FROM app_user WHERE id = :u", u=old_id)
    assert tomb == [(True, None)]
    assert query(clean_db, "SELECT count(*) FROM user_subject WHERE user_id = :u", u=old_id) == [(0,)]
    assert query(clean_db, "SELECT count(*) FROM owned_item WHERE user_id = :u", u=old_id) == [(1,)]  # history kept
    # gone for everyone else
    assert neon.get("/api/v2/profiles/leaver", "buddy").status_code == 404
    assert neon.get("/api/v2/me/friends", "buddy").json()["friends"] == []
    assert neon.get("/api/v2/users/search", "buddy", params={"q": "@leaver"}).json()["results"] == []
    # the claimed unit stays claimed
    again = redeem(neon, "buddy", unit["delivery"]["activation_key"])
    assert again.status_code == 400 and again.json()["code"] == "INVALID_ACTIVATION_CODE"
    # same broker subject -> brand-new empty account; handle is held for 30 days
    me = neon.get("/api/v2/me", "leaver").json()
    assert me["user_id"] != str(old_id) and me["needs_onboarding"] is True
    assert neon.get("/api/v2/me/items", "leaver").json()["items"] == []
    assert neon.client.patch("/api/v2/me/profile", json={"handle": "leaver"},
                             headers=neon.headers("buddy2")).json()["code"] == "HANDLE_UNAVAILABLE"
    audit = query(clean_db, "SELECT details::text FROM audit_event WHERE action = 'account.deleted'")
    assert audit and "leaver" not in audit[0][0]
    out = query(clean_db, "SELECT payload::text FROM outbox_event WHERE event_type = 'account.deleted'")
    assert out == [("{}",)]


@pytest.mark.parametrize("point", ["delete.after_social", "delete.after_tombstone"])
def test_fault_during_deletion_leaves_no_partial_state(clean_db, neon_issuer, neon, point):
    onboard(neon, "wobbly")
    onboard(neon, "pal")
    befriend(neon, "wobbly", "pal")

    def fail(p):
        if p == point:
            raise RuntimeError("injected")

    faulty = Api(create_test_app(make_settings(clean_db, neon_issuer), issuer=neon_issuer, faults=fail), neon_issuer)
    snapshot = counts(clean_db, "account_profile", "privacy_setting", "friendship", "user_subject", "handle_hold")
    assert delete(faulty, "wobbly", "wobbly").status_code == 500
    assert counts(clean_db, "account_profile", "privacy_setting", "friendship", "user_subject", "handle_hold") == snapshot
    assert query(clean_db, "SELECT count(*) FROM app_user WHERE deleted_at IS NOT NULL") == [(0,)]
    assert neon.get("/api/v2/profiles/wobbly").status_code == 200


def test_deleted_relation_on_public_projections(neon, clean_db):
    onboard(neon, "ghost")
    set_privacy(neon, "ghost", wardrobe="public", friends_list="public")
    give_item(neon, "ghost")
    assert neon.get("/api/v2/profiles/ghost/wardrobe").status_code == 200
    assert delete(neon, "ghost", "ghost").status_code == 204
    for path in ("/api/v2/profiles/ghost", "/api/v2/profiles/ghost/wardrobe", "/api/v2/profiles/ghost/friends"):
        assert neon.get(path).status_code == 404
