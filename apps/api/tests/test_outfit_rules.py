"""align-wearhouse-outfit-recommender 1.1: thesis hard rules, appendix lookup parity with RQ2, Eqs. 7–9 (pure)."""
from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from wearhouse.recommendations.application import (ItemStats, OutfitSuggester, WeatherContext, preference, recency)
from wearhouse.recommendations.ports import ItemFeatures
from wearhouse.recommendations.domain import ATTRIBUTE_RULES, OCCASIONS, derive, failed_rule

RQ2_CONFIG = Path(__file__).resolve().parents[3] / "research" / "configs" / "rq2.json"
NONE = WeatherContext(None, None, "NONE")


def test_same_vocabulary_as_the_research():
    if not RQ2_CONFIG.exists():
        pytest.skip("research workspace not present")
    research = json.loads(RQ2_CONFIG.read_text(encoding="utf-8"))["attribute_rules"]
    assert {k: v for k, v in research.items() if k != "note"} == ATTRIBUTE_RULES
    assert set(json.loads(RQ2_CONFIG.read_text(encoding="utf-8"))["schedule"]["weekday"]) <= set(OCCASIONS)


def test_appendix_lookup():
    assert derive("outer", "Wool coat")["warmth"] == "heavy"
    assert derive("top", "Linen tee")["warmth"] == "light"
    assert derive("bottom", "Cargo trousers")["warmth"] == "medium"  # slot default
    assert derive("footwear", "Chelsea boots")["rain_suitable"] is True
    assert derive("top", "Rain jacket")["rain_suitable"] is False  # rain-suitability counts for footwear/outer only
    assert derive("outer", "Anything")["long_sleeve"] is True
    assert derive("bottom", "Denim shorts")["long_bottom"] is False
    assert derive("dress", "Maxi dress")["long_bottom"] is True
    assert derive("footwear", "Satin heels")["formal"] is True


def a(**over):
    base = {"warmth": "light", "rain_suitable": False, "long_sleeve": False, "long_bottom": False, "formal": False}
    return {**base, **over}


def test_hard_rules():
    outfit = [("top", a()), ("bottom", a(long_bottom=True)), ("footwear", a()), ("outer", a(warmth="heavy"))]
    assert failed_rule(outfit, rain=False, hot=True, occasion="casual") == "heat"
    assert failed_rule(outfit[:3], rain=True, hot=False, occasion="casual") == "rain"
    assert failed_rule(outfit[:3], rain=None, hot=None, occasion="casual") is None  # unknown weather: no weather rule
    assert failed_rule(outfit[:3], rain=False, hot=False, occasion="worship") == "worship_dress_code"
    assert failed_rule([("top", a(long_sleeve=True)), *outfit[1:3]], rain=False, hot=False, occasion="worship") is None
    assert failed_rule(outfit[:3], rain=False, hot=False, occasion="wedding") == "wedding_dress_code"


def test_preference_and_recency_maths():
    assert preference(ItemStats()) == 0.5  # a new item starts at p0
    assert preference(ItemStats(chosen=4, recommended=5)) == pytest.approx(0.65)
    assert recency(ItemStats()) == 0.0  # never worn
    assert recency(ItemStats(days_since_worn=1)) == pytest.approx(math.exp(-0.25))
    assert recency(ItemStats(days_since_worn=0)) > recency(ItemStats(days_since_worn=3))


def wardrobe():
    items = [ItemFeatures("t1", "top", "#1F1F1F"), ItemFeatures("t2", "top", "#1F1F1F"),
             ItemFeatures("b1", "bottom", "#F2F2F2"), ItemFeatures("s1", "footwear", "#1F1F1F"),
             ItemFeatures("s2", "footwear", "#1F1F1F")]
    attrs = {"t1": a(), "t2": a(), "b1": a(long_bottom=True), "s1": a(), "s2": a(rain_suitable=True)}
    return items, attrs


def test_recently_worn_ranks_lower_and_cores_are_distinct():
    items, attrs = wardrobe()
    out = OutfitSuggester().suggest(items, attrs=attrs, stats={"t1": ItemStats(days_since_worn=1)}, weather=NONE,
                                    occasion="casual", limit=5)
    first = out["suggestions"][0]
    assert "t2" in first["item_ids"] and first["components"]["recency"] == 0.0
    cores = [tuple(i for i in s["item_ids"] if i in ("t1", "t2", "b1")) for s in out["suggestions"]]
    assert len(cores) == len(set(cores)) == 2  # (t1,b1) and (t2,b1): the shoe choice never repeats a core
    assert out["ruleset"] == "wardrobe-rules@1" and out["params"]["h"] == 4.0


def test_rain_keeps_only_rain_ready_and_explains_when_nothing_passes():
    items, attrs = wardrobe()
    rain = WeatherContext(True, False, "LIVE")
    out = OutfitSuggester().suggest(items, attrs=attrs, stats={}, weather=rain, occasion="casual", limit=5)
    assert out["suggestions"] and all("s2" in s["item_ids"] for s in out["suggestions"])
    assert out["removed_by_rule"]["rain"] > 0
    attrs["s2"] = a()
    none = OutfitSuggester().suggest(items, attrs=attrs, stats={}, weather=rain, occasion="casual", limit=5)
    assert none["suggestions"] == [] and "no outfit passes the rules" in none["reasons"][-1]


def test_preference_evidence_lifts_an_item():
    items, attrs = wardrobe()
    liked = {"t1": ItemStats(chosen=4, recommended=5), "t2": ItemStats(chosen=0, recommended=5)}
    out = OutfitSuggester().suggest(items, attrs=attrs, stats=liked, weather=NONE, occasion="casual", limit=1)
    assert "t1" in out["suggestions"][0]["item_ids"]
