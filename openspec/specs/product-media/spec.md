# product-media Specification

## Purpose
Gives every product replaceable image objects. They start as generated placeholders, and staff can add, reorder and remove them, with nothing hardcoded.

## Requirements

### Requirement: Media objects per product
Each product SHALL have an ordered list of media objects, each with:
- an id and kind (`generated` or `uploaded`);
- content type, checksum and byte size;
- alt text, position and rights;
- status: active, or removed with its removal time.

Accounts with `catalogue:media` (editors and admins) SHALL be able to list, upload, generate, reorder, edit alt text, and remove media objects. Removing SHALL be soft and audited, and a removed object SHALL no longer be served. A product SHALL have at most 20 active media objects.

#### Scenario: Replace a placeholder
- **GIVEN** a product with one generated placeholder
- **WHEN** an editor uploads a PNG and removes the placeholder
- **THEN** the public detail shows only the uploaded image, and the placeholder's URL returns 404

#### Scenario: Customer cannot manage media
- **WHEN** a customer uploads or removes product media
- **THEN** the service returns 403

### Requirement: Generated placeholders, never presented as real photos
The service SHALL generate a deterministic SVG placeholder from the product's own published facts: name, category, colour (from the documented colour table, or neutral when unknown) and wardrobe slot. The placeholder SHALL carry a visible "generated placeholder" label and `kind: generated`. A bulk job SHALL add one placeholder to every product that has no active media, in batches, and SHALL be idempotent.

#### Scenario: Bulk generation is idempotent
- **WHEN** "generate missing" runs twice over the same catalogue
- **THEN** each product has exactly one generated placeholder

#### Scenario: Markup in product names is inert
- **WHEN** a product name contains `<script>` or `&`
- **THEN** the SVG contains the escaped text, and no element comes from the name

### Requirement: Safe serving and upload validation
`GET /media/{id}` SHALL serve an active media object only when its product is published, or to staff. Responses SHALL include `X-Content-Type-Options: nosniff`, `Content-Security-Policy: default-src 'none'; style-src 'unsafe-inline'` and an ETag. Uploads SHALL be JPEG, PNG or WebP, decided by magic bytes, and at most 5 MB. An uploaded SVG or any other type SHALL be rejected. Public product detail and browse thumbnails SHALL use the first active media object.

#### Scenario: SVG upload rejected
- **WHEN** an editor uploads an SVG file
- **THEN** the service returns 422 `not_an_image`

#### Scenario: Draft product media hidden
- **WHEN** anyone requests media of an unpublished product
- **THEN** the service returns 404, and staff still can read it
