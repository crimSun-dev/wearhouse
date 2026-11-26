"""RQ2 pipeline mechanics on SYNTHETIC Polyvore-format data (synthetic_only; never a reported result)."""
from __future__ import annotations

import numpy as np
import pytest

from synth_rq2 import SYNTH_MANIFEST, write
from wearhouse_research.core import ROOT, ManifestError, Split, TestDataAccess, load_config
from wearhouse_research.rq2.compat import TextEmbedding, TypeAwareModel, auc, fitb_accuracy, make_triplets
from wearhouse_research.rq2.data import load, overlap_audit, unseen_items
from wearhouse_research.rq2.run import grid_search, run
from wearhouse_research.rq2.simulate import UserSim, attributes, days, passes, sample_wardrobe

pytestmark = pytest.mark.synthetic_only


def small_cfg():
    cfg = load_config(ROOT / "research" / "configs" / "rq2.json")
    cfg.update(users_tuning=4, users_reporting=4, seeds=[1, 2], days=14, candidate_outfit_cap=120,
               weight_grid=[[1, 0, 0], [1, 1, 1]], h_grid=[2, 5], wardrobe_size=[12, 16],
               model={"dim": 16, "margin": 0.2, "lr": 0.05, "reg": 0.0001, "epochs": 4}, embedding_dims=16)
    return cfg


def test_loader_resolves_refs_and_audit_finds_overlap(tmp_path):
    pv = load(write(tmp_path / "a"))
    assert len(pv.outfits["train"]) == 160 and pv.compatibility["test"] and pv.fitb["test"]
    assert all(0 <= q["correct"] < 4 for q in pv.fitb["test"])
    assert overlap_audit(pv)["thesis_claim_P0390_holds"] in (True, False)
    pv2 = load(write(tmp_path / "b", overlap=5))
    audit = overlap_audit(pv2)
    assert audit["test_items_seen_in_training"] >= 1 and audit["thesis_claim_P0390_holds"] is False
    assert not unseen_items(pv2) & pv2.outfit_items("train")


def test_analytic_gradients_match_numeric():
    rng = np.random.default_rng(0)
    m = TypeAwareModel(6, dim=4, margin=5.0, seed=1)
    m.masks[("a", "b")] = rng.normal(size=4)
    m.masks[("a", "a")] = rng.normal(size=4)
    xa, xp, xn = (rng.normal(size=6) for _ in range(3))
    loss, gW, gm = m.triplet_grads(xa, xp, xn, "a", "b", "a")
    assert loss > 0
    eps = 1e-6
    for (r, c) in [(0, 0), (3, 2), (5, 1)]:
        m.W[r, c] += eps
        up = m.triplet_grads(xa, xp, xn, "a", "b", "a")[0]
        m.W[r, c] -= 2 * eps
        down = m.triplet_grads(xa, xp, xn, "a", "b", "a")[0]
        m.W[r, c] += eps
        assert gW[r, c] == pytest.approx((up - down) / (2 * eps), rel=1e-4, abs=1e-6)
    k = ("a", "b")
    m.masks[k][2] += eps
    up = m.triplet_grads(xa, xp, xn, "a", "b", "a")[0]
    m.masks[k][2] -= 2 * eps
    down = m.triplet_grads(xa, xp, xn, "a", "b", "a")[0]
    m.masks[k][2] += eps
    assert gm[k][2] == pytest.approx((up - down) / (2 * eps), rel=1e-4, abs=1e-6)


def test_random_embeddings_score_chance_and_training_learns(tmp_path):
    pv = load(write(tmp_path / "c"))
    ids = list(pv.items)
    types = {i: pv.type_of(i) for i in ids}
    rng = np.random.default_rng(5)
    noise = {i: rng.normal(size=16) for i in ids}
    m0 = TypeAwareModel(16, dim=8, seed=2)
    rows = pv.compatibility["test"]
    a0 = auc([m0.outfit_compat(noise, types, x) for l, x in rows if l], [m0.outfit_compat(noise, types, x) for l, x in rows if not l])
    assert 0.3 < a0 < 0.7  # random features: no better than chance
    emb = TextEmbedding(16, 0).fit_transform(ids, [pv.items[i]["title"] for i in ids])
    trained = TypeAwareModel(16, dim=8, epochs=6, seed=2)
    trained.fit(make_triplets(pv.outfits["train"], types, rng), emb, types)
    a1 = auc([trained.outfit_compat(emb, types, x) for l, x in rows if l], [trained.outfit_compat(emb, types, x) for l, x in rows if not l])
    assert a1 > 0.7 and fitb_accuracy(trained, emb, types, pv.fitb["test"]) > 0.25


