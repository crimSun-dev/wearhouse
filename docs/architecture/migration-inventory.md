# Migration inventory — rearchitect-wearhouse-foundation

Recorded 2026-11-25 on branch `rearchitect-wearhouse-foundation`, created from `main` at `ea21b05`.
Your uncommitted edits came with the branch and are listed below. This change keeps them as they are.

## 1. Working-tree state when the change began

### Tracked files with uncommitted edits

These are your edits, and they move together with their directories (`git mv` keeps the working-tree contents):

| Path | Edit | Destination |
|---|---|---|
| `Frontend/frontend/package.json` | adds `@neondatabase/auth`, reorders devDependencies | `legacy/web/package.json` |
| `Frontend/frontend/package-lock.json` | lockfile for the above | `legacy/web/package-lock.json` |
| `neon-backend/package.json` | adds `jose`, expands formatting | `legacy/neon/package.json` |
| `neon-backend/package-lock.json` | lockfile for the above | `legacy/neon/package-lock.json` |

### Untracked inputs

These stay where they are and are never moved, published, or deleted by this change:

| Path | Kind | Policy |
|---|---|---|
| `Assets/` (5 PNG, including the Wearhouse logos) | supplied brand originals | checksummed, unchanged |
| `Reference/` (4 Steam reference screenshots) | supplied design references | checksummed, unchanged |
| `Research Resources/` (Ch1–3 methodology .docx) | thesis evidence | checksummed, unchanged |
| `Digital Wardrobe Favicon.png` | supplied brand original | checksummed, unchanged |
| `test-tags/` | legacy v1 QR tag fixtures | legacy-only; v2 never treats public QR contents as credentials |
| `CRIMSUN_POOL/`, `.agents/`, `.cursor/`, `openspec/` | planning/experience tooling | unchanged by the restructure (except openspec task checkboxes) |

Checksums are listed in `docs/architecture/source-asset-checksums.sha256`. To verify them:

```bash
sha256sum -c docs/architecture/source-asset-checksums.sha256
```

### Ignored local state, never moved into tracked source

| Path | Contents | Handling |
|---|---|---|
| `backend/.env` | Neon credentials (deny-listed; not read) | stays where it is. Legacy config looks in `legacy/python/.env` first, then the old `backend/.env` (see §3) |
| `backend/.venv/` | Python 3.11.8 virtual environment | not copied; recreate under `legacy/python/.venv` (see `docs/runbooks/local-environments.md`) |
| `backend/*.db*` | none present at inventory time | new legacy SQLite files go in `legacy/python/` (ignored) |
| `Frontend/frontend/node_modules/`, `neon-backend/node_modules/` | installed dependencies | not moved; reinstall with `npm ci` in the new location |
| `Frontend/frontend/dist/`, `Frontend/frontend/test-results/` | generated build output | not moved; rebuilt in `legacy/web/` |
| `_site/`, `.deployment/`, `Digital_Wardrobe_Frontend.zip` | generated/historical artefacts | left where they are; never bulk-moved, published, or deleted |
| `Canva_-_download.png` (tracked) | historical image | left at the root, checksummed |

## 2. Legacy commands (before relocation)

| Purpose | Command (from the old location) | Notes |
|---|---|---|
| Python tests | `cd backend; python -m pytest` (+ `TEST_POSTGRES_URL` for PG) | SQLite always, PG optional |
| CLI | `cd backend; python -m app.cli recommend --rain --occasion campus` | pure core |
| Seed/reset | `cd backend; python seed.py [--reset] [--issue-codes N]` | writes to `DATABASE_URL` |
| Measurement | `cd backend; python measure.py [--live] [--db-url URL --yes]` | defaults to root `results/` and `docs/RESULTS.md`; `--db-url` resets demo data |
| Local demo | `.\run_demo.ps1 [-Offline] [-Live] [-Reset]` | uses `backend\.venv`, port 8000 |
| Node parity | `npm ci --prefix neon-backend; npm test --prefix neon-backend` | imports `../backend/fixtures/…` and `../docs/openapi.json` |
| Neon deploy | `neon functions deploy wardrobeapi … --src neon-backend/index.mjs` | documented in `docs/DEPLOYMENT.md`; not run by this change |
| Web unit/type/build | `npm test` / `npm run typecheck` / `npm run build` in `Frontend/frontend` | base path from `VITE_BASE_PATH` |
| v1 API types | `npm run types:api` → `openapi-typescript ../../docs/openapi.json` | |
| Pages build | `python scripts/build_pages.py` → `_site/` | `API_BASE_URL`, `SITE_BASE_PATH=/LIVE-DEMO/` |
| Pages e2e | `npx playwright test -c playwright.pages.config.js` | targets the live Neon API **and registers clothing**, so it is excluded from baselines |

