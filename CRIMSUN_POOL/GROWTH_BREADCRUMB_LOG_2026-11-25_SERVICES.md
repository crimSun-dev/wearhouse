# Growth Breadcrumb Log — Wearhouse services build (catalogue, commerce, wardrobe, social, H&M import)

**Date:** 2026-11-25. **Produced:** 6 new drafts and 4 confirmations. **Repeated-mistake actions:** 0.

**Deduplication.** DIGITAL_WARDROBE_HISTORY was read in full. It has no entries on SQL insert results, SPA rendering, UI select defaults, privacy ceilings, or licensed-data handling, so none of these drafts duplicates an existing entry. The confirmations update existing entries instead of minting new ones.

## Confirmations (no new entry)

- **GROWN-001:** achieved in v2. It was proven again by the commerce cancel-versus-claim race test (exactly one winner over 3 rounds).
- **GROWN-002:** achieved in v2. Owner-only isolation is tested in every new service.
- **PROGRESS-001:** confirmed. The v2 weather gateway keeps the contract, and a live BMKG fetch returned 17 valid slots.
- **PROGRESS-002:** confirmed. Commerce cancellation reuses the credential-then-unit lock order from redemption.

## New drafts (TIER-0)

- **MISTAKE-DRAFT-A [IMPACT-MEDIUM]:** In a hash-routed vanilla SPA, a slow async render for a route the user had already left overwrote the next page. It surfaced as flaky e2e clicks ("element was detached from the DOM"). **Correction applied:** routes run one at a time, in order, and `view()` drops a render whose hash is no longer current. A guard comparing against the *latest* route alone was not enough. [SRC: Wearhouse / apps/web/account-pages/src/main.ts, ui.ts / 2026-11-25]
- **MISTAKE-DRAFT-B [IMPACT-MEDIUM]:** A select helper set `value = ''` when no option had that value. The browser then left the select empty, so a share audience was sent blank (422). **Correction applied:** a value is only set when an option has it; otherwise the first option is kept. [SRC: Wearhouse / src/ui.ts / 2026-11-25]
- **RULE-DRAFT-C:** IF success detection relies on `rowcount` after `INSERT … ON CONFLICT DO NOTHING` (SQLAlchemy 2.1 + psycopg3) THEN use `RETURNING` and test for a row BECAUSE rowcount came back `-1` and a fresh shelf was reported as a name clash. [SRC: Wearhouse / wardrobe and commerce adapters / 2026-11-25]
- **RULE-DRAFT-D:** IF sharing visibility is capped by a privacy setting that defaults to private THEN show the owner the effective audience BECAUSE otherwise a share succeeds while being visible to nobody. [SRC: Wearhouse / social application, `effective_audience` / 2026-11-25]
- **PROGRESS-DRAFT-E:** Computing visibility and notifications at read time from source records made "unfriend, block or privacy reversal invalidates access" true by construction. No invalidation code was needed, and the tests proved it for shares, the feed, notifications, the week view and the showcase. [SRC: Wearhouse / tests/test_social.py / 2026-11-25]
- **RULE-DRAFT-F:** IF a licensed dataset whose terms forbid redistribution is dropped inside a repository THEN git-ignore it (and any fixtures derived from it) before any processing BECAUSE the folder arrived un-ignored, and one routine commit or push would redistribute it. [SRC: Wearhouse / .gitignore, H&M DATABASE / 2026-11-25]

## Tally

6 new drafts and 4 confirmations. 0 logged mistakes repeated. The session produced more than it repeated: no Growth Alert.

These can be appended to DIGITAL_WARDROBE_HISTORY as PROGRESS-003, RULE-003..006 and MISTAKE-003..004 on request. Nothing has been appended yet.

## Session continuation: recommendation serving + hardening (2026-11-25)

