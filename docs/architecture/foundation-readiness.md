# Foundation readiness evidence: rearchitect-wearhouse-foundation

This is a readiness matrix for the foundation stop gate (design D8; GROWN-001/002). Every row records a command that was actually run on 2026-11-25 and its observed result: Windows 11, Python 3.11.8, Node 26.13.0, a throwaway local PostgreSQL 18.4 cluster (`initdb` on port 55432), and Docker 28.5.1 with `postgres:17`.

A gate without a command and a result is not counted as passed. For the pre-relocation baseline, see `legacy-baseline.md`.

> **Overall: the foundation engineering gates PASS. The source-backed readiness gate PASSED on 2026-11-25** (see "Source-backed thread" below).
>
> No permitted H&M source row exists in this workspace (`apps/api/fixtures/source-products/manifest.json` has `status: pending`). Every ownership-thread result below comes from the **data-free synthetic fixture** (pytest marker `synthetic_only`). Those results are lower-level invariant proofs, not the source-backed proof. `test_thread_source_backed` reports SKIPPED until a permitted fixture is added. Under GROWN-001/002, the frontend must not start until that gate passes.

## 1. Legacy relocation (Section 2)

| Gate | Command | Result |
|---|---|---|
| Legacy Python suite from `legacy/python` (SQLite + throwaway PG 18) | `.venv\Scripts\python.exe -m pytest -q` with `DATABASE_URL` set to a scratch SQLite file and `TEST_POSTGRES_URL` set to the throwaway cluster | **142 passed, 1 skipped** (baseline 130 + 7 relocation guards + 5 v1/v2 target guards; the baseline skip is unchanged) |
| Root, fixture, output and static-mount guards | `pytest tests/unit/test_relocation_paths.py` | 7 passed |
| CLI | `python -m app.cli recommend --rain --occasion campus` | exit 0, same top outfit as baseline |
| Offline measurement | `python measure.py --out-dir <scratch>` | M1–M5 PASS |
| Node parity from `legacy/neon` | `npm ci; npm test` | 21/21 (20 baseline + a module-graph guard proving that `../python/fixtures` and `../contracts/openapi-v1.json` resolve) |
| Web from `legacy/web` | `npm ci; npm test; npm run typecheck; npm run build` | 8/8, exit 0, built |
| v1 type generation | `openapi-typescript ../contracts/openapi-v1.json` | generated |
| Pages artifact + policy | `API_BASE_URL=https://… python scripts/build_pages.py --out <scratch>` (the wrapper calls `tools/build_legacy_pages.py`) | 11 public files only; `config.js` carries the public base |
| Artifact policy rejects private files | `--verify-only` on a directory containing `.env` and `demo.db` | `ArtifactPolicyError: forbidden file .env; forbidden file demo.db` |
| Pages deep links (non-mutating) | `python tools/smoke_legacy_pages.py <artifact>` | 18 URLs under `/LIVE-DEMO/`, including `/LIVE-DEMO/app/` and every referenced asset: 200 |
| Launcher on a path with spaces + apostrophe | `run_demo.ps1 -CheckOnly` | resolves `legacy\python`, the venv and `legacy\web\dist` |
| Offline demo through the launcher | `run_demo.ps1 -Offline -NoBrowser -Port 8011` | seed OK; `/api/v1/health` reports `db=sqlite weather_mode=mock`; `/`, `/LIVE-DEMO/`, `/LIVE-DEMO/app/`, `/api/v1/weather` return 200 |
| Local state not tracked | `git status --ignored legacy/python` | `.env`, `.venv/`, `demo.db*` are ignored, and none is tracked |
| Workflow paths | every `working-directory`, `cache-dependency-path`, `--prefix` and script path in `.github/workflows/*.yml` | all exist; both YAML files parse |

`git mv backend legacy/python` also renamed the ignored `backend/.env` and `backend/.venv`, because they lived inside that directory. Both remain ignored at `legacy/python/`, and neither was copied into tracked source. The legacy config looks for `legacy/python/.env` first, and falls back to `backend/.env` with a warning.

