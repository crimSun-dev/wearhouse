"""RQ1 models (methodology 3.4.1, 3.5.1): popularity, item-based nearest neighbour, BPR-MF (numpy), the declared
text/attribute content embedding (FashionCLIP image term unavailable: no permitted product images), the first
stage (Eq. 2) and the owned-item re-ranker (Eq. 3)."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import scipy.sparse as sp
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize

TOKEN_FIELDS = ("product_type_name", "product_group_name", "colour_group_name", "perceived_colour_master_name",
                "graphical_appearance_name", "section_name", "garment_group_name", "index_group_name")


class Catalogue:
    """Article index + content embedding (TF-IDF of description and attribute tokens, L2-normalised)."""

    def __init__(self, articles: pd.DataFrame):
        self.ids = articles["article_id"].astype(str).tolist()
        self.index = {a: i for i, a in enumerate(self.ids)}
        self.type = articles["product_type_name"].astype(str).to_numpy()
        docs = []
        for _, r in articles.iterrows():
            tokens = " ".join(f"{f}_{str(r.get(f, '')).strip().lower().replace(' ', '_')}" for f in TOKEN_FIELDS
                              if str(r.get(f, "")).strip())
            docs.append(f"{r.get('prod_name', '')} {r.get('detail_desc', '')} {tokens}")
        self.vectorizer = TfidfVectorizer(min_df=1, sublinear_tf=True, token_pattern=r"(?u)\b\w[\w/&]+\b")
        self.content = normalize(self.vectorizer.fit_transform(docs).astype(np.float32).tocsr())

    def idx(self, items) -> np.ndarray:
        return np.array([self.index[a] for a in items if a in self.index], dtype=np.int64)

    def profile(self, owned: set[str]):
        rows = self.idx(owned)
        if len(rows) == 0:
            return None
        return normalize(sp.csr_matrix(self.content[rows].mean(axis=0)))


# ------------------------------------------------------------------ baselines
def popularity(tx_week: pd.DataFrame, k: int = 12) -> list[str]:
    """Twelve most purchased products of the given (previous) week."""
    return tx_week["article_id"].value_counts().index[:k].tolist()


class ItemKNN:
    """Products often bought together with the customer's past purchases (cosine over co-purchase)."""

    def __init__(self, cat: Catalogue, tx: pd.DataFrame, neighbours: int = 100):
        self.cat = cat
        users = {u: i for i, u in enumerate(tx["customer_id"].unique())}
        rows = tx["customer_id"].map(users).to_numpy()
        cols = tx["article_id"].map(cat.index).to_numpy()
        ok = ~pd.isna(cols)
        x = sp.csr_matrix((np.ones(ok.sum(), dtype=np.float32), (rows[ok], cols[ok].astype(np.int64))),
                          shape=(len(users), len(cat.ids)))
        x.data[:] = 1.0  # binary
        sim = (x.T @ x).tocsr().astype(np.float32)
        norms = np.sqrt(sim.diagonal()) + 1e-9
        sim = sp.diags(1 / norms) @ sim @ sp.diags(1 / norms)
        sim.setdiag(0)
        self.sim = _top_n_rows(sim.tocsr(), neighbours)

    def recommend(self, owned: set[str], k: int = 12, fallback: list[str] | None = None) -> list[str]:
        rows = self.cat.idx(owned)
        if len(rows) == 0:
            return list(fallback or [])[:k]
        scores = np.asarray(self.sim[rows].sum(axis=0)).ravel()
        top = _topk(scores, k)
        out = [self.cat.ids[i] for i in top if scores[i] > 0]
        return (out + [a for a in (fallback or []) if a not in out])[:k]


def _top_n_rows(m: sp.csr_matrix, n: int) -> sp.csr_matrix:
    rows, cols, vals = [], [], []
    for r in range(m.shape[0]):
        s, e = m.indptr[r], m.indptr[r + 1]
        if e - s == 0:
            continue
        data, idx = m.data[s:e], m.indices[s:e]
        keep = np.argsort(-data)[:n]
        rows += [r] * len(keep)
        cols += idx[keep].tolist()
        vals += data[keep].tolist()
    return sp.csr_matrix((vals, (rows, cols)), shape=m.shape, dtype=np.float32)


def _topk(scores: np.ndarray, k: int) -> np.ndarray:
    k = min(k, len(scores))
    part = np.argpartition(-scores, k - 1)[:k]
    return part[np.argsort(-scores[part], kind="stable")]


