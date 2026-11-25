# Wearhouse dependency roadmap

Only `rearchitect-wearhouse-foundation` is proposed as an actual OpenSpec change here. The names below reserve future scopes; they are not existing changes or completed implementation plans. This roadmap applies the user's architecture-first/fresh-frontend instruction over the old incremental extraction sequence.

## Dependency order and gates

```text
Foundation → persisted ecosystem services → fresh frontend → hardening/cutover
           ↘ research intelligence ────────────────────────↗
```

Research jobs can progress after foundation independently of UI work; model-serving integration and truthful mode labels are required before their relevant release. Fresh frontend implementation cannot start before foundation readiness. It may be developed against completed, versioned subsets of service contracts, but its release requires all promised persisted behaviours. No screen is called functional based on fake successful handlers.

| Change | Prerequisites | Scope and explicit exit criteria |
|---|---|---|
| `rearchitect-wearhouse-foundation` | Reviewed planning artifacts; fixture/provider evidence tasks tracked | This proposal's five capabilities: canonical Python architecture, legacy separation, migrations/contracts, authenticated one-time ownership, relocated build/tests. GROWN-001/002 and source-backed thread pass before frontend work; no visual rebuild here |
| `add-wearhouse-accounts` | Foundation identity/ownership contracts | Neon Auth (Google) broker tokens; handles/profiles; per-section privacy; friend requests/friendships/blocks; sign out everywhere, export, deletion tombstone; temporary account pages. Exit: accounts readiness matrix incl. real Google sign-in on the dev Auth branch; no styled UI |
| `implement-wearhouse-ecosystem-services` | Foundation complete | Catalogue staging/import/review/publish/retire, media jobs, mock commerce/wishlist, buyer receipt envelopes, wardrobe/slots/looks/manual add, planner/wear, social/profile/sharing/notifications; all persisted with roles/privacy/transaction tests. Recommendation APIs initially declare actual heuristic mode where trained artifacts are unavailable |
| `rebuild-wearhouse-frontend` | Foundation readiness plus stable versioned service contracts | Entirely new Vite/TypeScript/Three.js presentation, customer shell and separate admin workspace, real object imagery, inspector, avatar, Focus mode, seven-day profile/planner and all flow states. Exit: integration, responsive/keyboard/accessibility, visual and asset-coverage checks; no copy/reskin of old renderer |
| `complete-wearhouse-research-intelligence` | Foundation artifact/feature contracts; legitimate acquired datasets | Frozen FashionCLIP features, type-aware projection/masks, BPR/content retrieval, completion/duplicate catalogue ranking, context/preference/rotation outfit strategy. Exit: reproducible RQ1–RQ4 reports/baselines, source/split/model hashes, declared modes and failures/trade-offs; no test-set tuning |
| `harden-and-cutover-wearhouse` | Complete services/UI/model integration and required audience rights | Full-scale latency, actual devices/avatar FPS, performance/accessibility, redaction/security, backup restore, reconciled migration and release runbook. Exit: measured acceptance matrix and staged v1-write freeze/v2 rollout with post-write rollback boundary |

## Services subchanges

The services umbrella must be split before apply into reviewable proposals in this order; each requires its own delta specs/design/tasks and real validation:

1. **`publish-wearhouse-catalogue`** — foundation source records → durable import jobs, provenance/rights, attribute mappings, media/embedding status, review/publish/retire, indexed browse/detail. Gate: editor publishes legitimate source-derived products; retired products remain in owned history; restricted images stay restricted.
2. **`add-wearhouse-sandbox-commerce`** — catalogue → wishlist/cart/mock offers/orders/cancellation/buyer delivery. Gate: repeated/concurrent checkout produces one order and one unit per quantity; receipt is buyer-only; redemption creates ownership separately; cancelled claimed sandbox state is handled explicitly.
3. **`build-wearhouse-wardrobe-planning-services`** — owned items → manual add/media, care states/collections, typed slot registry, saved look revisions, planner and actual wear, initial weather/recommendation APIs. Gate: ownership checks on every referenced item, dress/multi-slot conflicts, idempotent wear and forecast horizon labels pass.
4. **`add-wearhouse-social-profile-services`** — builds on `add-wearhouse-accounts` (which now owns handles, profiles, privacy, friend requests/friendships and blocks) → look/plan share projections, timeline, profile customisation beyond the basics, and notifications. Gate: sharing honours the accounts privacy/block policy; friends/blocks/visibility reversal invalidate shared access; no serial/key/location/private-wear leak; inspiration never grants items.

Service UI contracts are part of these proposals; new UI design does not get to silently invent incompatible persistence/ownership semantics.

## TDD requirement coverage

