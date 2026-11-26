## Context

See proposal.md for the motivation. The full brief is `docs/WEARHOUSE_FRONTEND_PROMPT.md`, which this design follows and does not repeat.

Observed state that shapes the approach:

- **The v2 API is fixed.** It has 145 operations in `packages/contracts/openapi-v2.json`, and generated types are in `packages/contracts/src/schema.d.ts` and `error-codes.d.ts`. Errors are `{code, message, field_errors?, request_id}`. CORS exposes `X-Request-ID`, `Retry-After` and `Idempotent-Replayed`. The allowed dev origins include `http://127.0.0.1:5174`.
- **Media URLs are origin-relative** (`/api/v2/media/{id}`) or source references. Declared-item photos (`/me/wardrobe/items/{id}/photo`) need a bearer token, so they cannot be loaded directly as an `<img src>`.
- **`apps/web/account-pages` is working reference code**, not legacy. It has a tested Neon Auth port (`src/auth/{port,neon,fake,provider}.ts`), an API client (`src/api.ts`) and an e2e harness. The harness (`e2e/harness.py`) runs the real API from the test factory against a disposable Postgres, with a local EdDSA issuer, `GET /__e2e/token?sub=` and `POST /__e2e/grant?sub=&role=` (roles `catalogue_editor` or `admin`).
- **Two occasion vocabularies exist.** Suggestions use the registry `occasions`; planner entries use `casual|work|formal|sport|event`.
- **Planning context already exists:**
  - `PRODUCT.md` (daily dressing is primary);
  - `.impeccable/config.json` (`buildPath: comp`);
  - `.scrollcraft.json` (workspace `apps/web/client/scrollcraft`), with the brief at `builds/wearhouse/BRIEF.md`.
- **The repo's home drive is exFAT** and Codex's sandbox cannot use it. Implementation happens in the NTFS working copy `C:\dev\wearhouse`. Paths in the repo may contain spaces, so scripts must spawn processes without shell strings.

## Goals / Non-Goals

**Goals:**
- One package that a coding agent can build task by task, each task with its own verification.
- Every screen backed by real endpoints, with no client-side invention of server facts.
- Big Picture interaction quality: the focus/selection effect, spatial navigation and motion that hold 60 fps on a mid-range laptop.
- A visual direction chosen by Impeccable within the fixed brand, not prescribed here.

**Non-Goals:**
- Deployment, hosting choice, cutover from v1, and retiring `account-pages` (all follow-ups).
- Any API, contract, migration or research change.
- Server-side rendering, PWA/offline mode, push notifications, chat, real payments.
- Custom per-SKU 3D models, cloth simulation and fit accuracy (TDD §11).

## Decisions

### D1: One multi-page Vite package, with hash routes inside the app
`apps/web/client` builds `index.html` (landing) and `app/index.html` (app). Inside the app, hash routes (`createHashRouter`) mean static hosting needs no fallback rules (TDD §4). `VITE_BASE` sets the base path for a future Pages host.

*Alternatives:* separate packages for the landing page and the app would duplicate tokens and deploys. History routing needs host rewrites that are not decided yet.

### D2: React 19 + TanStack Query + React Router + Motion
About 60 routes with shared focus state, overlays and shared-element transitions benefit from components and a mature animation library. The plain-TS temporary pages showed how much manual DOM work this would otherwise take.

- **TanStack Query** owns server state. Query keys start with the user id, and sign-out calls `queryClient.clear()`. Mutations invalidate the affected keys instead of patching the cache by hand. Optimistic updates are used only for wishlist, settings toggles and notification read, each with rollback.
- **Motion** handles springs, `layoutId` shared elements and gestures. The View Transitions API is used for route changes where it is supported.

*Alternatives:* vanilla TS (too costly at this scope), Svelte or Solid (less library depth for 3D and animation), Redux (unnecessary next to Query).

