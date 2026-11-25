## Purpose

Accessory positions as in the TDD slot registry (§11), without guessing.

## ADDED Requirements

### Requirement: Typed accessory positions
The slot registry SHALL contain top, outer, bottom, dress, footwear, bag, headwear, eyewear, earrings, necklace, tie, scarf, belt, wrist (capacity 2), ring (capacity 2) and accessory (uncategorized, capacity 3). Verified items whose catalogue slot is `accessory` SHALL resolve to a position by product type using ruleset `accessory-subtypes@1`, with slot source `rule`. Product types without a mapping SHALL stay `accessory`. Looks SHALL enforce each position's capacity.

#### Scenario: Bag resolves by rule
- **WHEN** an owner claims an H&M item whose product type is `Bag`
- **THEN** the wardrobe shows slot `bag` with source `rule`

#### Scenario: Two wrists, not three
- **WHEN** a look puts three items in `wrist`
- **THEN** it is refused with `over_capacity`
