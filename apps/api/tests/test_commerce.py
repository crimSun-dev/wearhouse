"""add-wearhouse-sandbox-commerce 2.1 / 3.x / 4.x: offers, wishlist, cart, checkout, receipts, renewal, cancel.

Products are the data-free synthetic fixture (synthetic_only). Prices are sandbox values set by the tests.
"""
from __future__ import annotations

import threading
import uuid

import pytest

from conftest import counts, query, redeem, synthetic_product

pytestmark = [pytest.mark.postgres, pytest.mark.synthetic_only]


@pytest.fixture
def shop(api):
    """Editor + two published products (A, B) with sandbox offers."""
    api.grant("editor-1", "catalogue_editor")
    ids = {}
    for label, ext, name in (("A", "0500000001", "Sandbox tee A"), ("B", "0500000002", "Sandbox coat B")):
        r = api.post("/api/v2/admin/source-products", "editor-1", json=synthetic_product(ext, product_name=name))
        pid = r.json()["product_id"]
        rev = api.get(f"/api/v2/admin/catalogue/products/{pid}", "editor-1").json()["revisions"][-1]["id"]
        assert api.post(f"/api/v2/admin/catalogue/products/{pid}/publish", "editor-1",
                        json={"revision_id": rev}).status_code == 200
        ids[label] = pid
    offer(api, ids["A"], 150_000, 10)
    offer(api, ids["B"], 90_000, 10)
    return ids


def offer(api, pid, price, stock, sub="editor-1"):
    return api.client.put(f"/api/v2/admin/commerce/offers/{pid}", headers=api.headers(sub),
                          json={"price_idr": price, "stock": stock})


def put(api, path, sub, json=None):
    return api.client.put(path, headers=api.headers(sub), json=json)


def delete(api, path, sub):
    return api.client.delete(path, headers=api.headers(sub))


def cart_set(api, sub, pid, qty):
    return put(api, f"/api/v2/me/cart/{pid}", sub, {"quantity": qty})


def checkout(api, sub, total, idem=None):
    return api.post("/api/v2/me/checkout", sub, json={"expected_total_idr": total},
                    idem=idem or ("co-" + uuid.uuid4().hex))


def stock(db, pid):
    return query(db, "SELECT stock FROM sandbox_offer WHERE product_id = :p", p=pid)[0][0]


def key_of(api, sub, order, unit):
    r = api.get(f"/api/v2/me/orders/{order['id']}/units/{unit['unit_id']}/key", sub)
    assert r.status_code == 200, r.text
    return r.json()


def units_of(order):
    return [u for line in order["lines"] for u in line["units"]]


# ============================================================== offers
def test_offers_staff_only_and_public_view_hides_stock(api, shop, clean_db):
    assert offer(api, shop["A"], 1, 1, sub="shopper").status_code == 403
    assert offer(api, str(uuid.uuid4()), 1000, 1).status_code == 404
    bad = offer(api, shop["A"], 0, -1)
    assert bad.status_code == 422 and {e["field"] for e in bad.json()["field_errors"]} == {"body.price_idr", "body.stock"}
    pub = api.get(f"/api/v2/commerce/products/{shop['A']}/offer").json()
    assert pub == {"product_id": shop["A"], "price_idr": 150_000, "currency": "IDR", "in_stock": True, "sandbox": True,
                   "sizes": []}  # one-size product (add-wearhouse-sizes)
    staff = {o["product_id"]: o for o in api.get("/api/v2/admin/commerce/offers", "editor-1").json()}
    assert staff[shop["A"]]["stock"] == 10 and staff[shop["A"]]["on_sale"] is True
    api.post(f"/api/v2/admin/catalogue/products/{shop['B']}/retire", "editor-1")
    assert api.get(f"/api/v2/commerce/products/{shop['B']}/offer").status_code == 404
    assert delete(api, f"/api/v2/admin/commerce/offers/{shop['A']}", "editor-1").status_code == 204
    assert api.get(f"/api/v2/commerce/products/{shop['A']}/offer").status_code == 404
    actions = {a for (a,) in query(clean_db, "SELECT action FROM audit_event WHERE action LIKE 'commerce.%'")}
    assert {"commerce.offer_saved", "commerce.offer_withdrawn"} <= actions


