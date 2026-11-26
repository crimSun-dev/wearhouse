# Wearhouse frontend build prompt (Impeccable + Scrollcraft)

> **This document drives the v2 frontend.** `docs/FRONTEND_PROMPT.md` is the historical v1 (Digital Wardrobe demo) prompt; do not use it.
> Written 2026-11-26 against `packages/contracts/openapi-v2.json` (Wearhouse API 0.1.0, 145 operations).

## How to use this file

Each step runs in a **fresh agent session** opened at the repo root (`Live Demo/`). Every prompt begins by telling the agent to read **§1–§9 of this file in full**. The prompts are short because the spec is here: paste only the fenced prompt block.

| Step | Skill | Builds | Output |
|---|---|---|---|
| 0 | `/opsx:propose` | OpenSpec change `add-wearhouse-frontend` (repo convention: `apps/web/README.md`) | `openspec/changes/add-wearhouse-frontend/` |
| A1 | `/impeccable` | PRODUCT.md, DESIGN.md, design tokens, **the Big Picture shell**, focus engine, motion kit, auth + onboarding | the shell at `/app/` |
| A2 | `/impeccable` | Catalogue + commerce (the "Store") | store routes |
| A3 | `/impeccable` | Wardrobe, item inspector, fitting room + avatar, looks, suggestions, planner, wear, redeem, weather | wardrobe routes |
| A4 | `/impeccable` | Community, profiles, notifications, settings, security, account, about | community + account routes |
| A5 | `/impeccable` | Staff workspace (role-gated) | `#/admin/*` |
| B | `/scrollcraft` | Scroll-driven landing page that sells the ecosystem and hands off to the app | `/` |
| C | `/impeccable animate` → `audit` → `polish` → `harden` → `document` | Motion pass, audit, fixes, final DESIGN.md | everything |

Build A1 before anything else: every later step inherits its shell, tokens, focus engine and motion kit. Build B after A2–A4 so the landing page can use real screenshots of the finished app.

---

## §1 Project and sources of truth

**Wearhouse** is a Steam-inspired fashion ecosystem for Indonesian Gen Z. *Catalogue* is the store, *Wardrobe* is the library, *Community* is the friends layer, and *Profile* is your identity. People browse a real-source catalogue (H&M research snapshot, 105k articles), wishlist items, make a **simulated** purchase, receive a **private activation key**, redeem it once, and the garment becomes an owned item in their wardrobe. They can then equip an avatar, get weather-aware outfit suggestions (BMKG), plan seven days, log what they actually wore, and share looks with friends. Staff import, curate, publish and retire products, manage media, sizes, offers and units, moderate shares, and assign roles.

"Digital Wardrobe" survives only in research titles. The product name is **Wearhouse** everywhere in the UI.

The backend is **done and tested**. You are building the frontend only.

Read, in this order:

| Source | Why |
|---|---|
| `apps/api/README.md` | Route table with behaviour, limits and principals: the functional truth |
| `packages/contracts/openapi-v2.json`, `packages/contracts/src/schema.d.ts`, `src/error-codes.d.ts` | Exact request/response shapes and all 49 error codes. **Import types only from `@wearhouse/contracts`** |
| `CRIMSUN_POOL/TDD_Digital_Wardrobe_Ecosystem_v1.md` §3–§5, §7, §10–§12, §14, §17 | Steam translation, information architecture, tile system, Focus mode, privacy, ownership/commerce state machines, release bars, definition of complete |
| `docs/architecture/tdd-status.md` | What is done: F05 avatar and F10 UI are the frontend's job |
| `docs/architecture/*-readiness.md` | Behaviour detail per module (wardrobe, social, commerce, sizes, settings-security, object-management, outfit-recommender) |
| `openspec/specs/*/spec.md` | Normative requirements with scenarios. Read the spec for every area you build |
| `apps/web/account-pages/` | **Temporary** functional pages: a working reference client for every flow, including Neon Auth (`src/auth/*`), the API client (`src/api.ts`) and the e2e harness (`e2e/harness.py`). Reuse its auth port and client patterns. Do not reuse its markup or CSS |
| `Reference/*.png` (4 Steam screenshots) and `Assets/*.png` (logos + 4 owner mocks) | Structure and feel. See §3 |

---

## §2 Hard rules

1. **Do not change `apps/api`, `packages/contracts`, migrations or tests.** If the UI needs something the API does not provide, record it in `apps/web/client/API_GAPS.md` and design around it honestly. Do not fake it client-side. Known gaps are listed in §8.
2. **Every feature on screen maps to a real endpoint** (§7). Owner mocks show features that do not exist (Sale, Trending, Sets/Activewear categories, Cloud Sync, Downloads). Map them per §8 or leave them out.
3. **Honest labels, always:**
   - sandbox prices say "Simulated price", and checkout says nothing is charged or shipped;
   - recommendation `model.mode` is shown (`heuristic_baseline` is labelled as a baseline, never as AI or "trained");
   - attribute `origin: rule` is shown as "estimated" and `owner` as "set by you";
   - missing media shows a slot silhouette with "Image unavailable", never stock imagery;
   - weather outside the ~3-day BMKG horizon says "Forecast unavailable" and is never invented;
   - BMKG is credited wherever weather appears;
   - `GET /about` sources, licences and the AI disclosure are reachable from every page footer or menu.
4. **Secrets:** activation keys and access tokens never go into URLs, query strings, `localStorage`/`sessionStorage`/IndexedDB, logs, analytics or error reports. A key that has been revealed is held only in component state, is cleared when you leave the route, and is masked until the person reveals it.
5. **Public QR is discovery only.** `#/items/:serial` shows the product and "Add to wishlist". It never claims, and the page explains that ownership needs the private key.
6. **Privacy by default.** Never show another user's serials, ids, receipts or wear history. Respect `profile_visibility`, `sections` and 404s exactly as returned. A blocked handle, a deleted handle and an unknown handle look the same.
7. **Server state is the truth.** Keep only composition drafts, focus position and UI preferences on the client. Clear every private cache on sign-out. Abort obsolete requests, and drop out-of-order responses.
8. **No legacy code.** Do not import from `legacy/` or copy the v1 renderer. The old Canva prototype and `docs/legacy/frontend/*` are not references.
9. **Accessibility is not optional:** WCAG 2.2 AA; semantic DOM controls (never a canvas-only UI); visible focus; 44 px targets; full keyboard, screen reader and gamepad paths; usable at 200% zoom; `prefers-reduced-motion` **and** the `reduce_motion` setting both respected.
10. Synthetic and generated imagery only: no real people's photos, no third-party brand logos, no text baked into images.

---

## §3 Reference reading: structure from Steam Big Picture, creativity unrestricted

**What is fixed:** the brand (Wearhouse logos in `Assets/`, plum/aubergine/blush family), the information architecture (§5), the functional map (§7) and the Big Picture interaction model below.

**What is open:** composition, typography pairing, exact colours and spacing, illustration and effect language, iconography, motion choreography. Treat the owner mocks as **mood and structure evidence, not pixel specs**. Impeccable should commit to a distinct visual world with a clear point of view, and go further than the mocks where that serves the product.

### What each reference teaches

