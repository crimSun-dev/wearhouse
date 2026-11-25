## 1. Broker contract and test issuer

- [x] 1.1 Add an EdDSA mode to `wearhouse.testing.LocalIssuer`. It must produce Neon-shaped tokens: Ed25519 key with `kid`; `iss` and `aud` both the Auth origin; `sub`, `iat`, `exp` 15 min; `name`, `email`, `image`, `role`, `banned`. It must also serve a JWKS. Verify with a unit test that decodes a token with PyJWT using `algorithms=["EdDSA"]` and the published JWK.
- [x] 1.2 Record the verified Neon Auth token contract in `docs/architecture/runtime-identity.md`: algorithm, issuer and audience equal to the origin, the JWKS path, no discovery, the 15-minute lifetime, which claims are authority and which are hints, and the shared audience risk. Verify that every claim listed has a cited doc source and a matching test fixture field.

## 2. Federated sign-in in the v2 API

- [x] 2.1 Extend `_parse_jwks` to accept OKP/Ed25519 keys. Set the allowlist to `("EdDSA", "RS256")`, with `WEARHOUSE_OIDC_ALGORITHMS` able to narrow it but never widen it. Verify that EdDSA tokens are accepted, and that HS256, `none`, RSA-signed tokens with an EdDSA-only allowlist, and malformed OKP keys are all rejected.
- [x] 2.2 Add a `JwksUrlSource` (explicit URL, shared cache, bounded refresh, fail-closed) and the `WEARHOUSE_OIDC_JWKS_URL` setting. Make `build_verifier` choose JWKS file, then URL, then discovery. Require https and forbid the JWKS file in deployment. Verify with config tests, plus a mock-transport rotation test that makes exactly one refresh for a new `kid` and fails closed on unknown kids.
- [x] 2.3 Extend `VerifiedIdentity` with `issued_at` and frozen `hints` (`name`, https-only `image`, `banned`). Require `iat`. Raise 403 `ACCOUNT_SUSPENDED` for `banned: true` before the account is resolved. Verify that broker `role: admin` grants nothing, that a banned first sign-in creates no account, and that public routes still work for banned users.
- [x] 2.4 Add `app_user.tokens_not_before` and `deleted_at` (part of migration 0004, task 3.1). Reject tokens with `iat <= tokens_not_before` using the generic 401. Verify that a token issued before revocation fails and one issued after succeeds, including across a restart.
- [x] 2.5 Report `needs_onboarding` in `GET /api/v2/me`, and seed the display name from the `name` hint at account creation. Verify that 8 concurrent first sign-ins with a Neon-shaped token create one account with `needs_onboarding: true` and no roles.

## 3. Accounts data model and module

- [x] 3.1 Write migration `0004_accounts` (design D5): profile, handle hold, privacy, friend request, friendship and block tables with their constraints and indexes; the new `app_user` columns; the widened `attempt_bucket.scope` CHECK; runtime grants. Update `SCHEMA_HEAD` and `RUNTIME_PRIVILEGES`. Verify that upgrading from 0003 twice works, that `compare_metadata` is empty, that startup on 0003 fails as stale, and that the runtime-role privilege check passes.
- [x] 3.2 Create the `accounts` module (domain, ports, application, adapters, api). Add the `OwnedItemReader` port to ownership and the `AccountDirectory` port to identity, and compose them in `bootstrap`. Verify with the extended boundary test: `accounts` appears in `MODULES`; its domain and application import no framework; it reaches ownership and identity only through their ports and domain.
- [x] 3.3 Implement the pure `can_view` policy and the handle, display-name and bio validators, with the reserved list. Verify with exhaustive unit tests over 3 sections × 3 settings × 5 relations, plus validator edge cases (case, length, leading digit, Unicode, control characters).

## 4. Profiles and privacy

