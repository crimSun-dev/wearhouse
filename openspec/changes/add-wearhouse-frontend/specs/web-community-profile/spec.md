## Purpose

Defines the web community and profile experience: feed, friends, requests, blocks, inspirations, shares, reports, notifications, profiles, showcase and plan sharing. It respects the privacy projections of the friends-timeline, look-sharing, notifications, profile-showcase and moderation-inspiration capabilities.

## ADDED Requirements

### Requirement: Feed and inspirations
The community view SHALL show friends' visible shares from `GET /me/feed`, newest first, with cursor paging. Users SHALL be able to save a share as an inspiration and to remove inspirations. In an inspiration, pieces the user does not own SHALL link to a catalogue search or show as placeholders; an inspiration never grants items.

#### Scenario: Inspiration does not grant
- **WHEN** a user saves a friend's shared look as an inspiration
- **THEN** their wardrobe is unchanged and the missing pieces link to catalogue search

### Requirement: Friends, requests and blocks
Users SHALL be able to:
- search accounts (a prefix of at least 3 characters, or `@exact`; at most 20 results);
- send friend requests with an idempotency key;
- list incoming and outgoing requests, and accept, decline or cancel them;
- list friends and remove a friend;
- block and unblock accounts.

Before blocking, the app SHALL explain that blocking overrides friendship. The app SHALL explain the limits and the codes `REQUESTS_CLOSED`, `ALREADY_FRIENDS`, `PENDING_LIMIT_REACHED`, `FRIEND_LIMIT_REACHED` and `BLOCK_LIMIT_REACHED`.

#### Scenario: Requests closed
- **WHEN** the target has `friend_requests_from: nobody`
- **THEN** sending shows that this person is not accepting requests

### Requirement: Shares and reports
Users SHALL be able to:
- share a look to friends or the public with a caption of up to 140 characters;
- change the audience or caption;
- repin a share to the look's latest revision;
- delete a share.

The share list SHALL show the effective audience and moderation state. Signed-in users SHALL be able to report another user's share with a reason; `ALREADY_REPORTED` SHALL be explained.

#### Scenario: Effective audience narrower
- **WHEN** a share's audience is public but the owner's wardrobe privacy is friends
- **THEN** the share list shows the effective audience as friends

### Requirement: Notifications
Notifications SHALL list friend requests, accepted requests and friends' shares, with an unread badge, and SHALL support marking all as read. The unread count SHALL be refreshed only while the page is visible.

#### Scenario: Mark read
- **WHEN** a user marks notifications as read
- **THEN** the badge shows zero and the items no longer show as unread

### Requirement: Profiles, showcase and plan sharing
A profile SHALL show the server's privacy-filtered projection: avatar, display name, bio, showcase (headline, accent, featured shares), shared looks, and the wardrobe and friends sections when permitted. A blocked, deleted or unknown handle SHALL show one identical "not found" state.

The owner SHALL be able to:
- edit the display name, bio, avatar (preset or provider) and handle, with the 7-day change interval and the 30-day hold explained;
- edit the showcase (accent re-themes the profile header; up to 3 featured shares);
- set plan sharing to none or friends, and preview the friend-visible week, which contains no wear, weather or location.

#### Scenario: Not-found parity
- **WHEN** a user opens the profile of someone who blocked them
- **THEN** the page is identical to the page for a handle that does not exist
