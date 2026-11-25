## Why

Accounts already give Wearhouse handles, profiles, privacy, friends and blocks. Nothing social happens on top of them yet. The Steam-like experience needs:
- shared looks;
- a friends timeline (the "Friends" tab of Big Picture);
- a visible week plan for friends;
- notifications;
- profile showcases.

All of it must obey privacy and blocks, and it must never leak serials, keys, locations or private wear. This is roadmap services step 4 (`add-wearhouse-social-profile-services`, F06/F08 social side).

## What Changes

- **Look sharing.** A user shares one of their looks, pinned to a revision, with `friends` or `public` and an optional caption. Viewers see a safe projection: slot, item name, category, colour, verified or declared, and a store link only for verified items whose product is currently published. There are no serials, item ids, photos, care states or wear data. The owner's `wardrobe` privacy setting caps visibility at read time. Blocks hide everything, and unfriending, blocking or tightening privacy invalidates access immediately. The owner can revoke a share or re-pin it to the current revision.
- **Week plan sharing.** A user can let friends see their next seven planned looks: look names and projected items per date, with no weather, location or wear. The audience is `none` or `friends`, again capped by `wardrobe` privacy.
- **Friends timeline.** `GET /me/feed` lists looks shared by friends that the viewer can see now, newest first, with an encrypted cursor.
- **Notifications.** These are derived at read time from the source records, so a reversal removes them too:
  - incoming friend requests;
  - accepted outgoing requests (last 30 days);
  - friends' new shared looks (last 30 days).

  Each user has a read marker, giving an unread count and "mark all read".
- **Profile showcase.** A user sets a headline (up to 80 characters), an accent preset and up to 3 featured shares. `GET /profiles/{handle}/showcase` returns them under the profile visibility, listing only the featured shares the viewer can see.
- **Inspiration never grants items.** A shared look links to store products, and nothing in this change creates owned items, credentials or wishlist entries for a viewer.
- **Temporary pages.** The temporary web app gains: Share buttons on looks, a Feed page (Friends, plus What's New from the catalogue), a Notifications page with an unread badge, Showcase settings, and showcase, shared-look and week sections on public profiles.

## Capabilities

### New Capabilities
- `look-sharing`: look shares, week plan sharing and the safe projections.
- `friends-timeline`: the friends feed.
- `notifications`: derived notifications with read markers.
- `profile-showcase`: headline, accent and featured shares on public profiles.

### Modified Capabilities
None archived. This builds on `add-wearhouse-accounts` (privacy, friendship and block policy) and the wardrobe planning services (looks, revisions, plans).

## Impact

- **API.**
  - New `social` module.
  - Wardrobe exposes a safe projection operation through its application layer.
  - Accounts gains an `accepted_outgoing` read port.
  - Migration `0008_social`.
  - New `/api/v2/me/shares|feed|notifications|showcase|plan-sharing` routes, plus `/api/v2/shares/{id}`, `/api/v2/profiles/{handle}/showcase|week`.
  - Export and deletion sections are added; contracts are regenerated.
- **Pages.** `apps/web/account-pages` gains the social pages.
- **Unchanged.** Legacy v1.
