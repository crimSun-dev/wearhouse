"""add-wearhouse-sizes: size registry as managed objects, product sizes (rule mock data / staff), usual sizes,
shop-by-size, sized commerce, sized units and wardrobe sorting. Synthetic rows in H&M format (synthetic_only)."""
from __future__ import annotations

import csv
import io

import pytest

from conftest import onboard, query

pytestmark = [pytest.mark.postgres, pytest.mark.synthetic_only]

CONTEXT = {
    "source": {"namespace": "hm-format-synthetic", "name": "Synthetic rows in H&M articles.csv format",
               "url": "https://wearhouse.invalid/hm-format-synthetic"},
    "snapshot": {"sha256": "e" * 64, "file_name": "articles-sizes.csv", "acquired_on": "2026-11-25"},
    "permission": {"basis": "synthetic-test-fixture", "scope": "automated tests only", "accepted_on": "2026-11-25",
                   "accepted_by": "wearhouse test suite", "terms_url": "https://wearhouse.invalid/terms"},
}
ROWS = {"tee": ("1200000001", "Size tee", "T-shirt", "Garment Upper body"),
        "chino": ("1200000002", "Size chino", "Trousers", "Garment Lower body"),
        "shoe": ("1200000003", "Size sneaker", "Sneakers", "Shoes"),
        "bag": ("1200000004", "Size bag", "Bag", "Accessories")}
ALPHA_COMMON = ["XS", "S", "M", "L", "XL", "XXL"]
SHOE_COMMON = [str(n) for n in range(36, 46)]


def put(api, path, sub, json=None):
    return api.client.put(path, headers=api.headers(sub), json=json)


def csv_text() -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["article_id", "product_code", "prod_name", "product_type_name", "product_group_name",
                "colour_group_name", "department_name", "garment_group_name", "detail_desc"])
    for aid, name, ptype, group in ROWS.values():
        w.writerow([aid, aid[:7], name, ptype, group, "Black", "Synthetic dept", "Synthetic group", name + "."])
    return buf.getvalue()


@pytest.fixture
def shop(api):
    api.grant("editor-1", "catalogue_editor")
    api.grant("inventory-1", "inventory_manager")
    job = api.post("/api/v2/admin/catalogue/import-jobs", "editor-1", json={**CONTEXT, "csv": csv_text()}).json()
    api.post(f"/api/v2/admin/catalogue/import-jobs/{job['id']}/publish", "editor-1")
    ids = {r["external_id"]: r["product_id"] for r in job["rows"]}
    return {k: ids[v[0]] for k, v in ROWS.items()}


def assign(api):
    r = api.post("/api/v2/admin/catalogue/sizes/assign-missing", "editor-1")
    assert r.status_code == 200, r.text
    return r.json()


def codes(sizes):
    return [s["code"] for s in sizes]


