## Why

The thesis (methodology v11, §§3.4–3.5) defines four research questions. Wearhouse currently answers none of them with evidence: suggestions are a labelled heuristic, and registration security is tested but not run as the RQ3 experiment. The user's direction on 2026-11-25 is to finish research before the frontend. The H&M transactions/customers files and Polyvore Outfits will be supplied later. Product images are generated placeholders, so they carry **no visual signal**.

This change therefore:
- runs **RQ3 completely now**;
- builds **RQ1 and RQ2 as complete, tested pipelines** that produce their reports as soon as the data lands;
- integrates serving with **truthful model modes**;
- leaves RQ4 (avatar frame rate) to the frontend change, where the avatar exists.

## What Changes

- **A research workspace** (`research/`) with its own pinned environment, separate from the API runtime. It provides dataset manifests (sha256 and permission recorded; a mismatch refuses to run), frozen experiment configs, seeds, and machine-readable reports with environment and hash provenance. Nothing tunes on test data.
- **RQ3 experiment** (§3.5.3). It uses the real v2 API in a disposable database and [500] real H&M catalogue products. The steps:
  1. Genuine activations land in the correct wardrobe and category.
  2. Four false-claim families run at the validation layer with rate limiting disabled, so the limiter cannot mask a validation failure: [100,000] random guesses, altered genuine codes, public QR contents, and reused codes by the same and another user.
  3. A separate rate-limit test checks that attempts above 10 per user per hour are refused.
  4. The design checks (Eq. 10 and Eq. 11) are computed.

  The output is a report.
- **RQ1 pipeline** (§3.4.1, §3.5.1):
  - **Split:** chronological (test week, then validation week, then training), and Gen Z test customers (age ≤ 23 in September 2020) with at least one test purchase.
  - **Baselines:** popularity, item-based nearest neighbour, BPR-MF, and the first stage alone.
  - **First stage:** BPR plus a content term, with α chosen on validation.
  - **Re-ranker:** with Comp and Dup, and λ values chosen on validation.
  - **Measures:** MAP@12, Recall@12, NDCG@12 and duplicate share, with a paired customer bootstrap (1,000 resamples, 95% CI).

  **Declared deviation:** the FashionCLIP image term is unavailable because there are no permitted product images. It is replaced by a text/attribute embedding (TF-IDF over the description plus attributes), recorded in the model mode. The success criteria are evaluated as written.
- **RQ2 pipeline** (§3.4.2–3.4.3, §3.5.2):
  - Polyvore loader with an **item-overlap audit** of the non-disjoint split; the thesis P0390 "unseen items" claim must be resolved, not assumed.
  - A type-aware compatibility model with per-type-pair masks and triplet loss, against a shared-space baseline, measured by AUC and FITB.
  - A simulated wardrobe study: 40–80 items, 30 days, 3 behaviours, dry and rainy starts, 5 seeds, and 100 tuning / 100 reporting users. Grid search for w1–w3 and h runs on the tuning group only.
  - Ablations for compatibility-only, no-context and no-recency; coverage and compatibility measures; a paired Wilcoxon test.

  Embeddings are pluggable: FashionCLIP on Polyvore images when the weights are present, otherwise a declared text fallback.
- **Synthetic validation of every pipeline.** Small generated datasets, clearly labelled `synthetic_only`, prove the mechanics:
  - metric values on hand-computed cases;
  - split leakage checks;
  - bootstrap determinism;
  - an oracle recommender scoring MAP of 1.

  They never produce reported results.
- **Serving integration.** The API gains catalogue recommendations (`GET /me/recommendations/products`) and similar-items (`GET /catalogue/products/{id}/similar`). Both are served from versioned artifacts imported with sha256 manifests. Each declares its `ModelInfo`: trained, with an artifact hash, only when a trained artifact is loaded; otherwise a labelled popularity or content baseline. Outfit suggestions keep the heuristic baseline until an RQ2 artifact is imported.

## Capabilities

### New Capabilities
- `research-reproducibility`: manifests, configs, seeds, provenance, and the no-test-tuning rule.
- `rq3-registration-evaluation`: the full RQ3 experiment and report.
- `rq1-catalogue-recommender`: the RQ1 pipeline, baselines, measures and report.
- `rq2-outfit-recommender`: the compatibility model, simulation, measures and report.
- `recommendation-serving`: artifact import and the recommendation endpoints with truthful modes.

### Modified Capabilities
None archived. This extends the foundation recommendation ports and the wardrobe suggestion contract.

## Impact

- New `research/` project (Python 3.11, numpy/pandas/scipy, with optional torch/transformers for FashionCLIP).
- The API `recommendations` module gains artifact-backed rankers.
- Migration `0010_recommendation_artifacts`; new routes; contracts regenerated.
- **Data:** nothing is committed; datasets stay in git-ignored folders with manifests.
