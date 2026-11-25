## 1. Data model

- [x] 1.1 Write migration `0007_wardrobe_planning` (all D3 tables, CHECK constraints, grants with no UPDATE on `look_revision`) and update `RUNTIME_PRIVILEGES`. Verify upgrade/repeat, empty `compare_metadata`, and the startup privilege check.

## 2. Wardrobe items and shelves

- [x] 2.1 Implement the unified wardrobe list (verified plus declared; effective slot; filters), declared items with an owner-only photo (magic bytes, 2 MB), care states, slot overrides and archive. Verify: a claimed item appears `verified` with its slot, unknown attributes stay explicit, a fake image gives 422, a foreign item gives 404, and the photo is owner-only.
- [x] 2.2 Implement shelves (create, rename, replace items, delete; limits). Verify the foreign item 422, ordering, and the limits.

## 3. Looks

- [x] 3.1 Implement the slot registry endpoint, looks with immutable revisions, ownership/slot/conflict validation, and delete with history kept. Verify: dress plus top `slot_conflict`, `slot_unknown`, 4 accessories rejected, a foreign item, edit-keeps-history, and that the runtime cannot UPDATE `look_revision`.

## 4. Weather

- [x] 4.1 Implement weather ports, the BMKG httpx adapter, the SQL cache, `WeatherService` (fresh cache, live, stale fallback, manual), the `adm4` validation, `/weather/forecast`, and the user location with `/me/weather`. Verify with a fake fetcher: live then cached, a timeout with a 4 h cache giving CACHED, a timeout with a 7 h cache giving MANUAL_REQUIRED, malformed feed fallback, bad `adm4` 422, and no location giving `no_location`.

## 5. Planner and wear

- [x] 5.1 Implement date plans (today to +30, own revision, occasion, note) and the seven-day view with forecast-horizon labels. Verify: past and +31 rejected, a plan keeps revision 1 after an edit, beyond-forecast dates carry no weather values, forecast dates are summarised from slots, and there is no location.
- [x] 5.2 Implement the idempotent wear log (look revision or items, today to −60 days), delete, and per-item wear count and last worn. Verify: a retry does not double count, future dates are rejected, foreign items are rejected, and planned is not counted as worn.

## 6. Suggestions

- [x] 6.1 Implement `OutfitSuggester` (pure) and the `/me/recommendations/outfits` endpoint, with the colour table, components, the model info and the weather source. Verify: missing footwear reason, laundry items excluded, rain prefers outer, recency lowers rotation, unknown colours give null compatibility, and the mode is `heuristic_baseline`.

## 7. Integration, contracts, pages, readiness

- [x] 7.1 Add the export and deletion `wardrobe` sections, regenerate contracts, and update the route allowlist and boundaries. Verify the export has no photo bytes, deletion erases wardrobe data, and the full v2 suite and drift check pass.
- [x] 7.2 Add Wardrobe (shelves and items, care, slot), Add item (with photo), Looks, Planner (seven days: plan, wore it) and Suggestions pages. Verify typecheck, the build guard and an e2e flow: claim → wardrobe → look → plan → wore it → suggestion shown.
- [x] 7.3 Record evidence in `docs/architecture/wardrobe-readiness.md` and update the API README.
