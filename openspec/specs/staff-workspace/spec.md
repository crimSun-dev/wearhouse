# staff-workspace Specification

## Purpose
Gives staff a management surface for the objects behind the shop: garment units, orders and sandbox offers at catalogue scale.

## Requirements

### Requirement: Unit management
Inventory managers and admins SHALL be able to list a product's units with serial, status and creation time, using cursor paging. Issuing and reissuing SHALL keep the existing rules: idempotent, with the key delivered only to the issuing actor. A unit list SHALL NOT contain keys or owner identities.

#### Scenario: Unit list has no secrets
- **WHEN** staff list a product's units after one was claimed
- **THEN** each unit shows serial and status (`issued`, `claimed` or `retired`), and no key or owner

### Requirement: Staff order view
Accounts with `commerce:orders` (inventory managers and admins) SHALL be able to list all sandbox orders, newest first with cursor paging, filtered by status. Each entry SHALL show the buyer's handle (null for deleted accounts), total, status, item count and time. Staff order reads SHALL NOT reveal activation keys.

#### Scenario: Customer cannot list all orders
- **WHEN** a customer requests the staff order list
- **THEN** the service returns 403

### Requirement: Bulk sandbox offers
Accounts with `commerce:offers` SHALL be able to apply up to 50 rules. Each rule matches a category and/or slot and sets a sandbox price (1–100,000,000 IDR) and stock (0–100,000) for every matching published product. With `overwrite: false`, existing offers SHALL be kept. The response SHALL report counts per rule, and one audit event SHALL record the rules. Prices SHALL be labelled sandbox like every offer.

#### Scenario: Category rule
- **WHEN** staff apply `{category: "Trousers", price_idr: 249000, stock: 50}`
- **THEN** every published Trousers product without an offer gets that sandbox offer, and the response reports the count
