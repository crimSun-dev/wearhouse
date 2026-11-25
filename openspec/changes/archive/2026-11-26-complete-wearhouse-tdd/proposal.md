## Why

The owner asked to finish what is left of the ecosystem TDD (`CRIMSUN_POOL/TDD_Digital_Wardrobe_Ecosystem_v1.md`) before the frontend. The backend, research tooling and release evidence still have gaps:
- §11 slot registry: only six broad slots;
- §10.2 sandbox cancellation after a claim: currently refused;
- §7 moderator role;
- §11 saving a friend's look as inspiration;
- §12.2 catalogue ranking: "hide owned products", plus completion and duplicate reranking;
- §14 observability, performance budgets and backup/restore;
- §16 the RQ2 hand-labelled H&M transfer pairs.

## What Changes

- **Accessory slots (§11).** The registry gains bag, headwear, eyewear, earrings, necklace, tie, scarf, belt, wrist (2) and ring (2). `accessory` remains as an explicitly uncategorized slot (3), never assigned at random.
  - Catalogue items in the H&M "Accessories" group resolve to a position by product type (ruleset `accessory-subtypes@1`, slot source `rule`). Unknown types (hair accessories, gloves, umbrellas, etc.) stay `accessory`.
  - Owners can override, as before. The database slot constraints widen.
  - Outfit rules treat every accessory position as an accessory.
- **Sandbox revocation after a claim (§10.2).** Cancelling a completed sandbox order works even after a garment was claimed:
  - unclaimed units retire and their keys are revoked, as before;
  - claimed items move to `revoked_sandbox` in one audited transaction (an ownership event, and an outbox event); they leave the wardrobe inventory, looks validation and recommendations; the private item view shows the revoked state; the unit can never be claimed again;
  - stock is restored.

  This changes only the sandbox entitlement; it does not model real returns.
- **Moderation (§7).** A `moderator` role with `social:moderate`:
  - anyone signed in may report a share they can see (at most one report per user per share);
  - moderators see the open reports, and can hide or restore a share with a reason;
  - a hidden share is invisible to everyone except its owner, who sees it marked "hidden by moderation";
  - everything is audited;
  - moderators get no access to activation keys, orders or private wardrobes.
- **Inspiration (§11).** Save a visible shared look as a private inspiration: a snapshot of its safe projection (look name, slots, item names and categories, store links). It never grants items. List and delete. Saving re-checks visibility at that moment.
- **Personal catalogue shelf (§12.2).**
  - Browse gains `hide_owned=true` (signed in).
  - `GET /me/recommendations/products` reranks its candidates with Eq. 3 in labelled heuristic form: `score = candidate + λc·completion − λd·duplicate`.
    - **Completion:** the mean colour compatibility with the best 3 owned items of other slots; 0 with an empty wardrobe, and cold start is declared.
    - **Duplicate:** 1 when you already own an item of the same category and colour.
  - The model info declares `content+popularity, completion/duplicate rerank (heuristic)` with λc = 0.5 and λd = 0.5, which are proposed settings, not tuned.
- **Operations (§14).** `GET /admin/ops` (admin) returns:
  - claim failures and rate-limited attempts in the last 24 h;
  - the import job backlog and outbox backlog;
  - the active recommendation artifact and model mode;
  - the schema head.

  It shows counts only, never identifiers.
- **Release evidence (§14, phase 6).**
  - `tools/perf_bars.py` measures the §14 budgets: catalogue first page p95 with 20 concurrent clients on the 105k catalogue, personal recommendations p95, and outfit suggestions p95 at 80 items.
  - `tools/backup_restore.ps1` dumps the dev database, restores it into a new database, runs migrations and readiness checks, and compares row counts.

  The results are recorded with hardware, dataset size and warm/cold state.
- **RQ2 transfer labels (§16).** `research/tools/label_pairs.py` samples 200 cross-type H&M article pairs (seeded and stratified) and serves a local labelling page. The labels are written to `research/data/hm_transfer_labels.csv` and pinned in a manifest. The RQ2 runner reports transfer accuracy when the labels exist, and states that they are missing otherwise. Labels are never generated.

## Not in this change (owner or frontend)

- Phase 3 visual shell, Focus mode and 3D avatar with templates/textures (RQ4).
- Deployment and v1→v2 cutover (needs the owner's confirmation).
- The manual sign-in check (accounts 9.2).
- Object storage for media (a deployment choice; the media port stays).
- The owner labelling the 200 pairs.

## Impact

Migration `0015`:
- widened slot constraints;
- `owned_item.revoked_at` and `revoked_reason`;
- `share_report`, plus moderation columns on `look_share`;
- `inspiration`.

New routes and roles; contracts regenerated; pages updated (slots, cancel, report, moderation, inspiration, hide owned); new tools and docs.
