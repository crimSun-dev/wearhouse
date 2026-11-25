"""publish-wearhouse-catalogue 2.2 / 3.1 / 3.2 / 4.1: import jobs, publication lifecycle, collections, public browse.

All rows are SYNTHETIC rows in the H&M articles.csv column format (namespace hm-format-synthetic). They are not
H&M data and never count as the source-backed proof.
"""
from __future__ import annotations

import csv
import io
import uuid

import pytest

from conftest import issue, query, redeem, synthetic_product

pytestmark = [pytest.mark.postgres, pytest.mark.synthetic_only]

COLUMNS = ["article_id", "product_code", "prod_name", "product_type_name", "product_group_name",
           "colour_group_name", "department_name", "garment_group_name", "detail_desc"]
CONTEXT = {
    "source": {"namespace": "hm-format-synthetic", "name": "Synthetic rows in H&M articles.csv format",
               "url": "https://wearhouse.invalid/hm-format-synthetic"},
    "snapshot": {"sha256": "c" * 64, "file_name": "articles-synthetic.csv", "acquired_on": "2026-11-25"},
    "permission": {"basis": "synthetic-test-fixture", "scope": "automated tests only", "accepted_on": "2026-11-25",
                   "accepted_by": "wearhouse test suite", "terms_url": "https://wearhouse.invalid/terms"},
}
BASE = {
    "0100000001": ("Basic tee", "T-shirt", "Garment Upper body", "Black", "Plain jersey tee."),
    "0100000002": ("Linen dress", "Dress", "Garment Full body", "Black", "Sleeveless linen dress."),
    "0100000003": ("Wool coat", "Coat", "Garment Upper body", "Grey", "Long coat in wool blend."),
    "0100000004": ("Cargo trousers", "Trousers", "Garment Lower body", "Beige", "Relaxed cargo trousers."),
}


def csv_text(rows: dict[str, tuple], extra: list[list[str]] | None = None) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(COLUMNS)
    for aid, (name, ptype, group, colour, desc) in rows.items():
        w.writerow([aid, aid[:7], name, ptype, group, colour, "Synthetic dept", "Synthetic group", desc])
    for r in extra or []:
        w.writerow(r)
    return buf.getvalue()


def run_import(api, text, sub="editor-1", **over):
    return api.post("/api/v2/admin/catalogue/import-jobs", sub, json={**CONTEXT, "csv": text, **over})


@pytest.fixture
def editor(api):
    api.grant("editor-1", "catalogue_editor")
    api.grant("inventory-1", "inventory_manager")
    return "editor-1"


def imported(api, rows=BASE) -> dict[str, dict]:
    r = run_import(api, csv_text(rows))
    assert r.status_code == 201, r.text
    return {row["external_id"]: row for row in r.json()["rows"]}


def latest_revision_id(api, pid):
    return api.get(f"/api/v2/admin/catalogue/products/{pid}", "editor-1").json()["revisions"][-1]["id"]


def publish(api, pid, rev=None):
    r = api.post(f"/api/v2/admin/catalogue/products/{pid}/publish", "editor-1",
                 json={"revision_id": rev or latest_revision_id(api, pid)})
    assert r.status_code == 200, r.text
    return r.json()


def browse(api, **params):
    r = api.get("/api/v2/catalogue/products", params=params)
    assert r.status_code == 200, r.text
    return r.json()


# ============================================================== 2.2 import jobs
def test_mixed_rows_are_processed_independently(api, editor, clean_db):
    bad = ["0100000009", "0100000", "Mystery", "", "Garment Upper body", "Red", "", "", ""]
    r = run_import(api, csv_text(BASE, [bad]))
    assert r.status_code == 201, r.text
    job = r.json()
    assert job["status"] == "completed" and job["row_count"] == 5
    assert job["totals"] == {"created": 4, "revised": 0, "unchanged": 0, "rejected": 1}
    rejected = [x for x in job["rows"] if x["outcome"] == "rejected"]
    assert rejected[0]["external_id"] == "0100000009" and rejected[0]["errors"][0]["field"] == "product_type_name"
    assert api.get(f"/api/v2/admin/catalogue/import-jobs/{job['id']}", "editor-1").json()["totals"] == job["totals"]
    # Drafts: products exist, nothing is public yet; leading zeros preserved.
    assert query(clean_db, "SELECT count(*) FROM product WHERE publication_state = 'draft'") == [(4,)]
    assert browse(api)["items"] == []
    assert query(clean_db, "SELECT external_id FROM product ORDER BY external_id")[0] == ("0100000001",)



