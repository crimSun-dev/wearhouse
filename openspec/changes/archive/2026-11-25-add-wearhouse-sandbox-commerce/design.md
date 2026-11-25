## Context

The catalogue publication change gives a `publication_state` per product. Ownership already provides:
- issuance with a buyer-bound credential (`audience_user_id`);
- an encrypted delivery bound to an actor (`issuance_delivery`, AES-GCM, 24 h);
- redemption that enforces the audience;
- unit states `issued`, `claimed` and `retired`.

The platform already has the idempotency executor, the outbox, audit and signed cursors.

## Goals / Non-Goals

**Goals:** a believable sandbox shop whose purchases go through the real ownership machinery; all-or-nothing checkout under concurrency; buyer-only key visibility.

**Non-Goals:** real payments, taxes, shipping, refunds of money, coupons, multiple currencies, or stock reservations held while browsing.

## Decisions

### D1: New `commerce` module; ownership exposes fulfilment through its application layer

`ownership.application` gains:
- `fulfil_units(uow, product_id, revision_id, quantity, buyer_id)`, which reuses the credential minter with `actor_id = audience_user_id = buyer`, so the delivery opens only for the buyer;
- `retire_units(uow, unit_ids, actor_id)`;
- `renew_unit_key(uow, unit_id, buyer_id)`;
- `open_delivery(uow, delivery_id, buyer_id)`.

Commerce calls these inside its own unit of work, because every repository shares the transaction. This keeps the credential rules in one place, and the boundary test allows imports of `application`.

### D2: Tables (migration `0006_sandbox_commerce`)

| Table | Columns and constraints |
|---|---|
| `sandbox_offer` | `product_id` (PK, FK `product`), `price_idr` (bigint, 1 to 100,000,000), `currency` (`IDR`), `stock` (int, 0 to 100,000), `updated_by`, `updated_at` |
| `wishlist_item` | (`user_id`, `product_id`) PK, `created_at` |
| `cart_line` | (`user_id`, `product_id`) PK, `quantity` (1 to 5), `updated_at` |
| `sandbox_order` | `id`, `user_id`, `status` (`fulfilled` or `cancelled`), `currency`, `total_idr`, `payment_ref`, `created_at`, `cancelled_at` |
| `sandbox_order_line` | (`order_id`, `line_no`) PK, `product_id`, `revision_id`, `product_name`, `unit_price_idr`, `quantity` |
| `sandbox_order_unit` | `unit_id` (PK, FK `garment_unit`), `order_id`, `line_no`, `delivery_id` (current delivery) |

### D3: Checkout transaction and races

Checkout runs under `IdempotentExecutor` (actor + route + key, body fingerprint `{expected_total_idr}` plus the cart snapshot). Inside it:

1. Lock the cart lines.
2. Lock the offers `FOR UPDATE`, ordered by `product_id`, so that two checkouts touching the same products cannot deadlock.
3. Verify the publication state, the offer and the stock, and compare the total.
4. Decrement the stock.
5. Insert the order, its lines and its units, delivering keys through `fulfil_units`.
6. Delete the cart, then write the audit and outbox records.

Last-item races serialise on the offer row lock. The loser sees too little stock and gets `OUT_OF_STOCK`.

### D4: Cancellation versus claim

Redemption locks credential then unit. Cancellation does the same: it locks the active credentials of the order's units (ordered by id), then the units, then the order. The lock order matches, so the two cannot deadlock.

- If a unit is already claimed, cancellation returns `ORDER_CLAIMED`.
- If cancellation commits first, the credential is revoked, and the redemption sees a non-active credential and returns the generic invalid-key response.

### D5: Receipts open deliveries on read

The receipt calls `open_delivery` for each unclaimed unit, which only the buyer can open, and audits each reveal (`ownership.delivery_accessed`). Claimed units show `claimed` and never a key. Key renewal revokes the old credential, erases its deliveries, mints a new one and updates `sandbox_order_unit.delivery_id`.

### D6: Capabilities

- `commerce:offers` belongs to `catalogue_editor` and `admin`.
- Shopping, ordering and cancelling need only a verified principal; customers can already redeem and read their own items.
- Offer reads are public.

### D7: Accounts integration through a port

`commerce.ports.CommerceAccountData` gives `export(user_id)` and `erase_lists(user_id)`. The accounts export and deletion call it through the shared unit of work. Accounts may import `commerce.ports`, but not the commerce adapters.

## Risks / Trade-offs

- **[Keys shown on every receipt read while unexpired.]** These are buyer-only, audited and expire after 24 h, with renewal available after that. A shared screen is still a risk, so the page reveals a key only on a "Show key" click.
- **[A synchronous issuance of up to 100 units, 20 lines of 5.]** Each unit is a few inserts, which is bounded and acceptable.
- **[Sandbox prices could be mistaken for real ones.]** Every price field carries `sandbox: true`, and the pages show "Sandbox price (no real payment)".

## Migration Plan

Run `0006` (additive), then deploy. Roll back by restoring the backup before data exists; after that, roll forward only.
