# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Decided in `docs/WEARHOUSE_FRONTEND_PROMPT.md` §4: a multi-page Vite 7 build in `apps/web/client` (`@wearhouse/web`) with TypeScript 5.9 (strict), React 19, TanStack Query, React Router `createHashRouter`, Motion (motion.dev) plus the View Transitions API, and a lazy-loaded Three.js avatar. The landing page is served at `/` and the app at `/app/#/…`; the base path is configurable for GitHub Pages. API types come only from `@wearhouse/contracts`. The backend (`apps/api`, FastAPI, `/api/v2`, 145 operations) is finished and tested, and the frontend must not change it.

## Users

- **Primary: Indonesian Gen Z, both men and women.** They live with Jakarta heat and sudden rain, own more clothes than they remember, and decide what to wear in a hurry. Their jobs are to discover clothes worth adding, own them provably, dress from what they already have, plan the week, and share looks with friends.
- **Staff:** catalogue editors, inventory managers, moderators and admins. They import, review, publish and retire products, manage media, sizes, offers and serialized units, moderate shares, and assign roles.
- **First real use: the capstone defense and live demo.** Lecturer Gilang Raka Rayuda Dewa, reviewers and examiners watch it with seeded and real-source data. The product is still built for real Gen Z users, so demo convenience never replaces a real flow, and nothing is faked for the examiners.

## Product Purpose

Wearhouse is a Steam-inspired fashion ecosystem. **Catalogue** is the store, **Wardrobe** is the library, **Community** is the friends layer, and **Profile** is your identity. A person browses a real-source catalogue, wishlists items, makes a simulated purchase, receives a private activation key, and redeems it once. The garment then becomes an owned item they can equip on an avatar, dress with weather-aware suggestions, plan across seven days, log as worn, and share.

**Priority: daily dressing.** When catalogue discovery and wardrobe use compete for space, help someone turn an owned garment into a look they plan or wear. For signed-out visitors and users with an empty wardrobe, lead with catalogue discovery and provide actions to redeem a key or add a garment.

Success means a new customer can complete that whole loop. A second customer can neither see the first one's private records nor claim the same unit. Staff can run the catalogue without code edits or fabricated entries. The experience reads as one coherent, delightful product on desktop, in Focus mode and on a phone.

## Positioning

Two connected centres share one fashion intelligence: discovering clothes that improve your wardrobe, and wearing the clothes you already own. Ownership is Steam's definition-and-instance model applied to garments. A product is shared metadata; an owned item is a private instance claimed with a one-time key. The public QR tag is discovery only. Suggestions are grounded in a real weather source (BMKG) and in your own wear history, and they always say how they were made.

## Operating Context

- Sampoerna University Senior Capstone (FYP) research system, also the base of the INFS4305 System Integration demo. Research titles keep the name "Digital Wardrobe"; the product is **Wearhouse** everywhere in the UI.
- Two presentations of the same routes: a desktop client (top nav, sidebars, dense grids) and **Focus mode** after Steam Big Picture (large rails, one focused tile, footer button hints), usable with mouse, keyboard and touch (no gamepad controls, owner decision 2026-11-26).
- Weather comes from BMKG for a location set as an `adm4` code, in Asia/Jakarta time. The horizon is about 3 days, and the source is shown as LIVE, CACHED or MANUAL.
- Identity is Neon Auth (Google plus email/password). Roles and capabilities are granted on the server, and staff work in a separate, capability-gated workspace.
- The catalogue is the H&M research snapshot (about 105k articles) with provenance and revisions. Product imagery is generated placeholders that staff can replace.

## Capabilities and Constraints