# ============================================================== wishlist / cart
def test_wishlist_rules(api, shop, monkeypatch):
    r = api.post("/api/v2/admin/source-products", "editor-1", json=synthetic_product("0500000009"))
    draft = r.json()["product_id"]
    assert put(api, f"/api/v2/me/wishlist/{draft}", "shopper").status_code == 404
    assert put(api, f"/api/v2/me/wishlist/{shop['A']}", "shopper").status_code == 200
    w = put(api, f"/api/v2/me/wishlist/{shop['A']}", "shopper").json()  # twice: no-op
    assert [i["product_id"] for i in w["items"]] == [shop["A"]] and w["items"][0]["offer"]["sandbox"] is True
    assert api.get("/api/v2/me/wishlist", "other").json()["items"] == []  # owner only
    import wearhouse.commerce.application as app_mod
    monkeypatch.setattr(app_mod, "MAX_WISHLIST", 1)
    full = put(api, f"/api/v2/me/wishlist/{shop['B']}", "shopper")
    assert full.status_code == 409 and full.json()["code"] == "WISHLIST_FULL"
    monkeypatch.undo()
    api.post(f"/api/v2/admin/catalogue/products/{shop['A']}/retire", "editor-1")
    item = api.get("/api/v2/me/wishlist", "shopper").json()["items"][0]
    assert item["available"] is False and item["offer"] is None and item["name"] == "Sandbox tee A"
    assert delete(api, f"/api/v2/me/wishlist/{shop['A']}", "shopper").status_code == 204
    assert api.get("/api/v2/me/wishlist", "shopper").json()["items"] == []


def test_cart_rules_and_totals(api, shop):
    assert cart_set(api, "shopper", shop["A"], 6).status_code == 422
    assert cart_set(api, "shopper", shop["A"], 0).status_code == 422
    r = api.post("/api/v2/admin/source-products", "editor-1", json=synthetic_product("0500000010"))
    pid = r.json()["product_id"]
    rev = api.get(f"/api/v2/admin/catalogue/products/{pid}", "editor-1").json()["revisions"][-1]["id"]
    api.post(f"/api/v2/admin/catalogue/products/{pid}/publish", "editor-1", json={"revision_id": rev})
    nfs = cart_set(api, "shopper", pid, 1)
    assert nfs.status_code == 409 and nfs.json()["code"] == "NOT_FOR_SALE"
    cart_set(api, "shopper", shop["A"], 2)
    c = cart_set(api, "shopper", shop["B"], 1).json()
    assert c["total_idr"] == 390_000 and c["checkout_ready"] is True and c["sandbox"] is True
    assert {l["product_id"]: l["line_total_idr"] for l in c["lines"]} == {shop["A"]: 300_000, shop["B"]: 90_000}
    assert api.get("/api/v2/me/cart", "other").json()["lines"] == []
    offer(api, shop["B"], 90_000, 0)
    c = api.get("/api/v2/me/cart", "shopper").json()
    assert c["checkout_ready"] is False and not next(l for l in c["lines"] if l["product_id"] == shop["B"])["available"]
    c = delete(api, f"/api/v2/me/cart/{shop['B']}", "shopper").json()
    assert c["total_idr"] == 300_000


# ============================================================== checkout
def test_checkout_issues_buyer_bound_units_and_is_idempotent(api, shop, clean_db):
    cart_set(api, "buyer", shop["A"], 2)
    cart_set(api, "buyer", shop["B"], 1)
    r = checkout(api, "buyer", 390_000, idem="co-fixed-0001")
    assert r.status_code == 201, r.text
    order = r.json()
    assert order["total_idr"] == 390_000 and order["status"] == "fulfilled" and order["sandbox"] is True
    assert order["payment_ref"].startswith("sandbox-")
    assert len(units_of(order)) == 3 and "activation_key" not in r.text  # no keys in the receipt
    assert stock(clean_db, shop["A"]) == 8 and stock(clean_db, shop["B"]) == 9
    assert api.get("/api/v2/me/cart", "buyer").json()["lines"] == []
    assert query(clean_db, "SELECT count(*) FROM activation_credential WHERE audience_user_id IS NOT NULL") == [(3,)]
    again = checkout(api, "buyer", 390_000, idem="co-fixed-0001")
    assert again.status_code == 201 and again.json()["id"] == order["id"]
    assert again.headers.get("Idempotent-Replayed") == "true"
    assert counts(clean_db, "sandbox_order", "garment_unit") == {"sandbox_order": 1, "garment_unit": 3}
    other_body = checkout(api, "buyer", 1, idem="co-fixed-0001")
    assert other_body.status_code == 409 and other_body.json()["code"] == "IDEMPOTENCY_KEY_REUSED"