# ============================================================== 1.1 registry
def test_registry_is_seeded_ordered_and_staff_managed(api, clean_db):
    reg = api.get("/api/v2/catalogue/sizes").json()["systems"]
    assert [s["code"] for s in reg] == ["alpha", "eu_clothing", "eu_shoe"]
    assert codes(reg[0]["sizes"]) == ["XXS", "XS", "S", "M", "L", "XL", "XXL", "3XL"]
    assert codes(reg[2]["sizes"])[0] == "35" and codes(reg[2]["sizes"])[-1] == "47"
    assert reg[0]["slots"] == ["top", "outer", "bottom", "dress"] and reg[2]["slots"] == ["footwear"]
    assert reg[0]["active"] is None  # public view hides retirement flags
    api.grant("editor-1", "catalogue_editor")
    assert put(api, "/api/v2/admin/catalogue/size-systems/alpha/sizes/4XL", "shopper",
               {"label": "4XL", "rank": 90}).status_code == 403
    r = put(api, "/api/v2/admin/catalogue/size-systems/kids/sizes/K1", "editor-1", {"label": "K1", "rank": 10})
    assert r.status_code == 404  # unknown system
    r = put(api, "/api/v2/admin/catalogue/size-systems/kids", "editor-1",
            {"label": "Kids (age)", "position": 40, "slots": ["top"]})
    assert r.status_code == 422 and r.json()["field_errors"][0]["code"] == "slot_taken"  # alpha already owns top
    assert put(api, "/api/v2/admin/catalogue/size-systems/kids", "editor-1",
               {"label": "Kids (age)", "position": 40}).status_code == 200
    for code, rank in (("2Y", 20), ("1Y", 10)):
        assert put(api, f"/api/v2/admin/catalogue/size-systems/kids/sizes/{code}", "editor-1",
                   {"label": code, "rank": rank}).status_code == 200
    kids = api.get("/api/v2/catalogue/sizes").json()["systems"][-1]
    assert kids["code"] == "kids" and codes(kids["sizes"]) == ["1Y", "2Y"]  # rank order, not insert order
    put(api, "/api/v2/admin/catalogue/size-systems/kids/sizes/2Y", "editor-1", {"label": "2Y", "rank": 20,
                                                                              "active": False})
    assert codes(api.get("/api/v2/catalogue/sizes").json()["systems"][-1]["sizes"]) == ["1Y"]  # retired: hidden
    staff = api.get("/api/v2/admin/catalogue/sizes", "editor-1").json()["systems"][-1]
    assert {s["code"]: s["active"] for s in staff["sizes"]} == {"1Y": True, "2Y": False}
    assert query(clean_db, "SELECT count(*) FROM audit_event WHERE action LIKE 'catalogue.size%'") == [(4,)]


def test_bad_registry_input(api):
    api.grant("editor-1", "catalogue_editor")
    assert put(api, "/api/v2/admin/catalogue/size-systems/Bad-Code", "editor-1",
               {"label": "x", "position": 1}).status_code == 422
    assert put(api, "/api/v2/admin/catalogue/size-systems/alpha/sizes/TOO_LONG_CODE", "editor-1",
               {"label": "x", "rank": 1}).status_code == 422
    assert put(api, "/api/v2/admin/catalogue/size-systems/alpha", "editor-1",
               {"label": "Letter", "position": 10, "slots": ["hat"]}).status_code == 422


# ============================================================== 1.1 product sizes
def test_rule_assignment_by_slot_and_staff_edits(api, shop, clean_db):
    out = assign(api)
    assert out == {"assigned": 3, "more_remaining": False}  # tee, chino, shoe; the bag stays one-size
    assert assign(api)["assigned"] == 0  # idempotent: only products without sizes
    tee = api.get(f"/api/v2/catalogue/products/{shop['tee']}").json()
    assert codes(tee["sizes"]) == ALPHA_COMMON and tee["sizes"][0]["origin"] == "rule" and not tee["one_size"]
    assert codes(api.get(f"/api/v2/catalogue/products/{shop['shoe']}/sizes").json()["sizes"]) == SHOE_COMMON
    bag = api.get(f"/api/v2/catalogue/products/{shop['bag']}").json()
    assert bag["one_size"] and bag["sizes"] == []
    mixed = put(api, f"/api/v2/admin/catalogue/products/{shop['tee']}/sizes", "editor-1",
                {"sizes": [{"system": "alpha", "code": "M"}, {"system": "eu_shoe", "code": "42"}]})
    assert mixed.status_code == 422 and mixed.json()["field_errors"][0]["code"] == "mixed_systems"
    unknown = put(api, f"/api/v2/admin/catalogue/products/{shop['tee']}/sizes", "editor-1",
                  {"sizes": [{"system": "alpha", "code": "9XL"}]})
    assert unknown.status_code == 422
    assert codes(api.get(f"/api/v2/catalogue/products/{shop['tee']}").json()["sizes"]) == ALPHA_COMMON  # unchanged
    r = put(api, f"/api/v2/admin/catalogue/products/{shop['tee']}/sizes", "editor-1",
            {"sizes": [{"system": "alpha", "code": c} for c in ("L", "S", "M")]})
    assert r.status_code == 200 and codes(r.json()["sizes"]) == ["S", "M", "L"]  # rank order
    assert r.json()["sizes"][0]["origin"] == "staff"
    assert put(api, f"/api/v2/admin/catalogue/products/{shop['tee']}/sizes", "shopper",
               {"sizes": []}).status_code == 403
    assert api.post("/api/v2/admin/catalogue/sizes/assign-missing", "shopper").status_code == 403
    card = next(i for i in api.get("/api/v2/catalogue/products", params={"q": "size tee"}).json()["items"])
    assert card["sizes"] == ["S", "M", "L"]
    assert query(clean_db, "SELECT count(*) FROM audit_event WHERE action LIKE 'catalogue.product_sizes%'") == [(3,)]


