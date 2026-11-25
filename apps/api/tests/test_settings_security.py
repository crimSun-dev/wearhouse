"""add-wearhouse-settings-security: synced settings (registry, versions, behaviour), security overview, About."""
from __future__ import annotations

import pytest

from conftest import befriend, onboard, query
from wearhouse.recommendations.application import OutfitSuggester, WeatherContext
from wearhouse.recommendations.ports import ItemFeatures

pytestmark = [pytest.mark.postgres]


def patch(api, sub, version, **values):
    return api.client.patch("/api/v2/me/settings", headers=api.headers(sub), json={"version": version, "values": values})


def settings(api, sub):
    r = api.get("/api/v2/me/settings", sub)
    assert r.status_code == 200, r.text
    return r.json()


# ============================================================== 1.1 registry, versions, audit
def test_defaults_schema_and_versioned_saves(api, clean_db):
    s = settings(api, "ana")
    assert s["version"] == 0 and s["updated_at"] is None
    assert s["values"]["theme"] == "system" and s["values"]["recommendation_style"] == "balanced"
    assert s["values"]["sound_volume"] == 60 and s["values"]["friend_requests_from"] == "everyone"
    keys = {x["key"]: x for x in s["schema"]}
    assert keys["wardrobe_view"]["choices"] == ["grid", "list", "outfit"] and keys["sound_volume"]["max"] == 100
    assert s["sections"][0] == "general" and {x["section"] for x in s["schema"]} <= set(s["sections"])
    one = patch(api, "ana", 0, theme="dark", wardrobe_view="list")
    assert one.status_code == 200, one.text
    assert one.json()["version"] == 1 and one.json()["values"]["theme"] == "dark"
    stale = patch(api, "ana", 0, theme="light")  # another device still holding version 0
    assert stale.status_code == 409 and stale.json()["code"] == "SETTINGS_CHANGED"
    assert settings(api, "ana")["values"]["theme"] == "dark"
    two = patch(api, "ana", 1, sound_volume=10)
    assert two.json()["version"] == 2 and two.json()["values"]["wardrobe_view"] == "list"  # earlier keys kept
    for bad in ({"colour_scheme": "pink"}, {"theme": "neon"}, {"sound_volume": 101}, {"sound_volume": True},
                {"beta_features": "yes"}):
        r = patch(api, "ana", 2, **bad)
        assert r.status_code == 422, bad
    assert patch(api, "ana", 2).status_code == 422  # nothing to change
    assert settings(api, "bob")["values"]["theme"] == "system"  # per account
    audits = query(clean_db, "SELECT details->'keys' FROM audit_event WHERE action = 'account.settings_changed' "
                             "ORDER BY created_at")
    assert [a[0] for a in audits] == [["theme", "wardrobe_view"], ["sound_volume"]]  # keys only, never values


# ============================================================== 1.1 behaviour
def test_requests_closed_and_discoverability(api):
    for u in ("ana", "bob", "cyd"):
        onboard(api, u)
    patch(api, "bob", 0, friend_requests_from="nobody", discoverable=False)
    r = api.post("/api/v2/me/friend-requests", "ana", json={"handle": "bob"}, idem="fr-closed-0001")
    assert r.status_code == 409 and r.json()["code"] == "REQUESTS_CLOSED"
    # bob can still send, and ana's acceptance of bob's request still works
    out = api.post("/api/v2/me/friend-requests", "bob", json={"handle": "ana"}, idem="fr-closed-0002")
    assert out.status_code == 201
    assert api.post(f"/api/v2/me/friend-requests/{out.json()['request_id']}/accept", "ana").status_code == 200
    prefix = [a["handle"] for a in api.get("/api/v2/users/search", "cyd", params={"q": "bob"}).json()["results"]]
    assert prefix == []  # hidden from prefix search
    exact = [a["handle"] for a in api.get("/api/v2/users/search", "cyd", params={"q": "@bob"}).json()["results"]]
    assert exact == ["bob"]  # an exact @handle still works (so a handle can be shared)


def test_notification_toggles(api):
    for u in ("ana", "bob"):
        onboard(api, u)
    api.post("/api/v2/me/friend-requests", "ana", json={"handle": "bob"}, idem="fr-note-0001")
    kinds = lambda: [n["kind"] for n in api.get("/api/v2/me/notifications", "bob").json()["items"]]  # noqa: E731
    assert kinds() == ["friend_request"]
    patch(api, "bob", 0, notify_friend_requests=False)
    assert kinds() == [] and api.get("/api/v2/me/notifications/unread-count", "bob").json()["unread"] == 0


