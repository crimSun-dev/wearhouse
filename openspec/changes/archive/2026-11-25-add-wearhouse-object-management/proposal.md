## Why

The real H&M catalogue is in: 105,542 products. They have no images, the sandbox shop has no prices at that scale, staff access depends on CLI-granted roles, and several staff objects (units, orders) have APIs but no management surface. The user's direction on 2026-11-25:
- products get **generated placeholder images**, because the project is a mockup;
- those images must be **replaceable objects** that staff add and remove, never hardcoded;
- the staff view follows the account's roles, so an account with a role gets the matching object management.

All of this must be finished before the frontend.

## What Changes

- **Product media objects.** Each product has an ordered list of media objects: generated or uploaded, each with alt text, rights, a checksum and a status. Staff can generate, upload, reorder, edit and remove them; removal is soft. Every product gets a deterministic **generated placeholder** (SVG, labelled `generated`) through a bulk "generate missing" job. Public reads serve a product's active media only for published products, through `/media/{id}`, with safe headers. Uploads are raster only (JPEG, PNG or WebP, sniffed, at most 5 MB); only server-generated SVG is ever served. Browse thumbnails and product detail use these objects.
- **Role management in the app.** Admins can list staff, and grant or revoke `catalogue_editor`, `inventory_manager` and `admin` by handle. Every change is audited. The last admin cannot be removed, and admins cannot remove their own admin role. `/me` already reports roles and capabilities; the staff workspace shows only the sections those capabilities allow.
- **Staff workspace objects:**
  - unit management: issue N units with keys delivered to the issuer, reissue, and a unit list per product with status;
  - a staff order view (`commerce:orders`): every order, with the buyer's handle and status, filterable;
  - bulk sandbox offers: rules by category or slot set mock prices and stock for all matching published products, labelled sandbox, never H&M prices.
- **Catalogue at real scale.** A `pg_trgm` GIN index makes literal substring search fast, and indexes cover the browse filters. A short-TTL facet cache gives measured latency at 105k products.
- **Temporary pages.** A staff workspace with Products & media, Units, Offers (single and bulk), Orders, and Roles (admin), shown per capability. No visual polish.

## Capabilities

### New Capabilities
- `product-media`: media objects, generated placeholders, upload/remove/reorder, and public serving.
- `staff-roles`: in-app role management under admin capability.
- `staff-workspace`: unit management, staff orders and bulk sandbox offers.
- `catalogue-scale`: indexed search, facets and measured latency at 105k products.

### Modified Capabilities
None archived. This extends the catalogue publication, commerce, ownership and identity behaviour of the earlier changes.

## Impact

- **API.**
  - The `catalogue` module gains media.
  - `accounts` gains staff role administration, through identity ports.
  - `ownership` gains a unit listing; `commerce` gains staff orders and bulk offers.
  - New capabilities `catalogue:media`, `identity:manage_roles` and `commerce:orders`.
  - Migration `0009_object_management`; contracts regenerated.
- **CLI.** `wearhouse generate-media`.
- **Pages.** The staff workspace pages.
- **Unchanged.** Legacy v1.
