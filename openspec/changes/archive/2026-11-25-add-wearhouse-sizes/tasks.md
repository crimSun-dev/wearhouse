## 1. Registry and product sizes

- [x] 1.1 Write migration `0011_sizes` with seeded systems and sizes, the catalogue size repository and `SizingService` (registry, staff edits, product sizes, assign-missing, usual sizes), routes, the `assign-sizes` CLI, and browse/detail sizes and filters. Verify: registry order, staff-only edits audited, one-system rule, rule assignment by slot, size and `my_sizes` filters with bound cursors, `NO_USUAL_SIZES`.

## 2. Sized commerce and ownership

- [x] 2.1 Add per-size offers (single and bulk), sized cart lines, checkout and cancellation by size, sizes on order lines and units, size in the claimed presentation, and an optional size on staff issuance. Verify: stock per size, size required/refused, last item in a size, restock on cancel, receipt and staff views, claimed item keeps size, one-size products unchanged.

## 3. Wardrobe, preferences and recommendations

- [x] 3.1 Add wardrobe size corrections, the size filter and `sort=size`, usual sizes in export and erasure, and size-aware personal recommendations. Verify: sort order, filters, correction, export/erasure, recommendation filtering.

## 4. Pages, contracts and readiness

- [x] 4.1 Regenerate contracts; add "My sizes", the store size filter and "In my size", the product size picker, receipt sizes, wardrobe size sort/edit and the staff sizes panel; e2e; full suite; size the dev catalogue; write `docs/architecture/sizes-readiness.md`.
