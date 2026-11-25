## Purpose

Lets each account decide who can see its profile details, its wardrobe and its friends list. The server enforces those choices on every read, and blocks always override them.

## ADDED Requirements

### Requirement: Per-section visibility with safe defaults
Each account SHALL have separate visibility settings for profile, wardrobe and friends list. Each setting SHALL take one of `public`, `friends` or `private`. New accounts SHALL default to profile `public`, friends list `friends` and wardrobe `private`. Only the account itself SHALL be able to read or change its settings.

#### Scenario: Defaults for a new account
- **WHEN** a new account reads `GET /api/v2/me/privacy`
- **THEN** the response is profile `public`, friends list `friends`, wardrobe `private`

#### Scenario: Owner changes a setting
- **WHEN** the owner sets wardrobe visibility to `friends`
- **THEN** subsequent wardrobe reads by friends succeed and reads by non-friends return 404

### Requirement: Visibility is evaluated per read on the server
Every profile, wardrobe and friends-list read by someone other than the owner SHALL be decided at the time of the request. The decision SHALL use the owner's current settings, the current friendship state and the current block state. No client-supplied parameter SHALL widen access.

#### Scenario: Unfriending removes access immediately
- **GIVEN** B could read A's friends-only wardrobe
- **WHEN** A removes B as a friend and B reads the wardrobe again
- **THEN** B receives 404

#### Scenario: Client tries to widen access
- **WHEN** a viewer adds query parameters or headers such as `as_friend=true` or `visibility=public`
- **THEN** the response is identical to the request without them

### Requirement: Blocks override every visibility
If either account has blocked the other, the following SHALL all respond as if the other account does not exist:
- profile, wardrobe and friends-list reads;
- search;
- friend requests.

This holds regardless of visibility settings.

#### Scenario: Blocked viewer and a public profile
- **GIVEN** A's profile is public and A has blocked B
- **WHEN** B reads A's profile, wardrobe or friends list, or searches for A
- **THEN** B receives the same 404 or empty result as for an unknown handle

### Requirement: Friends-list projection respects both sides
A friends-list read by a permitted viewer SHALL list the owner's friends as handle, display name and avatar. It SHALL omit friends whose own profile is private, and friends in a block relationship with the viewer. Lists SHALL use stable cursor pagination with a default page of 24 and a maximum of 100.

#### Scenario: A friend has a private profile
- **GIVEN** A's friends list is public and A's friend C has a private profile
- **WHEN** an anonymous viewer reads A's friends list
- **THEN** C does not appear in the list
