# Wearhouse v2 API (`apps/api`, package `wearhouse`)

This is the canonical Python/FastAPI v2 backend. It provides:

- verified identities, with roles granted on the server, and sign-in through Neon Auth (Google)
- Steam-like accounts: handles, profiles, per-section privacy, friends, blocks, export and deletion
- source-backed products and serialized garment units
- public tag lookup that is **discovery only**
- private, one-time redemption of activation keys
- owner-scoped reads of owned items

It is separate from the legacy v1 demo under `legacy/`. It shares no database, config, port or code with it, and it never imports it.

## Layout

```text
src/wearhouse/
  bootstrap/        config, read-only startup checks, composition root, app factory, CLI, ASGI entry
  identity/         principals, roles/capabilities, OIDC/EdDSA resource-server adapter, account mapping, revocation
  accounts/         profiles, handles, privacy policy, friends/requests/blocks, export, deletion (tombstone)
  catalogue/        source products, immutable revisions, bulk import (hm-articles@1), publication, collections,
                    public browse (RevisionReader is its public read interface)
  ownership/        units, credentials, encrypted delivery, discovery, redemption, owned items, fulfilment
  commerce/         sandbox offers, wishlist, cart, checkout, orders/receipts, key renewal, cancellation
  wardrobe/         unified wardrobe (verified + declared), care/slots, shelves, looks + revisions, planner, wear
  social/           look shares, week sharing, friends feed, derived notifications, profile showcase
  recommendations/  typed ranker ports, heuristic baseline + outfit suggester (labelled; no trained-model claims)
  weather/          BMKG contract, gateway service (fresh cache -> live -> stale <=6 h -> MANUAL), cache, location
  platform/         errors, crypto, idempotency, cursors, HTTP edge, outbox, unit of work (no business rules)
  testing/          TEST-ONLY factory, fixed-principal adapter, local RS256 issuer
migrations/         Alembic revisions 0001-0009 (forward-only); run only by the release command
tests/              pytest suite (PostgreSQL tests need a disposable server)
```

Inside each module, routers call application services, which call domain rules and ports. The SQL and OIDC adapters are wired together only in `bootstrap`. `tests/test_boundaries.py` checks these rules against the real import statements.

## Setup (Windows paths contain spaces and an apostrophe; keep them quoted)

```powershell
py -3.11 -m venv apps\api\.venv
apps\api\.venv\Scripts\python.exe -m pip install -r apps\api\requirements-dev.lock
apps\api\.venv\Scripts\python.exe -m pip install --no-deps -e apps\api
```

`tools\dev_api.ps1` does the same automatically the first time you run it.

## Database, roles and migration

1. Provision a **dedicated** PostgreSQL database for each environment, with two roles: a migration owner and a least-privilege runtime role. See `deploy/provision_roles.sql`.
2. Run the release migration:
   ```powershell
   $env:WEARHOUSE_MIGRATION_DATABASE_URL = "postgresql://wearhouse_migrator:...@host/wearhouse_dev"
   wearhouse migrate --environment development --runtime-role wearhouse_runtime
   ```
   The migration installs an immutable environment marker and grants the runtime role only the privileges listed in `bootstrap/schema.py`.

   It refuses to run when the target is:
   - a legacy v1 demo database
   - a database registered for a different environment
3. Startup **never** migrates or seeds. Before serving, it checks:
   - connectivity
   - that the target is not a legacy database
   - the environment marker
   - schema head `0009_object_management`
   - that the runtime role is not over-privileged and has every required privilege

   Any failure stops it with an actionable error.

## Configuration

The API reads only `WEARHOUSE_*` environment variables (see `.env.example`). It never reads a `.env` file.

`staging` and `production` are deployment environments, and they fail closed:

- an https issuer and an audience are required
- a delivery secret is required
- the OIDC adapter is required
- the local JWKS file is not allowed
- the test adapter is not allowed

The provider's token contract is in `docs/architecture/runtime-identity.md`.

Request rate limits (sliding 60 s windows, **per API process**; with N instances the effective ceiling is N times the value):

