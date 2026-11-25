"""Thesis §3.4.3 hard rules and the appendix attribute lookup (pure).

Ruleset `wardrobe-rules@1` is the SAME keyword table as `research/configs/rq2.json` `attribute_rules` (thesis appendix,
P0390); `tests/test_outfit_rules.py` asserts parity so the app and the RQ2 simulation decide eligibility identically.
Derived values are annotations (origin `rule`), not verified retail facts; an owner's correction (origin `owner`) wins.
"""
from __future__ import annotations

import re
from typing import Sequence

RULESET_ID = "wardrobe-rules@1"
OCCASIONS = ("casual", "campus", "hangout", "worship", "wedding")  # research schedule vocabulary + casual
ATTRIBUTES = ("warmth", "rain_suitable", "long_sleeve", "long_bottom", "formal")
WARMTH = ("light", "medium", "heavy")

ATTRIBUTE_RULES = {
    "heavy_words": ["coat", "parka", "wool", "puffer", "down", "shearling", "fleece", "knit", "sweater", "cardigan",
                    "leather"],
    "light_words": ["linen", "tank", "cami", "tee", "t-shirt", "sleeveless", "chiffon", "sandal", "shorts", "crop"],
    "rain_words": ["rain", "trench", "waterproof", "boot", "parka", "windbreaker", "anorak", "jacket"],
    "long_sleeve_words": ["long sleeve", "long-sleeve", "shirt", "blouse", "sweater", "cardigan", "hoodie",
                          "turtleneck"],
    "long_bottom_words": ["maxi", "trouser", "pants", "jeans", "palazzo", "culotte", "long skirt", "midi"],
    "short_bottom_words": ["shorts", "mini", "short skirt", "hot pants"],
    "formal_words": ["blazer", "suit", "gown", "silk", "satin", "heel", "pump", "tuxedo", "evening", "cocktail",
                     "oxford"],
    "default_warmth": {"top": "light", "bottom": "medium", "dress": "light", "outer": "medium", "footwear": "medium",
                       "accessory": "light"},
}


ACCESSORY_POSITIONS = ("bag", "headwear", "eyewear", "earrings", "necklace", "tie", "scarf", "belt", "wrist", "ring")


def derive(slot: str, text: str) -> dict:
    """The appendix lookup, exactly as the RQ2 simulation applies it (simulate.attributes). Accessory positions use
    the research's single "accessory" slot."""
    slot = "accessory" if slot in ACCESSORY_POSITIONS else slot
    t = (text or "").lower()
    r = ATTRIBUTE_RULES

    def has(words):
        return any(re.search(rf"\b{re.escape(w)}", t) for w in words)

    warmth = "heavy" if has(r["heavy_words"]) else "light" if has(r["light_words"]) else \
        r["default_warmth"].get(slot, "medium")
    return {
        "warmth": warmth,
        "rain_suitable": has(r["rain_words"]) and slot in ("footwear", "outer"),
        "long_sleeve": slot == "outer" or has(r["long_sleeve_words"]) or (slot == "dress" and has(r["long_bottom_words"])),
        "long_bottom": (slot == "bottom" and not has(r["short_bottom_words"])) or (slot == "dress" and has(r["long_bottom_words"])),
        "formal": has(r["formal_words"]),
    }


def attribute_errors(values: dict) -> list[str]:
    errors = []
    for k, v in values.items():
        if k not in ATTRIBUTES:
            errors.append(f"unknown attribute {k}")
        elif k == "warmth" and v is not None and v not in WARMTH:
            errors.append("warmth must be light, medium or heavy")
        elif k != "warmth" and v is not None and not isinstance(v, bool):
            errors.append(f"{k} must be true or false")
    return errors


def failed_rule(outfit: Sequence[tuple[str, dict]], *, rain: bool | None, hot: bool | None, occasion: str) -> str | None:
    """`outfit`: (slot, attributes) per item. Returns the first failing rule name, or None when the outfit passes.
    Unknown weather (None) applies no weather rule: it is reported as unknown, never guessed."""
    if hot and any(a["warmth"] == "heavy" for s, a in outfit if s == "outer"):
        return "heat"
    if rain and not any(a["rain_suitable"] for s, a in outfit if s in ("footwear", "outer")):
        return "rain"
    if occasion == "worship" and not (any(a["long_sleeve"] for s, a in outfit if s in ("top", "dress", "outer"))
                                      and any(a["long_bottom"] for s, a in outfit if s in ("bottom", "dress"))):
        return "worship_dress_code"
    if occasion == "wedding" and not any(a["formal"] for _, a in outfit):
        return "wedding_dress_code"
    return None


RULE_TEXT = {
    "heat": "hot day: heavy outerwear is left out",
    "rain": "rain: needs rain-suitable footwear or outerwear",
    "worship_dress_code": "worship: needs long sleeves and a long bottom",
    "wedding_dress_code": "wedding: needs at least one formal piece",
}
