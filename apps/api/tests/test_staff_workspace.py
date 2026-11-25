"""add-wearhouse-object-management 3.1 / 3.2: in-app role administration, capability-driven access, staff unit list,
staff order view, bulk sandbox offers. Products are the data-free synthetic fixture (synthetic_only)."""
from __future__ import annotations

import pytest

from conftest import issue, onboard, query, redeem, synthetic_product

pytestmark = [pytest.mark.postgres, pytest.mark.synthetic_only]


def put(api, path, sub, json=None):
    return api.client.put(path, headers=api.headers(sub), json=json)


def delete(api, path, sub):
    return api.client.delete(path, headers=api.headers(sub))


@pytest.fixture
def staffed(api):
    api.grant("boss", "admin")
    for u in ("boss", "alice", "carol"):
        onboard(api, u)
    return api


def caps(api, sub):
    return set(api.get("/api/v2/me", sub).json()["capabilities"])


# ============================================================== 3.1 roles
def test_admin_grants_and_revokes_with_immediate_effect(staffed, clean_db):
    api = staffed
    assert api.get("/api/v2/admin/catalogue/review", "alice").status_code == 403
    g = put(api, "/api/v2/admin/staff/alice/roles/catalogue_editor", "boss")
    assert g.status_code == 200 and g.json()["roles"] == ["catalogue_editor"]
    assert {"catalogue:ingest", "catalogue:media", "commerce:offers"} <= caps(api, "alice")
    assert api.get("/api/v2/admin/catalogue/review", "alice").status_code == 200  # next request
    staff = {s["handle"]: s["roles"] for s in api.get("/api/v2/admin/staff", "boss").json()}
    assert staff == {"boss": ["admin"], "alice": ["catalogue_editor"]}
    assert api.get("/api/v2/admin/staff/alice", "boss").json()["roles"] == ["catalogue_editor"]
    r = delete(api, "/api/v2/admin/staff/alice/roles/catalogue_editor", "boss")
    assert r.status_code == 200 and r.json()["roles"] == []
    assert api.get("/api/v2/admin/catalogue/review", "alice").status_code == 403
    actions = [a for (a,) in query(clean_db, "SELECT action FROM audit_event WHERE details->>'via' = 'admin_api' "
                                             "")]
    assert sorted(actions) == ["identity.role_granted", "identity.role_revoked"]


def test_role_admin_protections_and_permissions(staffed):
    api = staffed
    last = delete(api, "/api/v2/admin/staff/boss/roles/admin", "boss")
    assert last.status_code == 409 and last.json()["code"] == "LAST_ADMIN"
    put(api, "/api/v2/admin/staff/alice/roles/admin", "boss")
    own = delete(api, "/api/v2/admin/staff/boss/roles/admin", "boss")
    assert own.status_code == 409 and own.json()["code"] == "SELF_REVOKE"
    assert delete(api, "/api/v2/admin/staff/boss/roles/admin", "alice").status_code == 200  # another admin may
    assert api.get("/api/v2/admin/staff", "boss").status_code == 403  # boss is no longer an admin
    assert put(api, "/api/v2/admin/staff/carol/roles/admin", "carol").status_code == 403
    assert api.get("/api/v2/admin/staff", "carol").status_code == 403
    assert put(api, "/api/v2/admin/staff/nobody/roles/admin", "alice").status_code == 404
    assert put(api, "/api/v2/admin/staff/carol/roles/superuser", "alice").status_code == 422


def test_inventory_manager_capabilities(staffed):
    api = staffed
    put(api, "/api/v2/admin/staff/carol/roles/inventory_manager", "boss")
    c = caps(api, "carol")
    assert {"inventory:issue", "inventory:reissue", "commerce:orders"} <= c
    assert not c & {"catalogue:ingest", "identity:manage_roles", "catalogue:media"}
    assert {"identity:manage_roles", "catalogue:media", "commerce:orders"} <= caps(api, "boss")