- [x] 4.1 Implement `GET/PATCH /api/v2/me/profile`. It covers handle claim and change, with the 7-day change interval, the 30-day hold and race-safe uniqueness; display name; bio; and avatar (a preset, or the provider image taken from the verified token only). Verify that a concurrent claim yields one success and one 409; that changes are rejected as `HANDLE_CHANGE_TOO_SOON` and `HANDLE_UNAVAILABLE`; that an arbitrary avatar URL gets 422; and that no email appears in any response.
- [x] 4.2 Implement `GET/PUT /api/v2/me/privacy` with defaults of profile public, friends list friends, wardrobe private. Verify the defaults, that only the owner can read and change the settings, and that any other caller gets 401 or 404.
- [x] 4.3 Implement `GET /api/v2/profiles/{handle}`, `/wardrobe` and `/friends`, honouring visibility, blocks and deletion, with a uniform 404 and viewer-bound cursors. Verify with tests for every relation (anonymous, stranger, friend, blocked either way, deleted): the wardrobe projection has no serial, id or exact time; unfriending takes effect immediately; widening parameters change nothing; friends with private profiles are omitted.
- [x] 4.4 Implement `GET /api/v2/users/search`: onboarded caller, exact match or a prefix of at least 3 characters, at most 20 results, excluding blocked and deleted accounts. Verify the limits, the exclusions and a response containing only handle, display name and avatar.
- [x] 4.5 Enforce `HANDLE_REQUIRED` on social routes. Ownership routes keep working without a handle. Verify that a friend request before onboarding gets 409, and that redemption before onboarding still gets 201.

## 5. Friends and blocks

- [x] 5.1 Implement friend requests (send, cancel, accept, decline, incoming and outgoing lists) using the idempotent executor; opposite-direction requests auto-accept; requests are rejected across blocks (404) and to oneself (422). Verify the duplicate-send result, the auto-accept, a concurrent accept-versus-cancel race with a single outcome, and owner-only lists with a cursor replay rejected.
- [x] 5.2 Implement friendship removal and the friends list. Verify that removal is mutual and immediate, and that friends-only access is lost on the next request.
- [x] 5.3 Implement block and unblock in the design D6 lock order. Blocking ends the friendship and removes requests in both directions atomically, and nothing is restored on unblock. Verify that after a block each account is invisible to the other in profiles, search and requests, and that a fault injected mid-block leaves no partial state.
- [x] 5.4 Enforce the social limits: 50 requests per 24 h through the `friend_request` scope, 200 pending, 1000 friends, 1000 blocks. Verify the 51st request gets 429 with `Retry-After`, the friend cap gets 409 `FRIEND_LIMIT_REACHED`, and a multi-process boundary test lets exactly the permitted number through.

## 6. Account lifecycle

- [x] 6.1 Implement `POST /api/v2/me/sessions/revoke-all` (sets `tokens_not_before`). Verify that a still-valid earlier token gets 401 immediately and that a fresh token works.
- [x] 6.2 Implement `GET /api/v2/me/export`: profile, privacy, handle history, friends, requests, blocks and private owned items; `no-store`; 5 per hour. Verify that the document has every section, that it contains no other account's private data, key, digest or token, and that the 6th export gets 429.
- [x] 6.3 Implement `DELETE /api/v2/me` (design D8): recent authentication within 300 s and a typed confirmation, then one transaction that erases social and profile data, holds the handle, removes the mapping, tombstones the account and emits audit and outbox events with no personal data. Verify: a stale token gets 401 `REAUTHENTICATION_REQUIRED` and a wrong confirmation 422, each with no change; after deletion the former handle and the friends lists no longer show the account; the claimed unit still rejects redemption; the same subject signing in again gets a fresh empty account; a fault at each step leaves no partial deletion.

## 7. Contracts, configuration and documentation

