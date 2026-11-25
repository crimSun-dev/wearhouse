# sandbox-orders Specification

## Purpose
Turns a cart into a sandbox order that issues real garment units to the buyer, with keys only the buyer can see, and lets the buyer review, renew keys for, or cancel the order.

## Requirements

### Requirement: Idempotent all-or-nothing checkout
`POST /me/checkout` SHALL require an `Idempotency-Key` and the total the buyer saw. In one transaction it SHALL:
- verify every line is a published product with an offer and enough stock;
- decrement the stock;
- record an order with an immutable unit-price snapshot per line and the total;
- issue one unit per item, each bound to the buyer's account;
- deliver each activation key to the buyer, encrypted;
- empty the cart.

The order SHALL be marked `fulfilled`, with a sandbox payment reference, and no money SHALL be charged. If any check fails, nothing SHALL change. Repeating the same key and body SHALL return the same order, and a different body with the same key SHALL be rejected.

#### Scenario: Successful checkout
- **GIVEN** a cart with 2 of product A (sandbox price 150,000) and 1 of product B (price 90,000)
- **WHEN** the buyer checks out with expected total 390,000
- **THEN** one order with total 390,000 is created; 3 buyer-bound units are issued; stock drops by 2 and 1; and the cart is empty

#### Scenario: Price changed since the buyer looked
- **WHEN** the expected total differs from the current total
- **THEN** the service returns 409 `PRICE_CHANGED`, and no order, unit or stock change exists

#### Scenario: Not enough stock
- **GIVEN** product A with stock 1 and a cart line of 2
- **WHEN** the buyer checks out
- **THEN** the service returns 409 `OUT_OF_STOCK`, and nothing changes

#### Scenario: Concurrent checkouts for the last item
- **GIVEN** stock 1, and two buyers each with 1 in their cart
- **WHEN** both check out at the same time
- **THEN** exactly one order succeeds, and the other gets `OUT_OF_STOCK`

#### Scenario: Retry with the same key
- **WHEN** the buyer retries the same checkout with the same `Idempotency-Key`
- **THEN** the same order is returned, and no second order or unit exists

### Requirement: Buyer-scoped receipts
`GET /me/orders` SHALL list only the buyer's orders, newest first, with cursor pagination. `GET /me/orders/{id}` SHALL show:
- lines with their snapshot prices;
- the total and the `sandbox` label;
- each unit's public serial and claim state;
- each key delivery state: `available` while it is unexpired, otherwise `expired`, `unavailable` or `claimed`.

The key itself SHALL appear only in `GET /me/orders/{id}/units/{unit_id}/key`, and every reveal SHALL be audited. Receipts, order lists and the checkout response SHALL NOT contain keys. Another user's order SHALL return the same 404 as a missing order.

#### Scenario: Another user's receipt
- **WHEN** user B requests user A's order
- **THEN** the service returns 404, and no key is revealed

#### Scenario: Buyer claims a purchased unit
- **WHEN** the buyer redeems a key from their receipt
- **THEN** the unit appears in the buyer's items, and the receipt shows it as claimed with no key

#### Scenario: Another user tries a buyer-bound key
- **WHEN** another user redeems a key from the buyer's order
- **THEN** redemption fails with the generic invalid-key response

### Requirement: Key renewal for unclaimed units
The buyer SHALL be able to request a new key for an unclaimed unit of their own order. This SHALL require an `Idempotency-Key`, revoke the previous key, and deliver the new key to the buyer.

#### Scenario: Old key stops working
- **WHEN** the buyer renews a unit's key and then redeems the old key
- **THEN** redemption fails, and the new key works

### Requirement: Cancellation while unclaimed
The buyer SHALL be able to cancel a fulfilled order while none of its units is claimed. Cancelling SHALL:
- revoke every key and erase deliveries;
- retire the units;
- restore the stock;
- mark the order `cancelled`;
- be audited.

An order with any claimed unit SHALL be refused with 409 `ORDER_CLAIMED`. A claim and a cancellation racing on the same order SHALL resolve to exactly one winner.

#### Scenario: Cancel then try to redeem
- **WHEN** the buyer cancels and then redeems a key from that order
- **THEN** redemption fails, and the stock is back

### Requirement: Account integration
The account export SHALL include the user's wishlist, cart and orders, without keys. Account deletion SHALL remove the wishlist and cart, and SHALL keep orders as records of a deleted account.

#### Scenario: Export lists orders without secrets
- **WHEN** a buyer with one order exports their data
- **THEN** the export contains the order lines and total, and no activation key
