## Purpose

Shows a signed-in user what their friends have recently shared.

## ADDED Requirements

### Requirement: Friends feed
`GET /me/feed` SHALL list active look shares whose owners are the caller's friends and that the caller can currently see, newest first. It SHALL use an encrypted cursor (default 24, maximum 100). Each entry SHALL carry the owner's public card, the caption, the share time and the safe projection. Shares that stop being visible SHALL disappear from the feed on the next read.

#### Scenario: Friend's share appears
- **WHEN** a friend shares a look with friends
- **THEN** it appears at the top of the caller's feed

#### Scenario: Blocked friend's shares vanish
- **WHEN** the caller blocks a friend
- **THEN** none of that user's shares appear in the caller's feed
