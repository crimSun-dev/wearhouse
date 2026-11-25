"""Polyvore Outfits (Vasileva et al., 2018) loader for the mvasil/fashion-compatibility release layout, plus the
item-overlap audit required before trusting the thesis's 'test items were never seen in training' claim (P0390)."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

# Polyvore semantic categories -> Wearhouse slots (11 Polyvore types; documented, versioned with the config)
SLOT_OF = {"tops": "top", "bottoms": "bottom", "all-body": "dress", "outerwear": "outer", "shoes": "footwear",
           "bags": "accessory", "jewellery": "accessory", "accessories": "accessory", "sunglasses": "accessory",
           "hats": "accessory", "scarves": "accessory"}


@dataclass
class Polyvore:
    items: dict[str, dict]                      # item_id -> metadata (title, semantic_category, ...)
    outfits: dict[str, dict[str, list[str]]]    # split -> set_id -> [item_id] in index order
    compatibility: dict[str, list[tuple[int, list[str]]]] = field(default_factory=dict)  # split -> (label, items)
    fitb: dict[str, list[dict]] = field(default_factory=dict)  # split -> {question:[ids], answers:[ids], correct:int}

    def type_of(self, item_id: str) -> str:
        return self.items[item_id].get("semantic_category", "unknown")

    def outfit_items(self, split: str) -> set[str]:
        return {i for items in self.outfits[split].values() for i in items}


def _resolve(ref: str, outfits: dict[str, list[str]]) -> str | None:
    """'<set_id>_<index>' (1-based index within the outfit) -> item_id."""
    set_id, _, idx = ref.rpartition("_")
    items = outfits.get(set_id)
    if not items or not idx.isdigit() or not 1 <= int(idx) <= len(items):
        return None
    return items[int(idx) - 1]


def load(root: Path, variant: str = "nondisjoint", splits=("train", "valid", "test")) -> Polyvore:
    meta = json.loads((root / "polyvore_item_metadata.json").read_text(encoding="utf-8"))
    outfits = {}
    for s in splits:
        raw = json.loads((root / variant / f"{s}.json").read_text(encoding="utf-8"))
        outfits[s] = {o["set_id"]: [it["item_id"] for it in sorted(o["items"], key=lambda x: x["index"])] for o in raw}
    pv = Polyvore(meta, outfits)
    for s in splits:
        comp = root / variant / f"compatibility_{s}.txt"
        if comp.exists():
            rows = []
            for line in comp.read_text(encoding="utf-8").splitlines():
                parts = line.split()
                if not parts:
                    continue
                ids = [_resolve(r, outfits[s]) for r in parts[1:]]
                if all(ids):
                    rows.append((int(parts[0]), ids))
            pv.compatibility[s] = rows
        fitb = root / variant / f"fill_in_blank_{s}.json"
        if fitb.exists():
            qs = []
            for q in json.loads(fitb.read_text(encoding="utf-8")):
                question = [_resolve(r, outfits[s]) for r in q["question"]]
                answers = [_resolve(r, outfits[s]) for r in q["answers"]]
                qset = q["question"][0].rpartition("_")[0]
                correct = [n for n, r in enumerate(q["answers"]) if r.rpartition("_")[0] == qset]
                if all(question) and all(answers) and len(correct) == 1:
                    qs.append({"question": question, "answers": answers, "correct": correct[0]})
            pv.fitb[s] = qs
    return pv


def overlap_audit(pv: Polyvore, train: str = "train", test: str = "test") -> dict:
    """How many test items also occur in training outfits (non-disjoint splits do not prevent this)."""
    tr, te = pv.outfit_items(train), pv.outfit_items(test)
    shared = tr & te
    return {"train_items": len(tr), "test_items": len(te), "test_items_seen_in_training": len(shared),
            "share": len(shared) / len(te) if te else 0.0, "unseen_test_items": len(te - tr),
            "thesis_claim_P0390_holds": len(shared) == 0}


def unseen_items(pv: Polyvore, train: str = "train", test: str = "test") -> set[str]:
    return pv.outfit_items(test) - pv.outfit_items(train)