def test_rerun_is_unchanged_and_changed_facts_revise(api, editor, clean_db):
    imported(api)
    again = run_import(api, csv_text(BASE)).json()
    assert again["totals"] == {"created": 0, "revised": 0, "unchanged": 4, "rejected": 0}
    changed = dict(BASE)
    changed["0100000001"] = ("Basic tee v2", *BASE["0100000001"][1:])
    third = run_import(api, csv_text(changed)).json()
    assert third["totals"] == {"created": 0, "revised": 1, "unchanged": 3, "rejected": 0}
    row = next(x for x in third["rows"] if x["outcome"] == "revised")
    assert row["revision_no"] == 2
    assert query(clean_db, "SELECT count(*) FROM product") == [(4,)]
    assert query(clean_db, "SELECT count(*) FROM product_revision") == [(5,)]


@pytest.mark.parametrize("text,code", [
    ("article_id,prod_name\n0001,Tee\n", "missing_columns"),
    ("", "empty"),
    (",".join(COLUMNS) + "\n", "empty"),
    (",".join(COLUMNS) + "\n0001,0000001,Tee\n", "malformed"),
    (",".join(COLUMNS) + '\n"0001,unterminated\n', "malformed"),
])
def test_malformed_csv_is_rejected_before_processing(api, editor, clean_db, text, code):
    r = run_import(api, text)
    assert r.status_code == 422, r.text
    assert r.json()["field_errors"][0]["code"] == code
    assert query(clean_db, "SELECT count(*) FROM catalogue_import_job") == [(0,)]
    assert query(clean_db, "SELECT count(*) FROM product") == [(0,)]


def test_row_limit_and_unknown_mapping(api, editor, clean_db, monkeypatch):
    import wearhouse.catalogue.publication as pub
    monkeypatch.setattr(pub, "MAX_ROWS", 3)
    r = run_import(api, csv_text(BASE))
    assert r.status_code == 422 and r.json()["field_errors"][0]["code"] == "too_many_rows"
    monkeypatch.undo()
    r = run_import(api, csv_text(BASE), mapping="made-up@9")
    assert r.status_code == 422 and r.json()["field_errors"][0]["code"] == "unknown_mapping"
    bad_ctx = {**CONTEXT["source"], "url": "http://insecure.example"}
    r = run_import(api, csv_text(BASE), source=bad_ctx)
    assert r.status_code == 422 and r.json()["field_errors"][0]["field"] == "source.url"
    assert query(clean_db, "SELECT count(*) FROM product") == [(0,)]


def test_customer_cannot_import_or_read_jobs(api, editor, clean_db):
    r = run_import(api, csv_text(BASE), sub="shopper")
    assert r.status_code == 403
    assert api.get(f"/api/v2/admin/catalogue/import-jobs/{uuid.uuid4()}", "shopper").status_code == 403
    assert api.get("/api/v2/admin/catalogue/review", "shopper").status_code == 403
    assert query(clean_db, "SELECT count(*) FROM catalogue_import_job") == [(0,)]


# ============================================================== 3.1 publication
def test_publish_review_and_newer_revision(api, editor, clean_db):
    rows = imported(api)
    tee = rows["0100000001"]["product_id"]
    queue = api.get("/api/v2/admin/catalogue/review", "editor-1").json()
    assert {q["external_id"] for q in queue} == set(BASE)
    assert api.get(f"/api/v2/catalogue/products/{tee}").status_code == 404  # draft invisible
    rev1 = latest_revision_id(api, tee)
    out = publish(api, tee, rev1)
    assert out["publication_state"] == "published" and out["published_revision_id"] == rev1
    assert api.get(f"/api/v2/catalogue/products/{tee}").json()["facts"]["product_name"]["value"] == "Basic tee"
    assert tee not in {q["product_id"] for q in api.get("/api/v2/admin/catalogue/review", "editor-1").json()}
    # A later import revises it: back in the review queue, public still shows revision 1.
    changed = dict(BASE)
    changed["0100000001"] = ("Basic tee v2", *BASE["0100000001"][1:])
    run_import(api, csv_text(changed))
    item = next(q for q in api.get("/api/v2/admin/catalogue/review", "editor-1").json() if q["product_id"] == tee)
    assert item["latest_revision_no"] == 2 and item["published_revision_no"] == 1
    assert api.get(f"/api/v2/catalogue/products/{tee}").json()["revision_no"] == 1
    publish(api, tee)
    detail = api.get(f"/api/v2/catalogue/products/{tee}").json()
    assert detail["revision_no"] == 2 and detail["facts"]["product_name"]["value"] == "Basic tee v2"
    staff = api.get(f"/api/v2/admin/catalogue/products/{tee}", "editor-1").json()
    assert [r["revision_no"] for r in staff["revisions"]] == [1, 2]  # revision 1 stays auditable
    actions = [a for (a,) in query(clean_db, "SELECT action FROM audit_event WHERE target_id = :t ORDER BY id",
                                   t=tee)]
    assert actions.count("catalogue.product_published") == 2


