## Why

Wearhouse needs a real, browsable catalogue: the "Store" of the Steam-like product. Commerce, wardrobe and recommendations all depend on it. The foundation can ingest one source product at a time, but nothing is published, browsable or searchable. You asked to build all ecosystem functionality without waiting on UI polish. The catalogue comes first in the dependency order (`roadmap.md`, services step 1).

## What Changes

- **Bulk import.** Staff run import jobs over the H&M `articles.csv` format (header-mapped CSV). A versioned field mapping preserves every original field, maps documented columns to verified facts, and adds a rule-derived wardrobe `slot` annotation. Unknown types stay unknown. Each job records row-level errors and per-row outcomes; it is idempotent per `(source, external_id)` and creates a revision only when the content changes. The existing single-product ingestion is unchanged.
- **Publication workflow.** Import → review → publish → retire. A product is invisible to the public until an editor publishes one of its revisions. Retiring hides it from browse but never removes owned-item history or blocks lookups of units already issued. Every step is audited.
- **Media rights.** Media references carry a rights record. Only media whose rights allow public display appear publicly; nothing is fetched from arbitrary URLs.
- **Featured collections.** Editors manage ordered collections ("Special Sections") of published products.
- **Public browse.** Text search, category/colour/slot filters, facets with counts, stable cursor pagination, product detail (published facts only), and collections. These are public and read-only.
- **Discovery uses the published presentation.** Tag lookup shows the published revision when one exists.
- **Temporary pages.** The temporary web app gains plain Store pages (browse, search, product, collections) and staff pages (import, review/publish/retire, collections). No visual polish.
- **Data honesty.** No permitted H&M snapshot exists in the workspace. All automated tests use clearly labelled synthetic rows in the H&M column format, and real data is imported the same way once you have it. No product facts, images, prices or stock are invented.

## Capabilities

### New Capabilities
- `catalogue-import`: bulk source import jobs, versioned field mapping, row-level outcomes, idempotency.
- `catalogue-publication`: draft/published/retired lifecycle, editor review, media rights visibility, featured collections, audit.
- `catalogue-browse`: public search/filter/facets/pagination, product detail, collections and the published presentation for discovery.

### Modified Capabilities
None in `openspec/specs/` (no archived specs yet). This builds on the foundation's `source-product-units` behaviour (immutable revisions, source-preserving identity) and on `identity-access` (editor capability).

## Impact

- **API.** `apps/api` `catalogue` module (import, publication, browse application services and adapters); migration `0005_catalogue_publication`; new `/api/v2/admin/catalogue/*` and `/api/v2/catalogue/*` routes; regenerated contracts.
- **Pages.** `apps/web/account-pages` (temporary pages) gains Store and staff catalogue pages.
- **Unchanged.** Legacy v1, the accounts behaviour, and redemption semantics.
