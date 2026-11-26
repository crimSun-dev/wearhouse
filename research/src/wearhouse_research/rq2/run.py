"""RQ2 runner (methodology 3.5.2): Polyvore audit -> compatibility model (type-aware vs shared-space; AUC, FITB on the
test split) -> simulated wardrobe study (grid search on the TUNING group only, single scoring of the REPORTING group).

    research/.venv/Scripts/python.exe -m wearhouse_research.rq2.run --config research/configs/rq2.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from scipy.stats import wilcoxon

from ..core import (ROOT, ManifestError, Split, Stopwatch, for_selection, load_config, load_manifest, provenance,
                    write_report)
from .compat import FashionClipEmbedding, TextEmbedding, TypeAwareModel, auc, fitb_accuracy, make_triplets
from .data import Polyvore, load, overlap_audit, unseen_items
from .simulate import BEHAVIOURS, VARIANTS, UserSim, attributes, days, sample_wardrobe
from .transfer import evaluate_transfer, labelled


def compatibility(pv: Polyvore, cfg: dict, emb: dict, types: dict, log) -> tuple[TypeAwareModel, dict]:
    rng = np.random.default_rng(cfg["seed"])
    triplets = make_triplets(pv.outfits["train"], types, rng, cfg["triplets_per_outfit"])
    dim_in = len(next(iter(emb.values())))
    results, models = {}, {}
    for name, typed in (("type_aware", True), ("shared_space", False)):
        m = TypeAwareModel(dim_in, typed=typed, seed=cfg["seed"], **cfg["model"])
        hist = m.fit(triplets, emb, types)
        rows = pv.compatibility.get("test", [])
        pos = [m.outfit_compat(emb, types, ids) for lab, ids in rows if lab == 1]
        neg = [m.outfit_compat(emb, types, ids) for lab, ids in rows if lab == 0]
        results[name] = {"auc": auc(pos, neg), "fitb": fitb_accuracy(m, emb, types, pv.fitb.get("test", [])),
                         "final_triplet_loss": hist[-1] if hist else None, "triplets": len(triplets)}
        models[name] = m
        log(f"{name}: AUC {results[name]['auc']:.3f} FITB {results[name]['fitb']:.3f}")
    return models["type_aware"], results


def _users(pool, cfg, n, offset):
    return [{"uid": offset + u} for u in range(n)]


def _run_user(user, seed, pool, cfg, comp_fn, season_month, variant, behaviour, w, h):
    rng = np.random.default_rng([cfg["seed"], user["uid"], seed])
    wardrobe = sample_wardrobe(pool, cfg["wardrobe_size"], cfg["wardrobe_minimums"], rng)
    sim = UserSim(wardrobe, comp_fn, rng, cfg["candidate_outfit_cap"])
    day_rng = np.random.default_rng([cfg["seed"], user["uid"], seed, season_month])
    dl = days(season_month, cfg["days"], cfg["climatology"]["monthly"], cfg["schedule"], day_rng)
    return sim.run(dl, variant, behaviour, w, h, cfg["pref_p0"], cfg["pref_a"], np.random.default_rng([seed, user["uid"], 7]))


def grid_search(tuning: Split, pool, cfg, comp_fn, log) -> dict:
    (users,) = for_selection(tuning)
    seasons = cfg["season_start_months"]
    def mean_of(variant, w, h):
        cov, comp = [], []
        for u in users:
            for s in seasons:
                for b in BEHAVIOURS:
                    r = _run_user(u, 0, pool, cfg, comp_fn, s, variant, b, w, h)
                    cov.append(r["coverage"])
                    comp.append(r["compat_worn"])
        return float(np.mean(cov)), float(np.mean(comp))
    base_cov, base_comp = mean_of("compatibility_only", (1, 0, 0), 1.0)
    table = []
    for w in cfg["weight_grid"]:
        for h in cfg["h_grid"]:
            cov, comp = mean_of("full", tuple(w), h)
            table.append({"w": w, "h": h, "coverage": cov, "compat": comp,
                          "within_margin": comp >= (1 - cfg["compat_margin"]) * base_comp})
    ok = [t for t in table if t["within_margin"]] or table
    best = max(ok, key=lambda t: (t["coverage"], -t["h"]))
    log(f"grid: chose w={best['w']} h={best['h']}")
    return {"group": "tuning", "users": len(users), "baseline": {"coverage": base_cov, "compat": base_comp},
            "table": table, "chosen": best, "rule": "highest tuning coverage with compatibility within the margin of "
                                                   "the compatibility-only baseline"}


def report_group(reporting: Split, pool, cfg, comp_fn, w, h, log) -> dict:
    users = reporting.data
    out = {}
    for b in BEHAVIOURS:
        for s in cfg["season_start_months"]:
            key = f"{b}/{'rainy' if s in (11, 12, 1, 2, 3) else 'dry'}-start-{s}"
            per = {v: np.zeros((len(cfg["seeds"]), len(users), 2)) for v in VARIANTS}
            for si, seed in enumerate(cfg["seeds"]):
                for ui, u in enumerate(users):
                    for v in VARIANTS:
                        r = _run_user(u, seed, pool, cfg, comp_fn, s, v, b, w, h)
                        per[v][si, ui] = (r["coverage"], r["compat_worn"])
            summary = {v: {"coverage_seed_mean": float(per[v][:, :, 0].mean(axis=1).mean()),
                           "coverage_seed_std": float(per[v][:, :, 0].mean(axis=1).std()),
                           "compat_seed_mean": float(per[v][:, :, 1].mean(axis=1).mean()),
                           "compat_seed_std": float(per[v][:, :, 1].mean(axis=1).std())} for v in VARIANTS}
            full_u, base_u = per["full"][:, :, 0].mean(axis=0), per["compatibility_only"][:, :, 0].mean(axis=0)
            try:
                stat = wilcoxon(full_u, base_u, zero_method="zsplit")
                test = {"statistic": float(stat.statistic), "p_value": float(stat.pvalue)}
            except ValueError as exc:  # all differences zero
                test = {"statistic": None, "p_value": None, "note": str(exc)}
            cov_rel = (summary["full"]["coverage_seed_mean"] - summary["compatibility_only"]["coverage_seed_mean"]) \
                / summary["compatibility_only"]["coverage_seed_mean"]
            comp_rel = (summary["full"]["compat_seed_mean"] - summary["compatibility_only"]["compat_seed_mean"]) \
                / summary["compatibility_only"]["compat_seed_mean"]
            out[key] = {"variants": summary, "wilcoxon_full_vs_compatibility_only_coverage": test,
                        "coverage_relative": cov_rel, "compat_relative": comp_rel,
                        "met": cov_rel >= cfg["coverage_target"] and comp_rel >= -cfg["compat_margin"]}
            log(f"{key}: coverage {cov_rel:+.1%} compat {comp_rel:+.1%}")
    return out


def _fashionclip_source(cfg: dict) -> str:
    """A local copy of the FashionCLIP weights when present (offline, resumable download), else the hub model id."""
    local = cfg.get("fashionclip_local")
    if local and (ROOT / local / "model.safetensors").exists():
        return str(ROOT / local)
    return cfg.get("fashionclip_model", "patrickjohncyh/fashion-clip")


def transfer_rows(cfg: dict) -> tuple[list[dict] | None, str]:
    """The owner's H&M transfer labels when pinned in a permitted manifest; never generated (transfer.py)."""
    path = cfg.get("transfer_manifest")
    if not path:
        return None, "not configured"
    try:
        m = load_manifest(ROOT / path)
    except ManifestError as exc:
        return None, f"labels not supplied ({exc})"
    return labelled(m.path("pairs"), m.path("labels")), "supplied"