| File | Take from it | Do not copy |
|---|---|---|
| `Reference/…122759.png` (Steam Store) | Global destinations (STORE · LIBRARY · COMMUNITY · profile) above a contextual sub-bar (Browse, Categories, search, Wishlist count); a big featured carousel with a side panel of supporting media; blurred neighbouring cards bleeding off the edges | Toolbar clutter, the menu bar, banner ads |
| `Reference/…122849.png` (Store + account menu) | The account menu as a compact dropdown (Change account, Sign out, Settings): ours holds Profile, Redeem a garment, Orders, Settings, Sign out | Desktop-client chrome |
| `Reference/…122914.png` (Library) | Left collection sidebar plus a portrait 2:3 cover grid; "Add shelf"; shelf header with count and a SORT BY control; a persistent bottom status bar | The dense text list as the primary view |
| `Reference/…122951.png` (Big Picture home) | **The core model:** a dominant focused tile at the left of a horizontal rail; neighbours smaller; the **title and metadata of the focused tile beneath the rail**; the backdrop tinted by the focused item; tabs below (What's new / Friends / Recommended); a top-right cluster (search, bell, feed, clock, avatar); a **footer button-hint bar** (MENU · OPTIONS · A SELECT · B BACK) | Game art, the controller glyph style verbatim |
| `Assets/c9303a0b…png` (owner mock: Discover) | Big Picture home for fashion: left rail nav (Discover, My Wardrobe, Outfit Studio, Wishlist, Collections, Settings), a focused editorial hero card with portrait category tiles running off the right edge, pill tabs (For You / New In / Collections), "Browse by Category" tiles, "Outfit Picks for You" rail | The "Sale" and "Trending" tabs (no API: see §8) |
| `Assets/cd888c5c…png` (owner mock: Wardrobe) | Library for clothes: STORE · WARDROBE · COMMUNITY · STYLE LAB top nav with an underline indicator; a sidebar with category counts and **Collections** (shelves); filter chips; sort plus grid/list toggle; a soft-lit garment grid on blush tiles; a bottom bar with "Add Item", "Manage Collections", item count with a capacity bar, and "A View Item · Options" hints | Categories the API does not have (Sets, Activewear) |
| `Assets/5b18d145…png` (owner mock: Settings) | Settings as sectioned cards with a left section rail; toggles, segmented controls and selects. The sections line up almost one-to-one with the real settings registry (§6) | Cloud Sync / Sync Now, Downloads (see §8) |
| `Assets/c7791610…png` (brand: open wardrobe illustration) | Brand world: plum interior, warm shelf light, an open wardrobe as a metaphor. Good landing and empty-state material | |
| `Assets/Wearhouse Logo on Plum Background.png`, `03b20ba8…png` (wordmark on light), `208131bb…png` (mark, transparent), `Plum House Ribbon Logo.png` (mark + app-icon tile) | Logo lockups, the app icon and the favicon source. Use them as supplied: no recolouring beyond white/plum, no effects on the mark | |

### The Big Picture interaction model (required)

> **Owner decision (2026-11-26): no gamepad controls.** Wherever this brief mentions a gamepad, controller buttons (A/B/X/Y, LB/RB, Start, View) or the Gamepad API, use the keyboard equivalent instead: Enter, Escape, `[` `]`, `/`, `M` (Main menu) and `Q` (Quick access). The hint bar shows keyboard keys.


- **Two presentations of the same routes and data:**
  - **Desktop** (Steam client): top nav, sidebars, grids, dense metadata.
  - **Focus mode** (Big Picture): large rails, a single focused tile, a detail zone under the rail, quiet chrome, a footer hint bar.
  - Toggle from the top bar and remember the choice as a local UI preference. Focus mode is always the dark aubergine world. Desktop follows the `theme` setting (`dark | light | system`).
- **Selection is the hero effect.** The focused tile scales up, lifts, gets a crisp focus ring and **drives the page**: backdrop colour and a blurred wash of its imagery crossfade behind the rail, and the detail zone (name, source/owned state, price or care state, the primary action) updates beneath it. Neighbours recede. This must feel instant and physical on mouse, keyboard, touch and gamepad alike.
- **Spatial navigation:** arrows move within a rail or grid; up and down move between rails and remember the last focused index of each rail; Enter or A selects; Escape or B goes back; LB/RB (or `[`/`]`) switch tabs; Start opens the **Main menu** overlay (left: Home, Catalogue, Wardrobe, Community, Profile, Settings, Sign out); Select/View opens the **Quick access** overlay (right: notifications, friend requests, today's weather, quick toggles for theme / reduce motion / sound). Y (or `/`) focuses search. Use a roving `tabindex` on real links and buttons. Tab order stays logical. The Gamepad API runs only while a pad is connected.
- **Footer hint bar** in Focus mode shows the live actions for the focused object (for example `A Open · X Wishlist · Y Search · B Back`). It updates per context and is hidden on touch-only devices.
- **Top-right cluster:** search, notifications bell with the unread count (`/me/notifications/unread-count`), feed, a live clock (Asia/Jakarta by default) and the avatar/account menu.
- **Optional UI sounds** (Big Picture ticks on move, select and back), synthesised with WebAudio with no audio files. They play only when `sound_effects` is on (default **off**), at `sound_volume`.
- No required autoplay or auto-scroll. Every rail has visible previous/next controls and a grid alternative (TDD §5.3).

---

## §4 Stack, layout, environment

Decided. Do not relitigate unless something blocks you; if it does, say why in the OpenSpec design.

- **Package:** `apps/web/client/` (`@wearhouse/web`), a multi-page Vite build:
  - `index.html` → landing (Scrollcraft, step B; a minimal placeholder until then);
  - `app/index.html` → the app. Inside the app use **hash routes** (`#/catalogue`, …) so static hosting needs no fallback rules. The base path is configurable (`VITE_BASE`, default `/`) for later GitHub Pages hosting.
- **Stack:** Vite 7 + TypeScript 5.9 (strict) + React 19. TanStack Query for server state (keys include the user id; `queryClient.clear()` on sign-out). React Router `createHashRouter`. **Motion** (motion.dev) for UI animation and layout/shared-element transitions; the View Transitions API where supported. Three.js (lazy-loaded) for the avatar. Pin exact versions in `package.json` with a lockfile and `.npmrc` like `account-pages`. Reuse its pins where they overlap (`vite 7.3.8`, `typescript 5.9.3`, `@playwright/test 1.65.1`, `@neon/auth 0.8.2`).
- **Structure:** `src/shell/` (top bar, main menu, quick access, hint bar, focus engine, presentation toggle) · `src/api/` (one client) · `src/auth/` (port + neon + e2e fake) · `src/i18n/` · `src/motion/` (tokens, presets, sound) · `src/components/` (tiles, rails, grids, chips, sheets, dialogs, toasts, skeletons, silhouettes) · `src/features/{catalogue,commerce,wardrobe,looks,fitting-room,suggestions,planner,redeem,weather,community,profile,settings,account,staff,about}/` · `src/avatar/`.
- **Env:**
  - `VITE_WEARHOUSE_API_BASE` (default `http://127.0.0.1:8100/api/v2`);
  - `VITE_NEON_AUTH_URL` (Neon Auth branch URL);
  - e2e builds use `--mode e2e` with the fake auth port and `VITE_E2E_TOKEN_URL`.
  - The dev server runs on **5174**, which is already in `WEARHOUSE_ALLOWED_ORIGINS` in `apps/api/.env.example`.
- **Backend for development:** `.\tools\dev_api.ps1` (port 8100; see `docs/runbooks/local-environments.md`). For tests, run `apps/web/account-pages/e2e/harness.py` (disposable Postgres via `WEARHOUSE_TEST_ADMIN_URL`, local issuer, token endpoint on 8199). Point its `E2E_PAGES_ORIGIN` at the new app's preview origin.
- **i18n:** the `language` setting is `en | id`. Ship complete English **and** Indonesian catalogues. Use `Intl` for dates (`en-GB` / `id-ID`, Asia/Jakarta) and IDR (`id-ID`, no decimals).
- **Scripts:** `dev`, `build`, `preview`, `typecheck`, `test` (Vitest), `test:e2e` (Playwright), `test:visual`, `test:a11y`. Add a `web` job to `.github/workflows/ci.yml` (npm ci, typecheck, unit, build, contract-coverage check) without touching the existing jobs.

### Identity and the API client

- **Auth:** copy and adapt `apps/web/account-pages/src/auth/{port,neon,fake,provider}.ts`:
  - Neon Auth (Managed Better Auth): Google sign-in plus email/password, sign-up, reset (`#/reset?token=`), change password, verification, device sessions, sign out, revoke all.
  - The access JWT comes from `getSession().data.session.token`, with `token()` as a fallback (see the comment in `neon.ts`).
  - Ask for a fresh token per request and never store it. **Passwords go to the broker only.**
- **After sign-in:** `GET /me` returns `capabilities`, `roles`, `handle` and `needs_onboarding`. If `needs_onboarding` is true, route to **Onboarding** (choose a handle, display name, avatar preset) before anything private. Show staff entry points only for staff capabilities. The server stays authoritative: still handle a 403 gracefully.
- **One client module** (`src/api/`):
  - typed from `@wearhouse/contracts`; base URL; `Authorization: Bearer` when signed in; JSON, 204 and raw/binary (photo upload, media, export download);
  - an `AbortController` per request and a client timeout;
  - parse the error envelope `{code, message, field_errors?, request_id}`, and read `Retry-After` on 429;
  - map `field_errors` to inputs;
  - show `request_id` in a "Copy details" affordance on unexpected errors.
- **Idempotency-Key** (`web-<uuid>`) is required on: `POST /me/friend-requests`, `POST /me/checkout`, `POST /redemptions`, `POST /me/wear`, `POST /admin/unit-batches`. Generate one key per user intent and **reuse it on retries of the same intent**. `IDEMPOTENCY_KEY_REUSED` means the body changed, so make a new intent. `REQUEST_IN_PROGRESS` means wait and retry.
- **Error codes:** write a complete `code → {en, id}` copy map for all 49 codes in `error-codes.d.ts`. Special handling:
  - `REAUTHENTICATION_REQUIRED` → re-sign-in flow, then resume;
  - `SETTINGS_CHANGED` → reload and show "Changed on another device";
  - `PRICE_CHANGED` → refresh the cart and show the difference;
  - `INVALID_ACTIVATION_CODE` → one generic message, never hinting which part is wrong;
  - `RATE_LIMITED` → a countdown from `Retry-After`;
  - `HANDLE_CHANGE_TOO_SOON`, `LAST_ADMIN`, `SELF_REVOKE`, `ALREADY_CHOSEN` → explain inline.

---

## §5 Information architecture

**Primary destinations** (top nav on desktop, Main menu in Focus mode, bottom nav at 360–430 px): **Catalogue · Wardrobe · Community · Profile**, plus **Home** (the Big Picture landing inside the app).

**Utilities:** search, Wishlist (count), Cart (count), notifications, account menu (Profile, **Redeem a garment**, Orders, Settings, About, Sign out). **Staff** shows only for staff capabilities and opens a separate workspace.

Wardrobe is a self-contained area with its own sidebar: **All garments · Shelves · Looks · Fitting room · Suggestions · Planner · Wear log**. Catalogue filters are not wardrobe controls. A wishlist is not ownership, and a cart is not inventory. The planner is the editor; the profile week is its read-only projection.

Responsive (TDD §5.4):

| Width | Layout |
|---|---|
| Desktop | Max reading width about 1440 px (Focus mode may go edge to edge); 240 px wardrobe sidebar; 5–6 portrait columns |
| Tablet | Sidebar becomes a drawer; 3–4 columns |
| 360–430 px | 2 columns; compact top bar; bottom nav |

On phones, rails stay swipeable with snap, and the planner becomes a date strip plus a single-day editor. Check every route at 360, 390, 768, 1440 and 1920 px.

**Tile system** (TDD §5.2):

| Tile | Ratio | Notes |
|---|---|---|
| Product | 2:3, `object-fit: contain` | Name, source label, simulated price/availability, separate wishlist button |
| Owned item | 2:3 | Name, verified/declared, care state; no purchase CTA |
| Look | 3:4 | Avatar render or collage, name, occasion, planned marker |
| Feature / collection | 16:9 | Editorial crop |
| Timeline day | Date + portrait | planned / worn / empty, plus weather status |

At most two badges per tile. Image and title share one link. The wishlist control is a separate labelled button, never nested inside the link. Skeletons keep tile dimensions (CLS ≤ 0.1).

---

## §6 Domain vocabulary (exact values; read registries at runtime where an endpoint exists)

- **Slots** (`GET /wardrobe/slots` → `slots[{slot, capacity}]`, `exclusions`, `occasions`, `attributes`, `ruleset`):
  - capacity 1: `top, outer, bottom, dress, footwear, bag, headwear, eyewear, earrings, necklace, tie, scarf, belt`;
  - capacity 2: `wrist, ring`;
  - capacity 3: `accessory` (an explicit "uncategorised", never guessed);
  - exclusions: `dress`×`top`, `dress`×`bottom` (a dress clears both).
  - `slot_source`: `override | catalogue | rule | declared | unknown`. An item in `unknown` cannot be placed until it has a slot override.
- **Care states:** `ready | laundry | repair | stored`; plus `archived: true`. Suggestions use only ready, unarchived items. Manual composition may show a non-ready item with a warning.
- **Item kind:** `verified` (redeemed unit; has `public_serial`, `claimed_at`, provenance) or `declared` (manual/thrifted, private photo optional).
- **Attributes:** `warmth, rain_suitable, long_sleeve, long_bottom, formal`. Each value has `origin: rule | owner`.
- **Two occasion vocabularies.** Do not merge them:
  - outfit suggestions use the registry `occasions`: `casual | campus | hangout | worship | wedding`;
  - planner entries use `casual | work | formal | sport | event`.
- **Weather:**
  - forecast `source`: `LIVE | CACHED | MANUAL_REQUIRED` (`note: "no_location"` when no location is set);
  - suggestion weather `source`: `LIVE | CACHED | MANUAL | NONE | DISABLED`;
  - planner day `status`: `forecast | beyond_forecast | unavailable`;
  - location is a BMKG `adm4` code (example `31.71.03.1001`, Kemayoran); time zone Asia/Jakarta; horizon about 3 days.
- **Settings** (`GET /me/settings` returns schema + values + version; `PATCH {version, values}`). Render from the schema, grouped by `sections`:

  | Section | Keys |
  |---|---|
  | general | `language` en/id |
  | wardrobe | `wardrobe_view` grid/list/outfit, `wardrobe_group_by_slot` |
  | style | `style_suggestions`, `weather_in_suggestions`, `recommendation_style` balanced/classic/adventurous |
  | display | `theme` dark/light/system, `reduce_motion` |
  | audio | `sound_effects`, `sound_volume` 0–100 |
  | notifications | `notify_friend_requests`, `notify_request_accepted`, `notify_friend_shares` |
  | community | `friend_requests_from` everyone/nobody, `discoverable` |
  | beta | `beta_features` |

  Each setting must **visibly do something** in the UI: theme, motion, sound, language, the default wardrobe view, grouping, suggestions on/off, and so on.
- **Profile:**
  - avatar `kind: preset | provider`, presets `plum, ivory, blush, noir, sage, sky`;
  - privacy `profile | wardrobe | friends_list` ∈ `public | friends | private`;
  - showcase `accent` ∈ `plum, ivory, blush, noir, sage, sky`, `headline` ≤ 80, up to 3 featured shares;
  - handle change every 7 days at most, with a 30-day hold.
- **Shares:** `audience: friends | public`, caption ≤ 140, pinned to a look revision (`repin` to update); `effective_audience` and `moderation` are computed by the server. Plan sharing: `none | friends`.
- **Commerce:**
  - IDR integers, `sandbox: true`;
  - cart ≤ 20 lines, quantity 1–5, an optional size per line;
  - wishlist ≤ 500;
  - order `status: fulfilled | cancelled`;
  - unit delivery `available | expired | unavailable | claimed`.
- **Activation key:** 16 base32 characters (A–Z, 2–7) shown as `XXXX-XXXX-XXXX-XXXX`; case and dashes ignored; limit 10 attempts per user per hour.
- **Roles → capabilities:**

  | Role | Capabilities |
  |---|---|
  | `catalogue_editor` | `catalogue:ingest`, `commerce:offers`, `catalogue:media` |
  | `inventory_manager` | `inventory:issue`, `inventory:reissue`, `commerce:orders` |
  | `moderator` | `social:moderate` |
  | `admin` | everything above, plus `identity:manage_roles`, `ops:read` |

  Customers have `ownership:redeem` and `ownership:read_own`. **Gate the UI by capability, not role name.**
- **Limits worth surfacing:**
  - friends 1000, pending requests 200, sends 50 per 24 h, blocks 1000;
  - looks 200, shelves 50 × 500, declared items 1000;
  - photos JPEG/PNG/WebP ≤ 2 MB (staff media ≤ 5 MB);
  - plans from today to +30 days; wear entries from today back to −60 days;
  - export 5 per hour;
  - deleting the account needs a sign-in within the last 5 minutes plus the typed handle.

---

## §7 Screen and endpoint map (the frontend must cover all of it)

Every row is a requirement. "→" is the primary action. All paths are under `/api/v2`.

### 7.1 Public (works signed out)

| Route | Screen | Endpoints | Notes |
|---|---|---|---|
| `#/` (signed out) | App home, public variant: featured collections, new arrivals, sign-in CTA | `GET /catalogue/collections`, `GET /catalogue/products?sort=newest` | Big Picture rails |
| `#/catalogue` | Store front: featured hero rail, collections, category tiles (from facets), New in | `GET /catalogue/collections[/{slug}]`, `GET /catalogue/facets`, `GET /catalogue/products` | Category tiles come from real facet values and counts |
| `#/catalogue/browse` | Browse + search + filters: `q`, `category`, `colour`, `slot`, `size=system:code`, `my_sizes` (signed in), `hide_owned` (signed in), `sort=newest\|name` | `GET /catalogue/products` (cursor), `GET /catalogue/facets`, `GET /catalogue/sizes` | Infinite scroll with a sentinel plus a "Load more" button. Filters live in the URL hash (never secrets). Empty → "Clear filters" |
| `#/catalogue/products/:id` | Product detail: media gallery, facts with source fields, annotations with origin, source identity, sizes, simulated offer, similar products | `GET /catalogue/products/{id}`, `…/{id}/sizes`, `…/{id}/similar` (show `model.mode`/`fallback`), `GET /commerce/products/{id}/offer` → wishlist / add to cart (signed in) | Owned already? Show "In your wardrobe" (from wardrobe items' `product_id`) |
| `#/collections/:slug` | Collection page | `GET /catalogue/collections/{slug}` | |
| `#/items/:serial` | Public tag lookup (QR landing) | `GET /items/{serial}` → Add to wishlist | **Discovery only.** Includes an in-app QR scanner (BarcodeDetector + camera on HTTPS, with paste-a-link as fallback) that parses `/items/{serial}` links |
| `#/u/:handle` | Public profile: header, showcase, shared looks, wardrobe and friends sections per privacy, the week if allowed | `GET /profiles/{handle}`, `…/showcase`, `…/shares`, `…/wardrobe` (cursor), `…/friends` (cursor), `…/week` | One 404 state for blocked, deleted and unknown. Friendship and block actions when signed in (§7.4) |
| `#/shares/:id` | Shared look | `GET /shares/{id}` → save as inspiration, report (signed in) | |
| `#/about` | About: version, sources with licences and citations, notices, AI disclosure | `GET /about`, `GET /health` | Linked from the footer and the account menu |
| `#/signin`, `#/signup`, `#/reset` | Auth | Neon Auth broker only | Google + email |

### 7.2 Signed in: home, onboarding, commerce

| Route | Screen | Endpoints | Notes |
|---|---|---|---|
| `#/onboarding` | Handle, display name, avatar preset | `GET /me`, `PATCH /me/profile` | `HANDLE_UNAVAILABLE` inline |
| `#/` (signed in) | **Big Picture Home**: Continue styling (recent looks), Today (weather + 1–3 suggestions), Recently added, Not worn recently, For you (products), Friends activity; tabs What's new / Friends / Recommended | `GET /me/weather`, `GET /me/recommendations/outfits` (only on explicit open: see 7.3), `GET /me/wardrobe/items`, `GET /me/looks`, `GET /me/recommendations/products` (label: popularity of simulated orders over 30 days, then newest; `heuristic_baseline`), `GET /me/feed` | The focused tile drives the backdrop |
| `#/wishlist` | Wishlist with availability and offer | `GET /me/wishlist`, `PUT`/`DELETE /me/wishlist/{product_id}` | `WISHLIST_FULL` |
| `#/cart` | Cart: lines, sizes, quantity 1–5, availability, total, checkout readiness | `GET /me/cart`, `PUT /me/cart/{product_id}` `{quantity, size}`, `DELETE /me/cart/{product_id}?size=` | `CART_FULL`. Unavailable lines are flagged |
| `#/checkout` | Review: explicit "Simulated purchase. Nothing is charged, shipped or delivered." → place order | `POST /me/checkout` `{expected_total_idr}` + Idempotency-Key | `PRICE_CHANGED`, `OUT_OF_STOCK`, `NOT_AVAILABLE`, `CART_EMPTY` change nothing: refresh and explain |
| `#/orders`, `#/orders/:id` | Orders and receipt: lines, `payment_ref`, sandbox stamp; per unit, the delivery state and **Reveal key** (masked → reveal → copy → "Redeem now") and **Renew key**; Cancel while `cancellable` | `GET /me/orders` (cursor), `GET /me/orders/{id}`, `GET /me/orders/{id}/units/{unit_id}/key`, `POST …/renew-key`, `POST /me/orders/{id}/cancel` | Reveal is audited, so call it only on an explicit click. Renew revokes the old key. Cancel revokes keys and restores stock |
| `#/redeem` | **Redeem a garment**: auto-formatting key input (paste-friendly, accepts lowercase and spaces), submit | `POST /redemptions` `{activation_key}` + Idempotency-Key → `OwnedItem` | One generic invalid message. A 429 shows a countdown. Success plays the **unlock** moment (§9) and links to the new item |

### 7.3 Wardrobe

| Route | Screen | Endpoints | Notes |
|---|---|---|---|
| `#/wardrobe` | Library: sidebar (slot counts, shelves), filter chips, sort (`size\|name\|worn`), grid / list / outfit view (default from `wardrobe_view`), group by slot (`wardrobe_group_by_slot`), client-side text filter, a bottom status bar with the item count | `GET /me/wardrobe/items?slot&care_state&shelf_id&size&sort`, `GET /wardrobe/slots`, `GET /me/wardrobe/shelves` | Empty wardrobe → Redeem / Add a garment / Browse the catalogue |
| `#/wardrobe/items/:id` | **Item inspector**: imagery (product media or a private photo via `GET …/{id}/photo` with auth, rendered from a blob URL), verified/declared, provenance (`/me/items/{id}` acquisition: source namespace, external id, revision, snapshot) for verified items, serial (owner only), claimed date, size and its source, care state, slot and its source plus override, attributes with origin (editable), wear count, last worn, archive → Equip / Plan / Share | `GET`/`PATCH /me/wardrobe/items/{id}`, `PUT /me/wardrobe/items/{id}/photo` (raw image body), `GET /me/items/{id}` | Revoked sandbox items (`state: revoked_sandbox`) are shown as such and leave suggestions |
| `#/wardrobe/verified` | Verified garments (owned units, cursor) | `GET /me/items` | Can live as a filter or tab of the library |
| `#/wardrobe/add` | Add a declared (manual or thrifted) garment: name, slot, category, colour, size, then an optional photo | `POST /me/wardrobe/items` (`DeclareIn`), then `PUT …/photo` | `WARDROBE_FULL`. Unknown attributes stay visibly unknown and editable |
| `#/wardrobe/shelves` | Shelves (collections): create, rename, reorder items, delete | `GET`/`POST /me/wardrobe/shelves`, `PATCH`/`DELETE …/{id}` | `SHELF_NAME_TAKEN`, `SHELVES_FULL`. Drag to reorder, with a keyboard alternative |
| `#/wardrobe/looks`, `#/wardrobe/looks/:id` | Looks gallery, then look detail with revision history (open any revision read-only) → Equip / Plan / Share / Delete | `GET`/`POST /me/looks`, `GET`/`PATCH`/`DELETE /me/looks/{id}`, `GET /me/look-revisions/{id}` | `LOOKS_FULL`, `LOOK_DELETED`. Missing items show as `missing_item_id` placeholders |
| `#/wardrobe/fitting-room` | **Fitting room** (the mocks' "Style Lab" / "Outfit Studio"): avatar stage + slot list + item picker. Equip/replace previews conflicts **before** applying (dress clears top+bottom; capacity reached replaces the oldest in that slot after confirming) → Save as a look / Save a new revision | `POST /me/looks` `{name, slots}`, `PATCH /me/looks/{id}` | The draft lives on the client; the server validates on save (show its field errors) |
| `#/wardrobe/suggestions` | **Outfit suggestions**: date (today to the planner window), occasion (registry `occasions`), weather override (rain/hot toggles → `rain`/`hot` params = manual), the weather source chip; up to 5 cards with items, `explanation[]`, a score breakdown from `components` (compatibility / preference / recency) in a details popover, `ruleset`, `model` mode and `weights`; `reasons[]` and `removed_by_rule` when there are fewer than 5 or none | `GET /me/recommendations/outfits?date&occasion&rain&hot&limit`, `POST /me/recommendations/outfits/{run_id}/events` | **Call only on explicit user action** (open, a date/occasion change, Refresh), never on hover or prefetch. Send `displayed` once, when cards are actually visible; send `chosen` with the index once per run (`ALREADY_CHOSEN` → show which). `enabled:false` → "Turned off in Settings" plus a link. Card actions: Try on (fitting room draft), Save as look, Plan for a date, Wear today |
| `#/wardrobe/planner?from=YYYY-MM-DD` | **Planner**: 7 days (previous/next week), each with weather (`forecast` → icon, min/max, rain/hot; `beyond_forecast` → "Forecast unavailable"; `unavailable` → reason), the planned look revision + occasion (planner vocabulary) + note, and worn entries. Plan, replace and clear; **Mark worn** | `GET /me/planner?from`, `PUT /me/planner/{date}` `{look_revision_id, occasion?, note?}`, `DELETE /me/planner/{date}`, `POST /me/wear` + Idempotency-Key | Planned ≠ worn. Plans only up to +30 days. Past days are read-only for plans. Mobile: date strip + one-day editor |
| `#/wardrobe/wear` | Wear log: range filter; undo an entry | `GET /me/wear?from&to`, `DELETE /me/wear/{id}`, `POST /me/wear` (log a past day, back to −60, from a look or items) | |
| `#/weather` (also a Quick access panel) | Forecast for my location: slots grouped by local date, source chip (LIVE / CACHED + `fetched_at` / MANUAL_REQUIRED + note), BMKG credit; set or clear the location (adm4 input with a format hint and the documented Kemayoran example) | `GET /me/weather`, `GET /weather/forecast?adm4=`, `PUT`/`DELETE /me/weather/location` | `no_location` → a friendly setup prompt |
| `#/sizes` | My usual sizes per system | `GET`/`PUT /me/sizes`, `GET /catalogue/sizes` | `NO_USUAL_SIZES` when "my sizes" is used without any set |

### 7.4 Community and profile

| Route | Screen | Endpoints | Notes |
|---|---|---|---|
| `#/community` | Feed of friends' shares (cursor) → open, save as inspiration | `GET /me/feed`, `POST /me/inspirations` | `INSPIRATION_FULL` |
| `#/community/friends` | Friends list, remove; search users (≥ 3-character prefix or `@exact`, ≤ 20 results) → send request | `GET /me/friends`, `DELETE /me/friends/{handle}`, `GET /users/search?q`, `POST /me/friend-requests` `{handle}` + Idempotency-Key | Limits and `REQUESTS_CLOSED`, `ALREADY_FRIENDS` |
| `#/community/requests` | Incoming and outgoing requests → accept / decline / cancel | `GET /me/friend-requests?direction=`, `POST …/{id}/accept`, `POST …/{id}/decline`, `DELETE …/{id}` | `REQUEST_NOT_PENDING` |
| `#/community/blocks` | Blocks → unblock; block from any profile | `GET /me/blocks`, `PUT`/`DELETE /me/blocks/{handle}` | Blocking overrides friendship (explain this before confirming) |
| `#/community/inspiration` | Saved inspirations → open the look; missing pieces link to catalogue search; remove | `GET /me/inspirations`, `DELETE /me/inspirations/{id}` | Inspiration never grants items |
| `#/community/shares` | My shares: create from a look (audience, caption), edit audience/caption, repin to the latest revision, delete; shows `effective_audience` and `moderation` | `GET`/`POST /me/shares`, `PATCH`/`DELETE /me/shares/{id}` | `SHARES_FULL` |
| `#/notifications` (+ Quick access) | Derived notifications (friend_request, request_accepted, friend_shared_look) → mark all read | `GET /me/notifications`, `GET …/unread-count`, `POST /me/notifications/read` | The bell badge polls only while the tab is visible, at a modest interval |
| `#/profile` | My profile = the public projection as others see it, plus Edit | `GET /me/profile`, `GET /profiles/{handle}` + sections | "Preview as public / friend" toggle |
| `#/profile/edit` | Display name, bio, avatar (preset or provider picture), handle (with the 7-day / 30-day rules shown) | `PATCH /me/profile` | `HANDLE_CHANGE_TOO_SOON` |
| `#/profile/showcase` | Showcase editor: headline, accent (6), up to 3 featured shares (reorder) | `GET`/`PUT /me/showcase` | Accent re-themes the profile header |
| `#/profile/week` | Plan sharing (none / friends) and a preview of the friend-visible week | `GET`/`PUT /me/plan-sharing`, `GET /profiles/{handle}/week` | Never shows wear, weather or location |
| shared look and profile overflow menus | Report a share (reason ≤ 300) | `POST /shares/{id}/report` | `ALREADY_REPORTED` |

### 7.5 Account

| Route | Screen | Endpoints | Notes |
|---|---|---|---|
| `#/settings/:section` | Settings rendered from the schema (left section rail as in the mock; Focus-friendly) | `GET`/`PATCH /me/settings` | Optimistic toggle with rollback; `SETTINGS_CHANGED` reconciliation; show `updated_at` as "Synced" |
| `#/settings/privacy` | Profile / wardrobe / friends-list visibility | `GET`/`PUT /me/privacy` | Explain each level in one line |
| `#/settings/security` | Sign-in age, recent-auth flag, last 50 security events; change or set password; verification email; device sessions (revoke one / others); linked methods (read-only); **sign out everywhere** | `GET /me/security`, `POST /me/sessions/revoke-all`, broker methods | "Passwords are managed by Neon Auth" |
| `#/settings/account` | **Export my data** (JSON download, 5 per hour); **Delete account** (re-auth within 5 minutes + typed handle) | `GET /me/export`, `DELETE /me` `{confirm}` | `REAUTHENTICATION_REQUIRED` → re-sign-in, then return here |

### 7.6 Staff workspace `#/admin/*` (Operate mode: dense, precise, same brand; capability-gated)

| Route | Capability | Endpoints |
|---|---|---|
| `admin/catalogue/review` (queue → product: revisions, publish a specific revision, retire) | `catalogue:ingest` | `GET /admin/catalogue/review`, `GET /admin/catalogue/products/{id}`, `POST …/{id}/publish` `{revision_id}`, `POST …/{id}/retire` |
| `admin/catalogue/imports` (upload CSV ≤ 10 MB / 5000 rows with source, snapshot sha256 and permission fields; job status with per-row `created/revised/unchanged/rejected` and errors; publish the job) | `catalogue:ingest` | `POST /admin/catalogue/import-jobs`, `GET …/{id}`, `POST …/{id}/publish` |
| `admin/catalogue/ingest` (one source product, advanced form) | `catalogue:ingest` | `POST /admin/source-products` |
| `admin/catalogue/collections` (create/edit title + ordered products, delete) | `catalogue:ingest` | `GET /admin/catalogue/collections`, `PUT`/`DELETE …/{slug}` |
| `admin/catalogue/products/:id/media` (generate a placeholder, upload with rights basis + alt, drag reorder, edit alt, soft remove / show removed; batch "generate missing") | `catalogue:media` | `GET`/`POST …/products/{id}/media`, `POST …/media/generate`, `PUT …/media/order`, `PATCH`/`DELETE /admin/catalogue/media/{id}`, `POST /admin/catalogue/media/generate-missing`, `GET /media/{id}` |
| `admin/catalogue/sizes` (systems, values, retire; product sizes; assign missing by rule) | `catalogue:ingest` | `GET /admin/catalogue/sizes`, `PUT …/size-systems/{code}`, `PUT …/{code}/sizes/{size_code}`, `GET`/`PUT …/products/{id}/sizes`, `POST …/sizes/assign-missing` |
| `admin/commerce/offers` (list, set price/stock/size stock, remove, bulk rules ≤ 50 with overwrite) | `commerce:offers` | `GET /admin/commerce/offers`, `PUT`/`DELETE …/{product_id}`, `POST …/offers/bulk` |
| `admin/commerce/orders` (status filter, cursor; buyer handle; never keys) | `commerce:orders` | `GET /admin/commerce/orders` |
| `admin/inventory` (units of a product: serial, status, times; **issue a unit**, which shows the one-time key delivery (no-store, 24 h) with copy and QR; reissue an unclaimed unit) | `inventory:issue` / `inventory:reissue` | `GET /admin/units?product_id`, `POST /admin/unit-batches` + Idempotency-Key, `POST /admin/units/{id}/reissue` |
| `admin/moderation` (reported shares → hide / restore / dismiss with a reason) | `social:moderate` | `GET /admin/moderation/reports`, `POST /admin/moderation/shares/{id}` |
| `admin/staff` (accounts with roles; grant/revoke; `LAST_ADMIN` / `SELF_REVOKE` explained) | `identity:manage_roles` | `GET /admin/staff[/{handle}]`, `PUT`/`DELETE /admin/staff/{handle}/roles/{role}` |
| `admin/ops` (model mode, active artifact, claim counts and failures, rate limits, outbox, import jobs, schema head) | `ops:read` | `GET /admin/ops`, `GET /health/ready` |

The staff workspace can generate a printable QR tag for a unit's public serial: a client-side QR encoder of the `#/items/:serial` URL. It never encodes the key.

**Coverage gate:** add `scripts/check-coverage.mjs`. It lists every `method + path` in `openapi-v2.json`, finds each one in `src/api/`, and fails CI for any operation that is neither used nor listed with a reason in `coverage-allowlist.json`. Expected allowlist: `GET /health` (used only by About), nothing else.

---

## §8 Mock-to-API reconciliation and known gaps

| Seen in a mock or the TDD | Reality | Do this |
|---|---|---|
| Sale tab | No sale or discount concept | Omit |
| Trending | `GET /me/recommendations/products` = popularity of simulated orders (30 days), then newest | Label it "Popular in Wearhouse" with a baseline note. Signed in only |
| Sets, Activewear categories | Categories come from H&M facets | Use the facet values (`GET /catalogue/facets`); never hardcode categories |
| Style Lab / Outfit Studio | Fitting room + suggestions | Name them as you like; the route content follows §7.3 |
| Cloud Sync / Sync now / Last synced | Settings are server-synced with `version`/`updated_at` | Show "Synced · time"; no fake sync button |
| Downloads | No downloads concept | Map to Export my data (§7.5) or omit |
| Wardrobe text search | No `q` on wardrobe items | Client-side filter over the loaded list (it is unpaginated) |
| Avatar body choice | No server field (profile avatar presets are pictures, not bodies) | Local UI preference; body options are not gender identity (TDD §11) |
| Weather location picker | Only `adm4` codes, no geocoder | Code input with validation and the one documented example; add a curated list only from a cited BMKG source |
| Chat | Out of scope (TDD §11) | Omit |
| Item count + capacity bar (wardrobe mock) | Declared limit 1000 (`WARDROBE_FULL`) | Show "N garments"; the capacity bar may reflect declared items against 1000 |
| Mock people photos | Product media are generated placeholders, replaceable by staff | Use real `media`/`thumbnail` URLs with silhouette fallback; never stock photos as products |

---

## §9 Motion, effects and scroll (quality bar, not a straitjacket)

Motion is a first-class part of this product: it should feel like a console dashboard at night. It is physical, responsive and confident, and nothing is gratuitous. Impeccable owns the choreography; these are the requirements.

**System**
- Define motion tokens (durations, easings, springs) in one module plus CSS custom properties. Animate only `transform`, `opacity`, `filter` (sparingly) and `clip-path`. Never use `transition: all`, and never animate layout properties.
- Every animation has a reduced-motion variant (a short crossfade or instant) triggered by **either** `prefers-reduced-motion` **or** `reduce_motion: true`. Parallax, scale and View Transitions turn off.
- Budgets: 60 fps focus navigation on a mid-range laptop; INP ≤ 200 ms; no animation delays input (interruptible springs, no awaited animations before navigation).

**Selection and focus (the signature of the whole app)**
- The focused tile scales and lifts with a spring, and gets a crisp ring with an offset gap. The shadow has real offset and blur: no zero-offset neon halo. Neighbours recede.
- The backdrop tint and a blurred wash of the focused item crossfade behind the rail.
- The detail zone text slides and fades in, debounced so fast scrubbing does not flicker.
- The rail scrolls to keep the focus in its anchor position (the Big Picture left third), with snap.
- The same effect must work for hover, keyboard, gamepad and touch (on touch: on press, plus a long-press preview).

**Buttons and controls (GUI animation)**
- Primary, secondary, icon, chip, toggle, segmented control, tab, dropdown, slider, stepper: each has distinct rest / hover / focus-visible / pressed / loading / success / disabled states.
- Press compression with a release spring; loading keeps the width (no layout shift); success morphs to a check.
- Tabs and segmented controls slide a shared indicator.
- Micro-moments with meaning:
  - wishlist heart fills with a small burst;
  - the cart count bumps when a line is added (with a fly-to-cart from the tile);
  - the bell swings once on a new unread notification;
  - a toggle's thumb springs.

**Transitions**
- Route changes use shared-element transitions: tile image → detail hero (View Transitions API or Motion `layoutId`), reversed on Back.
- The Main menu and Quick access overlays slide from their edges with a dimmed, blurred page behind; focus is trapped and returned on close.
- Sheets on mobile are draggable with velocity-based dismissal.

**Scroll animations inside the app**
- Rails and grids reveal with a short stagger as they enter, using CSS scroll-driven animations (`animation-timeline: view()`) with an `IntersectionObserver` fallback. Cap the stagger so long grids do not feel slow.
- The top bar is transparent over the Home/Store hero and turns to solid blurred aubergine after a small scroll (scroll-driven).
- The Home hero has a subtle depth parallax between the backdrop and the foreground tile.
- Sticky shelf headers compress.
- The catalogue's infinite scroll shows dimension-stable skeletons with a shimmer. Long grids use `content-visibility`/virtualisation.
- Scroll restoration on Back returns to the exact tile, with focus restored.

**Signature moments (each tied to a real state change)**
1. **Redeem unlock:** the key's four groups lock in one after another; the card flips from key to garment; the garment flies into the Wardrobe nav, which bumps; then "Added to your wardrobe · Inspect". The failure path is a calm shake plus the generic message.
2. **Simulated checkout:** the receipt slides out like a printed slip with a "Simulated" stamp; each unit shows its key state.
3. **Suggestions deal in:** up to five outfit cards deal onto the table; the explanation chips type in; choosing one sends `chosen` and the others fold away.
4. **Equip:** a garment snaps onto its avatar slot. A conflicting dress first ghosts out the top and bottom as a preview, then commits on confirm.
5. **Plan and wear:** a look card drops into a planner day; Mark worn stamps the day and leaves the plan intact (planned ≠ worn).
6. **Friend accepted:** the two avatars meet in the notification.

**Effects:** layered depth (backdrop blur, soft grain/noise, warm light falloff on tiles), glassy overlays, and skeleton shimmer are welcome where they serve hierarchy. No gradient text and no neon glow. Contrast is measured on the composited result.

**Sound:** optional WebAudio ticks for move / select / back / success / error (§3), off by default.

---

## §10 3D avatar (RQ4) and garment imagery

- The avatar never blocks anything. Lazy-load Three.js after the shell is interactive.
- Category GLB templates per slot plus accessory attachment points (headwear, eyewear, earrings, necklace, scarf, tie, belt, bag, wrist×2, ring×2). Create simple low-poly placeholder GLBs (or procedural meshes) named by template in `public/avatar/` with a manifest, so real models can be dropped in later.
- Tint from the item colour: H&M colour names map to a labelled approximate palette (`colour_known: false` → neutral). The approximation is disclosed in the inspector.
- Supports rotate, zoom, equip, remove and a body option (local preference).
- **2D fallback:** a layered SVG figure with tinted slot layers. Use it when WebGL is unavailable, a model fails to load, or frames are slow. Say which mode is showing.
- Measurement: a dev route `#/dev/avatar-fps` rotates a full look for 60 s and records the median FPS. Release bar: median ≥ 30 FPS on a named laptop and a mid-range phone, or a disclosed 2D fallback. Write results to `docs/architecture/release-evidence-avatar.md`.
- Product and item imagery: use `thumbnail`/`media[].uri` from the API (prefix the API origin if relative). Declared-item photos are private: fetch them with auth and show them through blob URLs, revoking those URLs on unmount. The fallback is the slot silhouette with "Image unavailable".

---

## §11 Verification and definition of done

- **Unit (Vitest):** API client (error envelope, 204, Retry-After, idempotency reuse on retry, abort); key formatter and normaliser; slot/occupancy and conflict preview; focus engine (grid/rail movement, memory); settings schema rendering; i18n completeness (every `en` key exists in `id`).
- **E2E (Playwright against the harness, two users):** the TDD §17 path end to end:
  1. staff publishes a product and sets an offer;
  2. customer A browses, wishlists, adds to cart, checks out (simulated), reveals the key and redeems;
  3. the item appears; customer B cannot redeem the same key (generic error) or see A's item (404);
  4. A equips and saves a look, gets suggestions (displayed/chosen), plans the week, marks worn, shares with friends;
  5. B sends a request, A accepts, B sees the share and the week (when plan sharing = friends);
  6. A blocks B, and B loses access.

  Also cover: settings change theme, motion and language live; sign-out clears private caches; `PRICE_CHANGED` and `RATE_LIMITED` paths; the beyond-forecast planner day; an empty wardrobe; an empty filter; offline/API down shows a clear state with no console errors.
- **Keyboard / gamepad:** each primary flow completes with arrows + Enter/Escape only, and with Tab only. Gamepad mapping is tested with a simulated `navigator.getGamepads`.
- **Visual regression** at 360 / 390 / 768 / 1440 / 1920, desktop + Focus, dark + light, with reduced motion on.
- **Accessibility:** axe on every route (0 serious/critical), screen-reader labels for badges, swatches, weather chips and the avatar, and announced validation and results.
- **Performance:** LCP ≤ 2.5 s (documented mobile profile), CLS ≤ 0.1, INP ≤ 200 ms, initial JS for the shell kept small (Three.js and the staff workspace are lazy chunks).
- **Coverage gate** (§7) green. `python tools/contracts.py check` still green. The API test suite is untouched.
- **Docs:** `apps/web/client/README.md` (run, build, env, e2e); PRODUCT.md and DESIGN.md at the repo root (Impeccable); update `apps/web/README.md` and `docs/architecture/tdd-status.md` (F05/F10/Phase 3) only with evidence.

---

## PROMPT 0: OpenSpec change

```text
/opsx:propose add-wearhouse-frontend

Read docs/WEARHOUSE_FRONTEND_PROMPT.md §1–§11 in full, plus apps/web/README.md and
docs/architecture/tdd-status.md. Propose the change that builds the fresh Wearhouse frontend in
apps/web/client exactly as that document specifies: proposal, design (stack, shell, focus engine,
motion system, auth port, API client, avatar, testing), specs as deltas against the existing
capabilities it surfaces (catalogue-browse, sandbox-orders, private-redemption, wardrobe-items,
outfit-planner, outfit-recommendations, friends-timeline, look-sharing, profile-showcase,
account-settings, account-security, staff-workspace, ...) plus a new web-experience capability for
Focus mode, motion and accessibility, and tasks grouped by the prompt steps A1–A5, B, C.
Do not write application code. Do not change apps/api or packages/contracts.
```

## PROMPT A1: `/impeccable` foundation, shell and design system

```text
/impeccable

Read docs/WEARHOUSE_FRONTEND_PROMPT.md §1–§11 in full, then the files it lists in §1, then look at
every image in Reference/ and Assets/. This is a new surface and a new visual world: run init to
write PRODUCT.md (users: Indonesian Gen Z in Jakarta heat and sudden rain, plus staff; jobs: discover,
own, dress, plan, share; tone: warm, confident, playful, honest about uncertainty), then new-work.

Mode: Operate for the app, but with Experience-level craft in Focus mode. Take heavy structural
inspiration from the Steam Big Picture references (§3): the focused-tile rail, the detail zone under
the rail, focus-driven backdrop, footer hint bar, Main menu and Quick access overlays, top-right
cluster. Brand is fixed (Assets/ logos, plum/aubergine/blush family); everything else about the
visual world is yours to decide, so commit to a distinct point of view and go beyond the mocks.

Build in apps/web/client (§4):
1. Vite multi-page scaffold (landing placeholder at /, app at /app/), pinned deps, scripts, CI job.
2. Design tokens (colour for dark, light and Focus; type; space; radius; elevation; motion tokens §9)
   and DESIGN.md.
3. Auth port (adapted from account-pages), API client, error-code copy map (en + id), i18n.
4. Shell: desktop and Focus presentations with the toggle, top nav, wardrobe sidebar slot, mobile
   bottom nav, top-right cluster with live clock and unread badge, Main menu, Quick access, hint bar,
   spatial focus engine (keyboard + gamepad + touch), optional WebAudio sounds, theme / reduce
   motion / language driven by /me/settings.
5. Component kit with full state matrices and motion: buttons, icon buttons, chips, toggles,
   segmented controls, tabs, selects, sliders, inputs (with field errors), dialogs, sheets, toasts,
   skeletons, product, owned-item, look, feature and day tiles, rails with prev/next and snap, grids,
   slot silhouettes, the weather chip, the sandbox label, the model-mode label.
6. Sign in / sign up / reset, onboarding (needs_onboarding), signed-out and signed-in Home (§7.1/7.2)
   as the first real Big Picture screen, About.
Verify by looking at the rendered result at 360/768/1440/1920 in both presentations and both themes,
with keyboard and reduced motion. Run the unit tests and the coverage gate (it will list the
remaining operations; that is expected).
```

## PROMPT A2: `/impeccable` Catalogue and commerce

```text
/impeccable

Read docs/WEARHOUSE_FRONTEND_PROMPT.md §1–§11, PRODUCT.md and DESIGN.md. Build everything in §7.1
(catalogue, browse, product, collections, public tag + QR scanner) and §7.2 (wishlist, cart, checkout,
orders, receipt with key reveal / renew / cancel, redeem) inside the existing shell and component kit.
Store front = Steam Store structure translated to fashion (featured hero rail with supporting media,
contextual sub-bar with browse / categories / search / wishlist), in both presentations. Implement the
redeem-unlock and simulated-receipt moments from §9, the shared-element tile→detail transition, the
wishlist burst and the fly-to-cart. Honour every honest-label and secret rule in §2. Verify visually
and with the e2e slice "publish → wishlist → cart → checkout → reveal → redeem → second user rejected".
```

## PROMPT A3: `/impeccable` Wardrobe, fitting room, suggestions, planner

```text
/impeccable

Read docs/WEARHOUSE_FRONTEND_PROMPT.md §1–§11, PRODUCT.md and DESIGN.md. Build §7.3 completely:
library (Steam Library structure: sidebar with slot counts and shelves, shelf headers with sort, grid /
list / outfit views, bottom status bar), item inspector, add declared item with photo, shelves, looks
with revisions, the fitting room with the 3D avatar and 2D fallback (§10), outfit suggestions (explicit
calls only, displayed/chosen events, explanations, model mode), the planner (7 days, weather status,
planned vs worn), the wear log, weather and location, my sizes. Implement the equip, deal-in, and
plan/wear moments from §9. Add the avatar FPS route and write the evidence file. Verify at all widths,
in Focus mode with a gamepad simulation, and with reduced motion.
```

## PROMPT A4: `/impeccable` Community, profile and account

```text
/impeccable

Read docs/WEARHOUSE_FRONTEND_PROMPT.md §1–§11, PRODUCT.md and DESIGN.md. Build §7.4 and §7.5: feed,
friends, search, requests, blocks, inspirations, my shares, notifications (bell + Quick access),
public and own profile with showcase accent theming, profile edit, plan sharing with the
friend-visible week, report; settings rendered from the server schema (every setting visibly takes
effect), privacy, security (broker password and session flows), export and delete account with
re-auth. Profile = Steam profile translated to fashion identity: showcase, shared looks, and the
seven-day week. Verify privacy paths with two users (friend, non-friend, blocked) and the
SETTINGS_CHANGED reconciliation.
```

## PROMPT A5: `/impeccable` Staff workspace

```text
/impeccable

Read docs/WEARHOUSE_FRONTEND_PROMPT.md §1–§11, PRODUCT.md and DESIGN.md. Build the staff workspace in
§7.6 as a lazy-loaded section, gated by capability. Mode: Operate. Dense, scannable, keyboard-first,
same brand at lower volume (it is Steamworks to the customer app's Big Picture). Imports with per-row
results, the review queue and revisions, publish / retire with confirmation, the media manager with
drag reorder and rights, sizes, collections, offers (single + bulk), orders, units with the one-time
key delivery and a printable tag QR (serial only), moderation, staff roles, ops. Every destructive or
audited action confirms and says what it does. Then run the coverage gate: it must be green.
```

## PROMPT B: `/scrollcraft` landing page

```text
/scrollcraft

Read docs/WEARHOUSE_FRONTEND_PROMPT.md §1–§3 and §8, PRODUCT.md and DESIGN.md, look at every image in
Assets/ and Reference/, and take screenshots of the finished app in Focus mode to use as real product
assets. Build the landing page at apps/web/client/index.html (route /), in the existing Vite build. Do
not change the app at /app/ or anything in apps/api. Set the scrollcraft workspace with a
.scrollcraft.json at the repo root pointing to apps/web/client/scrollcraft.

BRIEF: self-authored under explicit creative delegation. The owner may override any answer.
1. Vibe: a plum velvet dressing room at night; console-dashboard confidence; warm tungsten on fabric.
   References: Steam Big Picture's focus rail, the open-wardrobe brand illustration in Assets/,
   late-night Jakarta after rain.
2. Journey: your clothes as a library → a store of real-source products (sandbox prices, said
   plainly) → a simulated purchase gives a private key → the key becomes the garment → the wardrobe
   opens → dressed for Jakarta's actual weather (BMKG, honest 3-day horizon) → seven planned days →
   a look shared with friends, privately by default → Open Wearhouse.
3. Energy: calm open, rising through the store, sharp at the key, peak at the wardrobe, calm
   through weather and week, warm at friends, resolved close.
4. Feeling: curiosity → want → anticipation → delight (the one moment: the wardrobe opening onto
   the garment you just redeemed) → reassurance → belonging → ready.
5. Signature move: scroll types and resolves a specimen activation key, labelled as an example
   (WEAR-HOUS-EXAM-PLE2), one group at a time; each completed group releases one hinge of the
   wardrobe; on the fourth the doors swing open and the garment settles onto its shelf.
6. Distance from premium-minimal: editorial-premium with a game-dashboard edge; dark, tactile, lit.
7. Distinct scenes (Store, Key, Wardrobe, Weather, Week, Friends), not one unbroken world.
8. Assets: Assets/ logos and brand illustration (never ship the mocks as screenshots: they show
   features that do not exist); real app screenshots; generated photoreal garments, studio sets,
   wardrobe interior and rain-on-glass Jakarta via kie.ai: synthetic people only, no logos, no text.

Live data (public endpoints only, degrade silently, never invent numbers): GET /catalogue/collections
and /catalogue/products for real featured tiles, GET /catalogue/facets for real counts (no fallback
number), GET /about for the sources, licence and AI-disclosure footer. No authenticated calls on
the landing page. CTAs: "Open Wearhouse" → /app/#/ and "Browse the catalogue" → /app/#/catalogue.

Requirements: dimensional layered hero (independent background / subject / foreground / atmosphere
planes), at least four device families, one peak, a separate mobile composition, a reduced-motion
version with static frames, semantic HTML readable without JS, keyboard-reachable CTAs, no layout
shift, compressed lazy assets. Verify with the scrollcraft shoot harness on desktop, mobile and
reduced motion, run the feel check, and report.
```

## PROMPT C: `/impeccable` animate, audit, polish, harden, document

```text
/impeccable animate apps/web/client

Read docs/WEARHOUSE_FRONTEND_PROMPT.md §1–§11, PRODUCT.md and DESIGN.md. Do a full motion pass
against §9 across the app and landing: focus/selection, every control's state matrix, route and
overlay transitions, in-app scroll animations, the six signature moments, sounds, and reduced-motion
variants for each. Measure frame rate during Focus navigation and fix anything below budget.

Then run, in order, fixing what each finds before the next:
/impeccable audit apps/web/client     (a11y, performance budgets, responsive widths, contrast on
                                        composited pixels, keyboard / gamepad / screen reader)
/impeccable harden apps/web/client    (every error code in the copy map in both languages, offline
                                        API, slow BMKG, empty / loading / error states, 429 countdowns,
                                        re-auth resume, sign-out cache clearing, secrets never stored)
/impeccable polish apps/web/client    (§3 Big Picture fidelity, §2 honest labels, copy consistency
                                        en + id, visual regression at all widths)
/impeccable document                  (DESIGN.md from the shipped result)

Finish with the §11 checklist: report each item as passed / failed / not run, with evidence.
```
