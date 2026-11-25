"""Synthetic demo data (no real people, no personal photos).

28 garments for one synthetic user, plus retail products used for the
QR + activation-code registration flow. Pure data; `seed.py` loads it into the DB.
"""
from __future__ import annotations

import uuid

from .domain import Garment

DEMO_USER_ID = uuid.UUID("00000000-0000-4000-8000-000000000001")
DEMO_USER_NAME = "Demo User (synthetic)"
DEFAULT_ADM4 = "31.71.03.1001"  # Kemayoran, Jakarta Pusat
_NS = uuid.UUID("6f1d2b1e-5d0c-4c1e-9a52-1b2f0d3c4e5f")

# name, slot, color, style, rain, heavy, long_sleeve, long_bottom, formality
_GARMENTS = [
    ("Pink oxford shirt", "top", "#F4B6C2", "smart", 0, 0, 1, 0, 2),
    ("White long-sleeve blouse", "top", "#F5F2EA", "smart", 0, 0, 1, 0, 3),
    ("Light blue shirt", "top", "#A9C4E8", "smart", 0, 0, 1, 0, 3),
    ("Grey graphic tee", "top", "#9A9A9A", "casual", 0, 0, 0, 0, 1),
    ("Black polo", "top", "#222222", "casual", 0, 0, 0, 0, 2),
    ("Beige wrap skirt", "bottom", "#D8C3A5", "smart", 0, 0, 0, 0, 2),
    ("Pink pleated skirt", "bottom", "#E8A5B5", "smart", 0, 0, 0, 0, 2),
    ("Denim mini skirt", "bottom", "#5B7FA6", "casual", 0, 0, 0, 0, 1),
    ("Beige wide trousers", "bottom", "#CDB89A", "smart", 0, 0, 0, 1, 3),
    ("Light-wash jeans", "bottom", "#8FB3D9", "casual", 0, 0, 0, 1, 1),
    ("Black tailored trousers", "bottom", "#1E1E1E", "formal", 0, 0, 0, 1, 3),
    ("Navy long-sleeve maxi dress", "dress", "#2B3A67", "modest", 0, 0, 1, 1, 3),
    ("Orange floral sundress", "dress", "#F2A65A", "casual", 0, 0, 0, 0, 1),
    ("Black cocktail dress", "dress", "#111111", "formal", 0, 0, 0, 0, 4),
    ("Clear lightweight raincoat", "outer", "#DDE8EE", "casual", 1, 0, 1, 0, 1),
    ("Denim jacket", "outer", "#4A6C93", "casual", 0, 1, 1, 0, 1),
    ("Beige trench coat", "outer", "#C8B08A", "smart", 1, 1, 1, 0, 3),
    ("Black blazer", "outer", "#1C1C1C", "formal", 0, 0, 1, 0, 4),
    ("White sneakers", "footwear", "#F2F2F2", "casual", 0, 0, 0, 0, 1),
    ("Rubber rain sandals", "footwear", "#3C6E71", "casual", 1, 0, 0, 0, 1),
    ("Black loafers", "footwear", "#1A1A1A", "smart", 0, 0, 0, 0, 3),
    ("Nude heels", "footwear", "#D9B99B", "formal", 0, 0, 0, 0, 4),
    ("Waterproof leather ankle boots", "footwear", "#5A4636", "smart", 1, 0, 0, 0, 3),
    ("Canvas tote bag", "accessory", "#E9DFC9", "casual", 0, 0, 0, 0, 1),
    ("Cream hijab", "accessory", "#EFE6D8", "modest", 0, 0, 0, 0, 2),
    ("Silver necklace", "accessory", "#C0C0C0", "formal", 0, 0, 0, 0, 3),
    ("Baseball cap", "accessory", "#2F4F4F", "sporty", 0, 0, 0, 0, 1),
    ("Pearl earrings", "accessory", "#F8F4EC", "formal", 0, 0, 0, 0, 4),
]


def garment_id(name: str) -> uuid.UUID:
    return uuid.uuid5(_NS, name)


def seed_garment_rows() -> list[dict]:
    rows = []
    for name, slot, color, style, rain, heavy, ls, lb, formality in _GARMENTS:
        rows.append(
            {
                "id": garment_id(name),
                "name": name,
                "slot": slot,
                "attrs": {
                    "color_hex": color,
                    "style": style,
                    "rain_suitable": bool(rain),
                    "heavy": bool(heavy),
                    "long_sleeve": bool(ls),
                    "long_bottom": bool(lb),
                    "formality": formality,
                },
            }
        )
    return rows


def seed_wardrobe() -> list[Garment]:
    """The same 28 garments as domain objects (used by the CLI and unit tests)."""
    return [Garment(id=str(r["id"]), name=r["name"], slot=r["slot"], **r["attrs"]) for r in seed_garment_rows()]


def gs1_check_digit(body: str) -> str:
    """GS1 mod-10 check digit for a GTIN body (all digits except the last)."""
    total = sum(int(d) * (3 if i % 2 == 0 else 1) for i, d in enumerate(reversed(body)))
    return str((10 - total % 10) % 10)


def _gtin(body13: str) -> str:
    return body13 + gs1_check_digit(body13)


# Synthetic products under the Indonesian GS1 prefix 899 (not real company numbers).
PRODUCTS = [
    {
        "gtin": _gtin("0899900000011"), "name": "DW Lightweight Rain Parka", "category": "jacket",
        "slot": "outer", "color_hex": "#3B5B7A", "style": "casual", "rain_suitable": True, "heavy": False,
        "long_sleeve": True, "long_bottom": False, "formality": 1, "glb_template": "outer_jacket.glb",
    },
    {
        "gtin": _gtin("0899900000028"), "name": "DW Linen Shirt", "category": "shirt",
        "slot": "top", "color_hex": "#F4B6C2", "style": "smart", "rain_suitable": False, "heavy": False,
        "long_sleeve": True, "long_bottom": False, "formality": 3, "glb_template": "top_shirt.glb",
    },
    {
        "gtin": _gtin("0899900000035"), "name": "DW Pleated Midi Skirt", "category": "skirt",
        "slot": "bottom", "color_hex": "#D8C3A5", "style": "smart", "rain_suitable": False, "heavy": False,
        "long_sleeve": False, "long_bottom": True, "formality": 3, "glb_template": "bottom_skirt.glb",
    },
    {
        "gtin": _gtin("0899900000042"), "name": "DW Canvas Sneakers", "category": "sneakers",
        "slot": "footwear", "color_hex": "#F2F2F2", "style": "casual", "rain_suitable": False, "heavy": False,
        "long_sleeve": False, "long_bottom": False, "formality": 1, "glb_template": "footwear_sneaker.glb",
    },
]
