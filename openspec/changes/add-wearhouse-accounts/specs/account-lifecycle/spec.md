## Purpose

Gives account holders self-service control over their sessions and data: signing out everywhere, exporting everything Wearhouse holds about them, and deleting their account. Deletion must not corrupt ownership history.

## ADDED Requirements

### Requirement: Sign out everywhere
An account SHALL be able to revoke all of its sessions. Wearhouse SHALL record a token-not-before instant, so that every token issued until then is rejected immediately (see `federated-sign-in`). The account pages SHALL also revoke the account's broker sessions.

#### Scenario: Stolen token after sign out everywhere
- **GIVEN** a token was issued to account A, and A then signs out everywhere
- **WHEN** that token is used within its remaining validity
- **THEN** the v2 API returns 401

### Requirement: Linked sign-in methods do not change account identity
Linking or unlinking broker sign-in methods SHALL NOT create, merge or change a Wearhouse account. Wearhouse is keyed only on the broker issuer and subject. Linked methods SHALL be viewed and managed through the broker client, not stored by Wearhouse.

#### Scenario: Adding email sign-in to a Google account
- **WHEN** a user links another sign-in method to the same broker user and signs in with it
- **THEN** the v2 API resolves the same Wearhouse account as before

### Requirement: Data export
`GET /api/v2/me/export` SHALL return one JSON document of everything Wearhouse holds about the caller:
- profile, privacy settings and handle history held for the caller;
- friends, pending requests (both directions) and blocks;
- owned items in their private representation;
- account timestamps.

It SHALL NOT include other accounts' private data, activation keys, credential digests or tokens. It SHALL be `no-store`, and limited to 5 exports per hour per account.

#### Scenario: Export
- **WHEN** an account requests an export
- **THEN** the response is a JSON document with those sections, and a sixth export within an hour returns 429

### Requirement: Account deletion with ownership-preserving tombstone
`DELETE /api/v2/me` SHALL require:
- a token issued within the last 5 minutes (recent authentication), otherwise 401 `REAUTHENTICATION_REQUIRED`;
- a confirmation equal to the account's handle (or `DELETE` when it has none), otherwise 422.

Deletion SHALL, atomically:
- erase profile fields, privacy settings, friendships, requests in both directions, blocks in both directions, and staff role grants;
- release the handle (subject to the 30-day hold);
- remove the issuer/subject mapping;
- keep only a personal-data-free tombstone.

Owned items SHALL stay attached to the tombstone, so their units remain claimed and cannot be redeemed again. Ownership and audit history SHALL remain consistent. A later sign-in with the same broker subject SHALL create a new, empty account.

#### Scenario: Delete then sign in again
- **GIVEN** account A owns one item and deletes itself with recent authentication and the correct confirmation
- **WHEN** the same broker user signs in again
- **THEN** a new account with no items, friends or handle is created, and the previously claimed unit still rejects redemption with the generic invalid response

#### Scenario: Deleted account disappears from others
- **WHEN** A's former friends read their friends lists, or anyone looks up A's former handle
- **THEN** A does not appear, and the handle lookup returns the unknown-handle 404

#### Scenario: Stale token
- **WHEN** a deletion request carries a token older than 5 minutes
- **THEN** the service returns 401 `REAUTHENTICATION_REQUIRED` and deletes nothing

### Requirement: Broker identity deletion is completed or disclosed
When an account is deleted, the account pages SHALL also delete the broker user if the broker allows self-deletion. If it does not, the pages SHALL tell the user plainly that their sign-in identity, including the email held by the broker, remains with the broker, and SHALL explain how to request its removal.

#### Scenario: Broker without self-deletion
- **GIVEN** the broker does not allow the user to delete their own identity
- **WHEN** the user completes Wearhouse account deletion
- **THEN** the pages state that the sign-in identity remains and show the removal procedure, and they do not claim that all data is gone
