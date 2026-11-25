## Purpose

Lets users show looks and their week to others without exposing anything private, under the existing privacy and block policy.

## ADDED Requirements

### Requirement: Look shares with read-time visibility
A user SHALL be able to share one of their own looks, pinned to its current revision, with audience `friends` or `public` and an optional caption of up to 140 characters. A user SHALL have at most 100 active shares. A share SHALL be visible to a viewer only when all of the following hold:
- neither user blocks the other;
- the owner's account exists;
- `can_view(min(share audience, owner wardrobe privacy), relation)` is true.

The owner SHALL be able to revoke a share and re-pin it to the look's current revision. An invisible, revoked or missing share SHALL return the same 404.

#### Scenario: Unfriending invalidates access
- **GIVEN** A shares a look with friends, and B is A's friend
- **WHEN** A removes B as a friend
- **THEN** B's next read of that share returns 404

#### Scenario: Privacy ceiling
- **GIVEN** a `public` share, and the owner later sets wardrobe privacy to `private`
- **WHEN** an anonymous visitor reads it
- **THEN** it returns 404

#### Scenario: Block hides everything
- **WHEN** either user blocks the other
- **THEN** shares in both directions return 404

### Requirement: Safe projection
A shared look projection SHALL contain only, per slot entry:
- the slot;
- the item name, category and colour, or null;
- whether the item is verified;
- for verified items whose catalogue product is currently published, the product id for a store link.

It SHALL NOT contain public serials, activation keys, wardrobe item ids, photos, care states, wear counts or dates, weather or location.

#### Scenario: No private fields leak
- **WHEN** a friend reads a share of a look containing a claimed garment
- **THEN** the response contains the product id and name, and does not contain the unit's public serial or the wardrobe item id

### Requirement: Week plan sharing
A user SHALL be able to set plan sharing to `none` (the default) or `friends`. `GET /profiles/{handle}/week` SHALL return the next 7 local dates, each with the planned look's name and projected items. It SHALL be visible only when plan sharing is `friends`, the viewer is a friend, there is no block, and the owner's wardrobe privacy is not `private`. It SHALL NOT include wear entries, weather or location.

#### Scenario: Stranger cannot see the week
- **WHEN** a non-friend requests a user's week
- **THEN** the service returns 404

### Requirement: Inspiration never grants items
Reading shares, the feed, the week or the showcase SHALL NOT create owned items, credentials, units, wishlist or cart entries for anyone.

#### Scenario: Viewing a share changes nothing
- **WHEN** a friend reads a share many times
- **THEN** that friend's owned items, wishlist and cart are unchanged
