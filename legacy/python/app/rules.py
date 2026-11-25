"""Rules engine (thesis 3.4.3 a–d): slot, heat, rain and dress-code rules.

Pure functions only. `allowed()` is the single definition of a valid outfit; the
check helpers are reused by measure.py (metric M1) so baseline and integrated
runs are judged by exactly the same rules.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import product

from .domain import OCCASIONS, Garment, Outfit

CLOTHING_SLOTS = ("top", "bottom", "dress", "outer", "footwear")  # formality applies to these
MIN_FORMALITY = {"campus": 1, "casual": 1, "worship": 1, "formal": 2, "wedding": 3}


@dataclass(frozen=True)
class Context:
    rain: bool
    hot: bool
    occasion: str  # one of OCCASIONS

    def __post_init__(self):
        if self.occasion not in OCCASIONS:
            raise ValueError(f"unknown occasion {self.occasion!r}")


# (a) slot rule -------------------------------------------------------------
def slot_ok(o: Outfit) -> bool:
    slots = [g.slot for g in o.items]
    if len(slots) != len(set(slots)):
        return False  # one item per slot
    s = set(slots)
    if "dress" in s:
        if "top" in s or "bottom" in s:
            return False  # a dress fills both top and bottom
    elif not ("top" in s and "bottom" in s):
        return False
    return "footwear" in s


# (b) heat rule -------------------------------------------------------------
def heat_ok(o: Outfit, hot: bool) -> bool:
    return not hot or not any(g.heavy for g in o.items)


# (c) rain rule -------------------------------------------------------------
def rain_ok(o: Outfit, rain: bool) -> bool:
    if not rain:
        return True
    return any(g.rain_suitable for g in o.items if g.slot in ("footwear", "outer"))


# (d) dress-code rule -------------------------------------------------------
def dress_code_ok(o: Outfit, occasion: str) -> bool:
    if occasion == "worship":
        sleeve = any(g.long_sleeve for g in o.items if g.slot in ("top", "dress", "outer"))
        legs = any(g.long_bottom for g in o.items if g.slot in ("bottom", "dress"))
        if not (sleeve and legs):
            return False
    floor = MIN_FORMALITY.get(occasion, 1)
    return all(g.formality >= floor for g in o.items if g.slot in CLOTHING_SLOTS)


def weather_ok(o: Outfit, ctx: Context) -> bool:
    return rain_ok(o, ctx.rain) and heat_ok(o, ctx.hot)


def allowed(outfit: Outfit, ctx: Context) -> bool:
    return (
        slot_ok(outfit)
        and heat_ok(outfit, ctx.hot)
        and rain_ok(outfit, ctx.rain)
        and dress_code_ok(outfit, ctx.occasion)
    )


def _item_could_fit(g: Garment, ctx: Context) -> bool:
    """Cheap per-item pre-filter; the full check is still `allowed()`."""
    if ctx.hot and g.heavy:
        return False
    if g.slot in CLOTHING_SLOTS and g.formality < MIN_FORMALITY.get(ctx.occasion, 1):
        return False
    return True


def candidates(wardrobe: list[Garment], ctx: Context) -> list[Outfit]:
    """Every allowed combination: (top+bottom | dress) + footwear [+ outer] [+ accessory]."""
    by: dict[str, list[Garment]] = {}
    for g in wardrobe:
        if _item_could_fit(g, ctx):
            by.setdefault(g.slot, []).append(g)
    bases: list[tuple[Garment, ...]] = [(t, b) for t, b in product(by.get("top", []), by.get("bottom", []))]
    bases += [(d,) for d in by.get("dress", [])]
    outers: list[Garment | None] = [None, *by.get("outer", [])]
    accessories: list[Garment | None] = [None, *by.get("accessory", [])]
    out: list[Outfit] = []
    for base in bases:
        for shoe in by.get("footwear", []):
            for outer in outers:
                for acc in accessories:
                    items = base + (shoe,) + tuple(x for x in (outer, acc) if x is not None)
                    o = Outfit(items)
                    if allowed(o, ctx):
                        out.append(o)
    return out
