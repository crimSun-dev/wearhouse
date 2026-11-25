"""add-wearhouse-accounts §4: handles, profile fields, privacy settings, public projections, search."""
from __future__ import annotations

import threading
from datetime import timedelta

import pytest
from sqlalchemy import text

from conftest import (Api, admin_engine, befriend, counts, create_test_app, issue, make_settings, onboard, query,
                      redeem, synthetic_product)
from wearhouse.platform.clock import utcnow

pytestmark = pytest.mark.postgres


def h(api, sub, **kw):
    return api.headers(sub, **kw)


def patch(api, sub, body, **kw):
    return api.client.patch("/api/v2/me/profile", json=body, headers=api.headers(sub, **kw))


# ------------------------------------------------------------------ 4.1 profile & handles
def test_choose_handle_lowercases_and_finishes_onboarding(neon, clean_db):
    r = patch(neon, "draven", {"handle": "Dravenstyle", "display_name": "Draven", "bio": "Plum enjoyer"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["handle"] == "dravenstyle" and body["needs_onboarding"] is False and body["bio"] == "Plum enjoyer"
    assert neon.get("/api/v2/me", "draven").json()["needs_onboarding"] is False
    assert neon.get("/api/v2/profiles/DravenStyle").status_code == 200


def test_taken_reserved_held_and_invalid_handles(neon, clean_db):
    onboard(neon, "owner-a", "taken")
    for bad, status in (("TAKEN", 409), ("admin", 409), ("wearhouse_x", 409), ("1abc", 422), ("ab", 422)):
        r = patch(neon, "other", {"handle": bad})
        assert r.status_code == status, (bad, r.text)
        if status == 409:
            assert r.json()["code"] == "HANDLE_UNAVAILABLE"
    assert query(clean_db, "SELECT count(*) FROM account_profile WHERE handle IS NOT NULL") == [(1,)]


def test_concurrent_claims_one_winner(neon, clean_db):
    for sub in ("racer-1", "racer-2", "racer-3", "racer-4"):
        neon.get("/api/v2/me", sub)
    out = []

    def go(sub):
        out.append(patch(neon, sub, {"handle": "prize"}).status_code)

    ts = [threading.Thread(target=go, args=(s,)) for s in ("racer-1", "racer-2", "racer-3", "racer-4")]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert sorted(out) == [200, 409, 409, 409]
    assert query(clean_db, "SELECT count(*) FROM account_profile WHERE handle = 'prize'") == [(1,)]


def test_change_interval_and_30_day_hold(neon, clean_db, neon_issuer):
    onboard(neon, "changer", "first_name")
    assert patch(neon, "changer", {"handle": "second_name"}).status_code == 200  # first replacement allowed
    too_soon = patch(neon, "changer", {"handle": "third_name"})
    assert too_soon.status_code == 409 and too_soon.json()["code"] == "HANDLE_CHANGE_TOO_SOON"
    assert 6 * 86400 < int(too_soon.headers["Retry-After"]) <= 7 * 86400
    neon.get("/api/v2/me", "squatter")
    held = patch(neon, "squatter", {"handle": "first_name"})
    assert held.status_code == 409 and held.json()["code"] == "HANDLE_UNAVAILABLE"
    later = {"now": utcnow() + timedelta(days=31)}
    future = Api(create_test_app(make_settings(clean_db, neon_issuer), issuer=neon_issuer,
                                 clock=lambda: later["now"]), neon_issuer)
    assert patch(future, "squatter", {"handle": "first_name"}).status_code == 200  # hold expired
    assert patch(future, "changer", {"handle": "third_name"}).status_code == 200  # interval passed


def test_avatar_preset_or_verified_provider_picture_only(neon, clean_db):
    onboard(neon, "pic")
    assert patch(neon, "pic", {"avatar": {"kind": "preset", "preset": "plum"}}).json()["avatar"] == \
        {"kind": "preset", "preset": "plum", "url": None}
    assert patch(neon, "pic", {"avatar": {"kind": "preset", "preset": "neon-green"}}).status_code == 422
    assert patch(neon, "pic", {"avatar": {"kind": "provider"}}).status_code == 422  # token has no image
    goog = "https://lh3.googleusercontent.com/a/picture"
    r = patch(neon, "pic", {"avatar": {"kind": "provider"}}, profile={"image": goog})
    assert r.json()["avatar"] == {"kind": "provider", "preset": None, "url": goog}
    sneaky = patch(neon, "pic", {"avatar": {"kind": "provider", "url": "https://evil.example/x.png"}},
                   profile={"image": goog})
    assert sneaky.status_code == 422  # client-supplied URLs are rejected outright


def test_no_email_anywhere_and_field_rules(neon, clean_db):
    onboard(neon, "privacyfan")
    email = "privacyfan@example.test"
    for path in ("/api/v2/me", "/api/v2/me/profile", "/api/v2/profiles/privacyfan"):
        assert email not in neon.get(path, "privacyfan").text
    assert email not in neon.get("/api/v2/profiles/privacyfan").text
    assert patch(neon, "privacyfan", {"display_name": ""}).status_code == 422
    assert patch(neon, "privacyfan", {"bio": "x" * 161}).status_code == 422
    assert patch(neon, "privacyfan", {}).status_code == 422
    assert patch(neon, "privacyfan", {"email": "x@y.z"}).status_code == 422


# ------------------------------------------------------------------ 4.2 privacy settings
def test_privacy_defaults_and_owner_only(neon, clean_db):
    assert neon.get("/api/v2/me/privacy", "newcomer").json() == \
        {"profile": "public", "wardrobe": "private", "friends_list": "friends"}
    r = neon.client.put("/api/v2/me/privacy", json={"profile": "friends", "wardrobe": "public",
                                                    "friends_list": "private"}, headers=h(neon, "newcomer"))
    assert r.status_code == 200 and r.json()["wardrobe"] == "public"
    assert neon.client.get("/api/v2/me/privacy").status_code == 401
    bad = neon.client.put("/api/v2/me/privacy", json={"profile": "everyone", "wardrobe": "public",
                                                      "friends_list": "private"}, headers=h(neon, "newcomer"))
    assert bad.status_code == 422


# ------------------------------------------------------------------ 4.3 public projections
def set_privacy(api, sub, **kw):
    cur = api.get("/api/v2/me/privacy", sub).json()
    r = api.client.put("/api/v2/me/privacy", json={**cur, **kw}, headers=api.headers(sub))
    assert r.status_code == 200


def own_item(api, sub):
    api.grant("ed", "catalogue_editor")
    api.grant("inv", "inventory_manager")
    pid = api.post("/api/v2/admin/source-products", "ed", json=synthetic_product()).json()["product_id"]
    unit = issue(api, pid, sub="inv")
    assert redeem(api, sub, unit["delivery"]["activation_key"]).status_code == 201
    return unit


def test_profile_projection_by_relation(neon, clean_db):
    onboard(neon, "alice")
    onboard(neon, "bob")
    onboard(neon, "carol")
    befriend(neon, "alice", "bob")
    pub = neon.get("/api/v2/profiles/alice").json()
    assert set(pub) == {"handle", "display_name", "avatar", "profile_visibility", "bio", "member_since", "sections"}
    set_privacy(neon, "alice", profile="private")
    for viewer in (None, "carol", "bob"):
        r = neon.get("/api/v2/profiles/alice", viewer).json()
        assert set(r) == {"handle", "display_name", "avatar", "profile_visibility"}, viewer
        assert r["profile_visibility"] == "private"
    set_privacy(neon, "alice", profile="friends")
    assert "bio" in neon.get("/api/v2/profiles/alice", "bob").json()
    assert "bio" not in neon.get("/api/v2/profiles/alice", "carol").json()
    assert "bio" in neon.get("/api/v2/profiles/alice", "alice").json()


def test_wardrobe_projection_and_immediate_unfriend(neon, clean_db):
    onboard(neon, "owner")
    onboard(neon, "pal")
    onboard(neon, "stranger")
    unit = own_item(neon, "owner")
    set_privacy(neon, "owner", wardrobe="friends")
    befriend(neon, "owner", "pal")
    r = neon.get("/api/v2/profiles/owner/wardrobe", "pal")
    assert r.status_code == 200 and r.headers["cache-control"] == "no-store"
    items = r.json()["items"]
    assert len(items) == 1 and set(items[0]) == {"product"}
    for leak in (unit["public_serial"], unit["unit_id"], "claimed_at", "acquisition", "revision_id"):
        assert leak not in r.text
    assert neon.get("/api/v2/profiles/owner/wardrobe", "stranger").status_code == 404
    assert neon.get("/api/v2/profiles/owner/wardrobe").status_code == 404
    tricks = neon.client.get("/api/v2/profiles/owner/wardrobe?as_friend=true&visibility=public",
                             headers={**h(neon, "stranger"), "X-Relation": "friend"})
    assert tricks.status_code == 404
    assert neon.client.delete("/api/v2/me/friends/pal", headers=h(neon, "owner")).status_code == 204
    assert neon.get("/api/v2/profiles/owner/wardrobe", "pal").status_code == 404


def test_blocks_and_deleted_accounts_look_absent(neon, clean_db):
    onboard(neon, "blocker")
    onboard(neon, "blocked_one")
    set_privacy(neon, "blocker", wardrobe="public", friends_list="public")
    unknown = neon.get("/api/v2/profiles/nobody_here", "blocked_one")
    assert neon.client.put("/api/v2/me/blocks/blocked_one", headers=h(neon, "blocker")).status_code == 204
    for path in ("/api/v2/profiles/blocker", "/api/v2/profiles/blocker/wardrobe", "/api/v2/profiles/blocker/friends"):
        r = neon.get(path, "blocked_one")
        assert r.status_code == 404
        assert {k: v for k, v in r.json().items() if k != "request_id"} == \
            {k: v for k, v in unknown.json().items() if k != "request_id"}
    r = neon.get("/api/v2/profiles/blocked_one", "blocker")
    assert r.status_code == 404  # either direction


def test_friends_list_omits_private_profiles_and_viewer_blocks(neon, clean_db):
    for s in ("hub", "f_public", "f_private", "f_blocker", "viewer"):
        onboard(neon, s)
    for f in ("f_public", "f_private", "f_blocker"):
        befriend(neon, "hub", f)
    set_privacy(neon, "hub", friends_list="public")
    set_privacy(neon, "f_private", profile="private")
    assert neon.client.put("/api/v2/me/blocks/viewer", headers=h(neon, "f_blocker")).status_code == 204
    anon = [f["handle"] for f in neon.get("/api/v2/profiles/hub/friends").json()["friends"]]
    assert sorted(anon) == ["f_blocker", "f_public"]
    seen = [f["handle"] for f in neon.get("/api/v2/profiles/hub/friends", "viewer").json()["friends"]]
    assert seen == ["f_public"]
    own = [f["handle"] for f in neon.get("/api/v2/me/friends", "hub").json()["friends"]]
    assert sorted(own) == ["f_blocker", "f_private", "f_public"]


def test_wardrobe_cursor_is_sealed_and_viewer_bound(neon, clean_db):
    onboard(neon, "collector")
    onboard(neon, "fan")
    neon.grant("ed", "catalogue_editor")
    neon.grant("inv", "inventory_manager")
    pid = neon.post("/api/v2/admin/source-products", "ed", json=synthetic_product()).json()["product_id"]
    for i in range(3):
        assert redeem(neon, "collector", issue(neon, pid, sub="inv")["delivery"]["activation_key"]).status_code == 201
    set_privacy(neon, "collector", wardrobe="public")
    first = neon.get("/api/v2/profiles/collector/wardrobe", "fan", params={"limit": 2}).json()
    cursor = first["next_cursor"]
    item_ids = [r[0] for r in query(clean_db, "SELECT id::text FROM owned_item")]
    assert all(i not in cursor for i in item_ids)
    # sealed: no claim date in the text or in the decoded bytes (a substring like "20" can occur in ciphertext by chance)
    import base64
    raw = cursor.split(".")[0]
    decoded = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
    dates = [r[0] for r in query(clean_db, "SELECT to_char(claimed_at, 'YYYY-MM-DD') FROM owned_item")]
    assert dates and all(d not in cursor and d.encode() not in decoded for d in dates)
    nxt = neon.get("/api/v2/profiles/collector/wardrobe", "fan", params={"cursor": cursor}).json()
    assert len(nxt["items"]) == 1 and nxt["next_cursor"] is None
    assert neon.get("/api/v2/profiles/collector/wardrobe", params={"cursor": cursor}).status_code == 422
    assert neon.get("/api/v2/profiles/collector/wardrobe", "fan", params={"cursor": cursor + "x"}).status_code == 422


# ------------------------------------------------------------------ 4.4 search
def test_search_limits_and_exclusions(neon, clean_db):
    for i in range(25):
        onboard(neon, f"dra_{i:02d}")
    onboard(neon, "searcher")
    onboard(neon, "dra_blocks_you")
    neon.client.put("/api/v2/me/blocks/searcher", headers=h(neon, "dra_blocks_you"))
    r = neon.get("/api/v2/users/search", "searcher", params={"q": "dra"}).json()["results"]
    assert len(r) == 20 and all(set(x) == {"handle", "display_name", "avatar"} for x in r)
    assert "dra_blocks_you" not in [x["handle"] for x in r]
    assert neon.get("/api/v2/users/search", "searcher", params={"q": "dr"}).status_code == 422
    assert neon.get("/api/v2/users/search", "searcher", params={"q": "@dra_07"}).json()["results"][0]["handle"] == "dra_07"
    assert neon.get("/api/v2/users/search", "searcher", params={"q": "dra_%"}).json()["results"] == []  # no wildcards
    assert neon.client.get("/api/v2/users/search", params={"q": "dra"}).status_code == 401
    neon.get("/api/v2/me", "no_handle_yet")
    assert neon.get("/api/v2/users/search", "no_handle_yet", params={"q": "dra"}).json()["code"] == "HANDLE_REQUIRED"


# ------------------------------------------------------------------ 4.5 onboarding gate
def test_social_requires_handle_but_ownership_does_not(neon, clean_db):
    onboard(neon, "target")
    r = neon.post("/api/v2/me/friend-requests", "fresh", json={"handle": "target"}, idem="fresh-req-0001")
    assert r.status_code == 409 and r.json()["code"] == "HANDLE_REQUIRED"
    assert neon.client.put("/api/v2/me/blocks/target", headers=h(neon, "fresh")).json()["code"] == "HANDLE_REQUIRED"
    own_item(neon, "fresh")  # redemption before onboarding works
    assert neon.get("/api/v2/me", "fresh").json()["needs_onboarding"] is True
    assert counts(clean_db, "friend_request") == {"friend_request": 0}
