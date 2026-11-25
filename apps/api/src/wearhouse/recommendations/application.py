"""Outfit suggestions (pure), aligned with thesis §3.4.3 and Eqs. 7–9 (align-wearhouse-outfit-recommender).

1. Candidates: per slot the top-M items by item value (preference − recency), then top+bottom or dress, footwear, optional
   outer layer; a final exact check of the hard rules (rules.failed_rule) on every combination.
2. Score (Eq. 7): w1·compatibility + w2·mean preference − w3·mean recency, with
   preference (Eq. 8) = (chosen + a·p0)/(recommended + a) and recency (Eq. 9) = exp(−days_since_worn/h), 0 if never worn.
3. At most `limit` suggestions with distinct cores (no two share their top+bottom or dress).
Compatibility is the labelled heuristic baseline (no trained model is claimed); unknown colours count as 0.5 and say so.
The defaults (0.5/0.3/0.2, p0 0.5, a 5, h 4) are the demo baselines, not tuned research settings.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from itertools import product
from typing import Sequence

from .baseline import BASELINE_MODEL, HeuristicCompatibility
from .ports import ItemFeatures
from .domain import RULE_TEXT, RULESET_ID, failed_rule

DEFAULT_WEIGHTS = {"compatibility": 0.5, "preference": 0.3, "recency": 0.2}
P0, A, H = 0.5, 5.0, 4.0
TOP_M = 8
CORE_SLOTS = ("top", "bottom", "dress")


@dataclass(frozen=True)
class WeatherContext:
    rain: bool | None
    hot: bool | None
    source: str  # LIVE | CACHED | MANUAL | NONE | DISABLED


@dataclass(frozen=True)
class ItemStats:
    chosen: int = 0           # recommendation runs whose chosen outfit contained the item
    recommended: int = 0      # recommendation runs that displayed the item (deduplicated per run)
    days_since_worn: float | None = None


def preference(s: ItemStats, p0: float = P0, a: float = A) -> float:
    """Eq. 8."""
    return (s.chosen + a * p0) / (s.recommended + a)


def recency(s: ItemStats, h: float = H) -> float:
    """Eq. 9: never worn contributes zero."""
    return 0.0 if s.days_since_worn is None else math.exp(-max(s.days_since_worn, 0.0) / h)


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs)


class OutfitSuggester:
    model = BASELINE_MODEL

    def __init__(self):
        self.compat = HeuristicCompatibility()

    def candidates(self, items: Sequence[ItemFeatures], stats: dict[str, ItemStats], top_m: int = TOP_M
                   ) -> tuple[list[tuple[ItemFeatures, ...]], list[str]]:
        def value(i: ItemFeatures) -> tuple:
            s = stats.get(i.item_id, ItemStats())
            return (-(preference(s) - recency(s)), i.item_id)

        by = {s: sorted((i for i in items if i.slot == s), key=value)[:top_m]
              for s in ("top", "bottom", "dress", "footwear", "outer")}
        reasons = []
        if not by["footwear"]:
            reasons.append("missing_slot: footwear")
        if not (by["top"] and by["bottom"]) and not by["dress"]:
            reasons.append("missing_slot: top+bottom or dress")
        if reasons:
            return [], reasons
        bases = [(t, b) for t, b in product(by["top"], by["bottom"])] + [(d,) for d in by["dress"]]
        out: list[tuple[ItemFeatures, ...]] = []
        for base, shoe in product(bases, by["footwear"]):
            out.append((*base, shoe))
            out.extend((*base, shoe, outer) for outer in by["outer"])
        return out, []

    def suggest(self, items: Sequence[ItemFeatures], *, attrs: dict[str, dict], stats: dict[str, ItemStats],
                weather: WeatherContext, occasion: str, limit: int, weights: dict[str, float] | None = None,
                style: str = "balanced") -> dict:
        w = weights or DEFAULT_WEIGHTS
        combos, reasons = self.candidates(items, stats)
        removed: dict[str, int] = {}
        ranked = []
        for combo in combos:
            rule = failed_rule([(i.slot, attrs[i.item_id]) for i in combo], rain=weather.rain, hot=weather.hot,
                               occasion=occasion)
            if rule:
                removed[rule] = removed.get(rule, 0) + 1
                continue
            compat = self.compat.score(combo)
            st = [stats.get(i.item_id, ItemStats()) for i in combo]
            comps = {"compatibility": round(compat, 4) if compat is not None else None,
                     "preference": round(_mean([preference(s) for s in st]), 4),
                     "recency": round(_mean([recency(s) for s in st]), 4)}
            score = (w["compatibility"] * (compat if compat is not None else 0.5)
                     + w["preference"] * comps["preference"] - w["recency"] * comps["recency"])
            ranked.append((round(score, 4), comps, combo))
        ranked.sort(key=lambda r: (-r[0], tuple(i.item_id for i in r[2])))
        chosen, cores = [], set()
        for score, comps, combo in ranked:
            core = tuple(i.item_id for i in combo if i.slot in CORE_SLOTS)
            if core in cores:
                continue
            cores.add(core)
            chosen.append((score, comps, combo))
            if len(chosen) == limit:
                break
        if combos and not ranked:
            reasons.append("no outfit passes the rules: " + "; ".join(
                f"{RULE_TEXT[k]} ({n} removed)" for k, n in sorted(removed.items())))
        return {
            "model": {"mode": self.model.mode.value, "name": self.model.name, "version": self.model.version,
                      "trained_artifact": self.model.trained_artifact},
            "ruleset": RULESET_ID, "occasion": occasion,
            "weather": {"source": weather.source, "rain": weather.rain, "hot": weather.hot},
            "style": style, "weights": dict(w), "params": {"p0": P0, "a": A, "h": H, "top_m": TOP_M},
            "candidates_considered": len(combos), "removed_by_rule": removed, "reasons": reasons,
            "suggestions": [{"item_ids": [i.item_id for i in combo], "slots": {i.item_id: i.slot for i in combo},
                             "score": score, "components": comps,
                             "explanation": self._explain(combo, comps, attrs, stats, weather, occasion)}
                            for score, comps, combo in chosen],
        }

    @staticmethod
    def _explain(combo, comps, attrs, stats, weather: WeatherContext, occasion: str) -> list[str]:
        out = []
        if weather.rain:
            rainy = [i for i in combo if i.slot in ("footwear", "outer") and attrs[i.item_id]["rain_suitable"]]
            out.append(f"Rain-ready: {rainy[0].slot} is rain-suitable.")
        if weather.hot:
            out.append("Hot day: no heavy outerwear.")
        if weather.rain is None and weather.hot is None:
            out.append("Weather unknown: rain and heat rules not applied.")
        if occasion == "worship":
            out.append("Worship: long sleeves and a long bottom.")
        if occasion == "wedding":
            out.append("Wedding: includes a formal piece.")
        if comps["compatibility"] is None:
            out.append("Colour compatibility unknown (colours missing); counted as neutral.")
        worn = [stats[i.item_id].days_since_worn for i in combo
                if i.item_id in stats and stats[i.item_id].days_since_worn is not None]
        out.append(f"Most recently worn piece: {int(min(worn))} day(s) ago." if worn else "None of these worn recently.")
        return out
