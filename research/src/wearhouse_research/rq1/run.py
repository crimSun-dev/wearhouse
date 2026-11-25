"""RQ1 runner: select alpha and lambda_d on the VALIDATION week, then evaluate every method once on the TEST week
(methodology 3.5.1). Usage (research environment, after the transactions manifest is permitted):

    research/.venv/Scripts/python.exe -m wearhouse_research.rq1.run --config research/configs/rq1.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from ..core import ROOT, Split, Stopwatch, for_selection, load_config, load_manifest, provenance, write_report
from . import metrics as M
from .data import chronological_split, genz_cohort, load_articles, load_customers, load_transactions, owned_before, \
    purchases_by_customer
from .models import BPR, Catalogue, Duplicates, FirstStage, ItemKNN, Reranker, popularity


def _window(tx: pd.DataFrame, cutoff: pd.Timestamp, weeks: int | None) -> pd.DataFrame:
    hist = tx[tx["t_dat"] < cutoff]
    return hist if not weeks else hist[hist["t_dat"] >= cutoff - pd.Timedelta(weeks=weeks)]


def _sample(users: list[str], cap: int | None, seed: int) -> list[str]:
    if not cap or len(users) <= cap:
        return users
    return sorted(np.random.default_rng(seed).choice(users, size=cap, replace=False).tolist())


def _phase(tx, customers, cat, cfg, *, cutoff, evaluated: pd.DataFrame, seed: int):
    """Fit models on history before `cutoff`; return everything needed to score customers of `evaluated`."""
    window = _window(tx, cutoff, cfg["train_weeks"])
    prev_week = tx[(tx["t_dat"] >= cutoff - pd.Timedelta(days=7)) & (tx["t_dat"] < cutoff)]
    users, cohort = genz_cohort(customers, evaluated, cfg["genz_max_age"])
    users = _sample(users, cfg.get("max_eval_customers"), seed)
    truth = purchases_by_customer(evaluated[evaluated["customer_id"].isin(set(users))])
    owned = owned_before(tx, cutoff, users)
    pop = popularity(prev_week)
    bpr = BPR(**cfg["bpr"], seed=seed).fit(cat, window)
    knn = ItemKNN(cat, window, cfg["itemknn_neighbours"])
    return {"users": users, "truth": truth, "owned": owned, "pop": pop, "bpr": bpr, "knn": knn, "cohort": cohort,
            "window": {"from": str(window["t_dat"].min()), "to": str(window["t_dat"].max()), "rows": len(window)}}


def _lists(ph, cat, *, alpha, lambda_d, dup, candidates) -> dict[str, dict[str, list[str]]]:
    first = FirstStage(cat, ph["bpr"], alpha, candidates)
    rerank = Reranker(first, dup, lambda_d)
    out = {"popularity": {}, "item_knn": {}, "bpr": {}, "first_stage": {}, "reranked": {}}
    for u in ph["users"]:
        o = ph["owned"][u]
        out["popularity"][u] = ph["pop"]
        out["item_knn"][u] = ph["knn"].recommend(o, fallback=ph["pop"])
        out["bpr"][u] = ph["bpr"].recommend(u, fallback=ph["pop"])
        idx, s1 = first.top(u, o)  # once; the reranker reuses it (identical to rerank.recommend(u, o))
        out["first_stage"][u] = [cat.ids[i] for i in idx[:12]]
        out["reranked"][u] = rerank.recommend_from(idx, s1, dup.flags(idx, o), o)
    return out


def _select(vph, cat, dup, cfg, log=None) -> tuple[dict, float, dict, float]:
    """alpha then lambda_d on the validation week. Each customer's catalogue scores and duplicate flags are computed
    once and reused across the grids; the result equals _select_reference (checked in tests/test_rq1.py)."""
    users, owned, truth, grid = vph["users"], vph["owned"], vph["truth"], cfg["alpha_grid"]
    probe = FirstStage(cat, vph["bpr"], 0.0, cfg["candidates"])
    tops: dict = {a: {} for a in grid}
    aps: dict = {a: [] for a in grid}
    for n, u in enumerate(users, 1):
        if log and n % 2000 == 0:
            log(f"  validation scoring {n}/{len(users)}")
        cos, bt = probe.components(u, owned[u])
        for a in grid:
            idx, s1 = probe.top_of(FirstStage.combine(cos, bt, a))
            tops[a][u] = (idx, s1)
            aps[a].append(M.ap_at_k([cat.ids[i] for i in idx[:12]], truth[u]))
    alpha_scores = {a: float(np.mean(aps[a])) for a in grid}
    alpha = max(alpha_scores, key=lambda a: (alpha_scores[a], -a))
    chosen = tops[alpha]
    del tops
    flags = {u: dup.flags(chosen[u][0], owned[u]) for u in users}

    def lookup(u):
        f = dict(zip((cat.ids[i] for i in chosen[u][0]), flags[u]))
        return lambda art: bool(f[art])
    is_dup = {u: lookup(u) for u in users}
    base_dup = np.mean([M.duplicate_share([cat.ids[i] for i in chosen[u][0][:12]], is_dup[u]) for u in users])
    first = FirstStage(cat, vph["bpr"], alpha, cfg["candidates"])
    lam_scores = {}
    for lam in cfg["lambda_d_grid"]:
        rr = Reranker(first, dup, lam)
        ls = {u: rr.recommend_from(*chosen[u], flags[u], owned[u]) for u in users}
        lam_scores[lam] = {"map@12": float(np.mean([M.ap_at_k(ls[u], truth[u]) for u in users])),
                           "duplicate_share": float(np.mean([M.duplicate_share(ls[u], is_dup[u]) for u in users]))}
    return alpha_scores, alpha, lam_scores, float(base_dup)


def _select_reference(vph, cat, dup, cfg) -> tuple[dict, float, dict, float]:
    """The original per-setting computation, kept as the reference for the equivalence test."""
    alpha_scores = {}
    for a in cfg["alpha_grid"]:
        first = FirstStage(cat, vph["bpr"], a, cfg["candidates"])
        alpha_scores[a] = float(np.mean([M.ap_at_k([cat.ids[i] for i in first.top(u, vph["owned"][u])[0][:12]],
                                                   vph["truth"][u]) for u in vph["users"]]))
    alpha = max(alpha_scores, key=lambda a: (alpha_scores[a], -a))
    first = FirstStage(cat, vph["bpr"], alpha, cfg["candidates"])
    base_dup = np.mean([M.duplicate_share([cat.ids[i] for i in first.top(u, vph["owned"][u])[0][:12]],
                                          dup.is_dup_fn(vph["owned"][u])) for u in vph["users"]])
    lam_scores = {}
    for lam in cfg["lambda_d_grid"]:
        rr = Reranker(first, dup, lam)
        ls = {u: rr.recommend(u, vph["owned"][u]) for u in vph["users"]}
        lam_scores[lam] = {"map@12": float(np.mean([M.ap_at_k(ls[u], vph["truth"][u]) for u in vph["users"]])),
                           "duplicate_share": float(np.mean([M.duplicate_share(ls[u], dup.is_dup_fn(vph["owned"][u]))
                                                             for u in vph["users"]]))}
    return alpha_scores, alpha, lam_scores, float(base_dup)


def _evaluate(lists, ph, dup, *, resamples, seed) -> dict:
    res = {}
    for name, ls in lists.items():
        pu = M.per_user(ls, ph["truth"], ph["users"])
        dups = np.array([M.duplicate_share(ls[u], dup.is_dup_fn(ph["owned"][u])) for u in ph["users"]])
        res[name] = {"per_user": {**pu, "duplicate_share": dups},
                     **{m: M.bootstrap_ci(v, resamples=resamples, seed=seed) for m, v in {**pu, "duplicate_share": dups}.items()}}
    return res


def evaluate(tx: pd.DataFrame, customers: pd.DataFrame, articles: pd.DataFrame, cfg: dict, log=print) -> dict:
    cat = Catalogue(articles)
    split = chronological_split(tx)
    dup = Duplicates(cat, cfg["tau"])
    seed = cfg["seed"]

    # ---- selection on the VALIDATION week only (guarded: test data cannot be passed here)
    (val_week,) = for_selection(split.validation)
    vph = _phase(tx[tx["t_dat"] < split.test_start], customers, cat, cfg, cutoff=split.validation_start,
                 evaluated=val_week, seed=seed)
    log(f"validation: {len(vph['users'])} Gen Z customers")
    alpha_scores, alpha, lam_scores, base_dup = _select(vph, cat, dup, cfg, log=log)
    target = cfg["duplicate_reduction_target"]
    meets = {lam: s for lam, s in lam_scores.items()
             if base_dup == 0 or s["duplicate_share"] <= (1 - target) * base_dup}
    pool = meets or lam_scores
    lambda_d = max(pool, key=lambda lam: (pool[lam]["map@12"], -lam))
    selection = {"split": "validation", "alpha_grid_map": alpha_scores, "alpha": alpha,
                 "first_stage_duplicate_share": float(base_dup), "lambda_d_grid": lam_scores, "lambda_d": lambda_d,
                 "lambda_d_rule": f"max validation MAP among settings reducing duplicates by >= {target:.0%} vs first "
                                  f"stage; if none, max MAP (met: {bool(meets)})", "tau": cfg["tau"],
                 "tau_note": "fixed in config (thesis tau from hand-checked image pairs cannot be reproduced without images)"}
    log(f"selected alpha={alpha} lambda_d={lambda_d}")

    # ---- single evaluation on the TEST week (models refit on everything before it)
    tph = _phase(tx, customers, cat, cfg, cutoff=split.test_start, evaluated=split.test.data, seed=seed)
    log(f"test: {len(tph['users'])} Gen Z customers")
    lists = _lists(tph, cat, alpha=alpha, lambda_d=lambda_d, dup=dup, candidates=cfg["candidates"])
    res = _evaluate(lists, tph, dup, resamples=cfg["bootstrap_resamples"], seed=seed)
    baselines = ("popularity", "item_knn", "bpr", "first_stage")
    best = max(baselines, key=lambda b: res[b]["map@12"]["mean"])
    diff_map = res["reranked"]["per_user"]["map@12"] - res[best]["per_user"]["map@12"]
    diff_dup = res["reranked"]["per_user"]["duplicate_share"] - res["first_stage"]["per_user"]["duplicate_share"]
    map_change = M.relative_change(res["reranked"]["map@12"]["mean"], res[best]["map@12"]["mean"])
    dup_change = M.relative_change(res["reranked"]["duplicate_share"]["mean"], res["first_stage"]["duplicate_share"]["mean"])
    success = {"map_target": cfg["map_improvement_target"], "duplicate_target": target,
               "map_relative_vs_best_baseline": map_change, "best_baseline": best,
               "duplicate_relative_vs_first_stage": dup_change,
               "map_met": map_change["relative"] is not None and map_change["relative"] >= cfg["map_improvement_target"],
               "duplicates_met": dup_change["relative"] is not None and dup_change["relative"] <= -target,
               "paired_map_difference_ci": M.bootstrap_ci(diff_map, resamples=cfg["bootstrap_resamples"], seed=seed),
               "paired_duplicate_difference_ci": M.bootstrap_ci(diff_dup, resamples=cfg["bootstrap_resamples"], seed=seed)}
    success["rq1_positive"] = success["map_met"] and success["duplicates_met"]
    for r in res.values():
        r.pop("per_user")
    return {"selection": selection, "test": {"cohort": tph["cohort"], "evaluated_customers": len(tph["users"]),
                                             "window": tph["window"], "methods": res},
            "success": success, "split": {"validation_start": str(split.validation_start),
                                          "test_start": str(split.test_start), "end": str(split.end)}}


def markdown(rep: dict) -> str:
    rows = "\n".join(
        f"| {m} | {v['map@12']['mean']:.4f} [{v['map@12']['lo']:.4f}, {v['map@12']['hi']:.4f}] | "
        f"{v['recall@12']['mean']:.4f} | {v['ndcg@12']['mean']:.4f} | {v['duplicate_share']['mean']:.3f} |"
        for m, v in rep["result"]["test"]["methods"].items())
    s = rep["result"]["success"]
    return f"""# RQ1 — Catalogue recommendation (methodology 3.5.1)

