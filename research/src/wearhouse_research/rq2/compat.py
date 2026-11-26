"""Item embeddings + type-aware compatibility (Vasileva et al., 2018; methodology 3.4.2, Eq. 4-6, 14).

Embedding providers: TextEmbedding (TF-IDF of title + category -> TruncatedSVD; the declared fallback) or
FashionClipEmbedding (Polyvore images; optional extra). The model learns a linear projection g and a sigmoid-gated
mask per unordered type pair with the triplet loss; the shared-space baseline has no masks. Pure numpy with
analytic gradients (checked numerically in tests).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations

import numpy as np
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize


class TextEmbedding:
    name = "text_tfidf_svd"

    def __init__(self, dims: int = 128, seed: int = 0):
        self.dims, self.seed = dims, seed

    def fit_transform(self, ids: list[str], texts: list[str]) -> dict[str, np.ndarray]:
        x = TfidfVectorizer(sublinear_tf=True, min_df=1).fit_transform(texts)
        k = max(2, min(self.dims, x.shape[1] - 1, x.shape[0] - 1))
        z = normalize(TruncatedSVD(n_components=k, random_state=self.seed).fit_transform(x))
        return {i: z[n].astype(np.float32) for n, i in enumerate(ids)}


def _features(out):
    """CLIP projected features: transformers < 5 returns the tensor, 5.x a model output whose pooler_output holds the
    projected embedding."""
    return out if hasattr(out, "norm") else out.pooler_output


class FashionClipEmbedding:
    """FashionCLIP image embeddings (Chia et al., 2022) of the Polyvore item images (methodology: image term).

    Images come from the permitted Polyvore image files (parquet: item_id + JPEG bytes). Items without an image
    (and H&M transfer items, which have no permitted images) get FashionCLIP *text* embeddings of their title and
    type, in the same joint space; their count is reported (`text_fallback`). Embeddings are L2-normalised and cached
    under research/.cache keyed by the model and the image files' sha256, so re-runs skip the image pass."""
    name = "fashionclip_image"

    def __init__(self, image_files: list[Path], digests: list[str], *, model_name: str = "patrickjohncyh/fashion-clip",
                 batch: int = 256, cache_dir: Path | None = None, log=print):
        try:
            import torch  # noqa: F401
            from transformers import CLIPModel, CLIPProcessor  # noqa: F401
        except ImportError as exc:  # pragma: no cover - optional path
            raise RuntimeError("FashionCLIP needs `pip install .[fashionclip]` and the model weights") from exc
        self.image_files, self.digests, self.model_name = list(image_files), list(digests), model_name
        self.batch, self.cache_dir, self.log = batch, cache_dir, log
        self.text_fallback = 0
        self.images_embedded = 0

    def _cache_path(self) -> Path | None:
        if self.cache_dir is None:
            return None
        import hashlib
        key = hashlib.sha256(("|".join([self.model_name, *self.digests])).encode()).hexdigest()[:16]
        return self.cache_dir / f"fashionclip_images_{key}.npz"

    def _image_vectors(self, wanted: set[str]) -> dict[str, np.ndarray]:
        cache = self._cache_path()
        if cache is not None and cache.exists():
            z = np.load(cache, allow_pickle=False)
            self.log(f"FashionCLIP: {len(z['ids'])} cached image embeddings ({cache.name})")
            return {i: v for i, v in zip(z["ids"].tolist(), z["vecs"]) if i in wanted}
        import io

        import pyarrow.parquet as pq
        import torch
        from PIL import Image
        from transformers import CLIPModel, CLIPProcessor
        dev = "cuda" if torch.cuda.is_available() else "cpu"
        model = CLIPModel.from_pretrained(self.model_name).to(dev).eval()
        proc = CLIPProcessor.from_pretrained(self.model_name)
        out: dict[str, np.ndarray] = {}
        for f in self.image_files:
            for rb in pq.ParquetFile(f).iter_batches(batch_size=self.batch, columns=["item_id", "image"]):
                ids = rb.column("item_id").to_pylist()
                imgs = rb.column("image").to_pylist()
                keep = [(i, im) for i, im in zip(ids, imgs) if i not in out and im and im.get("bytes")]
                if not keep:
                    continue
                pics = [Image.open(io.BytesIO(im["bytes"])).convert("RGB") for _, im in keep]
                with torch.no_grad():
                    x = proc(images=pics, return_tensors="pt")["pixel_values"].to(dev)
                    v = _features(model.get_image_features(pixel_values=x))
                    v = torch.nn.functional.normalize(v, dim=-1).float().cpu().numpy()
                for (i, _), row in zip(keep, v):
                    out[i] = row
                if len(out) % (self.batch * 40) < self.batch:
                    self.log(f"FashionCLIP: {len(out)} images embedded")
        if cache is not None:
            cache.parent.mkdir(parents=True, exist_ok=True)
            ids = sorted(out)
            np.savez(cache, ids=np.array(ids), vecs=np.stack([out[i] for i in ids]).astype(np.float32))
        return {i: v for i, v in out.items() if i in wanted}

    def _text_vectors(self, texts: list[str]) -> np.ndarray:
        import torch
        from transformers import CLIPModel, CLIPProcessor
        dev = "cuda" if torch.cuda.is_available() else "cpu"
        model = CLIPModel.from_pretrained(self.model_name).to(dev).eval()
        proc = CLIPProcessor.from_pretrained(self.model_name)
        vecs = []
        for k in range(0, len(texts), self.batch):
            with torch.no_grad():
                t = proc(text=texts[k:k + self.batch], return_tensors="pt", padding=True, truncation=True, max_length=77)
                v = _features(model.get_text_features(**{n: x.to(dev) for n, x in t.items()}))
                vecs.append(torch.nn.functional.normalize(v, dim=-1).float().cpu().numpy())
        return np.concatenate(vecs) if vecs else np.zeros((0, 512), np.float32)

    def fit_transform(self, ids: list[str], texts: list[str]) -> dict[str, np.ndarray]:
        emb = self._image_vectors(set(ids))
        self.images_embedded = sum(1 for i in ids if i in emb)
        missing = [(i, t) for i, t in zip(ids, texts) if i not in emb]
        self.text_fallback = len(missing)
        if missing:
            for (i, _), v in zip(missing, self._text_vectors([t for _, t in missing])):
                emb[i] = v
        self.log(f"FashionCLIP: {self.images_embedded} items by image, {self.text_fallback} by text")
        return {i: emb[i].astype(np.float32) for i in ids}


