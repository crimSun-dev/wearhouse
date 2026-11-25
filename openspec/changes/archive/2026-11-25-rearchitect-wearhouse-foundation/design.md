## Context

See `proposal.md` for motivation and scope. Current `backend/app/main.py` creates tables at startup, optionally seeds, mounts frontend assets by relative ancestry and routes v1 APIs. `deps.py` selects a fixed demo user. `registration.py` accepts public serials as ownership credentials; its attempts count/check is not an atomic multi-process admission policy. The public Hono adapter duplicates these behaviours and imports fixtures from `../backend/` and OpenAPI from `../docs/`. Vite and Pages CI use `Frontend/frontend`; `build_pages.py` copies its output to `_site`; the Windows launcher targets `backend/.venv`. These dependencies make a folder-only move unsafe.

Authoritative inputs: Wearhouse TDD v1.1, `CRIMSUN_POOL/UNIFIED_DECISION_MANIFEST_WEARHOUSE_v2.md`, the user-directed fresh frontend override and current inspected code. Local experience is DIGITAL_WARDROBE_HISTORY: PROGRESS-001/002, RULE-001/002, MISTAKE-001/002 and GROWN-001/002. All are recent artifact evidence, not newly passed tests. The generated experience index includes derived-manifest citation false positives; select only the eight original entries. External Understanding Pool path remains pending the earlier clarification; no invented AXIOM/TRAP authority or independent corroboration is claimed.

## Goals / Non-Goals

**Goals:** create a runnable canonical v2 ownership thread, clear module/state boundaries, repeatable migrations/contracts and a verified path migration for the legacy environment. Prove identity and transaction invariants before frontend work; establish source/media and recommendation extension seams without fake feature endpoints.

**Non-Goals:** no new customer/admin screens, bulk catalogue pipeline, checkout/receipt UI, full planner/social functionality, trained inference, real payments, public production cutover or automatic conversion of synthetic ownership. The target web application is reserved, not a copy of old `app.js`. Source/asset originals stay intact.

## Decisions

### D1 — One application with bounded modules and a separate legacy environment

Choose the following target structure, with Python package `wearhouse` to avoid confusion with legacy `app` imports:

```text
apps/
  api/
    pyproject.toml
    src/wearhouse/
      bootstrap/                 # app factory, config, dependency composition
      identity/                  # verification, principal mapping, roles
      catalogue/                 # source product, revision and unit descriptors
      ownership/                 # issuance, credential/claim lifecycle, owned reads
      recommendations/           # typed scoring/model ports and baseline adapters
      weather/                   # gateway contract and reusable validation/rules
      platform/                  # transactions, HTTP errors, IDs, clock, outbox
    migrations/ tests/ fixtures/
  web/                           # later fresh UI; no legacy screen transplant
packages/contracts/
  openapi-v2.json
  src/schema.d.ts
  package.json                   # deterministic generation/type validation only
legacy/
  python/                        # current backend source, fixtures and local demo
  neon/                          # current adapter + seed/parity fixtures
  web/                           # current Vite demo unchanged in presentation
  contracts/openapi-v1.json
research/
  README.md                      # separate source/evaluation and data policy
tools/                           # dev, contracts and legacy build entrypoints
docs/architecture/ docs/runbooks/
Assets/ Reference/ Research Resources/ CRIMSUN_POOL/ openspec/
```

Only modules used by the foundation thread get implemented now. Later commerce, wardrobe composition, planner, social and admin-publishing modules have documented contracts/dependencies in the roadmap, not empty services or routes returning placeholder success. `ownership` owns unit claim state and owned items; `catalogue` owns product facts and immutable revisions. Future modules consume their application interfaces, not their SQL tables directly. `platform` contains infrastructure primitives, never fashion/business rules.

Routers → application services → domain rules/ports; SQL/media/OIDC adapters implement ports and are composed in `bootstrap`. Domain code imports neither FastAPI nor ORM models. Cross-module access goes through explicit application interfaces, and tests check forbidden imports (not merely directory names). No imports from `legacy` into v2. Reuse selected pure rules/weather logic by extracting a v2-owned copy with attribution/behaviour tests; the compatibility runtime keeps its frozen implementation. Do not create a new shared package coupling v1 and v2 releases.

Rejected: a deployable service per menu; no independent scaling/ownership evidence justifies it. Rejected: moving the old app into `apps/api` and keeping demo principals/startup reset paths. Evidence: TDD §6, source imports, MISTAKE-001/002 and latest user directive. Tier: project proposal with explicit source grounding.

