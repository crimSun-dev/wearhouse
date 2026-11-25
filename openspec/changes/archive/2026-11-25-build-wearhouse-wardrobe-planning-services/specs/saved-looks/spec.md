## Purpose

Lets users compose looks from their own items under explicit slot rules, and keeps every saved version.

## ADDED Requirements

### Requirement: Slot registry and occupancy rules
The service SHALL publish its slot registry at `GET /wardrobe/slots`. A look SHALL obey these rules:
- `top`, `outer`, `bottom`, `dress` and `footwear` take at most one item each;
- `accessory` takes at most 3 items;
- `dress` SHALL NOT be combined with `top` or `bottom`;
- an item SHALL appear at most once;
- each item's effective slot SHALL match the slot it is placed in.

#### Scenario: Dress with a top
- **WHEN** a user saves a look with a dress and a top
- **THEN** the service returns 422 `slot_conflict`

#### Scenario: Unknown-slot item
- **WHEN** a user places an item whose effective slot is `unknown`
- **THEN** the service returns 422 `slot_unknown` until the user sets a slot override

### Requirement: Looks with immutable revisions
A user SHALL be able to create a look (name plus slot assignments), edit it, list their looks, read any revision, and delete a look. Every create or edit SHALL write a new immutable revision. Plans and wear entries SHALL reference a revision, and a deleted look's revisions SHALL stay readable to those plans. Every referenced item SHALL belong to the caller at save time. A user SHALL have at most 200 looks.

#### Scenario: Editing keeps history
- **GIVEN** a look at revision 1, planned for Friday
- **WHEN** the user swaps the shoes, creating revision 2
- **THEN** Friday's plan still shows revision 1, and the look's current revision is 2

#### Scenario: Foreign item in a look
- **WHEN** a user references another user's item
- **THEN** the service returns 422 `unknown_item`
