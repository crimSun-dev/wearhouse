"""add-wearhouse-social-profile-services 2.x-5.1: look shares, week, feed, notifications, showcase.
Read-time visibility (accounts policy + wardrobe privacy ceiling), safe projections, inspiration never grants items.
Products are the data-free synthetic fixture (synthetic_only)."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from conftest import befriend, counts, issue, onboard, query, redeem, synthetic_product
from wearhouse.weather.application import local_today

pytestmark = [pytest.mark.postgres, pytest.mark.synthetic_only]


def put(api, path, sub, json=None):
    return api.client.put(path, headers=api.headers(sub), json=json)


def patch(api, path, sub, json):
    return api.client.patch(path, headers=api.headers(sub), json=json)


def delete(api, path, sub):
    return api.client.delete(path, headers=api.headers(sub))


def privacy(api, sub, **over):
    body = {"profile": "public", "wardrobe": "public", "friends_list": "friends", **over}
    assert put(api, "/api/v2/me/privacy", sub, body).status_code == 200


@pytest.fixture
def soc(api):
    """alice + bob are friends, carol is a stranger. alice has a look with a claimed (verified) top."""
    api.grant("editor-1", "catalogue_editor")
    api.grant("inventory-1", "inventory_manager")
    for u in ("alice", "bob", "carol"):
        onboard(api, u)
    befriend(api, "alice", "bob")
    privacy(api, "alice", wardrobe="friends")  # default wardrobe privacy is private (caps every share)
    pid = api.post("/api/v2/admin/source-products", "editor-1", json=synthetic_product("0700000001")).json()["product_id"]
    rev = api.get(f"/api/v2/admin/catalogue/products/{pid}", "editor-1").json()["revisions"][-1]["id"]
    api.post(f"/api/v2/admin/catalogue/products/{pid}/publish", "editor-1", json={"revision_id": rev})
    unit = issue(api, pid)
    item = redeem(api, "alice", unit["delivery"]["activation_key"]).json()
    put_slot = patch(api, f"/api/v2/me/wardrobe/items/{item['id']}", "alice", {"slot_override": "top"})
    assert put_slot.status_code == 200
    bottom = api.post("/api/v2/me/wardrobe/items", "alice", json={"name": "Thrifted skirt", "slot": "bottom",
                                                                   "colour": "Black"}).json()["id"]
    look = api.post("/api/v2/me/looks", "alice", json={"name": "Brunch", "slots": {"top": [item["id"]],
                                                                                   "bottom": [bottom]}}).json()
    return {"product_id": pid, "serial": unit["public_serial"], "item_id": item["id"], "bottom": bottom,
            "look_id": look["id"], "revision_id": look["current"]["id"]}


def share(api, soc, audience="friends", caption="Sunday brunch"):
    r = api.post("/api/v2/me/shares", "alice", json={"look_id": soc["look_id"], "audience": audience, "caption": caption})
    assert r.status_code == 201, r.text
    return r.json()["id"]


# ============================================================== 2.1 shares
def test_share_projection_is_safe_and_links_published_products(api, soc):
    sid = share(api, soc)
    r = api.get(f"/api/v2/shares/{sid}", "bob")
    assert r.status_code == 200, r.text
    body = r.json()
    items = {i["slot"]: i for i in body["look"]["items"]}
    assert items["top"]["verified"] and items["top"]["product_id"] == soc["product_id"]
    assert items["bottom"]["verified"] is False and items["bottom"]["product_id"] is None
    assert body["owner"]["handle"] == "alice" and "look_id" not in body or body["look_id"] is None
    text = json.dumps(body)
    for secret in (soc["serial"], soc["item_id"], soc["bottom"]):
        assert secret not in text
    assert "care_state" not in text and "wear" not in text
    api.post(f"/api/v2/admin/catalogue/products/{soc['product_id']}/retire", "editor-1")
    again = api.get(f"/api/v2/shares/{sid}", "bob").json()
    assert {i["slot"]: i for i in again["look"]["items"]}["top"]["product_id"] is None  # no link once retired


def test_visibility_reversals(api, soc):
    sid = share(api, soc)
    assert api.get(f"/api/v2/shares/{sid}", "carol").status_code == 404  # stranger, friends-only
    assert api.get(f"/api/v2/shares/{sid}").status_code == 404  # anonymous
    assert delete(api, "/api/v2/me/friends/bob", "alice").status_code == 204
    assert api.get(f"/api/v2/shares/{sid}", "bob").status_code == 404  # unfriend invalidates
    befriend(api, "alice", "bob")
    assert api.get(f"/api/v2/shares/{sid}", "bob").status_code == 200
    assert put(api, "/api/v2/me/blocks/alice", "bob").status_code in (200, 204)  # block by the VIEWER
    assert api.get(f"/api/v2/shares/{sid}", "bob").status_code == 404

    pub = share(api, soc, audience="public")
    privacy(api, "alice", wardrobe="public")
    assert api.get(f"/api/v2/shares/{pub}").status_code == 200
    assert api.get(f"/api/v2/shares/{pub}", "carol").status_code == 200
    assert api.get(f"/api/v2/shares/{pub}", "bob").status_code == 404  # still blocked
    privacy(api, "alice", wardrobe="private")
    assert api.get(f"/api/v2/shares/{pub}").status_code == 404  # privacy ceiling
    assert api.get(f"/api/v2/shares/{pub}", "alice").status_code == 200  # owner always
    privacy(api, "alice", wardrobe="public")
    assert delete(api, f"/api/v2/me/shares/{pub}", "alice").status_code == 204
    assert api.get(f"/api/v2/shares/{pub}").status_code == 404  # revoked
    assert api.get(f"/api/v2/shares/{uuid.uuid4()}").status_code == 404


def test_share_management_repin_and_limits(api, soc, monkeypatch):
    sid = share(api, soc)
    shoes = api.post("/api/v2/me/wardrobe/items", "alice", json={"name": "Clogs", "slot": "footwear"}).json()["id"]
    patch(api, f"/api/v2/me/looks/{soc['look_id']}", "alice",
          {"slots": {"top": [soc["item_id"]], "bottom": [soc["bottom"]], "footwear": [shoes]}})
    assert api.get(f"/api/v2/shares/{sid}", "bob").json()["look"]["revision_no"] == 1  # pinned
    r = patch(api, f"/api/v2/me/shares/{sid}", "alice", {"repin": True, "caption": "Updated", "audience": "public"})
    assert r.status_code == 200 and r.json()["look"]["revision_no"] == 2 and r.json()["caption"] == "Updated"
    assert patch(api, f"/api/v2/me/shares/{sid}", "bob", {"caption": "mine now"}).status_code == 404
    assert api.post("/api/v2/me/shares", "bob", json={"look_id": soc["look_id"], "audience": "public"}).status_code == 422
    privacy(api, "alice", wardrobe="private")
    assert api.get("/api/v2/me/shares", "alice").json()[0]["effective_audience"] == "private"
    privacy(api, "alice", wardrobe="friends")
    mine = api.get("/api/v2/me/shares", "alice").json()
    assert mine[0]["look_id"] == soc["look_id"] and mine[0]["revoked"] is False
    import wearhouse.social.application as app_mod
    monkeypatch.setattr(app_mod, "MAX_ACTIVE_SHARES", 1)
    full = api.post("/api/v2/me/shares", "alice", json={"look_id": soc["look_id"], "audience": "friends"})
    assert full.status_code == 409 and full.json()["code"] == "SHARES_FULL"


def test_profile_shares_and_deleted_owner(api, soc):
    privacy(api, "alice", wardrobe="public")
    friends_only, public = share(api, soc), share(api, soc, audience="public")
    assert [s["id"] for s in api.get("/api/v2/profiles/alice/shares").json()["items"]] == [public]
    assert {s["id"] for s in api.get("/api/v2/profiles/alice/shares", "bob").json()["items"]} == {public, friends_only}
    api.client.request("DELETE", "/api/v2/me", headers=api.headers("alice"), json={"confirm": "alice"})
    assert api.get(f"/api/v2/shares/{public}").status_code == 404


# ============================================================== 2.2 week
def test_week_plan_sharing(api, soc):
    today = local_today(datetime.now(timezone.utc))
    assert put(api, f"/api/v2/me/planner/{today.isoformat()}", "alice",
               {"look_revision_id": soc["revision_id"]}).status_code == 200
    api.post("/api/v2/me/wear", "alice", json={"worn_on": today.isoformat(), "look_revision_id": soc["revision_id"]},
             idem="wear-week-0001")
    assert api.get("/api/v2/profiles/alice/week", "bob").status_code == 404  # default none
    assert put(api, "/api/v2/me/plan-sharing", "alice", {"audience": "friends"}).json() == {"audience": "friends"}
    w = api.get("/api/v2/profiles/alice/week", "bob")
    assert w.status_code == 200, w.text
    days = w.json()["days"]
    assert len(days) == 7 and days[0]["look"]["look_name"] == "Brunch"
    text = w.text
    assert "worn" not in text and "weather" not in text and soc["serial"] not in text
    assert api.get("/api/v2/profiles/alice/week", "carol").status_code == 404
    assert api.get("/api/v2/profiles/alice/week").status_code == 404
    privacy(api, "alice", wardrobe="private")
    assert api.get("/api/v2/profiles/alice/week", "bob").status_code == 404


# ============================================================== 3.1 feed
def test_feed_newest_first_paging_and_block(api, soc):
    ids = [share(api, soc, caption=f"look {i}") for i in range(5)]
    page1 = api.get("/api/v2/me/feed", "bob", params={"limit": 2}).json()
    assert [s["id"] for s in page1["items"]] == ids[::-1][:2] and page1["next_cursor"]
    seen, cursor = [s["id"] for s in page1["items"]], page1["next_cursor"]
    while cursor:
        page = api.get("/api/v2/me/feed", "bob", params={"limit": 2, "cursor": cursor}).json()
        seen += [s["id"] for s in page["items"]]
        cursor = page["next_cursor"]
    assert seen == ids[::-1]
    assert api.get("/api/v2/me/feed", "carol").json()["items"] == []
    assert api.get("/api/v2/me/feed", "bob", params={"cursor": page1["next_cursor"][:-3] + "AAA"}).status_code == 422
    assert api.get("/api/v2/me/feed", "carol", params={"cursor": page1["next_cursor"]}).status_code == 422
    put(api, "/api/v2/me/blocks/alice", "bob")
    assert api.get("/api/v2/me/feed", "bob").json()["items"] == []


# ============================================================== 3.2 notifications
def test_derived_notifications_and_read_marker(api, soc):
    r = api.post("/api/v2/me/friend-requests", "carol", json={"handle": "alice"}, idem="fr-carol-0001")
    assert r.status_code == 201
    kinds = [n["kind"] for n in api.get("/api/v2/me/notifications", "alice").json()["items"]]
    assert "friend_request" in kinds
    api.post(f"/api/v2/me/friend-requests/{r.json()['request_id']}/accept", "alice")
    carol = api.get("/api/v2/me/notifications", "carol").json()["items"]
    assert carol[0]["kind"] == "request_accepted" and carol[0]["account"]["handle"] == "alice" and carol[0]["unread"]
    sid = share(api, soc)
    bob = api.get("/api/v2/me/notifications", "bob").json()["items"]
    assert bob[0]["kind"] == "friend_shared_look" and bob[0]["ref"] == sid
    assert api.get("/api/v2/me/notifications/unread-count", "bob").json()["unread"] >= 1
    assert api.post("/api/v2/me/notifications/read", "bob").json() == {"unread": 0}
    assert api.get("/api/v2/me/notifications/unread-count", "bob").json()["unread"] == 0
    share(api, soc, caption="newer")
    assert api.get("/api/v2/me/notifications/unread-count", "bob").json()["unread"] == 1
    put(api, "/api/v2/me/blocks/alice", "bob")
    assert all(n["kind"] != "friend_shared_look" for n in api.get("/api/v2/me/notifications", "bob").json()["items"])


# ============================================================== 4.1 showcase
def test_showcase_rules_and_visibility(api, soc):
    privacy(api, "alice", wardrobe="public", profile="public")
    friends_only, public = share(api, soc), share(api, soc, audience="public")
    other = api.post("/api/v2/me/looks", "bob", json={"name": "Bob", "slots": {"top": [
        api.post("/api/v2/me/wardrobe/items", "bob", json={"name": "Tee", "slot": "top"}).json()["id"]]}}).json()
    bobs = api.post("/api/v2/me/shares", "bob", json={"look_id": other["id"], "audience": "public"}).json()["id"]
    bad = put(api, "/api/v2/me/showcase", "alice", {"headline": "Hi", "accent": "sage", "featured_share_ids": [bobs]})
    assert bad.status_code == 422 and bad.json()["field_errors"][0]["code"] == "unknown_share"
    assert put(api, "/api/v2/me/showcase", "alice", {"accent": "neon"}).status_code == 422
    ok = put(api, "/api/v2/me/showcase", "alice", {"headline": "Plum enjoyer", "accent": "sage",
                                                     "featured_share_ids": [friends_only, public]})
    assert ok.status_code == 200 and ok.json()["featured"] == [friends_only, public]
    anon = api.get("/api/v2/profiles/alice/showcase").json()
    assert anon["headline"] == "Plum enjoyer" and [s["id"] for s in anon["featured"]] == [public]
    assert [s["id"] for s in api.get("/api/v2/profiles/alice/showcase", "bob").json()["featured"]] == [friends_only, public]
    privacy(api, "alice", profile="private")
    assert api.get("/api/v2/profiles/alice/showcase").status_code == 404
    delete(api, f"/api/v2/me/shares/{public}", "alice")
    revoked = put(api, "/api/v2/me/showcase", "alice", {"featured_share_ids": [public]})
    assert revoked.status_code == 422


# ============================================================== 5.1 integration
def test_inspiration_never_grants_items_and_account_integration(api, soc, clean_db):
    privacy(api, "alice", wardrobe="public")
    sid = share(api, soc, audience="public")
    before = counts(clean_db, "owned_item", "garment_unit", "activation_credential", "wishlist_item", "cart_line")
    for viewer in ("bob", "carol", None):
        for _ in range(3):
            api.get(f"/api/v2/shares/{sid}", viewer)
        api.get("/api/v2/me/feed", viewer) if viewer else None
        api.get("/api/v2/profiles/alice/shares", viewer)
    assert counts(clean_db, "owned_item", "garment_unit", "activation_credential", "wishlist_item", "cart_line") == before
    put(api, "/api/v2/me/showcase", "alice", {"headline": "x", "accent": "plum", "featured_share_ids": [sid]})
    put(api, "/api/v2/me/plan-sharing", "alice", {"audience": "friends"})
    doc = api.get("/api/v2/me/export", "alice").json()["social"]
    assert doc["shares"][0]["id"] == sid and doc["plan_sharing"] == "friends" and doc["showcase"]["featured"] == [sid]
    gone = api.client.request("DELETE", "/api/v2/me", headers=api.headers("alice"), json={"confirm": "alice"})
    assert gone.status_code == 204, gone.text
    for t in ("look_share", "plan_share_setting", "profile_showcase"):
        assert query(clean_db, f"SELECT count(*) FROM {t}") == [(0,)], t


# ============================================================== complete-wearhouse-tdd 2.1 moderation + inspiration
def test_reports_and_moderation(api, soc, clean_db):
    privacy(api, "alice", wardrobe="public")
    sid = share(api, soc, audience="public")
    rep = lambda sub, reason="Not a real outfit": api.post(f"/api/v2/shares/{sid}/report", sub, json={"reason": reason})  # noqa: E731
    assert rep("carol").json() == {"share_id": sid, "reported": True}
    assert rep("carol").status_code == 409  # once per reporter
    assert rep("bob", "Spam").status_code == 200
    assert rep("alice").status_code == 422  # not your own
    assert api.post(f"/api/v2/shares/{sid}/report", json={"reason": "x"}).status_code == 401
    assert api.get("/api/v2/admin/moderation/reports", "carol").status_code == 403
    api.grant("mod", "moderator")
    queue = api.get("/api/v2/admin/moderation/reports", "mod").json()["items"]
    assert len(queue) == 1 and queue[0]["id"] == sid and queue[0]["reports"] == 2
    assert sorted(queue[0]["reasons"]) == ["Not a real outfit", "Spam"]
    me = api.get("/api/v2/me", "mod").json()
    assert me["capabilities"] == sorted({"social:moderate", "ownership:redeem", "ownership:read_own"})  # nothing else
    assert api.get("/api/v2/admin/commerce/orders", "mod").status_code == 403
    assert api.get("/api/v2/admin/units", "mod", params={"product_id": soc["product_id"]}).status_code == 403
    hide = api.post(f"/api/v2/admin/moderation/shares/{sid}", "mod", json={"action": "hide", "reason": "Reported twice"})
    assert hide.json() == {"share_id": sid, "moderation": "hidden"}
    assert api.get(f"/api/v2/shares/{sid}").status_code == 404
    assert api.get(f"/api/v2/shares/{sid}", "bob").status_code == 404
    assert api.get("/api/v2/me/feed", "bob").json()["items"] == []
    assert [s["id"] for s in api.get("/api/v2/profiles/alice/shares").json()["items"]] == []
    owner = api.get(f"/api/v2/shares/{sid}", "alice").json()
    assert owner["moderation"] == "hidden"
    assert api.get("/api/v2/admin/moderation/reports", "mod").json()["items"] == []  # reports actioned
    back = api.post(f"/api/v2/admin/moderation/shares/{sid}", "mod", json={"action": "restore", "reason": "Appeal ok"})
    assert back.json()["moderation"] == "visible" and api.get(f"/api/v2/shares/{sid}").status_code == 200
    audits = query(clean_db, "SELECT action FROM audit_event WHERE action LIKE 'social.share_%' ORDER BY created_at")
    assert [a[0] for a in audits] == ["social.share_hide", "social.share_restore"]
    bad = api.post(f"/api/v2/admin/moderation/shares/{sid}", "mod", json={"action": "delete", "reason": "x"})
    assert bad.status_code == 422


def test_inspiration_snapshots(api, soc, clean_db):
    sid = share(api, soc)  # friends-only
    assert api.post("/api/v2/me/inspirations", "carol", json={"share_id": sid}).status_code == 404  # cannot see it
    saved = api.post("/api/v2/me/inspirations", "bob", json={"share_id": sid})
    assert saved.status_code == 201, saved.text
    body = saved.json()
    assert body["from"]["handle"] == "alice" and body["look"]["look_name"] == "Brunch"
    text = saved.text
    assert soc["serial"] not in text and soc["item_id"] not in text  # safe projection only
    assert delete(api, f"/api/v2/me/shares/{sid}", "alice").status_code == 204  # the friend revokes the share
    mine = api.get("/api/v2/me/inspirations", "bob").json()["items"]
    assert len(mine) == 1 and mine[0]["look"]["look_name"] == "Brunch"  # the snapshot survives
    assert api.get("/api/v2/me/items", "bob").json()["items"] == []  # inspiration never grants items
    assert api.get("/api/v2/me/inspirations", "carol").json()["items"] == []
    assert delete(api, f"/api/v2/me/inspirations/{mine[0]['id']}", "carol").status_code == 404
    assert "inspirations" in api.get("/api/v2/me/export", "bob").json()["social"]
    assert delete(api, f"/api/v2/me/inspirations/{mine[0]['id']}", "bob").status_code == 204