### D2 — Path migration is one compatibility change

| Current path / dependency | Target and associated edits |
|---|---|
| `backend/` tracked source/config/tests | `legacy/python/`; preserve local `app` namespace and fixture adjacency; recreate virtual environments rather than copying `.venv` |
| `backend/.env`, SQLite files, local environments | Leave secrets/local state in place until an explicit local migration step; document new config location and fail with actionable error, never auto-copy credentials into source |
| `neon-backend/` | `legacy/neon/`; maintain existing package/lockfile edits; fixture import becomes `../python/fixtures/...`, v1 schema import `../contracts/openapi-v1.json`; update deploy documentation/source argument |
| `Frontend/frontend/` | `legacy/web/`; preserve Vite inputs and customer presentation; update legacy API type path to `../contracts/openapi-v1.json` |
| `Frontend/{BRIEF,DESIGN,PRODUCT,README-frontend}.md` | `docs/legacy/frontend/`; contextualise obsolete claims rather than treating them as current v2 architecture |
| `docs/openapi.json` | `legacy/contracts/openapi-v1.json`; separate from new generated v2 contract |
| `scripts/build_pages.py` | `tools/build_legacy_pages.py`; update frontend path, retain secret-excluding public output and `/LIVE-DEMO/` base; keep root compatibility wrapper during transition |
| `run_demo.ps1` | Retain root entrypoint, resolve `legacy/python` with literal quoted paths; new `tools/dev_api.ps1` uses distinct v2 config/port |
| Legacy FastAPI frontend mounting | Resolve `legacy/web/dist` through explicit repo-root/config path; retain static fallback and deep-link behaviour |
| `backend/app/config.py`, `measure.py` repository ancestry | Update root resolution after relocation; results remain root `results/`, legacy results docs remain explicit; fixtures stay under legacy Python |
| `.github/workflows/ci.yml` | Point legacy Python and Node jobs/cache keys at relocated paths; add independent v2 PostgreSQL, migration, boundary and contract-drift jobs |
| `.github/workflows/pages.yml` | Continue building **legacy** web only, with matching cache/install/typecheck/build paths and existing base/API variable; no v2 rollout from this change |
| Playwright demo/pages configs | Keep tests adjacent to legacy web; verify working directories, API target, preview base and test-only mutations; no unintended calls to v2 |
| Root `.gitignore`, README, deployment/test instructions | Distinguish v2/legacy envs, builds, DB files, datasets and generated output; preserve all existing user changes |
| `_site`, `dist`, `.deployment`, ZIP archives | Treat as existing generated/historical inputs; never bulk-move/publish them with application source or delete them as unsolicited cleanup |
| `Assets`, `Reference`, thesis/research evidence | Keep originals and historical paths; document downstream consumers; no logo processing or photo publishing in foundation |

Move source, not `node_modules`, ignored local secrets, DB files or `.venv`. A working v2 `pyproject.toml` uses a reproducible pinned installation path; independent legacy lockfiles remain intact. No root workspace tool is required merely to create `apps/` and `packages/`.

### D3 — Canonical Python v2, explicit deployment inputs

Use FastAPI/SQLAlchemy/PostgreSQL and Alembic for v2. Pin dependencies during implementation against installed/official support information; do not treat old assumed versions as confirmed. Development binds v2 to port 8100; legacy local API remains 8000. Production artifact is an OCI image running the same ASGI app, with migrations a separate release command. No v2 static frontend mount or legacy imports. A selected Python container host can consume that artifact; no host is assumed provisioned and no network cutover is required to complete the local foundation.

Use `WEARHOUSE_DATABASE_URL`, `WEARHOUSE_ENV`, `WEARHOUSE_OIDC_ISSUER`, `WEARHOUSE_OIDC_AUDIENCE`, explicit allowed origins and an issuance-delivery encryption secret. Missing deployment identity configuration fails startup. Runtime role cannot create/drop schemas. Migration role can operate only the v2 database. Production/debug/test modes cannot be selected by headers.

Bind each v2 database to an immutable environment identity record installed by the migration role, and compare it with the configured expected application family/environment before any runtime write. Legacy startup/seed/reset/measurement entrypoints must perform an equivalent read-only target check before their existing `init_db`/seed calls; reject a v2 identity record and never rely only on URL-name substrings. An unmarked local legacy SQLite database can be explicitly initialised as legacy by the legacy setup command; an unmarked remote database requires explicit environment registration before destructive utilities. Separate DB credentials/roles provide an additional boundary.

