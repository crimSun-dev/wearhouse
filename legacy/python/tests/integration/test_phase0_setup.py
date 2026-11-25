"""Phase 0 — setup & data freeze (DB-backed parts)."""
from sqlalchemy.orm import Session

from app.db import count, init_db, make_engine
from app.models import Garment, Product
from app.seeding import seed


def test_health_reports_db_backend(client, db_url):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    body = r.json()
    from app.db import backend_name

    assert body["db"] == backend_name(db_url)
    assert body["db"] in ("sqlite", "postgresql", "neon")
    assert body["weather_mode"] == "mock"
    assert body["fault"] == "none"


def test_health_names_neon_for_neon_hosts():
    from app.db import backend_name

    assert backend_name("postgresql://ep-cool-name-123.ap-southeast-1.aws.neon.tech/db?sslmode=require") == "neon"
    assert backend_name("sqlite:///demo.db") == "sqlite"


def test_seed_is_idempotent(db_url):
    engine = make_engine(db_url)
    init_db(engine)
    with Session(engine) as s:
        first = seed(s)
        n_garments, n_products = count(s, Garment), count(s, Product)
        second = seed(s)
        assert first["garments_added"] == 28
        assert second == {"products_added": 0, "garments_added": 0}
        assert (count(s, Garment), count(s, Product)) == (n_garments, n_products) == (28, 4)
    engine.dispose()


def test_api_seeded_wardrobe_has_28_garments_across_all_slots(client):
    garments = client.get("/api/v1/wardrobe").json()
    assert len(garments) == 28
    assert {g["slot"] for g in garments} == {"top", "bottom", "dress", "outer", "footwear", "accessory"}
