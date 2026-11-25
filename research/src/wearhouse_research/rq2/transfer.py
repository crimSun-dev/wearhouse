"""RQ2 domain transfer to H&M (thesis §3.5.2: 200 hand-labelled H&M pairs; complete-wearhouse-tdd 4.2).

The owner labels cross-type H&M article pairs ("do these go together?") with research/tools/label_pairs.py. Labels are
never generated. With labels pinned in a manifest, the Polyvore-trained compatibility model scores each pair and the
report states transfer AUC. Without them it states that the labels are not supplied.
Texts only: H&M images are not part of the permitted local data, the same declared deviation as RQ1.
"""
from __future__ import annotations

import csv
import random
from pathlib import Path

import numpy as np

# H&M product group/type -> Polyvore semantic category (the RQ2 type vocabulary)
GROUP_TYPE = {"Garment Upper body": "tops", "Garment Lower body": "bottoms", "Garment Full body": "all-body",
              "Shoes": "shoes"}
OUTER_TYPES = {"Jacket", "Coat", "Blazer", "Outdoor Waistcoat"}
ACCESSORY_TYPE = {"Bag": "bags", "Earring": "jewellery", "Earrings": "jewellery", "Necklace": "jewellery",
                  "Ring": "jewellery", "Bracelet": "jewellery", "Hat/beanie": "hats", "Cap/peaked": "hats",
                  "Hat/brim": "hats", "Beanie": "hats", "Sunglasses": "sunglasses", "Scarf": "scarves"}
# stratification: cross-type combinations sampled evenly (200 / 8 = 25 each)
STRATA = [("tops", "bottoms"), ("tops", "shoes"), ("bottoms", "shoes"), ("all-body", "shoes"), ("outerwear", "tops"),
          ("tops", "bags"), ("all-body", "jewellery"), ("bottoms", "outerwear")]
PAIR_FIELDS = ["pair_id", "a_article_id", "a_type", "a_text", "b_article_id", "b_type", "b_text"]


def polyvore_type(row: dict) -> str | None:
    group, ptype = row.get("product_group_name", ""), row.get("product_type_name", "")
    if group == "Accessories":
        return ACCESSORY_TYPE.get(ptype)
    t = GROUP_TYPE.get(group)
    return "outerwear" if t == "tops" and ptype in OUTER_TYPES else t


def article_text(row: dict) -> str:
    return " ".join(x for x in (row.get("prod_name"), row.get("product_type_name"), row.get("colour_group_name"),
                                row.get("detail_desc")) if x)


def sample_pairs(rows: list[dict], n: int = 200, seed: int = 20261126) -> list[dict]:
    """Seeded, stratified sample of cross-type pairs; no article is used twice."""
    rng = random.Random(seed)
    by_type: dict[str, list[dict]] = {}
    for r in rows:
        t = polyvore_type(r)
        if t:
            by_type.setdefault(t, []).append(r)
    for v in by_type.values():
        rng.shuffle(v)
    used: set[str] = set()
    per = n // len(STRATA)
    pairs = []
    for ta, tb in STRATA:
        for _ in range(per):
            a = next(x for x in by_type[ta] if x["article_id"] not in used)
            used.add(a["article_id"])
            b = next(x for x in by_type[tb] if x["article_id"] not in used)
            used.add(b["article_id"])
            pairs.append({"pair_id": f"p{len(pairs) + 1:03d}", "a_article_id": a["article_id"], "a_type": ta,
                          "a_text": article_text(a), "b_article_id": b["article_id"], "b_type": tb,
                          "b_text": article_text(b)})
    return pairs


def write_pairs(path: Path, pairs: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, PAIR_FIELDS)
        w.writeheader()
        w.writerows(pairs)


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def labelled(pairs_path: Path, labels_path: Path) -> list[dict]:
    """Pairs joined with their latest label; 'unsure' is excluded from evaluation (reported as a count)."""
    latest = {r["pair_id"]: r["label"] for r in read_csv(labels_path)} if labels_path.exists() else {}
    return [{**p, "label": latest[p["pair_id"]]} for p in read_csv(pairs_path) if p["pair_id"] in latest]


def auc(pos: list[float], neg: list[float]) -> float | None:
    if not pos or not neg:
        return None
    p, q = np.asarray(pos), np.asarray(neg)
    return float(((p[:, None] > q[None, :]).sum() + 0.5 * (p[:, None] == q[None, :]).sum()) / (len(p) * len(q)))


def evaluate_transfer(model, emb: dict, rows: list[dict]) -> dict:
    pos, neg = [], []
    for r in rows:
        if r["label"] not in ("yes", "no"):
            continue
        s = model.compat(emb["hm:" + r["a_article_id"]], emb["hm:" + r["b_article_id"]], r["a_type"], r["b_type"])
        (pos if r["label"] == "yes" else neg).append(s)
    return {"status": "evaluated", "labelled_pairs": len(rows), "yes": len(pos), "no": len(neg),
            "unsure_excluded": sum(1 for r in rows if r["label"] == "unsure"), "auc": auc(pos, neg)}
