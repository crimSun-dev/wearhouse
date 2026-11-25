# Accounts runbook (Neon Auth + Google)

Change `add-wearhouse-accounts`. The token contract and its sources are in `docs/architecture/runtime-identity.md` §5.

## 1. Configuration mapping

Each environment needs its own Neon Auth branch. Take its `NEON_AUTH_BASE_URL` (for example `https://ep-xxxx.aws.neon.tech/neondb/auth`) and set:

| Variable | Value |
|---|---|
| `WEARHOUSE_OIDC_ISSUER` | origin only: `https://ep-xxxx.aws.neon.tech` |
| `WEARHOUSE_OIDC_AUDIENCE` | the same origin |
| `WEARHOUSE_OIDC_JWKS_URL` | `NEON_AUTH_BASE_URL` + `/.well-known/jwks.json` |
| `WEARHOUSE_OIDC_ALGORITHMS` | `EdDSA` |
| `WEARHOUSE_ALLOWED_ORIGINS` | the account pages' origin(s), https in staging/production |

To confirm, run `wearhouse check`: it must report `ready`. The first EdDSA token then resolves through `GET /api/v2/me`.

**Never** point a staging or production API at a development Auth branch. The audience is the Auth origin, so a separate branch for each environment is the isolation boundary. Never enable Auth on the legacy demo Neon project.

## 2. Sign out everywhere

The user runs `POST /api/v2/me/sessions/revoke-all`; the account pages also revoke broker sessions. This sets `app_user.tokens_not_before`. From then on the API rejects every token for that account issued at or before that second, with a 401.

Other services that trust the same Auth branch stay exposed until the token expires, up to 15 minutes.

**Operator (incident).** Revoke a user's tokens without their session:

```sql
UPDATE app_user SET tokens_not_before = now() WHERE id = '<user uuid>';
```

Run it as the migration role, then record it in your incident log.

## 3. Export

`GET /api/v2/me/export` returns the full JSON document:

- account and profile
- privacy settings
- handle holds
- friends, pending requests and blocks
- private owned items

It is limited to 5 per hour, and contains no keys, digests, tokens or email.

## 4. Deletion

The request is `DELETE /api/v2/me` with body `{"confirm": "<handle or DELETE>"}`, and it needs a token issued within the last 5 minutes.

**What one transaction does:**

1. Removes profile, privacy, requests, friendships and blocks (both directions), and role grants.
2. Holds the handle for 30 days.
3. Removes the `user_subject` mapping.
4. Sets `app_user.deleted_at`, clears `display_name` and revokes tokens.
5. Writes an audit event and an outbox `account.deleted` event, with no personal data in either.

**What stays:** `owned_item` rows remain attached to the tombstone, so claimed units stay claimed and ownership history stays consistent. A later sign-in with the same Google account creates a new, empty account.

**Broker identity (Neon Auth user, including the email).** If the managed client exposes self-deletion, the account pages delete the broker user too; task 8.1 records whether it does. If it doesn't, the pages tell the user that the sign-in identity remains, and the operator removes it on request:

1. Find the broker user id. Users live in the branch's `neon_auth` schema; check the table name on your branch first:
   ```sql
   SELECT id FROM neon_auth."user" WHERE email = '<requester email>';
   ```
2. Delete the user. This is checked against Neon CLI 9.6.0, whose `neon neon-auth user` offers only `create`, `delete` and `set-role`:
   ```bash
   neon neon-auth user delete <user-id> --project-id <project> --branch <branch>
   ```

Record the request and its completion date.

## 5. Moderation (deny-only)

A Neon Auth admin can ban a user. Their tokens then carry `banned: true`, and Wearhouse refuses every protected route with 403 `ACCOUNT_SUSPENDED`; public pages stay readable.

Broker `role` claims never grant Wearhouse staff capabilities. Use `wearhouse grant-role`.

## 6. Rollout and rollback

1. Back up the database.
2. Run `wearhouse migrate --environment <env>`, which applies `0004_accounts`.
3. Deploy the API.
4. Run `wearhouse check`.

**Rollback.** If no account data exists yet, restore the pre-migration backup and the foundation image. Once accounts exist, **roll forward only**: the foundation image refuses schema `0004_accounts`, and dropping account tables would delete users' data.

## 7. Production prerequisites

None of these have been created yet.

| Item | Owner | Status |
|---|---|---|
| Dedicated Wearhouse Neon project (AWS, no IP Allow or Private Networking), one Auth branch per environment | project owner | dev: see task 9.1 evidence; staging/prod: not created |
| Google Cloud OAuth client (own credentials; shared Neon credentials are dev-only), redirect `{NEON_AUTH_BASE_URL}/callback/google` | project owner | not created |
| `neon neon-auth oauth-provider update --provider-id google --oauth-client-id … --oauth-client-secret-file …` per branch | operator | pending the client |
| Trusted domains per deployed origin: `neon neon-auth domain add https://<origin>` | operator | pending hosting |
| Custom SMTP for password-reset and verification emails (email/password is enabled; dev uses Neon's shared provider) | operator | dev: shared provider, unverified; staging/prod: needed |
| Production `WEARHOUSE_DELIVERY_SECRET` in the host's secret store | operator | not created |

## Passwords and sessions (add-wearhouse-settings-security)

- Email/password is enabled on each Auth branch (Neon's default). Passwords live only in Neon Auth: the v2 API never receives, stores or logs one, and the pages send them straight to the broker.
- Reset and verification emails come from the branch's email provider. Development uses Neon's shared provider; staging and production need custom SMTP (see the table above). Reset links return to `<pages origin>/#/reset`, so each pages origin must be a trusted domain on its branch.
- A Google-only account sets a first password through the reset email; the broker creates the credential then.
- "Sign out this device" and "Sign out other devices" revoke broker sessions. "Sign out everywhere" additionally revokes every v2 API token issued so far (`tokens_not_before`).
- The client password policy (10–128 characters, not common, not containing the email name or handle) runs before anything is sent. The broker's own server-side minimum still applies.