- **[TIER-0] MISTAKE draft (IMPACT-MEDIUM, corrected):** the per-caller write limit was first keyed by a digest of the `Authorization` header at the edge. A test that minted 3 tokens for one user exposed it: fresh tokens reset the budget. Fix: key the write limit by the verified user id after authentication; keep only IP/global at the edge. Lesson: any limit meant to be "per user" must key on a server-verified identity, never on client-presented bytes. BRIDGE: SNHU CS-305 TRAP-054, SYSTEM_DESIGN RULE-033.
- **[TIER-0] MISTAKE draft (IMPACT-LOW, corrected):** `from_env` patch used `env.get` while the mapping was named `e`. It would have crashed every deployment start. Caught by reading the helper before trusting the patch. Lesson: confirm local names in the function you patch.
- **[TIER-0] PROGRESS draft (IMPACT-MEDIUM):** recommendation responses always carry `ModelInfo`; `trained` is only reported with a model hash from a sha-verified artifact, with an explicit `fallback` note when the artifact has no neighbours. Keeps the "never fabricate model results" rule enforced in the API shape, not just docs.
- **[TIER-0] PROGRESS draft (IMPACT-HIGH):** the F11 acceptance thread (HTTP only, fresh app on the same DB, stranger isolation over every private object) passed first time after a test-side fix. It is the single best regression guard before frontend work.
- Confirmation note: MISTAKE "test helper returns identical tokens within one second" (tokens are deterministic per `iat`). Tests that need distinct tokens must set `now`.

Tally: 4 new breadcrumbs + 1 confirmation; 0 logged mistakes repeated.

## Session continuation: sizes, research close-out, archive (2026-11-25)