| Requirement | Owning changes | Observable acceptance gate |
|---|---|---|
| F01 existing catalogue | Foundation source identity; publish catalogue; research | Preserved source IDs/provenance, real acquired source snapshot, no fabricated retail products |
| F02 shared intelligence | Foundation ports; wardrobe services; research | Shared versioned compatibility/features; distinct purchase/outfit rankers; truthful model modes |
| F03 product/unit/item objects | Foundation; commerce; fresh frontend | Two same-product units have separate lifecycle; owned tiles/inspector link real records |
| F04 dedicated redemption | Foundation private claim; fresh frontend | Public QR discovery-only; separate Redeem page with one-time private key flow |
| F05 visual wardrobe/avatar | Wardrobe services; fresh frontend; research RQ4 | Actual permitted product imagery, category assets/accessory slots, texture/2D fallback and occupancy/FPS evidence |
| F06 seven-day timeline | Wardrobe/social services; fresh frontend | Seven local dates backed by plan records, planned≠worn, explicit privacy and beyond-forecast states |
| F07 mock purchasing/wishlist | Commerce; fresh frontend | Durable wishlist/cart/order/receipt/key; no real payments/stock claims; retries preserve effects |
| F08 friends/profile | `add-wearhouse-accounts` (invite/accept/remove/block, profile + private projection); social services (shared look, notifications); fresh frontend | Invite/accept/remove/block works across accounts with private projection enforced (accounts); shared look works across accounts (social services) |
| F09 admin publication | Foundation permissions; publish catalogue; fresh admin UI | Import/review/publish/retire and issue unit without code edits; role-scoped audited actions |
| F10 reference-led UI | Fresh frontend | Global Catalogue/Wardrobe/Community/Profile, contextual menus, portrait shelves, focused rectangle/Big Picture view and feminine Wearhouse palette |
| F11 functional ecosystem | All changes; hardening | Admin publishes → customer discovers/wishlists/mock-buys/redeems/equips/plans/wears/shares; state survives restart and account isolation holds |
| F12 context/rotation | Foundation weather contracts; wardrobe services; research | Rain/heat/occasion rules, preference/recency and source attribution/fallback tested; no fabricated seven-day forecast |
| F13 manual/thrifted clothes | Wardrobe services; fresh frontend | Private uploaded photo/category creates declared item with unknown attributes explicit, without fabricated verification serial |

## Research obligations

- **RQ1:** acquire legitimate H&M snapshot, chronological train/validation/test and age-cohort policy; popularity/item-neighbour/BPR/first-stage baselines; MAP/Recall/NDCG@12, duplicate trade-off and paired bootstrap. Treat bracketed settings as settings to freeze. Sandbox behaviour is not a replacement for purchase test labels.
- **RQ2:** Polyvore chosen non-disjoint benchmark plus explicit item-overlap audit to resolve the thesis's unseen-item statement; type-aware/shared-space AUC/FITB, H&M transfer pairs and seeded wardrobe/month/season/behaviour simulations. Tune only validation group; report coverage/compatibility and paired statistics by behaviour/season. Same candidate-budget methodology across comparisons.
- **RQ3:** source-derived test products with generated keys/serials, genuine placement, public/altered/guessed/reused rejection, multi-user races and independent admission-limit tests. Large attack corpus tests validation separately so a rate limiter cannot mask validation failures. Foundation proves its subset; it does not claim full experiment completion.
- **RQ4:** all types/templates/textures/accessories and multi-slot occupancy; 60-second measurements on named laptop/phone with ≥30 median FPS target or explicitly measured 2D fallback. New UI tiles alone are not evidence for avatar completeness.

## Reference and brand handoff

Use `Reference/Screenshot 2026-11-25 122759.png` and `122849.png` for Store hierarchy/menu; `122914.png` for Library category navigation and portrait shelves; `122951.png` for Big Picture's dominant selection and quiet detail area. All were visually inspected in the preceding review; they define organisation, not permission to copy game imagery or trademarks.

Use `Assets/208131bb-60d2-479d-8546-16acbd429bd1.png` as emblem and `Assets/03b20ba8-8da5-4430-a532-394cd61085c8.png` as horizontal lockup. `Assets/Plum House Ribbon Logo.png` is the ivory/blush brand board, not a whole-navbar image. Preserve originals; prepare semantic production names and favicon sizes only in the frontend change; inspect padding/transparency/contrast and use a light brand surface where plum is illegible. No replacement logo generation or tracing is required.

The frontend proposal must specify semantic responsive routes/components, token system, scoped search/menus, generated client, server/query state, private-cache sign-out handling, keyboard/touch focus navigation, loading/empty/error/permission states and avatar resource cleanup. Customer diagnostics/reset controls are excluded; admin is its own role-scoped workspace. Mock checkout must not look like a real payment request.

## Outstanding prerequisites

External Understanding Pool path remains unsupplied; current source-backed decisions are project proposals, not a completed pool audit. Dataset/image/model terms, provider session/host compatibility, unknown attribute mapping, split leakage and UV/template quality each have a concrete owning gate above. Revisit affected planning if new evidence changes a contract; do not silently waive requirements or report targets as measurements.
