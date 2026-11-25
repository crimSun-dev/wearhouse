# catalogue-browse Specification

## Purpose
Lets anyone explore the published Wearhouse catalogue the way a store front works: search, filter, browse facets and collections, and open product details. Only published, rights-cleared data is shown.

## Requirements

### Requirement: Search, filters and stable pagination
`GET /api/v2/catalogue/products` SHALL support the following, over published, non-retired products only:
- a text query over product name and description;
- filters by category, colour and wardrobe slot;
- sorting by newest or name;
- stable cursor pagination, default 24 and maximum 100.

Text input SHALL be treated literally, without wildcards. Invalid cursors or limits SHALL be rejected.

#### Scenario: Filtered search
- **WHEN** a visitor searches "dress" filtered to colour Black
- **THEN** only published products whose name or description contains "dress" and whose colour fact is Black are returned

#### Scenario: Paging is stable
- **WHEN** a visitor pages through results while a new product is published
- **THEN** later pages neither repeat nor skip products that were already listed

### Requirement: Facets
The service SHALL return counts of published products per category, colour and slot, so a client can build browse menus.

#### Scenario: Facet counts
- **WHEN** three published products are T-shirts and one is a Dress
- **THEN** the category facet reports T-shirt 3 and Dress 1, and drafts are not counted

### Requirement: Product detail and discovery presentation
`GET /api/v2/catalogue/products/{id}` SHALL return the published revision's verified facts, its annotations labelled as annotations, its source identity and its public media. Unpublished or retired products SHALL return 404. Tag discovery SHALL present the published revision when one exists.

#### Scenario: Annotation is labelled
- **WHEN** a product has a rule-derived slot
- **THEN** the detail shows it under annotations with origin `rule` and the mapping version, not as a verified fact