- **[TIER-0] MISTAKE draft (IMPACT-MEDIUM, corrected):** first size filter was a correlated EXISTS over a 500k-row child table; at full scale the planner drove from the child index and sorted every match (250-300 ms). Measured on the real 105k catalogue BEFORE closing the task, fixed with a denormalised GIN-indexed array kept in step by the repository (12 ms). Lesson: "filter by child-table membership + newest-first LIMIT" needs measuring at real cardinality; a denormalised array lets the planner walk the sort index. Confirms the 0009 lesson (measure at 105k, not on fixtures).
- **[TIER-0] MISTAKE draft (IMPACT-LOW, corrected):** a new reference-data seed broke the "startup performs no writes" test (it counted any inserted table). The seed is migration work, not startup work; the exclusion is explicit and commented. Also: tests that edit reference data must reset it (clean_db now reseeds the size registry from the migration's own constant: one source).
- **[TIER-0] MISTAKE draft (IMPACT-LOW):** started a full suite in the background, then changed the schema head mid-run; the run reported hundreds of stale-schema errors. Never edit migrations/SCHEMA_HEAD while a suite is running; rerun after.
- **[TIER-0] PROGRESS draft (IMPACT-MEDIUM):** cross-module reference data (sizes) served through one catalogue port + a pure `SizeIndex` in catalogue/application lets commerce, ownership and wardrobe validate/present sizes without touching catalogue tables; the AST boundary test stayed green with no exceptions.
- **[TIER-0] PROGRESS draft (IMPACT-MEDIUM):** honest mock data: rule-generated sizes carry `origin: rule` end to end and the store labels them "generated sizes: the source has none" (same pattern as GENERATED PLACEHOLDER media).
- Confirmation note: OpenSpec archive merged 96 requirements from 8 changes into 31 main specs with zero conflicts because every delta was ADDED-only.

Tally: 5 new breadcrumbs + 1 confirmation; 0 logged mistakes repeated (the measuring-at-scale lesson was applied, which is how the slow query was caught before close).

## Session continuation: settings + account security (2026-11-25)

- **[TIER-0] PROGRESS draft (IMPACT-HIGH):** passwords stay entirely with the identity broker; the API exposes only a security overview built from its own audit log. Verified a library claim by reading the installed code (better-auth `resetCredentialPassword` creates the credential for Google-only users) instead of assuming it, and listed what can only be proven against the real Auth branch.
- **[TIER-0] PROGRESS draft (IMPACT-MEDIUM):** settings as a code-side registry + one versioned JSONB row: new keys need no migration, the schema drives a generic UI, and the version gives honest cross-device conflict handling (409, never a silent overwrite). Every setting either changes server behaviour or is labelled as client-applied in the readiness doc; none are decorative.
- **[TIER-0] MISTAKE draft (IMPACT-LOW, corrected):** reset page changed the URL hash before rendering, so the stale-render guard dropped the success view. Lesson: when a page rewrites its own URL, keep the route segment and strip only the sensitive query.
- **[TIER-0] MISTAKE draft (IMPACT-LOW, corrected):** a TypeScript parameter property broke `node --test` (strip-only TS). Keep page modules to erasable TypeScript syntax.
- **[TIER-0] MISTAKE draft (IMPACT-LOW, caught by the safety check):** tried to write a dataset permission record with an inferred acceptance date before the owner confirmed it. Permission/acceptance facts are the owner's statement, recorded only after explicit confirmation.

Tally: 5 new breadcrumbs; 0 logged mistakes repeated.

## Session continuation: thesis-exact outfit recommender (2026-11-26)

- **[TIER-0] PROGRESS draft (IMPACT-HIGH):** app and research share one rule vocabulary, enforced by a parity test that reads the research config. Divergence between "the product's recommender" and "the thesis's recommender" is now a failing test, not a silent drift.
- **[TIER-0] MISTAKE draft (IMPACT-MEDIUM, corrected):** SQLAlchemy JSONB stores Python None as JSON `null`, not SQL NULL; an `IS NOT NULL` filter then returns it and `dict(None)` crashes. Use `sqlalchemy.null()` when clearing a JSONB column.
- **[TIER-0] MISTAKE draft (IMPACT-LOW, corrected):** a test asserted that ciphertext never contains "20" — flaky by construction. Assert on the real secret values (and the decoded bytes) instead of a short substring.
- **[TIER-0] MISTAKE draft (IMPACT-MEDIUM):** session restarts kill scratchpad-hosted processes (dev Postgres, API, Vite). Symptom: tests hang on connection timeouts. Check `pg.log` for "terminated by exception 0x40010004" and restart with pg_ctl before debugging code.
- **[TIER-0] MISTAKE draft (IMPACT-LOW, corrected):** documented research run commands omitted `PYTHONPATH=research/src` (package not installed); the first real run failed in 1 s. Run documented commands literally before publishing them.
- Finding (research): RQ2 type-aware compatibility on text embeddings: AUC 0.530 vs shared-space 0.515 (published image model ~0.86). Recorded as a limitation, not hidden.

Tally: 5 new breadcrumbs + 1 finding; 0 logged mistakes repeated.

## Session continuation: TDD completion (2026-11-26)

- **[TIER-0] PROGRESS draft (IMPACT-HIGH):** release bars measured on the real 105k catalogue over HTTP with a dedicated dev-mode instance (local JWKS, raised edge limits) instead of weakening the test-env database guard; measurement users removed through the normal account-deletion API. All three §14 budgets passed with margin.
- **[TIER-0] PROGRESS draft (IMPACT-MEDIUM):** least-privilege preserved while adding revocation: column-level UPDATE grant on owned_item (revoked_at, revoked_reason) only; ownership rows otherwise immutable for the runtime role.
- **[TIER-0] MISTAKE draft (IMPACT-LOW, corrected):** hand-written migration used full constraint names without op.f(); the naming convention prefixed them twice. Wrap explicit constraint names in op.f() when the metadata has a naming convention.
- **[TIER-0] MISTAKE draft (IMPACT-LOW, corrected):** a cross-module import of a non-public module (`recommendations.rules`) violated the layering rule; renamed to `domain`. The AST boundary test caught it immediately — keep running it after every new module.
- **[TIER-0] RULE draft (IMPACT-MEDIUM):** research labels the thesis requires from a human are produced by a human-in-the-loop tool, pinned by checksum manifest, and the runner reports "not supplied" until then — never synthesized.

Tally: 5 new breadcrumbs; 0 logged mistakes repeated.
