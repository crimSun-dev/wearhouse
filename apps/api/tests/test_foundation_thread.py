"""Integrated ownership thread (design D8): staff ingest -> issue -> public lookup -> private claim -> owner read,
with restart, customer-B negatives and DB/event-count assertions.

`test_thread_synthetic` uses the data-free synthetic product (lower-level proof, labelled synthetic_only).
`test_thread_source_backed` runs only when apps/api/fixtures/source-products/manifest.json is `permitted`;
until then it is reported SKIPPED and the source-backed readiness gate stays PENDING.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from conftest import Api, counts, create_test_app, issue, query, redeem, synthetic_product

pytestmark = pytest.mark.postgres
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "source-products"
# A permitted fixture lives in the git-ignored local/ folder (Kaggle rules: no redistribution; see
# tools/make_hm_fixture.py). Without it, the committed PENDING manifest makes the source-backed test skip.
MANIFEST = FIXTURES / "local" / "manifest.json" if (FIXTURES / "local" / "manifest.json").exists()     else FIXTURES / "manifest.json"
OWNERSHIP_TABLES = ("garment_unit", "activation_credential", "owned_item", "ownership_event", "outbox_event",
                    "attempt_event", "issuance_delivery")


def run_thread(api: Api, settings, issuer, product_body: dict, db) -> dict:
    api.grant("editor-1", "catalogue_editor")
    api.grant("inventory-1", "inventory_manager")
    r = api.post("/api/v2/admin/source-products", "editor-1", json=product_body)
    assert r.status_code == 201, r.text
    product_id = r.json()["product_id"]

    unit = issue(api, product_id, idem="thread-issue-0001")
    key, serial = unit["delivery"]["activation_key"], unit["public_serial"]
    assert unit["delivery"]["status"] == "available"

    before = counts(db, *OWNERSHIP_TABLES)
    for _ in range(3):  # anonymous public lookup / link preview
        pub = api.get(f"/api/v2/items/{serial}")
        assert pub.status_code == 200
        assert pub.json()["product"]["id"] == product_id
    assert counts(db, *OWNERSHIP_TABLES) == before, "public lookup must create no ownership rows"

    claim = redeem(api, "customer-a", key, idem="thread-claim-0001")
    assert claim.status_code == 201, claim.text
    item = claim.json()
    assert item["product"]["category"] == product_body["facts"]["category"]["value"]

    a_list = api.get("/api/v2/me/items", "customer-a").json()["items"]
    assert [i["id"] for i in a_list] == [item["id"]]
    assert api.get(f"/api/v2/me/items/{item['id']}", "customer-a").status_code == 200

    b_claim = redeem(api, "customer-b", key, idem="thread-claim-b-0001")
    assert b_claim.status_code == 400 and b_claim.json()["code"] == "INVALID_ACTIVATION_CODE"
    b_read = api.get(f"/api/v2/me/items/{item['id']}", "customer-b")
    assert b_read.status_code == 404 and b_read.json()["code"] == "NOT_FOUND"
    assert api.get("/api/v2/me/items", "customer-b").json()["items"] == []

    # restart: a brand-new app process state against the same database
    restarted = Api(create_test_app(settings, issuer=issuer), issuer)
    after = restarted.get("/api/v2/me/items", "customer-a").json()["items"]
    assert [i["id"] for i in after] == [item["id"]]
    replay = redeem(restarted, "customer-a", key, idem="thread-claim-0001")
    assert replay.status_code == 201 and replay.json() == item and replay.headers["Idempotent-Replayed"] == "true"

    c = counts(db, *OWNERSHIP_TABLES)
    assert c["garment_unit"] == 1 and c["owned_item"] == 1
    assert c["ownership_event"] == 1  # exactly one claim event
    actor_attempts = query(db, "SELECT count(*) FROM attempt_event WHERE scope = 'actor'")[0][0]
    assert actor_attempts == 2  # A's claim and B's rejected claim; the post-restart replay reserved nothing
    assert c["issuance_delivery"] == 1
    return {"item": item, "counts": c}


@pytest.mark.synthetic_only
def test_thread_synthetic(api, settings, issuer, clean_db):
    result = run_thread(api, settings, issuer, synthetic_product(), clean_db)
    assert result["item"]["acquisition"]["source_namespace"] == "wearhouse-synthetic-test"


@pytest.mark.source_backed
def test_thread_source_backed(api, settings, issuer, clean_db):
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if manifest.get("status") != "permitted" or not manifest.get("records"):
        pytest.skip("source-backed readiness gate PENDING: no permitted H&M fixture in "
                    "apps/api/fixtures/source-products (see its README)")
    body = json.loads((MANIFEST.parent / manifest["request_file"]).read_text(encoding="utf-8"))
    subset = (MANIFEST.parent / manifest["snapshot"]["file"]).read_bytes()
    assert hashlib.sha256(subset).hexdigest() == manifest["snapshot"]["sha256"]  # fixture file untouched
    lines = subset.decode("utf-8").splitlines(keepends=True)[1:]
    assert sorted(hashlib.sha256(ln.encode()).hexdigest() for ln in lines) ==         sorted(r["row_sha256"] for r in manifest["records"])  # rows byte-for-byte as in the original file
    assert body["external_id"] == manifest["records"][0]["external_id"] and body["external_id"].startswith("0")
    result = run_thread(api, settings, issuer, body, clean_db)
    assert result["item"]["acquisition"]["source_namespace"] == body["source"]["namespace"]