def test_assignment_is_bounded(api, shop):
    first = api.post("/api/v2/admin/catalogue/sizes/assign-missing", "editor-1", params={"limit": 2}).json()
    assert first == {"assigned": 2, "more_remaining": True}
    assert assign(api) == {"assigned": 1, "more_remaining": False}


# ============================================================== 1.1 usual sizes + shop by size
def test_usual_sizes_and_shop_by_size(api, shop):
    assign(api)
    assert put(api, f"/api/v2/admin/catalogue/products/{shop['chino']}/sizes", "editor-1",
               {"sizes": [{"system": "alpha", "code": c} for c in ("L", "XL")]}).status_code == 200
    me = api.get("/api/v2/me/sizes", "dina").json()["systems"]
    assert [s["system"] for s in me] == ["alpha", "eu_clothing", "eu_shoe"] and all(s["usual"] is None for s in me)
    no = api.get("/api/v2/catalogue/products", "dina", params={"my_sizes": "true"})
    assert no.status_code == 409 and no.json()["code"] == "NO_USUAL_SIZES"
    assert api.get("/api/v2/catalogue/products", params={"my_sizes": "true"}).status_code == 401
    bad = put(api, "/api/v2/me/sizes", "dina", {"usual": {"alpha": "9XL"}})
    assert bad.status_code == 422
    r = put(api, "/api/v2/me/sizes", "dina", {"usual": {"alpha": "M", "eu_shoe": "42"}})
    assert r.status_code == 200
    usual = {s["system"]: s["usual"] for s in r.json()["systems"]}
    assert usual["alpha"]["label"] == "M" and usual["eu_shoe"]["code"] == "42" and usual["eu_clothing"] is None
    assert all(s["usual"] is None for s in api.get("/api/v2/me/sizes", "other").json()["systems"])  # private

    def names(**params):
        r = api.get("/api/v2/catalogue/products", "dina", params=params)
        assert r.status_code == 200, r.text
        return {i["name"] for i in r.json()["items"]}

    assert names(my_sizes="true") == {"Size tee", "Size sneaker"}  # the chino only comes in L/XL
    assert names(size="alpha:XL") == {"Size tee", "Size chino"}
    assert names(size="eu_shoe:36") == {"Size sneaker"}
    assert api.get("/api/v2/catalogue/products", params={"size": "M"}).status_code == 422  # needs system:code
    page = api.get("/api/v2/catalogue/products", params={"size": "alpha:XL", "limit": 1}).json()
    crossed = api.get("/api/v2/catalogue/products", params={"size": "alpha:S", "limit": 1,
                                                            "cursor": page["next_cursor"]})
    assert crossed.status_code == 422  # cursor bound to the size filter
    assert put(api, "/api/v2/me/sizes", "dina", {"usual": {"alpha": None}}).status_code == 200
    assert names(my_sizes="true") == {"Size sneaker"}


