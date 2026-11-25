## Why

Customers can now buy and claim garments, but they cannot use them. The wardrobe is the "Library" of the Steam-like product: shelves of owned items, looks built from them, a seven-day plan, a wear log and weather-aware suggestions. This change also covers clothes bought elsewhere (thrifted or gifted), declared by the user without a fake verification serial. It is roadmap services step 3 (`build-wearhouse-wardrobe-planning-services`, F05/F06/F12/F13 service side).

## What Changes

- **Wardrobe items.** One private list combines:
  - claimed (verified) items;
  - manually declared items: name, slot, category, optional colour and an optional private photo, with every unknown attribute left explicitly unknown and no serial.

  Users can set a slot override when the catalogue slot is unknown, set a care state (`ready`, `laundry`, `repair`, `stored`), and archive declared items.
- **Shelves.** These are named, ordered collections of the user's own items, like Steam library shelves: up to 50 shelves of up to 500 items each.
- **Typed slot registry.** The slots are `top`, `outer`, `bottom`, `dress`, `footwear` and `accessory`, with occupancy rules. A `dress` excludes `top` and `bottom`; up to 3 accessories; every other slot takes at most one item.
- **Saved looks with immutable revisions.** A look maps slots to the user's own items. Every edit creates a new revision; past revisions stay readable and plans keep pointing at theirs. Ownership, care and slot conflicts are checked on every save.
- **Planner.** Each local date (Asia/Jakarta) can hold one planned look revision plus an occasion and a note, from today up to 30 days ahead. The seven-day view labels each date `forecast` (inside the BMKG horizon) or `beyond_forecast`, and never invents weather.
- **Actual wear.** The user logs what they actually wore on a past or current date. It is idempotent, it is separate from the plan (planned is not the same as worn), and it feeds the rotation.
- **Weather.** A BMKG gateway adapter persists a cache and applies the existing LIVE, then CACHED, then MANUAL_REQUIRED contract. Each user can set a BMKG `adm4` location, and the forecast endpoint reports its source and fetch time.
- **Outfit suggestions.** For a date, the service builds valid slot combinations from `ready` items. It ranks them with the labelled heuristic baseline (colour and style), weather rules (rain and heat) and a recency rotation penalty. It returns the model mode, the score components and the weather source. It never claims a trained model.
- **Temporary pages.** The temporary web app gains plain Wardrobe (shelves and items), Add item, Looks, Planner (seven-day) and Suggestions pages.

## Capabilities

### New Capabilities
- `wardrobe-items`: the unified private wardrobe, manual items with private photos, care states, slot overrides and shelves.
- `saved-looks`: the slot registry, looks and immutable revisions.
- `outfit-planner`: date plans, the seven-day view with forecast-horizon labels, and the actual wear log.
- `weather-forecast`: the BMKG gateway with a persisted cache, fallback and user location.
- `outfit-recommendations`: heuristic, weather and rotation suggestions with truthful model mode.

### Modified Capabilities
None archived. This builds on ownership (owned items), the catalogue (published facts and slot annotations), and the foundation weather and recommendation contracts.

## Impact

- **API.**
  - New `wardrobe` module.
  - The `weather` and `recommendations` modules gain an application layer and adapters. The boundary rule is updated so that only their `adapters` and `api` files may use frameworks.
  - Migration `0007_wardrobe_planning`.
  - New routes under `/api/v2/me/wardrobe|looks|planner|wear|weather|recommendations` and `/api/v2/weather`.
  - Account export and deletion include the wardrobe data; contracts are regenerated.
- **Pages.** `apps/web/account-pages` gains the wardrobe pages.
- **Unchanged.** Legacy v1.
