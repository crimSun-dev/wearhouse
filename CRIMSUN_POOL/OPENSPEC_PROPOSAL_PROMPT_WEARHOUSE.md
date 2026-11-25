# Wearhouse — OpenSpec proposal prompt

Copy the prompt below into a new agent session rooted in this repository. It requests proposal artifacts, not implementation. The first change establishes the architecture; later changes implement services and rebuild the frontend. The supplied logo assets were visually inspected when preparing this prompt.

---

Use `$openspec-propose`, `$expert-pipeline`, and `$adaptation-growth-pipeline` to prepare an implementation-ready OpenSpec proposal for **Wearhouse**.

## Objective and controlling direction

Wearhouse is a fashion catalogue, owned-wardrobe and styling ecosystem inspired by Steam's separation of Store, Library, Community and Profile. We are replacing a single-user course demo with a coherent application. **Restructure the repository and architecture first. Prove the new backend boundaries, identity, ownership and API contracts before rebuilding the frontend entirely from scratch.** A rename, folder shuffle or CSS reskin does not satisfy this request.

The latest user direction overrides the TDD's incremental extraction of the old frontend. A fresh presentation layer is required after the architecture/service gates. Retain suitable technologies and verified domain rules; do not copy the old monolithic page renderer, layout, route state or demo UI into a new directory and call that a rebuild. A new framework is not mandated: Vite, TypeScript and Three.js remain the baseline unless an explicit, evidence-backed ADR establishes a better fit.

This invocation is **planning only**: create the required proposal/design/delta-spec/task artifacts and a dependency roadmap. Do not apply changes, move application files, install dependencies, modify deployed resources or start the frontend implementation in this turn.

## Read these authoritative inputs

1. `CRIMSUN_POOL/TDD_Digital_Wardrobe_Ecosystem_v1.md` — Wearhouse TDD v1.1; retain historical filename.
2. `CRIMSUN_POOL/UNIFIED_DECISION_MANIFEST_WEARHOUSE_v2.md` — latest architecture-first/front-end-rebuild revision, including the controlling sequencing override.
3. `CRIMSUN_POOL/UNIFIED_DECISION_MANIFEST_DIGITAL_WARDROBE_v1.md` — previous decisions and rationale.
4. `CRIMSUN_POOL/DIGITAL_WARDROBE_FOUNDATIONAL_EXPERIENCE.md` — eight real experience entries; preserve source identity.
5. `CRIMSUN_POOL/ARCHAEOLOGY_REPORT_DIGITAL_WARDROBE.md`, `CRIMSUN_POOL/HISTORICAL_EVENT_STREAM.md`, and `CRIMSUN_POOL/RESEARCH_EXTRACT.txt`.
6. `Research Resources/Digital_Wardrobe_Capstone_Ch1-3_v11_Methodology.docx` where exact research context or formulas need verification.
7. All four screenshots under `Reference/`: Store, menu, Library and Big Picture. Inspect them visually.
8. Exact supplied assets under `Assets/`:
   - `208131bb-60d2-479d-8546-16acbd429bd1.png` — standalone plum roof/window and fabric-W emblem.
   - `03b20ba8-8da5-4430-a532-394cd61085c8.png` — horizontal emblem plus Wearhouse wordmark.
   - `Plum House Ribbon Logo.png` — brand presentation board with ivory background, horizontal lockup and blush app-icon example; use as colour/context reference, not the entire navbar logo image.
9. `openspec/config.yaml`, applicable `AGENTS.md`, local OpenSpec skill instructions and the actual source/build/test/deployment files.

Read current files from disk; do not treat a prior summary as proof of unchanged code. In this baseline the public application is a Node/Hono Neon Function, while Python/FastAPI is the local/research implementation. Frontend is Vite with mostly JavaScript, TypeScript tooling and Three.js. Newly present auth dependencies do not prove authentication exists.

## Evidence and skill discipline

Index/select before consulting pools. The external Understanding/Experience pool path has not been supplied in this conversation; ask for it if still missing, while progressing independent repo-grounded planning. Do not guess a path or claim an Expert Pool audit passed. Use the known local foundational experience module, clearly distinguishing it from the missing external pool. Exclude manifests, prompts and reports that the index may falsely parse as independent modules because they quote entry IDs.

Carry forward **PROGRESS-001** (weather validation/provenance/recovery), **PROGRESS-002** (transactional one-time claim mechanics), **RULE-001** (destructive test isolation), and **RULE-002** (legacy scoring parity while v1 operates), all from DIGITAL_WARDROBE_HISTORY. Explicitly name **MISTAKE-001** (public QR ownership) and **MISTAKE-002** (shared demo identity/key) wherever matching patterns arise. They are unresolved hazards, not fixed incidents. **GROWN-001/002** define proposed claim and isolation gates; do not report them achieved without tests.

Cite real source paths/requirements and evidence tiers. New design choices without Pool coverage are project proposals or labelled inferences, with named gaps. Log novel decisions as growth breadcrumbs, deduplicate against actual module files and end with produced/confirmation/repeated-mistake counts. Do not manufacture historical successes or cross-pool bridges.