def evaluate(pv: Polyvore, cfg: dict, log=print, embedder=None, transfer: list[dict] | None = None) -> dict:
    audit = overlap_audit(pv)
    ids = list(pv.items)
    texts = [f"{pv.items[i].get('title', '')} {pv.items[i].get('semantic_category', '')}" for i in ids]
    if transfer:  # unsupervised: the H&M texts only join the embedding fit; their labels are never used to train
        for r in transfer:
            for side in ("a", "b"):
                ids.append("hm:" + r[f"{side}_article_id"])
                texts.append(f"{r[f'{side}_text']} {r[f'{side}_type']}")
    embedder = embedder or TextEmbedding(cfg["embedding_dims"], cfg["seed"])
    emb = embedder.fit_transform(ids, texts)
    types = {i: pv.type_of(i) for i in pv.items}
    model, comp_results = compatibility(pv, cfg, emb, types, log)
    transfer_result = evaluate_transfer(model, emb, transfer) if transfer else None
    if transfer_result:
        log(f"H&M transfer: AUC {transfer_result['auc']} on {transfer_result['yes']} yes / {transfer_result['no']} no")
    sim_items = unseen_items(pv) if audit["test_items_seen_in_training"] else pv.outfit_items("test")
    garments = [attributes(i, pv.items[i], cfg["attribute_rules"]) for i in sorted(sim_items)]
    pool: dict = {}
    for g in garments:
        pool.setdefault(g.slot, []).append(g)

    def comp_fn(outfit):
        return model.outfit_compat(emb, types, [g.id for g in outfit])

    tuning = Split("tuning", _users(pool, cfg, cfg["users_tuning"], 0), "first group of simulated users")
    reporting = Split("reporting", _users(pool, cfg, cfg["users_reporting"], 10_000), "second group (reported)")
    grid = grid_search(tuning, pool, cfg, comp_fn, log)
    w, h = tuple(grid["chosen"]["w"]), grid["chosen"]["h"]
    results = report_group(reporting, pool, cfg, comp_fn, w, h, log)
    by_behaviour = {b: all(v["met"] for k, v in results.items() if k.startswith(b + "/")) for b in BEHAVIOURS}
    return {"audit": audit, "embedding": embedder.name, "compatibility": comp_results,
            "transfer": transfer_result or {"status": "labels not supplied: run research/tools/label_pairs.py"},
            "simulation_items": {"source": "unseen test items" if audit["test_items_seen_in_training"] else "test items",
                                 "count": len(garments), "by_slot": {k: len(v) for k, v in pool.items()}},
            "selection": grid, "reporting": results,
            "success": {"by_behaviour": by_behaviour, "rq2_positive": all(by_behaviour.values()),
                        "targets": {"coverage": cfg["coverage_target"], "compat_margin": cfg["compat_margin"]}}}


