"""RQ1 measures (Eq. 12-13): MAP@12, Recall@12, NDCG@12, duplicate share; paired customer bootstrap with a
fixed seed; relative change with an explicit zero-baseline rule."""
from __future__ import annotations

import math
from typing import Callable, Sequence

import numpy as np

K = 12


def ap_at_k(rec: Sequence[str], truth: set[str], k: int = K) -> float:
    """Average precision at k, normalised by min(|truth|, k) (the H&M competition definition)."""
    if not truth:
        return 0.0
    hits, score = 0, 0.0
    for i, item in enumerate(rec[:k], start=1):
        if item in truth:
            hits += 1
            score += hits / i
    return score / min(len(truth), k)


def recall_at_k(rec: Sequence[str], truth: set[str], k: int = K) -> float:
    return len(set(rec[:k]) & truth) / len(truth) if truth else 0.0


def ndcg_at_k(rec: Sequence[str], truth: set[str], k: int = K) -> float:
    if not truth:
        return 0.0
    dcg = sum(1.0 / math.log2(i + 1) for i, item in enumerate(rec[:k], start=1) if item in truth)
    idcg = sum(1.0 / math.log2(i + 1) for i in range(1, min(len(truth), k) + 1))
    return dcg / idcg


def duplicate_share(rec: Sequence[str], is_dup: Callable[[str], bool], k: int = K) -> float:
    """Share of the k recommended items that duplicate an owned item (Eq. 13, per user)."""
    items = list(rec[:k])
    return sum(1 for i in items if is_dup(i)) / len(items) if items else 0.0


def per_user(lists: dict[str, Sequence[str]], truth: dict[str, set[str]], users: list[str]) -> dict[str, np.ndarray]:
    return {"map@12": np.array([ap_at_k(lists[u], truth[u]) for u in users]),
            "recall@12": np.array([recall_at_k(lists[u], truth[u]) for u in users]),
            "ndcg@12": np.array([ndcg_at_k(lists[u], truth[u]) for u in users])}


def bootstrap_ci(values: np.ndarray, *, resamples: int = 1000, seed: int = 0, alpha: float = 0.05) -> dict:
    """Customer bootstrap of a mean (paired when `values` is a per-customer difference). Deterministic by seed."""
    rng = np.random.default_rng(seed)
    n = len(values)
    if n == 0:
        return {"mean": None, "lo": None, "hi": None, "n": 0}
    idx = rng.integers(0, n, size=(resamples, n))
    means = values[idx].mean(axis=1)
    return {"mean": float(values.mean()), "lo": float(np.quantile(means, alpha / 2)),
            "hi": float(np.quantile(means, 1 - alpha / 2)), "n": int(n), "resamples": resamples, "seed": seed}


def relative_change(new: float, base: float) -> dict:
    """Zero-baseline rule (fixed before any results): if base == 0 the relative change is undefined; report the
    absolute difference instead."""
    if base == 0:
        return {"relative": None, "absolute": new - base, "note": "undefined: zero baseline (absolute reported)"}
    return {"relative": (new - base) / base, "absolute": new - base}
