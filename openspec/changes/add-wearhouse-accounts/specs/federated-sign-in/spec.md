## Purpose

Lets people sign in to Wearhouse through a managed identity broker (Neon Auth, starting with Google), so that the v2 API accepts only broker-issued tokens that verify. Claims from the broker can never grant Wearhouse authority.

## ADDED Requirements

### Requirement: Broker access tokens are verified against a configured key set
The v2 API SHALL accept a broker access token only when all of these hold:
- the token is signed by an allowlisted asymmetric algorithm, which SHALL include EdDSA (Ed25519);
- its key identifier matches a key in the configured JWKS URL;
- its issuer and audience equal the configured broker origin;
- it is within its validity period, allowing for bounded clock skew.

The service SHALL NOT require an OpenID discovery document when a JWKS URL is configured. A key identifier still unknown after one bounded refresh of the key set SHALL be rejected. Missing or invalid tokens SHALL return 401 and perform no operation.

#### Scenario: Valid broker token
- **GIVEN** a token signed with a published Ed25519 key, issued and audienced to the configured broker origin, and not expired
- **WHEN** it is presented as a bearer token to `GET /api/v2/me`
- **THEN** the request succeeds as the account mapped to that issuer and subject

#### Scenario: Token from another issuer, audience or key
- **WHEN** a token has a different issuer, a different audience, a symmetric or `none` algorithm, an unpublished key identifier, or an expired validity period
- **THEN** the service returns 401 and creates or changes no account state

#### Scenario: Broker rotates its signing key
- **GIVEN** the broker publishes a new key and signs new tokens with it
- **WHEN** a token with the new key identifier first arrives
- **THEN** the service refreshes the key set at most once within the bounded interval and accepts the token

### Requirement: Broker claims can only deny
Broker-supplied claims other than issuer and subject SHALL NOT grant Wearhouse roles, capabilities or ownership. Those claims include role, email, name, image and organization. A token carrying `banned: true` SHALL be refused with 403 `ACCOUNT_SUSPENDED` on every protected route.

#### Scenario: Broker role claim
- **WHEN** a verified token carries a broker role such as `admin`
- **THEN** the account receives only customer capabilities unless a server-side Wearhouse grant exists

#### Scenario: Banned broker user
- **WHEN** a verified token carries `banned: true`
- **THEN** every protected route returns 403 `ACCOUNT_SUSPENDED` and performs no mutation, while public routes remain available

### Requirement: Wearhouse can revoke previously issued tokens
The service SHALL keep a per-account token-not-before instant. It SHALL reject any token for that account whose issued-at time is not later than that instant, even if the token has not yet expired.

#### Scenario: Token issued before revocation
- **GIVEN** an account revoked its sessions at time T
- **WHEN** a token issued at or before T is presented after T
- **THEN** the service returns 401 and performs no operation, while a token issued after T is accepted

### Requirement: First sign-in creates an account needing onboarding
The first verified request from a previously unseen issuer and subject SHALL create exactly one Wearhouse account, as before. The account SHALL report that it still needs onboarding until a handle is chosen. Concurrent first requests SHALL still create exactly one account.

#### Scenario: New Google user
- **WHEN** a person signs in through the broker for the first time and calls `GET /api/v2/me`
- **THEN** the response identifies one new account with no staff roles and `needs_onboarding: true`

### Requirement: Deployment broker configuration fails closed
In deployment environments, startup SHALL fail when any of these holds:
- the broker issuer, audience or JWKS URL is missing;
- that issuer, audience or JWKS URL is not https;
- a local development key set is configured.

#### Scenario: Missing JWKS URL in production
- **WHEN** production configuration selects the broker but omits the JWKS URL and has no discovery issuer
- **THEN** the API refuses to start with an actionable configuration error
