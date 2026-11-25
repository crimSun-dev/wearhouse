"""5.1-5.5 source-preserving ingestion, serialized issuance, restricted delivery, reissue, public discovery."""
from __future__ import annotations

import base64
import copy
import re
from datetime import timedelta

import pytest

from conftest import Api, counts, issue, make_settings, query, redeem, synthetic_product
from wearhouse.ownership.domain import key_digest, normalize_key
from wearhouse.platform.clock import utcnow
from wearhouse.testing import create_test_app

pytestmark = [pytest.mark.postgres, pytest.mark.synthetic_only]
INGEST = "/api/v2/admin/source-products"
KEY_FORMAT = re.compile(r"^[A-Z2-7]{4}-[A-Z2-7]{4}-[A-Z2-7]{4}-[A-Z2-7]{4}$")


# ------------------------------------------------------------------ 5.1 ingestion
def test_identical_ingest_upserts_one_identity_and_one_revision(api, clean_db):
    api.grant("ed", "catalogue_editor")
    first = api.post(INGEST, "ed", json=synthetic_product())
    again = api.post(INGEST, "ed", json=synthetic_product())
    assert first.status_code == 201 and again.status_code == 200
    assert again.json() == {**first.json(), "product_created": False, "revision_created": False}
    assert counts(clean_db, "product", "product_revision", "catalogue_source") == \
        {"product": 1, "product_revision": 1, "catalogue_source": 1}
    assert query(clean_db, "SELECT external_id FROM product") == [("0000000001",)]


def test_changed_facts_create_new_revision_and_keep_prior(api, clean_db):
    api.grant("ed", "catalogue_editor")
    api.grant("inv", "inventory_manager")
    r1 = api.post(INGEST, "ed", json=synthetic_product()).json()
    unit = issue(api, r1["product_id"], sub="inv")
    r2 = api.post(INGEST, "ed", json=synthetic_product(product_name="Synthetic test tee (revised)")).json()
    assert r2["product_id"] == r1["product_id"] and r2["revision_no"] == 2 and r2["revision_created"]
    revs = query(clean_db, "SELECT revision_no, facts->'product_name'->>'value' FROM product_revision ORDER BY 1")
    assert revs == [(1, "Synthetic test tee"), (2, "Synthetic test tee (revised)")]
    assert unit["acquisition_revision_id"] == r1["revision_id"]
    assert query(clean_db, "SELECT acquisition_revision_id::text FROM garment_unit") == [(r1["revision_id"],)]
    assert api.get("/api/v2/items/" + unit["public_serial"]).json()["product"]["name"] == "Synthetic test tee (revised)"


@pytest.mark.parametrize("mutate,field", [
    (lambda b: b.pop("permission"), "body.permission"),
    (lambda b: b.pop("snapshot"), "body.snapshot"),
    (lambda b: b["snapshot"].update(sha256="NOT-A-CHECKSUM" + "0" * 50), "snapshot.sha256"),
    (lambda b: b["permission"].update(terms_url="http://insecure.example"), "permission.terms_url"),
    (lambda b: b.update(original_fields={}), "original_fields"),
    (lambda b: b["facts"].pop("category"), "facts.category"),
    (lambda b: b["facts"]["colour"].update(value="Waterproof Navy"), "facts.colour"),  # not the source value
    (lambda b: b["facts"].update(fabric={"value": "Gore-Tex", "source_field": "fabric"}), "facts.fabric"),
    (lambda b: b["annotations"].update(product_name={"value": "x", "origin": "curator"}), "annotations.product_name"),
    (lambda b: b.update(gtin={"value": "0000000001", "scheme": "gs1", "evidence": "made up"}), "gtin.value"),
    (lambda b: b.update(external_id=1), "body.external_id"),  # JSON number would lose leading zeros
])
def test_missing_provenance_or_unverified_facts_rejected(api, clean_db, mutate, field):
    api.grant("ed", "catalogue_editor")
    body = synthetic_product()
    mutate(body)
    r = api.post(INGEST, "ed", json=body)
    assert r.status_code == 422, r.text
    assert any(e["field"].endswith(field) or e["field"] == field for e in r.json()["field_errors"]), r.json()
    assert counts(clean_db, "product", "product_revision", "source_snapshot", "catalogue_source") == \
        {"product": 0, "product_revision": 0, "source_snapshot": 0, "catalogue_source": 0}