## 2. v2 package, boundaries, configuration and migrations (Section 3)

The command is `pytest` in `apps/api` with `WEARHOUSE_TEST_ADMIN_URL` set to the throwaway cluster.

| Gate | Test(s) | Result |
|---|---|---|
| Installable src-layout package; health; port 8100 vs 8000; only foundation routes | `test_app_factory.py` | 6 passed (includes offline, deterministic OpenAPI export identical to the checked-in file) |
| Forbidden imports (AST) | `test_boundaries.py`: no legacy imports; domain/ports/application free of FastAPI/SQLAlchemy/adapters; cross-module access only via domain/ports/application; platform free of business modules | 134 parametrised checks pass |
| Fail-closed config and targets | `test_config_safeguards.py`: deployment config without issuer, audience, DB or secret, or with http issuer/origins, the test adapter or a local JWKS; weak secret; SQLite; legacy DB refused **with no mutation, and migration refused**; unmarked DB; DB registered for another environment; runtime role without grants; superuser runtime role; immutable marker | 23 passed |
| Migrations | `test_migrations.py`: alembic head == `SCHEMA_HEAD`; upgrade from empty run twice (no duplicates or side effects); metadata vs migrations `compare_metadata == []`; leading-zero external IDs; immutable revisions; DB rejects a second owner and a second live credential; runtime role cannot DDL/DELETE/UPDATE/TRUNCATE history; **stale schema → startup fails and the version and row counts are unchanged**; startup performs zero writes | 10 passed |
| Least-privilege live run | `wearhouse migrate` ×2, then `wearhouse check` and `tools\dev_api.ps1 -CheckOnly` as the runtime role | `ready`: environment, schema `0003_ownership`, `least_privilege`, privileges ok |
| Baseline and weather ports | `test_recommendation_baseline.py`, `test_weather_contract.py`: matches legacy compat reference values; deterministic; `heuristic_baseline` label; unknown attributes not defaulted; trained mode needs an artifact; 24/24 BMKG violations rejected; real sample maps 100 %; LIVE→CACHED→MANUAL ladder | 12 passed |
| Legacy refuses v2 targets | `legacy/python/tests/unit/test_target_guard.py`: startup, `seed --reset` and `measure` refuse a v2-marked DB before any write; local SQLite is registered as legacy by seed; an unregistered remote DB is refused for destructive use until `--register-legacy-environment` | 5 passed |

## 3. Identity and access (Section 4)

| Gate | Test(s) | Result |
|---|---|---|
| Token verification | `test_identity.py`: valid RS256 yields only `(iss, sub)`; expired, wrong issuer, wrong audience, wrong signature, unknown kid, `nbf` in the future, HS256, `none`, malformed and missing `sub` all rejected; leeway bounds; discovery rotation with **one** bounded refresh and fail-closed handling of unknown kids; issuer mismatch and unreachable provider fail closed | pass |
| 401 without mutation | 8 credential variants × 4 protected routes | all 401 + `WWW-Authenticate`; counts unchanged |
| One account per subject | 8 concurrent first requests, then a restart | exactly 1 `app_user`; same id after restart; no roles |
| Roles | editor ingests but cannot issue; inventory manager issues but cannot ingest; customer gets 403 on all three staff routes with no state change; admin has both; token role claims grant nothing; grants audited | pass |
| Test-mode isolation | `X-Test-User`/`X-Debug`/`X-User-Id`/query flags/`X-API-Key`/`owner_id` body field ignored or rejected (422); fixed-principal adapter only via `create_test_app`; request id sanitised; tokens absent from logs | pass |

The identity suite totals 24 passed.

## 4. Source products, units and delivery (Section 5, `synthetic_only`)

