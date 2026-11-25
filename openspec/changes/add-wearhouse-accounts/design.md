## Context

See `proposal.md` (Why) and the six capability specs for the required behaviour.

**What already exists in the foundation code.** These pieces are already in place under `apps/api/src/wearhouse`:

- **Token verification.** `identity/adapters/oidc.py` verifies JWTs with an allowlist of `RS256` only. It loads keys through OIDC discovery (`DiscoveryJwks`) or from a static JWKS file, and parses only `kty: RSA` keys. The claims it requires are `exp`, `iss`, `aud` and `sub`.
- **Account resolution.** `IdentityService.authenticate` maps `(iss, sub)` to exactly one `app_user` (a race-safe insert using a savepoint) and loads the server-owned `role_grant` rows. `VerifiedIdentity` carries only issuer and subject.
- **Platform services.** `platform` supplies the idempotent executor, the `AttemptLedger` (whose `attempt_bucket.scope` CHECK constraint allows only `actor`, `ip` and `global`), signed cursors, audit, the outbox, uniform errors and no-store headers for private prefixes.
- **Boundaries.** `tests/test_boundaries.py` fixes the module list. Cross-module imports may target only `domain`, `ports` or `application`.

**Neon Auth facts** (from the docs, read 2026-11-25):

- Tokens are EdDSA (Ed25519) and carry a `kid`. `iss` and `aud` both equal the origin of the Auth URL, and `sub` is the Better Auth user id.
- Tokens expire after 15 minutes, and the payload includes `iat`. The payload also carries `name`, `email`, `image`, `role` and `banned`, and custom claims are not supported.
- The JWKS is at `<auth url>/.well-known/jwks.json`. No discovery document is documented.
- Google is supported through `signIn.social`. The shared credentials are for development only.

## Goals / Non-Goals

**Goals:**

- Accept Neon Auth tokens with no change to the foundation's verified-principal guarantees.
- Add a new bounded-context module, `accounts`, for profiles, privacy and the social graph. It reaches other modules only through their ports.
- Run every account test locally without Neon or Google. A local EdDSA issuer reproduces Neon's claim shape.

**Non-Goals:**

- Hosting our own OAuth or session server.
- Storing email addresses.
- Avatar uploads and media storage.
- Notifications, activity feeds and look/plan sharing. These belong to the later social services.
- Staff moderation endpoints.
- Styled UI. The pages are temporary.
- Changing legacy v1.
- Enabling Auth on the legacy Neon project.

## Decisions

### D1: Neon Auth as broker; Wearhouse stays a resource server

The browser signs in with Google through `@neon/auth`, using the managed Better Auth wrapper with the vanilla adapter. It then sends `Authorization: Bearer <JWT>` to v2. v2 never reads the `neon_auth` schema and never receives Google tokens.

The Neon Auth branch is configuration only:

- `WEARHOUSE_OIDC_ISSUER` and `WEARHOUSE_OIDC_AUDIENCE` both equal the origin of `NEON_AUTH_BASE_URL`;
- `WEARHOUSE_OIDC_JWKS_URL` equals `NEON_AUTH_BASE_URL + /.well-known/jwks.json`.

Each environment uses its own Auth branch, so a dev token can never be accepted by staging or production. Auth is enabled on a **dedicated Wearhouse Neon project**, not the legacy demo project. The v2 database may live on the same branch, but its runtime role is granted nothing in `neon_auth`.

*Alternatives considered:*
- A FastAPI-hosted OAuth/session server: this means more security surface for us to own (CSRF, refresh, logout).
- A different hosted IdP: the user chose Neon Auth.
- Reading `neon_auth.user` directly: this couples v2 to Better Auth internals and needs cross-schema grants.

### D2: Verifier: EdDSA keys and an explicit JWKS URL

