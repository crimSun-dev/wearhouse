"""Export a serving artifact (manifest.json + neighbours.csv, sha256-pinned) from a fitted RQ1 model.

- BPR item factors -> nearest neighbours by cosine: mode `trained`, model_hash = sha256 of the factor matrix.
- Item-kNN co-purchase lists: mode `heuristic_baseline` (a data-derived baseline, not a trained model).
Import with:  wearhouse import-recommendations --artifact <dir> --operator-issuer ... --operator-subject ...
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

HEADER = "article_id,rank,neighbour_article_id,score"


def _write(out: Path, rows: list[tuple[str, int, str, float]], manifest: dict) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    body = (HEADER + "\n" + "\n".join(f"{a},{r},{b},{s:.6f}" for a, r, b, s in rows) + "\n").encode("utf-8")
    (out / "neighbours.csv").write_bytes(body)
    manifest = {**manifest, "kind": "similar_items", "files": {"neighbours.csv": hashlib.sha256(body).hexdigest()}}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return out


def from_bpr(bpr, out: Path, *, k: int = 12, namespace: str, version: str, report: str | None, datasets: dict) -> Path:
    q = bpr.Q[bpr.known]
    ids = [a for a, known in zip(bpr.cat_ids, bpr.known) if known]
    qn = q / (np.linalg.norm(q, axis=1, keepdims=True) + 1e-9)
    rows = []
    for s in range(0, len(ids), 1024):
        sims = qn[s:s + 1024] @ qn.T
        for r, row in enumerate(sims):
            row[s + r] = -np.inf
            top = np.argpartition(-row, k)[:k]
            top = top[np.argsort(-row[top])]
            rows += [(ids[s + r], n + 1, ids[j], float(row[j])) for n, j in enumerate(top)]
    model_hash = hashlib.sha256(np.ascontiguousarray(bpr.Q).tobytes()).hexdigest()
    return _write(out, rows, {"name": "bpr-item-factors-cosine", "version": version, "mode": "trained",
                              "model_hash": model_hash, "source_namespace": namespace, "report": report,
                              "datasets": datasets, "settings": {"factors": bpr.factors, "epochs": bpr.epochs,
                                                                 "seed": bpr.seed}})


def from_itemknn(knn, out: Path, *, k: int = 12, namespace: str, version: str, report: str | None,
                 datasets: dict) -> Path:
    rows = []
    sim = knn.sim.tocsr()
    for i in range(sim.shape[0]):
        s, e = sim.indptr[i], sim.indptr[i + 1]
        if e == s:
            continue
        order = np.argsort(-sim.data[s:e])[:k]
        rows += [(knn.cat.ids[i], n + 1, knn.cat.ids[sim.indices[s + j]], float(sim.data[s + j]))
                 for n, j in enumerate(order)]
    return _write(out, rows, {"name": "item-knn-copurchase", "version": version, "mode": "heuristic_baseline",
                              "model_hash": None, "source_namespace": namespace, "report": report, "datasets": datasets})
