# Sizes readiness (add-wearhouse-sizes)

Date: 2026-11-25. Local PostgreSQL 18 (port 55432), dev catalogue `wh_smoke` with the full H&M article file (105,543 published products).

## What exists

| Area | Behaviour |
|---|---|
| Size registry | `size_system` / `size_value` are data, seeded by migration 0011. Staff with `catalogue:ingest` can add, rename, re-rank and retire them (`PUT /admin/catalogue/size-systems/{code}[/sizes/{size_code}]`). Retired sizes are hidden from pickers and assignment but stay readable on old records. Nothing is deleted. |
| Seeded commercial sizes | Letter (international) XXS–3XL: common XS–XXL, default for top, outer, bottom and dress. EU clothing 32–52 (even): common 34–46, no default slot. EU shoe 35–47: common 36–45, default for footwear. |
| Product sizes | One system per product. Staff set them (`origin: staff`), or `assign-missing` / `wearhouse assign-sizes` generates them by slot rule (`origin: rule`). Accessories and unknown slots stay one size. **The H&M file has no sizes, so every rule size is mock data**, and the store says so ("generated sizes: the source has none"). |
| Usual sizes | `GET`/`PUT /me/sizes`: one per system. They are in the account export (`sizes.usual_sizes`) and erased on account deletion. |
| Store | Cards list sizes. Browse takes `size=system:code` and `my_sizes=true` (signed in; `409 NO_USUAL_SIZES` without usual sizes; cursors bound to the filter). The product page has a size picker that preselects your usual size and disables sold-out sizes. |
| Commerce | Per-size stock (`sandbox_offer_size`); for sized products `stock` means per size unless `size_stock` is given. The offer total is the sum. Each cart line has a size. Checkout locks offers, then size rows, and refuses a short size with `OUT_OF_STOCK (size M)`, changing nothing. Order lines, receipts, staff orders and units record the size; cancelling restocks it. |
| Ownership | `garment_unit` snapshots the size, and the claimed item's presentation carries it. Staff issuance takes an optional `size`. |
| Wardrobe | Every item has `size` and `size_source` (`purchase`, `owner` or null). The owner can correct any item, and `null` restores the purchased size. `size=system:code` filters; `sort=size` orders by system, then rank, with unsized items last (also `name` and `worn`). |
| Recommendations | "For you" leaves out sized products that miss your usual size in their system (`sized_to_you: true`). One-size products and systems without a usual size always pass. |

## Evidence

| Check | Result |
|---|---|
| `tests/test_sizes.py` | 13 passed:<br>• registry: seeded order, staff-only edits, audit, slot conflict, retire<br>• bad registry input<br>• rule assignment by slot (bounded, idempotent, one-system rule, staff edits)<br>• usual sizes and shop-by-size (`my_sizes`, `size`, cursor binding, 401/409)<br>• CLI<br>• per-size stock (single and bulk)<br>• sized cart, checkout, claim and cancel (short size changes nothing)<br>• staff issuance with size<br>• wardrobe sort, filter and correction<br>• export and erasure<br>• size-aware recommendations |
| Changed expectations | `test_commerce` (public offer gains `sizes: []`) and `test_staff_workspace` (bulk result gains `sized: 0`): additive fields only. One-size products behave exactly as before. |
| Migrations | 0011 and 0012 match the table metadata. The startup no-writes check excludes the two seeded reference tables. |
| e2e `sizes.spec.ts` | Staff set S M L, offer stock 2 per size (`stock 6 (S:2 M:2 L:2)`). Shopper sets My sizes M, finds the product "In my size", the picker preselects M, the receipt shows "(size M)" and the wardrobe sorts S before M with "size M (bought)". |
| Dev catalogue | `wearhouse assign-sizes` sized 81,128 of 105,543 published products in 103 s; the remaining 24,415 are accessories or unknown slots (one size). |

### Browse at full scale (warm, 24 per page, dev API)

| Query | Before 0012 | After 0012 |
|---|---|---|
| no filter | 13 ms | 12 ms |
| `size=alpha:M` (75,845 matches) | 250–270 ms | 12 ms |
| `size=eu_shoe:42` | 36 ms | 14 ms |
| `q=denim&size=alpha:S` | 250–280 ms | 14 ms |
| `category=Trousers&size=alpha:XL&sort=name` | 230–245 ms | 37 ms |
| `size=alpha:3XL` (no product has it) | 8 ms | 100–130 ms |

Why 0012: with an EXISTS over `product_size`, Postgres read every matching size row and sorted them. The denormalised `product.browse_sizes` array (GIN, kept in step by the size repository) lets it walk the newest-first index for common sizes. The remaining slow case is a size no product has: the planner has no element statistics for it and scans. That case returns an empty page in about 0.1 s.

## Deliberate limits

- After changing a product's sizes, re-save its offer (single or bulk with overwrite); until then the new sizes show as sold out. The staff pages say this.
- Size codes are unique within a system only (`38` exists in both EU systems), so references are always `system:code`.
- No size conversion between systems: a product uses one system, and usual sizes are per system.
