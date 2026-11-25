"""harden-wearhouse-services-api 2.1: the F11 ecosystem acceptance thread.

One database, signed identities, HTTP only (the first admin comes from the CLI-equivalent bootstrap grant):
admin grants roles -> editor imports, publishes, generates media, applies bulk offers -> customer searches, wishlists,
buys, reveals the key, claims -> builds a look, plans it, wears it, shares it -> friend sees feed + notification ->
recommendations declare their mode -> a FRESH app on the same database serves the same state -> a second customer
cannot read any private object. Products are synthetic rows in H&M format (synthetic_only)."""
from __future__ import annotations

import csv
import io
from datetime import datetime, timezone

import pytest

from conftest import Api, befriend, onboard
from wearhouse.testing import create_test_app
from wearhouse.weather.application import local_today

pytestmark = [pytest.mark.postgres, pytest.mark.synthetic_only]

CONTEXT = {
    "source": {"namespace": "hm-format-synthetic", "name": "Synthetic rows in H&M articles.csv format",
               "url": "https://wearhouse.invalid/hm-format-synthetic"},
    "snapshot": {"sha256": "d" * 64, "file_name": "articles-acceptance.csv", "acquired_on": "2026-11-25"},
    "permission": {"basis": "synthetic-test-fixture", "scope": "automated tests only", "accepted_on": "2026-11-25",
                   "accepted_by": "wearhouse test suite", "terms_url": "https://wearhouse.invalid/terms"},
}
ROWS = [("0900000001", "Acceptance linen shirt", "Shirt", "Garment Upper body", "Light Blue", "Relaxed linen shirt."),
        ("0900000002", "Acceptance chino", "Trousers", "Garment Lower body", "Beige", "Straight chino trousers."),
        ("0900000003", "Acceptance oxford shirt", "Shirt", "Garment Upper body", "White", "Oxford cotton shirt.")]


def ok(r, status=200):
    assert r.status_code == status, f"{r.request.method} {r.request.url.path}: {r.status_code} {r.text}"
    return r.json() if r.content else None


def put(api, path, sub, json=None, idem=None):
    return api.client.put(path, headers=api.headers(sub, idem), json=json)


def patch(api, path, sub, json):
    return api.client.patch(path, headers=api.headers(sub), json=json)


def csv_text() -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["article_id", "product_code", "prod_name", "product_type_name", "product_group_name",
                "colour_group_name", "department_name", "garment_group_name", "detail_desc"])
    for aid, name, ptype, group, colour, desc in ROWS:
        w.writerow([aid, aid[:7], name, ptype, group, colour, "Synthetic dept", "Synthetic group", desc])
    return buf.getvalue()


