"""Phase 2 — Persistence & Wardrobe API (runs on SQLite and, if configured, Postgres)."""
import uuid
from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Garment, InterfaceLog, Outfit, OutfitItem
from app.seed_data import DEMO_USER_ID


def _by_slot(client):
    out = {}
    for g in client.get("/api/v1/wardrobe").json():
        out.setdefault(g["slot"], []).append(g)
    return out


# 1
def test_add_manual_garment_then_listed_in_wardrobe(client):
    body = {"name": "Thrifted corduroy jacket", "slot": "outer",
            "attrs": {"color_hex": "#7B4B2A", "style": "casual", "heavy": True, "long_sleeve": True}}
    r = client.post("/api/v1/garments", json=body)
    assert r.status_code == 201, r.text
    created = r.json()
    assert created["attrs"]["heavy"] is True and created["attrs"]["formality"] == 1  # defaults filled in
    names = [g["name"] for g in client.get("/api/v1/wardrobe").json()]
    assert "Thrifted corduroy jacket" in names


def test_add_garment_with_bad_slot_or_colour_is_422(client):
    assert client.post("/api/v1/garments", json={"name": "x", "slot": "hat"}).status_code == 422
    bad_color = {"name": "x", "slot": "top", "attrs": {"color_hex": "red"}}
    assert client.post("/api/v1/garments", json=bad_color).status_code == 422


# 2
def test_create_outfit_with_two_items_in_same_slot_returns_409(client):
    s = _by_slot(client)
    items = [s["top"][0]["id"], s["top"][1]["id"], s["bottom"][0]["id"], s["footwear"][0]["id"]]
    r = client.post("/api/v1/outfits", json={"items": items})
    assert r.status_code == 409
    dress_and_top = [s["dress"][0]["id"], s["top"][0]["id"], s["footwear"][0]["id"]]
    assert client.post("/api/v1/outfits", json={"items": dress_and_top}).status_code == 409


def test_create_outfit_with_unknown_garment_is_422(client):
    r = client.post("/api/v1/outfits", json={"items": [str(uuid.uuid4())]})
    assert r.status_code == 422


# 3
def test_db_rejects_duplicate_slot_in_outfit_item(app):
    with Session(app.state.engine) as s:
        tops = s.scalars(select(Garment).where(Garment.slot == "top")).all()[:2]
        o = Outfit(owner_id=DEMO_USER_ID, label="dup")
        s.add(o)
        s.flush()
        s.add(OutfitItem(outfit_id=o.id, slot="top", garment_id=tops[0].id))
        s.flush()
        s.add(OutfitItem(outfit_id=o.id, slot="top", garment_id=tops[1].id))
        with pytest.raises(IntegrityError):
            s.flush()  # the primary key (outfit_id, slot) itself enforces one item per slot
        s.rollback()


# 4
def test_wear_outfit_updates_last_worn_and_times_chosen(client):
    s = _by_slot(client)
    items = [s["top"][0]["id"], s["bottom"][0]["id"], s["footwear"][0]["id"]]
    oid = client.post("/api/v1/outfits", json={"items": items, "label": "1"}).json()["id"]
    r = client.post(f"/api/v1/outfits/{oid}/wear", json={"worn_on": "2026-11-24"})
    assert r.status_code == 204
    after = {g["id"]: g for g in client.get("/api/v1/wardrobe").json()}
    for gid in items:
        assert after[gid]["last_worn_at"] == "2026-11-24"
        assert after[gid]["times_chosen"] == 1
    untouched = s["dress"][0]["id"]
    assert after[untouched]["times_chosen"] == 0 and after[untouched]["last_worn_at"] is None


def test_wear_unknown_outfit_is_404(client):
    assert client.post(f"/api/v1/outfits/{uuid.uuid4()}/wear").status_code == 404


# 5
def test_week_endpoint_returns_only_outfits_planned_in_that_week(client):
    s = _by_slot(client)
    base = [s["dress"][0]["id"], s["footwear"][0]["id"]]
    for label, day in (("in-mon", "2026-11-23"), ("in-sun", "2026-11-29"), ("before", "2026-11-22"), ("after", "2026-11-30")):
        assert client.post("/api/v1/outfits", json={"items": base, "label": label, "planned_for": day}).status_code == 201
    week = client.get("/api/v1/outfits", params={"week": "2026-W48"}).json()
    assert sorted(o["label"] for o in week) == ["in-mon", "in-sun"]
    assert client.get("/api/v1/outfits", params={"week": "2026-48"}).status_code == 422


# 6
def test_delete_garment_used_in_outfit_is_blocked_or_cascades_as_documented(client):
    """Documented behaviour: deleting a garment that a saved outfit uses is BLOCKED with 409;
    an unused garment is deleted (204); a second delete is 404."""
    s = _by_slot(client)
    used, unused = s["accessory"][0]["id"], s["accessory"][1]["id"]
    client.post("/api/v1/outfits", json={"items": [s["dress"][0]["id"], s["footwear"][0]["id"], used]})
    assert client.delete(f"/api/v1/garments/{used}").status_code == 409
    assert client.delete(f"/api/v1/garments/{unused}").status_code == 204
    assert client.delete(f"/api/v1/garments/{unused}").status_code == 404
    ids = {g["id"] for g in client.get("/api/v1/wardrobe").json()}
    assert used in ids and unused not in ids


# 7
def test_every_request_writes_interface_log_row(client, app):
    def rows():
        with Session(app.state.engine) as s:
            return s.scalars(select(InterfaceLog).order_by(InterfaceLog.id)).all()

    before = len(rows())
    calls = [
        ("GET", "/api/v1/health", None),
        ("GET", "/api/v1/wardrobe", None),
        ("POST", "/api/v1/garments", {"name": "x", "slot": "nope"}),  # 422 is logged too
        ("GET", "/api/v1/outfits", None),
        ("POST", "/api/v1/outfits/recommend", {"occasion": "campus", "manual_weather": {"rain": True, "hot": False}}),
    ]
    for method, path, body in calls:
        client.request(method, path, json=body)
    new = rows()[before:]
    assert [(r.route, r.status) for r in new] == [
        ("GET /api/v1/health", 200),
        ("GET /api/v1/wardrobe", 200),
        ("POST /api/v1/garments", 422),
        ("GET /api/v1/outfits", 200),
        ("POST /api/v1/outfits/recommend", 200),
    ]
    assert all(r.interface == "I1" and r.latency_ms is not None and r.latency_ms >= 0 for r in new)
    assert new[-1].weather_source == "MANUAL"
    log = client.get("/api/v1/metrics/interface-log", params={"limit": 3}).json()
    assert len(log) == 3 and log[0]["route"] == "POST /api/v1/outfits/recommend"  # newest first


def test_writes_require_api_key(anon_client):
    assert anon_client.get("/api/v1/wardrobe").status_code == 200
    assert anon_client.post("/api/v1/garments", json={"name": "x", "slot": "top"}).status_code == 401
