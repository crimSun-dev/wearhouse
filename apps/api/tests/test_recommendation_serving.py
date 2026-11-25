"""complete-wearhouse-research-intelligence 5.1: artifact import (sha-verified, audited, all-or-nothing activation)
and the recommendation endpoints with truthful model modes. Synthetic products only (synthetic_only)."""
from __future__ import annotations

import hashlib
import uuid

import pytest

from conftest import issue, query, redeem, synthetic_product

pytestmark = [pytest.mark.postgres, pytest.mark.synthetic_only]
NS = "wearhouse-synthetic-test"


@pytest.fixture
def cat(api):
    api.grant("editor-1", "catalogue_editor")
    api.grant("inventory-1", "inventory_manager")
    ids = {}
    for ext, name in (("1100000001", "Black tee one"), ("1100000002", "Black tee two"), ("1100000003", "Black tee three")):
        pid = api.post("/api/v2/admin/source-products", "editor-1",
                       json=synthetic_product(ext, product_name=name)).json()["product_id"]
        rev = api.get(f"/api/v2/admin/catalogue/products/{pid}", "editor-1").json()["revisions"][-1]["id"]
        api.post(f"/api/v2/admin/catalogue/products/{pid}/publish", "editor-1", json={"revision_id": rev})
        ids[ext] = pid
    return ids


def artifact(mode="trained", model_hash="ab" * 32, tamper=False):
    body = ("article_id,rank,neighbour_article_id,score\n1100000001,1,1100000003,0.9\n1100000001,2,1100000002,0.5\n"
            "1100000001,3,9999999999,0.1\n").encode()
    manifest = {"kind": "similar_items", "name": "bpr-item-factors-cosine", "version": "t1", "mode": mode,
                "model_hash": model_hash, "source_namespace": NS,
                "files": {"neighbours.csv": hashlib.sha256(body + (b"x" if tamper else b"")).hexdigest()}}
    return manifest, body


def editor(api):
    return api.services.identity.operator_principal(issuer=api.issuer.issuer, subject="editor-1")


def test_baselines_declare_heuristic_mode(api, cat):
    r = api.get(f"/api/v2/catalogue/products/{cat['1100000001']}/similar")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["model"]["mode"] == "heuristic_baseline" and body["model"]["trained_artifact"] is None
    assert {i["id"] for i in body["items"]} == {cat["1100000002"], cat["1100000003"]}
    me = api.get("/api/v2/me/recommendations/products", "shopper").json()
    assert me["model"]["mode"] == "heuristic_baseline" and len(me["items"]) == 3
    assert api.get(f"/api/v2/catalogue/products/{uuid.uuid4()}/similar").status_code == 404


def test_imported_trained_artifact_is_declared_with_hash(api, cat, clean_db):
    manifest, body = artifact()
    out = api.services.recommendations.import_similar_items(editor(api), manifest, body)
    assert out["rows"] == 2 and out["skipped_unknown_products"] == 1  # unknown product ids are skipped, counted
    r = api.get(f"/api/v2/catalogue/products/{cat['1100000001']}/similar").json()
    assert r["model"]["mode"] == "trained" and r["model"]["trained_artifact"] == "ab" * 32
    assert [i["id"] for i in r["items"]] == [cat["1100000003"], cat["1100000002"]]  # artifact order kept
    cold = api.get(f"/api/v2/catalogue/products/{cat['1100000002']}/similar").json()
    assert cold["model"]["mode"] == "heuristic_baseline" and cold["model"]["fallback"]
    assert query(clean_db, "SELECT count(*) FROM audit_event WHERE action = 'recommendations.artifact_activated'") == [(1,)]
    # a second import replaces the active artifact (one active per kind)
    api.services.recommendations.import_similar_items(editor(api), *artifact(mode="heuristic_baseline", model_hash=None))
    assert query(clean_db, "SELECT count(*) FROM recommendation_artifact WHERE active") == [(1,)]
    again = api.get(f"/api/v2/catalogue/products/{cat['1100000001']}/similar").json()
    assert again["model"]["mode"] == "heuristic_baseline" and again["model"]["name"] == "bpr-item-factors-cosine"


def test_tampered_or_dishonest_artifacts_are_refused(api, cat, clean_db):
    from wearhouse.platform.errors import ApiError
    svc = api.services.recommendations
    with pytest.raises(ApiError) as tampered:
        svc.import_similar_items(editor(api), *artifact(tamper=True))
    assert tampered.value.field_errors[0].code == "checksum_mismatch"
    with pytest.raises(ApiError) as no_hash:
        svc.import_similar_items(editor(api), *artifact(model_hash=None))  # "trained" without a model hash
    assert no_hash.value.field_errors[0].field == "manifest.model_hash"
    api.get("/api/v2/me", "customer-1")  # an ordinary account without catalogue capability
    customer = api.services.identity.operator_principal(issuer=api.issuer.issuer, subject="customer-1")
    with pytest.raises(ApiError) as forbidden:
        svc.import_similar_items(customer, *artifact())
    assert forbidden.value.status == 403
    assert query(clean_db, "SELECT count(*) FROM recommendation_artifact") == [(0,)]


