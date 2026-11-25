"""add-wearhouse-object-management 2.2 / 4.1: product media objects, generated placeholders, serving, facet cache.
Products are the data-free synthetic fixture (synthetic_only)."""
from __future__ import annotations

import uuid

import pytest

from conftest import counts, query, synthetic_product

pytestmark = [pytest.mark.postgres, pytest.mark.synthetic_only]
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


@pytest.fixture
def prod(api):
    api.grant("editor-1", "catalogue_editor")
    pid = api.post("/api/v2/admin/source-products", "editor-1", json=synthetic_product("0800000001")).json()["product_id"]
    return pid


def publish(api, pid):
    rev = api.get(f"/api/v2/admin/catalogue/products/{pid}", "editor-1").json()["revisions"][-1]["id"]
    assert api.post(f"/api/v2/admin/catalogue/products/{pid}/publish", "editor-1",
                    json={"revision_id": rev}).status_code == 200


def upload(api, pid, data=PNG, sub="editor-1", basis="own-photo"):
    params = {"alt": "Front", "rights_basis": basis} if basis else {"alt": "Front"}
    return api.client.post(f"/api/v2/admin/catalogue/products/{pid}/media", headers=api.headers(sub), content=data,
                           params=params)


def test_generate_upload_replace_and_remove(api, prod, clean_db):
    gen = api.post(f"/api/v2/admin/catalogue/products/{prod}/media/generate", "editor-1")
    assert gen.status_code == 201, gen.text
    g = gen.json()
    assert g["kind"] == "generated" and g["content_type"] == "image/svg+xml" and g["rights"]["basis"] == "generated"
    # draft product: hidden from the public, visible to staff
    assert api.get(g["url"]).status_code == 404
    staff = api.get(g["url"], "editor-1")
    assert staff.status_code == 200 and b"GENERATED PLACEHOLDER" in staff.content
    assert "no-store" in staff.headers["cache-control"]  # authenticated responses are never cached
    publish(api, prod)
    pub = api.get(g["url"])
    assert pub.status_code == 200 and pub.headers["content-type"].startswith("image/svg+xml")
    assert pub.headers["x-content-type-options"] == "nosniff" and "default-src 'none'" in pub.headers["content-security-policy"]
    assert api.get(g["url"], headers={"If-None-Match": pub.headers["etag"]}).status_code == 304
    # replace: upload a photo, put it first, remove the placeholder
    up = upload(api, prod)
    assert up.status_code == 201, up.text
    u = up.json()
    assert u["kind"] == "uploaded" and u["content_type"] == "image/png" and u["rights"]["basis"] == "own-photo"
    order = api.client.put(f"/api/v2/admin/catalogue/products/{prod}/media/order", headers=api.headers("editor-1"),
                           json={"media_ids": [u["id"], g["id"]]})
    assert [m["id"] for m in order.json()] == [u["id"], g["id"]]
    assert api.client.delete(f"/api/v2/admin/catalogue/media/{g['id']}", headers=api.headers("editor-1")).status_code == 204
    assert api.get(g["url"]).status_code == 404
    detail = api.get(f"/api/v2/catalogue/products/{prod}").json()
    assert [m["id"] for m in detail["media"]] == [u["id"]] and detail["media"][0]["kind"] == "uploaded"
    card = next(i for i in api.get("/api/v2/catalogue/products").json()["items"] if i["id"] == prod)
    assert card["thumbnail"] == u["url"]
    listed = api.get(f"/api/v2/admin/catalogue/products/{prod}/media", "editor-1", params={"include_removed": True}).json()
    assert {m["status"] for m in listed} == {"active", "removed"}
    alt = api.client.patch(f"/api/v2/admin/catalogue/media/{u['id']}", headers=api.headers("editor-1"),
                           json={"alt_text": "Front view"})
    assert alt.json()["alt_text"] == "Front view"
    actions = {a for (a,) in query(clean_db, "SELECT action FROM audit_event WHERE action LIKE 'catalogue.media%'")}
    assert {"catalogue.media_generated", "catalogue.media_uploaded", "catalogue.media_reordered",
            "catalogue.media_removed"} <= actions


