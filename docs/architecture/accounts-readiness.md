# Accounts readiness evidence: add-wearhouse-accounts

Each row records a command that was run on 2026-11-25 and its observed result: Windows 11, Python 3.11.8, Node 26.13.0, a throwaway PostgreSQL 18.4 cluster on port 55432, and `@neon/auth` 0.8.2. A gate without a command and a result is not counted.

> **Status.** The account system passes against a **local Neon-shaped EdDSA issuer**: Ed25519, `iss` = `aud` = the Auth origin, 15-minute tokens and Neon's profile claims. The real Neon Auth branch and the real Google sign-in (tasks 9.1/9.2) are **not yet verified**. They need your confirmation to provision, plus a manual Google sign-in. The foundation's source-backed gate (`rearchitect-wearhouse-foundation` 7.5) is separate and still **PENDING**.

## API (apps/api, `pytest` with `WEARHOUSE_TEST_ADMIN_URL` set to the throwaway cluster)

| Gate | Test(s) | Result |
|---|---|---|
| Neon-shaped issuer matches the documented contract | `test_neon_issuer.py` | 2 passed |
| EdDSA accepted. HS256/`none`/RSA-on-EdDSA-allowlist/cross-family kid/malformed OKP rejected; `iat` required; the allowlist can only narrow | `test_federated_sign_in.py` | pass |
| Explicit JWKS URL: no discovery call, one bounded refresh per new kid, fail-closed on unknown kid or unreachable provider; deployment config needs an https JWKS URL (or an explicit discovery opt-in) | `test_federated_sign_in.py` | pass |
| Broker `role`/`o` claims grant nothing; `banned` → 403 `ACCOUNT_SUSPENDED` with no account created; public routes still work | `test_federated_sign_in.py` | pass |
| Revocation: a token issued earlier gets 401 immediately, still after a restart; a later token works | `test_federated_sign_in.py`, `test_account_lifecycle.py` | pass |
| 8 concurrent first sign-ins → 1 account, `needs_onboarding`, display name from the name hint, no email | `test_federated_sign_in.py` | pass |
| Migration 0004: 0003→0004 upgrade with backfill, run twice; a stale 0003 database fails startup; column-level `app_user` UPDATE grant; widened attempt scopes; social CHECK and unique constraints | `test_accounts_migration.py`, `test_migrations.py` | pass |
| Boundaries: `accounts` reaches identity and ownership only through ports/domain/application | `test_boundaries.py` | pass |
| Visibility policy: 3 sections × 3 settings × 5 relations; handle, display name and bio validators | `test_accounts_domain.py` | 64 passed |
| Handles: lowercase, taken/reserved/held → 409, invalid → 422, 4-way concurrent claim → exactly 1 winner, 7-day change interval with Retry-After, 30-day hold (checked with the clock moved forward) | `test_profiles_privacy.py` | pass |
| Avatar: preset or the provider picture from the verified token only; a client-supplied URL → 422; no email in any response | `test_profiles_privacy.py` | pass |
| Privacy: defaults, owner only; projections per relation (anonymous, stranger, friend, self, blocked either way, deleted); wardrobe without serials, ids or times; unfriending takes effect immediately; widening parameters are ignored; friends-list omissions; sealed, viewer-bound cursors | `test_profiles_privacy.py`, `test_account_lifecycle.py` | pass |
| Search: limit 20, minimum 3 characters, `@exact`, no LIKE wildcards, block exclusion, onboarded caller only | `test_profiles_privacy.py` | pass |
| `HANDLE_REQUIRED` on social routes; redemption without a handle works | `test_profiles_privacy.py` | pass |
| Friend lifecycle: send/accept (idempotent), duplicate send, crossed requests auto-accept, decline/cancel, recipient-only accept, 5× concurrent accept-vs-cancel → a single outcome, self/unknown/blocked targets, owner-only lists with cursor replay rejected | `test_friends_blocks.py` | pass |
| Blocking: atomic, invisible both ways, idempotent, unblock restores nothing; a fault at each step leaves no partial state | `test_friends_blocks.py` | pass |
| Limits: 50 per 24 h → 429 + Retry-After; friend cap 409; pending cap 409; block cap 409; **multi-process boundary** (49 seeded + 6 processes → exactly 1 × 201, 5 × 429) | `test_friends_blocks.py` | pass |
| Export: every section, no other account's private data, key, digest or email; `no-store` + attachment; 6th in an hour → 429 | `test_account_lifecycle.py` | pass |
| Deletion: stale token → 401 `REAUTHENTICATION_REQUIRED`, wrong confirmation → 422 (nothing changed); a tombstone with no personal data; social data removed both ways; owned item kept, unit still rejects redemption; handle held; the same subject later gets a fresh account; audit/outbox carry no personal data; a fault at each step → no partial deletion | `test_account_lifecycle.py` | pass |
| Contracts: new routes; `ErrorCode` union (25 codes generated from source); drift detection | `python tools/contracts.py check`; `npm run check --prefix packages/contracts` | up to date; TS check passes |
| Full v2 suite | `pytest -q -rs` | **392 passed, 1 skipped** (the skip is the foundation source-backed gate) |