### D3: Reuse the auth port, rewrite the client
The auth port files are copied into `src/auth/` and keep their unit tests, because they already encode Neon's token quirk (the JWT is in `getSession().data.session.token`). The API client is rewritten against the same rules, with these additions:
- typed operations generated from `schema.d.ts` paths;
- an `AbortSignal` on every call;
- a client timeout;
- `Retry-After` parsing;
- `request_id` capture;
- binary helpers (raw photo upload, authenticated blob fetch, export download).

Idempotency keys are created per *intent* (one per user action) and reused on retries of that intent.

### D4: The focus engine is DOM-first
Focusable tiles and controls are real `<a>`/`<button>` elements that register with a focus engine.

- Rails and grids are "zones" with a roving `tabindex`.
- Arrow keys move within a zone and between neighbouring zones. Each zone remembers its last index.
- Enter/Escape, `[`/`]` (tabs), `/` (search), `M` (Main menu) and `Q` (Quick access) map to app-wide intents. Gamepad input is out of scope (owner decision, 2026-11-26).
- The engine publishes the focused object's descriptor (title, meta, image, accent, actions). The backdrop, detail zone and hint bar subscribe to it, which is how the "selection drives the page" behaviour works.

*Alternatives:* a canvas UI (forbidden: TDD §5.3), or relying on Tab alone (no spatial navigation).

### D5: Presentations are a shell mode, not separate routes
`presentation: desktop | focus` is a local UI preference that changes layout components and density. The routes and data are the same. Focus mode always uses the dark aubergine theme. Desktop follows the `theme` setting.

### D6: Design tokens as CSS custom properties, owned by Impeccable
Tokens cover colour (desktop dark and light, Focus), type, space, radius, elevation and motion (durations, easings, spring presets mirrored in TS). They are generated into `src/theme/tokens.css` and documented in `DESIGN.md`. Components use only tokens. The visual direction is chosen during the A1 build, so no palette is fixed in this design beyond the brand family.

### D7: Motion runs on a budget
- Only `transform`, `opacity`, `clip-path` and sparing `filter` are animated, and every animation can be interrupted.
- A single `useMotionPreference()` combines `prefers-reduced-motion` with the `reduce_motion` setting. Under reduced motion, presets switch to crossfades or instant changes, and parallax, scale and View Transitions are disabled.
- In-app scroll animation uses CSS scroll-driven animations (`animation-timeline: view()/scroll()`) under `@supports`, with an `IntersectionObserver` fallback.
- Long grids use `content-visibility: auto`. The catalogue uses cursor pages with a sentinel plus a "Load more" button.

### D8: Settings are applied globally
After sign-in, `/me/settings` is read once and applied at the root:
- `theme`;
- `reduce_motion`;
- `language` (i18n catalogue switch, `Intl` locale `en-GB`/`id-ID`, time zone Asia/Jakarta);
- `sound_effects` / `sound_volume` (WebAudio tick synthesiser, never initialised until enabled);
- `wardrobe_view` and `wardrobe_group_by_slot` (wardrobe defaults);
- `style_suggestions`.

`PATCH` sends `{version, values}`. On `SETTINGS_CHANGED` the client refetches, re-applies its change if it still makes sense, and shows "Changed on another device". Signed-out visitors use local defaults.

### D9: i18n is message catalogues
`src/i18n/en.ts` and `id.ts` hold typed keys. A unit test fails on a missing or extra key. The error-code copy map covers all 49 `ErrorCode` values in both languages. Server-provided strings (product names, explanations, reasons) are shown as returned, and the server's own `reasons` codes are mapped to copy where known.

### D10: Media and private images
`src/api/media.ts` resolves relative URIs against the API origin. Missing or failed images fall back to the slot silhouette with "Image unavailable".

Private photos are fetched with the bearer token, shown through `URL.createObjectURL`, and revoked on unmount. They are never cached by a service worker (there is none).

