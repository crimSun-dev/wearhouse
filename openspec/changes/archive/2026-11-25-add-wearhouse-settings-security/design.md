## Decisions

### D1: The registry lives in code; values live in one JSONB row per user
The allowed values are product decisions tested with the code (`accounts/domain.py` `SETTINGS`). Each user has one `account_setting(user_id, values jsonb, version int, updated_at)` row. Storing only explicitly set keys means new keys get their defaults with no migration. The version gives optimistic concurrency across devices: the "Cloud Sync" of the mock is simply that the settings live on the server.

### D2: Other modules read settings through the accounts port
Social (notifications), accounts (search, requests) and wardrobe (suggestions) call `uow.accounts.settings(user_id)` and resolve it with `domain.effective_settings`. Recommendations stays pure: `OutfitSuggester.suggest` receives the weight profile.

### D3: Security events come from the existing audit log
`audit_event` already records account actions, and the runtime role can read it. Handle, privacy, settings and export now audit too. The overview reads the caller's own events (`actor_id = me`), plus role changes targeting them. No new table, and no IP addresses or user agents in our API: the broker's session list shows device details.

### D4: Passwords never touch the v2 API
The pages call the broker client methods that the installed `@neon/auth` 0.8.2 exposes:
- `signUp.email`, `signIn.email`;
- `changePassword`, `requestPasswordReset`, `resetPassword`;
- `listSessions`, `revokeSession`, `revokeOtherSessions`;
- `sendVerificationEmail`.

A Google-only account sets its first password through the reset email. Whether the managed server creates a credential for it, and whether it sends the emails, can only be checked against the real Auth branch; this is added to the manual check (accounts 9.2).

### D5: Client password policy
Length 10–128, not in an embedded list of very common passwords, and not containing the email local part or the handle. A strength rating counts length and character variety. It never calls an external breach service, because sending password material elsewhere is out of bounds.
