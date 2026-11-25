## Context

The thesis methodology v11 (`CRIMSUN_POOL/RESEARCH_EXTRACT.txt`, P0386–P0483) fixes the protocols. Available now:
- the permitted H&M `articles.csv` (105,542 rows), already in the dev catalogue;
- the v2 API.

Pending from the user: `transactions_train.csv`, `customers.csv` and Polyvore Outfits. Product images are generated placeholders by direction, so **no visual features exist** for H&M products.

### Understanding-pool grounding (`C:\Users\Draven Chen\.claude\skills\POOL`, indexed 2026-11-25; 709 modules)

| Entry | Tier | How it applies |
|---|---|---|
| COMP3315_AI_FOUNDATIONS TRAP-003 | DIRECT | Specify each RQ's task, measure and environment before choosing algorithms. The RQ sections are that specification. |
| COMP3315_AI_FOUNDATIONS TRAP-005 | DIRECT | Distance on categorical attributes needs a meaningful metric. The content fallback is TF-IDF plus one-hot attributes with cosine, never raw codes. |
| COMP3315_AI_FOUNDATIONS TRAP-013 | DIRECT | Evaluate with objective metrics, not inspection. Every model reports its metrics against baselines. |
| COMP3315_AI_FOUNDATIONS TRAP-016 | DIRECT | Disclose GenAI assistance in academic work. The reports carry a disclosure field, and the thesis must disclose tool use. |
| SNHU_CS_305 AXIOM-083 / AXIOM-095 | CONVERGENT | Secrets come from an OS-seeded CSPRNG, and algorithms fail when randomness fails. RQ3 checks the key source (`secrets`) and its entropy. |
| SNHU_CS_305 AXIOM-082 | INFERRED | Fast unsalted hashes are unfit for low-entropy secrets. Activation keys are 80-bit random, so a SHA-256 digest lookup is acceptable. RQ3 quantifies the offline brute-force cost. |
| SYSTEM_DESIGN RULE-033, TRAP-018 | DIRECT | Layered rate limits. RQ3 tests the per-user limit separately from validation. |
| SOPHIA_INTRO_STATISTICS RULE-002, AXIOM-017 | THIN | Random sampling and CI = estimate ± margin. Bootstrap and Wilcoxon procedures are **not** covered by the pool (POOL GAP); they follow the thesis text. |

**Pool gaps:**
- recommender systems (BPR, MAP@K/NDCG, implicit feedback);
- representation learning (FashionCLIP, triplet loss, type-aware embeddings);
- resampling statistics;
- the Polyvore benchmark.

The thesis citations are the authority for these.

## Decisions

### D1: Separate research project

`research/` is a Python 3.11 project (`wearhouse_research`) with its own `.venv` and pinned requirements: numpy, pandas, pyarrow, scipy, scikit-learn. The `fashionclip` extra adds torch and transformers. The API never imports it. Research code may import the `wearhouse` package (for RQ3) and the API test helpers.

Datasets live in git-ignored folders: `H&M DATABASE/` and `research/data/`. Manifests (`research/manifests/*.json`) hold paths, sha256 and permission, and are committed because they contain no data.

### D2: Runners and reports

`python -m wearhouse_research <rq1|rq2|rq3> --config research/configs/<rq>.json` writes `research/reports/<rq>/<UTC timestamp>-<config hash8>/report.json` and `report.md`. The provenance block records git commit and dirty flag, Python and library versions, the config hash, dataset hashes, seeds, wall time, and the disclosure field. Splits are objects with a `role` (`train`, `validation`, `test`, `tuning`, `reporting`). The selection helpers accept only `validation` or `tuning`, and anything else raises `TestDataAccess`.

### D3: RQ3 through the real API

`AdmissionPolicy` gains `actor_limit` (default 10, the production value), so a run can disable per-user, per-IP and global limits for the validation corpus only. The harness:
1. creates a disposable database with the API test factory;
2. imports [500] real H&M rows through the catalogue import service under the permission manifest, and publishes them;
3. issues units through `/admin/unit-batches`;
4. redeems them through `/redemptions` with distinct signed test identities;
5. checks `/me/wardrobe/items`.

The genuine pass runs before the false claims, which avoids rate interplay. A second app instance with production limits runs the rate test. Response bodies are compared byte-for-byte after removing `request_id`.

### D4: RQ1 implementation

- **Data:** pandas with explicit dtypes (`article_id` as a string with zeros, dates parsed), cached to parquet keyed by the source sha256.
- **BPR:** numpy minibatch SGD with uniform negative sampling, a fixed seed and L2 regularisation; factors, learning rate, epochs and regularisation come from the config.
- **Item-kNN:** co-purchase counts (scipy sparse), cosine-normalised.
- **Content:** TF-IDF over `detail_desc` and the product type/group/colour/section tokens; the customer profile is the mean of owned vectors.
- **Dup:** same `product_type_name` and content cosine ≥ τ, with τ chosen on validation (the thesis's hand-checked τ cannot be reproduced without images, so this is declared).
- **Comp:** taken from the RQ2 compatibility model mapped by a versioned H&M→Polyvore type table. Before RQ2 exists, Comp is reported as `unavailable` and λc = 0, stated in the report.

### D5: RQ2 implementation

- **Data:** the Polyvore Outfits loader reads `polyvore_outfits/{nondisjoint,disjoint}/` (outfits JSON, `compatibility_*.txt`, `fill_in_blank_*.json`) and `polyvore_item_metadata.json`.
- **Embeddings:** a provider interface. `TextEmbedding` uses TF-IDF on title and category, reduced to 128 dimensions by TruncatedSVD with a fixed seed. `FashionClipEmbedding` (optional extra) uses Polyvore images.
- **Model:** a linear projection g and a sigmoid-gated mask per type pair, trained with the triplet loss in numpy with analytic gradients. The shared-space baseline has no masks.
- **Simulation:** documented tables in `research/configs/`. The attribute lookup gives warmth, rain suitability and dress codes. The occasion schedule is as in P0391. Monthly rain and heat probabilities for Jakarta are configurable values; every default is labelled `assumed`, with the source to cite (BMKG climatology) recorded in the config. The three behaviours are as specified.
- **Statistics:** scipy Wilcoxon with `zero_method="zsplit"`, defined up front.

### D6: Serving

Migration `0010` adds two tables:
- `recommendation_artifact`: kind, name, version, mode, model hash, manifest JSON, active flag, imported by and at.
- `item_neighbour`: artifact id, product id, rank, neighbour id, score.

`wearhouse import-recommendations` verifies the manifest sha256 and activates the artifact (audited). The endpoints prefer the active artifact. Otherwise:
- similar items come from a content baseline over browse columns (same category, then colour/slot/text-trigram similarity in SQL);
- personal recommendations come from sandbox-order popularity, falling back to newest published, excluding owned products.

Both return `ModelInfo`.

## Risks / Trade-offs

- **[No images.]** Image terms are replaced by text and attributes, declared everywhere. The thesis results section must report the deviation. FashionCLIP can be slotted in later without code changes.
- **[31M transactions in pandas on a laptop.]** This needs about 3 GB of RAM with category dtypes and a parquet cache. Training BPR on the full history may be slow, so the training window (number of weeks) is a config setting.
- **[Assumed climatology.]** The values are labelled and configurable, and must be replaced with cited BMKG figures before thesis reporting.
