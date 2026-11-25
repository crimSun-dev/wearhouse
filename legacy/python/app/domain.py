"""Plain domain objects used by the pure rules/scoring core (no DB, no HTTP)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

SLOTS = ("top", "bottom", "dress", "outer", "footwear", "accessory")
OCCASIONS = ("campus", "casual", "worship", "formal", "wedding")
STYLES = ("casual", "smart", "formal", "modest", "sporty", "street")

# Attributes a garment carries for the rules engine / compat stand-in.
ATTR_DEFAULTS = {
    "color_hex": "#808080",
    "style": "casual",
    "rain_suitable": False,
    "heavy": False,
    "long_sleeve": False,
    "long_bottom": False,
    "formality": 1,
}


@dataclass(frozen=True)
class Garment:
    id: str
    name: str
    slot: str
    color_hex: str = "#808080"
    style: str = "casual"
    rain_suitable: bool = False
    heavy: bool = False
    long_sleeve: bool = False
    long_bottom: bool = False
    formality: int = 1
    times_recommended: int = 0
    times_chosen: int = 0
    last_worn_at: date | None = None


@dataclass(frozen=True)
class Outfit:
    items: tuple[Garment, ...]

    def by_slot(self) -> dict[str, Garment]:
        return {g.slot: g for g in self.items}

    def get(self, slot: str) -> Garment | None:
        return self.by_slot().get(slot)

    @property
    def core_key(self) -> tuple[str, ...]:
        """Identity of the main body garments (used for diversity in the top-5)."""
        s = self.by_slot()
        return tuple(s[k].id if k in s else "" for k in ("top", "bottom", "dress"))
