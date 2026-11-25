"""Phase 4 — Garment registration (QR + activation code; FYP RQ3)."""
import threading
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app import registration
from app.models import ActivationAttempt, Garment, GarmentCode
from app.seed_data import DEMO_USER_ID, PRODUCTS

GTIN = PRODUCTS[0]["gtin"]  # rain parka, slot "outer"


def issue(client, n=1, gtin=GTIN):
    r = client.post("/api/v1/admin/codes", json={"gtin": gtin, "count": n})
    assert r.status_code == 201, r.text
    return r.json()


# 1
def test_valid_code_adds_garment_in_product_slot_exactly_once(client):
    tag = issue(client)[0]
    before = len(client.get("/api/v1/wardrobe").json())
    r = client.post("/api/v1/garments/activate", json={"code": tag["activation_code"]})
    assert r.status_code == 201, r.text
    g = r.json()
    assert g["slot"] == "outer" and g["origin"] == "registered" and g["serial"] == tag["serial"]
    assert g["attrs"]["rain_suitable"] is True
    wardrobe = client.get("/api/v1/wardrobe").json()
    assert len(wardrobe) == before + 1
    assert sum(1 for x in wardrobe if x["serial"] == tag["serial"]) == 1


def test_code_is_accepted_without_dashes_and_in_lower_case(client):
    tag = issue(client)[0]
    typed = tag["activation_code"].replace("-", "").lower()
    assert client.post("/api/v1/garments/activate", json={"code": typed}).status_code == 201


# 2
def test_second_use_of_same_code_rejected_with_generic_error(client):
    code = issue(client)[0]["activation_code"]
    assert client.post("/api/v1/garments/activate", json={"code": code}).status_code == 201
    r = client.post("/api/v1/garments/activate", json={"code": code})
    assert r.status_code == 400 and r.json() == {"detail": "invalid code"}


# 3
def test_unknown_code_and_used_code_and_public_serial_return_identical_response_body(client):
    tag = issue(client)[0]
    client.post("/api/v1/garments/activate", json={"code": tag["activation_code"]})
    responses = [
        client.post("/api/v1/garments/activate", json={"code": "AAAA-BBBB-CCCC-DDDD"}),  # unknown
        client.post("/api/v1/garments/activate", json={"code": tag["activation_code"]}),  # used
        client.post("/api/v1/garments/activate", json={"code": tag["serial"]}),  # public serial from the QR
    ]
    assert {r.status_code for r in responses} == {400}
    assert len({r.content for r in responses}) == 1


# 4
def test_two_concurrent_redemptions_only_one_succeeds(app, db_url):
    """Two threads, two DB sessions, same code, released together. On Postgres this exercises the
    row lock + re-check of `used_at IS NULL`; on SQLite the database write lock."""
    rounds = 5  # repeat with fresh codes to give the race a fair chance to show up
    with Session(app.state.engine) as s:
        codes = [c["activation_code"] for c in registration.issue_codes(s, GTIN, rounds)]
    for code in codes:
        results: list[str] = []
        barrier = threading.Barrier(2)

        def worker():
            with app.state.Session() as s:
                barrier.wait()
                try:
                    registration.activate(s, DEMO_USER_ID, code)
                    results.append("ok")
                except registration.ActivationError:
                    results.append("rejected")

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)
        assert sorted(results) == ["ok", "rejected"]
    with Session(app.state.engine) as s:
        assert s.scalar(select(func.count()).select_from(Garment).where(Garment.gtin == GTIN)) == rounds


@pytest.mark.postgres
def test_many_concurrent_redemptions_postgres_exactly_one_wins(app, db_url):
    if not db_url.startswith("postgres"):
        pytest.skip("Postgres-only stress variant")
    with Session(app.state.engine) as s:
        code = registration.issue_codes(s, GTIN, 1)[0]["activation_code"]
    n = 8
    barrier = threading.Barrier(n)
    results: list[str] = []

    def worker(i):
        with app.state.Session() as s:
            barrier.wait()
            try:
                registration.activate(s, DEMO_USER_ID, code)
                results.append("ok")
            except registration.ActivationError:
                results.append("rejected")

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
    [t.start() for t in threads]
    [t.join(timeout=30) for t in threads]
    assert results.count("ok") == 1 and results.count("rejected") == n - 1


# 5
def test_eleventh_attempt_in_an_hour_returns_429(client, app):
    for i in range(10):
        r = client.post("/api/v1/garments/activate", json={"code": f"WRONG-CODE-{i:04d}"})
        assert r.status_code == 400, i
    valid = issue(client)[0]["activation_code"]
    r = client.post("/api/v1/garments/activate", json={"code": valid})
    assert r.status_code == 429  # even a correct code is refused once the limit is hit
    # attempts older than an hour stop counting
    with Session(app.state.engine) as s:
        old = datetime.now(timezone.utc) - timedelta(hours=2)
        s.execute(ActivationAttempt.__table__.update().values(at=old))
        s.commit()
    assert client.post("/api/v1/garments/activate", json={"code": valid}).status_code == 201


