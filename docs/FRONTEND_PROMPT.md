> **Historical document.** Paths here predate the `legacy/` relocation; see `docs/architecture/migration-inventory.md` §3 for the current locations.

# Frontend build prompt — Impeccable + Scrollcraft

How to use this file: run the three prompts **in order**, each in a fresh agent session opened at the
repo root (`Live Demo/`). Paste the **Shared Context** block together with each prompt; the agents need
it every time.

| Step | Skill | Builds | Route |
|---|---|---|---|
| A | `/impeccable` | The wardrobe app: weather, recommend, outfit selector, try-on, calendar, registration, demo controls. Also writes `PRODUCT.md` + `DESIGN.md`. | `/app/` |
| B | `/scrollcraft` | Scroll-driven landing page that tells the weather → outfit story and hands off to the app. Reads `PRODUCT.md` + `DESIGN.md`. | `/` |
| C | `/impeccable` (audit + polish) | Critique both against the contract and the acceptance list, fix, document. | both |

Build A before B: Scrollcraft should inherit the design system rather than invent one.

---

## SHARED CONTEXT (paste with every prompt)

```text
PROJECT
Digital Wardrobe — Live Demo (INFS4305 System Integration final project + FYP "Digital Wardrobe").
A weather-aware virtual wardrobe for Indonesian Gen Z. The backend is DONE and tested; you are
building the frontend only. Read these first, in this order:
  README.md
  docs/TDD_Digital_Wardrobe_Live_Demo.md      (§3 interfaces, §4 Phase 6–7, §5 edge cases)
  docs/openapi.json                            (exported OpenAPI 3 schema of the running API)
  docs/demo_script.md                          (the four live-demo runs the UI must support)
  Canva_-_download.png                         (visual prototype: desktop + mobile; local file in the repo root,
                                               not in git — ask the user for it if missing)
  backend/app/static/index.html                (current plain page: a working reference client for every call)

HARD RULES — compatibility
1. Do NOT change backend behaviour, response shapes, routes, or tests. The ONLY backend edit allowed is
   the static-serving hook in "Serving & build" below. `cd backend && python -m pytest` must still pass.
2. The browser talks ONLY to this server's /api/v1 (and /01/... scan links). Never call BMKG, Neon, or any
   database directly. The server is the only component that talks to BMKG (TDD §1.1) — this is graded.
3. Use the real API. No mock data in the shipped app. A dev-only fixture mode is fine if it is off by default
   and clearly labelled.
4. Generate TypeScript types from docs/openapi.json (e.g. `npx openapi-typescript docs/openapi.json -o
   frontend/src/api/schema.d.ts`) and hand-write types for the untyped responses listed below
   (recommend, weather, health, avatar, scan, interface-log). Keep the API client in ONE module.
5. Every write (POST/DELETE) sends header `X-API-Key: <key>`. Key comes from `import.meta.env.VITE_API_KEY`,
   default "demo-key". It is a static demo key for one synthetic user, not a secret — but never put any
   other credential in the frontend.
6. Synthetic data only. No photos of real people, no real brand names/logos. BMKG must be credited wherever
   weather is shown: render `weather.credit` (text: "Weather data: BMKG ...") — never hide it.

STACK
Vite + TypeScript. Use a component framework if you want (React is fine); keep the output static files.
Three.js (+ GLTFLoader) for the avatar. No server-side rendering, no Node server at runtime.
Folder: frontend/  (package.json, vite.config.ts, src/, public/). Multi-page Vite build:
  frontend/index.html      → landing (Scrollcraft, step B; a minimal placeholder until then)
  frontend/app/index.html  → the app (Impeccable, step A)
Inside the app use HASH routing (#/wardrobe, #/plan, ...) so no server fallback rules are needed.

SERVING & BUILD (the one allowed backend edit)
- Dev: Vite on :5173 with a proxy for "/api", "/01", "/docs", "/openapi.json" → http://127.0.0.1:8000.
  Same-origin in dev and prod means NO CORS config is needed.
- Prod: `npm run build` → frontend/dist. In backend/app/main.py, inside create_app(), AFTER all
  app.include_router(...) calls, replace the existing `@app.get("/") def index()` route with:

      from fastapi.staticfiles import StaticFiles
      FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
      if FRONTEND_DIST.is_dir():
          app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
      else:  # no build yet: keep serving the plain page
          @app.get("/", include_in_schema=False)
          def index():
              return FileResponse(STATIC_DIR / "index.html")

  The mount must come last so /api/v1/*, /01/*, /docs and /openapi.json keep winning. Do not delete
  backend/app/static/index.html (it is the fallback and a debug client).
- Optional standalone hosting (e.g. GitHub Pages): VITE_API_BASE points at the server, and the server needs
  CORS_ORIGINS=<that origin> in backend/.env. Default VITE_API_BASE = "" (same origin).
- Start the backend for development: `.\run_demo.ps1 -Offline` (SQLite + frozen real BMKG sample, no
  internet needed) or `.\run_demo.ps1` (Neon via backend/.env). Swagger: http://127.0.0.1:8000/docs

DOMAIN VOCABULARY (exact strings — the API rejects anything else with 422)
slots:     top | bottom | dress | outer | footwear | accessory      (a dress fills BOTH top and bottom)
occasions: campus | casual | worship | formal | wedding
styles:    casual | smart | formal | modest | sporty | street
weather.source: LIVE | CACHED | MANUAL | MANUAL_REQUIRED
fault modes: none | timeout | http500 | malformed | missing_fields
Garment attrs: color_hex "#RRGGBB", style, rain_suitable, heavy, long_sleeve, long_bottom, formality 1–5
Rules the server applies (show them, don't re-implement them as the source of truth):
  rain → needs rain-suitable footwear or outer; hot (t ≥ 32 °C) → no heavy garments;
  worship → long sleeves + long bottom; formal → formality ≥ 2; wedding → formality ≥ 3.

API CONTRACT (base /api/v1; GETs need no key; errors are {"detail": string} except 422 which is
{"detail": [ {loc, msg, type}, ... ]})
GET  /health → {status, db: "neon"|"postgresql"|"sqlite", weather_mode: "mock"|"live", fault, weather_cache}
GET  /wardrobe → Garment[]
     Garment = {id, name, slot, attrs:{...all 7 attrs, always filled}, gtin|null, serial|null,
                origin:"manual"|"registered", times_recommended, times_chosen, last_worn_at:"YYYY-MM-DD"|null}
POST /garments {name(1–120), slot, attrs?:{any subset of attrs; no other keys}} → 201 Garment | 422
DELETE /garments/{id} → 204 | 404 | 409 (used in a saved outfit; the message does not name it, so find it via GET /outfits)
POST /outfits/recommend {occasion, when?: ISO datetime (naive = Jakarta local time WIB), adm4?: "31.71.03.1001",
                         manual_weather?: {rain: bool, hot: bool}}
  → 200 normal: {weather:{source, fetched_at|null, at, local_time:"YYYY-MM-DD HH:MM WIB", rain, hot,
                 t|null, humidity|null, description, note, credit|null},
                 context:{rain, hot, occasion},
                 outfits:[{rank, score, compat, pref, recency, items: Garment[]}]   (0–5, best first)
                 message: string|null}       (message is set when outfits is empty — show it)
  → 200 cold failure: {weather:{source:"MANUAL_REQUIRED", note, ask:["rain","hot"], credit},
                       outfits: [], message}
     UI must then show a two-tap prompt (Rainy/Dry, Hot/Normal) and resend with manual_weather.
     When manual_weather is sent BMKG is skipped and source = "MANUAL" (t, humidity, fetched_at, credit null).
  NOTE: every recommend call increments times_recommended (it feeds the preference score). Only call it on an
  explicit user action (button, occasion/day change) — never on hover, keystroke, polling or prefetch.
POST /outfits {items: garment_id[] (1–6), label?: string(≤60), planned_for?: "YYYY-MM-DD", occasion?}
  → 201 Outfit{id, label, planned_for, occasion, items: Garment[]} | 409 slot clash | 422 unknown garment
GET  /outfits?week=2026-W48 → Outfit[] planned in that ISO week (omit week → all saved outfits) | 422 bad week
DELETE /outfits/{id} → 204 | 404
POST /outfits/{id}/wear {worn_on?: "YYYY-MM-DD"} → 204   ("Wear this" = POST /outfits then POST /wear)
GET  /weather?adm4= → {adm4, source, fetched_at, note, timezone, credit,
                       slots:[{at, local_time:"Tue 24 Nov 14:00", t, humidity, description, rain, hot}]}
                     or {adm4, source:"MANUAL_REQUIRED", note, slots:[], credit}
     The forecast covers ~3 days; a `when` beyond it returns MANUAL_REQUIRED ("no forecast entry near the
     requested time") — the calendar must handle that for later days.
GET  /avatar/{outfit_id} → {outfit_id, body:{model:"female_base.glb"|"male_base.glb", gender},
                            slots:{<slot>:{garment_id, name, template, texture|null, tint:"#RRGGBB"}},
                            covers: {"dress":["top","bottom"]} | {}}
     template ∈ top_shirt.glb, bottom_pants.glb, bottom_skirt.glb, dress.glb, outer_jacket.glb,
     footwear_sneaker.glb, null (accessory). These GLB files DO NOT exist yet (see avatar section).
POST /garments/activate {code} → 201 Garment | 400 {"detail":"invalid code"} | 429 {"detail":"too many attempts, try again later"}
     Codes look like XXXX-XXXX-XXXX-XXXX; case and dashes are ignored. Show the generic error as-is.
GET  /scan/01/{gtin}/21/{serial} → {gtin, serial, name, category, slot, color_hex, style, image_url|null,
                                    digital_link, wishlist_only:true, ownership} | 404
GET  /01/{gtin}/21/{serial} is the backend-rendered page a phone opens from the tag QR (leave it alone).
GET  /codes/{serial}/qr.svg → image/svg+xml, NEEDS the API key → fetch() it with the header and show it via a
     blob URL (an <img src> cannot send headers).
GET  /metrics/interface-log?limit=50&interface=I1..I6 → [{id, at, interface, route, status, latency_ms,
                                                         weather_source, note}] newest first (safe to poll)
GET  /metrics/summary → {rows_per_interface, bmkg_calls_last_24h}
Admin (key required): POST /admin/fault {mode} · POST /admin/weather/clear-cache ·
     POST /admin/codes {gtin(14 digits), count 1–20} → [{gtin, serial, activation_code}] (shown ONCE) ·
     GET /admin/products → [{gtin, name, slot}] · POST /admin/reset (wipes outfits/wear/registrations/log, re-seeds)

DATA FACTS
- One synthetic user, 28 seeded garments (5 top, 6 bottom, 3 dress, 4 outer, 5 footwear, 5 accessory).
  Seeded garments have NO images: only name, slot and attrs (incl. color_hex). Seed ids are stable UUIDs.
- 4 retail products exist for the QR/activation flow (GET /admin/products).
- "Saved outfits 1 2 3" (Canva) = outfits whose label is "1", "2" or "3". Labels are not unique on the
  server: to overwrite slot 2, DELETE the existing label-"2" outfit, then POST the new one; if several
  exist, the newest wins.
- Location default: adm4 31.71.03.1001 (Kemayoran, Jakarta Pusat), timezone Asia/Jakarta (WIB).
```