def test_cli_assign_sizes(api, shop, monkeypatch, settings):
    from wearhouse.bootstrap import cli
    monkeypatch.setattr(cli, "_runtime", lambda: (settings, api.app.state.engine, {}))
    base = ["assign-sizes", "--operator-issuer", api.issuer.issuer, "--batch", "2"]
    assert cli.main(base + ["--operator-subject", "nobody"]) == 2
    assert cli.main(base + ["--operator-subject", "editor-1"]) == 0
    assert codes(api.get(f"/api/v2/catalogue/products/{shop['chino']}").json()["sizes"]) == ALPHA_COMMON


# ============================================================== 2.1 sized commerce and units
def offer(api, pid, stock=3, size_stock=None, price=100_000):
    body = {"price_idr": price, "stock": stock, **({"size_stock": size_stock} if size_stock is not None else {})}
    return put(api, f"/api/v2/admin/commerce/offers/{pid}", "editor-1", body)


def cart(api, sub, pid, qty=1, size=None):
    return put(api, f"/api/v2/me/cart/{pid}", sub, {"quantity": qty, **({"size": size} if size else {})})


def checkout(api, sub, total, idem):
    return api.post("/api/v2/me/checkout", sub, json={"expected_total_idr": total}, idem=idem)


def size_stock(db, pid):
    return dict(query(db, "SELECT size_code, stock FROM sandbox_offer_size WHERE product_id = :p", p=pid))


def total_stock(db, pid):
    return query(db, "SELECT stock FROM sandbox_offer WHERE product_id = :p", p=pid)[0][0]


def test_per_size_stock_and_public_view(api, shop, clean_db):
    assign(api)
    r = offer(api, shop["tee"], stock=3, size_stock={"M": 0})
    assert r.status_code == 200, r.text
    assert {s["code"]: s["stock"] for s in r.json()["sizes"]} == {"XS": 3, "S": 3, "M": 0, "L": 3, "XL": 3, "XXL": 3}
    assert total_stock(clean_db, shop["tee"]) == 15  # 3 x 5 sizes
    pub = api.get(f"/api/v2/commerce/products/{shop['tee']}/offer").json()
    assert [(s["code"], s["in_stock"]) for s in pub["sizes"]][:4] == [("XS", True), ("S", True), ("M", False),
                                                                      ("L", True)]
    assert "stock" not in pub["sizes"][0] and pub["in_stock"] is True  # never counts
    bad = offer(api, shop["tee"], size_stock={"9XL": 1})
    assert bad.status_code == 422 and bad.json()["field_errors"][0]["code"] == "unknown_size"
    assert offer(api, shop["bag"], size_stock={"M": 1}).status_code == 422  # one-size product
    assert offer(api, shop["bag"], stock=4).status_code == 200
    assert api.get(f"/api/v2/commerce/products/{shop['bag']}/offer").json()["sizes"] == []
    bulk = api.post("/api/v2/admin/commerce/offers/bulk", "editor-1",
                    json={"rules": [{"slot": "footwear", "price_idr": 500_000, "stock": 2}]}).json()
    assert bulk["results"][0]["sized"] == 1
    assert size_stock(clean_db, shop["shoe"]) == {c: 2 for c in SHOE_COMMON}
    assert total_stock(clean_db, shop["shoe"]) == 20


