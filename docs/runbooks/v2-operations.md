# Wearhouse v2 operations runbook

Every command below needs `WEARHOUSE_*` set for the target environment. `wearhouse` is the CLI that `apps/api` installs; you can also run it as `python -m wearhouse.bootstrap.cli`.

## Release (in this order, every time)

1. **Back up** the v2 database, following the host's managed-backup procedure.
2. **Migrate** with the migration role. Use the same image or commit you are about to deploy:
   ```
   wearhouse migrate --environment <env> --runtime-role wearhouse_runtime
   ```
   The migration refuses legacy v1 databases and databases registered for a different environment. It is forward-only.
3. **Deploy** the API with the runtime role. If the schema head, environment marker or privileges don't match, startup fails and nothing is written.
4. **Verify** with `wearhouse check` (or `GET /api/v2/health/ready`); it must report `ready`.

## Staff roles (no HTTP self-elevation)

```
wearhouse grant-role  --issuer <iss> --subject <sub> --role catalogue_editor|inventory_manager|admin
wearhouse revoke-role --issuer <iss> --subject <sub> --role ...
```

Every grant and revoke writes an `audit_event` row. Roles are never taken from token claims.

## Issuance delivery and secrets

- A freshly issued key can be retrieved for 24 h, and only by the actor who issued it: they retry with the same `Idempotency-Key` and the same body. Once the unit is claimed, revoked or expired, the delivery reports `unavailable` or `expired` and no new unit is minted. To recover a lost key, use `POST /api/v2/admin/units/{id}/reissue`.
- `wearhouse purge-deliveries` erases the ciphertext of expired deliveries. Schedule it, for example hourly.
- **Rotate the secret** as follows:
  1. Generate a new secret with `wearhouse generate-secret`.
  2. Set it as `WEARHOUSE_DELIVERY_SECRET`, and move the old one to `WEARHOUSE_DELIVERY_SECRET_PREVIOUS`.
  3. Deploy.
  4. Remove the previous secret after at least 24 h.

  Cursors and idempotency fingerprints signed with the previous secret stay valid during that window.

## Sizes

The H&M source has no sizes. After importing a catalogue, generate mock sizes, then (re)apply offers so each size gets stock:

    wearhouse assign-sizes --operator-issuer urn:wearhouse:operator --operator-subject catalogue-import
    # then POST /admin/commerce/offers/bulk with "overwrite": true (stock is per size for sized products)

The command is idempotent (only products without sizes) and batched. Staff manage systems and sizes at `#/staff/sizes`; retiring a size hides it from pickers but keeps old orders and wardrobe items readable.

## Synthetic demo catalogue and starter kit (staging)

The public staging demo uses invented records only (namespace `wearhouse-synthetic-demo`, article ids 900000+); H&M rows are never published there. `tools/make_demo_catalogue.py` writes `apps/api/fixtures/demo-catalogue/wearhouse-demo-catalogue.csv` (+ `.sha256`) deterministically. Every step below is idempotent:

    wearhouse import-catalogue --csv apps/api/fixtures/demo-catalogue/wearhouse-demo-catalogue.csv --publish \
      --namespace wearhouse-synthetic-demo --source-name "Wearhouse synthetic demo catalogue" \
      --source-url https://wearhouse.invalid/demo --acquired-on 2026-11-26 --basis synthetic-demo-fixture \
      --scope "public demo; synthetic records only" --accepted-on 2026-11-26 --accepted-by "Wearhouse owner" \
      --terms-url https://wearhouse.invalid/demo/terms --operator-issuer <iss> --operator-subject <sub>
    wearhouse generate-media --operator-issuer <iss> --operator-subject <sub>
    wearhouse assign-sizes   --operator-issuer <iss> --operator-subject <sub>
    python tools/finish_demo_catalogue.py --operator-issuer <iss> --operator-subject <sub>   # offers (never overwrites) + 12-piece 'starter-kit' collection; prints the ids
    wearhouse grant-starter-kit   # tops every onboarded account up with kit pieces it has not received yet

The kit is `WEARHOUSE_STARTER_KIT` when set (render.yaml), otherwise the `starter-kit` collection; at most 12 pieces. A piece an account already received from the kit is never granted again.

## Recommendation artifacts

Import a research artifact (directory with `manifest.json` and `neighbours.csv`, written by `research/src/wearhouse_research/export.py`):

    wearhouse import-recommendations --artifact <dir> --operator-issuer urn:wearhouse:operator --operator-subject catalogue-import

The CLI refuses a checksum mismatch, a `trained` manifest without a model hash, and an operator without `catalogue:ingest`. The new artifact replaces the active one in one transaction and is audited (`recommendations.artifact_activated`). Unknown article ids are skipped and counted. With no artifact the API serves the declared content baseline.

## Outbox

`wearhouse outbox-dispatch --loop 5` delivers events that have been committed.

- **Retries.** A failing consumer is retried with exponential backoff, and its error is recorded in `last_error`.
- **No duplicates.** A `(consumer, event_id)` record prevents duplicate delivery, and consumers must also be idempotent by event id.
- **Rolled-back events.** An event from a rolled-back transaction never exists, so it can never be dispatched.

## Incident checks

| Symptom | Check |
|---|---|
| `NOT READY: ... schema version` | run the release migration; never edit `alembic_version` by hand |
| `registered for environment 'X'` | `WEARHOUSE_ENV` or `WEARHOUSE_DATABASE_URL` points at the wrong database. Fix the config; don't edit the marker (it is immutable) |
| `legacy v1 demo database` | `WEARHOUSE_DATABASE_URL` points at the legacy demo. Use the dedicated v2 database |
| `lacks required privileges` / `can create schemas` | re-run the migration with `--runtime-role`, or fix the runtime role; never run the API as the migration owner |
| many `429 RATE_LIMITED` on ordinary routes | the edge limits (`WEARHOUSE_RATE_IP_PER_MIN`, `WEARHOUSE_RATE_GLOBAL_PER_MIN`) or the per-user write limit (`WEARHOUSE_RATE_WRITES_PER_MIN`). They are per process: N instances allow N times the value. Raise them only after checking the access log for one IP or one user dominating |
| many `429 RATE_LIMITED` on `/redemptions` | expected after 10 attempts per user per hour. The IP and global budgets are `WEARHOUSE_REDEMPTION_*_LIMIT`, and `WEARHOUSE_TRUSTED_PROXIES` controls whose `X-Forwarded-For` is trusted |
| `503 SERVICE_UNAVAILABLE` on redemption | the admission store is unreachable, so the API fails closed by design. Restore database connectivity |

## Accounts

The broker configuration, sign out everywhere, export and deletion, removing a broker identity, and the roll-forward rule are all in `docs/runbooks/accounts.md`.

**Rollback warning.** Once `0004_accounts` holds account data, roll forward only. The foundation image refuses the newer schema head.

## Foundation rollback (this change only)

Production stays on legacy v1 for the whole foundation. To roll back:

1. Stop routing traffic to v2: stop the v2 container or process.
2. **Keep the v2 database** for audit. Do not drop it, reset it or migrate it down.
3. Nothing else is needed for legacy: it keeps running from `legacy/` with its own database, and GitHub Pages already builds legacy v1.

This sequence was rehearsed by `tools/rehearse_isolation.py`; see `docs/architecture/foundation-readiness.md`.

The later production cutover (backup and restore verification, freezing v1 writes, the owner-mapping rehearsal, then switching) belongs to a separate change; see `roadmap.md`. **Never use the legacy demo reset as a rollback.**
