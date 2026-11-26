## Purpose

Defines the web account area: settings rendered from the server schema, privacy, the security overview, data export, account deletion and About. It is built on the account-settings, account-security and identity-access capabilities.

## ADDED Requirements

### Requirement: Schema-driven settings
The settings screen SHALL render every key returned by `GET /me/settings`, grouped by its `sections`:
- flags as toggles;
- choices as segmented controls or selects;
- ranges as sliders.

Saving SHALL send `{version, values}`. A toggle MAY update optimistically and SHALL roll back on failure. On `SETTINGS_CHANGED` the app SHALL reload the values and tell the user that settings changed on another device. The screen SHALL show when settings were last synced. It SHALL NOT offer a manual sync control.

#### Scenario: Unknown future key
- **WHEN** the server adds a new flag key to the schema
- **THEN** the settings screen shows it as a toggle in its section without a client change

### Requirement: Privacy
Users SHALL be able to set profile, wardrobe and friends-list visibility to public, friends or private. Each level SHALL be explained in one line.

#### Scenario: Privacy saved
- **WHEN** a user sets wardrobe visibility to private
- **THEN** `PUT /me/privacy` is sent and a friend viewing the profile no longer sees the wardrobe section

### Requirement: Security overview
The security screen SHALL show:
- the account creation date;
- the current session's sign-in age and whether it is recent enough for sensitive actions;
- the last 50 security events;
- a "sign out everywhere" action (`POST /me/sessions/revoke-all` together with the broker's revocation).

It SHALL host the broker password and session flows required by `account-security`. It SHALL state that passwords are managed by the identity broker.

#### Scenario: Sign out everywhere
- **WHEN** a user signs out everywhere
- **THEN** the current session ends and the user is returned to sign-in

### Requirement: Export and deletion
Users SHALL be able to download their data export as a JSON file (5 per hour). Account deletion SHALL require typing the handle and a recent sign-in. When the server returns `REAUTHENTICATION_REQUIRED`, the app SHALL take the user through sign-in and return them to the deletion step.

#### Scenario: Stale session delete
- **WHEN** a user signed in 20 minutes ago confirms deletion
- **THEN** the app asks them to sign in again, then returns them to confirm deletion

### Requirement: About
An About view, reachable from every screen, SHALL show the version, schema head, data sources with licences, terms and citations, notices, and the AI-assistance disclosure from `GET /about`.

#### Scenario: Sources listed
- **WHEN** a visitor opens About
- **THEN** each source from `/about` is listed with its licence and a link to its terms
