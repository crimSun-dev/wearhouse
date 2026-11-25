# Source-product fixtures

**Status: PASSED locally (2026-11-25).** The permitted fixture is generated into the **git-ignored** `local/`
folder by `tools/make_hm_fixture.py` from the owner's permitted `articles.csv` (Kaggle rules: no
redistribution, so it is never committed). `tests/test_foundation_thread.py` prefers `local/manifest.json`. On a
machine without it, the committed `manifest.json` (still `pending`) makes the source-backed test skip. Tests that use the
synthetic fixture under `apps/api/tests/fixtures/` are labelled `synthetic_only`
and never count toward that gate.

## To complete this gate

1. Accept the competition rules with the account that will hold the data, and keep a
   record of the acceptance.
2. Copy the original `articles.csv` rows you are allowed to use. Keep them byte-for-byte,
   and keep `article_id` as a string with its leading zeros (for example `0108775015`).
3. Write one ingestion request (the `POST /api/v2/admin/source-products` body) per permitted row, for
   example `hm-0108775015.request.json`. Copy `original_fields` verbatim from the row; every fact must name
   its `source_field`. Then fill in `manifest.json` (see the shape below), including `request_file`, and
   set `"status": "permitted"`.
4. Run `pytest apps/api/tests/test_foundation_thread.py -rs`. When `test_thread_source_backed` passes
   instead of being skipped, the source-backed readiness gate is met (task 7.5). Record the result in
   `docs/architecture/foundation-readiness.md`.

```jsonc
{
  "status": "permitted",
  "permission": {
    "basis": "kaggle-competition-rules-accepted",   // the basis for using the data
    "accepted_by": "<account/role>",
    "accepted_on": "YYYY-MM-DD",
    "scope": "private academic test fixture; not redistributed publicly",
    "terms_url": "https://www.kaggle.com/competitions/h-and-m-personalized-fashion-recommendations/rules"
  },
  "snapshot": { "file": "hm-articles-subset.csv", "sha256": "<hex>", "acquired_on": "YYYY-MM-DD",
                "original_file": "articles.csv" },
  "records": [ { "external_id": "0108775015", "row_sha256": "<hex of original CSV line>" } ],
  "request_file": "hm-0108775015.request.json"
}
```

Rules (design D5):

- An H&M article ID is never a GTIN.
- Do not fabricate fields, rows or images.
- Unknown characteristics stay unknown.
- Images are added only as media references you have permission to use.
