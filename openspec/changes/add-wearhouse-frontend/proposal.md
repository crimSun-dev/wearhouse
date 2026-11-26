## Why

The Wearhouse v2 backend is complete. `docs/architecture/tdd-status.md` reports all 145 operations implemented and tested, but there is no product frontend. Two ecosystem TDD requirements, F05 (visual wardrobe and avatar) and F10 (Steam-inspired interface), and all of Phase 3 are still open. People can only reach the system through the temporary, functional-only `apps/web/account-pages`. The definition of complete (TDD §17) needs a customer to discover, buy (simulated), redeem, dress, plan, wear and share, and staff to curate, in an interface that is visually coherent on desktop and mobile. That interface does not exist yet.

The full brief is `docs/WEARHOUSE_FRONTEND_PROMPT.md` (§1–§11), and the product record is `PRODUCT.md`. This change turns them into a buildable contract.

## What Changes

- **New web package `apps/web/client`** (Vite + TypeScript), a multi-page build:
  - the landing page at `/`;
  - the app at `/app/` with hash routes.

  It imports API types only from `@wearhouse/contracts` and shares no code with `legacy/`.
- **Big Picture shell.**
  - Two presentations of the same routes: Desktop (Steam client) and Focus mode (Big Picture).
  - A spatial focus engine for keyboard, pointer and touch (no gamepad: owner decision, 2026-11-26).
  - Main menu and Quick access overlays, a contextual button-hint bar, and the top-right cluster (search, notifications, feed, clock, account).
  - Optional synthesised UI sounds.
  - English and Indonesian.
  - Theme, motion and language come from the synced account settings.
- **Customer surfaces covering every customer-facing v2 operation:**
  - catalogue browse, search, product, collections and the public tag lookup with a QR scanner;
  - wishlist, cart, simulated checkout, orders and receipts with key reveal, renew and cancel;
  - redemption;
  - wardrobe library, item inspector, declared items with photos, shelves, looks with revisions;
  - fitting room with a 3D avatar and a disclosed 2D fallback;
  - outfit suggestions with display and choice events;
  - seven-day planner, wear log, weather and location, usual sizes;
  - feed, friends, requests, blocks, inspirations, shares and reports, notifications, profiles, showcase and plan sharing;
  - settings, privacy, security (broker password and session flows), export, account deletion, About.
- **Staff workspace**, gated by capability: catalogue imports and review, publish and retire, media, sizes, collections, offers, orders, units and one-time key delivery, moderation, staff roles, and ops.
- **Motion system.** The focus/selection effect, state matrices for every control, shared-element transitions, scroll-driven reveals, six signature moments, and a reduced-motion variant for each.
- **Scroll-driven landing page** built with Scrollcraft from the saved brief (`apps/web/client/scrollcraft/builds/wearhouse/BRIEF.md`). It uses only public live data.
- **Quality gates.**
  - An endpoint coverage check in CI (every OpenAPI operation is used or allowlisted with a reason).
  - Vitest unit tests and two-user Playwright end-to-end tests against the v2 test harness.
  - Visual regression at 360, 390, 768, 1440 and 1920 px.
  - axe checks.
  - Performance budgets.
  - An avatar FPS evidence record (RQ4).
- **No backend change.** `apps/api`, `packages/contracts`, migrations and API tests are untouched. API gaps are recorded, not worked around.
- `apps/web/account-pages` stays in place until parity is demonstrated. Retiring it is a separate follow-up.

## Capabilities

### New Capabilities
- `web-client-contract`: the identity session, the single API client (errors, idempotency, retries, cancellation), private-data caching, secret handling, honest labelling, and the endpoint coverage gate.
- `web-shell`: the app shell, Desktop and Focus presentations, the spatial navigation model, overlays, the hint bar, settings-driven theme, language, motion and sound, and responsive navigation.
- `web-motion`: the motion system, the selection effect, control state animation, transitions, in-app scroll animation, signature moments, and reduced-motion behaviour.
- `web-catalogue-commerce`: catalogue discovery, public tag lookup, wishlist, cart, simulated checkout, orders and receipts, key reveal, renewal and cancellation, and redemption.
- `web-wardrobe`: the wardrobe library, inspector, declared items, shelves, looks, fitting room, outfit suggestions, planner, wear log, weather and location, and usual sizes.
- `web-avatar`: the 3D avatar, slot templates and attachment points, colour approximation, the 2D fallback, and FPS evidence.
- `web-community-profile`: the feed, friends, requests, blocks, inspirations, shares, reports, notifications, profiles, showcase and plan sharing.
- `web-account`: settings rendered from the server schema, privacy, the security overview, export, account deletion and About.
- `web-staff-workspace`: the capability-gated staff workspace for catalogue, media, sizes, collections, offers, orders, inventory, moderation, roles and ops.
- `web-landing`: the public scroll-driven landing page and its live-data and honesty constraints.
- `web-quality`: accessibility, responsive layouts, performance budgets, visual regression and end-to-end acceptance for the frontend.

### Modified Capabilities
- `account-security`: the "Passwords stay with the identity broker" requirement names the Wearhouse web app as the client that provides the password, verification and session flows. Until then it says "the pages", meaning the temporary account pages. The behaviour is unchanged.

The other existing capabilities (catalogue-browse, sandbox-orders, private-redemption, outfit-planner, look-sharing, …) describe API behaviour, and this change does not alter them. The frontend specs above reference them instead of re-stating them.

## Impact

- **New:** `apps/web/client/**`. This includes the package, the e2e harness copy/launcher, the coverage script and the scrollcraft workspace. `.scrollcraft.json` and `.impeccable/config.json` already exist at the repo root.
- **Updated:**
  - `.github/workflows/ci.yml`: a new `web` job; existing jobs are untouched.
  - `.gitignore`: generated landing assets and screenshot output.
  - `PRODUCT.md`: one sentence for the signed-out and empty-wardrobe Home.
  - `DESIGN.md`: new, written by Impeccable.
  - `apps/web/README.md`.
  - `docs/architecture/tdd-status.md` (F05, F10, Phase 3), with evidence only.
  - `docs/architecture/release-evidence-avatar.md`: new.
- **Dependencies (pinned):**
  - React 19, React Router (hash router), TanStack Query, Motion and Three.js;
  - `@neon/auth` 0.8.2, Vite 7.3.8 and TypeScript 5.9.3;
  - Vitest, `@playwright/test` 1.65.1 and axe-core;
  - a small QR encoder.
- **Runtime:**
  - the browser talks only to the v2 API (`VITE_WEARHOUSE_API_BASE`) and Neon Auth (`VITE_NEON_AUTH_URL`);
  - the dev origin `http://127.0.0.1:5174` is already in `WEARHOUSE_ALLOWED_ORIGINS`;
  - no deployment or cutover in this change (hosting is still an owner decision).
- **Not affected:** `legacy/` (the v1 demo and its Pages site), research pipelines, API behaviour.
