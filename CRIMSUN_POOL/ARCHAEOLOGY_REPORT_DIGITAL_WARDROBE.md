# Digital Wardrobe — Archaeology and research review

**Date:** 2026-11-25. **Scope:** read-only application inspection; new design/report artifacts only. Existing code and uncommitted user changes preserved.

## Reconnaissance and recovered intent

Observed stack: Vite/JS with TypeScript tooling and Three.js; FastAPI/SQLAlchemy Python backend; Hono/pg Neon Functions public adapter; Neon Postgres and SQLite local fallback. The old TDD deliberately scoped a single-user, functional-backend-first course demo. The frontend design described an editorial fashion direction; the actual app combines fitting, planning, wardrobe, registration and diagnostics through a shared HTML renderer. Deployment documentation records the public Node adapter and synthetic write key.

The next iteration is a scope expansion, not proof the original team failed to build an intended production service. Shared identity, destructive reset and synthetic catalogue are legitimate demo constraints that become migration hazards now. The public-QR ownership path is a concrete departure from the supplied research two-code contract.

## Historical mining

The skill's miner scanned four commits on 2026-11-24. It classified zero FIX/REVERT/REFACTOR/PERF events, found 94 files and zero stable candidates. [Full event stream](HISTORICAL_EVENT_STREAM.md). Do not infer absence of bugs from that classification. Source review identified runtime duplication, QR semantic changes and concentrated frontend rendering; no historical outage or long-term stability claim is supported.

Commits inspected by subject: initial snapshot `04c7449`; public Neon adapter `43b477e`; frontend integration `c9516ce`; QR/key and BMKG behaviour `ea21b05`. Churn includes deployment documentation (four changes), frontend/api/registration and weather surfaces. These guide review depth, not severity scores by themselves.

## Structural findings

1. `current_user()`/`seed.user_id` selects a synthetic principal and shared key guards writes/admin. New identity must be implemented, not inferred from newly added auth dependencies.
2. Public scan pages auto-submit ownership using serial; public QR metadata and private key do not have the research-prescribed privilege separation.
3. Python and JavaScript duplicate rule/scoring behaviour. Existing parity fixtures protect the demo, but are not a reason to train or maintain the next model twice.
4. Database product identity uses GTIN; source catalogue identities require a separate namespace and optional real identifiers.
5. Coloured SVG/geometry previews are useful fallbacks, but category/product imagery, template assets and typed accessory positions require explicit work.
6. Weather validation/cache/fallback, transaction claims and tests are reusable assets; no test execution was needed to write this design.

## Research recovery

The requested parent-folder DOCX and repository copy are byte-identical (SHA-256 recorded in the TDD). Standard-library ZIP/XML extraction captured paragraph text and a separate inspection captured all 17 math objects. Read methodology, scope, dataset table, experiments and ethics against code.

Key contracts: H&M purchase catalogue and age-based Gen Z evaluation; Polyvore non-disjoint compatibility; frozen FashionCLIP with trainable type-aware projection/masks; rule-filtered outfit score, preference and recency; public QR wishlist vs private activation ownership; category templates/accessory slots; offline evaluation, not user satisfaction.

Research review concerns: non-disjoint item leakage claim, draft bracketed thresholds, source-image rights, historical vs live catalogue pricing, explicit heavy-outerwear heat rule and simulation-assigned vs verified physical attributes. New TDD makes these gates and documents product extensions separately.

## Output and limits

[Foundational experience module](DIGITAL_WARDROBE_FOUNDATIONAL_EXPERIENCE.md): eight entries; current structural hazards tagged appropriately and proposed GROWN requirements not claimed achieved. Script-generated [experience index](EXPERIENCE_INDEX.md) verifies the module's parseability. [Unified activation manifest](UNIFIED_DECISION_MANIFEST_DIGITAL_WARDROBE_v1.md) and [new TDD](TDD_Digital_Wardrobe_Ecosystem_v1.md) carry decisions and release gates.

Understanding Pool path remains missing after clarification request. No existing external experience pool was guessed. New local experience is a bootstrap, not a substitute for the requested larger knowledge review. Primary Steam/dataset sources were browsed; four local references were visually inspected. No app mutation, package installation, data download, network deployment or external publishing was performed.
