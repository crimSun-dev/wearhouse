# Runtime and identity requirements (Wearhouse v2)

This page records what the v2 API requires of its runtime and its identity provider. These contracts are fixed. The values that differ per deployment are listed separately in §4, and **nobody has provided or verified them yet**.

## 1. Python and container runtime

| Item | Requirement | Evidence |
|---|---|---|
| Python | 3.11 (`requires-python >=3.11`), the same line the legacy demo was tested on | local venv `apps/api/.venv`, Python 3.11.8 |
| Dependencies | exact pins in `apps/api/requirements.lock` (runtime) and `requirements-dev.lock`; direct pins in `pyproject.toml` | resolved from the package index on 2026-11-25 |
| ASGI app | `wearhouse.bootstrap.asgi:app` (uvicorn 0.54.0), port **8100** (legacy stays on 8000) | `tools/dev_api.ps1`, `tests/test_app_factory.py` |
| Database | PostgreSQL only (SQLite is refused). Locally tested against PostgreSQL 18.4; CI uses `postgres:17` | `tests/test_config_safeguards.py::test_sqlite_is_not_a_v2_database` |
| Migrations | separate release command `wearhouse migrate --environment <env> --runtime-role <role>`, run with the migration role | `tests/test_migrations.py` |
| Startup | read-only checks only: connectivity, rejection of legacy targets, environment marker, schema head `0003_ownership`, and the runtime role's privileges. It never migrates or seeds | `tests/test_migrations.py::test_startup_performs_no_writes` |
| Container | OCI image built from `apps/api/Dockerfile`, running the same ASGI app as a non-root user. Migrations run as a separate command against the same image | task 7.3 evidence in `foundation-readiness.md` |

## 2. Environment variables

The API reads only `WEARHOUSE_*` variables, and never a `.env` file. For every variable, see `apps/api/.env.example`.

`staging` and `production` count as **deployment** environments, which fail closed. Startup there requires:

- an https issuer, an audience and the delivery secret
- the `oidc` adapter
- https-only allowed origins
- no local JWKS file

The test identity adapter can be used only with `WEARHOUSE_ENV=test`, and only through `wearhouse.testing.create_test_app`. No request header or query parameter can select a mode.

## 3. OIDC access-token contract (resource server)

The provider must issue **JWT access tokens** that meet all of the following:

