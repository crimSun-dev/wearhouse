# Research readiness (complete-wearhouse-research-intelligence)

Date: 2026-11-25. This records what each research question has proven, what is built but waiting for data, and how to run it.

## Summary

| RQ | Question | State |
|---|---|---|
| RQ3 | Can genuine garments be registered while false claims are refused? | **Answered: POSITIVE** on 500 real H&M products through the real API |
| RQ1 | Does a compatibility/duplicate-aware re-ranker beat the baselines for Gen Z customers? | Pipeline built and tested on synthetic H&M-format data. **Waiting for** `transactions_train.csv` + `customers.csv` |
| RQ2 | Do weather and rotation-aware outfit suggestions keep compatibility while improving coverage? | Pipeline built and tested on synthetic Polyvore-format data. **Waiting for** Polyvore Outfits (and its terms) |
| Serving | Can research models reach the product truthfully? | Done: sha-verified artifact import, `similar` and `for me` endpoints that always declare their model mode |

No synthetic result is ever written under `research/reports/`: `write_report` refuses it, and the synthetic runs write to temporary folders only.

## RQ3 result

Report: `research/reports/rq3/20261125T150923Z-a2983ef3/report.md` (+ `report.json`). Run 2026-11-25 15:09 UTC, 2,024 s wall time, seed 20261125, commit `ea21b05` with a dirty tree (the v2 work was not committed yet; the report records this).

| Check | Result |
|---|---|
| Genuine activations | 500 / 500 placed in the right buyer's wardrobe, right category and slot |
| Random guesses (CSPRNG) | 100,000 attempts, 0 accepted |
| Real keys with 1–3 characters altered | 1,500 attempts, 0 accepted |
| Public QR contents (serial and discovery URL) | 1,000 attempts, 0 accepted |
| Claimed key reused by owner / another user / its own redeemer | 500 + 500 + 500 attempts, 0 accepted |
| Distinct rejection bodies | 1 (`INVALID_ACTIVATION_CODE`) |
| Rate limit (production limits) | first 10 → 400, 11th → 429 with `Retry-After: 3600`, an independent user unaffected |

Design checks (calculations, not findings): serial collision bound at 10⁹ garments, 128 bits = 1.47×10⁻²¹ (target < 10⁻²⁰); one-year online guessing bound = 7.25×10⁻¹⁴ (target < 10⁻¹⁰); offline brute force of one 80-bit key at 10¹⁰ guesses/s ≈ 3.8 million years.

Reproduce (API venv, local PostgreSQL admin URL in `WEARHOUSE_TEST_ADMIN_URL`, the H&M articles file in `H&M DATABASE/`):

```bash
cd research
PYTHONPATH=src ../apps/api/.venv/Scripts/python.exe -m wearhouse_research.rq3 --config configs/rq3.json
```

## Running RQ1 when the data arrives

1. Put `transactions_train.csv` and `customers.csv` in `H&M DATABASE/` (git-ignored; Kaggle rules forbid redistribution).
2. Write their sha256 into `research/manifests/hm_transactions.json` (replace the `TO_FILL…` values) and set `"status": "permitted"`. The loader refuses a mismatch.
3. Run (first run builds a parquet cache keyed by the sha):

```bash
PYTHONPATH=research/src research/.venv/Scripts/python.exe -m wearhouse_research.rq1.run --config research/configs/rq1.json
```

4. To serve the winning model, export it with `research/src/wearhouse_research/export.py` (`from_bpr` → mode `trained` with the factor-matrix hash; `from_itemknn` → `heuristic_baseline`) and import it:

```bash
wearhouse import-recommendations --artifact <dir> --operator-issuer urn:wearhouse:operator --operator-subject catalogue-import
```

Settings frozen before any run (`configs/rq1.json`): 300 candidates, τ 0.90, targets +10 % MAP@12 and −30 % duplicate share, 1,000 paired bootstrap resamples, Gen Z ≤ 23, 12 training weeks.

## Running RQ2 when the data arrives

