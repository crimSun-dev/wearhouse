# Wearhouse / Digital Wardrobe

This repository holds **two independent runtimes**, which never share a database, config, port or code:

| | Wearhouse v2 foundation (new, canonical) | Legacy v1 demo (frozen course demo) |
|---|---|---|
| Source | `apps/api` (Python/FastAPI, package `wearhouse`), `packages/contracts` | `legacy/python`, `legacy/neon`, `legacy/web`, `legacy/contracts` |
| Start | `.\tools\dev_api.ps1` (port 8100; migrate first) | `.\run_demo.ps1 -Offline` (port 8000) |
un_demo.ps1 -Offline` (port 8000) |
| Identity | verified OIDC access tokens; roles granted on the server | single synthetic demo user and a shared write key |
| Ownership | private one-time activation keys; public tags are discovery-only | public QR plus activation code (demo semantics) |
| Public deployment | none yet (no cutover in this change) | GitHub Pages `/LIVE-DEMO/` + Neon Functions |

- v2 setup, routes and tests: [`apps/api/README.md`](apps/api/README.md). Identity/runtime contract: [`docs/architecture/runtime-identity.md`](docs/architecture/runtime-identity.md).
- Both environments side by side, and how to recreate the local ones: [`docs/runbooks/local-environments.md`](docs/runbooks/local-environments.md). v2 operations: [`docs/runbooks/v2-operations.md`](docs/runbooks/v2-operations.md).
- What is proven, how, and what is still pending: [`docs/architecture/foundation-readiness.md`](docs/architecture/foundation-readiness.md).
- What moved where: [`docs/architecture/migration-inventory.md`](docs/architecture/migration-inventory.md). Roadmap: `openspec/changes/rearchitect-wearhouse-foundation/roadmap.md`.
- `apps/web` is reserved for the fresh frontend (not started; it does not reuse the legacy renderer). `Assets/`, `Reference/` and `Research Resources/` are originals and are kept unchanged (checksums in `docs/architecture/source-asset-checksums.sha256`).

---

# Legacy v1: Digital Wardrobe Live Demo (INFS4305 System Integration)

Deployment: [GitHub Pages + Neon Functions + Neon Postgres](docs/DEPLOYMENT.md).
The public demo uses **GitHub Pages + Neon Functions + Neon Postgres**. The Neon
API adapter is in `legacy/neon/`; the Python backend below remains available locally.

A working virtual wardrobe backend that integrates the **BMKG open weather API**, built from
[`docs/TDD_Digital_Wardrobe_Live_Demo.md`](docs/TDD_Digital_Wardrobe_Live_Demo.md):
FastAPI + SQLAlchemy over **Neon Postgres** (SQLite as offline fallback), a validated/cached
weather gateway with a LIVE → CACHED → MANUAL fault ladder, QR + one-time activation-code garment
registration, and `measure.py`, which produces the Ch 15 metrics M1–M5.

The legacy frontend in `legacy/web/` includes an editorial landing page, wardrobe,
week planner, registration, demo controls, and a procedural Three.js avatar.
The public app is at https://crimsun-dev.github.io/LIVE-DEMO/app/.
Run `npm ci --prefix legacy/web` and `npm run dev --prefix legacy/web`
for frontend development with the local FastAPI proxy. Build with
`npm run build --prefix legacy/web` to serve it from FastAPI after restart.

## Quick start (Windows)

```powershell
.\run_demo.ps1 -Offline      # SQLite + mock BMKG: works with no internet
.\run_demo.ps1               # uses legacy\python\.env (Neon if DATABASE_URL is set)
.\run_demo.ps1 -Live -Reset  # real BMKG, fresh demo data
```

Then open http://127.0.0.1:8000/ (web page) or http://127.0.0.1:8000/docs (Swagger / OpenAPI = the Ch 12 interface list).
Writes need the header `X-API-Key` (default `demo-key`; the web page sends it).

Manual setup (any OS):

```bash
cd legacy/python
python -m venv .venv && . .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env                               # optional; edit DATABASE_URL for Neon
python seed.py                                     # idempotent
uvicorn app.main:app --reload
```

## Neon Postgres

> Destructive legacy utilities (`seed.py --reset`, `measure.py --db-url`) now refuse a remote database until it is explicitly registered as the legacy demo: run `python seed.py --register-legacy-environment` once against the `demo`/`test` branch. They always refuse Wearhouse v2 databases.

The demo database is the Neon project **`digital-wardrobe-live-demo`** (AWS ap-southeast-1, Postgres 17, database `wardrobe`):

| Branch | Used by |
|---|---|
| `demo` | the app (`legacy/python/.env`), seeded with the synthetic wardrobe |
| `test` | `pytest` (`TEST_POSTGRES_URL`) and `measure.py --db-url`; both drop/reset data, so they never touch `demo` |
| `main` | empty parent branch; reset `demo` from it in the Neon console if needed |

Put the connection string for the `demo` branch in `legacy/python/.env` (git-ignored, never commit it):

```
DATABASE_URL=postgresql://USER:PASSWORD@ep-xxxx.REGION.aws.neon.tech/neondb?sslmode=require
```

`postgresql://` URLs are switched to the psycopg 3 driver automatically. `GET /api/v1/health` then reports
`"db": "neon"`. Tables are created on start-up and `python seed.py` loads the synthetic data.
Neon scales to zero, so the first query after idle is slow: `run_demo.ps1` runs `seed.py` first, which wakes it up.