---

## PROMPT A — `/impeccable` · build the app (`/app/`)

```text
/impeccable

Build the complete Digital Wardrobe web app at frontend/app/ (route /app/), following the SHARED CONTEXT
exactly. It replaces the plain page at backend/app/static/index.html for users (keep that file as the
fallback). First produce PRODUCT.md and DESIGN.md at the repo root from the brief below, then build.

PRODUCT BRIEF
Users: Indonesian Gen Z students (campus, worship, weddings, hot humid weather, sudden rain). Also the
course examiners watching a live demo: they must SEE the system integration working (weather source,
fallbacks, interface log) without opening dev tools.
Job: "Tell me what to wear today (or on a planned day) that won't get rained on or cook me, for this
occasion, from clothes I actually own." Second job: register a newly bought garment by its tag (QR +
private activation code) so it appears in the wardrobe exactly once.
Tone: warm, calm, a little playful; confident about the weather, honest about uncertainty.

VISUAL DIRECTION — match the Canva prototype (Canva_-_download.png), then make it production-grade
- Soft blush/pink surfaces, deep plum headings, rounded cards, generous whitespace; desktop = two panes
  (Virtual try-on left, Outfit selector right) under a date header + 7-day week strip; mobile = avatar on
  top, outfit selector as a pull-up bottom sheet that retracts after a selection.
- Elements from the prototype to keep: date + clock header; Mon–Sun week strip with the selected day
  highlighted; "Camera | 3D Avatar" segmented toggle; avatar; "Saved outfits 1 2 3" chips; outfit selector
  grouped by slot (Shirt/Skirt/Pants in the mockup → use the real slots); "Color & variations" swatches.
- Accessible: WCAG AA contrast, visible focus, full keyboard use, prefers-reduced-motion, 44px touch targets,
  Indonesian-friendly copy (English UI is fine; dates in id-ID or en-GB format, times in WIB).

SCREENS & BEHAVIOUR (every item maps to a real endpoint)
1. Today / Try-on (default, #/)
   - Weather badge for the selected day/time: source LIVE (fresh) / CACHED (show "from cache · fetched
     HH:MM" and the note, e.g. "fallback after timeout") / MANUAL / MANUAL_REQUIRED. Show t °C, humidity,
     description, rain/hot chips, BMKG credit.
   - Occasion picker (5 occasions). "Recommend" button → POST /outfits/recommend. Show up to 5 ranked
     outfits as cards (items, swatches, and a short "why": rain-ready / no heavy layers / dress-code ok,
     derived from context + item attrs, plus score breakdown compat/pref/recency in a details popover).
   - Empty result → show `message` with a CTA to add a rain shoe/outer or suitable item.
   - MANUAL_REQUIRED → inline two-tap card (Rainy/Dry, Hot/Normal) → resend with manual_weather.
   - Card actions: "Try on" (updates avatar; no server call), "Wear this" (POST /outfits with
     planned_for = selected day, then POST /outfits/{id}/wear; optimistic UI + refresh wardrobe),
     "Save to 1/2/3".
2. Outfit selector (right pane / mobile sheet)
   - Browse the wardrobe grouped by slot; tap to compose an outfit manually. Mirror the slot rule in the UI
     (a dress clears top+bottom and vice versa) and let the server decide: POST /outfits shows 409 text.
   - "Color & variations": swatches of the color_hex values in the active slot; filters the grid.
3. Week planner (#/plan)
   - The 7-day strip selects a day; `when` = that day 09:00 WIB unless the user picks a time.
   - GET /outfits?week=YYYY-Www for planned outfits; plan = POST /outfits with planned_for.
   - Days beyond the ~3-day forecast: expect MANUAL_REQUIRED; say "forecast not available yet" kindly.
4. Wardrobe (#/wardrobe)
   - Grid/list with filters by slot and attribute; usage stats (times_chosen/times_recommended, last worn).
   - Add garment form (name, slot, colour picker, style, rain/heavy/long sleeve/long bottom, formality 1–5);
     map 422 field errors to the inputs. Delete with confirm; on 409 show the server message and list the saved outfits that use it (from GET /outfits).
5. Register a garment (#/register) — FYP RQ3
   - "Camera" mode of the Camera | 3D Avatar toggle = QR scanner: getUserMedia + BarcodeDetector (fallback:
     a small JS QR decoder, or paste the link). Parse the GS1 Digital Link /01/{gtin}/21/{serial}, call
     GET /scan/... and show the product card labelled "Wishlist only — scanning never gives ownership".
   - Activation code input (auto-format XXXX-XXXX-XXXX-XXXX, paste-friendly) → POST /garments/activate.
     400 → the generic "invalid code" (never hint which part was wrong); 429 → cooldown message.
     Success → animate the garment into its slot in the wardrobe.
   - Camera needs HTTPS or localhost: detect and explain otherwise.
6. Saved outfits 1 2 3 — chips under the avatar; tap = load into avatar; long-press/menu = overwrite/delete
   (see DATA FACTS for the label convention).
7. Demo controls (#/demo, also a collapsible drawer; this is for the live presentation)
   - Health line (db, weather_mode, fault). Fault selector → POST /admin/fault. "Clear weather cache".
     "Issue tag code" (product picker → POST /admin/codes; show code once + QR via the blob-URL fetch).
     "Reset demo data" with confirm.
   - Interface log panel: poll GET /metrics/interface-log every 3 s while visible; colour by interface
     (I1 client, I2 BMKG, I5 scan, I6 measure.py); highlight failed I2 rows; show BMKG calls in 24 h from
     /metrics/summary.
   - The four runs in docs/demo_script.md must be doable from this app alone, in that order.

3D AVATAR (TDD Phase 7) — must never block outfit selection
- Data: GET /avatar/{outfit_id} for saved outfits; for unsaved recommendations build the same structure
  client-side from the items (template by slot; bottom → bottom_pants.glb if attrs.long_bottom else
  bottom_skirt.glb; tint = color_hex; dress covers top+bottom).
- Load frontend/public/models/<body model> and <template>.glb with GLTFLoader; tint garment materials with
  `tint`; apply `texture` when non-null. The GLBs don't exist yet: create simple low-poly placeholder GLBs
  (or procedural Three.js meshes) named exactly as the templates so real models can be dropped in later.
- Fallback: a 2D layered SVG/canvas figure (body + tinted slot layers) used when WebGL is unavailable,
  a model fails to load, or the frame budget is missed. Lazy-load Three.js so the app is usable before it
  arrives. Targets: outfit switch < 300 ms, ≥ 45 fps desktop / ≥ 30 fps mid-range phone.
- Garment imagery: seeded garments have no images. Use tinted slot silhouettes (SVG) by default; optional
  generated product renders may live in frontend/public/garments/<slug-of-name>.webp keyed by garment name,
  synthetic and logo-free, always with the silhouette fallback.

ENGINEERING REQUIREMENTS
- One typed API client (src/api/) with: base URL, key header, JSON + 204 handling, {"detail"} error parsing
  (string or 422 array), AbortController per request, and a 10 s client timeout (the server's own BMKG
  deadline is 3 s, so a fault answer arrives in ~3–4 s: show a "checking BMKG…" state, not a frozen UI).
- State: refetch after mutations (the server is the source of truth; no websockets).
- No console errors with BMKG down (fault on) or the server off (show a clear offline state).
- Loading / empty / error states for every screen. Recommend → rendered < 1 s on a warm cache.
- Tests: Vitest for the API client + slot-composition logic; Playwright smoke test against
  `.\run_demo.ps1 -Offline` covering: recommend LIVE→CACHED, fault timeout → CACHED, cold failure →
  manual two-tap → MANUAL, issue code → activate → second activate rejected.
- Add npm scripts: dev, build, preview, test, test:e2e. Add a "frontend" job to .github/workflows/ci.yml
  (npm ci, typecheck, unit tests, build) without touching the existing jobs.
- Update README.md with frontend run/build instructions.

DONE WHEN
- Every endpoint in the SHARED CONTEXT is used somewhere in the UI (except /01/... which is backend-rendered).
- docs/demo_script.md runs end to end from /app/.
- `cd backend && python -m pytest` and `cd frontend && npm run build && npm test` pass; CI is green.
- PRODUCT.md and DESIGN.md exist at the repo root (Scrollcraft reads them next).
```

