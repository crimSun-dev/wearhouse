"""Heuristic colour/style compatibility baseline.

Extracted (v2-owned copy) from legacy/python/app/scoring.py `compat`/`color_pair`/`style_pair` at commit
ea21b05; the legacy runtime keeps its frozen implementation. Behaviour is pinned by
tests/test_recommendation_baseline.py. Difference from legacy by design: unknown colour/style is not
defaulted to grey/casual. Pairs with an unknown attribute are excluded, and if nothing is evaluable
the score is None.
This is NOT FashionCLIP/type-aware compatibility and reports HEURISTIC_BASELINE mode.
"""
from __future__ import annotations

import colorsys
from itertools import combinations
from typing import Sequence

from .ports import ItemFeatures, ModelInfo, RankedOutfit, RankerMode, RankerResult

BASELINE_MODEL = ModelInfo(RankerMode.HEURISTIC_BASELINE, "colour-style-heuristic", "1.0.0+legacy-ea21b05")

STYLE_PAIRS = {
    frozenset({"casual", "sporty"}): 0.7,
    frozenset({"casual", "smart"}): 0.7,
    frozenset({"casual", "street"}): 0.8,
    frozenset({"casual", "modest"}): 0.7,
    frozenset({"smart", "formal"}): 0.8,
    frozenset({"smart", "modest"}): 0.8,
    frozenset({"formal", "modest"}): 0.7,
    frozenset({"street", "sporty"}): 0.8,
}


def _hls(hex_color: str) -> tuple[float, float, float]:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return colorsys.rgb_to_hls(r, g, b)


def _is_neutral(hex_color: str) -> bool:
    _, light, sat = _hls(hex_color)
    return sat < 0.3 or light < 0.25 or light > 0.9


def color_pair(a: str, b: str) -> float:
    if _is_neutral(a) or _is_neutral(b):
        return 1.0
    d = abs(_hls(a)[0] - _hls(b)[0]) * 360
    d = min(d, 360 - d)
    if d <= 35:
        return 0.9  # analogous
    if d >= 150:
        return 0.8  # complementary
    return 0.45


def style_pair(a: str, b: str) -> float:
    if a == b:
        return 1.0
    return STYLE_PAIRS.get(frozenset({a, b}), 0.3)


class HeuristicCompatibility:
    model = BASELINE_MODEL

    def components(self, items: Sequence[ItemFeatures]) -> dict[str, float | None]:
        pairs = list(combinations(items, 2))
        colours = [color_pair(x.colour_hex, y.colour_hex) for x, y in pairs if x.colour_hex and y.colour_hex]
        styles = [style_pair(x.style, y.style) for x, y in pairs if x.style and y.style]
        return {"colour": sum(colours) / len(colours) if colours else None,
                "style": sum(styles) / len(styles) if styles else None}

    def score(self, items: Sequence[ItemFeatures]) -> float | None:
        if len(items) < 2:
            return 1.0  # legacy: a single item has no incompatible pair
        c = self.components(items)
        known = [v for v in (c["colour"], c["style"]) if v is not None]
        if not known:
            return None
        return sum(known) / len(known)


class HeuristicOutfitRanker:
    model = BASELINE_MODEL

    def __init__(self, scorer: HeuristicCompatibility | None = None):
        self.scorer = scorer or HeuristicCompatibility()

    def rank(self, candidates: Sequence[Sequence[ItemFeatures]], k: int) -> RankerResult:
        scored = []
        for items in candidates:
            s = self.scorer.score(items)
            if s is None:
                continue  # unknown compatibility is excluded, not guessed
            ids = tuple(i.item_id for i in items)
            scored.append(RankedOutfit(ids, round(s, 6), self.scorer.components(items)))
        scored.sort(key=lambda r: (-r.score, r.item_ids))
        return RankerResult(self.model, tuple(scored[:k]))