def test_suggestion_settings(api):
    mk = lambda name, slot: api.post("/api/v2/me/wardrobe/items", "ana", json={"name": name, "slot": slot})  # noqa: E731
    for name, slot in (("Tee", "top"), ("Jeans", "bottom"), ("Sneakers", "footwear")):
        assert mk(name, slot).status_code == 201
    on = api.get("/api/v2/me/recommendations/outfits", "ana").json()
    assert on["enabled"] is True and on["style"] == "balanced" and on["weights"]["recency"] == 0.2
    patch(api, "ana", 0, weather_in_suggestions=False, recommendation_style="adventurous")
    r = api.get("/api/v2/me/recommendations/outfits", "ana", params={"rain": "true"}).json()
    assert r["weather"]["source"] == "DISABLED" and r["style"] == "adventurous" and r["weights"]["recency"] == 0.4
    patch(api, "ana", 1, style_suggestions=False)
    off = api.get("/api/v2/me/recommendations/outfits", "ana").json()
    assert off["enabled"] is False and off["suggestions"] == [] and off["reasons"] == ["turned_off_in_settings"]


def test_weight_profiles_change_ranking_margin():
    """Eq. 7 profiles: a recently worn top is penalised most by adventurous, least by classic."""
    from wearhouse.accounts.domain import RECOMMENDATION_WEIGHTS
    from wearhouse.recommendations.application import ItemStats
    items = [ItemFeatures("t1", "top", "#1F1F1F"), ItemFeatures("t2", "top", "#1F1F1F"),
             ItemFeatures("b", "bottom", "#F2F2F2"), ItemFeatures("s", "footwear", "#1F1F1F")]
    attrs = {i.item_id: {"warmth": "light", "rain_suitable": False, "long_sleeve": False, "long_bottom": True,
                         "formal": False} for i in items}
    w = WeatherContext(None, None, "NONE")

    def margin(style):
        out = OutfitSuggester().suggest(items, attrs=attrs, stats={"t1": ItemStats(days_since_worn=1)}, weather=w,
                                        occasion="casual", limit=2, weights=RECOMMENDATION_WEIGHTS[style], style=style)
        first, second = out["suggestions"]
        assert "t2" in first["item_ids"]  # the unworn top wins under every profile
        return first["score"] - second["score"]

    assert margin("adventurous") > margin("balanced") > margin("classic") > 0


def test_export_and_erasure(api, clean_db):
    handle = onboard(api, "ana")
    patch(api, "ana", 0, theme="light")
    doc = api.get("/api/v2/me/export", "ana").json()
    assert doc["settings"]["version"] == 1 and doc["settings"]["values"]["theme"] == "light"
    gone = api.client.request("DELETE", "/api/v2/me", headers=api.headers("ana"), json={"confirm": handle})
    assert gone.status_code == 204
    assert query(clean_db, "SELECT count(*) FROM account_setting") == [(0,)]


# ============================================================== 2.1 security overview + About
def test_security_overview_events_are_own_only(api):
    onboard(api, "ana", "ana")
    onboard(api, "bob")
    api.client.put("/api/v2/me/privacy", headers=api.headers("ana"),
                   json={"profile": "public", "wardrobe": "friends", "friends_list": "friends"})
    patch(api, "ana", 0, discoverable=False)
    api.get("/api/v2/me/export", "ana")
    api.post("/api/v2/me/sessions/revoke-all", "ana")
    import time
    later = {"Authorization": "Bearer " + api.issuer.token("ana", now=time.time() + 2)}  # signed in again after it
    r = api.client.get("/api/v2/me/security", headers=later)
    assert r.status_code == 200, r.text
    sec = r.json()
    assert sec["account_created_at"] and sec["sessions_revoked_at"]
    assert sec["current_session"]["recent_enough_for_sensitive_actions"] is True
    assert "never receives your password" in sec["password_managed_by"]
    actions = [e["action"] for e in sec["events"]]
    assert actions == ["account.sessions_revoked", "account.exported", "account.settings_changed",
                       "account.privacy_changed"]  # newest first
    assert sec["events"][2]["details"] == {"keys": ["discoverable"]} and all(e["by_you"] for e in sec["events"])
    assert api.get("/api/v2/me/security", "bob").json()["events"] == []  # never someone else's
    api.grant("boss", "admin")
    onboard(api, "boss")
    api.client.put("/api/v2/admin/staff/bob/roles/catalogue_editor", headers=api.headers("boss"))
    bob = api.get("/api/v2/me/security", "bob").json()["events"]
    assert [(e["action"], e["by_you"], e["details"].get("role")) for e in bob] == [
        ("identity.role_granted", False, "catalogue_editor")]


def test_about_lists_sources_and_disclosure(api):
    r = api.get("/api/v2/about")
    assert r.status_code == 200
    body = r.json()
    names = {s["name"] for s in body["sources"]}
    assert any("Polyvore" in n for n in names) and any("H&M" in n for n in names) and any("BMKG" in n for n in names)
    poly = next(s for s in body["sources"] if "Polyvore" in s["name"])
    assert "CC BY 4.0" in poly["licence"] and "ECCV" in poly["citation"]
    assert body["schema_head"] and "AI assistance" in body["ai_disclosure"]