def test_publish_rejects_foreign_revision_and_customers(api, editor):
    rows = imported(api)
    tee, dress = rows["0100000001"]["product_id"], rows["0100000002"]["product_id"]
    r = api.post(f"/api/v2/admin/catalogue/products/{tee}/publish", "editor-1",
                 json={"revision_id": latest_revision_id(api, dress)})
    assert r.status_code == 422 and r.json()["field_errors"][0]["code"] == "unknown_revision"
    r = api.post(f"/api/v2/admin/catalogue/products/{tee}/publish", "shopper",
                 json={"revision_id": latest_revision_id(api, tee)})
    assert r.status_code == 403
    assert api.post(f"/api/v2/admin/catalogue/products/{tee}/retire", "shopper").status_code == 403
    assert api.post(f"/api/v2/admin/catalogue/products/{uuid.uuid4()}/retire", "editor-1").status_code == 404


def test_retire_keeps_owned_items_and_discovery(api, editor):
    r = api.post("/api/v2/admin/source-products", "editor-1", json=synthetic_product())
    pid = r.json()["product_id"]
    publish(api, pid)
    unit = issue(api, pid)
    assert redeem(api, "owner-1", unit["delivery"]["activation_key"]).status_code == 201
    assert any(i["id"] == pid for i in browse(api)["items"])
    out = api.post(f"/api/v2/admin/catalogue/products/{pid}/retire", "editor-1").json()
    assert out["publication_state"] == "retired"
    assert all(i["id"] != pid for i in browse(api)["items"])
    assert api.get(f"/api/v2/catalogue/products/{pid}").status_code == 404
    assert len(api.get("/api/v2/me/items", "owner-1").json()["items"]) == 1  # owned item remains
    lookup = api.get(f"/api/v2/items/{unit['public_serial']}")
    assert lookup.status_code == 200 and lookup.json()["catalogue_status"] == "retired"
    r = api.post("/api/v2/admin/unit-batches", "inventory-1", json={"product_id": pid}, idem="i-" + uuid.uuid4().hex)
    assert r.status_code == 409  # issuance stops for retired products
    publish(api, pid)  # republishing brings it back
    assert any(i["id"] == pid for i in browse(api)["items"])


def test_discovery_presents_published_revision(api, editor):
    r = api.post("/api/v2/admin/source-products", "editor-1", json=synthetic_product())
    pid = r.json()["product_id"]
    publish(api, pid)
    unit = issue(api, pid)
    api.post("/api/v2/admin/source-products", "editor-1",
             json=synthetic_product(product_name="Draft rename not yet published"))
    view = api.get(f"/api/v2/items/{unit['public_serial']}").json()
    assert view["product"]["name"] == "Synthetic test tee"


# ============================================================== 3.2 collections
def test_collections_order_retired_and_unknown(api, editor):
    rows = imported(api)
    ids = [rows[k]["product_id"] for k in ("0100000003", "0100000001", "0100000002")]
    for pid in ids:
        publish(api, pid)
    r = api.client.put("/api/v2/admin/catalogue/collections/autumn-picks", headers=api.headers("editor-1"),
                       json={"title": "Autumn picks", "product_ids": ids})
    assert r.status_code == 200, r.text
    public = api.get("/api/v2/catalogue/collections/autumn-picks").json()
    assert [i["id"] for i in public["items"]] == ids and public["title"] == "Autumn picks"
    # Reorder + rename via PUT.
    api.client.put("/api/v2/admin/catalogue/collections/autumn-picks", headers=api.headers("editor-1"),
                   json={"title": "Autumn edit", "product_ids": list(reversed(ids))})
    assert [i["id"] for i in api.get("/api/v2/catalogue/collections/autumn-picks").json()["items"]] == ids[::-1]
    api.post(f"/api/v2/admin/catalogue/products/{ids[0]}/retire", "editor-1")
    assert ids[0] not in [i["id"] for i in api.get("/api/v2/catalogue/collections/autumn-picks").json()["items"]]
    staff = api.get("/api/v2/admin/catalogue/collections", "editor-1").json()[0]
    assert {i["id"]: i["publication_state"] for i in staff["items"]}[ids[0]] == "retired"
    assert api.get("/api/v2/catalogue/collections").json()[0]["title"] == "Autumn edit"
    assert api.get("/api/v2/catalogue/collections/nope").status_code == 404
    bad = api.client.put("/api/v2/admin/catalogue/collections/x", headers=api.headers("editor-1"),
                         json={"title": "", "product_ids": [str(uuid.uuid4())]})
    assert bad.status_code == 422
    unknown = api.client.put("/api/v2/admin/catalogue/collections/new-one", headers=api.headers("editor-1"),
                             json={"title": "New", "product_ids": [str(uuid.uuid4())]})
    assert unknown.status_code == 422 and unknown.json()["field_errors"][0]["code"] == "unknown_product"
    shopper = api.client.put("/api/v2/admin/catalogue/collections/new-one", headers=api.headers("shopper"),
                             json={"title": "New", "product_ids": []})
    assert shopper.status_code == 403
    assert api.client.delete("/api/v2/admin/catalogue/collections/autumn-picks",
                             headers=api.headers("editor-1")).status_code == 204
    assert api.get("/api/v2/catalogue/collections/autumn-picks").status_code == 404


