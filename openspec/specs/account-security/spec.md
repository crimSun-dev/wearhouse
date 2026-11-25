# account-security Specification

## Purpose
Lets people see and control how their account is secured, without the API ever handling a password.

## Requirements

### Requirement: Security overview and events
`GET /me/security` SHALL return:
- the account creation time;
- the last "sign out everywhere" time;
- the current session's sign-in time and age;
- whether that session is recent enough for sensitive actions (5 minutes);
- up to 50 recent security events, newest first: sessions revoked, handle changed, privacy changed, settings changed, data exported, role granted or revoked.

Events SHALL only ever come from the caller's own account, and their details SHALL never include secrets or other people's identifiers beyond the action.

#### Scenario: Own events only
- **WHEN** A changes privacy and B reads `/me/security`
- **THEN** B sees none of A's events

### Requirement: Passwords stay with the identity broker
The API SHALL NOT accept, store or log passwords. The pages SHALL:
- offer email and password sign-up and sign-in, plus password reset by email;
- offer a password change that can sign out other sessions;
- let a Google-only account set a password through the reset email;
- show email verification status and let the user resend it;
- list broker sessions with revoke-one and revoke-others.

All of these go directly to Neon Auth. A client-side policy SHALL refuse passwords that are:
- shorter than 10 or longer than 128 characters;
- among the common passwords;
- containing the email local part or the handle.

The policy SHALL rate passwords that pass it.

#### Scenario: Weak password refused before it is sent
- **WHEN** a user types `password123` as a new password
- **THEN** the page shows why and does not call the broker

### Requirement: About
`GET /about` SHALL be public. It SHALL return:
- the API version and schema head;
- the data sources with licence, terms and citation (H&M articles, Polyvore Outfits, BMKG);
- the AI-assistance disclosure.

#### Scenario: Attribution visible
- **WHEN** anyone reads `/about`
- **THEN** the Polyvore citation (Vasileva et al., ECCV 2018) and the CC BY 4.0 licence are listed