---

## PROMPT B — `/scrollcraft` · landing page (`/`)

```text
/scrollcraft

Build the landing page for Digital Wardrobe at frontend/index.html (route /), inside the existing Vite
project from step A, following the SHARED CONTEXT. Read PRODUCT.md and DESIGN.md (brand inputs) and the
Canva prototype first. Do not change the app at /app/ or any backend behaviour.

INTERVIEW ANSWERS (use these instead of asking)
- Brand: Digital Wardrobe. A weather-aware virtual wardrobe for Indonesian Gen Z, built as a university
  capstone + System Integration project (Sampoerna University).
- Audience: (1) students in Jakarta who dress for heat and sudden rain; (2) the examiners at the live demo.
- Goal of the page: in under a minute of scrolling, make people feel the problem ("weather-blind outfits")
  and understand the integration (BMKG forecast → server → rules → 5 outfits, with a fallback when BMKG
  fails), then send them into the app. Primary CTA: "Open my wardrobe" → /app/. Secondary: "Watch the
  live demo" → /app/#/demo.
- Emotional peak: the sky turns and rain arrives mid-scroll; the avatar's outfit swaps to a rain-ready one
  (sandals → rain sandals, add the clear raincoat) as the forecast badge flips to "Hujan Ringan".
- Signature move: the scroll IS the 3-day forecast timeline. Scrubbing advances BMKG time slots
  (morning → afternoon rain → hot noon); light, sky colour, temperature readout and the avatar's outfit
  change per slot. Use the frozen real BMKG sample's shape for the sequence (backend/fixtures/
  bmkg_real_sample.json: 21 slots, including "Hujan Ringan" at 14:00 WIB) — label it as an example forecast.
- Story beats (one section each, pinned where it helps):
  1. Hero: "Dress for the weather you'll actually get." Avatar + live badge (see Live data).
  2. The problem: the same outfit across a rainy and a 33 °C day; outfits that ignore BMKG fail.
  3. The forecast timeline (signature move).
  4. How it works: client → server → BMKG (cached 3 h, validated) → rules (rain / heat / dress code) →
     top 5 outfits. Show the fault ladder LIVE → CACHED → MANUAL as a simple, honest diagram.
  5. Own it with one tap: QR tag shows the product (wishlist only) + a private one-time code adds it to your
     wardrobe exactly once.
  6. Plan the week: the Mon–Sun strip from the prototype; saved outfits 1 2 3.
  7. CTA + credits: "Weather data: BMKG" and a link to docs/RESULTS.md metrics on GitHub
     (https://github.com/crimSun-dev/LIVE-DEMO/blob/main/docs/RESULTS.md). Quote no numbers on the page;
     link to the measured results instead.
- Mood: soft blush and plum from DESIGN.md, a Jakarta skyline silhouette, humid haze, warm sun, monsoon
  rain. Calm and premium, not loud.

ASSETS
- Generated imagery is fine (kie.ai): stylised 3D-avatar look matching the Canva prototype, synthetic
  people only, no real faces, no brand logos, no text baked into images. Garments must look like the seeded
  ones (names/colours from backend/app/seed_data.py), e.g. "Pink oxford shirt #F4B6C2", "Clear lightweight
  raincoat #DDE8EE", "Rubber rain sandals #3C6E71".
- Put assets in frontend/public/landing/. Keep the total landing payload reasonable: compress, lazy-load
  below the fold, use poster frames for any video.

LIVE DATA (optional enhancement, must degrade silently)
- Hero badge may call GET /api/v1/weather (no key needed) once on load and show source + current slot
  ("LIVE · 31 °C · Cerah Berawan · BMKG"). If the server is unreachable, fall back to the example forecast
  and hide the badge's source. Never call /outfits/recommend from the landing page (it mutates stats).

REQUIREMENTS
- Separate mobile composition (not a squeezed desktop), reduced-motion version with static frames,
  semantic HTML, keyboard-reachable CTAs, no layout shift, works with JS disabled (content readable).
- Lives in the same Vite multi-page build; `npm run build` outputs dist/index.html + dist/app/index.html.
- Verify by screenshotting desktop, mobile and reduced-motion scroll states, then hand back to Impeccable.
```

