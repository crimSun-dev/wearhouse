# Research workspace (reserved)

This directory is kept separate from application code, so that research data and evaluation never leak into the product. Nothing here is imported by `apps/` or `legacy/`.

- **Datasets.** Research datasets (H&M Personalized Fashion Recommendations, Polyvore Outfits) and model weights (for example FashionCLIP) are **not** committed. Record each dataset's acquisition, terms acceptance and checksums in a manifest next to the evaluation that uses it. Redistribution and image rights are not assumed.
- **Product fixtures.** The product app reads source fixtures only through `apps/api/fixtures/source-products/`, which needs a permission record.
- **Results.** Evaluation protocols (RQ1–RQ4) and their frozen settings arrive with the research-intelligence change in the roadmap. Report measured outcomes honestly; never tune on test data.
