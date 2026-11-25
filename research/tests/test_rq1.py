"""RQ1 pipeline mechanics on hand-computed cases and SYNTHETIC data (synthetic_only; never a reported result)."""
from __future__ import annotations

import math

import numpy as np
import pytest

from synth_rq1 import SYNTH_MANIFEST, make
from wearhouse_research.core import ROOT, ManifestError, TestDataAccess, for_selection, load_config
from wearhouse_research.rq1 import metrics as M
from wearhouse_research.rq1.data import chronological_split, genz_cohort, owned_before
from wearhouse_research.rq1.run import run

pytestmark = pytest.mark.synthetic_only


def test_metrics_match_hand_values():
    rec, truth = ["a", "b", "c"], {"a", "c"}
    assert M.ap_at_k(rec, truth) == pytest.approx((1 / 1 + 2 / 3) / 2)
    assert M.recall_at_k(rec, truth) == 1.0
    assert M.ndcg_at_k(rec, truth) == pytest.approx((1 + 1 / math.log2(4)) / (1 + 1 / math.log2(3)))
    assert M.ap_at_k(["x"], set()) == 0.0
    truth = {f"i{n}" for n in range(20)}
    assert M.ap_at_k(sorted(truth)[:12], truth) == 1.0  # oracle: normalised by min(|truth|, 12)
    assert M.duplicate_share(["a", "b", "c", "d"], lambda i: i in {"a", "d"}) == 0.5


def test_bootstrap_is_deterministic_and_zero_rule_defined():
    v = np.arange(100, dtype=float)
    assert M.bootstrap_ci(v, seed=3) == M.bootstrap_ci(v, seed=3)
    ci = M.bootstrap_ci(v, seed=3)
    assert ci["lo"] < ci["mean"] < ci["hi"]
    assert M.relative_change(0.2, 0.0)["relative"] is None
    assert M.relative_change(0.11, 0.1)["relative"] == pytest.approx(0.1)


def test_split_is_chronological_and_owned_excludes_evaluated_week():
    tx, customers, _ = make(n_users=60, weeks=4)
    s = chronological_split(tx)
    assert s.train.data["t_dat"].max() < s.validation_start <= s.validation.data["t_dat"].min()
    assert s.validation.data["t_dat"].max() < s.test_start <= s.test.data["t_dat"].min()
    users, cohort = genz_cohort(customers, s.test.data)
    ages = customers.set_index("customer_id")["age"]
    assert all(ages[u] <= 23 for u in users) and cohort["missing_age_excluded"] > 0
    owned = owned_before(tx, s.test_start, users)
    assert all(tx[(tx["customer_id"] == u) & tx["article_id"].isin(owned[u])]["t_dat"].min() < s.test_start
               for u in users if owned[u])
    with pytest.raises(TestDataAccess):
        for_selection(s.test)


def test_end_to_end_synthetic_run(tmp_path):
    tx, customers, articles = make()
    cfg = load_config(ROOT / "research" / "configs" / "rq1.json")
    cfg.update(train_weeks=None, bpr={"factors": 16, "lr": 0.05, "reg": 0.001, "epochs": 15, "batch": 1024},
               bootstrap_resamples=200, candidates=60)
    rep = run(cfg, out_dir=tmp_path, log=lambda *_: None, data=(tx, customers, articles, [SYNTH_MANIFEST]))
    methods = rep["result"]["test"]["methods"]
    assert set(methods) == {"popularity", "item_knn", "bpr", "first_stage", "reranked"}
    assert methods["bpr"]["map@12"]["mean"] > methods["popularity"]["map@12"]["mean"]  # planted preference found
    assert methods["reranked"]["duplicate_share"]["mean"] <= methods["first_stage"]["duplicate_share"]["mean"]
    assert rep["result"]["selection"]["split"] == "validation"
    assert rep["declared"]["content_embedding"] == "text_attributes"
    assert rep["provenance"]["datasets"]["synthetic_hm"]["synthetic"] is True
    with pytest.raises(ManifestError):  # synthetic results can never land in research/reports/
        run(cfg, log=lambda *_: None, data=(tx, customers, articles, [SYNTH_MANIFEST]))


def test_real_run_refuses_without_a_permitted_manifest(tmp_path):
    """The real runner never touches data unless its manifest is present, permitted and checksum-verified."""
    cfg = load_config(ROOT / "research" / "configs" / "rq1.json")
    cfg["manifest"] = str(tmp_path / "missing_manifest.json")
    with pytest.raises(ManifestError, match="manifest not found"):
        run(cfg)


def test_shared_score_selection_equals_reference():
    """The speed-up (catalogue scores and duplicate flags computed once per customer, reused across the alpha and
    lambda_d grids) must give exactly the original selection, and the reranker reuse exactly recommend()."""
    from wearhouse_research.rq1 import run as R
    from wearhouse_research.rq1.models import Catalogue, Duplicates, FirstStage, Reranker

    tx, customers, articles = make()
    cfg = load_config(ROOT / "research" / "configs" / "rq1.json")
    cfg.update(train_weeks=None, bpr={"factors": 16, "lr": 0.05, "reg": 0.001, "epochs": 5, "batch": 1024},
               candidates=60, tau=0.5)
    cat = Catalogue(articles)
    split = chronological_split(tx)
    dup = Duplicates(cat, cfg["tau"])
    (val_week,) = for_selection(split.validation)
    vph = R._phase(tx[tx["t_dat"] < split.test_start], customers, cat, cfg, cutoff=split.validation_start,
                   evaluated=val_week, seed=cfg["seed"])
    new, ref = R._select(vph, cat, dup, cfg), R._select_reference(vph, cat, dup, cfg)
    assert new == ref
    assert ref[3] > 0  # the synthetic data has duplicates, so the flags path is exercised
    first = FirstStage(cat, vph["bpr"], ref[1], cfg["candidates"])
    for lam in cfg["lambda_d_grid"]:
        rr = Reranker(first, dup, lam)
        for u in vph["users"]:
            o = vph["owned"][u]
            idx, s1 = first.top(u, o)
            assert rr.recommend_from(idx, s1, dup.flags(idx, o), o) == rr.recommend(u, o)


def test_export_artifacts_are_sha_pinned(tmp_path):
    import hashlib
    import json

    from wearhouse_research.export import from_bpr, from_itemknn
    from wearhouse_research.rq1.models import BPR, Catalogue, ItemKNN
    tx, _, articles = make(n_users=60, weeks=3)
    cat = Catalogue(articles)
    bpr = BPR(factors=8, epochs=2, seed=1).fit(cat, tx)
    out = from_bpr(bpr, tmp_path / "bpr", k=5, namespace="hm-format-synthetic", version="t1", report=None, datasets={})
    m = json.loads((out / "manifest.json").read_text())
    assert m["mode"] == "trained" and len(m["model_hash"]) == 64
    assert m["files"]["neighbours.csv"] == hashlib.sha256((out / "neighbours.csv").read_bytes()).hexdigest()
    knn_out = from_itemknn(ItemKNN(cat, tx), tmp_path / "knn", k=5, namespace="x", version="t1", report=None, datasets={})
    assert json.loads((knn_out / "manifest.json").read_text())["mode"] == "heuristic_baseline"