## OpenSpec workflow and requested scope

Follow the installed OpenSpec CLI and skill instructions, including context/store resolution, artifact templates, dependency order and validation. The repository currently declares `schema: spec-driven` and has no authored capability specs; verify this remains true. Use the CLI's resolved root/output paths rather than assuming them.

Create the first concrete change named **`rearchitect-wearhouse-foundation`**, unless it already exists; handle collisions through the skill's workflow. Generate its full required artifact set: proposal, design, capability delta specs, and tasks. Use current `openspec instructions` as authority over the older example templates in the expert skill. Run the available validation and report exact results; do not imply a prompt or file-existence check is an implementation test.

Include a dependency roadmap for later separately scoped changes. Fully plan the first change now; subsequent changes get explicit scope, prerequisites and exit criteria, not fabricated completed OpenSpec artifacts:

1. **`rearchitect-wearhouse-foundation`** — target structure, canonical Python application, boundaries/contracts, migration scaffolding, authenticated ownership foundation, legacy isolation and CI/dev tooling.
2. **`implement-wearhouse-ecosystem-services`** — complete persisted catalogue/admin, commerce/receipt, wardrobe/planning and social/profile services required by the new UI; integrate shared recommendation interfaces with honestly labelled baseline mode. Split into smaller dependent changes if needed; give each a named contract and gate.
3. **`rebuild-wearhouse-frontend`** — entirely new customer/admin presentation from the TDD, references and real logo assets, consuming proven v2 services.
4. **`complete-wearhouse-research-intelligence`** — trained embeddings/compatibility, BPR retrieval/reranking and reproducible RQ1–RQ4 evaluation; preserve research limitations and no fabricated outcomes.
5. **`harden-and-cutover-wearhouse`** — full-scale/device/accessibility tests, source-asset permission clearance, migration rehearsal, backup restore and controlled cutover.

The dependency gate is substantive: a fresh frontend can be designed against stable contracts once the architecture gate passes, but it must not be implemented as a substitute for unfinished identity/ownership foundations. UI release requires its actual persisted services. Research jobs may use the new architecture independently; untrained modes stay labelled throughout.

## First-change design requirements

### Repository and boundaries

Propose one clean target tree and a per-path transition map from the current tree. A suitable starting point is `apps/api`, `apps/web`, `packages/contracts`, `research`, `tools`, `docs`, and a clearly isolated legacy area; choose exact paths based on actual imports/tooling, not aesthetics. `apps/web` may be reserved in the foundation plan without building replacement screens. Distinguish preserved legacy code, extracted reusable domain code, new modules, generated outputs, research datasets and deprecated build artifacts. Preserve the original Assets/Reference/research files and document their roles.

Within the canonical Python API, separate routers, application services, domain rules and persistence/adapters. Establish bounded modules for identity, catalogue/media, commerce, ownership/redemption, wardrobe/outfits, planner, recommendation/weather, social/profile and admin/audit. Specify permitted dependency directions and enforce critical boundaries with meaningful checks. Avoid empty-service scaffolding, a universal dumping-ground `shared` module, and a microservice deployment for each menu.

For each moved path specify required import, relative-path, package, lockfile, test, launch script, Vite/proxy, generated API type, build and CI changes. Inspect `scripts/build_pages.py`, `.github/workflows/{ci,pages}.yml`, `run_demo.ps1`, FastAPI static mounting and frontend test configuration before writing the task list. A folder move that leaves those pointing at old locations is incomplete.

### Runtime, contracts and state

FastAPI/Python is the canonical new domain and research-serving runtime; Neon Postgres remains the database. Legacy Node/Hono stays isolated until retirement and does not grow a second implementation of new-domain logic. Record a Python-capable deployment target/session-provider feasibility decision without pretending a host is provisioned. OIDC provider selection must verify issuer/audience/session/logout behaviour and supported browser flow. Do not replace user identity with owner IDs submitted by clients.

Define `/api/v2` schemas and a reproducible OpenAPI-to-TypeScript generation path. Establish request principal/roles, resource scoping, error envelope, pagination, version conflicts and mutation idempotency. Own persisted state on the server. Keep customer and admin permissions distinct. Define recommendation/model ports and baseline mode early; training need not block the initial ownership thread.

Use versioned relational migrations and isolated v2 schema/branch; no startup reset or schema recreation for customer data. Model product definition, source ID, variant, serialized unit, activation credential and owned item separately. Avoid GTIN as the only product identity. Include ownership events, media/provenance records and transactional outbox/idempotency infrastructure where the chosen thread requires them. Define contract/schema ownership so later features cannot bypass the domain.

### Required runnable proof before frontend work

Specify a minimal integration thread executable through API tests/CLI, without a redesigned frontend: an authorised admin imports/creates a source-backed test product fixture, issues a unit/private key, a verified customer performs a public read-only lookup and privately redeems the key, then lists the persisted owned item. A second customer cannot redeem the same key or read private records. Public QR contents cannot claim ownership. Exactly one claim wins under concurrent PostgreSQL transactions and failed intermediate writes roll back. Test principals are allowed only through an explicit test adapter; they are not the deployment identity solution.

