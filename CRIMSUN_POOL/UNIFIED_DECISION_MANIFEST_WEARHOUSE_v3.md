# Unified Senior and Growth Decision Manifest — Wearhouse v3 (services complete → pre-frontend finish)

**Generated:** 2026-11-25. **Revision:** v3. It supersedes the v2 §5 status only; v2's sequencing decisions stay in force. The trigger is the user's direction: "fully finish and polish all functionalities before building the frontend."

## 0. Evidence and selection

- **Experience pool.** `CRIMSUN_POOL/` was re-indexed (`build_experience_index.py`). The index shows 2 modules and 12 apparent entries. Only **DIGITAL_WARDROBE_HISTORY** (8 real entries) is selected. The `UNIFIED_SENIOR_AND_GROWTH_DECISION_MANIFEST` entries are citations, not observations, and stay excluded per v2 RULE-DRAFT-B.
- **Understanding pool.** Still **not supplied**. This is a POOL GAP carried from v1 and v2. No world-knowledge citations are claimed. Everything below is DIRECT project evidence (code, tests, readiness docs) or cites the experience module.
- **Project evidence used:**
  - `openspec list`: 5 changes complete, accounts at 32/33;
  - `docs/architecture/*-readiness.md`;
  - the full v2 suite: 539 passed, plus the source-backed thread passing locally;
  - e2e: 10/10;
  - live checks on 2026-11-25: BMKG fetch returned 17 valid slots; catalogue at about 44k of 105k rows, with search 7–28 ms and facets 53 ms.

## 1. Experience status update

| Entry | v2 status | v3 status | Evidence |
|---|---|---|---|
| MISTAKE-001 [HIGH] public QR grants ownership | NEVER_RESOLVED | **Corrected in v2; still live in deployed v1** | v2 discovery is read-only (`/items/{serial}`), and ownership comes only from `/redemptions`; foundation readiness gates pass. The public site still serves legacy v1, so the hazard remains in production until cutover. |
| MISTAKE-002 [HIGH] shared demo principal | NEVER_RESOLVED | **Corrected in v2; still live in deployed v1** | Neon Auth EdDSA principals, server-side roles, and two-user isolation tests in every service. Same cutover caveat as above. |
| GROWN-001 | proposed bar | **Achieved in v2** | Concurrency and discovery tests (foundation readiness), plus the commerce cancel-versus-claim race having exactly one winner. |
| GROWN-002 | proposed bar | **Achieved in v2** | Isolation tests across accounts, commerce, wardrobe and social; admin writes return 403 for customers in every staff route. |
| PROGRESS-001 | carried | **Confirmed again** | The v2 weather gateway reuses the contract, and a live BMKG fetch was validated on 2026-11-25. |
| PROGRESS-002 | carried | **Confirmed again** | Credential-then-unit lock order is reused by commerce cancellation. |
| RULE-001 | carried | **Honoured** | Every test uses disposable databases. The H&M import ran against the dev database, not customer data. |

## 2. Decisions for the pre-frontend finish

| Decision | Tier | Outcome |
|---|---|---|
| "All functionality" means the services in the roadmap's services umbrella plus the F-requirements they own, verified end to end on real data | DIRECT (roadmap F01–F13 table) | Add an **F11 ecosystem acceptance thread** on the real catalogue: admin publishes → customer discovers → wishlist → mock-buy → redeem → equip/look → plan → wear → share → friend sees. It runs in CI on synthetic data and locally on H&M. |
| Gaps against the services gates still open | DIRECT (roadmap services step 1) | **Media and embedding status**, which product imagery depends on. Blocked on permitted images (the H&M images are not supplied). |
| F09 says "issue unit without code edits" | DIRECT | The API exists, but there is no staff page for unit issuance or reissue. Staff pages are needed before the frontend so admin flows are exercised. |
| A sandbox shop over 105k products | INFERRED (commerce design and catalogue scale) | Offers are set one at a time today, so the shop is effectively empty. Add **bulk sandbox offers**: staff-defined rules per category, labelled sandbox, never presented as real H&M prices. |
| Research intelligence (RQ1–RQ4) before the frontend? | PROJECT DIRECTIVE needed | The roadmap allows it in parallel, and the frontend can consume the declared `heuristic_baseline`. It needs transactions/customers/images data that has not been supplied. **The user decides.** |
| Deploy v2 and import H&M to Neon | PROJECT DIRECTIVE (2026-11-25 answer) plus the v2 gap "Python host/OIDC spike" | It needs a hosting decision and a spike first. This is a cloud resource change and needs explicit confirmation. Cutover also removes the live MISTAKE-001/002 exposure. |
| Consolidate the baseline | DIRECT | 106 uncommitted paths, and 5 complete OpenSpec changes are not archived into `openspec/specs/`. Commit (when asked) and archive before the frontend, so it builds against archived specs. |

## 3. Vetoes and gates

- **BLOCK:** repeating MISTAKE-001/002 in any new surface. Staff unit pages must not reveal keys beyond the issuing actor's delivery.
- **BLOCK:** committing or deploying H&M data in ways that redistribute the source file. `H&M DATABASE/` and `fixtures/source-products/local/` are git-ignored. A public Store showing H&M rows is the user's call under the Kaggle rules (answered 2026-11-25).
- **BLOCK:** inventing prices, stock, images or model results.
- **WARN:** at 105k rows, substring search and facets use sequential scans. Add a `pg_trgm` GIN index and cached facets before the frontend relies on instant search.
- **WARN:** outbox events are emitted with no consumers beyond the log. That is acceptable while notifications are derived, and must not be mistaken for delivery.

## 4. Fragility-first finish sequence

1. **Baseline:** commit in logical slices (on request) and archive the 5 complete OpenSpec changes, the largest single risk being 106 uncommitted paths. Finish the H&M import and verify counts and checksum.
2. **Real-scale catalogue polish:** trigram index, facet caching, measured latency at 105k; bulk sandbox offers; staff unit issuance/reissue and commerce order pages.
3. **F11 acceptance thread:** across all services, in CI on synthetic data and locally on H&M, plus an API hardening pass: rate limits on the new mutation and proxy endpoints, plus a review of body and size limits.
4. **User-gated decisions:** product imagery (images permission and supply, then media jobs); research intelligence timing; v2 hosting spike, then a Neon deployment and import, then cutover planning; accounts 9.2 manual Google checks.

## 5. Pool gaps

- The Understanding pool path is unsupplied.
- No world-knowledge authority covers search indexing or rate-limit design. The decisions above are project-evidence-based.
- No experience exists for Python hosting on Neon-adjacent infrastructure.

## 6. Audit and growth

- **Citations checked:** all 8 cited IDs were re-read in full from DIGITAL_WARDROBE_HISTORY; there are no superseding entries.
- **Repeated-mistake scan:** 0 repetitions in v2. The two HIGH mistakes remain live only in the deployed legacy v1.
- **Breadcrumbs:** this session's log is in [GROWTH_BREADCRUMB_LOG_2026-11-25_SERVICES.md](GROWTH_BREADCRUMB_LOG_2026-11-25_SERVICES.md).
- **Tally:** 6 new drafts and 4 confirmations; 0 logged mistakes repeated.