OIDC is a configurable standards-based resource-server boundary using issuer discovery/JWKS and an allowlisted asymmetric algorithm (initially RS256), with signature, issuer, audience, expiry and not-before validation, bounded clock skew, bounded JWKS refresh and fail-closed unknown keys. Disable token logging. The actual provider must supply compatible access tokens; browser PKCE/renewal/logout integration is a downstream frontend acceptance test, not implemented by adding auth dependencies. Self-contained signed-token/JWKS integration tests verify the adapter now. An isolated local issuer is a development tool only and cannot be selected in deployment mode. Record the selected production provider/host compatibility evidence before deployed identity release; no provider-specific entitlement API is baked into domain rules.

Rejected: using Neon Functions for Python assumptions; preserving a public fixed owner/key; custom password storage. Evidence: actual public adapter, thesis Table 4, TDD §7, MISTAKE-002 [INFERRED]. Exact provider account and host URL are deployment configuration inputs that do not alter these contracts or task sequence.

### D4 — Actor mapping and authority are server owned

Map `(issuer, subject)` uniquely to local users; a verified new customer can create a minimal private user record. Roles are local server-managed grants, not editable profile fields or arbitrary token claims. A restricted bootstrap CLI grants an initial inventory manager/editor; no HTTP self-elevation endpoint. `catalogue_editor` can ingest/revise source products; `inventory_manager` can issue/revoke credentials; `admin` can do both. Both receive audited actions. Customers redeem and read only their own items. Private-ID probes return 404, role failure 403, invalid/missing token 401. Anonymous public tag lookup exposes only product presentation and public availability, never owner, attempts, credential digest, private attributes or claim details.

Production cannot load a fixed-principal adapter. Tests can inject an explicit principal port only through the test app factory, and the deployment configuration rejects that adapter. Access checks occur on both collection queries and individual resources. ID fields submitted by clients cannot override actor/role.

### D5 — Minimal relational ownership foundation

Create migration-managed tables for source/snapshot, product/revision/variant/media-reference, garment unit, activation credential, owned item, ownership event, attempt bucket/event, idempotency record, encrypted issuance delivery, outbox event, user/subject mapping/role grant. All IDs are UUIDs except preserved source external strings. Unique `(source, external_id)` retains leading zeros; GTIN is optional with issuer/scheme, never synthesized from an H&M ID. Fixture provenance includes source URL, checksum, acquisition/permission record and original fields; annotations remain separate from source facts.

Narrow admin routes ingest one validated source product at a time and issue one unit per request; full bulk import/review/catalogue-publication belongs to the services change. Product revision is immutable. Source product import upserts identity idempotently and creates a revision only on changed normalized content. Unknown source characteristics stay unknown. Retired catalogue visibility cannot erase previously owned item provenance. Media is a permitted versioned reference; no automatic arbitrary URL fetching.

`garment_unit` uniquely owns the 128-bit random public serial and lifecycle. At most one active credential per unit; credential stores a digest of an 80-bit CSPRNG base32 key, formatted as four groups of four. Strict ASCII normalization permits documented case/dashes only. Unique unit FK on `owned_item` prevents double claim even if application logic regresses. No floating owner field on `product`. Item acquisition revision and source remain visible to its owner. Event payloads omit secrets.

Admin issuance uses an idempotency key and a short-lived encrypted delivery envelope, owner-scoped to the issuing staff actor; the lookup table never stores plaintext. Same request can recover its exact response during a 24-hour envelope lifetime, with `no-store` headers and access audit. Redemption erases the envelope; expiry makes retrieval return an explicit delivery-expired response without minting another unit. Authorised revoke/reissue is a separate audited command, invalidates the former key, and is forbidden after claim. Later buyer receipts use a separate buyer-scoped envelope, never the staff delivery record. This resolves hash-only lost-response recovery without claiming hashes are reversible.

### D6 — Public lookup is not proof of ownership

v2 never exposes `POST /garments/scan` or serial-based ownership. Public `GET /api/v2/items/{serial}` returns discovery metadata; GS1 routes are supported only with legitimate identifiers. Before wishlist exists, lookup returns its product reference without a fake saved state. A camera scan/read/link preview creates no ownership mutation.