The fixture must retain real source provenance; generated test serials/keys are allowed. If dataset access is unavailable, specify the narrow missing prerequisite and a separate lower-level invariant test; do not call invented catalogue records a real-source integration proof.

Test owner/role isolation, rate limiting across processes, restart persistence, migration reproducibility, rollback boundaries, legacy/new writer isolation and retention of weather recovery contracts. Avoid placeholder endpoints that return success without persistent effects.

### Legacy preservation and release migration

Treat the current demo as a separately runnable compatibility environment. Retain applicable local/SQLite and legacy scoring tests while they are still supported; use PostgreSQL for concurrency/migration guarantees. Identify public-QR tests that must be replaced under v2, while legacy behaviour stays explicitly quarantined. Preserve course measurement scripts and fixtures without letting them reset customer data.

Supply staged rollout and rollback plans, owner/source-ID mapping and handling for legacy synthetic/QR-claimed records. No inference of real ownership from old demo data. Explain the point beyond which reverting a database snapshot would lose new transactions. Preserve user changes already present in manifests/lockfiles; no blanket reset or destructive cleanup.

## Requirements for downstream service and frontend proposals

Carry forward every TDD requirement F01–F13 in the roadmap with owning change and acceptance gate. Include the complete admin import/review/publish/retire flow; legitimate H&M source catalogue with preserved IDs and permitted imagery; Polyvore compatibility data; generated registration fixtures kept distinct; mock cart/order/receipt/key → redemption → wardrobe; manual/thrifted add; typed slots/category GLB templates and 2D fallback; saved looks/planner/actual wear; accepted friends/blocks/explicit sharing/private profiles; customisation and notifications.

Share FashionCLIP embeddings/type-aware compatibility across rankers, but keep catalogue BPR/content retrieval + completion/duplicate reranking separate from owned-outfit rules/preference/recency. Fix the public-QR privilege mismatch and audit the Polyvore non-disjoint/unseen-item claim. A seven-day timeline does not imply seven days of live BMKG forecast. Model targets in brackets are proposed settings, never achieved results.

The fresh frontend must express Steam's destination hierarchy with Wearhouse's fashion identity: **Catalogue, Wardrobe, Community, My Profile**, dedicated Redeem destination, scoped secondary controls and a separate admin workspace. Use photographic portrait product/owned-item tiles, a useful inspector, outfit objects, intentional shelves and an optional Big Picture-inspired Focus mode with one dominant selection. Include the profile's functional seven-day timeline. Follow the supplied references' organisation and selection behaviour rather than reproducing Steam's trademark artwork or stuffing all features on a dashboard.

Use the supplied emblem and wordmark, preserving proportions, silhouette and source files. Plan semantic production asset names, responsive sizing, accessible text, favicon/app-icon derivatives and light/dark surface checks. Verify actual transparency/padding before integration. Do not regenerate the logo, invent a different W, redraw it as a low-quality SVG or apply an unrequested redesign. A plum mark may need a lighter brand surface in dark Focus mode; preserve legibility deliberately.

Specify fresh theme tokens, responsive shell, routing, typed API client, server/query state, private-cache cleanup, accessible components, media handling and avatar lifecycle. All catalogue, library, commerce, redemption, planner, social and admin screens need loading/empty/error/permission states and actual service contracts. No returning the old HTML renderer with new colours. Core flows must work at mobile/desktop widths and by keyboard; maintain a grid alternative to rails and a 2D fallback to Three.js.

## Required proposal output quality

- Proposal: concrete problem, first-change scope/non-goals, new capabilities and impact. Distinguish architecture completion from later ecosystem completion.
- Design: target tree, dependency graph, current→target path map, ADRs with real evidence, contracts/data state, credential lifecycle, CI/build changes, migration/cutover, alternatives and explicit gaps.
- Delta specs: observable SHALL/MUST requirements with named Given/When/Then scenarios for isolation, public lookup vs private claim, one-winner concurrency, migration safety and compatibility. If no canonical requirement exists, use ADDED rather than inventing a MODIFIED/REMOVED spec; record legacy observations in design/impact.
- Tasks: numbered unchecked implementation steps small enough to review; dependency-ordered, with meaningful verification, concrete file targets, stop gates and no frontend remake before foundation readiness. Do not check off future tasks based on design completion.
- Roadmap: map all F01–F13 and research obligations to later changes, with prerequisites, acceptance criteria and intentional sequencing revisions from the older TDD.
- Final report: resolved planning location, created artifacts, validation results, pending evidence/feasibility gates and growth tally. Stop after planning; later implementation uses an explicitly requested apply workflow.

Complete the first change's required artifact graph. Do not finish with a generic recommendation, a TODO to analyse the repository later, or only a proposal.md while specs/design/tasks are missing.

---

**Prompt preparation audit:** project code, logo files and OpenSpec configuration unchanged. This file is a prompt, not a generated/validated OpenSpec change. See [updated unified decision record](UNIFIED_DECISION_MANIFEST_WEARHOUSE_v2.md) for local evidence limits and sequencing revisions.