def test_checkout_refusals_change_nothing(api, shop, clean_db):
    empty = checkout(api, "buyer", 0)
    assert empty.status_code == 409 and empty.json()["code"] == "CART_EMPTY"
    cart_set(api, "buyer", shop["A"], 2)
    changed = checkout(api, "buyer", 299_999)
    assert changed.status_code == 409 and changed.json()["code"] == "PRICE_CHANGED"
    offer(api, shop["A"], 150_000, 1)
    short = checkout(api, "buyer", 300_000)
    assert short.status_code == 409 and short.json()["code"] == "OUT_OF_STOCK"
    offer(api, shop["A"], 150_000, 10)
    api.post(f"/api/v2/admin/catalogue/products/{shop['A']}/retire", "editor-1")
    gone = checkout(api, "buyer", 300_000)
    assert gone.status_code == 409 and gone.json()["code"] == "NOT_AVAILABLE"
    assert counts(clean_db, "sandbox_order", "garment_unit", "activation_credential") == {
        "sandbox_order": 0, "garment_unit": 0, "activation_credential": 0}
    assert stock(clean_db, shop["A"]) == 10
    assert len(api.get("/api/v2/me/cart", "buyer").json()["lines"]) == 1  # cart kept


def test_concurrent_checkouts_for_the_last_item(api, shop, clean_db):
    offer(api, shop["A"], 150_000, 1)
    buyers = [f"racer-{i}" for i in range(4)]
    for b in buyers:
        cart_set(api, b, shop["A"], 1)
    headers = [api.headers(b, idem="race-" + uuid.uuid4().hex) for b in buyers]
    out, barrier = [], threading.Barrier(len(buyers))

    def go(h):
        barrier.wait()
        out.append(api.client.post("/api/v2/me/checkout", json={"expected_total_idr": 150_000}, headers=h))

    ts = [threading.Thread(target=go, args=(h,)) for h in headers]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert sorted(r.status_code for r in out) == [201, 409, 409, 409]
    assert {r.json()["code"] for r in out if r.status_code == 409} == {"OUT_OF_STOCK"}
    assert stock(clean_db, shop["A"]) == 0 and counts(clean_db, "sandbox_order")["sandbox_order"] == 1


# ============================================================== receipts / keys / cancel
def test_receipt_key_reveal_claim_and_isolation(api, shop, clean_db):
    cart_set(api, "buyer", shop["A"], 1)
    order = checkout(api, "buyer", 150_000).json()
    unit = units_of(order)[0]
    assert unit["delivery"]["status"] == "available" and "activation_key" not in unit["delivery"]
    assert api.get(f"/api/v2/me/orders/{order['id']}", "intruder").status_code == 404
    assert api.get(f"/api/v2/me/orders/{order['id']}/units/{unit['unit_id']}/key", "intruder").status_code == 404
    k = key_of(api, "buyer", order, unit)
    assert k["status"] == "available" and k["activation_key"]
    reveal_audits = query(clean_db, "SELECT count(*) FROM audit_event WHERE action = 'ownership.delivery_accessed'")
    assert reveal_audits == [(1,)]
    assert redeem(api, "intruder", k["activation_key"]).status_code == 400  # buyer-bound
    claim = redeem(api, "buyer", k["activation_key"])
    assert claim.status_code == 201, claim.text
    assert len(api.get("/api/v2/me/items", "buyer").json()["items"]) == 1
    receipt = api.get(f"/api/v2/me/orders/{order['id']}", "buyer").json()
    assert units_of(receipt)[0]["state"] == "claimed" and units_of(receipt)[0]["delivery"] == {
        "status": "claimed", "expires_at": None, "expired_at": None, "reason": None}
    assert receipt["cancellable"] is True  # complete-wearhouse-tdd: cancelling after a claim revokes the sandbox item
    assert key_of(api, "buyer", order, unit)["status"] == "claimed"
    listed = api.get("/api/v2/me/orders", "buyer").json()
    assert [o["id"] for o in listed["items"]] == [order["id"]] and listed["items"][0]["item_count"] == 1
    assert api.get("/api/v2/me/orders", "intruder").json()["items"] == []
    item_id = claim.json()["id"]
    gone = api.post(f"/api/v2/me/orders/{order['id']}/cancel", "buyer")
    assert gone.status_code == 200 and gone.json()["status"] == "cancelled"
    assert units_of(gone.json())[0]["state"] == "revoked"
    assert units_of(gone.json())[0]["delivery"]["reason"] == "revoked_sandbox"
    mine = api.get(f"/api/v2/me/items/{item_id}", "buyer").json()
    assert mine["state"] == "revoked_sandbox" and mine["revoked_reason"] == "sandbox_order_cancelled"
    assert api.get("/api/v2/me/wardrobe/items", "buyer").json()["items"] == []  # left the wardrobe
    assert stock(clean_db, shop["A"]) == 10  # restocked
    events = query(clean_db, "SELECT event_type FROM ownership_event WHERE item_id = :i ORDER BY created_at",
                   i=item_id)
    assert [e[0] for e in events] == ["claimed", "sandbox_revoked"]
    assert redeem(api, "buyer", k["activation_key"]).status_code == 400  # the unit can never be claimed again