For `POST /api/v2/redemptions`, authenticate first, then acquire the actor/route/idempotency admission record. Identical already-completed requests return the original owned-item result; different payload reuse returns 409. Redact/HMAC secret-bearing fingerprints and never store/log raw key bodies. Concurrent identical idempotent requests wait/retry to a single result; distinct requests racing the same key produce one claim.

Reserve one of 10 per-user attempts in the preceding rolling hour using a transaction with an actor-scoped lock and persistent attempt timestamps. Reservation commits independently from the claim so failures consume budget. Replay of an already-completed idempotency key consumes no additional attempt. Add configurable IP/global admission budgets with proxy trust explicitly configured; unavailable admission storage fails closed. For a processing record left by a crash, an expiring lease permits recovery without a duplicate effect.

Claim transaction locks credential/unit, checks audience/status, conditionally marks redeemed, inserts owned item, ownership event, outbox and successful idempotency result together, then commits. Injected intermediate failure rolls back all claim effects; admission attempt remains. Other key states return one generic 400 `INVALID_ACTIVATION_CODE`, with no item/owner disclosure. A committed result remains retrievable after restart even if the initial HTTP response was lost. Invalid key replay under a new idempotency key is a fresh rejected attempt. Outbox delivery is retried with event IDs and idempotent consumers; no network call occurs inside the ownership transaction.

Evidence: thesis §3.4.4, PROGRESS-002, MISTAKE-001, GROWN-001/002. The legacy public-QR tests are preserved only in quarantined v1, with inverse assertions in v2. Unclaimed credentials may be bearer or actor-bound by issuance policy; both require authenticated redemption, and actor mismatch uses the generic invalid response.

### D7 — Contract ownership and extension ports

Generate `packages/contracts/openapi-v2.json` from the v2 app without starting DB connections, migrations or network discovery. Generate deterministic `schema.d.ts` using a pinned tool and verify a clean diff in CI. Legacy schema generation remains separate. New client components will import generated types through the contracts package; no frontend implementation is included now.

Foundation route set:

| Method/path | Principal | Behaviour |
|---|---|---|
| `GET /api/v2/health` | public | Minimal service/liveness state; no DSN or identity secrets |
| `GET /api/v2/me` | verified user | Local identity/capabilities without arbitrary role edits |
| `POST /api/v2/admin/source-products` | editor/admin | Narrow source-backed product ingestion |
| `POST /api/v2/admin/unit-batches` | inventory manager/admin | Single-unit issuance and restricted delivery |
| `POST /api/v2/admin/units/{id}/reissue` | inventory manager/admin | Audited unclaimed-unit key rotation |
| `GET /api/v2/items/{serial}` | public | Product discovery only |
| `POST /api/v2/redemptions` | verified user | Atomic private claim with idempotency header |
| `GET /api/v2/me/items` | verified user | Owner-scoped stable cursor pagination |
| `GET /api/v2/me/items/{id}` | verified owner | Private item inspector representation |

Errors carry `{code,message,field_errors?,request_id}`. Private reads are `no-store`. List size defaults to 24, maximum 100; sort by `(created_at,id)` and bind opaque cursors to principal/filter/version, rejecting invalid cursors. Mutation keys scope to actor + route + payload digest; concurrent reuse returns one result, differing body 409. HTTP input validation produces 422, throttling 429 with Retry-After, and service/unavailable admission 503. No arbitrary `owner_id` field accepted for claims/owned reads.

A structurally invalid JSON/body (for example no `code` field) is 422; an authenticated, admitted request containing a credential string with invalid key contents follows the generic 400 invalid-activation contract. Field errors must strip raw input values so validation cannot echo credentials. A processing request interrupted before admission/claim must be recoverable via its lease; it is never reported as successful solely because an idempotency record exists.

Define recommendation ports/DTOs for item features, model version/mode and ranker result; a reusable heuristic baseline adapter has deterministic tests and names its heuristic mode. No model-ready endpoint pretending trained scores exists. Separate catalogue and outfit ranker interfaces share compatibility only. Preserve validation/fallback weather unit contracts (PROGRESS-001); full persistent weather cache/recommendation endpoints move with later services. Stubbed adapters may exist only in tests, not successful production handlers.

### D8 — Readiness requires a runnable thread, not completed folders