# ============================================================== 4.1 browse
def test_search_filters_facets_and_literal_wildcards(api, editor):
    rows = imported(api)
    for k in ("0100000001", "0100000002", "0100000003"):
        publish(api, rows[k]["product_id"])  # trousers stay draft
    assert {i["name"] for i in browse(api, q="dress")["items"]} == {"Linen dress"}
    assert {i["name"] for i in browse(api, q="DRESS", colour="Black")["items"]} == {"Linen dress"}
    assert {i["name"] for i in browse(api, colour="Black")["items"]} == {"Basic tee", "Linen dress"}
    assert {i["name"] for i in browse(api, slot="outer")["items"]} == {"Wool coat"}
    assert {i["name"] for i in browse(api, q="wool blend")["items"]} == {"Wool coat"}  # description searched
    assert browse(api, q="%")["items"] == [] and browse(api, q="_")["items"] == []
    assert browse(api, q="cargo")["items"] == []  # draft not searchable
    facets = api.get("/api/v2/catalogue/facets").json()
    assert {f["value"]: f["count"] for f in facets["colour"]} == {"Black": 2, "Grey": 1}
    assert {f["value"]: f["count"] for f in facets["category"]} == {"T-shirt": 1, "Dress": 1, "Coat": 1}
    assert "bottom" not in {f["value"] for f in facets["slot"]}
    assert [i["name"] for i in browse(api, sort="name")["items"]] == ["Basic tee", "Linen dress", "Wool coat"]
    assert api.get("/api/v2/catalogue/products", params={"sort": "price"}).status_code == 422
    assert api.get("/api/v2/catalogue/products", params={"limit": 0}).status_code == 422


def test_pagination_is_stable_when_products_publish_mid_paging(api, editor):
    rows = {f"02000000{i:02d}": (f"Tee {i:02d}", "T-shirt", "Garment Upper body", "White", "") for i in range(7)}
    ids = imported(api, rows)
    for aid in sorted(rows)[:6]:
        publish(api, ids[aid]["product_id"])
    for sort in ("newest", "name"):
        seen, cursor = [], None
        first = browse(api, limit=2, sort=sort)
        seen += [i["id"] for i in first["items"]]
        cursor = first["next_cursor"]
        if sort == "newest":
            publish(api, ids[sorted(rows)[6]]["product_id"])  # newest product appears after page 1
        while cursor:
            page = browse(api, limit=2, sort=sort, cursor=cursor)
            seen += [i["id"] for i in page["items"]]
            cursor = page["next_cursor"]
        assert len(seen) == len(set(seen))  # no repeats
        expected = 6 if sort == "newest" else 7
        assert len(seen) == expected  # no skips (the late newest item belongs before page 1)
    tampered = first["next_cursor"][:-2] + "AA"
    assert api.get("/api/v2/catalogue/products", params={"cursor": tampered}).status_code == 422
    other = api.get("/api/v2/catalogue/products", params={"cursor": first["next_cursor"], "q": "tee"})
    assert other.status_code == 422  # cursor bound to its filter