1. Unpack Polyvore Outfits to `research/data/polyvore_outfits/` (git-ignored).
2. Record the terms you accepted in `research/manifests/polyvore_outfits.json` (`permission` is blank on purpose; the loader refuses a blank permission), fill in each file's sha256 and set `"status": "permitted"`.
3. Replace the **ASSUMED** monthly climatology in `configs/rq2.json` with cited BMKG climatological normals for Jakarta, or keep them and leave the report's "assumed" label in place.
4. Run:

```bash
PYTHONPATH=research/src research/.venv/Scripts/python.exe -m wearhouse_research.rq2.run --config research/configs/rq2.json
```

## RQ1 result (real H&M data, 2026-11-26)

Report: `research/reports/rq1/20261125T205603Z-f1630668`, with 15,292 Gen Z customers in the test week. Settings were chosen on the validation week only: alpha 0.5, lambda_d 0.05.

| Method | MAP@12 [95% CI] | Duplicate share |
|---|---|---|
| popularity | 0.0106 [0.0096, 0.0117] | 0.016 |
| item_knn | 0.0056 | 0.213 |
| bpr | 0.0089 | 0.084 |
| first_stage (Eq. 2) | 0.0103 | 0.391 |
| reranked (Eq. 3) | 0.0080 [0.0069, 0.0091] | 0.174 |

**Not positive.** The reranker cuts duplicates by 56% compared with the first stage, which meets the 30% target. MAP@12 is 25% below the best simpler baseline (popularity) against a +10% target; the paired 95% CI of the difference, [−0.0040, −0.0012], excludes zero. BPR does not beat popularity either, so no RQ1 serving artifact is exported. The serving stack keeps the heuristic rerank.

Limitations to discuss:
- The content term uses text only, because there are no permitted H&M images.
- Popularity of the previous week is a strong baseline on H&M.
- Training uses 12 weeks.

The selection code was later sped up by reusing each customer's scores across the grid. The results are identical; `tests/test_rq1.py::test_shared_score_selection_equals_reference` checks this, and a check on 400 real customers matched exactly.

## RQ2 result (corrected re-run, 2026-11-26)

Report `research/reports/rq2/20261126T012606Z-21acd80e`, a declared correction of `20261125T192325Z-97b5a399` (kept).
Two inputs changed: FashionCLIP image embeddings (251,008 Polyvore items, all from images) and the cited Kemayoran
climatology. Targets, grids, seeds and model settings are unchanged.

**Answer: positive under the pre-registered rule**: coverage >= +20% with compatibility within 5%, for all three
behaviours.

| Model | AUC | FITB |
|---|---|---|
| type_aware | 0.899 (first run 0.530) | 0.623 (first run 0.702) |
| shared_space | 0.856 | 0.565 |

| Behaviour / season | Coverage | Compatibility |
|---|---|---|
| favourite rainy / dry | +155.5% / +145.6% | -2.0% / -1.3% |
| random rainy / dry | +50.7% / +45.5% | -2.0% / -1.3% |
| weather rainy / dry | +55.0% / +53.4% | -1.7% / -1.1% |

**Read this before citing the result.**

- *Rotation was not the cause.* Tuning chose w = [1, 0, 0]. That turns off both the preference term (Eq. 8) and the
  recency/rotation term (Eq. 9), so h has no effect. Every setting with w2 or w3 above 0 lost more than 5%
  compatibility on the tuning group, against the stronger image model. The coverage gain is therefore the Eq. 7
  compatibility score plus the hard weather and occasion rules, compared with compatibility alone. Rotation weights
  did not survive the margin. (In the first run, w = [1, 0.5, 0.5], h = 7 was chosen.)
- *FITB fell* (0.702 to 0.623) while AUC rose. The cause has not been investigated.
- *Wilcoxon p* is the same in most rows (3.9e-18): that is the floor for 100 paired users when every difference has
  the same sign.
- *Overlap audit*: 34.8% of test items also appear in training (non-disjoint split), so the thesis claim P0390 does
  not hold. Disclose this.