def test_rate_limit_survives_restart_because_it_lives_in_the_db(settings):
    from app.main import create_app
    from fastapi.testclient import TestClient
    from tests.conftest import API_KEY

    for _ in range(2):  # two separate app instances on the same DB = a restart
        a = create_app(settings)
        with TestClient(a, headers={"X-API-Key": API_KEY}) as c:
            for i in range(5):
                c.post("/api/v1/garments/activate", json={"code": f"nope{i}"})
        a.state.engine.dispose()
    a = create_app(settings)
    with TestClient(a, headers={"X-API-Key": API_KEY}) as c:
        assert c.post("/api/v1/garments/activate", json={"code": "nope"}).status_code == 429
    a.state.engine.dispose()


# 6
def test_tag_metadata_is_read_only_and_scan_page_contains_redemption(client, app):
    tag = issue(client)[0]
    before = client.get("/api/v1/wardrobe").json()
    r = client.get(f"/api/v1/scan/01/{GTIN}/21/{tag['serial']}")
    assert r.status_code == 200
    page = r.json()
    assert page["name"] == PRODUCTS[0]["name"] and page["wishlist_only"] is False
    assert page["digital_link"].endswith(f"/01/{GTIN}/21/{tag['serial']}")
    html = client.get(f"/01/{GTIN}/21/{tag['serial']}")
    assert html.status_code == 200 and PRODUCTS[0]["name"] in html.text
    assert "/api/v1/garments/scan" in html.text
    assert client.get("/api/v1/wardrobe").json() == before
    with Session(app.state.engine) as s:
        c = s.get(GarmentCode, tag["serial"])
        assert c.owner_id is None and c.used_at is None
    assert client.get(f"/api/v1/scan/01/{PRODUCTS[1]['gtin']}/21/{tag['serial']}").status_code == 404
    assert client.get(f"/api/v1/scan/01/{GTIN}/21/{'0' * 32}").status_code == 404


@pytest.mark.parametrize("first", ["qr", "key"])
def test_qr_and_key_redeem_the_same_registration_once(client, first):
    tag = issue(client)[0]
    qr = lambda: client.post("/api/v1/garments/scan", json={"gtin": tag["gtin"], "serial": tag["serial"]})
    key = lambda: client.post("/api/v1/garments/activate", json={"code": tag["activation_code"]})
    methods = [qr, key] if first == "qr" else [key, qr]
    result = methods[0]()
    assert result.status_code == 201
    assert result.json()["serial"] == tag["serial"]
    assert methods[1]().status_code == 400
    assert methods[0]().status_code == 400
    assert sum(g["serial"] == tag["serial"] for g in client.get("/api/v1/wardrobe").json()) == 1


def test_scans_are_logged_as_I5(client, app):
    from app.models import InterfaceLog

    tag = issue(client)[0]
    client.get(f"/01/{GTIN}/21/{tag['serial']}")
    with Session(app.state.engine) as s:
        last = s.scalars(select(InterfaceLog).order_by(InterfaceLog.id.desc())).first()
    assert last.interface == "I5"


def test_qr_svg_encodes_the_digital_link(client):
    tag = issue(client)[0]
    r = client.get(f"/api/v1/codes/{tag['serial']}/qr.svg")
    assert r.status_code == 200 and r.headers["content-type"].startswith("image/svg+xml")
    assert b"<svg" in r.content


# 7
def test_serials_are_128_bit_and_unique_over_100k_samples():
    serials = [registration.new_serial() for _ in range(100_000)]
    assert all(len(s) == 32 and int(s, 16) >= 0 for s in serials)  # 32 hex chars = 128 bit
    assert len(set(serials)) == 100_000


def test_activation_codes_are_80_bit():
    code, h = registration.new_activation_code()
    raw = code.replace("-", "")
    assert len(raw) == 16 and set(raw) <= set("ABCDEFGHIJKLMNOPQRSTUVWXYZ234567")  # 16 × 5 bit = 80 bit
    assert len(h) == 64


# 8
def test_activation_code_stored_only_as_hash(client, app):
    tag = issue(client)[0]
    code = tag["activation_code"]
    raw = code.replace("-", "")
    with Session(app.state.engine) as s:
        row = s.get(GarmentCode, tag["serial"])
        assert row.activation_hash == registration.hash_code(code)
        assert code not in row.activation_hash and raw not in row.activation_hash
        # nothing anywhere in the code table contains the plain code
        dump = " ".join(str(v) for r in s.execute(text("SELECT * FROM garment_code")).all() for v in r)
        assert raw not in dump and code not in dump
