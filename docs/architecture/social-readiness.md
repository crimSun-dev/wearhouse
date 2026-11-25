# Social services readiness (add-wearhouse-social-profile-services)

Recorded on 2026-11-25 against the disposable local PostgreSQL 18 cluster.

**Policy.**
- Visibility is never stored. Every read applies the accounts `can_view` policy, with the owner's `wardrobe` privacy as a ceiling (design D1), so unfriending, blocking or tightening privacy applies on the next read.
- Notifications are derived from source records (D3); only a read marker is stored.
- Projections come from the wardrobe application layer and carry only slot, name, category, colour, verified, and a store link for published products.
- Wardrobe privacy defaults to `private`. That caps every share until the owner opens it, and the owner's share view reports `effective_audience` so the pages can say so.

## Gates

| Gate | Command | Observed |
|---|---|---|
| Migration 0008, `compare_metadata`, privileges | `pytest tests/test_migrations.py` | passed |
| Projection: no serial, wardrobe item id, care or wear; store link only while the product is published | `test_share_projection_is_safe_and_links_published_products` | passed |
| Reversals: stranger and anonymous 404; unfriend 404, re-friend 200; block by the viewer 404; public share; privacy ceiling 404; owner always sees; revoked 404 | `test_visibility_reversals` | passed |
| Pinned revision, re-pin, owner-only patch, foreign look 422, `effective_audience`, `SHARES_FULL` | `test_share_management_repin_and_limits` | passed |
| Profile shares filtered per viewer; deleted owner gives 404 | `test_profile_shares_and_deleted_owner` | passed |
| Week: default `none` 404; friend sees 7 days with no wear, weather or serial; stranger, anonymous and private wardrobe 404 | `test_week_plan_sharing` | passed |
| Feed: newest first, paging without repeats, tampered and foreign cursor 422, block empties it | `test_feed_newest_first_paging_and_block` | passed |
| Notifications: request, accepted, friend share; mark read gives 0, a newer share gives 1; block removes | `test_derived_notifications_and_read_marker` | passed |
| Showcase: `unknown_share`, bad accent, anonymous sees only public featured shares, profile privacy 404, revoked share rejected | `test_showcase_rules_and_visibility` | passed |
| Inspiration never grants items (owned, units, credentials, wishlist and cart unchanged); export section; deletion erases shares, settings and showcase | `test_inspiration_never_grants_items_and_account_integration` | passed |
| Full v2 suite, routes, boundaries, contracts | `pytest -q` in `apps/api`; `python tools/contracts.py check` | 539 passed, 1 skipped (the source-backed H&M proof); "contracts up to date" |
| Pages: typecheck, unit tests, guarded build; e2e flow with two users: friend request → accept → privacy → declare → look → share → friend's feed, badge and notification → mark read → unfriend → gone | `npm run typecheck`, `npm test`, `npm run build`, `npx playwright test` | clean; 7 passed; "build guard OK"; 10 e2e passed (all flows) |

## Fixed along the way

- **Stale renders in the temporary pages.** A slow render for a route the user had already left could overwrite the next page. Routes now run one at a time, and `view()` skips a render whose hash is no longer current.
- **Empty selects.** `ui.select` no longer produces an empty select when the default value is not an option. This was why the share audience had been sent blank.
- **`INSERT … ON CONFLICT DO NOTHING` returns `rowcount = -1` here.** Shelf creation and the wishlist add now detect success with `RETURNING`.