def test_sized_cart_checkout_claim_and_cancel(api, shop, clean_db):
    assign(api)
    offer(api, shop["tee"], stock=5, size_stock={"M": 1})
    offer(api, shop["bag"], stock=5)
    assert cart(api, "dina", shop["tee"]).json()["field_errors"][0]["code"] == "size_required"
    assert cart(api, "dina", shop["tee"], size="9XL").status_code == 422
    assert cart(api, "dina", shop["bag"], size="M").json()["field_errors"][0]["code"] == "one_size"
    assert api.get("/api/v2/me/cart", "dina").json()["lines"] == []  # refusals change nothing
    cart(api, "dina", shop["tee"], 2, "M")
    c = cart(api, "dina", shop["tee"], 1, "L").json()
    assert [(x["size"]["code"], x["quantity"], x["available"]) for x in c["lines"]] == [("L", 1, True), ("M", 2, False)]
    short = checkout(api, "dina", 300_000, "co-size-0001")
    assert short.status_code == 409 and short.json()["code"] == "OUT_OF_STOCK" and "size M" in short.json()["message"]
    assert size_stock(clean_db, shop["tee"])["M"] == 1 and total_stock(clean_db, shop["tee"]) == 26  # nothing moved
    assert api.client.delete(f"/api/v2/me/cart/{shop['tee']}", params={"size": "M"},
                             headers=api.headers("dina")).status_code == 200
    cart(api, "dina", shop["tee"], 1, "M")
    cart(api, "dina", shop["bag"], 1)
    order = checkout(api, "dina", 300_000, "co-size-0002")
    assert order.status_code == 201, order.text
    lines = {(x["size"] or {}).get("code"): x for x in order.json()["lines"]}
    assert set(lines) == {"L", "M", None} and lines["M"]["size"]["label"] == "M"
    assert size_stock(clean_db, shop["tee"]) == {"XS": 5, "S": 5, "M": 0, "L": 4, "XL": 5, "XXL": 5}
    assert total_stock(clean_db, shop["tee"]) == 24
    staff = api.get("/api/v2/admin/commerce/orders", "inventory-1").json()["items"][0]
    assert {(x["size"] or {}).get("code") for x in staff["lines"]} == {"L", "M", None}
    units = {}
    for x in order.json()["lines"]:
        u = x["units"][0]
        units[(x["size"] or {}).get("code")] = u
    key = api.get(f"/api/v2/me/orders/{order.json()['id']}/units/{units['M']['unit_id']}/key", "dina").json()
    claimed = api.post("/api/v2/redemptions", "dina", json={"activation_key": key["activation_key"]},
                       idem="claim-size-0001")
    assert claimed.status_code == 201 and claimed.json()["size"] == {"system": "alpha", "code": "M", "label": "M"}
    assert query(clean_db, "SELECT count(*) FROM garment_unit WHERE size_code IS NOT NULL") == [(2,)]
    # a second order, cancelled, restocks its size
    cart(api, "dina", shop["tee"], 2, "XL")
    second = checkout(api, "dina", 200_000, "co-size-0003").json()
    assert size_stock(clean_db, shop["tee"])["XL"] == 3
    assert api.post(f"/api/v2/me/orders/{second['id']}/cancel", "dina").status_code == 200
    assert size_stock(clean_db, shop["tee"])["XL"] == 5 and total_stock(clean_db, shop["tee"]) == 24


def test_staff_issuance_with_size(api, shop, clean_db):
    assign(api)
    r = api.post("/api/v2/admin/unit-batches", "inventory-1", json={"product_id": shop["tee"], "size": "S"},
                 idem="issue-size-0001")
    assert r.status_code == 201, r.text
    bad = api.post("/api/v2/admin/unit-batches", "inventory-1", json={"product_id": shop["tee"], "size": "41"},
                   idem="issue-size-0002")
    assert bad.status_code == 422
    units = api.get("/api/v2/admin/units", "inventory-1", params={"product_id": shop["tee"]}).json()["items"]
    assert [u["size"] for u in units] == [{"system": "alpha", "code": "S", "label": "S"}]
    item = api.post("/api/v2/redemptions", "dina", json={"activation_key": r.json()["delivery"]["activation_key"]},
                    idem="claim-size-0002").json()
    assert item["size"]["code"] == "S"


# ============================================================== 3.1 wardrobe, export/erasure, recommendations
def wardrobe(api, sub="dina", **params):
    r = api.get("/api/v2/me/wardrobe/items", sub, params=params)
    assert r.status_code == 200, r.text
    return r.json()["items"]


