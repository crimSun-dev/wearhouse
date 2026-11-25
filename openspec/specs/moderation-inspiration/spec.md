# moderation-inspiration Specification

## Purpose
Moderation of shared looks and saved inspiration (TDD §§7, 11).

## Requirements

### Requirement: Reports and moderation
A signed-in user SHALL be able to report a share they can see, once per share, with a reason. Moderators (`social:moderate`) SHALL list open reports and hide or restore a share with a reason. Every moderation action SHALL be audited. A hidden share SHALL return 404 to everyone except its owner, who sees `moderation: hidden`. Moderators SHALL have no capability over keys, orders, units or private wardrobes.

#### Scenario: Hide
- **WHEN** a moderator hides a reported public share
- **THEN** anonymous viewers and friends get 404, it leaves feeds, and the owner sees it marked hidden

### Requirement: Inspiration snapshots
A user SHALL be able to save a share they can currently see as a private inspiration. The inspiration holds a snapshot of the safe projection and never grants items or reveals identifiers beyond that projection. It is listed and deleted by its owner only, and included in the export.

#### Scenario: Saved snapshot survives unsharing
- **WHEN** the friend later revokes the share
- **THEN** the saved inspiration remains with its snapshot, and still grants no items