def test_renew_key_revokes_old_key(api, shop):
    cart_set(api, "buyer", shop["A"], 1)
    order = checkout(api, "buyer", 150_000).json()
    unit = units_of(order)[0]
    old = key_of(api, "buyer", order, unit)["activation_key"]
    r = api.post(f"/api/v2/me/orders/{order['id']}/units/{unit['unit_id']}/renew-key", "buyer", idem="rk-renew-0001")
    assert r.status_code == 201, r.text
    assert api.post(f"/api/v2/me/orders/{order['id']}/units/{unit['unit_id']}/renew-key", "intruder",
                    idem="rk-renew-0002").status_code == 404
    new = key_of(api, "buyer", order, unit)["activation_key"]
    assert new != old
    assert redeem(api, "buyer", old).status_code == 400
    assert redeem(api, "buyer", new).status_code == 201


def test_cancel_revokes_keys_and_restocks(api, shop, clean_db):
    cart_set(api, "buyer", shop["A"], 2)
    order = checkout(api, "buyer", 300_000).json()
    key = key_of(api, "buyer", order, units_of(order)[0])["activation_key"]
    assert stock(clean_db, shop["A"]) == 8
    out = api.post(f"/api/v2/me/orders/{order['id']}/cancel", "buyer")
    assert out.status_code == 200, out.text
    body = out.json()
    assert body["status"] == "cancelled" and all(u["state"] == "retired" for u in units_of(body))
    assert stock(clean_db, shop["A"]) == 10
    assert redeem(api, "buyer", key).status_code == 400
    assert api.post(f"/api/v2/me/orders/{order['id']}/cancel", "buyer").json()["status"] == "cancelled"  # idempotent
    assert api.post(f"/api/v2/me/orders/{order['id']}/cancel", "intruder").status_code == 404
    renew = api.post(f"/api/v2/me/orders/{order['id']}/units/{units_of(order)[0]['unit_id']}/renew-key", "buyer",
                     idem="rk-cancelled")
    assert renew.status_code == 409


def test_cancel_versus_claim_race_has_one_winner(api, shop, clean_db):
    for attempt in range(3):
        cart_set(api, "buyer", shop["A"], 1)
        order = checkout(api, "buyer", 150_000).json()
        key = key_of(api, "buyer", order, units_of(order)[0])["activation_key"]
        h_cancel, h_claim = api.headers("buyer"), api.headers("buyer", idem="claim-" + uuid.uuid4().hex)
        res, barrier = {}, threading.Barrier(2)

        def cancel():
            barrier.wait()
            res["cancel"] = api.client.post(f"/api/v2/me/orders/{order['id']}/cancel", headers=h_cancel)

        def claim():
            barrier.wait()
            res["claim"] = api.client.post("/api/v2/redemptions", json={"activation_key": key}, headers=h_claim)

        ts = [threading.Thread(target=cancel), threading.Thread(target=claim)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        assert res["cancel"].status_code == 200, res["cancel"].text  # cancelling always succeeds now
        claimed = res["claim"].status_code == 201
        state = query(clean_db, "SELECT status FROM garment_unit WHERE id = :u", u=units_of(order)[0]["unit_id"])
        items = query(clean_db, "SELECT revoked_at IS NOT NULL FROM owned_item")
        if claimed:  # the claim won the race: the cancel then revoked the item
            assert state == [("claimed",)] and items == [(True,)]
        else:  # the cancel won: nothing was ever owned
            assert res["claim"].status_code == 400 and state == [("retired",)] and items == []


# ============================================================== accounts integration
def test_export_and_deletion_integration(api, shop, clean_db, issuer):
    put(api, f"/api/v2/me/wishlist/{shop['B']}", "buyer")
    cart_set(api, "buyer", shop["A"], 1)
    order = checkout(api, "buyer", 150_000).json()
    key_of(api, "buyer", order, units_of(order)[0])
    cart_set(api, "buyer", shop["B"], 1)
    exp = api.get("/api/v2/me/export", "buyer")
    assert exp.status_code == 200, exp.text
    doc = exp.json()["commerce"]
    assert [o["id"] for o in doc["orders"]] == [order["id"]] and doc["orders"][0]["lines"][0]["quantity"] == 1
    assert doc["wishlist"][0]["product_id"] == shop["B"] and doc["cart"][0]["product_id"] == shop["B"]
    assert "activation_key" not in exp.text
    handle = "buyer_" + uuid.uuid4().hex[:6]
    api.client.patch("/api/v2/me/profile", headers=api.headers("buyer"), json={"handle": handle})
    gone = api.client.request("DELETE", "/api/v2/me", headers=api.headers("buyer"), json={"confirm": handle})
    assert gone.status_code == 204, gone.text
    assert counts(clean_db, "wishlist_item", "cart_line", "sandbox_order") == {
        "wishlist_item": 0, "cart_line": 0, "sandbox_order": 1}
