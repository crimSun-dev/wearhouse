# Legacy baseline (before relocation)

Captured 2026-11-25 on Windows 11 with Python 3.11.8 (`backend/.venv`) and Node v26.13.0, from commit `ea21b05` plus the working-tree edits.

**Isolation.** Every command ran with `DATABASE_URL` set to a SQLite file in a temporary scratch directory. An environment variable takes precedence over `backend/.env`, so these runs never touched Neon or any customer data.

- The PostgreSQL runs used a throwaway local PostgreSQL 18 cluster created with `initdb` on port 55432 with trust auth. It is not the system server.
- `measure.py` wrote its outputs to the scratch directory. The repository's `results/` and `docs/RESULTS.md` were not modified.

| Check | Command | Result |
|---|---|---|
| Python unit + integration (SQLite) | `python -m pytest -q` | **92 passed, 1 skipped** (60.5 s) |
| Python unit + integration (SQLite + PostgreSQL 18) | `TEST_POSTGRES_URL=postgresql://postgres@127.0.0.1:55432/dw_legacy_test python -m pytest -q` | **130 passed, 1 skipped** (67.6 s) |
| CLI | `python -m app.cli recommend --rain --occasion campus` | exit 0, 5 outfits (top score 0.650) |
| Offline measurement | `python measure.py --out-dir <tmp> --report <tmp>/RESULTS.md --db-dir <tmp>` | M1–M5 **all PASS** |
| Node parity | `npm test` in `neon-backend` | **20/20 pass** |
| Web unit | `npm test` in `Frontend/frontend` | **8/8 pass** |
| Web typecheck | `npm run typecheck` | exit 0 |
| Web build (`VITE_BASE_PATH=/LIVE-DEMO/`) | `vite build` | success; existing warning: the `viewer` chunk is 574 kB (> 500 kB) |
| Pages e2e (Playwright) | `playwright test -c playwright.pages.config.js` | **not a valid baseline**: 3 failed, because no Playwright browser is installed. The spec also targets the live Neon API and registers clothing through it, so it is deliberately not run against shared data |

## Existing failures and limitations, recorded as found

- One skip, already in the suite before this change: `tests/integration/test_phase4_registration.py:96`, a "Postgres-only stress variant" that skips its SQLite parameter. It appears in both runs.
- The only route to the Pages e2e suite is a live, mutating demo backend. After relocation, the Pages deep-link checks use a non-mutating smoke test against `vite preview` instead (`tools/smoke_legacy_pages.py`).
- The large `viewer` chunk warning is already present. Fixing it is out of scope, because the legacy presentation is frozen.

After each relocation step, the same commands are rerun from the new paths. Those results go in `docs/architecture/foundation-readiness.md`.