class BPR:
    """Bayesian Personalised Ranking MF (Rendle et al., 2009): minibatch SGD with uniform negatives, L2 reg."""

    def __init__(self, factors: int = 64, lr: float = 0.05, reg: float = 0.002, epochs: int = 10,
                 batch: int = 4096, seed: int = 0):
        self.factors, self.lr, self.reg, self.epochs, self.batch, self.seed = factors, lr, reg, epochs, batch, seed

    def fit(self, cat: Catalogue, tx: pd.DataFrame) -> "BPR":
        rng = np.random.default_rng(self.seed)
        self.cat_ids = cat.ids
        self.users = {u: i for i, u in enumerate(tx["customer_id"].unique())}
        u = tx["customer_id"].map(self.users).to_numpy()
        i = tx["article_id"].map(cat.index)
        ok = i.notna().to_numpy()
        u, i = u[ok].astype(np.int64), i[ok].to_numpy().astype(np.int64)
        n_items = len(cat.ids)
        self.known = np.zeros(n_items, dtype=bool)
        self.known[i] = True
        self.P = rng.normal(0, 0.1, (len(self.users), self.factors)).astype(np.float32)
        self.Q = rng.normal(0, 0.1, (n_items, self.factors)).astype(np.float32)
        for _ in range(self.epochs):
            order = rng.permutation(len(u))
            for s in range(0, len(order), self.batch):
                b = order[s:s + self.batch]
                ub, ib = u[b], i[b]
                jb = rng.integers(0, n_items, len(b))
                pu, qi, qj = self.P[ub], self.Q[ib], self.Q[jb]
                x = np.sum(pu * (qi - qj), axis=1)
                g = (1.0 / (1.0 + np.exp(np.clip(x, -30, 30)))).astype(np.float32)[:, None]  # sigma(-x)
                np.add.at(self.P, ub, self.lr * (g * (qi - qj) - self.reg * pu))
                np.add.at(self.Q, ib, self.lr * (g * pu - self.reg * qi))
                np.add.at(self.Q, jb, self.lr * (-g * pu - self.reg * qj))
        return self

    def scores(self, customer: str) -> np.ndarray | None:
        ui = self.users.get(customer)
        if ui is None:
            return None
        s = self.Q @ self.P[ui]
        s[~self.known] = np.nan  # cold items: BPR cannot score them
        return s

    def recommend(self, customer: str, k: int = 12, fallback: list[str] | None = None) -> list[str]:
        s = self.scores(customer)
        if s is None:
            return list(fallback or [])[:k]
        return [self.cat_ids[j] for j in _topk(np.nan_to_num(s, nan=-np.inf), k)]


def rescale(x: np.ndarray) -> np.ndarray:
    """Min-max to [0, 1] over finite values (x-tilde in Eq. 2); NaN stays NaN."""
    finite = np.isfinite(x)
    if not finite.any():
        return x
    lo, hi = np.nanmin(x[finite]), np.nanmax(x[finite])
    return (x - lo) / (hi - lo) if hi > lo else np.where(finite, 0.0, np.nan)


@dataclass
class FirstStage:
    """Eq. 2: alpha * BPR(rescaled) + (1 - alpha) * cos(profile, content); cold items use the content term only."""

    cat: Catalogue
    bpr: BPR
    alpha: float
    candidates: int = 300

    def components(self, customer: str, owned: set[str]) -> tuple[np.ndarray, np.ndarray | None]:
        """The alpha-independent parts of Eq. 2 (content cosine, rescaled BPR); computed once per customer so a grid
        over alpha reuses them (same arithmetic as score())."""
        prof = self.cat.profile(owned)
        cos = np.zeros(len(self.cat.ids), dtype=np.float32) if prof is None else \
            np.asarray((self.cat.content @ prof.T).todense()).ravel()
        b = self.bpr.scores(customer)
        return cos, (None if b is None else rescale(b))

    @staticmethod
    def combine(cos: np.ndarray, bt: np.ndarray | None, alpha: float) -> np.ndarray:
        if bt is None:
            return cos
        return np.where(np.isfinite(bt), alpha * bt + (1 - alpha) * cos, cos)

    def score(self, customer: str, owned: set[str]) -> np.ndarray:
        return self.combine(*self.components(customer, owned), self.alpha)

    def top_of(self, s: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        idx = _topk(s, self.candidates)
        return idx, s[idx]

    def top(self, customer: str, owned: set[str]) -> tuple[np.ndarray, np.ndarray]:
        return self.top_of(self.score(customer, owned))


class Duplicates:
    """Dup(i, Wu) = 1 if an owned item has the same product type and content cosine >= tau (declared text-based
    stand-in for the thesis's image-embedding similarity)."""

    def __init__(self, cat: Catalogue, tau: float):
        self.cat, self.tau = cat, tau

    def flags(self, cand_idx: np.ndarray, owned: set[str]) -> np.ndarray:
        own = self.cat.idx(owned)
        if len(own) == 0 or len(cand_idx) == 0:
            return np.zeros(len(cand_idx), dtype=bool)
        sims = np.asarray((self.cat.content[cand_idx] @ self.cat.content[own].T).todense())
        same_type = self.cat.type[cand_idx][:, None] == self.cat.type[own][None, :]
        return ((sims >= self.tau) & same_type).any(axis=1)

    def is_dup_fn(self, owned: set[str]):
        own = self.cat.idx(owned)

        def is_dup(article: str) -> bool:
            i = self.cat.index.get(article)
            if i is None or len(own) == 0:
                return False
            return bool(self.flags(np.array([i]), owned)[0])
        return is_dup


@dataclass
class Reranker:
    """Eq. 3: s1 + lambda_c * Comp(i, Wu) - lambda_d * Dup(i, Wu); Comp comes from the RQ2 model when available."""

    first: FirstStage
    dup: Duplicates
    lambda_d: float
    lambda_c: float = 0.0
    comp: object | None = None  # callable(cand_idx, owned) -> np.ndarray in [0,1]

    def recommend(self, customer: str, owned: set[str], k: int = 12) -> list[str]:
        idx, s1 = self.first.top(customer, owned)
        return self.recommend_from(idx, s1, self.dup.flags(idx, owned), owned, k)

    def recommend_from(self, idx: np.ndarray, s1: np.ndarray, flags: np.ndarray, owned: set[str],
                       k: int = 12) -> list[str]:
        """Eq. 3 on a precomputed first-stage list and its duplicate flags (lambda-independent, so reusable)."""
        score = s1 - self.lambda_d * flags
        if self.comp is not None and self.lambda_c:
            score = score + self.lambda_c * self.comp(idx, owned)
        order = np.argsort(-score, kind="stable")[:k]
        return [self.first.cat.ids[i] for i in idx[order]]
