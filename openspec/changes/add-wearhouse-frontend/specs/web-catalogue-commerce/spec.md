## Purpose

Defines the web store experience: catalogue discovery, public tag lookup, wishlist, cart, simulated checkout, orders and receipts, and private redemption. It is built on the existing catalogue-browse, sandbox-offers, sandbox-orders, sized-commerce and private-redemption capabilities.

## ADDED Requirements

### Requirement: Catalogue discovery
The catalogue SHALL present:
- featured collections (`GET /catalogue/collections`);
- category entry points built from real facet values and counts (`GET /catalogue/facets`);
- newest products.

Browse SHALL support `q`, `category`, `colour`, `slot`, `size` and `sort`, and, when signed in, `my_sizes` and `hide_owned`. It SHALL use cursor pages with infinite loading and an explicit "Load more" control. Filters SHALL be reflected in the route so a view can be shared and restored. An empty result SHALL offer to clear the filters. Categories, a sale section and trending lists that the API does not provide SHALL NOT be shown.

#### Scenario: Filter restore
- **WHEN** a user filters by category and colour, opens a product and returns
- **THEN** the same filters and results are shown

### Requirement: Product detail
The product view SHALL show:
- the media gallery, with a silhouette fallback;
- the source facts, with their source fields;
- annotations, labelled by origin;
- the source identity;
- the sizes (or one size);
- the simulated offer and its availability;
- similar products, with the model mode and any fallback.

Signed-in users SHALL be able to add the product to the wishlist and add it to the cart with a size. A product the user already owns SHALL be marked as in their wardrobe.

#### Scenario: Out of stock
- **WHEN** the offer reports `in_stock: false`
- **THEN** add-to-cart is unavailable with a reason, and wishlisting remains available

### Requirement: Public tag lookup is discovery only
`#/items/:serial` SHALL show the product from `GET /items/{serial}` with an add-to-wishlist action. It SHALL state that ownership requires the private key. The page SHALL offer a camera QR scanner where supported, and a paste-a-link fallback. Nothing on the tag page SHALL create ownership.

#### Scenario: Scanning does not claim
- **WHEN** a signed-in user scans a tag and opens the result
- **THEN** no redemption request is sent and the wardrobe is unchanged

### Requirement: Wishlist and cart
The wishlist SHALL list saved products with availability and offer, and support removal (limit 500, `WISHLIST_FULL`). The cart SHALL show:
- lines with size and quantity 1–5;
- unavailable lines flagged;
- the current simulated total and checkout readiness.

The cart SHALL support updating and removing lines (limit 20 lines, `CART_FULL`).

#### Scenario: Unavailable line
- **WHEN** a cart line's product is retired
- **THEN** the line shows as unavailable and checkout readiness reflects the server's `checkout_ready`

### Requirement: Simulated checkout
The review step SHALL state plainly that the purchase is simulated and that nothing is charged, shipped or delivered. Placing the order SHALL send the displayed total as `expected_total_idr` with an idempotency key. On `PRICE_CHANGED`, `OUT_OF_STOCK`, `NOT_AVAILABLE` or `CART_EMPTY` the app SHALL refresh the cart, explain what changed, and create no order.

#### Scenario: Price changed
- **WHEN** an offer price changes between review and submit
- **THEN** the app shows the new total and asks the user to confirm again

### Requirement: Orders, receipts and keys
Orders SHALL be listed newest first with cursor paging. A receipt SHALL show:
- the lines;
- the payment reference with a simulated label;
- each unit's delivery state.

Revealing a key SHALL require an explicit action per unit. Renewing a key SHALL warn that the old key stops working. Cancellation SHALL be offered only while `cancellable` is true, and SHALL explain that keys are revoked and stock is restored.

#### Scenario: Claimed unit
- **WHEN** a unit's delivery status is `claimed`
- **THEN** no reveal action is shown and the unit links to the owned item

### Requirement: Redemption
The redeem screen SHALL accept a key in any case, with or without dashes or spaces, display it in `XXXX-XXXX-XXXX-XXXX` groups, and submit it with an idempotency key. Every invalid key SHALL produce the same generic message, with no hint about which part is wrong. A rate limit SHALL show a countdown. Success SHALL show the new owned item with a link to inspect it.

#### Scenario: Second redemption rejected
- **WHEN** user B submits a key already redeemed by user A
- **THEN** B sees the same generic invalid message as for a mistyped key
