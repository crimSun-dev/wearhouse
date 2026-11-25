# personal-sizes Specification

## Purpose
Lets each person keep their usual sizes and use them to shop and organise their wardrobe.

## Requirements

### Requirement: Usual sizes
A signed-in user SHALL be able to read and set one usual size per active system, and clear it with `null`. Unknown or retired sizes SHALL be refused with 422. Usual sizes SHALL appear in the account export and SHALL be erased with the account.

#### Scenario: Set and read
- **WHEN** a user sets letter `M` and EU shoe `42`
- **THEN** `GET /me/sizes` returns both, and other users never see them

### Requirement: Shop by size
Browse SHALL accept `size=<system>:<code>` and `my_sizes=true` (signed in only). It SHALL return only products available in that size, or in any of the caller's usual sizes. Cursors SHALL be bound to the size filter. `my_sizes=true` without usual sizes SHALL return `409 NO_USUAL_SIZES`. Personal product recommendations SHALL leave out sized products that miss every usual size in their system.

#### Scenario: In my size
- **WHEN** a user whose usual letter size is M browses with `my_sizes=true`
- **THEN** only products available in M (and products in their usual sizes of other systems) are listed

### Requirement: Wardrobe sizes and sorting
Every wardrobe item SHALL carry a size or `null`. A verified item takes the purchased size, and the owner can correct any item's size. The list SHALL accept `size=<system>:<code>` and `sort=size`, which orders by system position, then size rank, with unsized items last.

#### Scenario: Sort by size
- **WHEN** an owner with S, L and unsized items lists with `sort=size`
- **THEN** the order is S, L, then the unsized items