| Variable | Default | Layer |
|---|---|---|
| `WEARHOUSE_RATE_IP_PER_MIN` | 600 | every request per client IP (edge; `WEARHOUSE_TRUSTED_PROXIES` decides whose `X-Forwarded-For` counts) |
| `WEARHOUSE_RATE_GLOBAL_PER_MIN` | 6000 | every request, process-wide (edge) |
| `WEARHOUSE_RATE_WRITES_PER_MIN` | 120 | authenticated `POST`/`PUT`/`PATCH`/`DELETE` per verified user, checked after the token verifies (fresh tokens do not reset it) |

A refused request gets `429 RATE_LIMITED` with `Retry-After`. `/health` and `/health/ready` are exempt. `0` disables a layer outside deployments; staging and production refuse `0`. Redemption keeps its own database-backed limits, which are shared across processes.

## Run

```powershell
.\tools\dev_api.ps1 -CheckOnly      # config + startup checks
.\tools\dev_api.ps1                 # http://127.0.0.1:8100/api/v2/docs
```

## Routes (`/api/v2`)

| Method/path | Principal | Behaviour |
|---|---|---|
| `GET /health` | public | liveness |
| `GET /health/ready` | public | environment, schema and role checks (no secrets) |
| `GET /me` | verified user | local account, server-granted capabilities, `handle` and `needs_onboarding` |
| `GET`/`PATCH /me/profile`, `GET`/`PUT /me/privacy` | verified user | handle (7-day change interval, 30-day hold), display name, bio, avatar (preset or the provider picture); profile/wardrobe/friends-list visibility |
| `GET /profiles/{handle}` (`/wardrobe`, `/friends`) | public or signed in | privacy-filtered projections. Blocked, deleted and unknown handles all return the same 404, and wardrobes never show serials, ids or exact times |
| `GET /users/search?q=` | onboarded user | prefix of at least 3 characters or `@exact`, at most 20 results |
| `POST /me/friend-requests` (+ `/accept`, `/decline`, `DELETE` to cancel), `GET /me/friends`, `DELETE /me/friends/{handle}`, `GET`/`PUT`/`DELETE /me/blocks[/{handle}]` | onboarded user | friend lifecycle and blocks. Sending needs an `Idempotency-Key`; 50 sends per 24 h, 200 pending, 1000 friends, 1000 blocks |
| `POST /me/sessions/revoke-all`, `GET /me/export`, `DELETE /me` | verified user | sign out everywhere; JSON export (5 per hour); deletion (needs a sign-in within the last 5 minutes and your typed handle) |
| `POST /admin/source-products` | catalogue_editor/admin | ingest one permitted source-backed product (immutable revisions) |
| `POST /admin/catalogue/import-jobs`, `GET /admin/catalogue/import-jobs/{id}` | catalogue_editor/admin | bulk import of source CSV rows (mapping `hm-articles@1`, up to 5000 rows / 10 MB). Each row is `created`, `revised`, `unchanged` or `rejected`, in its own transaction |
| `GET /admin/catalogue/review`, `GET /admin/catalogue/products/{id}`, `POST …/{id}/publish` `{revision_id}`, `POST …/{id}/retire` | catalogue_editor/admin | review queue, every revision, publish a specific revision, retire (hidden from browse; owned items and tag lookups remain; issuance stops). All audited |
| `GET`/`PUT`/`DELETE /admin/catalogue/collections[/{slug}]` | catalogue_editor/admin | featured collections: title plus an ordered product list, replaced as a whole by `PUT` |
| `GET /catalogue/products` (`q`, `category`, `colour`, `slot`, `sort=newest\|name`, `limit`, `cursor`), `GET /catalogue/products/{id}`, `GET /catalogue/facets`, `GET /catalogue/collections[/{slug}]` | public | published products only. Literal substring search, signed cursors bound to the filter, facts and labelled annotations, media only when `rights.public_display` is true |
| `GET /admin/commerce/offers`, `PUT`/`DELETE /admin/commerce/offers/{product_id}` | catalogue_editor/admin (`commerce:offers`) | sandbox price (IDR, 1-100,000,000) and stock (0-100,000); audited. Nothing is ever charged |
| `GET /commerce/products/{id}/offer` | public | sandbox price and `in_stock` of a published product (no stock count), labelled `sandbox: true` |
| `GET`/`PUT`/`DELETE /me/wishlist[/{product_id}]`, `GET`/`PUT`/`DELETE /me/cart[/{product_id}]` | verified user | wishlist (500), cart (20 lines, quantity 1-5) with current sandbox totals |
| `POST /me/checkout` `{expected_total_idr}` | verified user | requires `Idempotency-Key`. All-or-nothing: offer row locks, stock, price snapshots, one buyer-bound unit per item, encrypted key delivery for the buyer, cart cleared. `PRICE_CHANGED`, `OUT_OF_STOCK`, `NOT_AVAILABLE`, `CART_EMPTY` change nothing |
| `GET /me/orders[/{id}]`, `GET /me/orders/{id}/units/{unit_id}/key`, `POST …/renew-key`, `POST /me/orders/{id}/cancel` | buyer | receipts never contain keys; the key endpoint reveals one (audited); renewal revokes the old key; cancel works while nothing is claimed (keys revoked, units retired, stock restored) |
| `GET /wardrobe/slots` | public | slot registry: capacities and `dress` exclusions |
| `GET`/`POST /me/wardrobe/items`, `GET`/`PATCH /me/wardrobe/items/{id}`, `PUT`/`GET …/{id}/photo` | owner | verified (claimed) and declared items; care state, slot override, archive; private photos (JPEG/PNG/WebP by magic bytes, 2 MB) |
| `GET`/`POST /me/wardrobe/shelves`, `PATCH`/`DELETE …/{id}` | owner | ordered shelves of your own items (50 × 500) |
| `GET`/`POST /me/looks`, `GET`/`PATCH`/`DELETE /me/looks/{id}`, `GET /me/look-revisions/{id}` | owner | looks with immutable revisions; ownership, slot and conflict rules checked on every save |
| `GET /me/planner?from=`, `PUT`/`DELETE /me/planner/{date}` | owner | 7 local dates; plans from today to +30; weather labelled `forecast` / `beyond_forecast` / `unavailable`, never invented |
| `POST /me/wear` (Idempotency-Key), `GET /me/wear`, `DELETE /me/wear/{id}` | owner | actual wear (today to −60 days), separate from plans |
| `GET /me/recommendations/outfits?date=&occasion=&rain=&hot=` | owner | thesis hard rules (slots, heat, rain, worship/wedding dress codes; ruleset `wardrobe-rules@1`) and Eq. 7 score (compatibility, preference, recency); up to 5 distinct cores with explanations and a private `run_id` |
| `POST /me/recommendations/outfits/{run_id}/events` `{kind: displayed\|chosen, index}` | owner | deduplicated exposures and one choice per run (409 `ALREADY_CHOSEN`); feeds Eq. 8 preference |
| `GET /weather/forecast?adm4=`, `GET /me/weather`, `PUT`/`DELETE /me/weather/location` | signed in | BMKG gateway with persisted cache and the fallback contract |
| `GET`/`POST /me/shares`, `PATCH`/`DELETE /me/shares/{id}`, `GET /shares/{id}`, `GET /profiles/{handle}/shares` | owner / public or signed in | look shares pinned to a revision; visibility computed at read time (accounts policy, wardrobe privacy ceiling, blocks); safe projections only |
| `GET`/`PUT /me/plan-sharing`, `GET /profiles/{handle}/week` | owner / friends | the next 7 planned looks for friends (no wear, weather or location) |
| `GET /me/feed` | signed in | friends' visible shares, newest first, encrypted cursor |
| `GET /me/notifications`, `GET …/unread-count`, `POST …/read` | signed in | derived from requests, accepted requests and friends' shares (30 days); read marker |
| `GET`/`PUT /me/showcase`, `GET /profiles/{handle}/showcase` | owner / profile visibility | headline, accent, up to 3 featured shares (filtered per viewer) |
| `GET`/`POST /admin/catalogue/products/{id}/media`, `POST …/media/generate`, `PUT …/media/order`, `PATCH`/`DELETE /admin/catalogue/media/{id}`, `POST /admin/catalogue/media/generate-missing` | `catalogue:media` (editor/admin) | replaceable media objects: generated placeholders, uploads (sniffed raster, 5 MB, rights basis), reorder, soft remove |
| `GET /media/{id}` | public (published) / staff (drafts) | media bytes with `nosniff`, strict CSP, ETag; public media cacheable for a day |
| `GET /admin/staff[/{handle}]`, `PUT`/`DELETE /admin/staff/{handle}/roles/{role}` | `identity:manage_roles` (admin) | in-app role administration; last-admin and own-admin protection; audited |
| `GET /admin/units?product_id=` | `inventory:issue` | unit list: serial, status, times (never keys or owners) |
| `GET /admin/commerce/orders`, `POST /admin/commerce/offers/bulk` | `commerce:orders` / `commerce:offers` | staff order view (buyer handle, no keys); bulk sandbox offers by category/slot rules |
| `POST /admin/unit-batches` | inventory_manager/admin | issue one unit and its private key. Requires `Idempotency-Key`. The key comes back in a no-store, 24 h restricted delivery |
| `POST /admin/units/{id}/reissue` | inventory_manager/admin | revoke and reissue the key of an unclaimed unit (409 once claimed) |
| `GET /items/{serial}` | public | product discovery only. Never creates ownership, and never shows owner or claim state |
| `POST /redemptions` | verified user | atomic private claim. Requires `Idempotency-Key`. Limit: 10 attempts per user per rolling hour, plus IP and global budgets |
| `GET /me/items` | verified user | owner-scoped, cursor-paginated list (default 24, max 100) |
| `GET /me/items/{id}` | owner | private item view. Absent items and other users' items both return the same 404 |
| `GET /catalogue/products/{id}/similar?limit=` | public | similar published products. Uses the active imported artifact (mode `trained` only with a model hash) or the content baseline (same category, trigram similarity); `model.fallback` says when the artifact had no neighbours |
| `GET /catalogue/sizes`, `GET /catalogue/products/{id}/sizes` | public | the size registry (systems in order, sizes by rank) and a product's sizes (empty = one size; `origin` rule = generated mock data) |
| `GET /admin/catalogue/sizes`, `PUT /admin/catalogue/size-systems/{code}`, `PUT …/{code}/sizes/{size_code}`, `GET`/`PUT /admin/catalogue/products/{id}/sizes`, `POST /admin/catalogue/sizes/assign-missing` | `catalogue:ingest` | manage size systems and sizes (retire with `active: false`), set a product's sizes (one system), generate sizes for unsized published products by slot rule |
| `GET`/`PATCH /me/settings` | signed in | synced settings: every key with defaults, the schema and a version; `PATCH {version, values}` (409 `SETTINGS_CHANGED` when another device saved first). Settings drive notifications, friend requests (`REQUESTS_CLOSED`), search visibility and outfit suggestions |
| `GET /me/security` | signed in | account dates, this session's sign-in age and recent-auth flag, your last 50 security events. Passwords never reach this API (Neon Auth holds them) |
| `GET /about` | public | version, schema head, data sources with licences and citations, notices, AI disclosure |
| `GET`/`PUT /me/sizes` | signed in | your usual size per system (`{"usual": {"alpha": "M", "eu_shoe": null}}`). Browse adds `size=system:code` and `my_sizes=true`; wardrobe items add `size`, `sort=size\|name\|worn` |
| `GET /me/recommendations/products?limit=` | signed in | sandbox-order popularity (30 days) then newest; never products you own; `heuristic_baseline` declared |