| Gate | Result |
|---|---|
| Identical ingest → 1 product + 1 revision; leading zeros kept | pass |
| Changed facts → revision 2; revision 1 kept; units keep their acquisition revision | pass |
| Missing permission or snapshot, bad checksum, http terms, empty source row, missing category, a fact not equal to its source value, an invented fact, an annotation shadowing a fact, a GTIN derived from the external id, a numeric external id | each 422, zero rows |
| Two units of one product: distinct serials (128-bit) and keys (80-bit, `XXXX-XXXX-XXXX-XXXX`); **no plaintext key in any table**, including the idempotency, audit and outbox tables | pass |
| Lost-response retry returns the same unit and key; a different payload → 409; another actor cannot reach the delivery; expiry at 25 h → `expired`, no new unit; a claim erases the ciphertext | pass |
| Reissue: same unit, old key invalid, one active credential, 409 once claimed, audited without secrets | pass |
| Public lookup ×5 (including link-preview UA): zero ownership/attempt/idempotency rows; response has no owner, credential, attempt or claimed fields; a serial or QR URL submitted as a key → generic 400 | pass |

This suite totals 23 passed.

## 5. Redemption, reads, outbox, errors (Sections 6–7.1, `synthetic_only`)

| Gate | Result |
|---|---|
| Genuine claim (documented case and dash forms); second claim → 400; actor-bound key rejects another actor | pass |
| Nine invalid states (malformed, Unicode look-alikes, spaces, unknown, altered, public serial, revoked, reused, wrong actor) return **one identical** status, code, message and key set; 401 and 429 stay distinguishable | pass |
| 10 attempts per rolling hour, then 429 with Retry-After of about 1 h; still limited after restart; failed attempts retained; budget is per user | pass |
| **Multi-process limit boundary**: 9 seeded attempts + 6 spawned processes at once | exactly 1 admitted, 5 × 429, 10 reservations |
| IP budget (trusted proxy) and global budget configurable; admission store unavailable → 503 with no claim and no record, and a later retry succeeds | pass |
| Identical retry reserves no attempt; a changed body → 409 without evaluating it; invalid keys under new operation keys count as fresh attempts; 6 concurrent identical requests produce one effect | pass |
| Abandoned processing (hard crash, no cleanup) recovers by lease takeover without a second reservation | pass |
| **Multi-process race**: 4 users × 1 bearer key | 1 × 201, 3 × generic 400; 1 item, 1 claim event, 1 claim outbox event |
| Fault injected after each of 5 claim effects | no partial item, event or outbox row; credential active, unit issued, delivery intact; reservation kept; a retry with the same key claims once |
| Lost response, then retry after restart | same body; item, event, outbox, attempt and audit counts unchanged |
| Owned reads: default 24 + cursor, stable under inserts, limit 1–100; cross-user list empty; the 404 for another user's item equals the absent and malformed 404; a cursor replayed by another user, or forged, → 422; acquisition and source metadata present; `no-store` | pass |
| Outbox: a rolled-back claim leaves no event; dispatch is idempotent per consumer; a failing consumer gets backoff and then succeeds without repeating the others; payloads contain no secrets | pass |
| Error contract: 400/401/403/404/409/422/429/503 all `{code,message,request_id[,field_errors]}`; field errors never echo inputs; logs keep route and status metadata but no key, token or digest | pass |

Totals: `test_redemption.py` 18, `test_owned_items_outbox.py` 5 and `test_errors_contract.py` 4 passed.

## 6. Contracts, container, CI and isolation (Sections 7.2–7.6)

