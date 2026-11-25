## 1. Settings

- [x] 1.1 Build the settings registry, migration `0013`, the repository, `GET`/`PATCH /me/settings` with versions and audit, export and erasure, and the behaviour wiring (notifications, requests closed, search, suggestions on/off, weather off, weight profiles). Verify each behaviour, the 409 on a stale version, 422 on unknown keys or values, and defaults.

## 2. Security and About

- [x] 2.1 Add `GET /me/security` (overview and own events), audit events for handle, privacy, settings and export, and `GET /about`. Verify own-events-only, the event kinds, the recent-auth flag and About attribution.

## 3. Pages

- [x] 3.1 Extend the auth port (Neon and fake) with email/password, reset, change, sessions and verification; add the password policy with unit tests; add the sign-in page with email/password, sign-up and forgot-password, the reset page, the Settings page from the schema (sections as in the mock), Security (password, sessions, sign-out everywhere, events), theme application, and About. Add e2e for settings and security. Run the full suite, contracts, the build and `docs/architecture/settings-security-readiness.md`, and update the accounts 9.2 manual checklist.