def pair_key(a: str, b: str) -> tuple[str, str]:
    return (a, b) if a <= b else (b, a)


@dataclass
class TypeAwareModel:
    dim_in: int
    dim: int = 64
    margin: float = 0.2
    lr: float = 0.05
    reg: float = 1e-4
    epochs: int = 10
    typed: bool = True  # False = shared-space baseline (masks fixed at 1)
    seed: int = 0
    W: np.ndarray = field(init=False)
    masks: dict = field(init=False, default_factory=dict)  # pair -> mask logits

    def __post_init__(self):
        rng = np.random.default_rng(self.seed)
        self.W = (rng.normal(0, 1 / np.sqrt(self.dim_in), (self.dim_in, self.dim))).astype(np.float64)

    def _mask(self, ta: str, tb: str) -> np.ndarray:
        if not self.typed:
            return np.ones(self.dim)
        logits = self.masks.setdefault(pair_key(ta, tb), np.zeros(self.dim))
        return 1 / (1 + np.exp(-logits))

    def distance(self, xa, xb, ta, tb) -> float:
        diff = (xa - xb) @ self.W
        return float(np.sum((diff * self._mask(ta, tb)) ** 2))

    def compat(self, xa, xb, ta, tb) -> float:
        """Distance -> (0, 1]: 1 / (1 + d) (Eq. 6 transformation, documented)."""
        return 1.0 / (1.0 + self.distance(xa, xb, ta, tb))

    def outfit_compat(self, emb: dict, types: dict, items: list[str]) -> float:
        pairs = list(combinations(items, 2))
        if not pairs:
            return 1.0
        return float(np.mean([self.compat(emb[a], emb[b], types[a], types[b]) for a, b in pairs]))

    # ------------------------------------------------------------------ training
    def triplet_grads(self, xa, xp, xn, ta, tp, tn):
        """Loss and analytic gradients of max(0, d(a,p) - d(a,n) + margin)."""
        mp, mn = self._mask(ta, tp), self._mask(ta, tn)
        dp_vec, dn_vec = (xa - xp) @ self.W, (xa - xn) @ self.W
        dp, dn = np.sum((dp_vec * mp) ** 2), np.sum((dn_vec * mn) ** 2)
        loss = dp - dn + self.margin
        if loss <= 0:
            return 0.0, np.zeros_like(self.W), {}
        # d/dW of sum((W^T u * m)^2) = 2 * outer(u, (W^T u) * m^2)
        gW = 2 * np.outer(xa - xp, dp_vec * mp ** 2) - 2 * np.outer(xa - xn, dn_vec * mn ** 2)
        gm = {}
        if self.typed:
            # d/dlogit of sum((v*sigmoid(l))^2) = 2 v^2 s * s(1-s)
            sp_, sn_ = mp, mn
            gm[pair_key(ta, tp)] = gm.get(pair_key(ta, tp), 0) + 2 * dp_vec ** 2 * sp_ * sp_ * (1 - sp_)
            gm[pair_key(ta, tn)] = gm.get(pair_key(ta, tn), 0) - 2 * dn_vec ** 2 * sn_ * sn_ * (1 - sn_)
        return float(loss), gW, gm

    def fit(self, triplets: list[tuple], emb: dict, types: dict) -> list[float]:
        rng = np.random.default_rng(self.seed)
        history = []
        for _ in range(self.epochs):
            total = 0.0
            for t in rng.permutation(len(triplets)):
                a, p, n = triplets[t]
                loss, gW, gm = self.triplet_grads(emb[a], emb[p], emb[n], types[a], types[p], types[n])
                if loss:
                    self.W -= self.lr * (gW + self.reg * self.W)
                    for k, g in gm.items():
                        self.masks[k] = self.masks.setdefault(k, np.zeros(self.dim)) - self.lr * g
                total += loss
            history.append(total / max(1, len(triplets)))
        return history


