## 1. Evidence, environments and implementation baseline

- [x] 1.1 Record current tracked/untracked changes and existing legacy commands in `docs/architecture/migration-inventory.md`, preserving user edits; verify the inventory includes all paths in design D2 and unchanged source asset checksums.
- [x] 1.2 Record supported Python/container and OIDC access-token requirements in `docs/architecture/runtime-identity.md`; verify a local signed-token/JWKS fixture satisfies the configured issuer/audience/RS256 contract and document actual external deployment inputs separately.
- [x] 1.3 Obtain or identify a permitted minimal H&M source fixture and permission/checksum manifest for `apps/api/fixtures/source-products/`; verify source IDs/original fields and terms record, or explicitly leave the source-backed readiness gate pending while proceeding with labelled lower-level tests.
- [x] 1.4 Capture legacy Python, CLI, Node parity, frontend unit/typecheck/build and offline-measurement baseline results on isolated data; verify no command targets v2/customer data and record existing failures without masking them.

## 2. Relocate and preserve the legacy environment

- [x] 2.1 Relocate legacy Python tracked source to `legacy/python` and v1 OpenAPI to `legacy/contracts/openapi-v1.json`; update config/root discovery, results paths and static frontend mount; verify legacy Python unit/integration/CLI and measurement output paths.
- [x] 2.2 Relocate the adapter to `legacy/neon` preserving manifest/lockfile edits and fix fixture/schema imports; verify `npm ci` and Node parity tests resolve all imported files from the new location.
- [x] 2.3 Relocate old web source to `legacy/web`, preserve its renderer and update v1 type-generation/proxy/base paths; verify unit tests, typecheck, build and local Pages deep-link smoke tests.
- [x] 2.4 Move obsolete frontend documentation to `docs/legacy/frontend`, update root `run_demo.ps1` and add explicit local-environment recreation instructions; verify the launcher resolves a repository path with spaces/apostrophe without copying `.venv`, secrets or databases into tracked source.
- [x] 2.5 Introduce `tools/build_legacy_pages.py` with a compatibility wrapper at `scripts/build_pages.py`; verify `/LIVE-DEMO/` artifacts contain only frontend/public config and exclude secrets, source datasets and local state.
- [x] 2.6 Update existing `.github/workflows/ci.yml` and `pages.yml` working directories, cache keys and source commands together; verify all referenced paths exist and equivalent local legacy checks pass, leaving Pages pointed at legacy v1.

## 3. Canonical API package, boundaries and migrations

- [x] 3.1 Create installable `apps/api` src-layout package `wearhouse`, pinned reproducible dependencies and `tools/dev_api.ps1`; verify import/app-factory/health smoke tests and a distinct v2 port 8100.
- [x] 3.2 Implement `bootstrap`, domain/application/adapter interfaces for identity/catalogue/ownership and focused platform infrastructure; add forbidden-import checks and verify domain code does not import FastAPI/ORM/legacy modules.
- [x] 3.3 Add isolated v2 runtime/test/migration configuration examples and database-role/environment safeguards; verify wrong-target, missing-config, unsafe test-auth and insufficient-role startup tests fail closed.
- [x] 3.4 Add Alembic migration configuration and initial subject/user/role, source/product/revision/variant/media-reference tables; verify upgrade from empty PostgreSQL, repeated upgrade and stable leading-zero external IDs.
- [x] 3.5 Add unit/credential/owned-item/event, persistent attempt, idempotency/delivery and outbox tables with uniqueness/FK/status constraints; verify duplicate unit ownership and duplicate live credentials are rejected by the database.
- [x] 3.6 Ensure v2 startup only validates schema readiness and never seeds/migrates/resets; verify startup against stale schema fails without changing row counts or schema version.
- [x] 3.7 Define typed compatibility/ranker/weather ports, extract tested pure baseline/validation behaviour and label heuristic modes; verify deterministic baseline/forecast validation/fallback contracts without trained-model or external-service assumptions.

## 4. Identity and access foundation

