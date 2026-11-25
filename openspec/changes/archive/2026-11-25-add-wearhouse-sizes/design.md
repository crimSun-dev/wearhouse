## Context

The modules are layered: adapters never import another module's adapters, so each module owns its own size data.
- **Catalogue** owns the size registry, product sizes and usual sizes.
- **Commerce** owns per-size stock.
- **Ownership** records a unit's size.
- **Wardrobe** keeps a per-item size in its item state.

They share one unit of work, which gains a `sizes` repository (catalogue adapter) that other modules use through the catalogue port.

## Decisions

### D1: Sizes are data, seeded once
`size_system(code, label, position, slots text[], active)` and `size_value(system_code, code, label, rank, common, active)` are seeded by migration 0011:

| System | Sizes | Common | Default slots |
|---|---|---|---|
| `alpha` Letter (international) | XXS, XS, S, M, L, XL, XXL, 3XL | XS–XXL | top, outer, bottom, dress |
| `eu_clothing` EU clothing | 32–52 (even) | 34–46 | none (staff choose) |
| `eu_shoe` EU shoe | 35–47 | 36–45 | footwear |

Staff can add systems and sizes, rename them, re-rank them and set `active`.
- A retired size disappears from pickers and from the assignment rule.
- Existing product sizes, cart lines, orders and wardrobe items keep showing its label.
- Nothing is deleted.

### D2: A product uses one system; one-size means no rows
`product_size(product_id, system_code, size_code, origin)`. A product with no rows is one-size. Setting sizes replaces the whole set and must use a single system. `assign_missing` touches only published products that have no rows and whose slot is listed by an active system. It uses the common, active sizes of that system and records `origin = 'rule'`. Staff edits record `origin = 'staff'`. The detail view shows the origin, so mock sizes are never presented as H&M facts.

### D3: Size references
- API inputs: `{"system": "alpha", "code": "M"}`.
- Query parameters: `system:code`, e.g. `size=eu_shoe:42`.
- Outputs: `{system, code, label, rank}`.

Codes are unique within a system only, because "38" exists in both EU systems.

### D4: Stock per size, total kept in step
`sandbox_offer_size(product_id → sandbox_offer ON DELETE CASCADE, system_code, size_code, stock)`.
- **Saving the offer of a sized product:** writes one row per current product size. The stock is `size_stock[code]` if given, otherwise `stock`. `sandbox_offer.stock` becomes the sum.
- **Saving a one-size product:** behaves exactly as before.
- **Bulk offers:** follow the same rule per product.
- **Checkout:** locks offers first, then the size rows (ordered by product, then size), checks each line against its size, and decrements both the size row and the total.
- **Cancel:** restocks both.

If a product's sizes change after its offer was saved, the missing sizes count as out of stock until staff save the offer again. This is documented in the staff view.

### D5: Cart key includes the size
`cart_line` gains `size_system` and `size_code`, both `NOT NULL DEFAULT ''`, and its primary key becomes `(user_id, product_id, size_code)`. The empty string means one-size and is never exposed: the API shows `null`. Rules:
- a sized product needs a size that is one of its sizes;
- a one-size product rejects a size;
- each size is its own line, and the 20-line limit counts lines.

### D6: Unit and wardrobe sizes
- `garment_unit` gains `size_system`, `size_code` and `size_label` (a snapshot of the label at issue).
- Redemption copies the size into the owned item's presentation (`presentation.size`).
- `wardrobe_item_state` gains `size_system` and `size_code`, a user's correction for any item.
- An item's effective size is the correction, else the purchased size, else unknown.
- `sort=size` orders by system position, then rank; unsized items come last, ties go by name.

### D7: Usual sizes and filters
`user_size_preference(user_id, system_code, size_code)` holds at most one usual size per system.
- **Browse `my_sizes=true`:** needs a signed-in caller. It matches products that have a size equal to one of the caller's usual sizes; a caller with no usual sizes gets `409 NO_USUAL_SIZES`.
- **Personal recommendations:** drop candidates whose sizes miss every usual size of their system. One-size products always pass.

The cursor filter key includes the size filter, so a cursor cannot cross filters.

## Risks

- `product_size` reaches about 630,000 rows for the full catalogue. A `(system_code, size_code, product_id)` index serves the browse EXISTS filter.
- Products sized after their offer existed are out of stock until the offer is saved again (D4). The dev runbook says to run `assign-sizes` before bulk offers.

### D8: Denormalised browse sizes (migration 0012, found during implementation)
The first browse filter was an EXISTS over `product_size`. At 105,543 products Postgres drove the join from the size index and sorted every match: 250–270 ms for a common size such as `alpha:M`. Migration 0012 adds `product.browse_sizes text[]` (`system:code`) with a partial GIN index, backfilled from `product_size`. The size repository keeps it in step on every write, and `product_size` stays the source of truth. A common size now walks the newest-first index (about 12 ms). A size no product has costs about 0.1 s for an empty page, because there are no element statistics for it.