- Every screen maps to a real `/api/v2` endpoint; the full map is in the frontend prompt §7. Features in the owner mocks with no API behind them (Sale, Trending as such, Sets/Activewear categories, Cloud Sync, Downloads, chat) are omitted or mapped honestly (§8).
- Commerce is a **sandbox**: prices are simulated IDR, and nothing is charged, shipped or delivered.
- Activation keys are 16 base32 characters shown as `XXXX-XXXX-XXXX-XXXX`, redeemable once, and limited to 10 attempts per user per hour. Keys and tokens never enter URLs, storage, logs or analytics.
- Slots: 13 single-capacity, `wrist` and `ring` hold 2, and `accessory` holds 3. A dress clears top and bottom. Care states are ready, laundry, repair and stored, plus archived.
- There are two separate occasion vocabularies: suggestions use casual, campus, hangout, worship and wedding; the planner uses casual, work, formal, sport and event.
- Recommendations run in `heuristic_baseline` mode. They are labelled as a baseline, never as AI or trained.
- Settings are server-synced and versioned: language (en/id), theme, reduce motion, sound, wardrobe view, suggestions, notifications, community and beta.
- **Language:** before a signed-in user's `language` setting applies, the app follows the browser (`id` browsers get Indonesian, everyone else English). Signed-out visitors get a visible language switch remembered on the device. At onboarding, the language choice is pre-set to the current UI language and saved to the `language` setting, so the account does not flip to English after sign-in. Complete en and id catalogues ship together.
- Avatar body choice is a local UI preference and is not gender identity.
- Not decided: production hosting and cutover, which need the owner's go-ahead. The landing page and app run locally or on GitHub Pages until then.

## Brand Commitments

- Name: **Wearhouse**. Logos in `Assets/` (the house-and-ribbon mark, the wordmark on plum and on light, the app-icon tile) are used as supplied, with no recolouring beyond white or plum and no effects on the mark.
- Colour family: plum, aubergine and blush (TDD §5.1 base: paper `#faf6f3`, ink `#2b1624`, plum `#632947`, blush `#f1e0e6`). Focus mode is always the dark aubergine world.
- **Feminine-led, for everyone.** Plum and blush warmth and softness carry the brand. Users, garment categories and avatar bodies are never restricted or gendered.
- Structure and feel follow Steam: the Store, Library and Big Picture references in `Reference/`. The owner mocks in `Assets/` are mood and structure evidence, not pixel specs.
- Voice: warm, confident and playful, and honest about uncertainty.
- **Visual direction (owner's choice, 2026-11-26): the category standard, played straight.** After a bold and a safer re-roll, the owner chose a media-console home in plum over any bespoke metaphor world. Conventions are embraced without irony or smuggled quirk. The craft bar is the products it should sit alongside: Steam Big Picture / Steam Deck (focus rail, hints, overlays), the PlayStation 5 home (hero art repainted by the focused tile, cinematic transitions), Netflix / Apple TV (fast, crisp media rails) and Zalando / Zara (fashion-retail product, size, price and checkout clarity). The owner ruled out gamer neon and anything dark, murky or heavy, so the plum stays luminous.

## Evidence on Hand

- `Assets/`: logos plus four owner mocks (Discover, Wardrobe, Settings, and the open-wardrobe brand illustration). The mocks show features that do not exist, so they are never shipped as screenshots.
- `Reference/`: four Steam screenshots (Store, Store with account menu, Library, Big Picture home).
- Real data: about 105k H&M source products with provenance; real BMKG forecasts (a frozen Kemayoran sample exists); `GET /about` sources, licences and AI disclosure.
- Research results, to be stated exactly as measured: RQ3 is positive (0 false acceptances in 103,500 redemption attempts). RQ2's corrected run is positive under its pre-registered rule, with caveats. RQ1 is not positive. The UI must not overstate any of them.
- **Absent, and must not be fabricated:** real customers, testimonials, usage numbers, real prices or stock, real product photography, retailer partnerships, and model accuracy claims. Product imagery falls back to a slot silhouette marked "Image unavailable".

## Product Principles

1. **Honest by construction.** Simulated prices say "simulated", baselines say "baseline", estimates say "estimated", and weather past the forecast horizon says "Forecast unavailable". Trust is the product.
2. **Ownership is private and earned.** Only a private key claims an item. Discovery is public, possession is private, and privacy is the default in every social view.
3. **The selected thing drives the screen.** Following Big Picture, one focused object owns the page, and every input (mouse, keyboard, touch) reaches it equally.
4. **The server is the truth.** The client keeps drafts and preferences only. Planned is not worn, a wishlist is not ownership, and a cart is not inventory.
5. **Dressed for real life in Jakarta.** Suggestions answer to the actual forecast, the occasion and what is clean and ready, not to an idealised closet.

## Accessibility & Inclusion

WCAG 2.2 AA. Semantic DOM controls, never a canvas-only UI. Full keyboard and screen reader paths. 44 px targets, usable at 200% zoom. `prefers-reduced-motion` and the `reduce_motion` setting are both respected. Complete English and Indonesian. Avatar body options are separate from gender identity. Synthetic or generated imagery only: no real people's photos, and no third-party logos.
