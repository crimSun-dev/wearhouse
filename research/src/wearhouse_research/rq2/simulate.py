"""Simulated wardrobes and days (methodology 3.3.2) and the outfit recommender (3.4.3, Eq. 7-9).

Hard rules: (a) slots, (b) heat removes heavy outer layers, (c) rain needs rain-suitable footwear or outer layer,
(d) dress codes (worship: long sleeves + long bottoms; wedding: formal). Ranking: w1*Comp + w2*Pref - w3*Rec with
Pref = (k + a*p0) / (n + a) and Rec = mean exp(-dt / h). Variants: full, compatibility_only (slot rules + Comp),
no_context (no heat/rain/dress rules), no_recency (w3 = 0). Behaviours: favourite, random, weather.
Vectorised per user (outfit x garment index matrix, cached rule masks) so thesis-scale runs take minutes.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from itertools import product
from typing import Callable

import numpy as np

from .data import SLOT_OF

VARIANTS = ("full", "compatibility_only", "no_context", "no_recency")
BEHAVIOURS = ("favourite", "random", "weather")


@dataclass(frozen=True)
class Garment:
    id: str
    slot: str
    type: str
    warmth: str          # light | medium | heavy
    rain: bool
    long_sleeve: bool
    long_bottom: bool
    formal: bool


def attributes(item_id: str, meta: dict, rules: dict) -> Garment:
    """Attribute lookup (thesis appendix table): from item type and title keywords, else the fixed defaults."""
    cat = meta.get("semantic_category", "unknown")
    title = (meta.get("title") or meta.get("url_name") or "").lower()
    slot = SLOT_OF.get(cat, "accessory")

    def has(words):
        return any(re.search(rf"\b{re.escape(w)}", title) for w in words)

    warmth = ("heavy" if has(rules["heavy_words"]) else "light" if has(rules["light_words"]) else
              rules["default_warmth"].get(slot, "medium"))
    rain = has(rules["rain_words"]) and slot in ("footwear", "outer")
    long_sleeve = slot == "outer" or has(rules["long_sleeve_words"]) or (slot == "dress" and has(rules["long_bottom_words"]))
    long_bottom = (slot == "bottom" and not has(rules["short_bottom_words"])) or (slot == "dress" and has(rules["long_bottom_words"]))
    return Garment(item_id, slot, cat, warmth, rain, long_sleeve, long_bottom, has(rules["formal_words"]))


@dataclass(frozen=True)
class Day:
    index: int
    occasion: str
    rain: bool
    hot: bool


MONTH_DAYS = [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]


def days(start_month: int, n: int, clim: dict, schedule: dict, rng: np.random.Generator) -> list[Day]:
    """Occasions from the weekly student schedule; weather from monthly rain/heat probabilities (assumed values)."""
    out, month, dom, weekday = [], start_month, 1, 0  # simulations start on a Monday
    for i in range(n):
        p = clim[str(month)]
        occ = schedule["weekday"][weekday]
        if occ == "hangout" and rng.random() < schedule["wedding_probability_on_weekend"]:
            occ = "wedding"
        out.append(Day(i, occ, bool(rng.random() < p["rain"]), bool(rng.random() < p["hot"])))
        weekday, dom = (weekday + 1) % 7, dom + 1
        if dom > MONTH_DAYS[month - 1]:
            dom, month = 1, month % 12 + 1
    return out


def sample_wardrobe(pool: dict[str, list[Garment]], size_range, minimums: dict, rng) -> list[Garment]:
    size = int(rng.integers(size_range[0], size_range[1] + 1))
    chosen: list[Garment] = []
    for slot, k in minimums.items():
        cand = pool.get(slot, [])
        if len(cand) < k:
            raise ValueError(f"not enough unseen {slot} items for wardrobes")
        chosen += [cand[i] for i in rng.choice(len(cand), k, replace=False)]
    taken = {g.id for g in chosen}
    rest = [g for gs in pool.values() for g in gs if g.id not in taken]
    extra = max(0, size - len(chosen))
    chosen += [rest[i] for i in rng.choice(len(rest), min(extra, len(rest)), replace=False)]
    return chosen


def candidate_outfits(w: list[Garment], rng, cap: int) -> list[tuple[Garment, ...]]:
    """At most one item per slot: (top + bottom | dress) + footwear, optional outer (3.4.3, rule a)."""
    by = {s: [g for g in w if g.slot == s] for s in ("top", "bottom", "dress", "footwear", "outer")}
    bases = [(t, b) for t, b in product(by["top"], by["bottom"])] + [(d,) for d in by["dress"]]
    outs = []
    for base, f in product(bases, by["footwear"]):
        outs.append((*base, f))
        outs += [(*base, f, o) for o in by["outer"]]
    if len(outs) > cap:
        outs = [outs[i] for i in sorted(rng.choice(len(outs), cap, replace=False))]
    return outs


def passes(o: tuple[Garment, ...], rain: bool, hot: bool, occasion: str) -> bool:
    if hot and any(g.warmth == "heavy" for g in o if g.slot == "outer"):
        return False
    if rain and not any(g.rain for g in o if g.slot in ("footwear", "outer")):
        return False
    if occasion == "worship" and not (any(g.long_sleeve for g in o if g.slot in ("top", "dress", "outer"))
                                      and any(g.long_bottom for g in o if g.slot in ("bottom", "dress"))):
        return False
    if occasion == "wedding" and not any(g.formal for g in o):
        return False
    return True


class UserSim:
    """One simulated user: vectorised Eq. 7 scoring over the user's candidate outfits."""

    def __init__(self, wardrobe: list[Garment], outfit_comp: Callable[[tuple], float], rng, cap: int):
        self.wardrobe = wardrobe
        self.gidx = {g.id: n for n, g in enumerate(wardrobe)}
        self.outfits = candidate_outfits(wardrobe, rng, cap)
        width = max(len(o) for o in self.outfits)
        self.G = np.full((len(self.outfits), width), -1, dtype=np.int64)
        for r, o in enumerate(self.outfits):
            self.G[r, :len(o)] = [self.gidx[g.id] for g in o]
        self.valid = self.G >= 0
        self.n_items = self.valid.sum(axis=1)
        self.comp = np.array([outfit_comp(o) for o in self.outfits])
        self.likes = rng.beta(2, 2, len(wardrobe))  # latent liking (favourite behaviour)
        self._masks: dict = {}
        self.weather_fit = {}

    def mask(self, rain: bool, hot: bool, occasion: str) -> np.ndarray:
        key = (rain, hot, occasion)
        if key not in self._masks:
            m = np.array([passes(o, rain, hot, occasion) for o in self.outfits])
            self._masks[key] = m if m.any() else np.ones(len(self.outfits), dtype=bool)  # never leave a day empty
        return self._masks[key]

    def _per_outfit(self, garment_values: np.ndarray) -> np.ndarray:
        v = np.where(self.valid, garment_values[np.clip(self.G, 0, None)], 0.0)
        return v.sum(axis=1) / self.n_items

    def _weather_fit(self, rain: bool, hot: bool) -> np.ndarray:
        key = (rain, hot)
        if key not in self.weather_fit:
            per_g = np.array([(g.rain and g.slot in ("footwear", "outer") and rain) +
                              ((g.warmth == "light") if hot else (g.warmth != "light")) for g in self.wardrobe], float)
            self.weather_fit[key] = np.where(self.valid, per_g[np.clip(self.G, 0, None)], 0.0).sum(axis=1)
        return self.weather_fit[key]

    def run(self, day_list: list[Day], variant: str, behaviour: str, w: tuple, h: float, p0: float, a: float,
            rng, top: int = 5) -> dict:
        n = len(self.wardrobe)
        chosen, recommended = np.zeros(n), np.zeros(n)
        last = np.full(n, -np.inf)
        worn = np.zeros(n, dtype=bool)
        comp_worn, satisfied = [], 0
        w1, w2, w3 = w
        if variant == "no_recency":
            w3 = 0.0
        for day in day_list:
            rules = variant not in ("compatibility_only", "no_context")
            allowed = self.mask(day.rain, day.hot, day.occasion) if rules else np.ones(len(self.outfits), bool)
            if variant == "compatibility_only":
                score = self.comp.copy()
            else:
                pref = (chosen + a * p0) / (recommended + a)
                rec = np.exp(-(day.index - last) / h)  # never worn: exp(-inf) = 0
                score = w1 * self.comp + w2 * self._per_outfit(pref) - w3 * self._per_outfit(rec)
            score = np.where(allowed, score, -np.inf)
            k = min(top, int(allowed.sum()))
            shown = np.argsort(-score, kind="stable")[:k]
            for r in shown:
                recommended[self.G[r][self.valid[r]]] += 1
            if behaviour == "random":
                pick = shown[int(rng.integers(len(shown)))]
            elif behaviour == "favourite":
                pick = shown[np.argmax(self._per_outfit(self.likes)[shown])]
            else:
                pick = shown[np.argmax(self._weather_fit(day.rain, day.hot)[shown])]
            items = self.G[pick][self.valid[pick]]
            chosen[items] += 1
            last[items] = day.index
            worn[items] = True
            comp_worn.append(self.comp[pick])
            satisfied += passes(self.outfits[pick], day.rain, day.hot, day.occasion)
        return {"coverage": float(worn.mean()), "compat_worn": float(np.mean(comp_worn)),
                "rule_satisfaction": satisfied / len(day_list)}