| Claim/header | Requirement |
|---|---|
| `alg` | `RS256` (the allowlist; `none` and `HS*` are rejected) |
| `kid` | required; must be published in the issuer's JWKS |
| `iss` | exactly `WEARHOUSE_OIDC_ISSUER`. Discovery `{iss}/.well-known/openid-configuration` must report the same issuer and a `jwks_uri` |
| `aud` | contains `WEARHOUSE_OIDC_AUDIENCE` (the API's own audience, not the SPA client id) |
| `sub` | stable, non-empty, at most 255 chars. Wearhouse maps `(iss, sub)` to exactly one local account |
| `exp` | required; validated with 60 s leeway |
| `nbf` | validated when present (60 s leeway) |

Behaviour:

- **Keys.** The JWKS is cached for 600 s. An unknown `kid` triggers at most one refresh per 60 s, and a `kid` still unknown after refreshing fails closed. If the provider is unreachable and no keys are cached, verification also fails closed.
- **What a token can carry.** Roles are **never** read from token claims, and the same goes for profile fields. Staff capabilities come only from server-side `role_grant` rows, which the restricted CLI creates (`wearhouse grant-role`); there is no HTTP endpoint for granting roles.
- **Logging.** Tokens are never logged.

**Verification with a local signed-token/JWKS fixture.** `wearhouse.testing.LocalIssuer` generates RS256 keys and publishes a JWKS, and the following tests use it:

- `apps/api/tests/test_identity.py` covers a valid token; expired, wrong-issuer, wrong-audience and wrongly-signed tokens; an unknown `kid`; an `nbf` in the future; `HS256` and `none`; a missing `sub`; clock-skew bounds; discovery with key rotation, a bounded refresh and fail-closed handling of unknown keys; an issuer mismatch; and an unreachable provider.
- At the HTTP level, every invalid variant returns 401 with no mutation.

These tests prove the adapter against the contract. They do **not** prove any particular provider.

## 4. External deployment inputs (still pending, not assumed)

| Input | Status | Needed before |
|---|---|---|
| OIDC provider and tenant; issuer URL; API audience | **not selected** | deployed identity release |
| Provider evidence: RS256 JWT access tokens with `aud` set to the API audience, a stable `sub`, discovery and JWKS (check against §3) | **not collected** | deployed identity release |
| Browser PKCE login, renewal and logout | out of scope here; a frontend acceptance test | fresh frontend |
| Python container host and region; managed PostgreSQL for v2 (separate from the legacy Neon `demo` branch) | **not provisioned** | deployed release |
| Production `WEARHOUSE_DELIVERY_SECRET` in the host's secret store; rotation owner | **not created** | deployed release |
| Allowed browser origins (https) | depends on the frontend host | deployed release |

None of these inputs changes the contracts above or the order of the tasks. They are configuration values.

## 5. Selected broker: Neon Auth (Managed Better Auth) with Google (change `add-wearhouse-accounts`)

This contract was read from the Neon docs on 2026-11-25:

- [D1] https://neon.com/docs/auth/guides/plugins/jwt.md
- [D2] https://neon.com/docs/compute/functions/authentication.md
- [D3] the Neon Auth agent skill reference, plugin/JWT row (checked 2026-10-30)

The Neon-shaped test fixture is `wearhouse.testing.LocalIssuer.neon()`, checked by `apps/api/tests/test_neon_issuer.py`.

| Item | Neon Auth contract | Source | Fixture field |
|---|---|---|---|
| Algorithm | EdDSA (Ed25519); JWK `kty: OKP`, `crv: Ed25519`; `kid` in the header | D1, D3 | `algorithm="EdDSA"`, `kid` |
| `iss` | the **origin** of the Auth URL (e.g. `https://ep-xx.aws.neon.tech` for `https://ep-xx.aws.neon.tech/neondb/auth`) | D1 | `iss = origin` |
| `aud` | the same origin as `iss` | D1 | `aud = origin` |
| `sub` | the Better Auth user id (equal to `id` in the documented sample) | D1, D2 | `sub == id` |
| Lifetime | 15 minutes (`exp - iat = 900`); `iat` present; `nbf` not stated | D1, D3 | `ttl 900`, `iat` |
| JWKS | `<NEON_AUTH_BASE_URL>/.well-known/jwks.json` (`NEON_AUTH_JWKS_URL` inside Functions) | D1, D2 | `jwks()` |
| Discovery | `/.well-known/openid-configuration` is **not documented**, so Wearhouse configures the JWKS URL explicitly | D1, D2 | n/a |
| Profile claims | `name`, `email`, `emailVerified`, `image`, `role` (e.g. `authenticated`), `banned`; custom claims are unsupported | D1, D3 | default `profile` claims |
| Refresh | the browser client calls `getSession()` / `token()` and the SDK refetches near expiry; no refresh token reaches the API | D1 | n/a |

**What Wearhouse takes from these claims:**

- **Authority.** Only `iss` and `sub` select the account. Staff roles come solely from server-side `role_grant` rows.
- **Hints.** `name` seeds the display name at account creation. An https `image` can become the avatar, but only when the user picks it.
- **Deny-only.** `banned: true` refuses protected routes with 403 `ACCOUNT_SUSPENDED`.
- **Never used.** `email` is never stored or returned. `role` and the organization claim `o` are ignored.

**Configuration mapping:**

- `WEARHOUSE_OIDC_ISSUER` and `WEARHOUSE_OIDC_AUDIENCE` are both the origin of `NEON_AUTH_BASE_URL`.
- `WEARHOUSE_OIDC_JWKS_URL` is `NEON_AUTH_BASE_URL + /.well-known/jwks.json`.
- `WEARHOUSE_OIDC_ALGORITHMS=EdDSA`.

**Risks and requirements:**

- **Shared audience.** `aud` is the Auth origin, not something specific to this API, so any service that trusts the same Auth branch accepts the same tokens. Use a dedicated Auth branch per environment, and let only Wearhouse consume it.
- **Production Google credentials.** Neon's shared Google credentials are for development only. Production needs the project's own Google Cloud OAuth client, with the redirect `{NEON_AUTH_BASE_URL}/callback/google`.
- **Project requirements.** Neon Auth requires an AWS project without IP Allow or Private Networking.

### 5.1 Browser client (account pages): `@neon/auth` 0.8.2, checked 2026-11-25

These findings come from the installed package (`dist/types.d.ts` route list and `dist/index.d.ts`), using `createAuthClient(url, {adapter: BetterAuthVanillaAdapter({fetchOptions: {credentials: 'include'}})})`.

| Method | Present | Used for |
|---|---|---|
| `getSession` | yes | restoring the session after a reload |
| `signIn.social({provider: 'google'})` | yes | Google sign-in |
| `getSession()` → `session.token` | yes | **the v2 access token.** The wrapper copies the `set-auth-jwt` response header there (`dist/adapter-core.js`), and it is read before **every** API call and kept in memory only |
| `token()` (`GET /token`) | yes | fallback only. In the first real Google session it returned nothing (finding from task 9.2) |
| `signOut` / `revokeSessions` | yes | sign out, and sign out everywhere (on top of the v2 `tokens_not_before`) |
| `listAccounts` | yes | read-only list of linked sign-in methods |
| `linkSocial` / `unlinkAccount` | **no** | not offered by the managed client, so linked methods are view-only in the pages |
| `deleteUser` | yes, in the route list | broker self-deletion. The managed server may still refuse it (Better Auth needs `deleteUser` enabled); that outcome is recorded in task 9.2, and the pages show the disclosure when it fails |

Note: npm `file:` dependencies need `install-links=true` (see `apps/web/account-pages/.npmrc`), because this drive refuses the symlinks npm creates for them.

### 5.2 Development Auth branch (task 9.1, provisioned 2026-11-25 with your confirmation)

| Item | Value (public, no secrets) |
|---|---|
| Neon project | `wearhouse` (`soft-darkness-81364884`), AWS `aws-ap-southeast-1`, PostgreSQL 18, no IP Allow or Private Networking. Separate from the legacy `digital-wardrobe-live-demo` project |
| Branches | `main` (default, unused so far), `dev` (`br-morning-cell-bi67lpmt`), which holds Neon Auth |
| Neon Auth | Better Auth (managed), database `wearhouse`, schema `neon_auth` |
| `NEON_AUTH_BASE_URL` | `https://ep-restless-union-biyn7dtz.neonauth.c-5.ap-southeast-1.aws.neon.tech/wearhouse/auth` |
| `WEARHOUSE_OIDC_ISSUER` / `_AUDIENCE` | `https://ep-restless-union-biyn7dtz.neonauth.c-5.ap-southeast-1.aws.neon.tech` |
| `WEARHOUSE_OIDC_JWKS_URL` | `…/wearhouse/auth/.well-known/jwks.json`. Fetched: one key, `kty: OKP`, `crv: Ed25519`, `alg: EdDSA`, with a `kid`, as §5 expects |
| Discovery | `https://ep-restless-union-biyn7dtz.neonauth.c-5.ap-southeast-1.aws.neon.tech/.well-known/openid-configuration` returns **404**, which confirms the explicit JWKS URL decision |
| Google | `type: shared` (Neon's development credentials; production needs your own client, see the accounts runbook §7) |
| Origins | `allow_localhost: true`; no other trusted origins |
| Other defaults left as Neon set them | email/password enabled (the pages offer only Google), shared email provider, organization plugin enabled (not used by Wearhouse) |
