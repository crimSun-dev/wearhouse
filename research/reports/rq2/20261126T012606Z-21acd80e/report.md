# RQ2 — Outfit recommendation (methodology 3.5.2)

**Answer: POSITIVE** — per behaviour: {'favourite': True, 'random': True, 'weather': True}

Embedding: **fashionclip_image**. Overlap audit: {'train_items': 204679, 'test_items': 47854, 'test_items_seen_in_training': 16655, 'share': 0.34803778158565635, 'unseen_test_items': 31199, 'thesis_claim_P0390_holds': False}

| Compatibility model | AUC | FITB |
|---|---|---|
| type_aware | 0.899 | 0.623 |
| shared_space | 0.856 | 0.565 |

| Behaviour / season | Coverage vs compat-only | Compatibility vs compat-only | Wilcoxon p | Met |
|---|---|---|---|---|
| favourite/rainy-start-1 | +155.5% | -2.0% | 3.8965598450959084e-18 | True |
| favourite/dry-start-7 | +145.6% | -1.3% | 3.8965598450959084e-18 | True |
| random/rainy-start-1 | +50.7% | -2.0% | 3.8965598450959084e-18 | True |
| random/dry-start-7 | +45.5% | -1.3% | 3.8965598450959084e-18 | True |
| weather/rainy-start-1 | +55.0% | -1.7% | 3.8965598450959084e-18 | True |
| weather/dry-start-7 | +53.4% | -1.1% | 4.0161556854627e-18 | True |

H&M domain transfer (200 hand-labelled pairs): {'status': 'labels not supplied: run research/tools/label_pairs.py'}

Tuning (group 1 only): chose w = [1.0, 0.0, 0.0], h = 2.

Climatology: CITED: Jakarta Kemayoran (WMO 96745) 1991-2020; rain = WMO normals rain days (>= 1 mm) per day; hot = share of days with max >= 32 C from GHCN-Daily (validated against the normals, max difference 0.023). See research/manifests/jakarta_climate.json.

Embedding coverage: {'by_image': 251008, 'by_text': 0}

Corrections: Declared corrected re-run of report 20261125T192325Z-97b5a399 (kept): (1) FashionCLIP image embeddings as the methodology specifies, replacing the text TF-IDF stand-in used because images were not yet supplied; (2) cited BMKG Kemayoran 1991-2020 climatology replacing assumed values. Targets, grids, seeds and the model settings are unchanged.

## Disclosure
Code for this pipeline was written with AI assistance (Claude Code, Anthropic) under the author's direction; the author designed the study, reviewed the code and is responsible for the results. Disclose this in the thesis as required by the course's GenAI policy.