- *H&M domain transfer* is not reported: the owner deferred the 200 labels.
- *This is a re-run after a negative result.* Both reports are kept and the corrections are declared. Report both.

## RQ2 climate (cited, replaces the assumed placeholder)

`research/tools/climatology.py` builds the monthly rain and hot-day probabilities for BMKG Stasiun Meteorologi Kemayoran, Jakarta (WMO 96745), 1991–2020:
- **Rain** comes from the WMO 1991–2020 normals that BMKG submitted (NCEI accession 0253808): days with at least 1 mm of precipitation, divided by the days in the month.
- **Hot** is the share of days with a maximum of 32 °C or more, from the station's daily series in NOAA GHCN-Daily. The normals publish only 30 °C and 35 °C counts. The daily series agrees with the official 30 °C counts to within 0.023 in every month.

Sources, checksums and the per-month validation are in `research/manifests/jakarta_climate.json`. The first RQ2 report (`20261125T192325Z-97b5a399`) used the assumed values; it is kept and superseded by the corrected re-run.

## RQ2 domain transfer: 200 hand-labelled H&M pairs (owner)

The thesis requires 200 hand-labelled H&M pairs to check whether the Polyvore-trained compatibility model transfers to H&M. You label them; nothing is generated. 200 seeded, stratified cross-type pairs (25 per type combination) are already in `research/data/hm_transfer_pairs.csv`, which is git-ignored.

```bash
research/.venv/Scripts/python.exe research/tools/label_pairs.py serve     # http://127.0.0.1:8765, answer Yes/No/Unsure
research/.venv/Scripts/python.exe research/tools/label_pairs.py finalize  # pins the labels (sha256 manifest)
```

The next RQ2 run then reports transfer AUC. "Unsure" answers are excluded and counted. The labelling uses text only, because H&M images are not in the permitted local data.

## Declared deviations

- **RQ3**: 500 real H&M rows instead of a generated test catalogue; the QR payload is the Wearhouse discovery URL, not a GS1 Digital Link (H&M article ids are not GTINs); false-claim families run with admission limits off so the limiter cannot hide validation failures (the limiter is tested separately); slot placement is checked against mapping `hm-articles@1`.
- **RQ1**: no permitted product images exist (catalogue images are generated placeholders), so the FashionCLIP image term (Eq. 2) and the image-similarity duplicate term (Eq. 3) use a TF-IDF text/attribute embedding. Comp (Eq. 3) needs an RQ2 compatibility artifact; λc = 0 until one exists.
- **RQ2**: text embeddings by default (FashionCLIP optional, declared in the report); climatology is assumed until replaced with cited BMKG figures.

## Pool grounding

| Decision | Citation | Tier |
|---|---|---|
| Chronological split, no peeking at the test week (`TestDataAccess` guard) | COMP3315_AI_FOUNDATIONS TRAP-003, TRAP-005 | DIRECT |
| Baselines first; a model must beat popularity before it is claimed | COMP3315_AI_FOUNDATIONS TRAP-013 | DIRECT |
| Declared, reproducible settings frozen before running | COMP3315_AI_FOUNDATIONS TRAP-016 | DIRECT |
| Generic rejection, rate limits, no enumeration (RQ3) | SNHU_CS_305 AXIOM-082, AXIOM-083/095, RULE-074/082, TRAP-054/060 | CONVERGENT |
| Layered limits | SYSTEM_DESIGN RULE-033 / TRAP-018 | DIRECT |
| Paired bootstrap / Wilcoxon | SOPHIA statistics module | THIN |

**Pool gaps** (not filled with generic advice): recommender-system evaluation, representation learning (FashionCLIP / triplet models), resampling statistics beyond the basics, and Polyvore specifics. Ingest a recommender-systems text and a resampling-statistics text through `pool-ingestion-pipeline` to close them.

## Disclosure

Code for these pipelines was written with AI assistance (Claude Code, Anthropic) under the author's direction. The author designed the study, reviewed the code and is responsible for the results. Disclose this in the thesis as the course's GenAI policy requires. Every report carries the same note.