**Answer: {"POSITIVE" if s["rq1_positive"] else "NOT POSITIVE"}** (MAP target met: {s["map_met"]}, duplicate target met: {s["duplicates_met"]})

Content embedding: **{rep["declared"]["content_embedding"]}** — {rep["declared"]["reason"]}

| Method | MAP@12 [95% CI] | Recall@12 | NDCG@12 | Duplicate share |
|---|---|---|---|---|
{rows}

Best simpler baseline: {s["best_baseline"]}. MAP change: {s["map_relative_vs_best_baseline"]}. Duplicate change vs first stage: {s["duplicate_relative_vs_first_stage"]}.

Selection (validation week only): alpha = {rep["result"]["selection"]["alpha"]}, lambda_d = {rep["result"]["selection"]["lambda_d"]} ({rep["result"]["selection"]["lambda_d_rule"]}).

Cohort: {rep["result"]["test"]["cohort"]}

## Disclosure
{rep["provenance"]["disclosure"]}
"""


DECLARED = {"content_embedding": "text_attributes",
            "reason": "No permitted product images exist (catalogue images are generated placeholders), so the "
                      "FashionCLIP image term of Eq. 2 and the image-similarity Dup of Eq. 3 are replaced by a "
                      "TF-IDF text/attribute embedding. Comp (Eq. 3) needs the RQ2 compatibility model; lambda_c = 0 "
                      "until an RQ2 artifact exists."}


def run(cfg: dict, *, out_dir: Path | None = None, log=print, data=None) -> dict:
    sw = Stopwatch()
    if data is None:
        m = load_manifest(ROOT / cfg["manifest"])
        tx = load_transactions(m.path("transactions"), m.files["transactions"].sha256)
        customers = load_customers(m.path("customers"), m.files["customers"].sha256)
        articles = load_articles(m.path("articles"), m.files["articles"].sha256)
        manifests = [m]
    else:
        tx, customers, articles, manifests = data
    result = evaluate(tx, customers, articles, cfg, log=log)
    rep = {"rq": "RQ1", "provenance": provenance(cfg, manifests, {"bpr_bootstrap_sampling": cfg["seed"]},
                                                 ["numpy", "pandas", "scipy", "sklearn"]),
           "declared": DECLARED, "result": result, "wall_seconds": sw.seconds()}
    out = write_report("rq1", rep, markdown(rep), out_dir=out_dir)
    rep["_written_to"] = str(out)
    return rep


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    rep = run(load_config(Path(a.config)), out_dir=Path(a.out) if a.out else None)
    print(json.dumps(rep["result"]["success"], default=str), rep["_written_to"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
