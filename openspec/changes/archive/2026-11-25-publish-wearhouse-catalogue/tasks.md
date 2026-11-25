## 1. Data model

- [x] 1.1 Write migration `0005_catalogue_publication`: product publication and browse columns, with a backfill from `active`; import job/row tables; collection tables; indexes; runtime grants and `RUNTIME_PRIVILEGES`. Verify 0004→0005 upgrade, repeat-upgrade, `compare_metadata` empty, startup privilege check, and backfilled products staying issuable.

## 2. Import

- [x] 2.1 Implement mapping `hm-articles@1` (facts, `original_fields`, rule slot) as pure domain code. Verify with unit tests: leading zeros, optional columns, empty description, every slot rule row, an unknown group giving no slot, and missing required columns.
- [x] 2.2 Implement import jobs (CSV parsing with row/size bounds, one transaction per row, outcomes, totals) and the staff routes to run and read them. Verify: mixed valid/invalid rows, re-run unchanged, changed facts revised, oversized/malformed CSV rejected before processing, and a customer getting 403.

## 3. Publication

- [x] 3.1 Implement publish (a specific revision) and retire, with the review queue and the staff product detail, all audited. Verify: drafts invisible; publishing a newer revision; the review queue after an import revision; retiring keeping owned items and discovery lookups; a customer getting 403.
- [x] 3.2 Implement collections (create/rename/reorder via `PUT`, delete) and public collection reads. Verify editor order, retired products hidden publicly but shown to editors, and an unknown slug giving 404.

## 4. Browse

- [x] 4.1 Implement public search, filters, sorting, stable cursors, facets and detail (published revision, labelled annotations, public media only), and make discovery use the published revision. Verify: filtered search, literal wildcards, stability while a product is published mid-paging, facet counts excluding drafts, restricted media hidden, and 404 for drafts/retired.

## 5. Contracts, pages, readiness

- [x] 5.1 Regenerate contracts and update the route set and boundary tests. Verify the contract drift check and the full v2 suite.
- [x] 5.2 Add Store pages (browse/search/filters, product, collections) and staff pages (import CSV, review/publish/retire, collections) to the temporary web app. Verify typecheck, unit tests, the build guard, and an e2e flow: import → publish → find in the store → retire → gone.
- [x] 5.3 Record evidence in `docs/architecture/catalogue-readiness.md` and update the API README. Verify that every gate has a command and an observed result.
