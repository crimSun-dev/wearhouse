## Why

Wearhouse v2 can already verify tokens and map each `(issuer, subject)` to one private account. It still has no way for real people to sign in, no public identity, and no social layer. The product direction calls for a Steam-like account: sign in with Google, a unique handle, a profile whose visibility you control, friends, and self-service account management. The fresh frontend and the social services depend on these account contracts, so they should exist and be tested first.

## What Changes

- **Sign-in through a broker.** Use Neon Auth (Managed Better Auth) as the identity broker, with Google as the first sign-in method. Shared Google credentials are for development only; production uses the project's own Google Cloud OAuth client.
- **v2 accepts Neon Auth access tokens.** Add EdDSA (Ed25519) to the verifier's asymmetric algorithm allowlist. Add an explicitly configured JWKS URL source, because Neon Auth documents no OIDC discovery. Accept the Neon Auth issuer and audience, which are both the origin of the Auth URL. Keep verification fail-closed, with the existing bounded refresh.
- **Broker claims never add authority.** Neon Auth's `role`, `email` and `name` claims never confer Wearhouse permissions. Staff roles stay server-granted. A `banned: true` claim, or a Wearhouse-side account revocation, can only *deny* access.
- **Profiles.** Each profile has a unique case-insensitive handle (required before social features), a display name, a short bio, and an avatar. The avatar is either the provider's picture URL or a built-in preset; uploads are out of scope. A public profile read returns only the fields its owner's privacy settings allow, and never an email.
- **Privacy settings.** Separate public / friends / private settings for the profile, the wardrobe (owned items) and the friends list, all enforced on the server. A blocked viewer gets the same 404 an absent profile gets. Other people's view of a wardrobe never includes public serials, item IDs or exact claim times.
- **Friends and blocks.** Friend requests can be sent, cancelled, accepted and declined; two requests in opposite directions auto-accept. Friends can be removed. Blocking removes any friendship and pending requests, and stops requests and visibility in both directions. Requests are rate-limited, and the lists are bounded with cursor pagination.
- **Account management.**
  - Linked sign-in methods are viewed and changed through the Neon Auth client.
  - "Sign out everywhere" revokes broker sessions and sets a Wearhouse token-not-before timestamp. The v2 API then rejects tokens issued earlier, immediately rather than when they expire.
  - Users can export their data as JSON.
  - Account deletion requires recent authentication plus a typed confirmation. It erases profile and social data and removes the subject mapping. It keeps a PII-free tombstone so that claimed units stay claimed and ownership history stays consistent.
- **Minimal account pages in `apps/web`.** Plain, deliberately temporary pages: sign in with Google, choose a handle, edit profile and privacy, manage friends and blocks, and account settings. They use the Neon Auth client and generated types from `packages/contracts`. They are not the Steam-like visual rebuild and do not reuse the legacy renderer.
- **Supporting work.** New forward-only migrations (0004+), new `/api/v2` routes, regenerated contracts, tests driven by a local EdDSA issuer that mimics Neon Auth's claim shape, and docs and runbooks. This pulls the profile and friends part of the roadmap's `add-wearhouse-social-profile-services` forward.
- **Provisioning needs your confirmation.** Enabling Neon Auth, adding trusted domains and registering the Google OAuth client are explicit tasks. Each needs your confirmation; nothing is created implicitly.

## Capabilities

### New Capabilities

- `federated-sign-in`: Neon Auth/Google broker tokens accepted by v2, covering EdDSA verification against an explicit JWKS, issuer/audience binding, claims that can only deny, ban handling, and Wearhouse-side revocation through token-not-before.
- `account-profiles`: unique handles, display name, bio and avatar, required onboarding, and privacy-filtered public profile and wardrobe projections.
- `privacy-settings`: per-section visibility (profile, wardrobe, friends list) enforced on every read, with blocks overriding visibility.
- `friends-and-blocks`: the friend request lifecycle, friendship removal, blocking, request limits and paginated lists.
- `account-lifecycle`: linked-method visibility, sign out everywhere, data export, and recent-auth account deletion with a PII-free tombstone that preserves ownership history.
- `account-pages`: minimal temporary browser pages for the full account flow against the real broker and the v2 API.

### Modified Capabilities

None in `openspec/specs/`, which still has no archived specs. This change builds on the foundation change's `identity-access` behaviour (verified principals, server-owned roles, owner-scoped reads, no test principals in deployment) without relaxing it. The foundation design said "initially RS256"; adding EdDSA stays within its "allowlisted asymmetric algorithm" contract.

## Impact

- **Code:** `apps/api/src/wearhouse/identity` (verifier, key source, claim policy, revocation); a new `accounts` module (profiles, privacy, friends, blocks, lifecycle) with routers, application services, ports and SQL adapters; migrations `0004+`; `bootstrap` config (`WEARHOUSE_OIDC_JWKS_URL`, the Neon Auth issuer/audience origin) and its startup privilege map; `testing` (an EdDSA local issuer).
- **API and contracts:** new `/api/v2/me/*`, `/api/v2/profiles/*` and `/api/v2/users/search` routes; a regenerated `packages/contracts`. `/api/v2/me` gains profile/onboarding state, which is additive.
- **Frontend:** `apps/web` gets a small Vite + TypeScript app with a pinned Neon Auth client package. It sits on its own dev port and has no legacy imports.
- **External systems:** a Neon project/branch with Neon Auth enabled (AWS, without IP Allow or Private Networking), trusted domains, Google OAuth credentials, and the Neon Auth URL and JWKS URL as configuration. None of these exists yet, and each needs your confirmation.
- **Unchanged:** legacy v1, the GitHub Pages workflow, and the foundation's pending source-backed gate (task 7.5), which is independent. These pages are temporary and do not lift the foundation's stop gate on the real frontend rebuild.
- **Docs:** `docs/architecture/runtime-identity.md` (provider contract filled in), a new accounts runbook, the roadmap update, and `.env.example`.
