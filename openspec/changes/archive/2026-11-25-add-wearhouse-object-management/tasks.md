## 1. Data model

- [x] 1.1 Write migration `0009_object_management` (`product_media`, the `pg_trgm` extension and indexes, grants) and add the capabilities `catalogue:media`, `identity:manage_roles` and `commerce:orders`. Verify upgrade/repeat, `compare_metadata` and privileges.

## 2. Product media

- [x] 2.1 Implement the placeholder generator (pure; colour table moved into the catalogue domain) and its unit tests: determinism, XML escaping, unknown colour, every slot.
- [x] 2.2 Implement media objects: list, upload (sniffed raster, 5 MB), generate, reorder, alt text, soft remove, bulk generate-missing (API and CLI), public serving with headers, and browse/detail integration. Verify: replace a placeholder, removed gives 404, draft media hidden from the public but visible to staff, SVG upload 422, customer 403, idempotent bulk, and the 20 active-object limit.

## 3. Roles and staff workspace

- [x] 3.1 Implement staff role administration (list, lookup, grant, revoke, last-admin and self-revoke protection, audit). Verify: grant gives capabilities on the next request, revoke gives 403, `LAST_ADMIN` 409, non-admin 403.
- [x] 3.2 Implement the unit list, the staff order view and bulk sandbox offers. Verify: no keys or owners in unit lists, customer 403 on orders, buyer handle null after deletion, bulk counts with and without overwrite, audit.

## 4. Scale

- [x] 4.1 Add the facet cache with invalidation, and measure search, filters and facets at 105,542 products in the dev database. Verify the median below 50 ms, and record the numbers.

## 5. Contracts, pages, readiness

- [x] 5.1 Regenerate contracts, update routes and boundaries, and run the full v2 suite and drift check.
- [x] 5.2 Add a capability-driven staff workspace (Products & media, Units, Offers incl. bulk, Orders, Roles) and product images in the Store. Verify typecheck, the build guard and an e2e flow: admin grants editor → editor uploads and removes media → the store shows the new image.
- [x] 5.3 Generate placeholders for the dev catalogue, and record evidence in `docs/architecture/object-management-readiness.md`.