### D11: The avatar is lazy, template-based and honest
Three.js is loaded only on the fitting room, look detail and the Home focus preview.

- A manifest maps slot to template GLB and accessory to attachment point. Placeholder low-poly GLBs are generated by a script (`scripts/make-avatar-models.mjs`) so real models can replace them by file name.
- Colour comes from H&M colour names mapped through a labelled approximation table. `colour_known: false` renders a neutral colour.
- A 2D layered SVG fallback is used when WebGL is missing, a model fails, or the median frame time exceeds budget. The UI states which mode is active.
- `#/dev/avatar-fps` records the 60 s median FPS (RQ4 evidence).

### D12: Staff workspace is a separate lazy chunk
`#/admin/*` is code-split and shown only when `/me` capabilities include a staff capability. It has its own denser layout (Operate mode) and shares tokens and components. Every route checks capabilities. A 403 still renders a clear "not permitted" state, because the server is authoritative.

### D13: The landing page uses the Scrollcraft engine inside the same build
Scrollcraft's engine files are copied into the landing source unchanged, as its rules require. The page is real HTML in `index.html` with bespoke scripts. It fetches only public endpoints (collections, products, facets, about) with silent fallback, and makes no authenticated call. Generated assets live under the scrollcraft workspace. Only the compressed shipping assets are copied to `public/landing/`; raw sources and screenshot sheets are gitignored.

### D14: Tests reuse the v2 harness
`e2e/` contains a copy of `harness.py` and a spawn-based launcher (paths contain spaces). The copy's grant allowlist is widened to every role so moderator and inventory paths can be tested; the API itself is not changed. Playwright projects:
- `e2e` (two-user flows);
- `visual` (widths × presentations × themes);
- `a11y` (axe on every route).

Performance uses Lighthouse CI against the preview build with a documented mobile profile.

### D15: The coverage gate is static
`scripts/check-coverage.mjs` reads every `method + path` from the OpenAPI file and checks that the typed client references the operation. Missing operations must appear in `coverage-allowlist.json` with a reason. It runs in CI and in `npm test`. While the surfaces are being built (tasks 1.9–7.4), it runs with `--report`: it prints the table and exits 0, still failing on unknown allowlist entries. Task 7.5 switches it to strict, so the gate is enforced from then on.

## Risks / Trade-offs

- [Focus mode plus desktop doubles the layout work] → Shared components are parameterised by density. Focus mode is mandatory only for the primary destinations, wardrobe, catalogue and profile; staff screens stay desktop-only.
- [Real Neon Auth is not available in CI] → The e2e build uses the fake port against the harness issuer. Real Google and email sign-in remain a manual check (accounts 9.2).
- [A heavy bundle (Three.js, Motion, React)] → Code-split routes, lazy-load the avatar and staff, and set a CI bundle-size check for the shell chunk.
- [Animation fights accessibility or performance] → The reduced-motion variant is required per animation, FPS is measured during Focus navigation, and every animation can be interrupted.
- [The H&M colour approximation could be mistaken for fact] → It is labelled in the inspector and the avatar; the approximation table is documented.
- [An agent invents features from the owner mocks] → The reconciliation table (brief §8) is carried into `web-catalogue-commerce` and the other specs, and the coverage gate plus `API_GAPS.md` make the gaps explicit.
- [Two working copies, G: and C:, drift] → Implement only in `C:\dev\wearhouse`, and bring changes back through git.

## Migration Plan

Additive only:
1. `account-pages` keeps working, side by side.
2. After acceptance (tasks C), record parity and propose retiring `account-pages` as a separate change.
3. Deployment and hosting come in their own change.

Rollback means not deploying, or reverting the package. Nothing else depends on it.

## Open Questions

- The production hosting origin and base path. `VITE_BASE` and `WEARHOUSE_ALLOWED_ORIGINS` are configuration, so this does not affect the build.
- Whether to commission real GLB garment templates later. The manifest makes this a file drop-in.