def markdown(rep: dict) -> str:
    r = rep["result"]
    comp = "\n".join(f"| {k} | {v['auc']:.3f} | {v['fitb']:.3f} |" for k, v in r["compatibility"].items())
    rows = "\n".join(f"| {k} | {v['coverage_relative']:+.1%} | {v['compat_relative']:+.1%} | "
                     f"{v['wilcoxon_full_vs_compatibility_only_coverage'].get('p_value')} | {v['met']} |"
                     for k, v in r["reporting"].items())
    return f"""# RQ2 — Outfit recommendation (methodology 3.5.2)

**Answer: {"POSITIVE" if r["success"]["rq2_positive"] else "NOT POSITIVE"}** — per behaviour: {r["success"]["by_behaviour"]}

Embedding: **{r["embedding"]}**. Overlap audit: {r["audit"]}

| Compatibility model | AUC | FITB |
|---|---|---|
{comp}

| Behaviour / season | Coverage vs compat-only | Compatibility vs compat-only | Wilcoxon p | Met |
|---|---|---|---|---|
{rows}

H&M domain transfer (200 hand-labelled pairs): {r['transfer']}

Tuning (group 1 only): chose w = {r["selection"]["chosen"]["w"]}, h = {r["selection"]["chosen"]["h"]}.

Climatology: {rep["assumptions"]}

Embedding coverage: {r.get("embedding_coverage", "not applicable (text embedding)")}

Corrections: {r.get("corrections") or "none (first run)"}

## Disclosure
{rep["provenance"]["disclosure"]}
"""


def run(cfg: dict, *, out_dir: Path | None = None, log=print, data=None) -> dict:
    sw = Stopwatch()
    if data is None:
        m = load_manifest(ROOT / cfg["manifest"])
        pv = load(m.path("item_metadata").parent, cfg["variant"])
        manifests = [m]
        transfer, status = transfer_rows(cfg)
        log(f"H&M transfer labels: {status}")
        embedder = None
        if cfg.get("embedding") == "fashionclip_image":
            im = load_manifest(ROOT / cfg["images_manifest"])  # refuses unless permitted and every sha256 matches
            manifests.append(im)
            keys = sorted(im.files)
            embedder = FashionClipEmbedding([im.path(k) for k in keys], [im.files[k].sha256 for k in keys],
                                            model_name=_fashionclip_source(cfg),
                                            cache_dir=ROOT / "research" / ".cache", log=log)
    else:
        pv, manifests = data
        transfer, embedder = None, None
    result = evaluate(pv, cfg, log=log, transfer=transfer, embedder=embedder)
    if embedder is not None:
        result["embedding_coverage"] = {"by_image": embedder.images_embedded, "by_text": embedder.text_fallback}
    result["corrections"] = cfg.get("corrections")
    rep = {"rq": "RQ2", "provenance": provenance(cfg, manifests, {"base": cfg["seed"], "simulation": cfg["seeds"]},
                                                 ["numpy", "scipy", "sklearn"]),
           "assumptions": cfg["climatology"]["status"], "result": result, "wall_seconds": sw.seconds()}
    out = write_report("rq2", rep, markdown(rep), out_dir=out_dir)
    rep["_written_to"] = str(out)
    return rep


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    rep = run(load_config(Path(a.config)), out_dir=Path(a.out) if a.out else None)
    print(json.dumps(rep["result"]["success"]), rep["_written_to"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
