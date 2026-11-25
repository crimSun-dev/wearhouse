## Why

The Store can now show published products, but nobody can acquire them. A Steam-like product needs a wishlist, a cart, a checkout, an order history and a library item that comes out of the purchase. The thesis demo must not take real payments or claim real prices or stock. This change adds a clearly labelled sandbox: staff set mock offers, checkout approves without money, and every purchase issues real garment units whose private activation keys are delivered only to the buyer. This is roadmap services step 2 (`add-wearhouse-sandbox-commerce`).

## What Changes

- **Sandbox offers.** Staff set, change or withdraw a mock price (IDR, integer rupiah) and a sandbox stock count per product. Every public and buyer-facing price is labelled `sandbox`. Nothing is charged, and no real price or stock is implied.
- **Wishlist.** A signed-in customer can add, list and remove published products (at most 500).
- **Cart.** A signed-in customer can set a quantity from 1 to 5 per product (at most 20 lines), list the cart with current sandbox prices and totals, and remove lines.
- **Checkout.** Checkout is idempotent and needs an `Idempotency-Key` plus the total the buyer saw. In one transaction it:
  - checks that each product is published and has an offer;
  - reserves stock atomically;
  - records the order with immutable price snapshots;
  - issues one garment unit per item, each with a buyer-bound activation credential;
  - delivers each key to the buyer in an encrypted delivery that only the buyer can open;
  - clears the cart.

  A changed price or total, missing stock, or an unpublished product refuses the whole checkout. Nothing is charged.
- **Orders and receipts.** The buyer can list their orders and read a receipt. The receipt shows each unit's serial and key delivery state, and keys are revealed only to the buyer. The buyer can get a fresh key for an unclaimed unit whose delivery expired; the old key is revoked.
- **Cancellation.** The buyer can cancel an order while none of its units has been claimed. This revokes keys, retires the units and restocks the offers. Claim-versus-cancel races resolve to exactly one winner.
- **Account integration.** The account export includes the wishlist, cart and orders. Account deletion clears the wishlist and cart, while orders stay as tombstoned records.
- **Temporary pages.** The temporary web app gains: a price and Wishlist/Add-to-cart on the product page; Wishlist, Cart and Orders/Receipt pages; and a staff offers page. No visual polish.

## Capabilities

### New Capabilities
- `sandbox-offers`: staff-managed mock prices and stock with a sandbox label; public offer reads.
- `shopping-lists`: wishlist and cart.
- `sandbox-orders`: checkout, orders, receipts with buyer-scoped key delivery, key renewal and cancellation.

### Modified Capabilities
None archived. This builds on the catalogue publication state, ownership issuance and credentials (buyer-bound audience and encrypted delivery), and the accounts export and deletion.

## Impact

- **API.**
  - New `commerce` module.
  - Ownership exposes fulfilment and cancellation operations to other modules through its application layer.
  - Migration `0006_sandbox_commerce`.
  - New `commerce:offers` capability for `catalogue_editor` and `admin`.
  - New routes under `/api/v2/me/*`, `/api/v2/commerce/*` and `/api/v2/admin/commerce/*`; contracts regenerated.
- **Pages.** `apps/web/account-pages` gains the commerce pages.
- **Unchanged.** Legacy v1, public discovery and the redemption semantics. A buyer still redeems their key to own the item, exactly as with any other key.
