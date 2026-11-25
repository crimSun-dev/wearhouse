## Purpose

Gives every Wearhouse account a public identity: a unique handle, a display name, a bio and an avatar. A profile can be looked up only through projections that respect its owner's privacy choices.

## ADDED Requirements

### Requirement: Unique case-insensitive handles
A handle SHALL meet all of these rules:
- 3 to 20 characters;
- only `a-z`, `0-9` and `_`, starting with a letter;
- unique regardless of letter case;
- not on the reserved list (for example `admin`, `wearhouse`, `support`, `me`, `api`).

Handles SHALL be stored and returned in lowercase. A handle change SHALL be allowed at most once every 7 days. A released handle SHALL NOT be claimable by another account for 30 days.

#### Scenario: Choosing a free handle
- **WHEN** an account without a handle sets `Dravenstyle`
- **THEN** the handle `dravenstyle` is stored, `needs_onboarding` becomes false, and the profile is reachable at that handle

#### Scenario: Taken, reserved or invalid handle
- **WHEN** an account requests a handle that another account holds in any letter case, that is reserved, that was released by another account less than 30 days ago, or that breaks the character rules
- **THEN** the request fails with 409 `HANDLE_UNAVAILABLE` (taken, reserved or held) or 422 (invalid format), and no handle changes

#### Scenario: Concurrent claims
- **WHEN** two accounts request the same free handle at the same time
- **THEN** exactly one succeeds and the other receives 409 `HANDLE_UNAVAILABLE`

#### Scenario: Changing too often
- **WHEN** an account changes its handle a second time within 7 days
- **THEN** the request fails with 409 `HANDLE_CHANGE_TOO_SOON`, and a `Retry-After` header indicates when a change is allowed

### Requirement: Editable display name, bio and avatar
An account SHALL be able to set:
- a display name: 1–32 characters, trimmed, with no control characters;
- a bio: at most 160 characters;
- an avatar: either one built-in preset, or the https picture URL supplied by the broker for that account.

The display name SHALL default to the broker-supplied name at first sign-in. No email address SHALL be stored in or returned by Wearhouse profiles.

#### Scenario: Using the Google picture
- **WHEN** an account selects its provider avatar
- **THEN** the avatar is the https image URL from that account's verified token at that time, and arbitrary URLs submitted by the client are rejected with 422

#### Scenario: Profile never exposes email
- **WHEN** any caller reads any profile, the caller's own profile included
- **THEN** no email address appears in the response

### Requirement: Social features require onboarding
Friend requests, blocks, profile search visibility and public profile reads SHALL require the subject account to have a handle. Ownership features SHALL NOT require a handle; that includes redemption and owned-item reads.

#### Scenario: Social action before choosing a handle
- **WHEN** an account without a handle sends a friend request
- **THEN** the service returns 409 `HANDLE_REQUIRED`

#### Scenario: Redemption before choosing a handle
- **WHEN** an account without a handle redeems a valid activation key
- **THEN** the claim succeeds exactly as before

### Requirement: Privacy-filtered public profile reads
`GET /api/v2/profiles/{handle}` SHALL be callable anonymously. It SHALL return only the fields the viewer is allowed to see under the owner's profile visibility (see `privacy-settings`). An unknown handle, a deleted account and a viewer the owner has blocked (or who has blocked the owner) SHALL all receive the identical 404.

#### Scenario: Public profile viewed anonymously
- **GIVEN** a profile with public visibility
- **WHEN** an anonymous caller reads it
- **THEN** the response contains handle, display name, avatar, bio and member-since month, plus each section's visibility state, and nothing else

#### Scenario: Private profile
- **GIVEN** a profile with private visibility
- **WHEN** someone other than the owner reads it
- **THEN** the response contains only handle, display name, avatar and `profile_visibility: private`

### Requirement: Wardrobe projection for other viewers
`GET /api/v2/profiles/{handle}/wardrobe` SHALL return the owner's items to permitted viewers as product presentations only, with stable cursor pagination. It SHALL NOT include public serials, item or unit identifiers, acquisition revision identifiers, or exact claim timestamps. A viewer without permission SHALL receive the same 404 as an unknown handle.

#### Scenario: Friend views a friends-only wardrobe
- **GIVEN** owner A has wardrobe visibility `friends` and B is A's friend
- **WHEN** B reads A's wardrobe
- **THEN** B sees A's items as product name, category and facts, without serials, identifiers or exact times

#### Scenario: Non-friend views a friends-only wardrobe
- **WHEN** a signed-in non-friend reads the same wardrobe
- **THEN** the service returns 404

### Requirement: Bounded handle search
`GET /api/v2/users/search` SHALL accept an exact handle or a prefix of at least 3 characters. It SHALL require a signed-in, onboarded caller and return at most 20 results. Each result SHALL contain handle, display name and avatar only. Accounts in a block relationship with the caller, and deleted accounts, SHALL be excluded.

#### Scenario: Prefix search
- **WHEN** an onboarded user searches `dra`
- **THEN** at most 20 matching profiles are returned, none of which has a block relationship with the caller
