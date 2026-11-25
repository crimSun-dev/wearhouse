## Why

The ecosystem TDD (§12.3) and thesis §3.4.3 specify how wardrobe outfits are ranked. The live suggester does not follow that yet:
- it ranks with a colour heuristic, a weather fit and a 7-day rotation flag, with no hard rules and no occasions;
- nothing records which suggestions were shown or picked, which the preference term needs.

The RQ2 simulation already implements the thesis rules and Eqs. 7–9. The TDD requires the app and the research to share one rule vocabulary.

## What Changes

- **Thesis attribute lookup (shared vocabulary).** Ruleset `wardrobe-rules@1` derives warmth, rain-suitable, long sleeve, long bottom and formal from each item's slot and text, using the same keyword table as `research/configs/rq2.json` (thesis appendix, P0390). A parity test keeps the two identical. Each attribute carries its origin: `rule` for the appendix lookup, `owner` for the owner's correction. The owner can correct any attribute.
- **Hard rules (thesis §3.4.3 a–d).**
  - **a. Slots:** top+bottom or dress, plus footwear, plus optional outer.
  - **b. Heat:** a hot day removes heavy outerwear.
  - **c. Rain:** a rainy day requires rain-suitable footwear or outerwear.
  - **d. Dress codes:** worship requires long sleeves and a long bottom; a wedding requires something formal.

  Occasions are casual, campus, hangout, worship and wedding (the research schedule's vocabulary plus casual). The response reports how many outfits each rule removed, and why none were left when that happens.
- **Eqs. 7–9 scoring.** `score = w1·compatibility + w2·mean preference − w3·mean recency`, where:
  - `preference(g) = (chosen + a·p0)/(recommended + a)`;
  - `recency(g) = exp(−days_since_worn/h)`, and 0 for an item never worn;
  - the defaults are w = 0.5/0.3/0.2, p0 = 0.5, a = 5, h = 4 days (the demo defaults, declared as baselines).

  Compatibility stays the labelled heuristic baseline. Unknown colours count as 0.5 and say so.
- **Bounded, diverse candidates.** Per slot, the top M = 8 items by `pref − recency` are kept, then combinations are enumerated, with a final exact rule check. Up to 5 suggestions are returned, each with a distinct core (no two sharing top+bottom or dress).
- **Recommendation runs and events (TDD §12.3).**
  - Each suggestion request creates a private run holding its context and the suggestions shown.
  - `POST /me/recommendations/outfits/{run_id}/events` records `displayed` (exposures deduplicated per run and item) and `chosen` (once per run; a different second choice gets 409).
  - `recommended(g)` counts the distinct runs that displayed g; `chosen(g)` counts the runs whose chosen outfit contained g.
  - Repeated fetches and repeated events never inflate the counts.
- **Settings:** recommendation-style profiles become compatibility/preference/recency weights:
  - balanced 0.5/0.3/0.2;
  - classic 0.4/0.5/0.1 (favours what you pick);
  - adventurous 0.4/0.2/0.4 (penalises recent wear more).

  Weather off means rain and hot are unknown, so the weather rules are not applied (labelled).
- **Pages:** an occasion picker, a displayed event after rendering, and a chosen event when you save or wear a suggestion; rule explanations; item attribute corrections in the wardrobe.

## Capabilities

### New Capabilities
- `outfit-recommendations-thesis`: the shared rules, Eqs. 7–9, runs/events and attribute corrections.

### Modified Capabilities
None (extends outfit-recommendations; response fields are additive).

## Impact

Migration `0014_recommendation_runs`: runs, exposures and choices tables, plus `wardrobe_item_state.attrs`. The recommendations module gains a pure `rules.py`; the wardrobe service wires counts, attributes and runs. Contracts regenerated; pages updated.
