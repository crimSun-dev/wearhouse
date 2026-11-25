# catalogue-personal-shelf Specification

## Purpose
Catalogue ranking extras from TDD §12.2.

## Requirements

### Requirement: Hide owned and completion/duplicate rerank
Browse SHALL accept `hide_owned=true` for signed-in callers, excluding the products of their own (non-revoked) items. Personal product recommendations SHALL rerank candidates with `candidate + λc·completion − λd·duplicate`, where:
- completion is the mean heuristic compatibility with the best three owned items of other slots (0 with an empty wardrobe);
- duplicate is 1 when an owned item has the same category and colour.

The response SHALL declare the rerank, its λ values and whether cold start applied.

#### Scenario: Duplicate pushed down
- **WHEN** a user owns a black T-shirt
- **THEN** another black T-shirt ranks below an otherwise equal product that is not a duplicate
