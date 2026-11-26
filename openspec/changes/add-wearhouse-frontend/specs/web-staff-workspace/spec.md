## Purpose

Defines the web staff workspace for role-holding accounts: catalogue import and review, publication, media, sizes, collections, sandbox offers, orders, inventory and one-time key delivery, moderation, role administration and operations.

## ADDED Requirements

### Requirement: Capability gating
The staff workspace SHALL load only for accounts whose `/me` capabilities include a staff capability. Each staff screen SHALL appear only for its required capability:

| Capability | Screens |
|---|---|
| `catalogue:ingest` | review, imports, single ingest, collections, sizes |
| `catalogue:media` | media |
| `commerce:offers` | offers |
| `commerce:orders` | orders |
| `inventory:issue`, `inventory:reissue` | units |
| `social:moderate` | moderation |
| `identity:manage_roles` | staff roles |
| `ops:read` | ops |

A 403 from the server SHALL render a "not permitted" state.

#### Scenario: Moderator scope
- **WHEN** an account with only `social:moderate` opens the workspace
- **THEN** only moderation is listed, and opening a units URL directly shows "not permitted"

### Requirement: Catalogue publication workflow
Staff SHALL be able to:
- upload a source CSV (up to 10 MB and 5000 rows) with its source, snapshot checksum and permission fields;
- follow the import job's per-row outcomes and errors, and publish the job;
- work through the review queue;
- open a product's revisions and publish a specific revision;
- retire a product, with confirmation that owned items and tag lookups remain;
- ingest a single source product;
- edit featured collections as ordered product lists;
- manage size systems, size values and product sizes, and assign missing sizes.

#### Scenario: Rejected rows visible
- **WHEN** an import job has rejected rows
- **THEN** each rejected row is listed with its row number and errors

### Requirement: Media management
Staff SHALL be able to:
- list a product's media, including removed items on request;
- generate a placeholder;
- upload an image (up to 5 MB) with a rights basis and alt text;
- edit alt text;
- reorder media by drag and by keyboard;
- soft-remove media;
- generate missing placeholders in batches.

#### Scenario: Keyboard reorder
- **WHEN** staff move a media item up using only the keyboard
- **THEN** the new order is saved with `PUT …/media/order`

### Requirement: Commerce and inventory
Staff SHALL be able to:
- list, set and remove sandbox offers (price, stock, per-size stock);
- apply up to 50 bulk offer rules, with overwrite choice and per-rule results;
- list orders by status with the buyer's handle and no keys;
- list a product's units with serial and status;
- issue a unit with an idempotency key;
- reissue the key of an unclaimed unit.

A delivered key SHALL be shown once with copy and masking, and SHALL never be stored. A printable tag QR SHALL encode only the public serial URL.

#### Scenario: Tag never carries key
- **WHEN** staff print a tag for a newly issued unit
- **THEN** the QR encodes `#/items/{serial}` and does not contain the activation key

### Requirement: Moderation, roles and operations
Moderators SHALL be able to hide, restore or dismiss reported shares, with a required reason. Admins SHALL be able to list staff accounts and grant or revoke roles; `LAST_ADMIN` and `SELF_REVOKE` SHALL be explained. The ops view SHALL show model mode, the active artifact, claim attempts and failures, rate-limit counts, outbox state, running import jobs and the schema head, together with readiness from `GET /health/ready`. Every destructive or audited action SHALL require confirmation that states its effect.

#### Scenario: Last admin protected
- **WHEN** the only admin tries to revoke their own admin role
- **THEN** the app explains why it is refused and the role remains
