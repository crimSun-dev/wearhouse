## Purpose

Tells users about social events that concern them, derived from the source records so privacy reversals apply automatically.

## ADDED Requirements

### Requirement: Derived notifications
`GET /me/notifications` SHALL return up to 50 notifications, newest first. They SHALL be derived at read time from:
- pending incoming friend requests (`friend_request`);
- the caller's outgoing requests accepted in the last 30 days (`request_accepted`);
- shares by friends that are visible to the caller and created in the last 30 days (`friend_shared_look`).

Each notification SHALL carry a kind, a time, the other account's card, and a reference: a request id or a share id. It SHALL be marked unread when it is newer than the caller's read marker.

#### Scenario: Accepted request
- **WHEN** B accepts A's friend request
- **THEN** A has an unread `request_accepted` notification with B's card

#### Scenario: Reversal removes the notification
- **GIVEN** A has a `friend_shared_look` notification from B
- **WHEN** A blocks B
- **THEN** that notification no longer appears

### Requirement: Read marker
`POST /me/notifications/read` SHALL set the caller's read marker to now. `GET /me/notifications/unread-count` SHALL return the number of unread notifications.

#### Scenario: Mark all read
- **WHEN** the caller marks notifications read
- **THEN** the unread count is 0 until a newer notification exists
