## Purpose

Answers RQ1: whether owned-item-aware catalogue recommendations improve accuracy over simpler methods while reducing duplicates (methodology §3.4.1, §3.5.1).

## ADDED Requirements

### Requirement: Chronological split and cohort
The pipeline SHALL:
- split H&M transactions chronologically: the final week is test, the prior week validation, and earlier weeks training;
- define test customers as those aged ≤ 23 in September 2020 with at least one test purchase, excluding missing ages and counting them in the report;
- compute "owned" items only from purchases before each evaluation cutoff.

#### Scenario: No leakage
- **WHEN** the split is built
- **THEN** no training or validation feature uses a transaction dated within or after the evaluated week, and a check asserts it

### Requirement: Baselines, first stage and re-ranker
The pipeline SHALL produce, for every test customer, a list of 12 from each of:
- popularity of the previous week;
- item-based nearest neighbour over co-purchases;
- BPR-MF;
- the first stage alone: a BPR score rescaled to [0, 1], combined by α with the cosine similarity between the customer profile and item content embeddings, taking the top [300];
- the full re-ranker: first stage + λc·Comp − λd·Dup.

α, λc, λd and τ SHALL be chosen on the validation week. When image embeddings are unavailable, the content embedding SHALL be the declared text/attribute fallback, recorded in the report and the model mode.

#### Scenario: Declared fallback
- **WHEN** no permitted product images exist
- **THEN** the report states `content_embedding: text_attributes` (not FashionCLIP), and every claim is qualified accordingly

### Requirement: Measures and statistics
The report SHALL give MAP@12, Recall@12, NDCG@12 and the duplicate share for every method. It SHALL include 95% confidence intervals from a paired customer bootstrap with 1,000 resamples and a fixed seed, the relative MAP change against the best baseline, and the duplicate-share change against the first stage. The handling of a zero baseline SHALL be defined before computing relative changes. Success is judged against the bracketed targets (+10% MAP, −30% duplicates), and any accuracy loss SHALL be reported next to the duplicate reduction.

#### Scenario: Metric correctness
- **WHEN** the metrics run on hand-computed synthetic lists
- **THEN** they equal the hand values, and an oracle that ranks the true purchases first scores MAP@12 = 1
