# Outfit recommender readiness (align-wearhouse-outfit-recommender)

Date: 2026-11-26. Closes the ecosystem TDD §12.3 gap: the wardrobe suggester now follows thesis §3.4.3 and Eqs. 7–9, and shares its rule vocabulary with the RQ2 simulation.

## What the suggester does

1. **Attributes.** Each item gets warmth, rain_suitable, long_sleeve, long_bottom and formal from ruleset `wardrobe-rules@1`:
   - the source is the thesis appendix keyword table (P0390), applied to the slot and the item text;
   - the input text is the name, product type, garment group and description for verified items, and the name and category for declared items;
   - each value is labelled origin `rule`. The owner can correct any of them (origin `owner`), and `null` returns it to the rule.
   - `tests/test_outfit_rules.py` checks that the table equals `research/configs/rq2.json`, so the app and the simulation agree.
2. **Hard rules (a–d):**
   - **a. Slots:** top+bottom or dress, plus footwear, plus an optional outer.
   - **b. Heat:** a hot day removes heavy outerwear.
   - **c. Rain:** a rainy day needs rain-suitable footwear or outerwear.
   - **d. Dress codes:** worship needs long sleeves and a long bottom; a wedding needs a formal piece.

   Occasions are casual, campus, hangout, worship and wedding. When the weather is unknown (or turned off in Settings) no weather rule applies, and the explanation says so. The response counts how many candidates each rule removed, and when nothing passes it explains which rule removed everything.
3. **Score (Eq. 7):** `w1·compatibility + w2·mean preference − w3·mean recency`, where:
   - preference (Eq. 8) = `(chosen + 5·0.5)/(recommended + 5)`;
   - recency (Eq. 9) = `exp(−days since worn / 4)`, and 0 when never worn.

   The weights come from Settings: balanced 0.5/0.3/0.2 (the demo baseline), classic 0.4/0.5/0.1, adventurous 0.4/0.2/0.4. Compatibility is still the labelled heuristic baseline. Unknown colours count as 0.5 and say so. No trained model is claimed.
4. **Candidates:** the top 8 items per slot by preference − recency, all combinations of those, an exact rule check, and up to 5 suggestions with distinct cores. Each suggestion carries a plain explanation.
5. **Feedback:**
   - every request creates a private run;
   - `POST /me/recommendations/outfits/{run_id}/events` records `displayed` (one exposure per item per run, however often it is sent) and `chosen` (once per run; a different second choice gets 409 `ALREADY_CHOSEN`);
   - fetching suggestions alone never changes the counts;
   - the pages send `displayed` after showing suggestions and `chosen` when you save one as a look;
   - the feedback is included in the export and erased with the account.

## Evidence

| Check | Result |
|---|---|
| `tests/test_outfit_rules.py` | 7 passed: parity with the RQ2 table, appendix lookup, every hard rule (including unknown weather), preference and recency maths, recently-worn ranks lower, distinct cores, rain explanation when nothing passes, preference lifts a chosen item. |
| `tests/test_wardrobe.py` | 10 passed, including:<br>• **rules end to end:** rain removes everything until the owner marks the shoes rain-suitable (origin `owner`, reset back to `rule`); the heavy coat is excluded on hot days; every worship suggestion satisfies rule d; an unknown occasion gets 422; wearing the chinos yesterday raises recency only for outfits containing them;<br>• **feedback:** duplicate `displayed` events stay one exposure per item; a repeated choice is a no-op; a different choice gets 409; another user gets 404; the next request's chosen items score preference 0.5833 (Eq. 8 with 1 of 1); refetching changes nothing; export. |
| `tests/test_settings_security.py` | Weight profiles: adventurous penalises a recently worn top most, classic least. |
| e2e `wardrobe.spec.ts` | Rain with canvas shoes gives 0 suggestions plus the rain explanation. Worship gives the long-sleeved shirt with trousers, the explanation and the ruleset label, and saving it as a look records the choice. |

## Still not the research model

Compatibility in the app is the colour heuristic. The RQ2 type-aware model trained on Polyvore reaches AUC 0.530 with text embeddings (images not downloaded), which is not good enough to serve. Serving it would need an exported artifact, like the RQ1 path. The weights and h = 4 are demo baselines; the research tunes them on simulated validation users only.
