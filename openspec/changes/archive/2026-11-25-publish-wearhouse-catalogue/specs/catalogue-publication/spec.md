## Purpose

Gives editors control over what the public catalogue shows: review, publish or retire products, curate featured collections, and keep restricted images out of public view.

## ADDED Requirements

### Requirement: Draft, published and retired lifecycle
Imported or ingested products SHALL start unpublished. An editor SHALL be able to publish a specific revision of a product, to publish a newer revision later, and to retire a product. Retiring SHALL hide it from public browse. It SHALL NOT remove owned items, ownership history, or the discovery lookup of units that were already issued. Each transition SHALL be audited with the acting editor.

#### Scenario: Draft is invisible
- **GIVEN** a product imported but never published
- **WHEN** anyone browses or searches the catalogue
- **THEN** the product does not appear, and its detail returns 404

#### Scenario: Publishing a new revision
- **GIVEN** a product published at revision 1, and a later import created revision 2
- **WHEN** the editor publishes revision 2
- **THEN** the public detail shows revision 2's facts, and revision 1 stays auditable

#### Scenario: Retire after ownership
- **GIVEN** a customer owns a unit of a published product
- **WHEN** an editor retires the product
- **THEN** the product disappears from browse, while the customer's owned item and the unit's discovery lookup remain

### Requirement: Review queue
Editors SHALL be able to list products whose latest revision is not published, including drafts and products with newer unpublished revisions, with their source identity and revision numbers.

#### Scenario: New revision needs review
- **WHEN** an import revises a published product
- **THEN** the product appears in the review queue until that revision is published

### Requirement: Media visibility follows rights
Public responses SHALL include a media reference only when its rights record allows public display. Wearhouse SHALL NOT fetch media from URLs.

#### Scenario: Restricted image
- **GIVEN** a published product with one public and one restricted media reference
- **WHEN** the public detail is read
- **THEN** only the public media reference is returned

### Requirement: Featured collections
Editors SHALL be able to create, rename, reorder and delete collections, each an ordered list of products. Public collection reads SHALL list only published products, in editor order.

#### Scenario: Collection with a retired product
- **WHEN** a product in a collection is retired
- **THEN** the public collection no longer lists it, and the editor's collection still shows it as retired
