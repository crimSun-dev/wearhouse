## Purpose

Suggests complete outfits from the user's ready items, and is honest about how they were ranked.

## ADDED Requirements

### Requirement: Valid candidates from ready items
`GET /me/recommendations/outfits?date=&occasion=&limit=` SHALL build candidates only from the caller's `ready` items with a known slot. Each candidate SHALL obey the slot registry: either `top`, `bottom` and `footwear`, or `dress` and `footwear`. It SHALL add an `outer` when rain or no heat is expected and an outer exists. If no valid candidate exists, the service SHALL return an empty list with a reason, such as `missing_slot: footwear`.

#### Scenario: No shoes
- **WHEN** the user owns tops and bottoms but no footwear
- **THEN** the result is empty, with reason `missing_slot: footwear`

### Requirement: Truthful ranking with components
Each suggestion SHALL carry its total score and the components:
- `compatibility`: the heuristic colour/style baseline, or `null` when unknown;
- `weather`;
- `rotation`: penalising items worn in the last 7 days.

The result SHALL carry the ranker's `ModelInfo` (mode `heuristic_baseline`) and the weather source used: `LIVE`, `CACHED`, `MANUAL` when the request supplied weather, or `NONE`. It SHALL NOT claim a trained model. Colour hex values SHALL come only from a documented colour-name table; unknown colour names SHALL stay unknown.

#### Scenario: Rain prefers an outer layer
- **GIVEN** rain is forecast for the date
- **WHEN** suggestions are requested
- **THEN** candidates that include an outer score higher on `weather` than the same items without it

#### Scenario: Recently worn ranks lower
- **GIVEN** two otherwise identical candidates
- **WHEN** one of them contains an item worn yesterday
- **THEN** that candidate has the lower `rotation` component
