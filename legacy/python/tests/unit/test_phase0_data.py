"""Phase 0 — data freeze checks that need no database."""
import json
from datetime import datetime, timezone
from pathlib import Path

from app.seed_data import PRODUCTS, gs1_check_digit, seed_wardrobe
from app.weather import parse_feed, validate_entry

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "bmkg_real_sample.json"


def _real_entries():
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return payload, [e for day in payload["data"][0]["cuaca"] for e in day]


def test_real_bmkg_sample_passes_validate_entry():
    """Checks TDD assumption 0.3.1 against the frozen real response."""
    payload, entries = _real_entries()
    assert payload["lokasi"]["adm4"] == "31.71.03.1001"
    now = datetime.fromisoformat(entries[0]["analysis_date"]).replace(tzinfo=timezone.utc)
    assert len(entries) >= 8
    for raw in entries:
        slot = validate_entry(raw, now=now)
        assert slot.rain == ("hujan" in raw["weather_desc"].lower())
        assert slot.hot == (raw["t"] >= 32)
    slots = parse_feed(payload, now=now)
    assert len(slots) == len(entries)


def test_seed_has_28_garments_across_all_slots():
    wardrobe = seed_wardrobe()
    assert len(wardrobe) == 28
    for slot in ("top", "bottom", "dress", "outer", "footwear", "accessory"):
        assert sum(1 for g in wardrobe if g.slot == slot) >= 3, slot
    assert any(g.rain_suitable and g.slot == "footwear" for g in wardrobe)
    assert any(g.rain_suitable and g.slot == "outer" and not g.heavy for g in wardrobe)
    assert any(g.heavy for g in wardrobe)
    assert any(g.long_sleeve for g in wardrobe)
    assert len({g.id for g in wardrobe}) == 28


def test_seed_products_have_valid_gtin14():
    for p in PRODUCTS:
        gtin = p["gtin"]
        assert len(gtin) == 14 and gtin.isdigit()
        assert gtin[-1] == gs1_check_digit(gtin[:-1])
