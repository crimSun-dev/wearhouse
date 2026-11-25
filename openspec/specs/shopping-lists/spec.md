# shopping-lists Specification

## Purpose
Lets signed-in customers keep a wishlist and a cart of published products.

## Requirements

### Requirement: Wishlist
A signed-in user SHALL be able to add a published product to their wishlist, list it newest first, and remove products, with at most 500 products. Adding a product twice SHALL be a no-op. Products that become unpublished SHALL stay listed but be marked unavailable. Only the owner SHALL see their wishlist.

#### Scenario: Add an unpublished product
- **WHEN** a user adds a draft product to the wishlist
- **THEN** the service returns 404, and nothing is stored

#### Scenario: Wishlist limit
- **GIVEN** a wishlist with 500 products
- **WHEN** the user adds another
- **THEN** the service returns 409 `WISHLIST_FULL`

### Requirement: Cart
A signed-in user SHALL be able to set a quantity from 1 to 5 for a published product that has an offer, remove lines, and list the cart with at most 20 lines. The cart listing SHALL show each line's current sandbox unit price, line total, availability and the cart total. Only the owner SHALL see their cart.

#### Scenario: Quantity out of range
- **WHEN** a user sets a quantity of 6
- **THEN** the service returns 422, and the cart is unchanged

#### Scenario: Product without an offer
- **WHEN** a user adds a published product that has no offer
- **THEN** the service returns 409 `NOT_FOR_SALE`
