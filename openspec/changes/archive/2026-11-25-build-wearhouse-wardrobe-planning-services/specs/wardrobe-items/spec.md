## Purpose

Gives each user one private wardrobe: the garments they claimed and the clothes they declared themselves, with care states and shelves.

## ADDED Requirements

### Requirement: Unified private wardrobe
`GET /me/wardrobe/items` SHALL list the caller's wardrobe items. It SHALL include every claimed owned item, marked `verified` with its catalogue facts, and every non-archived declared item, marked `declared`. It SHALL support filters by slot, care state and shelf. Each item SHALL show its effective slot: the user override, else the catalogue rule annotation, else `unknown`. Other users SHALL never see these items or their photos.

#### Scenario: Claimed item appears
- **WHEN** a user claims a garment
- **THEN** the garment appears in their wardrobe as `verified`, with the slot from its catalogue annotation and care state `ready`

#### Scenario: Another user's item
- **WHEN** user B reads user A's wardrobe item id
- **THEN** the service returns the same 404 as for a missing item

### Requirement: Declared (manual) items without fabricated verification
A user SHALL be able to declare an item with:
- a name (1 to 80 characters);
- a slot from the registry;
- an optional category, colour name and photo.

A declared item SHALL have no serial, no product and no verification claim. Any attribute that was not given SHALL be stored and shown as unknown. A photo SHALL be JPEG, PNG or WebP (checked by its magic bytes), at most 2 MB. The photo SHALL be served only to its owner, through `GET /me/wardrobe/items/{id}/photo`. A user SHALL have at most 1000 declared items.

#### Scenario: Unknown colour stays unknown
- **WHEN** a user declares "Thrifted denim jacket" in slot `outer` without a colour
- **THEN** the item shows colour `null` with `colour_known: false`, `verified: false`, and no serial

#### Scenario: Fake image
- **WHEN** a user uploads a text file renamed `.jpg`
- **THEN** the service returns 422, and no photo is stored

### Requirement: Care states and slot overrides
A user SHALL be able to set the care state of any of their items to `ready`, `laundry`, `repair` or `stored`, and to set or clear a slot override. Only `ready` items SHALL be offered by suggestions. A declared item can be archived, which hides it but keeps any looks that already reference it readable.

#### Scenario: Laundry item not suggested
- **WHEN** an item is in `laundry`
- **THEN** outfit suggestions do not include it

### Requirement: Shelves
A user SHALL be able to create, rename, reorder (replace the whole list) and delete shelves. A user SHALL have at most 50 shelves, each an ordered list of at most 500 of their own wardrobe items. Referencing an item the user does not own SHALL be rejected.

#### Scenario: Foreign item on a shelf
- **WHEN** a user puts another user's item id on a shelf
- **THEN** the service returns 422 `unknown_item`, and the shelf is unchanged