def test_legitimate_gtin_needs_evidence_and_check_digit(api, clean_db):
    api.grant("ed", "catalogue_editor")
    body = synthetic_product()
    body["gtin"] = {"value": "4006381333931", "scheme": "gs1", "evidence": "printed on manufacturer label scan 12"}
    assert api.post(INGEST, "ed", json=body).status_code == 201
    body2 = synthetic_product("0000000002")
    body2["gtin"] = {"value": "4006381333932", "scheme": "gs1", "evidence": "x"}  # bad check digit
    assert api.post(INGEST, "ed", json=body2).status_code == 422


# ------------------------------------------------------------------ 5.2 issuance
def test_independent_units_with_entropy_and_no_plaintext_storage(api, staff, clean_db):
    a = issue(api, staff["product_id"], idem="unit-a-0001")
    b = issue(api, staff["product_id"], idem="unit-b-0001")
    assert a["unit_id"] != b["unit_id"] and a["public_serial"] != b["public_serial"]
    ka, kb = a["delivery"]["activation_key"], b["delivery"]["activation_key"]
    assert ka != kb and KEY_FORMAT.fullmatch(ka) and KEY_FORMAT.fullmatch(kb)
    assert len(base64.b32decode(ka.replace("-", ""))) == 10  # 80 bits
    assert re.fullmatch(r"[a-z2-7]{26}", a["public_serial"])
    assert len(base64.b32decode(a["public_serial"].upper() + "======")) == 16  # 128 bits
    assert ka.replace("-", "") not in a["public_serial"].upper()  # public serial reveals no key material
    digests = {d for (d,) in query(clean_db, "SELECT key_digest FROM activation_credential")}
    assert digests == {key_digest(normalize_key(ka)), key_digest(normalize_key(kb))}
    dump = " ".join(str(r) for t in ("activation_credential", "issuance_delivery", "idempotency_record", "audit_event",
                                     "outbox_event", "ownership_event", "garment_unit")
                    for r in query(clean_db, f"SELECT row_to_json(x)::text FROM {t} x"))
    for k in (ka, kb, ka.replace("-", ""), kb.replace("-", "")):
        assert k not in dump and k.lower() not in dump
    claim = redeem(api, "customer-a", ka)
    assert claim.status_code == 201
    assert query(clean_db, "SELECT status FROM garment_unit WHERE id = :u", u=b["unit_id"]) == [("issued",)]


# ------------------------------------------------------------------ 5.3 restricted delivery
def test_lost_response_retry_returns_same_unit_and_key(api, staff, clean_db):
    first = issue(api, staff["product_id"], idem="lost-0001")
    retry = api.post("/api/v2/admin/unit-batches", "inventory-1", json={"product_id": staff["product_id"]},
                     idem="lost-0001")
    assert retry.status_code == 201 and retry.headers["Idempotent-Replayed"] == "true"
    assert retry.json() == first
    assert retry.headers["cache-control"] == "no-store"
    assert counts(clean_db, "garment_unit", "activation_credential") == {"garment_unit": 1, "activation_credential": 1}
    changed = api.post("/api/v2/admin/unit-batches", "inventory-1",
                       json={"product_id": staff["product_id"], "audience_user_id": api.user_id("x")}, idem="lost-0001")
    assert changed.status_code == 409 and changed.json()["code"] == "IDEMPOTENCY_KEY_REUSED"
    access = query(clean_db, "SELECT details->>'outcome', details->>'replayed' FROM audit_event "
                             "WHERE action = 'ownership.delivery_accessed' ORDER BY created_at")
    assert access == [("available", "false"), ("available", "true")]


def test_other_actor_cannot_retrieve_delivery(api, staff, clean_db):
    mine = issue(api, staff["product_id"], idem="shared-key-0001")
    api.grant("inventory-2", "inventory_manager")
    theirs = issue(api, staff["product_id"], idem="shared-key-0001", sub="inventory-2")
    assert theirs["unit_id"] != mine["unit_id"]  # actor-scoped key: a new operation, not A's delivery
    assert theirs["delivery"]["activation_key"] != mine["delivery"]["activation_key"]
    assert "delivery_id" not in mine and "_delivery_id" not in mine and "credential_id" not in mine