- [x] 7.1 Regenerate `packages/contracts`: the new routes and their error codes (`ACCOUNT_SUSPENDED`, `HANDLE_REQUIRED`, `HANDLE_UNAVAILABLE`, `HANDLE_CHANGE_TOO_SOON`, `FRIEND_LIMIT_REACHED`, `REAUTHENTICATION_REQUIRED`), plus exported convenience types. Verify that `python tools/contracts.py check` and `npm run check --prefix packages/contracts` pass.
- [x] 7.2 Update `apps/api/.env.example`, `apps/api/README.md` and `docs/runbooks/v2-operations.md`, and add `docs/runbooks/accounts.md`. Cover the Neon Auth configuration mapping, revocation, export and deletion, the broker identity-removal procedure, and roll-forward after account data exists. Verify that every documented command or variable exists in code.
- [x] 7.3 Update the foundation roadmap (`openspec/changes/rearchitect-wearhouse-foundation/roadmap.md`): profile, privacy, friends and blocks move into `add-wearhouse-accounts`, and notifications and sharing stay in the later social change. Verify that every F08 acceptance gate still has an owning change.

## 8. Temporary account pages

- [x] 8.1 Scaffold `apps/web/account-pages` (Vite + TypeScript, port 5174). Pin the exact `@neon/auth` version after checking the installed package's vanilla adapter, `signIn.social`, `token()`, `signOut`, `revokeSessions`, `listAccounts` and `deleteUser` exports, and record which exist. Add `@wearhouse/contracts` as a `file:` dependency. Verify that `npm ci`, `typecheck` and `build` pass, and that the build contains no legacy imports.
- [x] 8.2 Implement the `AuthPort` seam and the Neon implementation, plus an API client that requests a token before every call and keeps it in memory only. Verify with unit tests that no token is written to local storage, session storage, the URL or console logs, and that sign-out clears state.
- [x] 8.3 Build the pages: sign-in, handle onboarding, profile edit, privacy, friends and search, blocks, public-profile preview, and account (linked methods, sign out everywhere, export download, deletion with a typed confirmation and either broker deletion or the disclosure). Every page needs loading, error and success states and the "temporary" label. Verify with Playwright e2e in `--mode e2e` (fake `AuthPort` backed by the test EdDSA issuer and the real local v2 API): two-user friend flow, block, privacy change, export, deletion, keyboard-only sign-out-everywhere, and readable error codes.
- [x] 8.4 Add a build guard that fails a production build if the e2e `AuthPort` alias is present, and install the Playwright Chromium browser for local runs. Verify that the guard trips on a deliberately mis-aliased build and passes the real one.

## 9. Broker provisioning and real Google verification

- [x] 9.1 With the user's explicit confirmation, create or choose the dedicated Wearhouse Neon project (AWS, ap-southeast-1, no IP Allow or Private Networking) and enable Neon Auth on its `dev` branch with Google (shared development credentials). Verify that `neon neon-auth status` and the Auth URL resolve, and record the issuer origin and JWKS URL (no secrets) in `runtime-identity.md`.
- [ ] 9.2 Configure local v2 and the pages against the dev Auth branch, then manually sign in with a real Google account. Check: first sign-in onboarding, reload persistence, profile and privacy, a second account's friend request, sign out everywhere (the old token gets 401), export, and deletion including the broker deletion outcome. Added by add-wearhouse-settings-security: email/password sign-up and sign-in, the reset email arriving and its link returning to `#/reset`, a Google-only account setting a password through that email, changing the password with other devices signed out, the device list and revoking one device, and the verification email. Record dated evidence in `docs/architecture/accounts-readiness.md` and state anything left unverified.
- [x] 9.3 Document, without creating anything, the production prerequisites: the user's own Google Cloud OAuth client with redirect `{NEON_AUTH_BASE_URL}/callback/google`, trusted domains for each deployed origin, custom SMTP if email sign-in is enabled, and separate Auth branches for staging and production. Verify that the accounts runbook lists each item with an owner and a status.

## 10. Integrated readiness

- [x] 10.1 Run the full v2 suite, legacy suite, contracts check, pages e2e and the clean-checkout CI emulation, then add an accounts e2e job to `.github/workflows/ci.yml`. Verify that every gate in `docs/architecture/accounts-readiness.md` has a command and an observed result, and that the foundation's pending source-backed gate is still reported separately.
