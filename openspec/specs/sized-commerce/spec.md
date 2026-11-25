# sized-commerce Specification

## Purpose
Buying a specific size, from offer to owned garment.

## Requirements

### Requirement: Per-size stock
For a sized product, saving an offer SHALL store stock for each of its sizes: `size_stock[code]` when given, otherwise `stock`. The offer total SHALL equal the sum. Bulk offers SHALL follow the same rule. The public offer SHALL list each size with `in_stock` and never show counts. A one-size product SHALL behave as before.

#### Scenario: Stock per size
- **WHEN** staff save an offer for a sized product with `stock` 3 and `size_stock` `{"M": 0}`
- **THEN** M shows out of stock, every other size shows in stock, and the total is 3 × (sizes − 1)

### Requirement: Sized cart, checkout and cancellation
A cart line for a sized product SHALL name one of its sizes; for a one-size product it SHALL name none. Each size SHALL be a separate line. Checkout SHALL refuse with `OUT_OF_STOCK` when a size lacks stock, changing nothing, and otherwise decrement that size. Order lines, receipts and staff order views SHALL show the size. Each issued unit SHALL record its size. Cancelling SHALL restock the same sizes.

#### Scenario: Size required
- **WHEN** a shopper adds a sized product without a size, or with a size it does not come in
- **THEN** they get 422, and the cart is unchanged

#### Scenario: Last item in a size
- **WHEN** size M has 1 left and a shopper checks out 2 M while L has plenty
- **THEN** checkout returns `OUT_OF_STOCK`, and no stock moves

#### Scenario: Claimed garment keeps its size
- **WHEN** the buyer claims a unit bought in size M
- **THEN** the wardrobe item shows size M
