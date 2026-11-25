## Context

See `proposal.md` and the three specs. The foundation `catalogue` module already has the following:
- immutable `product_revision` rows, made immutable by a trigger;
- source and snapshot provenance;
- single-product ingestion, through `CatalogueService.ingest` and the `domain.validate` rules;
- `RevisionReader` for other modules.

What it lacks: `product.catalogue_status` is `active`/`retired` but there is no publication state, and there are no browse queries.

## Goals / Non-Goals

**Goals:** bulk import that reuses the single-product validation rules exactly; publication as a pointer to one immutable revision; fast, simple public browse; and every new route covered by tests.

**Non-Goals:**
- async workers for import (a job is processed in its request, up to 5000 rows);
- image fetching, transformation or embeddings;
- search ranking beyond substring matching;
- prices or stock (the commerce change);
- styled UI.

## Decisions

### D1: Publication is a pointer, browse data is denormalised on publish

Migration `0005` adds to `product`:
- `publication_state` (`draft`, `published` or `retired`), with `published_revision_id`, `published_at` and `retired_at`;
- browse columns: `browse_name`, `browse_category`, `browse_colour`, `browse_slot` and `browse_text` (lowercased name + description). These are written in the same transaction that publishes.

Browse queries therefore read one table with plain indexes, and never parse JSON from revisions.

Other details:
- Retiring sets `publication_state = retired` and `catalogue_status = retired`, so issuance also stops.
- Existing `active` products are backfilled as `published` at their current revision. This keeps the foundation thread and units working.

*Alternative considered:* computing browse rows from the revision's JSONB facts at query time. It was rejected for being slower, and because filtering on facts that are not yet published would be easy to get wrong.

### D2: Import reuses the ingestion rules, one transaction per row

`import_rows` maps each CSV row to the same `SourceProductInput` that single ingestion validates, and runs `CatalogueService` row logic in its own unit of work.

- A rejected row commits its outcome only; a good row commits its product, its revision and its outcome.
- The job header (`catalogue_import_job`) and its rows (`catalogue_import_row`) are persisted.
- The same `(source, external_id)` with identical content gives `unchanged`.

*Alternative considered:* one big transaction. It was rejected because one bad row would discard thousands of good ones, and locks would be held for a long time.

### D3: Mapping `hm-articles@1`

| Source column | Verified fact | Required |
|---|---|---|
| `article_id` | external id (kept as a string, leading zeros preserved) | yes |
| `prod_name` | `product_name` | yes |
| `product_type_name` | `category` | yes |
| `product_group_name` | `product_group` | yes |
| `colour_group_name` | `colour` | yes |
| `department_name` | `department` | no |
| `section_name` | `section` | no |
| `garment_group_name` | `garment_group` | no |
| `index_group_name` | `index_group` | no |
| `graphical_appearance_name` | `graphical_appearance` | no |
| `perceived_colour_master_name` | `perceived_colour` | no |
| `detail_desc` | `description` | no; only when non-empty |

All columns stay in `original_fields`.

The `slot` annotation (origin `rule`, note `hm-articles@1`) is derived as follows:

| `product_group_name` | Slot |
|---|---|
| Garment Upper body | `top`, or `outer` when `product_type_name` ∈ {Jacket, Coat, Blazer, Outdoor Waistcoat} |
| Garment Lower body | `bottom` |
| Garment Full body | `dress` |
| Shoes | `footwear` |
| Accessories | `accessory` |
| anything else (underwear, socks, swimwear, nightwear, cosmetics, …) | no slot |

### D4: Collections

`catalogue_collection` has `(id, slug unique, title)`, and `catalogue_collection_item` has `(collection_id, product_id, position)`. An editor replaces the whole ordered list with a `PUT`. Public reads join on `publication_state = 'published'`.

### D5: Routes

**Staff** (the `catalogue:ingest` capability, which editors and admins have):
- `POST`/`GET /admin/catalogue/import-jobs[/{id}]`
- `GET /admin/catalogue/review`
- `GET /admin/catalogue/products/{id}`
- `POST …/{id}/publish {revision_id}`
- `POST …/{id}/retire`
- `GET`/`PUT`/`DELETE /admin/catalogue/collections[/{slug}]`

**Public:**
- `GET /catalogue/products`
- `GET /catalogue/products/{id}`
- `GET /catalogue/facets`
- `GET /catalogue/collections[/{slug}]`

### D6: Media rights

A media reference is public only when `rights.public_display` is `true`. The existing single ingestion already requires a `rights.basis`.

## Risks / Trade-offs

- **[Substring search is basic.]** It is sufficient for the demo and the thesis scope; a full-text index can come later without an API change.
- **[A synchronous 5000-row import takes seconds.]** The size is bounded, and progress is per-row durable, so a retried job is idempotent.
- **[No permitted real data.]** Synthetic rows in the H&M column format are labelled `synthetic_only`; the real import path is identical.

## Migration Plan

Run `0005` (additive, with backfill), then deploy. Rollback before catalogue data exists means restoring the backup; after that, roll forward only.
