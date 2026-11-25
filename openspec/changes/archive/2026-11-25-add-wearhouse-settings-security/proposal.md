## Why

The frontend's settings screen (owner's reference mock, `Assets/5b18d145-…png`) groups preferences into sections:
- General
- Wardrobe
- Style & Recommendations
- Sync
- Display
- Audio
- Notifications
- Friends & Community
- Downloads
- Beta
- About

Today the API has only profile and privacy. Nothing else is stored, so nothing follows the user across devices.

Account security is thin as well:
- sign-in is Google only, although the dev Neon Auth branch already has email and password enabled;
- the pages cannot set or change a password or recover one;
- sessions cannot be listed or revoked one by one;
- the user cannot see what security-relevant changes were made to their account.

## What Changes

- **Account settings (server-side, synced).** A typed settings registry in accounts with keys, sections, choices, ranges and defaults. `GET /me/settings` returns the values, the version and the schema, so a frontend can render the screen generically. `PATCH /me/settings` takes `{version, values}`: it validates every key, refuses a stale version with `409 SETTINGS_CHANGED` (another device saved first), and audits the changed keys.

  The settings drive real behaviour:
  - notification toggles filter derived notifications;
  - `friend_requests_from: nobody` closes incoming friend requests;
  - `discoverable: false` hides the account from prefix search (exact `@handle` still works);
  - `style_suggestions`, `weather_in_suggestions` and `recommendation_style` (balanced, classic, adventurous) change outfit suggestions;
  - display, language, wardrobe view and audio are stored for the client to apply.

  Settings are exported and erased with the account.
- **Security overview.** `GET /me/security` returns:
  - when the account was created;
  - when sessions were last revoked everywhere;
  - the current session's sign-in age, and whether it is recent enough for sensitive actions;
  - the last 50 security events for the account: sessions revoked, handle or privacy or settings changed, data exported, staff roles granted or revoked by an admin.

  Handle, privacy, settings and export now write these audit events.
- **Passwords and sessions (client to Neon Auth; the API never sees a password).** The pages gain:
  - email and password sign-up and sign-in, and "forgot password" (reset email, then reset page);
  - change password, with an option to sign out other sessions;
  - "set a password" for Google-only accounts through the reset email;
  - email verification status and resend;
  - a list of active sessions with revoke-one and revoke-others, next to the existing API "sign out everywhere".

  A client-side password policy checks length 10–128, rejects the most common passwords and anything containing your email name or handle, and shows strength. Neon Auth enforces its own server-side minimum.
- **About.** `GET /about`: API version, schema head, data sources with licences and citations (H&M, Polyvore, BMKG), and the AI-assistance disclosure.

## Capabilities

### New Capabilities
- `account-settings`: the registry, synced values, and behaviour wiring.
- `account-security`: the security overview and events, password and session management in the pages, and About.

### Modified Capabilities
None (additions; defaults preserve today's behaviour).

## Impact

- Migration `0013_account_settings`.
- Accounts, social, wardrobe and recommendations read settings through the accounts port.
- New routes, and contracts regenerated.
- In the pages: the auth port gains email/password and session methods (Neon adapter and the e2e fake), plus Settings, Security and reset pages.
- No change to Neon resources. Email/password is already enabled on the dev Auth branch. Reset and verification emails use Neon's shared email provider, which needs checking manually against the real branch.