def test_f11_thread_restart_and_isolation(api, settings, issuer):
    # 1. the bootstrap admin grants staff roles in the app (no direct DB grants for staff)
    api.grant("boss", "admin")
    for u in ("boss", "editor", "stock", "dina", "fajar", "stranger"):
        onboard(api, u)
    ok(put(api, "/api/v2/admin/staff/editor/roles/catalogue_editor", "boss"))
    ok(put(api, "/api/v2/admin/staff/stock/roles/inventory_manager", "boss"))
    assert ok(api.get("/api/v2/admin/staff", "boss")) and api.get("/api/v2/admin/staff", "editor").status_code == 403

    # 2. editor: import -> publish -> generated media -> bulk sandbox offers
    job = ok(api.post("/api/v2/admin/catalogue/import-jobs", "editor", json={**CONTEXT, "csv": csv_text()}), 201)
    assert job["totals"]["rejected"] == 0
    pub = ok(api.post(f"/api/v2/admin/catalogue/import-jobs/{job['id']}/publish", "editor"))
    assert pub["published"] == 3
    assert ok(api.post("/api/v2/admin/catalogue/media/generate-missing", "editor"))["generated"] == 3
    bulk = ok(api.post("/api/v2/admin/commerce/offers/bulk", "editor",
                       json={"rules": [{"category": "Shirt", "price_idr": 199000, "stock": 5},
                                       {"category": "Trousers", "price_idr": 249000, "stock": 5}]}))
    assert sum(r["written"] for r in bulk["results"]) == 3

    # 3. customer: search -> wishlist -> buy -> reveal key -> claim
    found = ok(api.get("/api/v2/catalogue/products", params={"q": "linen shirt"}))["items"]
    shirt = next(p for p in found if p["name"] == "Acceptance linen shirt")
    assert shirt["thumbnail"]  # the generated placeholder object
    img = api.client.get("/api/v2/media/" + shirt["thumbnail"].rstrip("/").split("/media/")[-1])
    assert img.status_code == 200 and img.headers["content-type"].startswith("image/svg+xml")
    ok(put(api, f"/api/v2/me/wishlist/{shirt['id']}", "dina"))
    ok(put(api, f"/api/v2/me/cart/{shirt['id']}", "dina", {"quantity": 1}))
    order = ok(api.post("/api/v2/me/checkout", "dina", json={"expected_total_idr": 199000}, idem="co-f11-0001"), 201)
    unit = order["lines"][0]["units"][0]
    key = ok(api.get(f"/api/v2/me/orders/{order['id']}/units/{unit['unit_id']}/key", "dina"))["activation_key"]
    claimed = ok(api.post("/api/v2/redemptions", "dina", json={"activation_key": key}, idem="claim-f11-0001"), 201)
    item_id = claimed["id"]

    # 4. look -> plan -> wear -> share
    wardrobe = {i["id"]: i for i in ok(api.get("/api/v2/me/wardrobe/items", "dina"))["items"]}
    assert wardrobe[item_id]["verified"] is True and wardrobe[item_id]["kind"] == "verified"
    if wardrobe[item_id].get("slot") != "top":
        ok(patch(api, f"/api/v2/me/wardrobe/items/{item_id}", "dina", {"slot_override": "top"}))
    skirt = ok(api.post("/api/v2/me/wardrobe/items", "dina", json={"name": "Own trousers", "slot": "bottom"}), 201)["id"]
    look = ok(api.post("/api/v2/me/looks", "dina", json={"name": "Office", "slots": {"top": [item_id],
                                                                                   "bottom": [skirt]}}), 201)
    rev = look["current"]["id"]
    today = local_today(datetime.now(timezone.utc)).isoformat()
    ok(put(api, f"/api/v2/me/planner/{today}", "dina", {"look_revision_id": rev}))
    ok(api.post("/api/v2/me/wear", "dina", json={"worn_on": today, "look_revision_id": rev}, idem="wear-f11-0001"), 201)
    ok(put(api, "/api/v2/me/privacy", "dina", {"profile": "public", "wardrobe": "friends", "friends_list": "friends"}))
    befriend(api, "dina", "fajar")
    share = ok(api.post("/api/v2/me/shares", "dina", json={"look_id": look["id"], "audience": "friends",
                                                           "caption": "Office day"}), 201)

    # 5. the friend sees it
    feed = ok(api.get("/api/v2/me/feed", "fajar"))["items"]
    assert [s["id"] for s in feed] == [share["id"]]
    notes = ok(api.get("/api/v2/me/notifications", "fajar"))["items"]
    assert any(n["kind"] == "friend_shared_look" and n["ref"] == share["id"] for n in notes)

    # 6. recommendations answer with a declared mode, never recommending what dina owns
    sim = ok(api.get(f"/api/v2/catalogue/products/{shirt['id']}/similar"))
    assert sim["model"]["mode"] == "heuristic_baseline" and sim["items"]
    mine = ok(api.get("/api/v2/me/recommendations/products", "dina"))
    assert mine["model"]["mode"] == "heuristic_baseline" and shirt["id"] not in {i["id"] for i in mine["items"]}

    before = {
        "item": ok(api.get(f"/api/v2/me/wardrobe/items/{item_id}", "dina")),
        "order": ok(api.get(f"/api/v2/me/orders/{order['id']}", "dina")),
        "look": ok(api.get(f"/api/v2/me/looks/{look['id']}", "dina")),
        "share": ok(api.get(f"/api/v2/shares/{share['id']}", "fajar")),
    }
    assert before["item"]["wear_count"] == 1

    # 7. restart: a fresh app instance on the same database serves the same state
    fresh = Api(create_test_app(settings, issuer=issuer), issuer)
    assert ok(fresh.get(f"/api/v2/me/wardrobe/items/{item_id}", "dina")) == before["item"]
    assert ok(fresh.get(f"/api/v2/me/orders/{order['id']}", "dina")) == before["order"]
    assert ok(fresh.get(f"/api/v2/me/looks/{look['id']}", "dina")) == before["look"]
    assert ok(fresh.get(f"/api/v2/shares/{share['id']}", "fajar")) == before["share"]
    assert any(n["ref"] == share["id"] for n in ok(fresh.get("/api/v2/me/notifications", "fajar"))["items"])

    # 8. isolation: an unrelated customer gets 404/403 for every private object of dina
    private_paths = [
        f"/api/v2/me/orders/{order['id']}",
        f"/api/v2/me/orders/{order['id']}/units/{unit['unit_id']}/key",
        f"/api/v2/me/wardrobe/items/{item_id}",
        f"/api/v2/me/wardrobe/items/{skirt}",
        f"/api/v2/me/items/{item_id}",
        f"/api/v2/me/looks/{look['id']}",
        f"/api/v2/me/look-revisions/{rev}",
        f"/api/v2/shares/{share['id']}",
        "/api/v2/profiles/dina/week",
    ]
    for path in private_paths:
        assert fresh.get(path, "stranger").status_code in (403, 404), path
    assert fresh.get(f"/api/v2/shares/{share['id']}").status_code == 404  # anonymous
    leaks = [ok(fresh.get(p, "stranger")) for p in ("/api/v2/me/orders", "/api/v2/me/looks", "/api/v2/me/feed")]
    assert all(not (x.get("items") if isinstance(x, dict) else x) for x in leaks)
    stranger_plan = ok(fresh.get("/api/v2/me/planner", "stranger"))
    assert rev not in str(stranger_plan) and look["id"] not in str(stranger_plan)  # own planner only
    assert rev in str(ok(fresh.get("/api/v2/me/planner", "dina")))  # dina's plan did survive the restart
