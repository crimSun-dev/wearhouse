# ecosystem-acceptance Specification

## Purpose
Proves the Wearhouse ecosystem works as one product before any new interface is built (roadmap F11).

## Requirements

### Requirement: End-to-end thread through the HTTP API
One automated test SHALL run the full thread on one database through the HTTP API with signed identities:
1. an admin grants the editor and inventory roles in the app;
2. the editor imports and publishes products, generates placeholder media and applies bulk sandbox offers;
3. a customer searches the store, wishlists a product, buys it, reveals the key and claims it;
4. the customer creates a look with the claimed garment, plans it today, logs wearing it, and shares it with friends;
5. a friend sees the share in the feed and a notification;
6. similar-items and personal recommendations answer with declared modes.

#### Scenario: Thread completes
- **WHEN** the acceptance test runs
- **THEN** every step succeeds, and the customer's wardrobe holds the verified garment with a wear count of 1

### Requirement: State survives restart, and isolation holds
After the thread, a new app instance built on the same database SHALL return the same wardrobe, order, look, share and notification. A second, unrelated customer SHALL receive 404 or 403 for every private object of the first customer: order, key, wardrobe item, look revision, plan and private share.

#### Scenario: Restart
- **WHEN** a fresh app instance serves the customer
- **THEN** the order receipt, wardrobe item and share are unchanged

#### Scenario: Isolation
- **WHEN** another customer requests the first customer's private objects by id
- **THEN** each request returns 404 or 403
