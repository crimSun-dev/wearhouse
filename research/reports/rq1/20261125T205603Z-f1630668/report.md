# RQ1 — Catalogue recommendation (methodology 3.5.1)

**Answer: NOT POSITIVE** (MAP target met: False, duplicate target met: True)

Content embedding: **text_attributes** — No permitted product images exist (catalogue images are generated placeholders), so the FashionCLIP image term of Eq. 2 and the image-similarity Dup of Eq. 3 are replaced by a TF-IDF text/attribute embedding. Comp (Eq. 3) needs the RQ2 compatibility model; lambda_c = 0 until an RQ2 artifact exists.

| Method | MAP@12 [95% CI] | Recall@12 | NDCG@12 | Duplicate share |
|---|---|---|---|---|
| popularity | 0.0106 [0.0096, 0.0117] | 0.0329 | 0.0192 | 0.016 |
| item_knn | 0.0056 [0.0048, 0.0064] | 0.0159 | 0.0093 | 0.213 |
| bpr | 0.0089 [0.0079, 0.0101] | 0.0244 | 0.0147 | 0.084 |
| first_stage | 0.0103 [0.0091, 0.0115] | 0.0233 | 0.0153 | 0.391 |
| reranked | 0.0080 [0.0069, 0.0091] | 0.0182 | 0.0120 | 0.174 |

Best simpler baseline: popularity. MAP change: {'relative': -0.24715280552854316, 'absolute': -0.002631610650016488}. Duplicate change vs first stage: {'relative': -0.5553137468262604, 'absolute': -0.2169217019792484}.

Selection (validation week only): alpha = 0.5, lambda_d = 0.05 (max validation MAP among settings reducing duplicates by >= 30% vs first stage; if none, max MAP (met: True)).

Cohort: {'buyers_in_week': 68984, 'missing_age_excluded': 292, 'genz_evaluated': 15292, 'max_age': 23}

## Disclosure
Code for this pipeline was written with AI assistance (Claude Code, Anthropic) under the author's direction; the author designed the study, reviewed the code and is responsible for the results. Disclose this in the thesis as required by the course's GenAI policy.
