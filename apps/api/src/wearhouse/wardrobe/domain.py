"""Wardrobe rules (pure): slot registry + occupancy, care states, limits, photo checks, planner windows."""
from __future__ import annotations

from datetime import date, timedelta

from ..platform.errors import FieldError, validation_failed

# ------------------------------------------------------------------ slot registry (design D4)
SLOT_CAPACITY = {"top": 1, "outer": 1, "bottom": 1, "dress": 1, "footwear": 1, "underwear": 1,
                 # accessory positions (TDD §11, complete-wearhouse-tdd); "accessory" = uncategorized, never guessed
                 "bag": 1, "headwear": 1, "eyewear": 1, "earrings": 1, "necklace": 1, "tie": 1, "scarf": 1, "belt": 1,
                 "wrist": 2, "ring": 2, "accessory": 3}
SLOTS = tuple(SLOT_CAPACITY)
ACCESSORY_POSITIONS = ("bag", "headwear", "eyewear", "earrings", "necklace", "tie", "scarf", "belt", "wrist", "ring",
                       "accessory")
# ruleset accessory-subtypes@1: H&M product types in the "Accessories" group -> position (design D1). Unlisted types
# (hair accessories, gloves, umbrellas, soft toys, ...) stay "accessory": an explicit unresolved category.
ACCESSORY_RULESET = "accessory-subtypes@1"
ACCESSORY_SUBTYPES = {
    "bag": "bag", "wallet": "bag",
    "hat/beanie": "headwear", "cap/peaked": "headwear", "hat/brim": "headwear", "beanie": "headwear", "cap": "headwear",
    "felt hat": "headwear", "bucket hat": "headwear", "straw hat": "headwear",
    "sunglasses": "eyewear", "eyeglasses": "eyewear",
    "earring": "earrings", "earrings": "earrings",
    "necklace": "necklace", "tie": "tie", "scarf": "scarf", "belt": "belt",
    "bracelet": "wrist", "watch": "wrist", "ring": "ring",
}


def accessory_position(product_type: str | None) -> str | None:
    return ACCESSORY_SUBTYPES.get((product_type or "").strip().lower())
EXCLUSIONS = (("dress", "top"), ("dress", "bottom"))
UNKNOWN_SLOT = "unknown"
CARE_STATES = ("ready", "laundry", "repair", "stored")
OCCASIONS = ("casual", "work", "formal", "sport", "event")
PHOTO_TYPES = {"image/jpeg": (b"\xff\xd8\xff",), "image/png": (b"\x89PNG\r\n\x1a\n",), "image/webp": (b"RIFF",)}
MAX_PHOTO_BYTES = 2 * 1024 * 1024
MAX_DECLARED = 1000
MAX_SHELVES = 50
MAX_SHELF_ITEMS = 500
MAX_LOOKS = 200
PLAN_AHEAD_DAYS = 30
WEAR_BACK_DAYS = 60
PLANNER_DAYS = 7


def registry() -> dict:
    return {"slots": [{"slot": s, "capacity": c} for s, c in SLOT_CAPACITY.items()],
            "exclusions": [list(x) for x in EXCLUSIONS]}


def sniff_photo(data: bytes) -> str | None:
    """Content type from magic bytes (never from the client's claimed type or file name)."""
    for ctype, magics in PHOTO_TYPES.items():
        if any(data.startswith(m) for m in magics):
            if ctype == "image/webp" and data[8:12] != b"WEBP":
                continue
            return ctype
    return None


def check_slots(slots: dict[str, list], effective: dict) -> None:
    """slots: {slot: [item_id, ...]}; effective: item_id -> effective slot (only the caller's items)."""
    errors: list[FieldError] = []
    seen: set = set()
    for slot, items in slots.items():
        if slot not in SLOT_CAPACITY:
            errors.append(FieldError(f"body.slots.{slot}", "unknown_slot", f"Unknown slot {slot!r}."))
            continue
        if len(items) > SLOT_CAPACITY[slot]:
            errors.append(FieldError(f"body.slots.{slot}", "over_capacity",
                                     f"{slot} holds at most {SLOT_CAPACITY[slot]} item(s)."))
        for item in items:
            if item in seen:
                errors.append(FieldError(f"body.slots.{slot}", "duplicate_item", "An item can be used once per look."))
            seen.add(item)
            if item not in effective:
                errors.append(FieldError(f"body.slots.{slot}", "unknown_item", "That item is not in your wardrobe."))
            elif effective[item] == UNKNOWN_SLOT:
                errors.append(FieldError(f"body.slots.{slot}", "slot_unknown",
                                         "Set a slot for this item before using it in a look."))
            elif effective[item] != slot:
                errors.append(FieldError(f"body.slots.{slot}", "slot_mismatch",
                                         f"That item is a {effective[item]}, not a {slot}."))
    used = {s for s, items in slots.items() if items}
    for a, b in EXCLUSIONS:
        if a in used and b in used:
            errors.append(FieldError("body.slots", "slot_conflict", f"A {a} cannot be combined with a {b}."))
    if not seen:
        errors.append(FieldError("body.slots", "empty", "A look needs at least one item."))
    if errors:
        raise validation_failed(errors)


def check_plan_date(d: date, today: date) -> None:
    if d < today or d > today + timedelta(days=PLAN_AHEAD_DAYS):
        raise validation_failed([FieldError("path.plan_date", "out_of_window",
                                            f"Plans can be set from today up to {PLAN_AHEAD_DAYS} days ahead.")])


def check_wear_date(d: date, today: date) -> None:
    if d > today or d < today - timedelta(days=WEAR_BACK_DAYS):
        raise validation_failed([FieldError("body.worn_on", "out_of_window",
                                            f"Wear can be logged for today or up to {WEAR_BACK_DAYS} days back.")])


def check_name(value: str, field: str, max_len: int) -> str:
    v = (value or "").strip()
    if not 1 <= len(v) <= max_len:
        raise validation_failed([FieldError(field, "invalid", f"Must be 1-{max_len} characters.")])
    return v
