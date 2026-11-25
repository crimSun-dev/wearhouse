"""SYNTHETIC (generated) H&M-shaped data with a planted signal, for validating RQ1 mechanics only. Never reported."""
from __future__ import annotations

import numpy as np
import pandas as pd

from wearhouse_research.core import Manifest

STYLES = ["denim", "floral", "sport", "office", "boho", "noir"]
TYPES = [("T-shirt", "Garment Upper body"), ("Trousers", "Garment Lower body"), ("Dress", "Garment Full body"),
         ("Sneakers", "Shoes")]
SYNTH_MANIFEST = Manifest("synthetic_hm", "permitted", {"basis": "synthetic"}, {}, synthetic=True)


def make(n_users=300, n_items=240, weeks=10, seed=7):
    rng = np.random.default_rng(seed)
    arts = []
    for i in range(n_items):
        style = STYLES[i % len(STYLES)]
        ptype, group = TYPES[(i // len(STYLES)) % len(TYPES)]
        arts.append({"article_id": f"0{900000000 + i}", "prod_name": f"{style} {ptype.lower()} {i}",
                     "product_type_name": ptype, "product_group_name": group,
                     "colour_group_name": ["Black", "White", "Blue"][i % 3], "perceived_colour_master_name": "",
                     "graphical_appearance_name": "Solid", "section_name": f"{style} section",
                     "garment_group_name": ptype, "index_group_name": "Ladieswear",
                     "detail_desc": f"A {style} style {ptype.lower()} in the {style} line."})
    articles = pd.DataFrame(arts)
    by_style = {s: articles.index[articles["prod_name"].str.startswith(s)].to_numpy() for s in STYLES}
    customers = pd.DataFrame({"customer_id": [f"c{u:05d}" for u in range(n_users)],
                              "age": [np.nan if u % 10 == 0 else (19 if u % 3 else 35) for u in range(n_users)]})
    start = pd.Timestamp("2020-07-01")
    rows = []
    for u in range(n_users):
        pref = STYLES[u % len(STYLES)]
        for d in range(weeks * 7):
            if rng.random() < 0.12:
                pool = by_style[pref] if rng.random() < 0.85 else articles.index.to_numpy()
                item = arts[int(rng.choice(pool))]["article_id"]
                rows.append({"t_dat": start + pd.Timedelta(days=d), "customer_id": f"c{u:05d}", "article_id": item,
                             "price": 0.02, "sales_channel_id": 2})
    tx = pd.DataFrame(rows)
    tx["t_dat"] = pd.to_datetime(tx["t_dat"])
    return tx, customers, articles