# ============================================================== 3.2 workspace objects
@pytest.fixture
def shop(staffed):
    api = staffed
    put(api, "/api/v2/admin/staff/alice/roles/catalogue_editor", "boss")
    put(api, "/api/v2/admin/staff/carol/roles/inventory_manager", "boss")
    ids = {}
    for ext, name, cat in (("0900000001", "Tee one", "T-shirt"), ("0900000002", "Tee two", "T-shirt"),
                           ("0900000003", "Jeans", "Trousers")):
        body = synthetic_product(ext, product_name=name, category=cat)
        pid = api.post("/api/v2/admin/source-products", "alice", json=body).json()["product_id"]
        rev = api.get(f"/api/v2/admin/catalogue/products/{pid}", "alice").json()["revisions"][-1]["id"]
        api.post(f"/api/v2/admin/catalogue/products/{pid}/publish", "alice", json={"revision_id": rev})
        ids[name] = pid
    return ids


def test_unit_list_has_no_secrets(staffed, shop):
    api = staffed
    pid = shop["Tee one"]
    units = [issue(api, pid, sub="carol") for _ in range(3)]
    assert redeem(api, "dora", units[0]["delivery"]["activation_key"]).status_code == 201
    page = api.get("/api/v2/admin/units", "carol", params={"product_id": pid, "limit": 2})
    assert page.status_code == 200, page.text
    first = page.json()
    rest = api.get("/api/v2/admin/units", "carol", params={"product_id": pid, "cursor": first["next_cursor"]}).json()
    listed = first["items"] + rest["items"]
    assert len(listed) == 3 and {u["status"] for u in listed} == {"issued", "claimed"}
    text = page.text + str(rest)
    assert "activation_key" not in text and "dora" not in text and "user" not in text
    assert api.get("/api/v2/admin/units", "alice", params={"product_id": pid}).status_code == 403


def test_bulk_offers_and_staff_orders(staffed, shop, clean_db):
    api = staffed
    r = api.post("/api/v2/admin/commerce/offers/bulk", "alice",
                 json={"rules": [{"category": "T-shirt", "price_idr": 99000, "stock": 5}]})
    assert r.status_code == 200, r.text
    assert r.json()["results"] == [{"category": "T-shirt", "slot": None, "matched": 2, "written": 2, "sized": 0}]
    again = api.post("/api/v2/admin/commerce/offers/bulk", "alice",
                     json={"rules": [{"category": "T-shirt", "price_idr": 120000, "stock": 5}]}).json()
    assert again["results"][0]["written"] == 0  # overwrite false keeps existing offers
    over = api.post("/api/v2/admin/commerce/offers/bulk", "alice",
                    json={"rules": [{"category": "T-shirt", "price_idr": 120000, "stock": 5}], "overwrite": True}).json()
    assert over["results"][0]["written"] == 2
    assert api.get(f"/api/v2/commerce/products/{shop['Tee one']}/offer").json()["price_idr"] == 120000
    bad = api.post("/api/v2/admin/commerce/offers/bulk", "alice", json={"rules": [{"price_idr": 0, "stock": 1}]})
    assert bad.status_code == 422
    assert api.post("/api/v2/admin/commerce/offers/bulk", "carol",
                    json={"rules": [{"category": "T-shirt", "price_idr": 1, "stock": 1}]}).status_code == 403
    assert query(clean_db, "SELECT count(*) FROM audit_event WHERE action = 'commerce.offers_bulk_saved'") == [(3,)]

    onboard(api, "dora")
    put(api, f"/api/v2/me/cart/{shop['Tee one']}", "dora", {"quantity": 2})
    order = api.post("/api/v2/me/checkout", "dora", json={"expected_total_idr": 240000}, idem="co-staff-0001").json()
    listing = api.get("/api/v2/admin/commerce/orders", "carol")
    assert listing.status_code == 200, listing.text
    o = listing.json()["items"][0]
    assert o["id"] == order["id"] and o["buyer_handle"] == "dora" and o["item_count"] == 2 and o["sandbox"] is True
    assert "activation_key" not in listing.text and "public_serial" not in listing.text
    assert api.get("/api/v2/admin/commerce/orders", "carol", params={"status": "cancelled"}).json()["items"] == []
    assert api.get("/api/v2/admin/commerce/orders", "dora").status_code == 403
    assert api.get("/api/v2/admin/commerce/orders", "alice").status_code == 403  # editors have no commerce:orders
    api.client.request("DELETE", "/api/v2/me", headers=api.headers("dora"), json={"confirm": "dora"})
    assert api.get("/api/v2/admin/commerce/orders", "boss").json()["items"][0]["buyer_handle"] is None
