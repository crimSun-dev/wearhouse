"""build-wearhouse-wardrobe-planning-services 2.x-6.x: wardrobe items, shelves, looks, weather, planner, wear and
suggestions. Products are the data-free synthetic fixture; weather uses a FAKE fetcher (no test calls BMKG)."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import ProgrammingError

from conftest import RUNTIME_PW, RUNTIME_ROLE, issue, query, redeem, role_url, synthetic_product
from wearhouse.weather.application import LOCAL, local_today
from wearhouse.weather.contract import CachedFeed, WeatherSlot
from wearhouse.weather.ports import FetchError

pytestmark = [pytest.mark.postgres, pytest.mark.synthetic_only]
ADM4 = "31.71.03.1001"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


def today():
    return local_today(datetime.now(timezone.utc))


class FakeFetcher:
    def __init__(self, mode="ok", rain_days=(0,)):
        self.mode, self.rain_days, self.calls = mode, rain_days, 0

    def fetch(self, adm4):
        self.calls += 1
        if self.mode == "timeout":
            raise FetchError("timeout")
        base = datetime.now(LOCAL).replace(minute=0, second=0, microsecond=0)
        day = []
        for h in range(0, 48, 3):
            at = base + timedelta(hours=h)
            rainy = (at.date() - base.date()).days in self.rain_days
            day.append({"local_datetime": at.strftime("%Y-%m-%d %H:%M:%S"), "t": 33 if self.mode == "hot" else 27,
                        "hu": 140 if self.mode == "malformed" else 80,
                        "weather_desc": "Hujan Ringan" if rainy else "Cerah Berawan"})
        return {"lokasi": {"adm4": adm4, "timezone": "Asia/Jakarta"}, "data": [{"cuaca": [day]}]}


def put(api, path, sub, json=None):
    return api.client.put(path, headers=api.headers(sub), json=json)


def patch(api, path, sub, json):
    return api.client.patch(path, headers=api.headers(sub), json=json)


def delete(api, path, sub):
    return api.client.delete(path, headers=api.headers(sub))


def owned_product(api, ext, name, slot, colour, sub="owner"):
    body = synthetic_product(ext, product_name=name, colour=colour)
    if slot:
        body["annotations"] = {"slot": {"value": slot, "origin": "rule", "note": "hm-articles@1"}}
    pid = api.post("/api/v2/admin/source-products", "editor-1", json=body).json()["product_id"]
    key = issue(api, pid)["delivery"]["activation_key"]
    item = redeem(api, sub, key)
    assert item.status_code == 201, item.text
    return item.json()["id"]


@pytest.fixture
def ward(api):
    api.grant("editor-1", "catalogue_editor")
    api.grant("inventory-1", "inventory_manager")
    api.services.weather.fetcher = FakeFetcher()
    ids = {"top": owned_product(api, "0600000001", "Black tee", "top", "Black"),
           "bottom": owned_product(api, "0600000002", "Beige chinos", "bottom", "Beige"),
           "shoes": owned_product(api, "0600000003", "White sneakers", "footwear", "White"),
           "outer": owned_product(api, "0600000004", "Grey coat", "outer", "Grey"),
           "dress": owned_product(api, "0600000005", "Navy dress", "dress", "Dark Blue"),
           "noslot": owned_product(api, "0600000006", "Mystery scarf", None, "Red")}
    return ids


def items(api, sub="owner", **params):
    r = api.get("/api/v2/me/wardrobe/items", sub, params=params)
    assert r.status_code == 200, r.text
    return {i["id"]: i for i in r.json()["items"]}


def look(api, name, slots, sub="owner"):
    return api.post("/api/v2/me/looks", sub, json={"name": name, "slots": slots})


# ============================================================== 2.1 items
def test_claimed_items_are_verified_with_catalogue_slot(api, ward):
    inv = items(api)
    top = inv[ward["top"]]
    assert top["kind"] == "verified" and top["verified"] and top["slot"] == "top"
    assert top["slot_source"] == "catalogue" and top["care_state"] == "ready" and top["public_serial"]
    assert inv[ward["noslot"]]["slot"] == "unknown" and inv[ward["noslot"]]["slot_source"] == "unknown"
    r = patch(api, f"/api/v2/me/wardrobe/items/{ward['noslot']}", "owner", {"slot_override": "accessory",
                                                                           "care_state": "laundry"})
    assert r.status_code == 200 and r.json()["slot"] == "accessory" and r.json()["slot_source"] == "override"
    assert set(items(api, care_state="laundry")) == {ward["noslot"]}
    assert set(items(api, slot="footwear")) == {ward["shoes"]}
    cleared = patch(api, f"/api/v2/me/wardrobe/items/{ward['noslot']}", "owner", {"slot_override": None})
    assert cleared.json()["slot"] == "unknown"
    assert api.get(f"/api/v2/me/wardrobe/items/{ward['top']}", "intruder").status_code == 404
    assert patch(api, f"/api/v2/me/wardrobe/items/{ward['top']}", "intruder", {"care_state": "repair"}).status_code == 404
    assert items(api, "intruder") == {}
    bad = patch(api, f"/api/v2/me/wardrobe/items/{ward['top']}", "owner", {"archived": True})
    assert bad.status_code == 422  # verified items cannot be archived


def test_declared_items_keep_unknowns_and_private_photos(api, ward):
    r = api.post("/api/v2/me/wardrobe/items", "owner", json={"name": "Thrifted denim jacket", "slot": "outer"})
    assert r.status_code == 201, r.text
    it = r.json()
    assert it["kind"] == "declared" and it["verified"] is False and it["public_serial"] is None
    assert it["colour"] is None and it["colour_known"] is False and it["slot_source"] == "declared"
    iid = it["id"]
    fake = api.client.put(f"/api/v2/me/wardrobe/items/{iid}/photo", headers={**api.headers("owner"),
                                                                             "Content-Type": "image/jpeg"},
                          content=b"just some text pretending to be a jpg")
    assert fake.status_code == 422 and fake.json()["field_errors"][0]["code"] == "not_an_image"
    big = api.client.put(f"/api/v2/me/wardrobe/items/{iid}/photo", headers=api.headers("owner"),
                         content=PNG + b"\x00" * (2 * 1024 * 1024))
    assert big.status_code == 422
    ok = api.client.put(f"/api/v2/me/wardrobe/items/{iid}/photo", headers=api.headers("owner"), content=PNG)
    assert ok.status_code == 200 and ok.json()["has_photo"] is True
    got = api.get(f"/api/v2/me/wardrobe/items/{iid}/photo", "owner")
    assert got.status_code == 200 and got.content == PNG and got.headers["content-type"] == "image/png"
    assert api.get(f"/api/v2/me/wardrobe/items/{iid}/photo", "intruder").status_code == 404
    assert api.client.put(f"/api/v2/me/wardrobe/items/{ward['top']}/photo", headers=api.headers("owner"),
                          content=PNG).status_code == 422  # verified items use catalogue media
    assert api.post("/api/v2/me/wardrobe/items", "owner", json={"name": "X", "slot": "hat"}).status_code == 422
    arch = patch(api, f"/api/v2/me/wardrobe/items/{iid}", "owner", {"archived": True})
    assert arch.json()["archived"] is True and iid not in items(api)


# ============================================================== 2.2 shelves
def test_shelves_order_foreign_items_and_names(api, ward):
    r = api.post("/api/v2/me/wardrobe/shelves", "owner", json={"name": "Work", "item_ids": [ward["shoes"], ward["top"]]})
    assert r.status_code == 201, r.text
    sid = r.json()["id"]
    assert list(items(api, shelf_id=sid)) == [ward["shoes"], ward["top"]]
    foreign = api.post("/api/v2/me/wardrobe/items", "intruder", json={"name": "Not yours", "slot": "top"}).json()["id"]
    bad = patch(api, f"/api/v2/me/wardrobe/shelves/{sid}", "owner", {"item_ids": [foreign]})
    assert bad.status_code == 422 and bad.json()["field_errors"][0]["code"] == "unknown_item"
    assert api.get("/api/v2/me/wardrobe/shelves", "owner").json()[0]["count"] == 2
    dup = api.post("/api/v2/me/wardrobe/shelves", "owner", json={"name": "Work"})
    assert dup.status_code == 409 and dup.json()["code"] == "SHELF_NAME_TAKEN"
    renamed = patch(api, f"/api/v2/me/wardrobe/shelves/{sid}", "owner", {"name": "Office", "item_ids": [ward["top"]]})
    assert renamed.json()["name"] == "Office" and renamed.json()["item_ids"] == [ward["top"]]
    assert patch(api, f"/api/v2/me/wardrobe/shelves/{sid}", "intruder", {"name": "Mine"}).status_code == 404
    assert delete(api, f"/api/v2/me/wardrobe/shelves/{sid}", "owner").status_code == 204
    assert api.get("/api/v2/me/wardrobe/shelves", "owner").json() == []


# ============================================================== 3.1 looks
def test_look_rules_history_and_immutability(api, ward, clean_db):
    assert api.get("/api/v2/wardrobe/slots").json()["exclusions"] == [["dress", "top"], ["dress", "bottom"]]
    conflict = look(api, "Bad", {"dress": [ward["dress"]], "top": [ward["top"]]})
    assert conflict.status_code == 422 and "slot_conflict" in {e["code"] for e in conflict.json()["field_errors"]}
    unknown = look(api, "Bad", {"accessory": [ward["noslot"]]})
    assert {e["code"] for e in unknown.json()["field_errors"]} == {"slot_unknown"}
    mismatch = look(api, "Bad", {"top": [ward["shoes"]]})
    assert {e["code"] for e in mismatch.json()["field_errors"]} == {"slot_mismatch"}
    accs = [api.post("/api/v2/me/wardrobe/items", "owner", json={"name": f"Ring {i}", "slot": "accessory"}).json()["id"]
            for i in range(4)]
    assert {e["code"] for e in look(api, "Bad", {"accessory": accs}).json()["field_errors"]} == {"over_capacity"}
    foreign = api.post("/api/v2/me/wardrobe/items", "intruder", json={"name": "Theirs", "slot": "top"}).json()["id"]
    assert {e["code"] for e in look(api, "Bad", {"top": [foreign]}).json()["field_errors"]} == {"unknown_item"}

    r = look(api, "Weekend", {"top": [ward["top"]], "bottom": [ward["bottom"]], "footwear": [ward["shoes"]]})
    assert r.status_code == 201, r.text
    lk = r.json()
    rev1 = lk["current"]["id"]
    plan_day = today() + timedelta(days=2)
    assert put(api, f"/api/v2/me/planner/{plan_day.isoformat()}", "owner", {"look_revision_id": rev1}).status_code == 200
    shoe2 = api.post("/api/v2/me/wardrobe/items", "owner", json={"name": "Loafers", "slot": "footwear"}).json()["id"]
    edited = patch(api, f"/api/v2/me/looks/{lk['id']}", "owner",
                   {"slots": {"top": [ward["top"]], "bottom": [ward["bottom"]], "footwear": [shoe2]}})
    assert edited.status_code == 200 and edited.json()["current_revision_no"] == 2
    day = api.get("/api/v2/me/planner", "owner", params={"from": plan_day.isoformat()}).json()["days"][0]
    assert day["plan"]["look_revision"]["id"] == rev1 and day["plan"]["look_revision"]["revision_no"] == 1
    hist = api.get(f"/api/v2/me/looks/{lk['id']}", "owner").json()["revisions"]
    assert [h["revision_no"] for h in hist] == [1, 2]
    assert api.get(f"/api/v2/me/look-revisions/{rev1}", "intruder").status_code == 404
    assert delete(api, f"/api/v2/me/looks/{lk['id']}", "owner").status_code == 204
    assert api.get("/api/v2/me/looks", "owner").json() == []
    assert api.get(f"/api/v2/me/look-revisions/{rev1}", "owner").status_code == 200  # history survives delete
    eng = create_engine(role_url(clean_db.name, RUNTIME_ROLE, RUNTIME_PW))
    try:
        with pytest.raises(ProgrammingError, match="permission denied"):
            with eng.begin() as c:
                c.execute(text("UPDATE look_revision SET name = 'tampered'"))
    finally:
        eng.dispose()


# ============================================================== 4.1 weather
def _cache(api, hours_old):
    now = datetime.now(timezone.utc)
    slot = WeatherSlot(at=now, temp_c=26.0, humidity=70, description="Berawan", rain=False, hot=False)
    with api.services.uow_factory() as uow:
        uow.weather.put_cache(ADM4, CachedFeed((slot,), now - timedelta(hours=hours_old),
                                               now - timedelta(hours=hours_old) + timedelta(hours=3)))
        uow.commit()


def test_weather_gateway_live_cache_and_fallbacks(api):
    fake = FakeFetcher()
    api.services.weather.fetcher = fake
    first = api.get("/api/v2/weather/forecast", "u1", params={"adm4": ADM4}).json()
    assert first["source"] == "LIVE" and first["slots"] and fake.calls == 1
    second = api.get("/api/v2/weather/forecast", "u1", params={"adm4": ADM4}).json()
    assert second["source"] == "CACHED" and second["note"] == "cache hit" and fake.calls == 1
    api.services.weather.fetcher = FakeFetcher("timeout")
    _cache(api, 4)
    stale = api.get("/api/v2/weather/forecast", "u1", params={"adm4": ADM4}).json()
    assert stale["source"] == "CACHED" and "timeout" in stale["note"] and stale["fetched_at"]
    _cache(api, 7)
    manual = api.get("/api/v2/weather/forecast", "u1", params={"adm4": ADM4}).json()
    assert manual["source"] == "MANUAL_REQUIRED" and manual["slots"] == []
    api.services.weather.fetcher = FakeFetcher("malformed")
    _cache(api, 7)
    bad = api.get("/api/v2/weather/forecast", "u1", params={"adm4": ADM4}).json()
    assert bad["source"] == "MANUAL_REQUIRED" and "malformed" in bad["note"]
    assert api.get("/api/v2/weather/forecast", "u1", params={"adm4": "jakarta"}).status_code == 422
    assert api.get("/api/v2/weather/forecast", params={"adm4": ADM4}).status_code == 401
    none = api.get("/api/v2/me/weather", "u1").json()
    assert none["source"] == "MANUAL_REQUIRED" and none["note"] == "no_location"
    assert put(api, "/api/v2/me/weather/location", "u1", {"adm4": "nope"}).status_code == 422
    api.services.weather.fetcher = FakeFetcher()
    assert put(api, "/api/v2/me/weather/location", "u1", {"adm4": ADM4}).status_code == 200
    assert api.get("/api/v2/me/weather", "u1").json()["adm4"] == ADM4


# ============================================================== 5.1 planner
def test_planner_window_and_forecast_labels(api, ward):
    rev = look(api, "Daily", {"top": [ward["top"]], "bottom": [ward["bottom"]],
                              "footwear": [ward["shoes"]]}).json()["current"]["id"]
    t = today()
    for bad in (t - timedelta(days=1), t + timedelta(days=31)):
        assert put(api, f"/api/v2/me/planner/{bad.isoformat()}", "owner", {"look_revision_id": rev}).status_code == 422
    assert put(api, f"/api/v2/me/planner/{t.isoformat()}", "intruder", {"look_revision_id": rev}).status_code == 422
    ok = put(api, f"/api/v2/me/planner/{t.isoformat()}", "owner", {"look_revision_id": rev, "occasion": "work",
                                                                    "note": "Meeting"})
    assert ok.status_code == 200 and ok.json()["plan"]["occasion"] == "work"
    view = api.get("/api/v2/me/planner", "owner").json()
    assert len(view["days"]) == 7 and view["days"][0]["is_today"]
    assert all(d["weather"]["status"] == "unavailable" and d["weather"]["reason"] == "no_location"
               for d in view["days"][:4])
    beyond = [d for d in view["days"] if d["weather"]["status"] == "beyond_forecast"]
    assert beyond and all(d["weather"].get("max_temp_c") is None for d in beyond)
    put(api, "/api/v2/me/weather/location", "owner", {"adm4": ADM4})
    view = api.get("/api/v2/me/planner", "owner").json()
    today_w = view["days"][0]["weather"]
    assert today_w["status"] == "forecast" and today_w["rain"] is True and today_w["source"] == "LIVE"
    assert view["days"][0]["worn"] == []  # planned is not worn
    assert delete(api, f"/api/v2/me/planner/{t.isoformat()}", "owner").status_code == 204
    assert api.get("/api/v2/me/planner", "owner").json()["days"][0]["plan"] is None


# ============================================================== 5.2 wear
def test_wear_log_idempotent_and_counted(api, ward):
    rev = look(api, "Daily", {"top": [ward["top"]], "bottom": [ward["bottom"]],
                              "footwear": [ward["shoes"]]}).json()["current"]["id"]
    body = {"worn_on": today().isoformat(), "look_revision_id": rev}
    a = api.post("/api/v2/me/wear", "owner", json=body, idem="wear-key-0001")
    b = api.post("/api/v2/me/wear", "owner", json=body, idem="wear-key-0001")
    assert a.status_code == 201 and b.status_code == 201 and a.json()["id"] == b.json()["id"]
    assert b.headers.get("Idempotent-Replayed") == "true"
    assert items(api)[ward["top"]]["wear_count"] == 1 and items(api)[ward["top"]]["last_worn_on"] == today().isoformat()
    future = api.post("/api/v2/me/wear", "owner", json={"worn_on": (today() + timedelta(days=1)).isoformat(),
                                                         "item_ids": [ward["top"]]}, idem="wear-key-0002")
    assert future.status_code == 422
    foreign = api.post("/api/v2/me/wear", "intruder", json={"worn_on": today().isoformat(), "item_ids": [ward["top"]]},
                       idem="wear-key-0003")
    assert foreign.status_code == 422
    neither = api.post("/api/v2/me/wear", "owner", json={"worn_on": today().isoformat()}, idem="wear-key-0004")
    assert neither.status_code == 422
    log = api.get("/api/v2/me/wear", "owner").json()["entries"]
    assert len(log) == 1 and sorted(log[0]["item_ids"]) == sorted([ward["top"], ward["bottom"], ward["shoes"]])
    assert api.get("/api/v2/me/planner", "owner").json()["days"][0]["worn"][0]["id"] == log[0]["id"]
    assert delete(api, f"/api/v2/me/wear/{log[0]['id']}", "intruder").status_code == 404
    assert delete(api, f"/api/v2/me/wear/{log[0]['id']}", "owner").status_code == 204
    assert items(api)[ward["top"]]["wear_count"] == 0


# ============================================================== 6.1 suggestions
def _suggest(api, sub="owner", **params):
    r = api.get("/api/v2/me/recommendations/outfits", sub, params={"limit": 5, **params})
    assert r.status_code == 200, r.text
    return r.json()


def core(s, ward):
    return tuple(sorted(i for i in s["item_ids"] if i in (ward["top"], ward["bottom"], ward["dress"])))


def test_suggestions_follow_thesis_rules(api, ward):
    """align-wearhouse-outfit-recommender: thesis hard rules a-d, distinct cores, explanations, declared mode."""
    out = _suggest(api)
    assert out["model"]["mode"] == "heuristic_baseline" and out["model"]["trained_artifact"] is None
    assert out["weather"]["source"] == "NONE" and out["occasion"] == "casual" and out["ruleset"] == "wardrobe-rules@1"
    assert out["run_id"] and out["params"] == {"p0": 0.5, "a": 5.0, "h": 4.0, "top_m": 8}
    cores = [core(s, ward) for s in out["suggestions"]]
    assert len(cores) == len(set(cores))  # distinct cores
    assert (ward["dress"],) in cores and not any(ward["dress"] in c and ward["top"] in c for c in cores)
    assert "Weather unknown: rain and heat rules not applied." in out["suggestions"][0]["explanation"]

    # rain: sneakers and a (non-rain) coat cannot satisfy rule c, so nothing is suggested, with the reason
    rain = _suggest(api, rain="true")
    assert rain["suggestions"] == [] and rain["removed_by_rule"]["rain"] > 0
    assert "rain: needs rain-suitable footwear or outerwear" in rain["reasons"][-1]
    shoes = items(api)[ward["shoes"]]
    assert shoes["attributes"]["rain_suitable"] == {"value": False, "origin": "rule"}
    fixed = patch(api, f"/api/v2/me/wardrobe/items/{ward['shoes']}", "owner", {"attributes": {"rain_suitable": True}})
    assert fixed.json()["attributes"]["rain_suitable"] == {"value": True, "origin": "owner"}
    assert _suggest(api, rain="true")["suggestions"]  # the owner's correction makes them eligible
    reset = patch(api, f"/api/v2/me/wardrobe/items/{ward['shoes']}", "owner", {"attributes": {"rain_suitable": None}})
    assert reset.status_code == 200, reset.text
    assert reset.json()["attributes"]["rain_suitable"]["origin"] == "rule"
    bad = patch(api, f"/api/v2/me/wardrobe/items/{ward['shoes']}", "owner", {"attributes": {"warmth": "toasty"}})
    assert bad.status_code == 422

    # heat: the coat is heavy (appendix lookup), so no suggestion contains it on a hot day
    hot = _suggest(api, hot="true")
    assert hot["removed_by_rule"]["heat"] > 0 and not any(ward["outer"] in s["item_ids"] for s in hot["suggestions"])
    assert items(api)[ward["outer"]]["attributes"]["warmth"] == {"value": "heavy", "origin": "rule"}

    # worship: long sleeves (the coat) and a long bottom (the chinos) are required
    worship = _suggest(api, occasion="worship")
    inv = items(api)
    attr = lambda i, k: inv[i]["attributes"][k]["value"]  # noqa: E731
    assert worship["suggestions"]
    for sug in worship["suggestions"]:  # every suggestion satisfies rule d from the items' own attributes
        ids = sug["item_ids"]
        assert any(attr(i, "long_sleeve") for i in ids if inv[i]["slot"] in ("top", "dress", "outer"))
        assert any(attr(i, "long_bottom") for i in ids if inv[i]["slot"] in ("bottom", "dress"))
    assert worship["removed_by_rule"]["worship_dress_code"] > 0
    assert api.get("/api/v2/me/recommendations/outfits", "owner", params={"occasion": "party"}).status_code == 422

    # recency (Eq. 9): wearing the chinos yesterday raises the recency of every outfit containing them
    api.post("/api/v2/me/wear", "owner", json={"worn_on": (today() - timedelta(days=1)).isoformat(),
                                                "item_ids": [ward["bottom"]]}, idem="wear-rot-0001")
    after = {core(s, ward): s for s in _suggest(api)["suggestions"]}
    assert after[(ward["dress"],)]["components"]["recency"] == 0.0
    with_chinos = [s for c, s in after.items() if ward["bottom"] in c]
    assert with_chinos and all(s["components"]["recency"] > 0 for s in with_chinos)

    patch(api, f"/api/v2/me/wardrobe/items/{ward['shoes']}", "owner", {"care_state": "laundry"})
    none = _suggest(api)
    assert none["suggestions"] == [] and "missing_slot: footwear" in none["reasons"]

    api.post("/api/v2/me/wardrobe/items", "u2", json={"name": "Odd tee", "slot": "top", "colour": "Mauve-ish"})
    api.post("/api/v2/me/wardrobe/items", "u2", json={"name": "Odd jeans", "slot": "bottom"})
    api.post("/api/v2/me/wardrobe/items", "u2", json={"name": "Odd shoes", "slot": "footwear"})
    s = _suggest(api, "u2")["suggestions"][0]
    assert s["components"]["compatibility"] is None and s["score"] is not None
    assert any("Colour compatibility unknown" in e for e in s["explanation"])


def test_feedback_events_are_deduplicated_and_feed_preference(api, ward, clean_db):
    out = _suggest(api)
    run = out["run_id"]
    shown = {i for s in out["suggestions"] for i in s["item_ids"]}
    ev = lambda body, sub="owner": api.post(f"/api/v2/me/recommendations/outfits/{run}/events", sub, json=body)  # noqa: E731
    assert ev({"kind": "displayed"}).json() == {"run_id": run, "displayed": True, "chosen_index": None}
    assert ev({"kind": "displayed"}).status_code == 200  # twice: still one exposure per item
    assert query(clean_db, "SELECT count(*) FROM recommendation_exposure") == [(len(shown),)]
    assert ev({"kind": "chosen", "index": 0}).json()["chosen_index"] == 0
    assert ev({"kind": "chosen", "index": 0}).status_code == 200  # same choice again: no-op
    other = ev({"kind": "chosen", "index": 1})
    assert other.status_code == 409 and other.json()["code"] == "ALREADY_CHOSEN"
    assert ev({"kind": "chosen", "index": 99}).status_code == 422
    assert ev({"kind": "displayed"}, sub="intruder").status_code == 404  # runs are private
    assert query(clean_db, "SELECT count(*) FROM recommendation_choice") == [(1,)]
    chosen = set(out["suggestions"][0]["item_ids"])
    # Eq. 8 on the next request: chosen items (1 of 1 displayed) score (1 + 2.5)/(1 + 5) = 0.5833
    nxt = _suggest(api)
    for s in nxt["suggestions"]:
        if set(s["item_ids"]) == chosen:
            assert s["components"]["preference"] == pytest.approx(0.5833, abs=1e-4)
    assert any(set(s["item_ids"]) == chosen for s in nxt["suggestions"])
    unshown = _suggest(api)  # fetching without events never changes counts
    assert query(clean_db, "SELECT count(*) FROM recommendation_exposure") == [(len(shown),)]
    assert unshown["run_id"] != run
    exp = api.get("/api/v2/me/export", "owner").json()["wardrobe"]["recommendation_feedback"]
    assert exp["runs"] >= 3 and exp["choices"][0]["suggestion_index"] == 0


# ============================================================== 7.1 account integration
def test_export_has_no_photo_bytes_and_deletion_erases_wardrobe(api, ward, clean_db):
    iid = api.post("/api/v2/me/wardrobe/items", "owner", json={"name": "Thrifted skirt", "slot": "bottom"}).json()["id"]
    api.client.put(f"/api/v2/me/wardrobe/items/{iid}/photo", headers=api.headers("owner"), content=PNG)
    rev = look(api, "Daily", {"top": [ward["top"]], "bottom": [iid], "footwear": [ward["shoes"]]}).json()["current"]["id"]
    put(api, f"/api/v2/me/planner/{today().isoformat()}", "owner", {"look_revision_id": rev})
    api.post("/api/v2/me/wear", "owner", json={"worn_on": today().isoformat(), "look_revision_id": rev},
             idem="wear-export-0001")
    api.post("/api/v2/me/wardrobe/shelves", "owner", json={"name": "All", "item_ids": [iid]})
    put(api, "/api/v2/me/weather/location", "owner", {"adm4": ADM4})
    exp = api.get("/api/v2/me/export", "owner")
    assert exp.status_code == 200, exp.text
    w = exp.json()["wardrobe"]
    declared = next(i for i in w["items"] if i["id"] == iid)
    assert declared["photo_sha256"] and "photo" not in declared
    assert len(w["looks"]) == 1 and len(w["plans"]) == 1 and len(w["wear"]) == 1 and len(w["shelves"]) == 1
    handle = "owner_" + uuid.uuid4().hex[:6]
    api.client.patch("/api/v2/me/profile", headers=api.headers("owner"), json={"handle": handle})
    gone = api.client.request("DELETE", "/api/v2/me", headers=api.headers("owner"), json={"confirm": handle})
    assert gone.status_code == 204, gone.text
    for table in ("wardrobe_declared_item", "look", "look_revision", "plan_entry", "wear_entry", "wardrobe_shelf",
                  "user_weather_location"):
        assert query(clean_db, f"SELECT count(*) FROM {table}") == [(0,)], table


# ============================================================== complete-wearhouse-tdd 1.1 accessory positions
def accessory(api, ext, name, product_type):
    body = synthetic_product(ext, product_name=name, category=product_type)
    body["annotations"] = {"slot": {"value": "accessory", "origin": "rule", "note": "hm-articles@1"}}
    pid = api.post("/api/v2/admin/source-products", "editor-1", json=body).json()["product_id"]
    item = redeem(api, "owner", issue(api, pid)["delivery"]["activation_key"])
    assert item.status_code == 201, item.text
    return item.json()["id"]


def test_accessory_positions_by_rule_and_capacity(api, ward):
    bag = accessory(api, "0610000001", "Canvas tote", "Bag")
    watch = accessory(api, "0610000002", "Steel watch", "Watch")
    clip = accessory(api, "0610000003", "Pearl clip", "Hair clip")
    inv = items(api)
    assert (inv[bag]["slot"], inv[bag]["slot_source"]) == ("bag", "rule")
    assert (inv[watch]["slot"], inv[watch]["slot_source"]) == ("wrist", "rule")
    assert (inv[clip]["slot"], inv[clip]["slot_source"]) == ("accessory", "catalogue")  # unmapped type: not guessed
    reg = api.get("/api/v2/wardrobe/slots").json()
    caps = {s["slot"]: s["capacity"] for s in reg["slots"]}
    assert caps["wrist"] == 2 and caps["ring"] == 2 and caps["accessory"] == 3 and "earrings" in caps
    b1 = api.post("/api/v2/me/wardrobe/items", "owner", json={"name": "Beaded bracelet", "slot": "wrist"}).json()["id"]
    b2 = api.post("/api/v2/me/wardrobe/items", "owner", json={"name": "Cord bracelet", "slot": "wrist"}).json()["id"]
    ok = look(api, "Two wrists", {"top": [ward["top"]], "wrist": [watch, b1], "bag": [bag]})
    assert ok.status_code == 201, ok.text
    over = look(api, "Three wrists", {"top": [ward["top"]], "wrist": [watch, b1, b2]})
    assert over.status_code == 422 and over.json()["field_errors"][0]["code"] == "over_capacity"
    wrong = look(api, "Bag as wrist", {"wrist": [bag]})
    assert wrong.status_code == 422 and wrong.json()["field_errors"][0]["code"] == "slot_mismatch"
    moved = patch(api, f"/api/v2/me/wardrobe/items/{clip}", "owner", {"slot_override": "headwear"})
    assert moved.json()["slot"] == "headwear" and moved.json()["slot_source"] == "override"
    assert items(api)[bag]["attributes"]["warmth"]["value"] == "light"  # research "accessory" default