def test_upload_validation_and_permissions(api, prod):
    svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
    bad = upload(api, prod, svg)
    assert bad.status_code == 422 and bad.json()["field_errors"][0]["code"] == "not_an_image"
    assert upload(api, prod, PNG + b"\x00" * (5 * 1024 * 1024)).status_code == 422
    assert upload(api, prod, basis=None).status_code == 422  # rights basis required
    assert upload(api, prod, sub="shopper").status_code == 403
    assert api.post(f"/api/v2/admin/catalogue/products/{prod}/media/generate", "shopper").status_code == 403
    assert api.get(f"/api/v2/admin/catalogue/products/{prod}/media", "shopper").status_code == 403
    assert api.post(f"/api/v2/admin/catalogue/products/{uuid.uuid4()}/media/generate", "editor-1").status_code == 404
    bad_order = api.client.put(f"/api/v2/admin/catalogue/products/{prod}/media/order", headers=api.headers("editor-1"),
                               json={"media_ids": [str(uuid.uuid4())]})
    assert bad_order.status_code == 422
    assert api.get(f"/api/v2/media/{uuid.uuid4()}").status_code == 404


def test_media_limit(api, prod, monkeypatch):
    import wearhouse.catalogue.publication as pub
    monkeypatch.setattr(pub, "MAX_ACTIVE_MEDIA", 2)
    for _ in range(2):
        assert api.post(f"/api/v2/admin/catalogue/products/{prod}/media/generate", "editor-1").status_code == 201
    full = api.post(f"/api/v2/admin/catalogue/products/{prod}/media/generate", "editor-1")
    assert full.status_code == 409 and full.json()["code"] == "MEDIA_FULL"


def test_bulk_generate_missing_is_idempotent(api, prod, clean_db):
    publish(api, prod)
    others = []
    for ext in ("0800000002", "0800000003"):
        pid = api.post("/api/v2/admin/source-products", "editor-1", json=synthetic_product(ext)).json()["product_id"]
        publish(api, pid)
        others.append(pid)
    draft = api.post("/api/v2/admin/source-products", "editor-1", json=synthetic_product("0800000004")).json()["product_id"]
    upload(api, others[0])  # already has media: skipped
    first = api.post("/api/v2/admin/catalogue/media/generate-missing", "editor-1", params={"limit": 1})
    assert first.json() == {"generated": 1, "more_remaining": True}
    second = api.post("/api/v2/admin/catalogue/media/generate-missing", "editor-1").json()
    assert second == {"generated": 1, "more_remaining": False}
    assert api.post("/api/v2/admin/catalogue/media/generate-missing", "editor-1").json()["generated"] == 0
    per_product = dict(query(clean_db, "SELECT product_id::text, count(*) FROM product_media GROUP BY 1"))
    assert per_product == {prod: 1, others[0]: 1, others[1]: 1} and draft not in per_product
    assert api.post("/api/v2/admin/catalogue/media/generate-missing", "shopper").status_code == 403


def test_facet_cache_invalidated_by_publish(api, prod):
    before = api.get("/api/v2/catalogue/facets").json()
    assert before["category"] == []
    publish(api, prod)
    after = api.get("/api/v2/catalogue/facets").json()  # publish in this process invalidates the cache
    assert after["category"] == [{"value": "T-shirt", "count": 1}]
    svc = api.services.publication
    svc._facets = (svc.monotonic(), {"category": [], "colour": [], "slot": []})  # simulate a cached stale value
    assert api.get("/api/v2/catalogue/facets").json()["category"] == []  # served from cache within TTL
    svc._facets = (svc.monotonic() - svc.FACET_TTL_S - 1, svc._facets[1])
    assert api.get("/api/v2/catalogue/facets").json()["category"] == [{"value": "T-shirt", "count": 1}]


def test_private_prefix_matches_whole_segments_only():
    from wearhouse.platform.http import is_private_path
    assert is_private_path("/api/v2/me") and is_private_path("/api/v2/me/cart") and is_private_path("/api/v2/admin/staff")
    assert not is_private_path("/api/v2/media/abc") and not is_private_path("/api/v2/catalogue/products")
    assert not is_private_path("/api/v2/menu")


def test_public_media_is_cacheable(api, prod):
    publish(api, prod)
    g = api.post(f"/api/v2/admin/catalogue/products/{prod}/media/generate", "editor-1").json()
    r = api.get(g["url"])
    assert r.headers["cache-control"] == "public, max-age=86400" and "pragma" not in r.headers
