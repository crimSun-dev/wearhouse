"""SYNTHETIC Polyvore-Outfits-format data (generated) for validating RQ2 mechanics only. Never reported."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from wearhouse_research.core import Manifest

STYLES = ["street", "office", "boho", "sport", "evening", "rainy"]
PIECES = {"tops": ["tee", "long sleeve shirt", "blouse", "tank"], "bottoms": ["jeans", "maxi skirt", "shorts", "trousers"],
          "shoes": ["sneaker", "rain boot", "heel", "sandal"], "outerwear": ["trench coat", "wool coat", "denim jacket"],
          "all-body": ["maxi dress", "mini dress"], "bags": ["tote", "clutch"]}
SYNTH_MANIFEST = Manifest("synthetic_polyvore", "permitted", {"basis": "synthetic"}, {}, synthetic=True)


def write(root: Path, n_items_per=40, outfits_per_split=(160, 20, 60), overlap: int = 0, seed=3) -> Path:
    rng = np.random.default_rng(seed)
    meta, by = {}, {}
    n = 0
    for cat, words in PIECES.items():
        for k in range(n_items_per):
            style = STYLES[k % len(STYLES)]
            iid = f"{100000 + n}"
            meta[iid] = {"semantic_category": cat, "title": f"{style} {words[k % len(words)]} {style}"}
            by.setdefault((style, cat), []).append(iid)
            n += 1
    splits, sid = {}, 0
    used_test: list[str] = []
    for split, count in zip(("train", "valid", "test"), outfits_per_split):
        outs = []
        for _ in range(count):
            style = STYLES[int(rng.integers(len(STYLES)))]
            cats = ["tops", "bottoms", "shoes"] if rng.random() < 0.7 else ["all-body", "shoes"]
            if rng.random() < 0.5:
                cats.append("outerwear")
            items = [str(rng.choice(by[(style, c)])) for c in cats]
            outs.append({"set_id": str(sid), "items": [{"item_id": i, "index": j + 1} for j, i in enumerate(items)]})
            sid += 1
        splits[split] = outs
    if overlap:  # force some test items to appear in training outfits
        for o, t in zip(splits["train"][:overlap], splits["test"][:overlap]):
            o["items"][0]["item_id"] = t["items"][0]["item_id"]
    d = root / "nondisjoint"
    d.mkdir(parents=True, exist_ok=True)
    (root / "polyvore_item_metadata.json").write_text(json.dumps(meta))
    for s, outs in splits.items():
        (d / f"{s}.json").write_text(json.dumps(outs))
    test = splits["test"]
    lines = []
    for o in test:
        refs = [f"{o['set_id']}_{it['index']}" for it in o["items"]]
        lines.append("1 " + " ".join(refs))
        # fake outfit: each item replaced by a random item of the SAME TYPE from a different outfit (thesis 3.5.2)
        fake = []
        for it in o["items"]:
            cat = meta[it["item_id"]]["semantic_category"]
            cands = [(t["set_id"], x["index"]) for t in test if t["set_id"] != o["set_id"] for x in t["items"]
                     if meta[x["item_id"]]["semantic_category"] == cat]
            sid_, idx = cands[int(rng.integers(len(cands)))]
            fake.append(f"{sid_}_{idx}")
        lines.append("0 " + " ".join(fake))
    (d / "compatibility_test.txt").write_text("\n".join(lines))
    fitb = []
    for o in test:
        refs = [f"{o['set_id']}_{it['index']}" for it in o["items"]]
        others = [t for t in test if t["set_id"] != o["set_id"]]
        wrong = [f"{others[int(rng.integers(len(others)))]['set_id']}_1" for _ in range(3)]
        fitb.append({"question": refs[:-1], "answers": [refs[-1]] + wrong, "blank_position": len(refs)})
    (d / "fill_in_blank_test.json").write_text(json.dumps(fitb))
    return root
