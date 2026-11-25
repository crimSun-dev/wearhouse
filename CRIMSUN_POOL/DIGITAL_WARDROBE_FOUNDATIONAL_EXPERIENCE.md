# DIGITAL_WARDROBE_HISTORY
# Domain Classification: FULLSTACK_WEB
# Source Material: Digital Wardrobe repository, four commits on 2026-11-24; methodology v11; current working tree
# Compiled By: adaptation-growth-pipeline (Experience Compiler)
# Total Indexed Experience Points: 8
# Last Expanded: 2026-11-25
# Origin: ARCHAEOLOGY

[LIMITED: four commits spanning one day; no long-term stability evidence. Current working tree includes pre-existing uncommitted dependency changes. Static observations are not production incidents.]

## 1. PROGRESS
<!-- APPEND NEW PROGRESS BELOW THIS LINE -->
- **PROGRESS-001:** Weather validation, explicit provenance and LIVE/CACHED/MANUAL recovery have dedicated unit and integration tests and were carried into the public adapter. Preserve these contracts; tests were inspected, not executed during this design review. [TIER-0] [EVIDENCE: ea21b05 / backend/tests/unit/test_weather_gateway.py; neon-backend/index.mjs] [SRC: Digital Wardrobe / docs/DEPLOYMENT.md / 2026-11-24]
- **PROGRESS-002:** One-time key consumption uses an atomic conditional update and a transaction; concurrency and replay tests exist. Carry forward the transaction pattern while replacing public-serial redemption. [TIER-0] [EVIDENCE: ea21b05 / backend/app/registration.py; backend/tests/integration/test_phase4_registration.py] [SRC: Digital Wardrobe / registration / 2026-11-24]

## 2. RULE
<!-- APPEND NEW RULE BELOW THIS LINE -->
- **RULE-001:** IF preserving the course demo THEN isolate measurement and reset traffic to dedicated test data BECAUSE the deployment document records that live tests reset data and refuse the public demo branch. [TIER-0] [EVIDENCE: 43b477e / neon-backend/test-live.mjs] [SRC: Digital Wardrobe / docs/DEPLOYMENT.md / 2026-11-24]
- **RULE-002:** IF deploying the existing public demo THEN preserve Python/JavaScript scoring parity BECAUSE Neon Functions required a JavaScript adapter while Python remained the local and measurement implementation. This is a legacy constraint, not a requirement to duplicate the new research model. [TIER-0] [EVIDENCE: 43b477e / neon-backend/rules.mjs; neon-backend/scoring-reference.json] [SRC: Digital Wardrobe / docs/DEPLOYMENT.md / 2026-11-24]

## 3. MISTAKE
<!-- APPEND NEW MISTAKE BELOW THIS LINE -->
- **MISTAKE-001:** Public QR contents currently grant wardrobe ownership, contradicting methodology 3.4.4, which explicitly reserves ownership for private keys. This is an observed requirements divergence, not an asserted exploit incident. Correction Applied: NONE; new TDD specifies discovery-only QR and transactional private-key redemption. [IMPACT-HIGH] [TIER-0] [NEVER_RESOLVED] [EVIDENCE: ea21b05 / backend/app/routers/registration.py; neon-backend/index.mjs] [SRC: Digital Wardrobe / methodology v11 P0424-P0425 / 2026-11-25]
- **MISTAKE-002:** A shared browser write key and fixed synthetic user cannot enforce separate customer/admin identities. This was an explicit demo simplification, now a scope-transition hazard rather than an undocumented historical failure. Correction Applied: NONE; authenticated principal and resource ownership checks are required before multi-user use. [IMPACT-HIGH] [TIER-0] [NEVER_RESOLVED] [INFERRED] [EVIDENCE: ea21b05 / backend/app/deps.py; Frontend/frontend/src/api.js; neon-backend/index.mjs] [SRC: Digital Wardrobe / scope transition review / 2026-11-25]

## 4. GROWN
<!-- APPEND NEW GROWN BELOW THIS LINE -->
- **GROWN-001:** Before the next ecosystem release, public QR scans must create zero ownership records, and concurrent private-key submissions by two authenticated users must create exactly one owned item. Proposed verification bar; not yet achieved. [TIER-0] [INFERRED] [SRC: Digital Wardrobe / TDD revamp / 2026-11-25]
- **GROWN-002:** Before the next ecosystem release, each private read/write must pass two-user isolation tests and admin writes must fail for customer sessions; old destructive tests must remain isolated. Proposed verification bar; not yet achieved. [TIER-0] [INFERRED] [SRC: Digital Wardrobe / TDD revamp / 2026-11-25]

## 5. BRIDGE
<!-- APPEND NEW BRIDGE BELOW THIS LINE -->
No Understanding pool supplied yet. No cross-pool authority or bridge is claimed.
