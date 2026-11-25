"""3.7 recommendation ports: deterministic heuristic baseline, truthful mode metadata, unknowns not invented.

Reference values were produced by the frozen legacy implementation (legacy/python/app/scoring.py::compat at
ea21b05) and are pinned here as literals; v2 does not import legacy code.
"""
from __future__ import annotations

import pytest

from wearhouse.recommendations.baseline import BASELINE_MODEL, HeuristicCompatibility, HeuristicOutfitRanker
from wearhouse.recommendations.ports import ItemFeatures, ModelInfo, RankerMode

LEGACY_REFERENCE = [
    ([("#000000", "casual"), ("#F4B6C2", "smart"), ("#1E3A8A", "formal")], 0.708333),
    ([("#FF0000", "street"), ("#00FFFF", "sporty")], 0.8),
    ([("#FF0000", "casual"), ("#FF4500", "casual"), ("#FFD700", "modest")], 0.775),
    ([("#3CB371", "formal"), ("#8A2BE2", "street")], 0.375),
]


def items(spec):
    return [ItemFeatures(item_id=str(i), slot="top", colour_hex=h, style=s) for i, (h, s) in enumerate(spec)]


@pytest.mark.parametrize("spec,expected", LEGACY_REFERENCE)
def test_baseline_matches_legacy_reference(spec, expected):
    assert round(HeuristicCompatibility().score(items(spec)), 6) == expected


def test_baseline_is_deterministic_and_labelled_heuristic():
    cands = [items(s) for s, _ in LEGACY_REFERENCE]
    r1 = HeuristicOutfitRanker().rank(cands, k=3)
    r2 = HeuristicOutfitRanker().rank(list(reversed(cands)), k=3)
    assert r1 == r2
    assert r1.model.mode is RankerMode.HEURISTIC_BASELINE
    assert r1.model.trained_artifact is None
    assert r1.model.version == BASELINE_MODEL.version
    assert [o.score for o in r1.outfits] == sorted((o.score for o in r1.outfits), reverse=True)


def test_unknown_attributes_are_not_defaulted():
    unknown = [ItemFeatures("a", "top"), ItemFeatures("b", "bottom")]
    assert HeuristicCompatibility().score(unknown) is None  # legacy would have assumed grey + casual
    partial = [ItemFeatures("a", "top", style="smart"), ItemFeatures("b", "bottom", style="formal")]
    assert HeuristicCompatibility().score(partial) == 0.8
    assert HeuristicOutfitRanker().rank([unknown], k=5).outfits == ()


def test_heuristic_cannot_claim_trained_and_trained_needs_artifact():
    with pytest.raises(ValueError):
        ModelInfo(RankerMode.HEURISTIC_BASELINE, "x", "1", trained_artifact="fashionclip.pt")
    with pytest.raises(ValueError):
        ModelInfo(RankerMode.TRAINED, "fashionclip", "1")
    assert ModelInfo(RankerMode.TRAINED, "fashionclip", "1", trained_artifact="sha256:abc").mode is RankerMode.TRAINED
