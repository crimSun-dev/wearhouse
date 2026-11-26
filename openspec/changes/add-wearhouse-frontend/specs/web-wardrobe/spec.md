## Purpose

Defines the web wardrobe: library, item inspector, declared garments, shelves, looks, fitting room, outfit suggestions, planner, wear log, weather and usual sizes. It is built on the wardrobe-items, accessory-slots, saved-looks, outfit-recommendations, outfit-planner, weather-forecast and personal-sizes capabilities.

## ADDED Requirements

### Requirement: Library
The wardrobe library SHALL list owned and declared items from `GET /me/wardrobe/items` with:
- filters for slot, care state, shelf and size;
- sorting by size, name and wear;
- a client-side text filter;
- grid, list and outfit views, defaulting to the `wardrobe_view` setting;
- grouping by slot when `wardrobe_group_by_slot` is on;
- slot counts and shelves in a sidebar;
- an item count.

An empty wardrobe SHALL offer redeem, add a garment and browse the catalogue.

#### Scenario: Default view from settings
- **WHEN** a user's `wardrobe_view` is `list`
- **THEN** the library opens in list view

### Requirement: Item inspector
The inspector SHALL show:
- imagery (product media, or the private photo loaded with authentication);
- whether the item is verified or declared;
- for verified items, provenance from `GET /me/items/{id}` (source namespace, external id, revision, snapshot), the serial (owner only) and the claimed date;
- size and its source;
- care state;
- slot and its source;
- attributes and their origin;
- wear count and last worn date;
- the archive state.

The owner SHALL be able to change the name, care state, slot override, attributes, size and archive state, and upload a JPEG, PNG or WebP photo of up to 2 MB. Items with `state: revoked_sandbox` SHALL be shown as revoked.

#### Scenario: Unknown slot needs override
- **WHEN** an item has `slot_source: unknown`
- **THEN** the inspector asks for a slot override before the item can be equipped

### Requirement: Declared garments
Users SHALL be able to declare a garment with name, slot, and optionally category, colour and size, then optionally add a photo. Unknown attributes SHALL stay visibly unknown and editable. `WARDROBE_FULL` SHALL be explained.

#### Scenario: Declared item appears
- **WHEN** a user declares a garment
- **THEN** it appears in the library marked as declared, with no serial

### Requirement: Shelves and looks
Users SHALL be able to create, rename, reorder (with pointer and keyboard), and delete shelves of their own items. Users SHALL be able to:
- list looks;
- open a look with its revision history and view any past revision read-only;
- rename and re-save a look;
- delete a look.

Items missing from a look revision SHALL render as placeholders.

#### Scenario: Revision history
- **WHEN** a user saves a changed look
- **THEN** the look shows a new current revision, and the previous revision remains viewable

### Requirement: Fitting room
The fitting room SHALL compose a look from the slot registry (`GET /wardrobe/slots`), respecting capacities and exclusions. Before any equip that would displace items, it SHALL show which items will be removed, for example a dress removing the top and bottom. Non-ready items SHALL carry a warning. Saving SHALL create a look or a new revision. Server validation errors SHALL be shown on the affected slots.

#### Scenario: Dress conflict preview
- **WHEN** a user equips a dress while a top and a bottom are equipped
- **THEN** the top and bottom are previewed as removed and are only removed after confirmation

### Requirement: Outfit suggestions
Suggestions SHALL be requested only on explicit user action: opening the view, changing the date or occasion, or pressing refresh. They SHALL NOT be requested on hover, prefetch or polling. The view SHALL offer:
- the date;
- the suggestion occasions from the registry;
- optional rain and hot overrides.

It SHALL show the weather source, up to five outfits with explanations, the score components, the ruleset, and the model mode and weights. When fewer outfits exist it SHALL show `reasons` and `removed_by_rule`. A `displayed` event SHALL be sent once when the results are visible. A `chosen` event SHALL be sent once per run when the user picks an outfit. `enabled: false` SHALL explain that suggestions are off in Settings.

#### Scenario: Single displayed event
- **WHEN** a user opens suggestions and scrolls the results back and forth
- **THEN** exactly one `displayed` event is sent for that run

### Requirement: Planner and wear
The planner SHALL show seven local dates from `GET /me/planner?from=` with previous and next week controls. For each day it SHALL show:
- the weather status (forecast summary, "Forecast unavailable", or the unavailable reason);
- the planned look revision with the planner occasion and note;
- the wear entries.

Users SHALL be able to plan or replace a plan from today up to 30 days ahead, and to clear a plan. Mark worn SHALL send one idempotent wear entry and SHALL leave the plan unchanged. The wear log SHALL list entries in a date range, allow logging a past day up to 60 days back, and allow undoing an entry. Planner occasions and suggestion occasions SHALL remain separate lists.

#### Scenario: Planned is not worn
- **WHEN** a user marks a planned day as worn
- **THEN** the day shows both the plan and a wear entry, and deleting the wear entry keeps the plan

### Requirement: Weather and sizes
Users SHALL be able to see the forecast for their saved location with its source and fetch time, set a BMKG adm4 location (validated format) or clear it, and get a setup prompt when no location is set. BMKG SHALL be credited. Users SHALL be able to view and set a usual size per size system.

#### Scenario: No location
- **WHEN** `GET /me/weather` returns `note: no_location`
- **THEN** the app prompts the user to set a location instead of showing an error