def test_simulation_rules_recency_and_tuning_guard(tmp_path):
    pv = load(write(tmp_path / "d"))
    cfg = small_cfg()
    garments = [attributes(i, pv.items[i], cfg["attribute_rules"]) for i in sorted(pv.outfit_items("test"))]
    pool = {}
    for g in garments:
        pool.setdefault(g.slot, []).append(g)
    rng = np.random.default_rng(1)
    w = sample_wardrobe(pool, (14, 14), cfg["wardrobe_minimums"], rng)
    sim = UserSim(w, lambda o: 0.5 + 0.01 * len(o), rng, 200)
    dl = days(1, 21, cfg["climatology"]["monthly"], cfg["schedule"], np.random.default_rng(2))
    full = sim.run(dl, "full", "random", (1, 1, 1), 2.0, 0.5, 5, np.random.default_rng(3))
    no_rec = sim.run(dl, "no_recency", "random", (1, 1, 1), 2.0, 0.5, 5, np.random.default_rng(3))
    assert full["coverage"] >= no_rec["coverage"]
    possible = sum(any(passes(o, d.rain, d.hot, d.occasion) for o in sim.outfits) for d in dl)
    assert full["rule_satisfaction"] * len(dl) >= possible - 1e-9  # whenever a rule-satisfying outfit exists
    with pytest.raises(TestDataAccess):
        grid_search(Split("reporting", []), pool, cfg, lambda o: 0.5, lambda *_: None)


def test_end_to_end_synthetic_run(tmp_path):
    pv = load(write(tmp_path / "e", n_items_per=200))
    rep = run(small_cfg(), out_dir=tmp_path / "out", log=lambda *_: None, data=(pv, [SYNTH_MANIFEST]))
    r = rep["result"]
    assert set(r["compatibility"]) == {"type_aware", "shared_space"} and r["selection"]["group"] == "tuning"
    assert len(r["reporting"]) == 6 and "by_behaviour" in r["success"]
    assert rep["assumptions"].startswith("CITED") and rep["provenance"]["datasets"]["synthetic_polyvore"]["synthetic"]


def test_real_run_refuses_without_a_permitted_manifest(tmp_path):
    """The real runner never touches data unless its manifest is present, permitted and checksum-verified."""
    cfg = load_config(ROOT / "research" / "configs" / "rq2.json")
    cfg["manifest"] = str(tmp_path / "missing_manifest.json")
    with pytest.raises(ManifestError, match="manifest not found"):
        run(cfg)


def test_transfer_sampler_labels_and_auc(tmp_path):
    """complete-wearhouse-tdd 4.2: stratified H&M pair sample, owner labels joined, AUC from the trained model."""
    import csv

    from wearhouse_research.rq2.transfer import (STRATA, evaluate_transfer, labelled, polyvore_type, sample_pairs,
                                                 write_pairs)
    groups = {"tops": ("Garment Upper body", "T-shirt"), "bottoms": ("Garment Lower body", "Trousers"),
              "shoes": ("Shoes", "Sneakers"), "all-body": ("Garment Full body", "Dress"),
              "outerwear": ("Garment Upper body", "Jacket"), "bags": ("Accessories", "Bag"),
              "jewellery": ("Accessories", "Necklace")}
    rows = [{"article_id": f"{t[:3]}{i:04d}", "product_group_name": g, "product_type_name": pt, "prod_name": f"{t} {i}",
             "colour_group_name": "Black", "detail_desc": "synthetic"} for t, (g, pt) in groups.items() for i in range(150)]
    assert polyvore_type(rows[0]) == "tops" and polyvore_type({"product_group_name": "Accessories",
                                                               "product_type_name": "Hair clip"}) is None
    pairs = sample_pairs(rows, n=200, seed=1)
    assert len(pairs) == 200 and len({p["a_article_id"] for p in pairs} | {p["b_article_id"] for p in pairs}) == 400
    assert {(p["a_type"], p["b_type"]) for p in pairs} == set(STRATA)
    assert sample_pairs(rows, n=200, seed=1) == pairs  # seeded
    pp, lp = tmp_path / "pairs.csv", tmp_path / "labels.csv"
    write_pairs(pp, pairs[:4])
    with lp.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["pair_id", "label", "labelled_at"])
        for pid, lab in (("p001", "no"), ("p001", "yes"), ("p002", "no"), ("p003", "unsure")):  # latest answer counts
            w.writerow([pid, lab, "t"])
    rows_l = labelled(pp, lp)
    assert [(r["pair_id"], r["label"]) for r in rows_l] == [("p001", "yes"), ("p002", "no"), ("p003", "unsure")]

    class Model:
        def compat(self, a, b, ta, tb):
            return float(a + b)

    emb = {"hm:" + r[k]: (1.0 if r["pair_id"] == "p001" else 0.0) for r in rows_l for k in ("a_article_id", "b_article_id")}
    out = evaluate_transfer(Model(), emb, rows_l)
    assert out == {"status": "evaluated", "labelled_pairs": 3, "yes": 1, "no": 1, "unsure_excluded": 1, "auc": 1.0}