def make_triplets(outfits: dict[str, list[str]], types: dict, rng: np.random.Generator, per_outfit: int = 4):
    """Anchor a and positive p from the same outfit; negative n of p's type from a different outfit (3.4.2)."""
    by_type: dict[str, list[tuple[str, str]]] = {}
    for sid, items in outfits.items():
        for i in items:
            by_type.setdefault(types[i], []).append((sid, i))
    out = []
    sets = list(outfits.items())
    for sid, items in sets:
        if len(items) < 2:
            continue
        for _ in range(per_outfit):
            a, p = rng.choice(items, 2, replace=False)
            pool = by_type.get(types[p], [])
            if len(pool) < 2:
                continue
            for _ in range(5):
                nsid, n = pool[int(rng.integers(len(pool)))]
                if nsid != sid:
                    out.append((a, p, n))
                    break
    return out


def auc(pos: list[float], neg: list[float]) -> float:
    """Probability a real outfit outscores a fake one (Mann-Whitney U / (n_pos * n_neg)); ties count half."""
    if not pos or not neg:
        return float("nan")
    p, n = np.asarray(pos), np.asarray(neg)
    wins = (p[:, None] > n[None, :]).sum() + 0.5 * (p[:, None] == n[None, :]).sum()
    return float(wins / (len(p) * len(n)))


def fitb_accuracy(model: TypeAwareModel, emb: dict, types: dict, questions: list[dict]) -> float:
    if not questions:
        return float("nan")
    right = 0
    for q in questions:
        scores = [np.mean([model.compat(emb[c], emb[o], types[c], types[o]) for o in q["question"]])
                  for c in q["answers"]]
        right += int(np.argmax(scores) == q["correct"])
    return right / len(questions)
