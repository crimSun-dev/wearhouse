# Catalogue publication readiness (publish-wearhouse-catalogue)

Recorded on 2026-11-25. The database is the disposable local PostgreSQL 18 cluster (`WEARHOUSE_TEST_ADMIN_URL=postgresql://postgres@127.0.0.1:55432/postgres`).

**Data honesty.** Every automated test uses synthetic rows in the H&M `articles.csv` column format, under the namespaces `hm-format-synthetic` and `hm-pfr-synthetic`, or the existing data-free synthetic product. These tests are marked `synthetic_only`, and none of them is H&M data. A real permitted `articles.csv` goes through the same import job: use the staff page "Import CSV", or `POST /api/v2/admin/catalogue/import-jobs` with the permission record filled in.

## Gates

| Gate | Command | Observed |
|---|---|---|
| Migration 0005: upgrade from 0004, repeat-upgrade, backfill publishes existing active products, privilege check, backfilled product stays issuable | `pytest tests/test_catalogue_migration.py tests/test_migrations.py tests/test_accounts_migration.py` | 14 passed |
| Mapping `hm-articles@1`: leading zeros, optional columns, empty description, all 15 slot rule rows, unknown group gives no slot, missing columns | `pytest tests/test_catalogue_mapping.py` | 19 passed |
| Import jobs, publication, review, retire versus ownership, discovery shows the published revision, collections, browse (filters, literal wildcards, facets excluding drafts, stable cursors, filter-bound cursors), media rights | `pytest tests/test_catalogue_publication.py` | 17 passed |
| Route allowlist, contracts, boundaries (new `publication` and `mapping` checked as framework-free) | `pytest tests/test_app_factory.py tests/test_boundaries.py`; `python tools/contracts.py check` | passed; "contracts up to date" |
| Full v2 suite | `pytest -q` in `apps/api` | 433 passed, 1 skipped (the source-backed proof that needs the permitted H&M fixture; still pending from the foundation task 7.5) |
| Temporary pages: typecheck, unit tests, production build guard | `npm run typecheck`, `npm test`, `npm run build` in `apps/web/account-pages` | clean; 7 passed; "build guard OK: 2 files in dist, no e2e fake, no legacy code" |
| Pages e2e: import → publish → found in store → retire → gone; customers cannot reach staff pages; all account flows still pass | `npx playwright test` | 7 passed |

## Known limits

- Search is literal substring matching over the name and description (`browse_text`). A full-text index can be added later without an API change.
- An import job runs inside its request: up to 5000 rows or 10 MB, with one transaction per row. A real `articles.csv` has about 105k rows, so it is imported in chunks of 5000 rows under the same snapshot checksum. Re-running a chunk is safe, because rows come back `unchanged`.
- Media are references only. Nothing is fetched; a reference is public only when `rights.public_display` is `true`.