def test_wardrobe_sizes_sort_filter_and_correction(api, shop):
    assign(api)
    unit = api.post("/api/v2/admin/unit-batches", "inventory-1", json={"product_id": shop["tee"], "size": "L"},
                    idem="issue-size-0101").json()
    bought = api.post("/api/v2/redemptions", "dina", json={"activation_key": unit["delivery"]["activation_key"]},
                      idem="claim-size-0101").json()
    mk = lambda name, slot, size=None: api.post("/api/v2/me/wardrobe/items", "dina", json={  # noqa: E731
        "name": name, "slot": slot, **({"size": size} if size else {})})
    small = mk("Small knit", "top", {"system": "alpha", "code": "S"}).json()
    shoes = mk("Loafers", "footwear", {"system": "eu_shoe", "code": "42"}).json()
    scarf = mk("Scarf", "accessory").json()
    assert mk("Odd", "top", {"system": "alpha", "code": "9XL"}).status_code == 422
    assert small["size"]["code"] == "S" and small["size_source"] == "owner" and scarf["size"] is None
    order = [i["name"] for i in wardrobe(api, sort="size")]
    assert order == ["Small knit", "Size tee", "Loafers", "Scarf"]  # S < L (alpha), then EU shoe, then unsized
    tee = next(i for i in wardrobe(api) if i["id"] == bought["id"])
    assert tee["size"]["code"] == "L" and tee["size_source"] == "purchase"
    assert [i["name"] for i in wardrobe(api, size="alpha:L")] == ["Size tee"]
    fix = api.client.patch(f"/api/v2/me/wardrobe/items/{bought['id']}", headers=api.headers("dina"),
                           json={"size": {"system": "alpha", "code": "XS"}})
    assert fix.status_code == 200 and fix.json()["size"]["code"] == "XS" and fix.json()["size_source"] == "owner"
    assert [i["name"] for i in wardrobe(api, sort="size")][:2] == ["Size tee", "Small knit"]  # XS now first
    reset = api.client.patch(f"/api/v2/me/wardrobe/items/{bought['id']}", headers=api.headers("dina"),
                             json={"size": None})
    assert reset.json()["size"]["code"] == "L" and reset.json()["size_source"] == "purchase"
    assert api.get("/api/v2/me/wardrobe/items", "dina", params={"sort": "colour"}).status_code == 422
    assert wardrobe(api, "other") == []


def test_usual_sizes_export_and_erasure(api, shop, clean_db):
    put(api, "/api/v2/me/sizes", "dina", {"usual": {"alpha": "M"}})
    doc = api.get("/api/v2/me/export", "dina").json()
    assert doc["sizes"] == {"usual_sizes": [{"system": "alpha", "code": "M"}]}
    handle = onboard(api, "dina")
    gone = api.client.request("DELETE", "/api/v2/me", headers=api.headers("dina"), json={"confirm": handle})
    assert gone.status_code == 204, gone.text
    assert query(clean_db, "SELECT count(*) FROM user_size_preference") == [(0,)]


def test_recommendations_respect_usual_sizes(api, shop):
    assign(api)
    put(api, f"/api/v2/admin/catalogue/products/{shop['chino']}/sizes", "editor-1",
        {"sizes": [{"system": "alpha", "code": c} for c in ("L", "XL")]})
    everything = api.get("/api/v2/me/recommendations/products", "dina").json()
    assert everything["sized_to_you"] is False and len(everything["items"]) == 4
    put(api, "/api/v2/me/sizes", "dina", {"usual": {"alpha": "M", "eu_shoe": "47"}})
    mine = api.get("/api/v2/me/recommendations/products", "dina").json()
    assert mine["sized_to_you"] is True and mine["model"]["mode"] == "heuristic_baseline"
    # the chino (no M) and the sneaker (common sizes stop at 45) drop; the tee fits; the one-size bag always passes
    assert {i["name"] for i in mine["items"]} == {"Size tee", "Size bag"}
