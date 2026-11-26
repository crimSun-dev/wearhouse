## MODIFIED Requirements

### Requirement: Passwords stay with the identity broker
The API SHALL NOT accept, store or log passwords. The Wearhouse web app (`apps/web/client`) SHALL provide the following, as the temporary account pages SHALL until they are retired:
- email and password sign-up and sign-in, plus password reset by email;
- a password change that can sign out other sessions;
- a way for a Google-only account to set a password through the reset email;
- email verification status, with a way to resend it;
- a list of broker sessions, with revoke-one and revoke-others.

All of these go directly to Neon Auth. A client-side policy SHALL refuse passwords that are:
- shorter than 10 or longer than 128 characters;
- among the common passwords;
- containing the email local part or the handle.

The policy SHALL rate passwords that pass it.

#### Scenario: Weak password refused before it is sent
- **WHEN** a user types `password123` as a new password
- **THEN** the page shows why and does not call the broker

#### Scenario: Web app provides broker flows
- **WHEN** a signed-in user opens security settings in the Wearhouse web app
- **THEN** they can change their password, resend verification and revoke a broker session without using the temporary account pages
