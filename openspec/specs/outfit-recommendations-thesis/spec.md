# outfit-recommendations-thesis Specification

## Purpose
Wardrobe outfit suggestions follow the thesis method (§3.4.3, Eqs. 7–9) and share their rule vocabulary with the RQ2 research.

## Requirements

### Requirement: Shared attribute lookup and hard rules
Every wardrobe item SHALL carry warmth, rain_suitable, long_sleeve, long_bottom and formal values, each with an origin:
- `rule`: derived by ruleset `wardrobe-rules@1` from the slot and the item text, using the same keyword table as the RQ2 configuration;
- `owner`: the owner's correction, which wins.

Suggestions SHALL only contain outfits that pass all of these:
- slots: top+bottom or dress, plus footwear, plus an optional outer;
- on a hot day, no heavy outerwear;
- on a rainy day, rain-suitable footwear or outerwear;
- for worship, long sleeves and a long bottom;
- for a wedding, at least one formal item.

The response SHALL report how many candidates each rule removed.

#### Scenario: Rain rule
- **WHEN** it is raining and the wardrobe's only footwear are sandals and there is no rain-suitable outerwear
- **THEN** no suggestion is returned, and the response explains that the rain rule removed every candidate

#### Scenario: Owner correction
- **WHEN** the owner marks those sandals `rain_suitable: true`
- **THEN** outfits with them become eligible, and the attribute shows origin `owner`

#### Scenario: Same vocabulary as the research
- **WHEN** the research configuration is present
- **THEN** its keyword table equals the app's `wardrobe-rules@1` table

### Requirement: Eqs. 7–9 ranking with deduplicated feedback
Eligible outfits SHALL be ranked by `w1·compatibility + w2·mean preference − w3·mean recency`, where:
- `preference = (chosen + a·p0)/(recommended + a)`;
- `recency = exp(−days since worn / h)`, and 0 when never worn.

The weights SHALL come from the caller's recommendation style. At most 5 suggestions SHALL be returned, with distinct cores. Every request SHALL create a run.

A `displayed` event SHALL count each item at most once per run. A `chosen` event SHALL be accepted once per run; repeating the same choice is a no-op, and a different choice gets `409 ALREADY_CHOSEN`. Runs SHALL be visible only to their owner.

#### Scenario: Preference moves with evidence
- **WHEN** an item is displayed in 5 runs and chosen in 4
- **THEN** its preference is (4 + 2.5)/(5 + 5) = 0.65, and refetching suggestions without events changes nothing

#### Scenario: Recency
- **WHEN** an item was worn yesterday
- **THEN** its recency is exp(−1/4) ≈ 0.78, and an outfit without it ranks above an otherwise identical outfit with it
