"""Phase 1 — Rules & Scoring core (pure functions, no DB/HTTP). TDD §4 Phase 1 tests 1–12."""
import math
import random
import time
from datetime import date, timedelta

from app.domain import Garment, Outfit
from app.rules import Context, allowed, candidates
from app.scoring import pref, recency, recommend, score
from app.seed_data import seed_wardrobe

TODAY = date(2026, 11, 24)


def g(id, slot, **kw):
    return Garment(id=id, name=id, slot=slot, **kw)


TOP = g("top", "top", long_sleeve=True, formality=3)
BOTTOM = g("bottom", "bottom", long_bottom=True, formality=3)
DRESS = g("dress", "dress", formality=3)
SHOES = g("shoes", "footwear", formality=3)
RAIN_SHOES = g("rainshoes", "footwear", rain_suitable=True)
RAINCOAT = g("raincoat", "outer", rain_suitable=True)
HEAVY_COAT = g("heavycoat", "outer", heavy=True)


# 1
def test_rain_rule_requires_rain_footwear_or_outer_when_rain_true():
    rain = Context(rain=True, hot=False, occasion="casual")
    assert not allowed(Outfit((TOP, BOTTOM, SHOES)), rain)
    assert allowed(Outfit((TOP, BOTTOM, RAIN_SHOES)), rain)
    assert allowed(Outfit((TOP, BOTTOM, SHOES, RAINCOAT)), rain)


# 2
def test_rain_rule_ignores_footwear_when_rain_false():
    dry = Context(rain=False, hot=False, occasion="casual")
    assert allowed(Outfit((TOP, BOTTOM, SHOES)), dry)
    assert allowed(Outfit((TOP, BOTTOM, RAIN_SHOES)), dry)


# 3
def test_heat_rule_removes_heavy_outer_when_hot():
    hot = Context(rain=False, hot=True, occasion="casual")
    normal = Context(rain=False, hot=False, occasion="casual")
    o = Outfit((TOP, BOTTOM, SHOES, HEAVY_COAT))
    assert allowed(o, normal)
    assert not allowed(o, hot)
    wardrobe = [TOP, BOTTOM, SHOES, HEAVY_COAT]
    assert all(HEAVY_COAT not in c.items for c in candidates(wardrobe, hot))


# 4
def test_slot_rule_rejects_top_plus_dress_combination():
    ctx = Context(rain=False, hot=False, occasion="casual")
    assert not allowed(Outfit((TOP, DRESS, SHOES)), ctx)
    assert allowed(Outfit((DRESS, SHOES)), ctx)


# 5
def test_slot_rule_requires_footwear():
    ctx = Context(rain=False, hot=False, occasion="casual")
    assert not allowed(Outfit((TOP, BOTTOM)), ctx)
    assert not allowed(Outfit((DRESS,)), ctx)


def test_slot_rule_rejects_two_items_in_one_slot():
    ctx = Context(rain=False, hot=False, occasion="casual")
    assert not allowed(Outfit((TOP, g("top2", "top"), BOTTOM, SHOES)), ctx)


# 6
def test_worship_requires_long_sleeve_and_long_bottom():
    ctx = Context(rain=False, hot=False, occasion="worship")
    short_top = g("tee", "top", long_sleeve=False)
    short_skirt = g("skirt", "bottom", long_bottom=False)
    assert allowed(Outfit((TOP, BOTTOM, SHOES)), ctx)
    assert not allowed(Outfit((short_top, BOTTOM, SHOES)), ctx)
    assert not allowed(Outfit((TOP, short_skirt, SHOES)), ctx)
    # a long-sleeve outer covers a short-sleeve top
    cardigan = g("cardigan", "outer", long_sleeve=True)
    assert allowed(Outfit((short_top, BOTTOM, SHOES, cardigan)), ctx)
    long_dress = g("maxi", "dress", long_sleeve=True, long_bottom=True)
    assert allowed(Outfit((long_dress, SHOES)), ctx)
    assert not allowed(Outfit((DRESS, SHOES)), ctx)


# 7
def test_wedding_requires_formality_at_least_3():
    ctx = Context(rain=False, hot=False, occasion="wedding")
    assert allowed(Outfit((TOP, BOTTOM, SHOES)), ctx)
    sneakers = g("sneakers", "footwear", formality=1)
    assert not allowed(Outfit((TOP, BOTTOM, sneakers)), ctx)
    casual_top = g("tee", "top", formality=2)
    assert not allowed(Outfit((casual_top, BOTTOM, SHOES)), ctx)


# 8
def test_pref_new_garment_starts_at_half():
    assert pref(g("new", "top")) == 0.5


def test_pref_moves_toward_choice_rate_with_evidence():
    little = g("a", "top", times_recommended=10, times_chosen=8)
    lots = g("b", "top", times_recommended=100, times_chosen=80)
    assert 0.5 < pref(little) < pref(lots) < 0.8
    never = g("c", "top", times_recommended=100, times_chosen=0)
    assert pref(never) < pref(g("d", "top", times_recommended=5, times_chosen=0)) < 0.5


# 9
def test_recency_penalty_highest_when_worn_yesterday_and_decays():
    yesterday = recency(g("a", "top", last_worn_at=TODAY - timedelta(days=1)), TODAY)
    three = recency(g("b", "top", last_worn_at=TODAY - timedelta(days=3)), TODAY)
    ten = recency(g("c", "top", last_worn_at=TODAY - timedelta(days=10)), TODAY)
    assert yesterday > three > ten > 0
    assert math.isclose(yesterday, math.exp(-1 / 4.0))


def test_never_worn_has_zero_penalty():
    assert recency(g("a", "top"), TODAY) == 0.0


def test_score_is_weighted_sum_of_compat_pref_minus_recency():
    o = Outfit((TOP, BOTTOM, SHOES))
    worn = Outfit((TOP, BOTTOM, g("shoes", "footwear", formality=3, last_worn_at=TODAY - timedelta(days=1))))
    assert score(worn, TODAY) < score(o, TODAY)


# 10
def test_recommend_returns_at_most_five_sorted_descending():
    ctx = Context(rain=False, hot=False, occasion="casual")
    recs = recommend(seed_wardrobe(), ctx, TODAY)
    assert 1 <= len(recs) <= 5
    scores = [r.score for r in recs]
    assert scores == sorted(scores, reverse=True)


# 11
def test_recommend_returns_empty_list_not_error_when_no_outfit_allowed():
    ctx = Context(rain=True, hot=False, occasion="casual")
    assert recommend([TOP, BOTTOM, SHOES], ctx, TODAY) == []
    assert recommend([], ctx, TODAY) == []


# 12
def test_every_recommended_outfit_passes_allowed():
    rng = random.Random(2026)
    wardrobe = seed_wardrobe()
    occasions = ["campus", "casual", "worship", "formal", "wedding"]
    for _ in range(200):
        ctx = Context(rain=rng.random() < 0.5, hot=rng.random() < 0.5, occasion=rng.choice(occasions))
        for r in recommend(wardrobe, ctx, TODAY):
            assert allowed(r.outfit, ctx), (ctx, r)


def test_candidate_generation_for_seed_wardrobe_within_150ms():
    wardrobe = seed_wardrobe()
    ctx = Context(rain=False, hot=False, occasion="casual")
    t0 = time.perf_counter()
    candidates(wardrobe, ctx)
    assert (time.perf_counter() - t0) * 1000 < 150
