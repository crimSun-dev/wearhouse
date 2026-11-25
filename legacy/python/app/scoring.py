"""Scoring (thesis Eq. 7–9) and the top-k recommender.

compat() is a colour/style stand-in for the FashionCLIP compatibility model
(interface I4); this is disclosed in the deck and in RESULTS.md.
"""
from __future__ import annotations

import colorsys
import math
from functools import lru_cache
from dataclasses import dataclass
from datetime import date
from itertools import combinations

from .domain import Garment, Outfit
from .rules import Context, candidates

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


@lru_cache(maxsize=4096)
def _hls(hex_color: str) -> tuple[float, float, float]:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i : i + 2], 16) / 255 for i in (0, 2, 4))
    return colorsys.rgb_to_hls(r, g, b)


@lru_cache(maxsize=4096)
def _is_neutral(hex_color: str) -> bool:
    _, light, sat = _hls(hex_color)
    return sat < 0.3 or light < 0.25 or light > 0.9


@lru_cache(maxsize=4096)
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


@lru_cache(maxsize=4096)
def style_pair(a: str, b: str) -> float:
    if a == b:
        return 1.0
    return STYLE_PAIRS.get(frozenset({a, b}), 0.3)


def compat(o: Outfit) -> float:
    """0..1 compatibility stand-in (I4): mean pairwise colour harmony and style match."""
    pairs = list(combinations(o.items, 2))
    if not pairs:
        return 1.0
    c = sum(color_pair(x.color_hex, y.color_hex) for x, y in pairs) / len(pairs)
    s = sum(style_pair(x.style, y.style) for x, y in pairs) / len(pairs)
    return 0.5 * c + 0.5 * s


def pref(g: Garment, p0: float = 0.5, a: int = 5) -> float:
    """Eq. 8: Bayesian-smoothed choice rate (chosen + p0·a) / (recommended + a)."""
    return (g.times_chosen + p0 * a) / (g.times_recommended + a)


def recency(g: Garment, today: date, h: float = 4.0) -> float:
    """Eq. 9: exp(-Δt/h) penalty for recently worn items; never worn → 0."""
    if g.last_worn_at is None:
        return 0.0
    dt = max((today - g.last_worn_at).days, 0)
    return math.exp(-dt / h)


def outfit_pref(o: Outfit) -> float:
    return sum(pref(g) for g in o.items) / len(o.items)


def outfit_recency(o: Outfit, today: date) -> float:
    return sum(recency(g, today) for g in o.items) / len(o.items)


def score(o: Outfit, today: date, w: tuple[float, float, float] = (0.5, 0.3, 0.2)) -> float:
    """Eq. 7: w1·compat + w2·pref − w3·recency."""
    return w[0] * compat(o) + w[1] * outfit_pref(o) - w[2] * outfit_recency(o, today)


@dataclass(frozen=True)
class ScoredOutfit:
    outfit: Outfit
    score: float
    compat: float
    pref: float
    recency: float


def rank(outfits: list[Outfit], today: date, k: int = 5) -> list[ScoredOutfit]:
    w1, w2, w3 = 0.5, 0.3, 0.2
    item_pref: dict[str, float] = {}
    item_rec: dict[str, float] = {}
    scored = []
    for o in outfits:
        for g in o.items:
            if g.id not in item_pref:
                item_pref[g.id] = pref(g)
                item_rec[g.id] = recency(g, today)
        n = len(o.items)
        c = compat(o)
        p = sum(item_pref[g.id] for g in o.items) / n
        r = sum(item_rec[g.id] for g in o.items) / n
        scored.append(ScoredOutfit(o, w1 * c + w2 * p - w3 * r, c, p, r))
    scored.sort(key=lambda s: (-s.score, tuple(g.id for g in s.outfit.items)))
    picked: list[ScoredOutfit] = []
    seen_cores: set[tuple[str, ...]] = set()
    for s in scored:  # first pass: one outfit per distinct top/bottom/dress core
        if len(picked) == k:
            break
        if s.outfit.core_key not in seen_cores:
            picked.append(s)
            seen_cores.add(s.outfit.core_key)
    for s in scored:  # fill if the wardrobe has fewer than k distinct cores
        if len(picked) == k:
            break
        if s not in picked:
            picked.append(s)
    picked.sort(key=lambda s: (-s.score, tuple(g.id for g in s.outfit.items)))
    return picked


def recommend(wardrobe: list[Garment], ctx: Context, today: date, k: int = 5) -> list[ScoredOutfit]:
    """Top-k allowed outfits, sorted by score descending. Empty list (not an error) if none."""
    return rank(candidates(wardrobe, ctx), today, k)
