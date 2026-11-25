# Ecosystem TDD status

Against `CRIMSUN_POOL/TDD_Digital_Wardrobe_Ecosystem_v1.md` (v1.1). Updated 2026-11-26. The evidence is linked readiness documents and automated tests; nothing here is claimed without one.

**Summary.** The backend, research tooling and release evidence are complete. What remains:
- the Phase 3 visual frontend and the 3D avatar (RQ4);
- deployment and cutover, which need the owner's go-ahead;
- owner actions: label the 200 RQ2 pairs, run the manual sign-in check, and download the Polyvore images for the corrected RQ2 run.

## Requirements F01–F13 (§1)

| ID | Requirement | Status | Evidence |
|---|---|---|---|
| F01 | Real-source catalogue | Done: 105,543 H&M articles with provenance, revisions and publish/retire | catalogue-readiness, object-management-readiness |
| F02 | Shared fashion intelligence | Done (rules shared with research; RQ1/RQ2 pipelines run on real data) | outfit-recommender-readiness, research-readiness |
| F03 | Item identity, key, lifecycle | Done | foundation-readiness; RQ3 report |
| F04 | Dedicated redemption; public QR cannot claim | Done: 0 false acceptances in 103,500 attempts | `research/reports/rq3/…` |
| F05 | Visual wardrobe, avatar, accessories | Backend done (accessory positions, looks, inspector data). **Visual avatar: frontend phase** | wardrobe-readiness; `test_accessory_positions_by_rule_and_capacity` |
| F06 | Seven-day timeline | Done (planner, week projection, plan sharing) | wardrobe-readiness, social-readiness |
| F07 | Mock purchase and wishlist | Done (sandbox offers, sizes, idempotent checkout, receipts, revocation) | commerce-readiness, sizes-readiness |
| F08 | Friends and profile | Done (requests, blocks, shares, feed, notifications, showcase, moderation, inspiration) | social-readiness |
| F09 | Admin supplies products | Done (import, review, publish, media, sizes, offers, units, roles, ops) | object-management-readiness |
| F10 | Steam-inspired feminine UI | **Frontend phase.** The temporary pages are functional only | the owner's reference mocks |
| F11 | Complete ecosystem, persists | Done (two-user thread, restart, isolation) | hardening-readiness; `test_ecosystem_acceptance` |
| F12 | Weather, occasion, rotation | Done (BMKG gateway, thesis rules a–d, Eqs. 7–9, occasions) | outfit-recommender-readiness |
| F13 | Thrifted or manual garments | Done (declared items, private photos, attributes, sizes) | wardrobe-readiness |

## Phases (§15)

| Phase | Status |
|---|---|
| 0. Evidence and feasibility | Done: dataset permissions and checksums, OIDC on Neon Auth (dev branch), frozen research configs, the pool consulted. The production host is not chosen yet. |
| 1. Identity and item foundation | Done |
| 2. Catalogue-to-wardrobe flow | Done |
| 3. Wardrobe experience (shell, Focus mode, avatar) | **Not started: the frontend stage.** The backend contracts are ready |
| 4. Shared intelligence | Done: pipelines, rules and serving. Results: RQ3 positive. RQ2 first run negative (2026-11-25): text-only compatibility (AUC 0.530) and assumed climate. A declared corrected re-run is in progress: the climate is now cited (BMKG Kemayoran 1991–2020) and FashionCLIP image embeddings start once the owner downloads the images. RQ1 finished 2026-11-26 (`research/reports/rq1/20261125T205603Z-f1630668`): not positive. The duplicate target was met (−56% vs first stage) and the MAP target was missed (reranked MAP@12 0.0080 vs popularity 0.0106, −25%) |
| 5. Social and profile | Done |
| 6. Hardening and cutover | Hardening done: limits, acceptance, performance bars, backup/restore rehearsal, ops view. **Cutover not done**: it needs a deployment decision |

## Release bars (§14)

| Area | Status |
|---|---|
| Catalogue p95 ≤ 500 ms at 20 concurrent | PASS, 267 ms (release-evidence-perf) |
| Recommendations p95 ≤ 1 s; outfits p95 ≤ 2 s at 80 items | PASS: 18 ms; 339 ms |
| UI (responsive, LCP, CLS), media payloads | Frontend stage |
| Avatar ≥ 30 FPS or a disclosed 2D fallback | Frontend stage (RQ4) |
| Isolation and transactions | PASS: acceptance isolation, races, revocation |
| Recovery | PASS locally: 1,040,816 rows restored identically (release-evidence-backup). Host-scheduled backups wait for deployment |
| Observability | Done: request ids, redacted errors, `/admin/ops` counts |

## Owner actions

1. Label the 200 H&M pairs: `research/tools/label_pairs.py serve`, then `finalize`. RQ2 then reports transfer AUC.
2. Run the manual Google, email and password sign-in check (accounts 9.2).
3. Download the Polyvore image files (`data/nondisjoint/*.parquet`, about 2.6 GB) for the FashionCLIP re-run.

Decided 2026-11-26: pushed to the public `crimSun-dev/wearhouse` as one fresh commit (thesis text, Steam references and v1 keys kept local); no Neon v2 deployment until the frontend exists.
