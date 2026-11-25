# staff-roles Specification

## Purpose
Lets admins decide in the app which accounts are staff. The staff view then follows the roles an account holds.

## Requirements

### Requirement: Role management by admins
Accounts with `identity:manage_roles` (admins only) SHALL be able to:
- list staff accounts with their handles and roles;
- look up an account by handle;
- grant or revoke `catalogue_editor`, `inventory_manager` and `admin`.

Every change SHALL be audited with the acting admin. Revoking the last remaining admin, or an admin revoking their own admin role, SHALL be refused with 409. Non-admins SHALL get 403. The CLI `grant-role` remains the bootstrap for the first admin.

#### Scenario: Grant editor
- **WHEN** an admin grants `catalogue_editor` to `@alice`
- **THEN** Alice's next `/me` lists the role and the `catalogue:*` capabilities, and her staff catalogue routes succeed

#### Scenario: Last admin protected
- **GIVEN** exactly one admin
- **WHEN** that admin revokes their own admin role
- **THEN** the service returns 409 `LAST_ADMIN`

#### Scenario: Revoked role takes effect immediately
- **WHEN** an admin revokes Alice's editor role
- **THEN** Alice's next staff catalogue request returns 403

### Requirement: Capability-driven staff view
`/me` SHALL report roles and capabilities. Staff surfaces SHALL be governed by capabilities:
- `catalogue:ingest` and `catalogue:media` for products and media;
- `commerce:offers` for offers;
- `inventory:issue` and `inventory:reissue` for units;
- `commerce:orders` for orders;
- `identity:manage_roles` for roles.

The server SHALL enforce every capability regardless of what the client shows.

#### Scenario: Inventory manager view
- **WHEN** an inventory manager reads `/me`
- **THEN** the capabilities include `inventory:issue` and `commerce:orders`, but not `catalogue:ingest` or `identity:manage_roles`
