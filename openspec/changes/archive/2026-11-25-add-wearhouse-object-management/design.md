## Context

The catalogue holds 105,542 published H&M products, with media only as source `media_reference` rows on immutable revisions (none for H&M). Roles live in `role_grant` (identity) and are granted by CLI. Ownership has the issue/reissue APIs, and commerce has offers and orders.

## Decisions

### D1: Media belong to the product, not the revision

`product_media` stores `(id, product_id, kind, content_type, data bytea, sha256, size, alt_text, position, rights jsonb, generator, status, created_by, created_at, removed_at)`. Images change independently of source facts, and immutable revisions must not churn for a picture swap. The source `media_reference` rows stay as provenance. Public views list product media first, then any public source references.

*Alternative considered:* new revisions per image change. Rejected: it pollutes the review queue and breaks the "revision = source facts" meaning.

### D2: Generated placeholder

`catalogue/placeholder.py` (pure) builds an SVG card of 600×800 px:
- the background is tinted from the colour hex (the colour table moves to `catalogue/domain.py`, and wardrobe re-exports it);
- a silhouette path per slot (top, outer, bottom, dress, footwear, accessory, unknown);
- the name and category as text, escaped with `xml.sax.saxutils`;
- a "GENERATED PLACEHOLDER" label.

`generator = "wearhouse-placeholder@1"`; `rights = {basis: "generated", public_display: true}`.

Generation is deterministic (same input, same bytes), so the sha256 identifies duplicates. Bulk "generate missing" selects published products with no active media, 1000 per transaction.

### D3: Serving

`GET /api/v2/media/{id}` returns 404 unless the object is active and its product is published, or the caller has `catalogue:media`. Headers: `nosniff`, a strict CSP, `Cache-Control: public, max-age=86400` for published products (`private, no-store` for staff-only reads), and an ETag from the sha256. Uploads are raster only, sniffed by magic bytes; SVG is never accepted from clients.

### D4: Capabilities

| Capability | Roles |
|---|---|
| `catalogue:media` | editor, admin |
| `identity:manage_roles` | admin |
| `commerce:orders` | inventory manager, admin |

Role administration lives in `accounts`, because it needs handles, and it uses identity ports (`find`/`grant`/`revoke`/`roles`) plus a new `staff()` listing. "Last admin" is counted in the same transaction, with the `role_grant` rows for `admin` locked.

### D5: Bulk offers

Product ids come from a new `RevisionReader.published_ids(category, slot)`. The offers are written with one multi-row upsert per rule (`ON CONFLICT DO NOTHING` when `overwrite` is false). There is one audit event.

### D6: Scale

Migration `0009` runs `CREATE EXTENSION IF NOT EXISTS pg_trgm` (a trusted extension, available on Neon) and adds:
- a GIN trigram index on `product.browse_text`, partial `WHERE publication_state = 'published'`;
- partial btree indexes on `browse_category`, `browse_colour`, `browse_slot` and `(lower(browse_name), id)`.

The facet cache is an in-process dictionary with a timestamp; the publication service clears it on any publish or retire.

## Risks / Trade-offs

- **[105k SVGs at about 2 KB each, roughly 200 MB, in PostgreSQL.]** This is acceptable for the mockup. The media object model allows moving bytes to object storage later behind the same id.
- **[The facet cache is per process.]** Staleness is bounded to 60 s across processes; that is documented.

## Migration Plan

Run `0009` (additive), then `wearhouse generate-media --missing`.
