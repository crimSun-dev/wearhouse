# Local environments: legacy v1 and Wearhouse v2

The repository holds two runtimes that run independently. **They never share a database, config file, port or virtual environment.**

| | Legacy v1 demo (frozen) | Wearhouse v2 foundation |
|---|---|---|
| Source | `legacy/python` (API), `legacy/neon` (public Neon adapter), `legacy/web` (Vite demo) | `apps/api` (package `wearhouse`), `packages/contracts` |
| Config | `legacy/python/.env` (ignored). The old `backend/.env` is read only as a fallback, with a warning | environment variables `WEARHOUSE_*` (see `apps/api/.env.example`) |
| Database | SQLite `legacy/python/demo.db`, or the Neon `demo` branch | dedicated PostgreSQL database, marked as v2 by its migrations |
| Port | 8000 (`run_demo.ps1`); Vite dev server on 5173 | 8100 (`tools/dev_api.ps1`) |
| Virtualenv | `legacy/python/.venv` | `apps/api/.venv` |

Paths in this repository contain spaces and an apostrophe. Always quote them, and in PowerShell use `-LiteralPath`.

## Recreating the legacy environment after the relocation

The relocation moved **tracked source only**. Machine-local state is never copied into tracked source, and you recreate it as follows.

1. **Virtual environment.** `run_demo.ps1` creates `legacy\python\.venv` automatically if it's missing. To do it by hand:
   ```powershell
   py -3.11 -m venv "legacy\python\.venv"
   & "legacy\python\.venv\Scripts\python.exe" -m pip install -r "legacy\python\requirements-dev.txt"
   ```
   A venv copied from `backend\.venv` still works through `python -m ...`, but its `*.exe` entry points contain the old absolute path. Recreate it if you use those entry points.
2. **Secrets.** Put the Neon `demo` connection string in `legacy\python\.env` (git-ignored). If the file still sits at the old `backend\.env`, the legacy config reads it there and warns. Move it yourself; no tool copies credentials.
3. **Node dependencies.** Run `npm ci` in `legacy\neon` and in `legacy\web`. The old `neon-backend\node_modules` and `Frontend\frontend\{node_modules,dist}` directories are leftover ignored output. You can delete them yourself once you no longer need them.
4. **Check paths without starting anything:**
   ```powershell
   .\run_demo.ps1 -CheckOnly
   ```

## Legacy commands (new locations)

| Purpose | Command |
|---|---|
| Offline demo | `.\run_demo.ps1 -Offline` |
| Python tests | `cd legacy\python; .venv\Scripts\python.exe -m pytest` (set `TEST_POSTGRES_URL` to a **throwaway** PostgreSQL database for PG runs) |
| CLI | `cd legacy\python; .venv\Scripts\python.exe -m app.cli recommend --rain --occasion campus` |
| Measurement | `cd legacy\python; .venv\Scripts\python.exe measure.py` (writes root `results\` and `docs\RESULTS.md`) |
| Node parity | `npm ci --prefix legacy/neon; npm test --prefix legacy/neon` |
| Web unit/type/build | `npm test --prefix legacy/web`, `npm run typecheck --prefix legacy/web`, `npm run build --prefix legacy/web` |
| v1 API types | `npm run types:api --prefix legacy/web` (reads `legacy/contracts/openapi-v1.json`) |
| Pages artifact | `python tools/build_legacy_pages.py` (or the wrapper `python scripts/build_pages.py`), then `python tools/smoke_legacy_pages.py` |

Legacy destructive utilities (`seed.py --reset`, `measure.py --db-url`) check the target database's environment marker before writing. They refuse any database marked as Wearhouse v2. See `docs/architecture/runtime-identity.md`.

## v2 commands

These are covered in `apps/api/README.md`. In short: `tools/dev_api.ps1` starts the API on port 8100 after you have run the explicit migration command against your v2 database. Startup never migrates or seeds.