## Account pages (apps/web/account-pages)

| Gate | Command | Result |
|---|---|---|
| Reproducible install, pinned `@neon/auth` 0.8.2 | `npm ci` (with `install-links=true`) | 48 packages |
| Typecheck | `npm run typecheck` | exit 0 |
| Tokens per call, memory only, nothing in storage/URL/console, gone after sign-out | `npm test` | 4/4 |
| Production build guard | `VITE_NEON_AUTH_URL=… npm run build` | `build guard OK … no e2e fake, no legacy code` |
| Guard trips on the e2e build | `npm run build:e2e && node scripts/check-build.mjs dist-e2e` | exit 1, fake detected |
| E2E harness: real v2 API (test factory) + Neon-shaped issuer + disposable DB; CORS for the pages origin | `node e2e/start-harness.mjs`, then curl | health 200, token → `/me` with `needs_onboarding: true`, `access-control-allow-origin: http://127.0.0.1:4174` |
| Pages e2e: onboarding + reload, readable error codes, two-user friend flow, privacy, block, export, deletion with disclosure, keyboard-only sign out everywhere | `npm run test:e2e` | **5 passed** (Chromium headless shell 1255, Playwright 1.65.1). Found and fixed on the way: the fake treated a URL subject as an open session (it now uses a session cookie like the broker); a success message was overwritten by a generic "Done." |

## Real broker (pending your confirmation)

| Gate | Status |
|---|---|
| 9.1 Dedicated Wearhouse Neon project + Auth on `dev` with Google | **done**: project `soft-darkness-81364884`, the live JWKS is Ed25519/EdDSA with a kid, discovery returns 404, Google uses shared credentials (`runtime-identity.md` §5.2) |
| 9.2 Manual real Google sign-in end to end, including the managed `deleteUser` outcome | **partial** (2026-11-25, your Google account against the dev Auth branch). Verified: Google sign-in; the v2 API accepts the real EdDSA JWT (`GET /me` 200); onboarding and profile saves (`PATCH /me/profile` 200); privacy (`PUT /me/privacy` 200); friends, blocks and public-preview reads. **Found and fixed:** the pages called `token()`, which returned nothing, so every call got 401. The Neon wrapper delivers the JWT in `getSession().session.token`, and the pages now read it there (`tests/neon-token.test.ts`). Also fixed: the log-redaction filter broke uvicorn's access-log formatter. **Not yet verified:** the two-account friend flow, sign out everywhere, export, and deletion with the managed `deleteUser` outcome |
| 9.3 Production prerequisites | documented in `docs/runbooks/accounts.md` §7; nothing created |

## Integrated (task 10.1)

| Gate | Command | Result |
|---|---|---|
| Clean-checkout emulation | Copy only tracked + new non-ignored files (`git ls-files -co --exclude-standard`, 252 files; no `.venv`, `node_modules`, `dist*` or `.env`). Then run every CI job's commands with fresh venvs and `npm ci`, a fresh legacy PG test DB, and one new DB per v2 module | legacy pytest **142 passed, 1 skipped**; CLI rc 0; measure M1–M5 PASS; Neon parity rc 0; legacy web test + typecheck rc 0; Pages smoke 18 URLs; v2 pytest **392 passed, 1 skipped**; contracts rc 0; account pages npm ci + unit + typecheck rc 0; production build guard OK; guard trips on the e2e build; pages e2e **5 passed** |
| CI | `.github/workflows/ci.yml` gains the `accounts-pages` job (PG17 service, v2 venv for the harness, unit, typecheck, build guard both ways, Playwright Chromium, e2e) | YAML parses, 8 jobs; not yet run on GitHub (nothing pushed) |
| Foundation gate | `rearchitect-wearhouse-foundation` 7.5, the source-backed thread | still **PENDING**, reported separately (it is the one v2 skip) |