def test_expired_delivery_reports_unavailable_without_reminting(clean_db, issuer, api, staff):
    issue(api, staff["product_id"], idem="expiry-0001")
    later = {"now": utcnow() + timedelta(hours=25)}
    future = Api(create_test_app(make_settings(clean_db, issuer), issuer=issuer, clock=lambda: later["now"]), issuer)
    r = future.post("/api/v2/admin/unit-batches", "inventory-1", json={"product_id": staff["product_id"]},
                    idem="expiry-0001")
    assert r.status_code == 201
    assert r.json()["delivery"]["status"] == "expired" and "activation_key" not in str(r.json()["delivery"].get("activation_key"))
    assert r.json()["delivery"]["activation_key"] is None
    assert counts(clean_db, "garment_unit") == {"garment_unit": 1}
    assert future.services.issuance.purge_expired_deliveries() == 1
    assert query(clean_db, "SELECT ciphertext IS NULL, erase_reason FROM issuance_delivery") == [(True, "expired")]


def test_claim_erases_delivery(api, staff, clean_db):
    unit = issue(api, staff["product_id"], idem="claim-erase-1")
    assert redeem(api, "customer-a", unit["delivery"]["activation_key"]).status_code == 201
    r = api.post("/api/v2/admin/unit-batches", "inventory-1", json={"product_id": staff["product_id"]},
                 idem="claim-erase-1")
    assert r.json()["delivery"] == {"status": "unavailable", "reason": "claimed", "activation_key": None,
                                    "expires_at": None, "expired_at": None}
    assert query(clean_db, "SELECT ciphertext IS NULL, nonce IS NULL FROM issuance_delivery") == [(True, True)]


# ------------------------------------------------------------------ 5.4 reissue
def test_reissue_invalidates_old_key_and_preserves_unit(api, staff, clean_db):
    unit = issue(api, staff["product_id"])
    old_key = unit["delivery"]["activation_key"]
    r = api.post(f"/api/v2/admin/units/{unit['unit_id']}/reissue", "inventory-1", idem="reissue-0001")
    assert r.status_code == 201, r.text
    new = r.json()
    assert new["unit_id"] == unit["unit_id"] and new["public_serial"] == unit["public_serial"]
    new_key = new["delivery"]["activation_key"]
    assert new_key != old_key
    assert query(clean_db, "SELECT status, count(*) FROM activation_credential GROUP BY status ORDER BY 1") == \
        [("active", 1), ("revoked", 1)]
    assert redeem(api, "customer-a", old_key).json()["code"] == "INVALID_ACTIVATION_CODE"
    assert redeem(api, "customer-a", new_key).status_code == 201
    claimed = api.post(f"/api/v2/admin/units/{unit['unit_id']}/reissue", "inventory-1", idem="reissue-0002")
    assert claimed.status_code == 409 and claimed.json()["code"] == "UNIT_ALREADY_CLAIMED"
    audit = query(clean_db, "SELECT details::text FROM audit_event WHERE action = 'ownership.credential_reissued'")
    assert len(audit) == 1 and old_key not in audit[0][0] and new_key not in audit[0][0]


def test_reissue_unknown_unit_404(api, staff):
    r = api.post("/api/v2/admin/units/00000000-0000-4000-8000-000000000000/reissue", "inventory-1", idem="reissue-x1")
    assert r.status_code == 404


# ------------------------------------------------------------------ 5.5 public discovery
def test_public_lookup_is_discovery_only(api, staff, clean_db):
    unit = issue(api, staff["product_id"])
    before = counts(clean_db, "owned_item", "ownership_event", "attempt_event", "idempotency_record", "app_user")
    for _ in range(5):
        r = api.client.get("/api/v2/items/" + unit["public_serial"],
                           headers={"User-Agent": "facebookexternalhit/1.1", "Purpose": "prefetch"})
        assert r.status_code == 200
    assert counts(clean_db, "owned_item", "ownership_event", "attempt_event", "idempotency_record", "app_user") == before
    body = r.json()
    assert set(body) == {"public_serial", "product", "catalogue_status", "source"}
    text = r.text.lower()
    for leak in ("owner", "user_id", "credential", "attempt", "digest", "claimed", "activation", "unit_id"):
        assert leak not in text
    assert api.get("/api/v2/items/NOT-A-SERIAL").status_code == 404
    assert api.get("/api/v2/items/" + "a" * 26).status_code == 404


def test_public_serial_or_qr_url_cannot_claim(api, staff, clean_db):
    unit = issue(api, staff["product_id"])
    for attempt in (unit["public_serial"], unit["public_serial"].upper(),
                    "https://wearhouse.example/api/v2/items/" + unit["public_serial"]):
        r = redeem(api, "customer-a", attempt)
        assert r.status_code == 400 and r.json()["code"] == "INVALID_ACTIVATION_CODE"
    assert counts(clean_db, "owned_item") == {"owned_item": 0}
