# Settings and security readiness (add-wearhouse-settings-security)

Date: 2026-11-25. Reference: the owner's settings mock `Assets/5b18d145-a682-4368-9cf9-4a4b017f7de0.png`.

## Settings (server-side, synced)

`GET`/`PATCH /me/settings` keeps one versioned row per account, holding only the keys you have set; every other key takes its registry default. The response carries the schema, so the frontend can draw the screen generically. A save from a device holding an older version gets `409 SETTINGS_CHANGED`, and the pages reload to show the newer values.

| Mock section | Setting | What it actually does |
|---|---|---|
| General | `language` (en, id) | Stored for the client. These temporary pages are English only; translation comes with the frontend. |
| Wardrobe | `wardrobe_view` (grid, list, outfit) | The wardrobe page uses grid or list. "Outfit" is stored for the frontend. |
| Wardrobe | `wardrobe_group_by_slot` | The wardrobe page groups items under slot headings, unless a sort is chosen. |
| Style & Recommendations | `style_suggestions` | Off: the API returns `enabled: false` with no suggestions. |
| Style & Recommendations | `weather_in_suggestions` | Off: suggestions rank without weather (source `DISABLED`), even if rain or heat is passed. |
| Style & Recommendations | `recommendation_style` | Eq. 7 weight profile (compatibility/preference/recency): balanced 0.5/0.3/0.2, classic 0.4/0.5/0.1, adventurous 0.4/0.2/0.4. Weather is a hard rule, not a weight (see `outfit-recommender-readiness.md`). |
| Sync & Backup | (none) | Everything already lives in the account, so "Sync now" just reloads. Last-saved time is shown. |
| Display | `theme` (dark, light, system), `reduce_motion` | Applied to the page at sign-in and on change (`data-theme`, `reduce-motion`). |
| Audio | `sound_effects`, `sound_volume` | Stored for the frontend; the temporary pages play no sounds. |
| Notifications | `notify_friend_requests`, `notify_request_accepted`, `notify_friend_shares` | Filter the derived notifications and the unread count. |
| Friends & Community | `friend_requests_from` (everyone, nobody) | Nobody: new requests get `409 REQUESTS_CLOSED`. Your own requests still work, and so does accepting theirs. |
| Friends & Community | `discoverable` | Off: hidden from prefix search; an exact `@handle` still finds you. |
| Downloads | (none) | The existing JSON export (5 per hour). |
| Beta Features | `beta_features` | Stored opt-in flag (no beta features yet). |
| About | (none) | `GET /about`: version, schema head, sources with licences and citations, notices, AI disclosure. |

Changes are audited as `account.settings_changed`, with the key names only, never the values. Settings are exported and erased with the account.

## Security

- `GET /me/security` returns:
  - when the account was created;
  - when you last signed out everywhere;
  - this session's sign-in time, and whether it is recent enough to delete the account (5 minutes);
  - the last 50 security events: sessions revoked, handle changed, privacy changed, settings changed, data exported, and roles granted or revoked by staff.

  Only your own events are shown; staff role changes appear as "by staff".
- Handle, privacy, settings and export now write audit events (they were not audited before).
- **Passwords never reach the Wearhouse API.** The pages talk to Neon Auth directly:
  - email and password sign-up and sign-in;
  - "Forgot your password?", which emails a link to `#/reset`; the token is removed from the address bar after use;
  - change password, optionally signing out other devices;
  - setting a first password for a Google-only account through the same reset email. The library code confirms a reset creates the password: better-auth `resetCredentialPassword` creates a credential account.
  - email verification status and resend;
  - a device list with "Sign out this device" and "Sign out other devices", alongside the API's "Sign out everywhere".
- **Client password policy** (`src/password.ts`): 10–128 characters; not one of the very common passwords (including trailing-digit variants); not your email name or handle; not one or two repeated characters. It shows a strength rating as you type. Nothing is sent to an external breach service. Neon Auth enforces its own minimum on the server.

## Evidence

| Check | Result |
|---|---|
| `tests/test_settings_security.py` | 8 passed: defaults, schema, versioned saves and 409, invalid input 422, audit stores keys only; requests closed and discoverability; notification toggles; suggestion switches and weights; weight profiles change the ranking margin (adventurous > balanced > classic, Eq. 7 since align-wearhouse-outfit-recommender); export and erasure; security events are your own (and staff role changes); About attribution. |
| Pages unit tests | 12 passed, including 5 password-policy tests and the extended Neon adapter test. |
| e2e `settings.spec.ts` | Sign-up refuses a common password, then succeeds. Theme, style and search settings save and survive a reload. Changing the password with the wrong current one is refused, then succeeds. Another device is signed out. Security activity is listed. The old password fails and the new one works. The theme follows the account to the next sign-in. The reset link sets a new password and the token leaves the URL. About lists Polyvore with its citation. |
| Full e2e | 13 passed. |

## Not verified here (needs the real Auth branch: accounts 9.2)

The e2e flows use the broker fake. Against the real dev Neon Auth branch, these still need checking by hand:
- the reset and verification emails actually arrive (Neon's shared email provider);
- the reset link returns to `localhost:5174/#/reset`;
- changing the password signs out other sessions;
- the session list shows real devices;
- a Google-only account can set a password through the reset email.

The checklist in the accounts change (task 9.2) now includes these.
