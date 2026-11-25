"""Re-export of the documented colour table, which lives in the catalogue domain (shared with generated
placeholders). Kept so wardrobe code keeps its import path."""
from __future__ import annotations

from ..catalogue.domain import COLOUR_HEX, colour_hex

__all__ = ["COLOUR_HEX", "colour_hex"]