def test_personal_recommendations_exclude_owned(api, cat):
    unit = issue(api, cat["1100000002"])
    assert redeem(api, "owner", unit["delivery"]["activation_key"]).status_code == 201
    items = {i["id"] for i in api.get("/api/v2/me/recommendations/products", "owner").json()["items"]}
    assert cat["1100000002"] not in items and items == {cat["1100000001"], cat["1100000003"]}


def test_cli_import_recommendations(api, cat, clean_db, tmp_path, monkeypatch, settings):
    import json

    from wearhouse.bootstrap import cli
    monkeypatch.setattr(cli, "_runtime", lambda: (settings, api.app.state.engine, {}))
    manifest, body = artifact(tamper=True)
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (tmp_path / "neighbours.csv").write_bytes(body)
    args = ["import-recommendations", "--artifact", str(tmp_path), "--operator-issuer", api.issuer.issuer,
            "--operator-subject", "editor-1"]
    assert cli.main(args) == 2  # tampered: refused, nothing written
    manifest, body = artifact()
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    assert cli.main(args[:-1] + ["nobody"]) == 2  # unknown operator
    assert query(clean_db, "SELECT count(*) FROM recommendation_artifact") == [(0,)]
    assert cli.main(args) == 0
    assert query(clean_db, "SELECT mode, active FROM recommendation_artifact") == [("trained", True)]


# ============================================================== complete-wearhouse-tdd 3.1
def publish(api, ext, name, category, colour, slot):
    body = synthetic_product(ext, product_name=name, category=category, colour=colour)
    body["annotations"] = {"slot": {"value": slot, "origin": "rule", "note": "hm-articles@1"}}
    pid = api.post("/api/v2/admin/source-products", "editor-1", json=body).json()["product_id"]
    rev = api.get(f"/api/v2/admin/catalogue/products/{pid}", "editor-1").json()["revisions"][-1]["id"]
    api.post(f"/api/v2/admin/catalogue/products/{pid}/publish", "editor-1", json={"revision_id": rev})
    return pid


def test_hide_owned_and_duplicate_rerank(api):
    api.grant("editor-1", "catalogue_editor")
    api.grant("inventory-1", "inventory_manager")
    chino = publish(api, "1300000001", "Beige chino", "Trousers", "Beige", "bottom")
    owned = publish(api, "1300000002", "Black tee", "T-shirt", "Black", "top")
    dup = publish(api, "1300000003", "Another black tee", "T-shirt", "Black", "top")  # newest
    assert redeem(api, "owner", issue(api, owned)["delivery"]["activation_key"]).status_code == 201
    names = lambda **p: [i["id"] for i in api.get("/api/v2/catalogue/products", "owner", params=p).json()["items"]]  # noqa: E731
    assert owned in names() and owned not in names(hide_owned="true")
    assert api.get("/api/v2/catalogue/products", params={"hide_owned": "true"}).status_code == 401
    r = api.get("/api/v2/me/recommendations/products", "owner").json()
    order = [i["id"] for i in r["items"]]
    assert owned not in order and order.index(chino) < order.index(dup)  # the duplicate is pushed below
    by = {i["id"]: i["rerank"] for i in r["items"]}
    assert by[dup]["duplicate"] == 1.0 and by[chino]["duplicate"] == 0.0 and by[chino]["completion"] > 0
    assert r["rerank"] == {"name": "completion-duplicate (heuristic Eq. 3)", "lambda_c": 0.5, "lambda_d": 0.5,
                           "cold_start": False}
    cold = api.get("/api/v2/me/recommendations/products", "newcomer").json()
    assert cold["rerank"]["cold_start"] is True


def test_ops_summary_is_admin_only_counts(api):
    api.grant("boss", "admin")
    api.grant("mod", "moderator")
    assert api.get("/api/v2/admin/ops", "mod").status_code == 403
    assert api.get("/api/v2/admin/ops", "someone").status_code == 403
    out = api.get("/api/v2/admin/ops", "boss")
    assert out.status_code == 200, out.text
    body = out.json()
    assert body["window_hours"] == 24 and body["model_mode"] == "heuristic_baseline" and body["schema_head"]
    assert set(body) >= {"claim_attempts", "claim_failures", "outbox_pending", "import_jobs_running",
                         "rate_limited_since_start"}
