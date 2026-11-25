## Context

Existing pieces this change builds on:
- **Ownership:** `owned_item` rows, one per claimed unit, each with a presentation snapshot and its acquisition revision.
- **Catalogue:** publishes facts plus a rule slot annotation.
- **Foundation contracts:** a pure BMKG contract (`weather/contract.py`: validation, LIVE → CACHED → MANUAL fallback) and a labelled heuristic baseline (`recommendations/baseline.py`).
- **Legacy:** already called the real BMKG endpoint `https://api.bmkg.go.id/publik/prakiraan-cuaca?adm4=` with a 3 s deadline.

## Goals / Non-Goals

**Goals:**
- a private wardrobe covering verified and declared items, enforcing ownership, care state and slot rules everywhere;
- immutable look history;
- a truthful seven-day planner;
- an idempotent wear log;
- a real, cached weather gateway;
- honest heuristic suggestions.

**Non-Goals:**
- trained models or FashionCLIP (the research change);
- avatar rendering (the frontend rebuild);
- sharing looks with friends (the social change);
- image processing beyond type and size checks.

## Decisions

### D1: Module layout

- **`wardrobe` (new).** Items, care, shelves, looks, planner and wear: domain, ports, application, adapters and api.
- **`weather`.** Gains `ports.py` (`ForecastFetcher`, `ForecastCache`), `application.py` (`WeatherService`, which applies `FallbackPolicy`), `adapters/bmkg.py` (sync httpx, 3 s total deadline), `adapters/sql.py` and `api.py`.
- **`recommendations`.** Gains `application.py` with `OutfitSuggester`. It is pure: candidate enumeration, weather and rotation components, and the heuristic compatibility.

The boundary test exempts only `adapters/` and `api.py` inside `weather` and `recommendations` from the framework-free rule; their contract, ports and application stay pure.

### D2: Item identity and state

- A verified item's id is its `owned_item.id`; a declared item's id is its `wardrobe_declared_item.id`. Both are UUIDs, and ownership is checked against both tables with `user_id = caller`.
- Per-item mutable state (care state and slot override) lives in `wardrobe_item_state (user_id, item_id)`. A missing row means `ready` with no override.
- A verified item's catalogue slot comes from the acquisition revision's annotations, read through a new `RevisionReader.annotations_for(revision_ids)`.

### D3: Tables (migration `0007_wardrobe_planning`)

| Table | Notes |
|---|---|
| `wardrobe_declared_item` | id, user, name, slot, category?, colour?, photo bytea?, photo_type?, photo_sha256?, archived_at?, created_at |
| `wardrobe_item_state` | (user, item) PK, care_state CHECK, slot_override CHECK, updated_at |
| `wardrobe_shelf` | (user, name) unique; `wardrobe_shelf_item` (shelf, item) PK, position |
| `look` | id, user, name, current_revision_id, deleted_at; `look_revision` (look, revision_no) unique, slots JSONB. The runtime has no UPDATE grant on `look_revision` |
| `plan_entry` | (user, plan_date) PK, look_revision_id, occasion CHECK, note |
| `wear_entry` | id, user, worn_on, look_revision_id?; `wear_entry_item` (wear, item) PK |
| `weather_cache` | adm4 PK, slots JSONB, fetched_at, fresh_until |
| `user_weather_location` | user PK, adm4 CHECK, updated_at |

### D4: Slot registry

`SLOTS = {top: 1, outer: 1, bottom: 1, dress: 1, footwear: 1, accessory: 3}`, with exclusions `dress ⟂ top` and `dress ⟂ bottom`. The registry is served at `GET /wardrobe/slots`.

### D5: Forecast horizon

The horizon is the contract's `MAX_AHEAD` (3 days). A planner date gets weather only when the cache or a fetch has slots on that local date. Dates past today + 3 are `beyond_forecast`; dates with no data are `unavailable`, with the reason.

### D6: Suggestions scoring (heuristic baseline, declared)

Components, each in [0, 1] or `null`:
- **compatibility:** `HeuristicCompatibility.score`. Colour hex values come from a documented H&M colour-group table (`wardrobe/colours.py`, for example Black → `#000000`); unknown names stay `null`. Style is unknown, so it is `null`.
- **weather:**
  - rain: with an outer 1.0, without 0.5;
  - heat: with an outer 0.4, without 1.0;
  - neither: 1.0;
  - weather unknown: `null`.
- **rotation:** `1 − 0.6 × (items worn in the last 7 days / outfit size)`.

The total is the weighted mean (0.5, 0.3, 0.2) over the known components. Enumeration is deterministic (ordered by item id) and capped at 2000 combinations. The occasion is accepted but not used, because no formality data exists, and the result says `occasion_used: false`.

### D7: Wear idempotency

`POST /me/wear` runs under `IdempotentExecutor`. The fingerprint is the date, the look revision and the sorted item ids.

### D8: Testing weather without the network

`Services.weather.fetcher` is an attribute that tests replace with a fake fetcher. They do so for success, timeout, HTTP 500 and malformed feeds. No test calls BMKG.

## Risks / Trade-offs

- **[Photos in PostgreSQL bytea.]** Photos are at most 2 MB each, 1000 declared items per user, owner-only. This is simple and transactional; object storage can replace it later behind the same route.
- **[Synchronous BMKG fetch inside a request.]** There is a 3 s deadline, and the cache keeps calls rare. The fallback is never worse than `MANUAL_REQUIRED`.
- **[Heuristic suggestions are basic.]** They are labelled `heuristic_baseline`; research models replace the ranker behind the same port.

## Migration Plan

Run `0007` (additive), then deploy. The account export and deletion gain a `wardrobe` section through the injected sections from commerce D7.