Automated integration proof on a disposable migrated PostgreSQL database: provision verified editor/inventory manager/customer A/customer B through test issuer; ingest a legitimate source-backed fixture; issue/retrieve its key; anonymous public lookup; A privately claims; A lists/reads; B gets generic claim failure and 404 for private read; restart preserves ownership; multiple processes race an unbound key with exactly one effect; fault injection between update/insert/event leaves no partial state; distributed attempts cannot exceed 10 reservations/hour. Compare data/event counts, not only response status.

A data-free synthetic unit fixture may exercise lower-level invariants, clearly marked test-only. It cannot satisfy the source-backed product-thread gate. No licensed catalogue row/image is present in inspected source: implementation must obtain a permitted minimal fixture from the intended source and preserve its manifest; if unavailable, record that gate failed/pending rather than inventing H&M metadata. No live external download/account agreement is assumed authorised by this planning task.

Legacy suite/build/CLI and `/LIVE-DEMO/` deep links must pass from relocated paths, including a path with spaces/apostrophe. V2 must refuse a v1 DB target and vice versa. Foundation readiness additionally requires deployed-mode config to reject test auth and original logo/research files to remain intact. Fresh frontend implementation starts only after these gates; later service release gates still apply.

## Risks / Trade-offs

- [Source access/permissions not established] → separate synthetic invariant tests from the source-backed gate; obtain a permitted minimal fixture before claiming foundation completion.
- [Legacy has unsafe semantics by v2 standards] → quarantine by origins, config, credentials and database roles; do not expose legacy as the new account system.
- [Physical codebase move breaks hidden path assumptions] → use the path map, check relative imports/root discovery and run actual legacy builds/tests after each grouped move.
- [Dual maintenance until retirement] → freeze legacy feature scope and prohibit v2 imports into/from it; reuse only tested domain knowledge.
- [Provider/hosting deployment availability] → generic verified-token boundary plus reproducible ASGI container; require actual provider/host integration evidence before deployed release; no fabricated provisioning.
- [SQLite differs from PostgreSQL] → retain SQLite only for legacy/offline compatibility and pure tests; no SQLite concurrency result substitutes for v2 PostgreSQL races.
- [Credential delivery encryption lifecycle adds complexity] → shared, narrowly scoped issuance delivery infrastructure with TTL/rotation/redaction; no plaintext DB lookup or impossible hash recovery.
- [Architecture-first grows into the entire product] → fixed minimal route set and concrete readiness gate; later capabilities assigned in `roadmap.md` rather than blank APIs.

## Migration Plan

1. Inventory working-tree changes and tracked path dependencies; establish repeatable existing legacy checks without overwriting user work. Use an isolated implementation branch/worktree when applying.
2. Relocate tracked legacy sources as mapped; update launch/build/CI/import paths atomically. Keep original secret/local-state files ignored and document manual environment recreation. Verify demo before proceeding.
3. Create v2 package and isolated database, least-privilege runtime/migration roles, migrations and generated contracts. Require explicit identity/env inputs; app startup performs no migrations/seeding. Fail readiness on schema mismatch.
4. Prove the ownership thread, rollback, race/attempt/idempotency/role invariants and restart behaviour. Record source fixture and deployment readiness evidence separately. No public frontend target changes.
5. Downstream changes build persisted services, new frontend, research intelligence and final production release per roadmap. Rehearse extraction/owner mapping rather than treating demo seed IDs as verified users. Historical QR claims stay `legacy_synthetic/unverified` in their isolated database, not in a real library by inference.
6. Final cutover (later change): backup/restore verification, freeze v1 writes, validate source/owner maps and FKs, switch frontend/API configuration, then enable v2 writes. Before new writes rollback can restore old config/snapshot. After new writes, rollback requires reconciliation or forward fix to avoid losing purchases/claims. Never use demo reset as rollback.

For this foundation only, rollback disables new v2 traffic and restores legacy source/config references; isolated v2 data is retained for audit rather than deleted. Production remains on v1 throughout this planning/implementation scope.

## Open Questions

- Deployment account/hostname and OIDC issuer/audience values are environment inputs; supported-token/resource-server contract is fixed above. Verify those values and real session behaviour before deployed release.
- Which permitted H&M minimal fixture can be acquired under the user's accepted dataset terms? Its required provenance/format/gate are fixed above; no substitution with fabricated source records is permitted.
- External Understanding/Experience pool directory remains pending the earlier request; material new authority requires a versioned manifest/proposal revision, not a claimed audit pass.