## Tests

```bash
cd legacy/python
python -m pytest                                    # SQLite
TEST_POSTGRES_URL=postgresql://... python -m pytest # + PostgreSQL (CI does this)
```

Each named test from TDD §4 Phases 0–5 exists, plus a few more. GitHub Actions runs the suite on Ubuntu (SQLite + Postgres 17)
and on Windows, runs the Phase 1 CLI, checks that no Neon secret is committed, and runs `measure.py`
(its RESULTS table appears in the job summary and as an artifact).

## Measurement (Ch 15)

```bash
cd legacy/python
python measure.py              # offline: synthetic 24-slot feed, temp SQLite, no network
python measure.py --live       # real BMKG (1 + 3 cold calls)
python measure.py --db-url "<neon url>" --yes   # measure on Neon (RESETS demo data there)
```

Writes `results/<timestamp>_<mode>.json` and regenerates [`docs/RESULTS.md`](docs/RESULTS.md).
Only `measure.py` writes numbers into RESULTS.md. Metrics and pass conditions are fixed in the TDD.

## Interfaces

| ID | Interface | Where |
|---|---|---|
| I1 | Client ↔ Server (JSON/REST) | `legacy/python/app/routers/*`, schemas in `app/schemas.py` |
| I2 | BMKG → Server | `app/weather.py` (`HttpBMKGClient`, `validate_entry`, `WeatherGateway`) |
| I3 | Server ↔ DB (SQL) | `app/models.py`, `app/services.py`, `app/registration.py` |
| I4 | Compatibility score | `app/scoring.py::compat` (colour/style stand-in) |
| I5 | Phone camera → Server (GS1 Digital Link) | `GET /01/{gtin}/21/{serial}`, `GET /api/v1/scan/...` |
| I6 | measure.py → Server (+ fault switch) | `legacy/python/measure.py`, `POST /api/v1/admin/fault` |

Every API call writes one `interface_log` row (`GET /api/v1/metrics/interface-log`), and so does every BMKG attempt (I2).

## Endpoints (`/api/v1`)

`GET /health` · `GET /wardrobe` · `POST /garments` · `DELETE /garments/{id}` (409 if a saved outfit uses it) ·
`POST /garments/activate` · `GET /scan/01/{gtin}/21/{serial}` · `POST /outfits/recommend` · `POST /outfits` ·
`GET /outfits?week=2026-W48` · `DELETE /outfits/{id}` · `POST /outfits/{id}/wear` · `GET /weather` ·
`GET /avatar/{outfit_id}` · `GET /metrics/interface-log` · `GET /metrics/summary` · `GET /codes/{serial}/qr.svg` ·
admin: `POST /admin/fault`, `POST /admin/weather/clear-cache`, `POST /admin/codes`, `GET /admin/products`, `POST /admin/reset`.

## Decisions made while implementing (where the TDD left room)

- **Schema creation** uses `metadata.create_all` (idempotent) instead of Alembic migrations; the schema is fixed for the demo.
- `activation_attempt` has an `id` primary key (the ORM needs one); otherwise the tables match TDD §3.2.
- **`manual_weather` overrides BMKG** when sent (`source=MANUAL`). That is the two-tap fallback after `MANUAL_REQUIRED`
  and the "no weather call" baseline for M2/M3.
- A forecast served from the 3 h cache is labelled `CACHED`, with `fetched_at` and a note (`cache hit` vs `fallback after timeout`).
- Switching the fault mode marks cached forecasts as due for refresh, so the next request really hits the fault while the cached copy stays available as the fallback.
- **Heat rule**: when hot (t ≥ 32 °C), *any* heavy garment is excluded (the seed only flags outerwear as heavy).
- **Dress code**: worship needs long sleeves (top, dress or outer) and a long bottom (bottom or dress); formal needs formality ≥ 2 and wedding ≥ 3 on clothing (accessories are exempt).
- **Delete garment** used by a saved outfit is **blocked (409)**, not cascaded.
- The top 5 keeps one outfit per distinct top/bottom/dress combination when it can, so it is not five copies of the same outfit with different accessories.
- Activation codes: 16 base32 characters (80 bit), shown once as `XXXX-XXXX-XXXX-XXXX`, case and dashes ignored, stored only as SHA-256.

## Data ethics

Synthetic wardrobe and user only; no personal photos. Synthetic GTINs use the GS1 Indonesia prefix 899 but are not real products.
Weather data: BMKG (Badan Meteorologi, Klimatologi, dan Geofisika), credited on every weather response and on the web page.
`legacy/python/fixtures/bmkg_real_sample.json` is one real BMKG response for Kemayoran, Jakarta (24 Nov 2026), frozen as the mock fixture.
