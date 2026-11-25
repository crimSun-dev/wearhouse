# Object management readiness (add-wearhouse-object-management)

Recorded on 2026-11-25. The tests ran on the disposable PostgreSQL 18 cluster; the scale measurements were taken on the local dev database `wh_smoke`, which holds the real H&M catalogue.

**Images are generated placeholders by the user's direction (mockup).** Each one is a replaceable `product_media` object labelled `kind: generated` with rights `basis: generated`, and it carries a visible "GENERATED PLACEHOLDER" label. None is presented as a product photo.

## Gates

| Gate | Command / place | Observed |
|---|---|---|
| Migration 0009 (`product_media`, `pg_trgm`, published-only indexes), `compare_metadata`, privileges | `pytest tests/test_migrations.py` | passed. On `wh_smoke` (105,543 products) the migration took 2.7 s, trigram index included |
| Placeholder generator: deterministic, XML-escaped (`<script>` inert), unknown colour shown neutral and labelled, every slot, long names wrapped | `pytest tests/test_placeholder.py` | 13 passed |
| Media objects: generate, upload (sniffed PNG/JPEG/WebP; SVG upload → 422; 5 MB; rights basis required), reorder, alt text, soft remove → 404; draft media hidden from public but visible to staff; customer 403; 20-object limit; idempotent bulk; public media cacheable | `pytest tests/test_product_media.py` | 7 passed |
| Facet cache: served within TTL, invalidated by publish, refreshed after TTL | `test_facet_cache_invalidated_by_publish` | passed |
| Roles in the app: grant takes effect on the next request; revoke gives 403; `LAST_ADMIN`; `SELF_REVOKE`; non-admin 403; unknown handle 404; audit `via=admin_api` | `pytest tests/test_staff_workspace.py` | 5 passed (with the workspace tests below) |
| Staff unit list (no keys, no owners), staff orders (buyer handle, null after deletion, editors 403), bulk sandbox offers (counts, overwrite, audit) | same file | passed |
| Full v2 suite, routes, boundaries (`placeholder` checked as pure), contracts | `pytest -q`; `python tools/contracts.py check` | **571 passed, 0 skipped**; "contracts up to date" |
| Pages: typecheck, unit, build guard; e2e: admin grants editor in the app → editor generates, uploads and removes media → the store shows the uploaded image; all earlier flows | `npm run typecheck`, `npm test`, `npm run build`, `npx playwright test` | clean; 7 passed; "build guard OK"; **11 passed** |

## Real-scale measurements (dev database, 105,543 published products, 20 requests each)

| Query | Median | p95 |
|---|---|---|
| search "dress" | 4.0 ms | 4.7 ms |
| search with no match | 2.4 ms | 2.8 ms |
| colour Black, sorted by name | 18.1 ms | 24.9 ms |
| category Trousers | 4.8 ms | 5.8 ms |
| newest page | 4.6 ms | 5.6 ms |
| facets (cached) | 1.5 ms | 1.9 ms |

**Placeholder generation for the dev catalogue:** `wearhouse generate-media` created 105,543 objects (96 MB) in 57 s. Afterwards 0 published products have no media.

## Fixed along the way

- **Private-route matching.** It used a plain string prefix, so `/api/v2/me` also matched `/api/v2/media` and forced `no-store` on public images. It now matches whole path segments (`is_private_path`), with regression tests.
- **Last-admin lock.** `SELECT … FOR UPDATE` on `role_grant` needs an UPDATE privilege the least-privilege runtime role deliberately lacks. The lock is now a transaction-scoped advisory lock.
- **Pages.** A stale page stayed interactive while the next route loaded, so input typed into it was silently lost. A route now starts with a "Loading…" state.
