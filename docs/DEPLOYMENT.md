# GitHub Pages + Neon Functions + Neon Postgres

Frontend: https://crimsun-dev.github.io/LIVE-DEMO/
Wardrobe app: https://crimsun-dev.github.io/LIVE-DEMO/app/

Vite source lives in `legacy/web/` (moved from `Frontend/frontend/`). Pages installs its locked dependencies,
runs unit/type checks, and builds both HTML entries with base `/LIVE-DEMO/` and
VITE_API_BASE set from the public API_BASE_URL repository variable.

The public API runs directly on Neon Functions, on the existing `demo` branch of
`digital-wardrobe-live-demo`. Neon injects the private DATABASE_URL at runtime.
No separate hosting provider is required. The Function origin is:

https://br-red-star-bion9m3g-wardrobeapi.compute.c-5.ap-southeast-1.aws.neon.tech

## Source and compatibility

`legacy/neon/index.mjs` implements the existing `/api/v1` routes, GS1 scan pages,
QR SVGs, and Swagger documentation. Neon Functions use Node.js, so this adapter
runs the public API in JavaScript. `legacy/python/` remains the Python implementation
for local demos, SQLite fallback, course tests, and measurement.

The adapter reuses existing tables and data. An additive `neon_demo_state` table
persists weather caches and demo fault settings across Function restarts.
Scoring is checked against 20 reference cases from the Python implementation:
every occasion/rain/heat combination.

## Deploy

Install with `npm ci --prefix legacy/neon`, then:

```powershell
neon functions deploy wardrobeapi --project-id mute-snow-39846153 --branch demo --src legacy/neon/index.mjs --env WEATHER_MODE=live
neon functions get wardrobeapi --project-id mute-snow-39846153 --branch demo
```

The first deployment sets DEMO_API_KEY privately; subsequent deployments preserve
it. The frontend sends the existing synthetic demo key for protected calls. Never place DATABASE_URL
or Neon management credentials in the browser, source control, or Pages variables.

GitHub Actions variable API_BASE_URL contains the public Function origin. Run
Deploy GitHub Pages after changing that variable. The Pages artifact includes
only the static frontend and public API URL. CORS allows the Pages origin.

## Verification

`/api/v1/health` reports `db: neon` and `runtime: neon-functions`.
`/api/v1/wardrobe` returns the persisted wardrobe.

```powershell
npm test --prefix legacy/neon
npm test --prefix legacy/web
npm run typecheck --prefix legacy/web
```

`legacy/neon/test-live.mjs` tests CORS, authorization, recommendations, outfits,
wear, wardrobe writes, registration, QR, weather fallback, and metrics. It resets
data and refuses to run unless TEST_API_URL is the dedicated
`br-noisy-frog-bivp6wyg` test branch. Never run it against the demo database.

This remains the synthetic single-user demo. Its write key also grants access
to demo controls, including reset; it is not a multi-user wardrobe service.

The built frontend smoke tests verify images, navigation, live recommendations,
wardrobe loading, retailer products, and mobile layout against the Neon API.

QR scanning and key entry are alternative registration methods. Both consume the
same tag once. Opening a tag URL registers through a POST from its scan page;
merely retrieving tag metadata does not redeem it. Fault simulations automatically
expire after 10 minutes. The app starts at the current Jakarta time and selects
real BMKG forecast slots within three hours of the requested time.

```powershell
# After the Pages build (tools/build_legacy_pages.py), from legacy/web:
npx playwright test --config playwright.pages.config.js
# To verify the published site instead:
$env:PAGES_TEST_URL='https://crimsun-dev.github.io/LIVE-DEMO/'
npx playwright test --config playwright.pages.config.js
```


## Wearhouse v2 (foundation): not deployed by this change

GitHub Pages and the Neon Functions adapter above keep serving **legacy v1**. Wearhouse v2 ships as an OCI image built from `apps/api/Dockerfile`, with migrations as a separate release command. The order is in `docs/runbooks/v2-operations.md`, and it was verified locally: see `docs/architecture/foundation-readiness.md`.

No v2 host, managed database, OIDC provider or production secret has been provisioned. Those are deployment inputs, listed in `docs/architecture/runtime-identity.md` §4. **Never point v2 at the legacy Neon `demo`/`test` branches.** v2 refuses them, and legacy refuses v2 databases. The production cutover is a later change.