## 3. Path dependency map (design D2)

Each row lists a dependency that has to change when its source moves. Section 2 of `tasks.md` uses this table as its checklist.

| D2 row | Current dependency found in code | Target edit |
|---|---|---|
| `backend/` tracked source | 43 tracked files; `app.config.BACKEND_DIR = parents[1]`, `REPO_DIR = BACKEND_DIR.parent` | `legacy/python/`; `REPO_DIR` must become `parents[3]` relative to `app/config.py` (`legacy/python/app/config.py`) |
| `backend/.env`, SQLite, venv | `load_dotenv(BACKEND_DIR / ".env")`; `normalize_url` resolves relative SQLite against `BACKEND_DIR` | `.env` lookup: `legacy/python/.env`, then old `backend/.env` with a warning; relative SQLite resolves against `legacy/python/` |
| `neon-backend/` | `index.mjs:8 ../backend/fixtures/bmkg_real_sample.json`; `index.mjs:9 ../docs/openapi.json` | `legacy/neon/`; `../python/fixtures/…` and `../contracts/openapi-v1.json` |
| `Frontend/frontend/` | `package.json types:api ../../docs/openapi.json`; vite proxy to `127.0.0.1:8000` | `legacy/web/`; `../contracts/openapi-v1.json`; proxy unchanged (legacy port 8000) |
| `Frontend/{BRIEF,DESIGN,PRODUCT,README-frontend}.md`, `Landing-preview.html` | historical frontend docs | `docs/legacy/frontend/` |
| `docs/openapi.json` | v1 schema | `legacy/contracts/openapi-v1.json` |
| `scripts/build_pages.py` | `ROOT/"Frontend"/"frontend"` | `tools/build_legacy_pages.py` + wrapper at `scripts/build_pages.py` |
| `run_demo.ps1` | `Join-Path $PSScriptRoot "backend"` | `legacy\python`, still `-LiteralPath` |
| Legacy static mount | `STATIC_DIR.parents[2] / "Frontend" / "frontend" / "dist"` | resolve `legacy/web/dist` through the repo root (override: `LEGACY_WEB_DIST`) |
| `measure.py` outputs | `REPO_DIR / "results"`, `REPO_DIR / "docs" / "RESULTS.md"` | unchanged targets once `REPO_DIR` is correct |
| `.github/workflows/ci.yml` | `working-directory: backend`, `--prefix neon-backend`, cache paths | `legacy/python`, `legacy/neon`, plus new v2 jobs |
| `.github/workflows/pages.yml` | `--prefix Frontend/frontend`, cache path | `legacy/web`; still builds legacy v1 only |
| Playwright configs | relative `./e2e`, preview at 4173 `/LIVE-DEMO/` | move alongside `legacy/web/` unchanged |
| `.gitignore`, `README.md`, `docs/DEPLOYMENT.md`, `docs/demo_script.md` | old paths in prose | update paths, keeping v2 and legacy environments distinct |
| `_site`, `dist`, `.deployment`, ZIP | generated | not moved |
| `Assets`, `Reference`, research | originals | not moved (checksums above) |
| `docs/FRONTEND_PROMPT.md`, `docs/TDD_…md` | historical prompt and TDD, citing old paths | historical documents; a note links to this map, and their text is not rewritten |

## 4. Baseline

The pre-relocation results of the legacy checks are in `docs/architecture/legacy-baseline.md`.
