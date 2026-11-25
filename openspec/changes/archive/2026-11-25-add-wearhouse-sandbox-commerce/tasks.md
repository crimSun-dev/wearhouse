## 1. Data model and capability

- [x] 1.1 Write migration `0006_sandbox_commerce` (offers, wishlist, cart, orders, lines, units; CHECK constraints; grants), add the `commerce:offers` capability, and update `RUNTIME_PRIVILEGES`. Verify upgrade/repeat, empty `compare_metadata`, and the startup privilege check.

## 2. Ownership fulfilment operations

- [x] 2.1 Add `fulfil_units`, `retire_units`, `renew_unit_key` and `open_delivery` to the ownership application layer, reusing the credential minter, plus credential locking in a consistent order. Verify with the existing ownership suite still passing and unit tests of buyer-bound delivery.

## 3. Offers, wishlist, cart

- [x] 3.1 Implement staff offers (`PUT`/`GET`/`DELETE`, audited) and the public offer read. Verify customer 403, unknown product 404, and retired/unoffered 404 publicly with no stock count exposed.
- [x] 3.2 Implement the wishlist and the cart with their limits and validation. Verify: draft 404, wishlist full 409, quantity 6 gives 422, not for sale 409, totals, availability after retire, and owner-only access.

## 4. Orders

- [x] 4.1 Implement idempotent checkout (offer locks, stock, snapshots, buyer-bound units, keys, cart cleared). Verify: success totals and counts, `PRICE_CHANGED`, `OUT_OF_STOCK` with nothing changed, the concurrent last-item race (threads), replay returning the same order, and a different body rejected.
- [x] 4.2 Implement orders list/receipt, key reveal audit, key renewal and cancellation. Verify: foreign order 404, buyer claims from the receipt, another user cannot redeem, renewal revokes the old key, cancel then redeem fails with stock restored, a claimed order cannot be cancelled, and the cancel-versus-claim race has one winner.
- [x] 4.3 Integrate with the accounts export and deletion. Verify the export holds orders without keys, and deletion clears the wishlist and cart but keeps orders.

## 5. Contracts, pages, readiness

- [x] 5.1 Regenerate contracts and update the route set and boundaries (the new module). Verify the full v2 suite and the drift check.
- [x] 5.2 Add the price, Wishlist and Add-to-cart controls to the product page, plus Wishlist, Cart, Orders/Receipt (show key, claim into wardrobe, renew, cancel) and staff Offers pages. Verify typecheck, unit tests, the build guard, and an e2e flow: offer → add to cart → checkout → receipt → claim → item in wardrobe.
- [x] 5.3 Record evidence in `docs/architecture/commerce-readiness.md` and update the API README.
