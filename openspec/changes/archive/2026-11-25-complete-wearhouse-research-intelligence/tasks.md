## 1. Research workspace

- [x] 1.1 Create `research/` (pyproject, pinned requirements, `.venv` ignored) with manifests (sha256 gate), configs, provenance, report writer, split roles and the `TestDataAccess` guard. Verify with unit tests: checksum mismatch refuses, same seed gives the same output, the selection guard raises, synthetic output cannot go to `reports/`.

## 2. RQ3 (complete now)

- [x] 2.1 Make `AdmissionPolicy.actor_limit` configurable (default 10, production unchanged), and build the RQ3 harness on the real API: genuine activations, the 4 false-claim families, the separate rate-limit test, response-body identity, and the Eq. 10/11 design checks. Verify a small pytest run (20 products, 1,000 guesses).
- [x] 2.2 Run RQ3 at full size ([500] real H&M products, [100,000] guesses) and commit the report. Verify 0 false acceptances, 500/500 correct placements, and the 429 on the 11th attempt.

## 3. RQ1 pipeline (data pending)

- [x] 3.1 Implement loaders (dtypes, parquet cache keyed by sha), the chronological split, the Gen Z cohort, and owned-before-cutoff, with leakage assertions. Verify on synthetic transactions.
- [x] 3.2 Implement the metrics (MAP/Recall/NDCG@12, duplicate share), the paired bootstrap and the zero-baseline rule. Verify against hand-computed values, the oracle (MAP 1), and bootstrap determinism.
- [x] 3.3 Implement popularity, item-kNN, BPR (numpy), the content embedding, the first stage, the re-ranker (Comp/Dup) and validation selection. Verify on synthetic data with planted signal: BPR beats popularity, and the re-ranker reduces the duplicate share.
- [x] 3.4 Write the RQ1 runner and report (declared deviations, success criteria evaluation). Verify an end-to-end synthetic run to a temporary directory and the manifest-pending refusal message.

## 4. RQ2 pipeline (data pending)

- [x] 4.1 Implement the Polyvore loader, the item-overlap audit, the embedding providers (text and optional FashionCLIP), and the type-aware model plus shared baseline with AUC/FITB. Verify on synthetic outfits: untrained near chance, trained above chance, analytic gradients matching numeric ones.
- [x] 4.2 Implement the simulation (attribute rules, occasion schedule, assumed climatology, hard rules, Pref/Rec, the three behaviours), the tuning/reporting split, the grid search, coverage/compatibility and Wilcoxon, and the RQ2 runner. Verify on synthetic wardrobes: rules always satisfied, recency raises coverage, the grid only sees the tuning group.

## 5. Serving

- [x] 5.1 Write migration `0010` (artifacts and neighbours), the `import-recommendations` CLI (sha-verified, audited), and the similar-items and personal endpoints with baselines and truthful `ModelInfo`. Verify: tampered artifact refused, `heuristic_baseline` without an artifact, `trained` with the hash when imported, owned excluded, published only.
- [x] 5.2 Regenerate contracts and routes; run the full suite; add a "Similar products" store section and "Recommended for you" to the pages; run e2e.

## 6. Readiness

- [x] 6.1 Write `docs/architecture/research-readiness.md`: RQ3 results, RQ1/RQ2 pipeline status and the exact commands to run when data arrives, declared deviations, the pool citations and gaps, and the disclosure note.