`_parse_jwks` will also accept `kty: OKP` / `crv: Ed25519` keys via `PyJWK` (PyJWT's crypto extra is already pinned). `ALLOWED_ALGORITHMS` becomes `("EdDSA", "RS256")`, and `WEARHOUSE_OIDC_ALGORITHMS` may narrow it but never add to it. Neon issues only EdDSA, so the Neon configuration sets `EdDSA`.

A `JwksUrlSource` reuses `DiscoveryJwks`'s cache, rate-limited refresh and fail-closed logic, but takes the JWKS URL directly. `build_verifier` chooses the source in this order:

1. the JWKS file, in development only;
2. the JWKS URL;
3. discovery.

Broker tokens additionally require `iat`, which revocation and the recent-authentication check depend on. Deployment validation requires the JWKS URL and the issuer to be https.

*Alternative considered:* fetching the JWKS on every request. That costs latency, and an outage would turn into 401s for every user.

### D3: Claims as hints, never authority

`VerifiedIdentity` gains `issued_at` and an optional, frozen `hints` object (`name`, https `image`, `banned`). Only issuer and subject select the account, and roles still come only from `role_grant`. `banned: true` raises 403 `ACCOUNT_SUSPENDED` after verification and before resolution, so a banned user's first sign-in does not create an account.

The hints are used in exactly two places:
- `name` seeds the display name when the account is created;
- `image` becomes the provider avatar, only when the user explicitly selects it.

The avatar URL comes from the verified token, so a client can never submit an arbitrary URL.

### D4: New `accounts` module, reached only through ports

`accounts/{domain,ports,application,adapters,api}.py` covers profiles, handles, privacy, friendships, requests, blocks, export and deletion. It reaches other modules as follows:

- **Ownership.** A new `OwnedItemReader` port in `ownership.ports` (implemented in `ownership/adapters/sql.py`) returns a *presentation-only* projection for the wardrobe view and the full private view for export. Accounts never touch ownership tables.
- **Identity.** A new `AccountDirectory` port in `identity.ports` provides tombstoning, the token-not-before value and subject-mapping removal.

`bootstrap` composes the new repositories into the shared unit of work, so deletion is a single transaction across modules. The boundary test gains `accounts` in `MODULES`, plus a test that `accounts` imports nothing beyond the ports, domain and application of `identity` and `ownership`.

### D5: Data model (forward-only migration `0004_accounts`)

**Identity-owned additions.**
- `app_user` gains `tokens_not_before timestamptz NULL` and `deleted_at timestamptz NULL`.

**Accounts tables.**

| Table | Contents |
|---|---|
| `account_profile` | `user_id` (PK/FK); `handle` (lowercase, unique index); `display_name`; `bio`; `avatar_kind` (`preset` or `provider`); `avatar_preset`; `avatar_url`; `handle_changed_at`; timestamps |
| `handle_hold` | `handle` (PK); `held_for` (nullable: the user it was released by); `available_at` |
| `privacy_setting` | `user_id` (PK); `profile`, `wardrobe` and `friends_list`, each CHECKed to `public`, `friends` or `private` |
| `friend_request` | `id`; `from_user`; `to_user`; `status` (`pending`, `accepted`, `declined` or `cancelled`); timestamps. A partial unique index on `(from_user, to_user)` where pending; a CHECK that `from_user <> to_user` |
| `friendship` | `(user_low, user_high)` PK with a CHECK that `user_low < user_high`, so each pair has exactly one row |
| `user_block` | `(blocker, blocked)` PK, CHECKed distinct |

**Platform change.** `attempt_bucket.scope` CHECK is widened to add `friend_request` and `export`.

**Grants.** The migration grants the runtime role exactly these privileges (`bootstrap/schema.py` is updated so startup verifies them):
- `SELECT`/`INSERT`/`UPDATE`/`DELETE` on the social tables;
- `UPDATE` on `app_user (tokens_not_before, deleted_at, display_name)`;
- `DELETE` on `user_subject` and `role_grant`.

*Alternative considered:* a separate `profiles` service database. That rules out an atomic deletion and needs a cross-service saga.

### D6: Consistency under concurrency

- **Handle claims** are serialised by the unique index, and a violation maps to 409.
- **Holds.** The service checks `handle_hold` and claims the handle in the same transaction.
- **Request accepts and cancels** lock the request row (`FOR UPDATE`), so exactly one transition wins.
- **Friendship creation, the 1000-friend cap and the 200-pending cap** lock both users' `account_profile` rows in UUID order, then count and insert.
- **Blocks** run in the same lock order. Ending the friendship, deleting requests and inserting the block happen in one transaction.
- **Mutating social routes** use the platform `IdempotentExecutor`, scoped by actor, route and body. Friend-request sends reserve an attempt in scope `friend_request` (50 per rolling 24 h) through `AttemptLedger`.
- **Export** reserves in scope `export` (5 per hour).

### D7: Visibility as a pure policy

`accounts.domain.can_view(section, setting, relation)` takes the relation as `self`, `friend`, `stranger`, `anonymous` or `blocked`, and is pure and exhaustively tested. Repositories load one relationship snapshot per request: either-direction block, friendship, and the owner's settings. Every non-permitted read raises the same `not_found()` used for unknown and deleted handles.

Wardrobe projections are built from `OwnedItemReader.presentations(owner, after, limit)`, which returns no serial, id or timestamp. Ordering uses the existing keyset, with a cursor scope (`profile.wardrobe:<owner>`) bound to the viewer.

### D8: Revocation, recent authentication and deletion

**Sign out everywhere.** `POST /api/v2/me/sessions/revoke-all` sets `tokens_not_before = now()`. `authenticate` then rejects any token with `iat <= tokens_not_before`. Its 401 is indistinguishable from other invalid tokens.

**Recent authentication.** `DELETE /api/v2/me` requires `now - iat <= 300 s`, plus a body `{"confirm": <handle or "DELETE">}`.

**Deletion runs in one unit of work:**
1. lock `app_user`;
2. delete profile, privacy, requests, friendships, blocks (both directions) and role grants;
3. hold the handle for 30 days;
4. delete `user_subject`;
5. set `deleted_at`, clear `display_name` and set `tokens_not_before`;
6. write an audit event and an outbox event `account.deleted` (ids only, no personal data).

`owned_item` rows keep their FK to the tombstone, so units stay claimed (the foundation's redeem path already rejects claimed units). The next sign-in with that subject creates a new `app_user`, because the mapping is gone.

### D9: Temporary account pages in `apps/web`

- **Stack and setup.** Vanilla TypeScript with Vite on port 5174 and hash routing. Dependencies are `@neon/auth`, pinned to an exact version verified at apply time, and `@wearhouse/contracts` as a `file:` dependency.
- **Auth behind a seam.** An `AuthPort` interface is implemented by `neonAuth.ts` (Neon client, `signIn.social({provider: 'google'})`, `token()`, `signOut()`, `revokeSessions`, `listAccounts`, `deleteUser` where available). The API client asks `AuthPort.token()` before every call and keeps the token in memory only.
- **Automated end-to-end tests.** Playwright builds with `--mode e2e`, which aliases `AuthPort` to a fake that obtains tokens from the test EdDSA issuer. A build check fails if the e2e alias appears in a production build.
- **Real Google flow.** The genuine Google sign-in is verified manually on the dev Auth branch and recorded as evidence. Google's consent popup cannot be automated honestly.

*Alternatives considered:*
- React + Better Auth UI: heavier for pages that are temporary.
- Server-rendered pages in FastAPI: the broker client is browser-side, and it would blur API and UI.

### D10: External provisioning is explicit and confirmed

No Neon or Google resource is created implicitly. The tasks are:

1. **Neon project.** With confirmation, create or choose the dedicated Wearhouse Neon project on AWS (ap-southeast-1, matching legacy), without IP Allow or Private Networking. Enable Auth on its `dev` branch with shared Google development credentials. Localhost is pre-approved.
2. **Production Google client.** The user creates a Google Cloud OAuth client with the redirect `{NEON_AUTH_BASE_URL}/callback/google` and adds it through `neon neon-auth oauth-provider`.
3. **Trusted domains.** Register each deployed origin.

## Risks / Trade-offs

- **[The audience is the Auth origin, not API-specific]** Any service trusting that origin accepts the same tokens. → Mitigation: a dedicated Auth branch per environment; Wearhouse is the only consumer; documented in `runtime-identity.md`.
- **[Signed-out tokens stay valid for up to 15 minutes elsewhere]** → Mitigation: `tokens_not_before` makes v2 reject them immediately; the 15-minute lifetime bounds every other consumer.
- **[Managed SDK may not expose `deleteUser`, `revokeSessions` or `listAccounts`]** → Mitigation: an early verification task on the dev branch, with spec-mandated fallbacks (a disclosure plus the operator runbook through the Neon API's auth-user deletion; Wearhouse revocation works regardless).
- **[Handle squatting and enumeration]** → Mitigation: a reserved list, the 30-day hold, a 7-day change interval, authenticated search with a 3-character minimum and 20-result cap, and no email anywhere.
- **[Provider image URLs are third-party hosted (Google)]** Viewers' browsers fetch them. → Mitigation: provider avatars are opt-in; presets are the default; uploads come later with object storage.
- **[The tombstone keeps ownership rows]** → Mitigation: the tombstone carries no personal data; units stay claimed so ownership history and redemption integrity hold; export comes before deletion; the retention basis is documented.
- **[Neon Auth is a managed dependency with beta-labelled adjacent features]** → Mitigation: Wearhouse depends only on the documented JWT/JWKS contract and the core social sign-in; the version is pinned; contract tests use the documented claim shape.
- **[The temporary pages could be mistaken for the product UI]** → Mitigation: visible labelling, kept in `apps/web/account-pages`, and the frontend rebuild change replaces them.

## Migration Plan

1. Add `0004_accounts`. It is additive: new tables, nullable columns and a widened CHECK. It is applied with the existing release command, and startup's schema head becomes `0004_accounts`.
2. Deploy the API with the broker configuration in development first. The existing local issuer and test flows keep working.
3. Provision Neon Auth on dev (confirmed task), then run the manual Google verification. Staging and production follow the same steps with their own Auth branch and their own Google client.

**Rollback.** Revert the API image to the foundation build. That build refuses the newer schema head, so rolling back also needs a forward fix, or a restore from the pre-migration backup **before** any account data exists. After account data exists, roll forward only (documented in the accounts runbook). The pages are static, and removing them does not affect the API.

## Open Questions

- Does the managed client's `token()` always mint a fresh JWT? If it returns a cached one, the pages re-run `signIn.social` when the API answers `REAUTHENTICATION_REQUIRED`. The behaviour is already specified either way.
- What is the exact `@neon/auth` version and its vanilla-adapter import path? This is checked against the installed package at apply time; the legacy `@neondatabase/auth@0.6.0-beta` is not reused.