def test_detail_labels_annotations_and_hides_restricted_media(api, editor):
    body = synthetic_product("0300000001")
    body["annotations"] = {"slot": {"value": "top", "origin": "rule", "note": "hm-articles@1"}}
    body["media"] = [{"uri": "https://media.wearhouse.invalid/public.jpg", "version": "1",
                      "rights": {"basis": "synthetic", "public_display": True}},
                     {"uri": "https://media.wearhouse.invalid/restricted.jpg", "version": "1",
                      "rights": {"basis": "synthetic", "public_display": False}}]
    r = api.post("/api/v2/admin/source-products", "editor-1", json=body)
    assert r.status_code == 201, r.text
    pid = r.json()["product_id"]
    publish(api, pid)
    d = api.get(f"/api/v2/catalogue/products/{pid}").json()
    assert d["annotations"]["slot"] == {"value": "top", "origin": "rule", "note": "hm-articles@1"}
    assert "slot" not in d["facts"]
    assert [m["uri"] for m in d["media"]] == ["https://media.wearhouse.invalid/public.jpg"]
    assert d["source"]["external_id"] == "0300000001"
    card = next(i for i in browse(api)["items"] if i["id"] == pid)
    assert card["thumbnail"] == "https://media.wearhouse.invalid/public.jpg" and card["slot"] == "top"
    assert api.get(f"/api/v2/catalogue/products/{uuid.uuid4()}").status_code == 404


# ============================================================== real-catalogue import tooling (chunking, job publish, CLI)
def test_chunk_csv_keeps_rows_verbatim_and_respects_limits():
    from wearhouse.catalogue.publication import chunk_csv
    text = csv_text({f"0400000{i:03d}": ("Tee", "T-shirt", "Garment Upper body", "Black", "d") for i in range(7)})
    chunks = chunk_csv(text, max_rows=3)
    assert len(chunks) == 3 and all(c.startswith(",".join(COLUMNS)) for c in chunks)
    assert "".join(c.split("\n", 1)[1] for c in chunks) == text.split("\n", 1)[1]  # rows unchanged, none lost
    assert len(chunk_csv(text, max_bytes=len(text.split("\n")[0]) + 200)) > 1


def test_publish_job_publishes_latest_and_skips_retired(api, editor, clean_db):
    job = run_import(api, csv_text(BASE)).json()
    rows = {r["external_id"]: r["product_id"] for r in job["rows"]}
    api.post(f"/api/v2/admin/catalogue/products/{rows['0100000004']}/retire", "editor-1")
    r = api.post(f"/api/v2/admin/catalogue/import-jobs/{job['id']}/publish", "editor-1")
    assert r.status_code == 200, r.text
    assert r.json() == {"job_id": job["id"], "published": 3, "already_published": 0, "retired_skipped": 1}
    assert len(browse(api)["items"]) == 3
    again = api.post(f"/api/v2/admin/catalogue/import-jobs/{job['id']}/publish", "editor-1").json()
    assert again["already_published"] == 3 and again["published"] == 0
    assert api.post(f"/api/v2/admin/catalogue/import-jobs/{job['id']}/publish", "shopper").status_code == 403
    assert query(clean_db, "SELECT count(*) FROM audit_event WHERE action = 'catalogue.import_job_published'") == [(2,)]


def test_cli_import_refuses_bad_checksum_and_unknown_operator(api, editor, tmp_path, monkeypatch, settings):
    import hashlib
    from wearhouse.bootstrap import cli
    data = csv_text(BASE).encode()
    f = tmp_path / "articles-synthetic.csv"
    f.write_bytes(data)
    (tmp_path / "articles-synthetic.csv.sha256").write_text("0" * 64)
    args = ["import-catalogue", "--csv", str(f), "--namespace", "hm-format-synthetic", "--source-name", "S",
            "--source-url", "https://wearhouse.invalid/s", "--acquired-on", "2026-11-25", "--basis", "synthetic",
            "--scope", "tests", "--accepted-on", "2026-11-25", "--accepted-by", "tests",
            "--terms-url", "https://wearhouse.invalid/t", "--operator-issuer", api.issuer.issuer,
            "--operator-subject", "editor-1", "--publish"]
    assert cli.main(args) == 2  # checksum mismatch: nothing touched
    (tmp_path / "articles-synthetic.csv.sha256").write_text(hashlib.sha256(data).hexdigest() + " *articles-synthetic.csv")
    monkeypatch.setattr(cli, "_runtime", lambda: (settings, api.app.state.engine, {}))
    bad = list(args)
    bad[bad.index("editor-1")] = "nobody"
    assert cli.main(bad) == 2  # unknown operator: refuses
    assert query(clean_db_name(api), "SELECT count(*) FROM product") == [(0,)]
    assert cli.main(args) == 0
    assert query(clean_db_name(api), "SELECT count(*) FROM product WHERE publication_state = 'published'") == [(4,)]


def clean_db_name(api):
    class _Db:
        name = api.app.state.engine.url.database
    return _Db
