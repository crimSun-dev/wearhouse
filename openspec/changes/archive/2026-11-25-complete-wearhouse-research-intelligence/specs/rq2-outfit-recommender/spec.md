## Purpose

Answers RQ2: whether context- and wear-aware outfit recommendation widens wardrobe use without hurting compatibility (methodology §3.4.2–3.4.3, §3.5.2).

## ADDED Requirements

### Requirement: Polyvore audit before modelling
Before training, the pipeline SHALL audit the non-disjoint Polyvore split for item overlap between train and test, and record the overlapping item count. Thesis P0390 claims test items were never seen in training. If overlap is non-zero, the simulation SHALL draw wardrobes from a constructed **unseen-item subset**, or the claim SHALL be revised in the report; a disjoint-split sensitivity evaluation SHALL be added. The primary benchmark SHALL NOT be silently changed.

#### Scenario: Overlap found
- **WHEN** test items also appear in training outfits
- **THEN** the report states the count, and the simulation uses only unseen items

### Requirement: Type-aware compatibility
The compatibility model SHALL learn a projection g and per-type-pair masks with a triplet loss of margin μ, over fixed item embeddings: FashionCLIP on Polyvore images when the weights are available, otherwise the declared text fallback. It SHALL report compatibility AUC (fake outfits of same-type random replacements) and FITB accuracy (4 candidates) on the test split, against a shared-space baseline.

#### Scenario: Chance levels
- **WHEN** the model is untrained (random weights)
- **THEN** AUC is approximately 0.5 and FITB approximately 25% on synthetic data, which confirms the metric implementation

### Requirement: Simulated wardrobe study
The pipeline SHALL run each of the following:
- the full recommender: hard rules for slots, heat, rain and dress code, then w1·Comp + w2·Pref − w3·Rec with the Beta-smoothed preference (p0 0.5, a 5) and recency decay h;
- compatibility-only;
- no-context;
- no-recency.

Each run SHALL cover 30 days, the 3 behaviours, dry-season and rainy-season starts, and 5 seeds. Wardrobes SHALL hold [40–80] items with the minimum slot counts. Users SHALL be split 100 tuning / 100 reporting, with the grid search for w1–w3 and h on the tuning group only. The pipeline SHALL report coverage (Eq. 15) and the mean compatibility of worn outfits per behaviour and season, with seed mean and standard deviation and a paired Wilcoxon test at 5%. Zero-difference handling SHALL be defined beforehand. Rule satisfaction SHALL be reported only as a correctness check.

#### Scenario: Reporting group untouched by tuning
- **WHEN** the grid search runs
- **THEN** it receives only tuning-group users, and the reporting group is scored once with the chosen settings