| Gate | Command | Result |
|---|---|---|
| Offline deterministic contract | `python tools/contracts.py generate` then `check` (exports twice, generates TS twice, no `WEARHOUSE_*` environment, no engine) | `contracts up to date` |
| Drift detection | appended a line to `schema.d.ts`, then edited the OpenAPI title | each fails with `CONTRACT DRIFT … Regenerate with: python tools/contracts.py generate`; `npm run check` also flags stale types |
| Types compile | `npm run check --prefix packages/contracts` (pinned openapi-typescript 7.13.0, TypeScript 5.9.3) | pass |
| Container image | `docker build -t wearhouse-api:foundation apps/api` (base pinned by digest) | built, 71.7 MB, runs as uid 10001 |
| Startup before migration | `docker run … wearhouse-api` | `StartupError: … not a migrated Wearhouse v2 database` |
| Release migration as its own command | `docker run … wearhouse migrate --environment staging --runtime-role wearhouse_runtime` | `0003_ownership`, marker `staging` |
| Serve + readiness | `docker run -p 8101:8100 …` | `/health` 200; `/health/ready` 200 (`least_privilege`); `/me` 401; Docker health `healthy`; 0 rows written by startup |
| Stale schema in container | set `alembic_version` to `0002_catalogue`, then start | exit 1 with `StartupError`; version unchanged |
| Wrong environment and test adapter in container | `WEARHOUSE_ENV=production` against the staging DB; `WEARHOUSE_AUTH_ADAPTER=test` | both refused |
| CI jobs | `.github/workflows/ci.yml`: legacy jobs on relocated paths plus `v2-tests` (own PG17 service), `v2-contracts`, `v2-container`; `pages.yml` still builds legacy v1 only | YAML parses; not yet run on GitHub (nothing pushed) |
| Clean-checkout emulation | copied only tracked + new non-ignored files (`git ls-files -co --exclude-standard`; no `.venv`, `node_modules`, `.env` or DB files) into a scratch directory, then ran every CI job's commands with fresh venvs and `npm ci`; a fresh legacy PG test DB; every v2 module gets its own new DB | legacy pytest **142 passed, 1 skipped**; CLI rc 0; measure M1–M5 PASS; Neon parity 21/21; web test + typecheck rc 0; Pages build + smoke 18 URLs; v2 pytest **255 passed, 1 skipped** (the skip is the pending source-backed gate); contracts check + TS check rc 0 |
| Isolation + rollback rehearsal | `apps/api/.venv/Scripts/python.exe tools/rehearse_isolation.py --admin-url <throwaway>` | **14/14 checks true**: legacy startup, `seed --reset` and `measure --db-url --yes` refuse a v2 DB holding a claimed item, which stays owned with counts unchanged; v2 startup and migration refuse a legacy DB created by the legacy setup command, whose data is unchanged; after the v2 app is stopped its data is retained, and legacy serves `/api/v1/health` on its own; checksums match |
| Brand and research originals | `sha256sum -c docs/architecture/source-asset-checksums.sha256` | 12/12 OK |

## 7. Explicit limitations (not passed, not assumed)

- **Source-backed thread: PASSED (2026-11-25).**
  - **Data.** The real H&M `articles.csv`: 105,542 rows, SHA-256 `25f21882053517f7684ea43f524225a9481a7bb9aab9cf0abfc7fe8c4576a72b`, matching the recorded `articles.csv.sha256`.
  - **Permission.** The project owner accepted the Kaggle competition rules on 2026-11-25. The basis is `kaggle-competition-rules-accepted`; the scope is non-commercial academic use, and the file is not redistributed.
  - **Fixture.** `tools/make_hm_fixture.py` built it from row `0108775015` (byte-for-byte, with per-row SHA-256) into the **git-ignored** `apps/api/fixtures/source-products/local/`. The Kaggle rules forbid redistribution, so the fixture is never committed. CI therefore still reports this test as SKIPPED; it runs on the machine that holds the permitted file.
  - **Run.** `pytest apps/api/tests/test_foundation_thread.py -rs` gave **2 passed, 0 skipped**. The test also checks that the subset file and every row match their manifest checksums, and that the article id keeps its leading zero.
- **Identity provider: not selected.** The adapter is proven against a local RS256/JWKS issuer only. The provider's token compatibility, browser PKCE/renewal/logout, and the host and secret store are deployment inputs (`runtime-identity.md` §4).
- **Deployment: none.** Production stays on legacy v1, the Pages workflow still builds legacy, and no cloud resource was created or changed.
- **CI on GitHub: not executed.** Nothing has been pushed; the jobs were emulated locally from a clean copy.
- **Playwright Pages e2e: not run.** It mutates the live demo backend and no browsers are installed; the non-mutating smoke test replaces it for deep links.
- **Cutover, commerce, catalogue publication, planner, social and trained models** belong to later changes (`roadmap.md`).

