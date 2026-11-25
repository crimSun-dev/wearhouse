# Wardrobe planning readiness (build-wearhouse-wardrobe-planning-services)

Recorded on 2026-11-25 against the disposable local PostgreSQL 18 cluster.

**Data honesty.**
- Products are the data-free synthetic fixture (`synthetic_only`).
- Weather in the tests comes from a fake fetcher, so no test calls BMKG. The real `BmkgFetcher` is wired for runtime: `https://api.bmkg.go.id/publik/prakiraan-cuaca?adm4=`, 3 s budget.
- Suggestions are the declared heuristic baseline (`heuristic_baseline`); no trained model is claimed.
- Colour hex values come only from the documented table in `wardrobe/colours.py`.

## Gates

| Gate | Command | Observed |
|---|---|---|
| Migration 0007 (11 tables, grants with no UPDATE on `look_revision`), `compare_metadata`, privileges | `pytest tests/test_migrations.py` | passed |
| Verified items carry the catalogue slot; override and care; filters; foreign item 404; verified items cannot be archived | `test_claimed_items_are_verified_with_catalogue_slot` | passed |
| Declared items: no serial, unknown colour explicit; fake image 422; over 2 MB 422; owner-only photo; archive | `test_declared_items_keep_unknowns_and_private_photos` | passed |
| Shelves: order, foreign item 422, name clash 409, rename/replace, owner-only | `test_shelves_order_foreign_items_and_names` | passed |
| Looks: `slot_conflict`, `slot_unknown`, `slot_mismatch`, `over_capacity`, `unknown_item`; edit keeps the plan on revision 1; history survives delete; the runtime role gets `permission denied` on `UPDATE look_revision` | `test_look_rules_history_and_immutability` | passed |
| Weather: LIVE, then a cache hit with no refetch; timeout with a 4 h cache gives CACHED; 7 h gives MANUAL_REQUIRED; a malformed feed is rejected; bad `adm4` 422; signed-in only; `no_location` | `test_weather_gateway_live_cache_and_fallbacks` | passed |
| Planner: past and +31 rejected; foreign revision rejected; 7 days; `beyond_forecast` days carry no values; forecast days summarised from real slots; planned is not worn | `test_planner_window_and_forecast_labels` | passed |
| Wear: idempotent retry (one entry, `Idempotent-Replayed`); future, foreign and neither-field requests rejected; counts and last worn; delete | `test_wear_log_idempotent_and_counted` | passed |
| Suggestions: heuristic mode, slot rules, unknown weather gives null, rain prefers outer, recency lowers rotation, a laundry item gives `missing_slot: footwear`, unknown colour gives null compatibility | `test_suggestions_rules_weather_rotation_and_mode` | passed |
| Export has no photo bytes (sha256 only); deletion erases all wardrobe tables and the weather location | `test_export_has_no_photo_bytes_and_deletion_erases_wardrobe` | passed |
| Route allowlist, boundaries (`weather`/`recommendations` adapters and api exempt; the rest stays pure), contracts | `pytest tests/test_app_factory.py tests/test_boundaries.py`; `python tools/contracts.py check` | passed; "contracts up to date" |
| Full v2 suite | `pytest -q` in `apps/api` | 514 passed, 1 skipped (the source-backed H&M proof, still pending its permitted fixture) |
| Pages: typecheck, unit tests, guarded build; e2e flow: declare (with photo) → wardrobe → look → plan → "I wore this" → suggestions | `npm run typecheck`, `npm test`, `npm run build`, `npx playwright test` | clean; 7 passed; "build guard OK"; 9 e2e passed |

## Known limits

- Occasion is stored on plans but not used for ranking, because no formality data exists. Suggestions report `occasion_used: false`.
- Photos are stored in PostgreSQL (bytea, 2 MB, owner-only). Object storage can replace this later behind the same routes.
