# RQ2 — Outfit recommendation (methodology 3.5.2)

**Answer: NOT POSITIVE** — per behaviour: {'favourite': False, 'random': False, 'weather': False}

Embedding: **text_tfidf_svd**. Overlap audit: {'train_items': 204679, 'test_items': 47854, 'test_items_seen_in_training': 16655, 'share': 0.34803778158565635, 'unseen_test_items': 31199, 'thesis_claim_P0390_holds': False}

| Compatibility model | AUC | FITB |
|---|---|---|
| type_aware | 0.530 | 0.702 |
| shared_space | 0.515 | 0.692 |

| Behaviour / season | Coverage vs compat-only | Compatibility vs compat-only | Wilcoxon p | Met |
|---|---|---|---|---|
| favourite/rainy-start-1 | +946.1% | -5.4% | 3.8965598450959084e-18 | False |
| favourite/dry-start-7 | +965.8% | -4.5% | 3.8965598450959084e-18 | True |
| random/rainy-start-1 | +237.9% | -5.6% | 3.8965598450959084e-18 | False |
| random/dry-start-7 | +244.9% | -4.7% | 3.8965598450959084e-18 | True |
| weather/rainy-start-1 | +463.4% | -5.2% | 3.8965598450959084e-18 | False |
| weather/dry-start-7 | +476.0% | -4.6% | 3.8965598450959084e-18 | True |

H&M domain transfer (200 hand-labelled pairs): {'status': 'labels not supplied: run research/tools/label_pairs.py'}

Tuning (group 1 only): chose w = [1.0, 0.5, 0.5], h = 7.

Climatology values are **assumed** (see config) until replaced with cited BMKG figures.

## Disclosure
Code for this pipeline was written with AI assistance (Claude Code, Anthropic) under the author's direction; the author designed the study, reviewed the code and is responsible for the results. Disclose this in the thesis as required by the course's GenAI policy.