## 8. Foundation stop gate (task 7.8)

See §9 for the F01–F13 and RQ audit. The frontend apply workflow is **not** started by this change. `apps/web` contains only a README (verified: `find apps/web -type f` → `apps/web/README.md`), so it has no screens and no copy of the legacy renderer.

The gate to begin `rebuild-wearhouse-frontend` is:

1. the source-backed thread passes;
2. the CI jobs pass on GitHub;
3. the provider and host inputs in `runtime-identity.md` §4 are recorded.

Only after those does `rebuild-wearhouse-frontend` begin.

## 9. Roadmap coverage audit (F01–F13, RQ1–RQ4)

For each requirement, this table shows what the foundation owns, its status, and where the rest is assigned. "Proven" means a test from §§1–6 above.

| Req | Foundation-owned part | Status | Remaining owner (roadmap) |
|---|---|---|---|
| F01 existing catalogue | source namespace + preserved string IDs, snapshot checksum, permission record, facts traceable to source fields, no GTIN synthesis | proven with synthetic data; **real H&M snapshot pending** | publish-wearhouse-catalogue; research |
| F02 shared intelligence | typed compatibility, outfit and catalogue ranker ports; heuristic baseline labelled `heuristic_baseline`; trained mode requires an artifact | proven (ports only; no endpoint) | wardrobe services; research |
| F03 product/unit/item | separate product → immutable revision → serialized unit → owned item; two units have independent lifecycles | proven | commerce; fresh frontend |
| F04 dedicated redemption | public lookup is discovery-only; private one-time key; atomic claim; generic invalid response; durable limits | proven | fresh frontend (Redeem page) |
| F05 visual wardrobe/avatar | none (no media pipeline, no UI) | not in scope | wardrobe services; frontend; RQ4 |
| F06 seven-day timeline | weather validation and fallback contract only; no fabricated forecast | contract proven | wardrobe/social services; frontend |
| F07 mock purchasing/wishlist | idempotency, encrypted-delivery and outbox infrastructure reusable for buyer receipts; lookup has no fake saved state | infrastructure proven | add-wearhouse-sandbox-commerce |
| F08 friends/profile | owner-scoped reads; uniform 404; actor binding | proven (privacy primitives) | social services |
| F09 admin publication | server-owned roles (editor / inventory manager / admin); audited ingestion, issuance and reissue; no self-elevation | proven | publish catalogue; admin UI |
| F10 reference-led UI | `Reference/` and `Assets/` originals preserved and checksummed; `apps/web` reserved | preserved; not started | rebuild-wearhouse-frontend |
| F11 functional ecosystem | issue → discover → redeem → own thread survives restart, with account isolation | proven with synthetic data; source-backed pending | all later changes; hardening |
| F12 context/rotation | rain/heat validation, LIVE→CACHED→MANUAL ladder, baseline compatibility | contract proven | wardrobe services; research |
| F13 manual/thrifted clothes | unknown attributes stay unknown (no defaults) in the baseline | principle proven | wardrobe services; frontend |
| RQ1 | none (dataset terms pending) | not in scope | research intelligence |
| RQ2 | ranker ports and truthful mode metadata | ports proven | research intelligence |
| RQ3 | **foundation subset**: genuine placement, public/altered/guessed/reused rejection, multi-user races, independent admission-limit tests (validation tested separately from the rate limiter) | subset proven with synthetic data; the full 500-fixture / 100,000-guess experiment is not claimed | research intelligence |
| RQ4 | none | not in scope | frontend; research |

Every F01–F13 and RQ item has an owning change and a gate. Nothing has been waived. This change neither started nor stubbed the frontend.