Errors are returned as `{code, message, field_errors?, request_id}`. Field errors never echo input values. Every invalid activation key gets one generic `400 INVALID_ACTIVATION_CODE`.

## Tests

```powershell
$env:WEARHOUSE_TEST_ADMIN_URL = "postgresql://postgres@127.0.0.1:55432/postgres"   # DISPOSABLE server only
apps\api\.venv\Scripts\python.exe -m pytest -q -rs apps\api\tests
```

Each test module creates and migrates its own database. The API in tests connects as a separate runtime role, exactly as in deployment.

Tests marked `synthetic_only` use a data-free invented product. **They never count as the source-backed readiness proof** (see `fixtures/source-products/README.md`).

## Contracts and container

- `python tools/contracts.py generate|check` writes `packages/contracts/openapi-v2.json` and `src/schema.d.ts`. It runs offline and fails when either file is stale.
- `docker build -t wearhouse-api apps/api` builds the image. Then run the release migration as its own step, separate from serving:
  ```
  docker run --rm -e WEARHOUSE_MIGRATION_DATABASE_URL=... wearhouse-api wearhouse migrate --environment <env> --runtime-role <role>
  ```

Operations (role grants, secret rotation, outbox, rollback) are covered in `docs/runbooks/v2-operations.md`, and accounts and Neon Auth in `docs/runbooks/accounts.md`.
