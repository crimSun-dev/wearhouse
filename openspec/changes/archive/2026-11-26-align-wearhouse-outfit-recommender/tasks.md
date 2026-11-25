## 1. Rules and ranking

- [x] 1.1 Add the pure `recommendations/rules.py` (ruleset `wardrobe-rules@1`, attribute derivation, hard rules, occasions) and rewrite `OutfitSuggester` for Eqs. 7–9 with per-slot top-M, distinct cores and rule accounting. Verify with unit tests: each rule, the preference and recency maths, ordering, distinct cores, and parity with `research/configs/rq2.json`.

## 2. Runs, events, attributes

- [x] 2.1 Write migration `0014`: runs, exposures, choices and item attribute overrides. Wire the suggestions service (counts, attributes, occasion, settings weights, run creation), the events endpoint and attribute corrections. Verify: displayed and chosen deduplication, 409 on a different choice, owner-only runs, preference and recency end to end, owner corrections, and the weather-off behaviour.

## 3. Pages and readiness

- [x] 3.1 Add the occasion picker, displayed/chosen events and rule explanations on the suggestions page, and attribute corrections on the wardrobe page. Regenerate contracts; run e2e, the full suite and the readiness notes.