---

## PROMPT C — `/impeccable` · audit and polish

```text
/impeccable

Audit and polish the whole frontend (landing at /, app at /app/) against PRODUCT.md, DESIGN.md, the Canva
prototype and the SHARED CONTEXT. Then fix what you find and update DESIGN.md from the shipped result.

Check in this order and fix each failure:
1. Contract: every request matches docs/openapi.json + the SHARED CONTEXT shapes; keys sent on every write;
   422 arrays and {"detail"} strings rendered; 204s handled; no call to BMKG/Neon from the browser;
   recommend only on explicit user action; no /outfits/recommend from the landing page.
2. Demo path: run docs/demo_script.md runs 1–4 against `.\run_demo.ps1 -Offline`, then against Neon
   (`.\run_demo.ps1`). Weather source always visible; BMKG credit always visible; fault answers within ~4 s
   with a visible pending state; MANUAL_REQUIRED two-tap works; activation reuse shows the generic error.
3. Resilience: server stopped → clear offline state, no console errors; WebGL disabled → 2D avatar
   fallback; camera denied → paste-link fallback; forecast-less day → manual prompt.
4. Quality: accessibility (AA contrast, focus, keyboard, screen-reader labels for badges and swatches),
   responsive desktop/tablet/mobile, reduced motion, performance (recommend render < 1 s warm, avatar
   switch < 300 ms, ≥ 30 fps on mobile), copy consistency.
5. Repo hygiene: `cd backend && python -m pytest` still green; `cd frontend && npm run build && npm test`
   green; CI green including the new frontend job; README frontend section accurate; nothing secret committed.
Report findings ranked by severity, then the fixes made.
```

---

## Why the prompt is shaped this way (for you, not the agents)

- **Untyped responses are written out in full.** `/recommend`, `/weather`, `/avatar`, `/health` and `/scan`
  return plain dicts, so `docs/openapi.json` doesn't describe them; the shapes above are copied from
  `backend/app/routers/*.py`.
- **Same-origin serving** (Vite proxy in dev, `frontend/dist` mounted last in prod) avoids CORS and keeps
  `/api`, `/01`, `/docs` working. The mount is the only backend edit, and it falls back to the current page.
- **Recommend only on explicit actions.** Each call increments `times_recommended`. Calling it on hover
  or polling would skew the preference score and the M-metrics.
- **QR image via fetch + blob.** That endpoint needs the API key header, which an `<img>` tag can't send.
- **Hash routing inside `/app/`.** Deep links work without server fallback rules.
- **Placeholder GLBs named exactly as the `/avatar` templates.** Real models can be dropped in later without
  touching code or the API.