- [x] 4.1 Implement deployment token verification with bounded discovery/JWKS refresh and allowlisted algorithm; verify missing/expired/wrong-issuer/wrong-audience/unknown-key cases and controlled key-rotation fixtures return the specified outcomes.
- [x] 4.2 Implement unique issuer/subject-to-user mapping and `/api/v2/me`; verify concurrent first access creates one customer account, restart retains identity and no staff role is self-granted.
- [x] 4.3 Add server-owned role grants/bootstrap CLI and route capability policies; verify editor can ingest but cannot issue, inventory manager can issue but cannot edit products, and customer attempts receive 403.
- [x] 4.4 Implement explicit test-only principal injection with deployment rejection and request-ID/redaction middleware; verify headers/query/client owner IDs cannot enable test mode, impersonate or leak tokens.

## 5. Source products and serialized-unit issuance

- [x] 5.1 Implement narrow `POST /api/v2/admin/source-products`, repository/application boundaries and immutable revisions; verify identical imports upsert one identity, changed facts retain prior revisions, and missing provenance is rejected.
- [x] 5.2 Implement single-unit `POST /api/v2/admin/unit-batches`, CSPRNG serial/key generation, strict key parser and digests; verify independent units of one product, required entropy/format and absence of plaintext lookup storage.
- [x] 5.3 Add scoped issuance idempotency and encrypted 24-hour delivery with no-store responses and redacted audit events; verify lost-response retries return one unit, another actor cannot retrieve its key and expiry/claim removes secret delivery without reminting.
- [x] 5.4 Implement audited unclaimed-unit revoke/reissue; verify former key invalidation, preserved unit identity, one active credential and 409 for claimed units.
- [x] 5.5 Implement public discovery-only `GET /api/v2/items/{serial}`; verify repeated GET/link preview creates zero claim rows and response omits owner/credential/attempt data.

## 6. Transactional redemption and owned reads

- [x] 6.1 Implement durable per-actor rolling-hour admission and configurable IP/global budgets in `ownership`; verify multi-process limit-boundary, restart, independent failure accounting and unavailable-store fail-closed tests.
- [x] 6.2 Implement actor/route/request-scoped idempotency reservation, processing lease and replay handling; verify identical retries do not reserve another attempt, changed body returns 409 and abandoned processing can recover safely.
- [x] 6.3 Implement `POST /api/v2/redemptions` transaction for credential/unit/item/event/outbox/success result; verify genuine claims, actor-bound rejection and generic malformed/unknown/altered/public/revoked/reused failures.
- [x] 6.4 Add PostgreSQL two-user/multi-process claim races and failure injection between each claim effect; verify exactly one winner/item/event, no partial claim, retained attempt reservation and one effect after lost-response restart retry.
- [x] 6.5 Implement `/api/v2/me/items` and item detail with principal-scoped repositories, stable bounded cursors and no-store responses; verify cross-user 404/list isolation, cursor actor binding and source/acquisition metadata.
- [x] 6.6 Add outbox dispatch/retry infrastructure with idempotent event IDs; verify rollback creates no deliverable event and repeated dispatch causes no duplicate downstream effect.

## 7. Contracts, delivery tooling and integrated readiness

- [x] 7.1 Implement consistent v2 errors/field-validation/request identifiers and route declarations; verify 400/401/403/404/409/422/429/503 shapes and secret-free response/log capture.
- [x] 7.2 Create offline-safe schema export and pinned `packages/contracts` OpenAPI-to-TypeScript generation; verify two clean generations match and CI detects stale types/API output without DB/network access.
- [x] 7.3 Add v2 container artifact, explicit release-migration command and role-scoped health/readiness checks; verify local container build/start, stale-schema failure and absence of startup migration/seed effects.
- [x] 7.4 Add independent PostgreSQL v2 test/migration/contract/boundary jobs to CI; verify relocated legacy checks and new jobs can run from a clean checkout without shared writable DB state.
- [x] 7.5 Execute the source-backed admin → unit → public lookup → private claim → owner read thread with signed test identities, restart and customer-B negative cases; verify against actual DB/event counts and retain fixture/test evidence in `docs/architecture/foundation-readiness.md`.
- [x] 7.6 Rehearse wrong-environment rejection and foundation rollback without deleting v2 state or resetting customer data; verify legacy can still run independently and all original brand/research file checksums match.
- [x] 7.7 Publish updated root setup/API/deployment/runbook docs and a readiness matrix referencing GROWN-001/002; verify every claimed gate has a command/result and keep provider/source/cutover limitations explicit.
- [x] 7.8 Audit `roadmap.md` F01–F13/research coverage and record the foundation stop gate; verify no new frontend screens or borrowed legacy renderer exist in `apps/web` and do not begin the frontend apply workflow as part of this change.
