## 1. Data model

- [x] 1.1 Write migration `0008_social` (D4 tables, CHECK constraints, grants) and update `RUNTIME_PRIVILEGES`. Verify upgrade/repeat, empty `compare_metadata`, and the privilege check.

## 2. Sharing

- [x] 2.1 Add the wardrobe safe projection and the accounts `accepted_outgoing` port. Implement look shares (create, list mine, patch audience/caption/repin, revoke, read by id) with D1 visibility, plus public profile shares. Verify: unfriend gives 404, block in both directions gives 404, the privacy ceiling gives 404, a deleted owner gives 404, no serial or item id in the projection, store links only for published products, and the 100-share limit.
- [x] 2.2 Implement week plan sharing (setting plus `/profiles/{handle}/week`). Verify: the stranger gets 404, a friend sees 7 days without wear or weather, `none` gives 404, and private wardrobe gives 404.

## 3. Feed and notifications

- [x] 3.1 Implement the friends feed with an encrypted cursor and post-filter page filling. Verify: newest first, a block removes entries, paging has no repeats, and a tampered cursor gives 422.
- [x] 3.2 Implement derived notifications, the read marker and the unread count. Verify: incoming request, accepted request, friend share, block removes, mark-read zeroes the count and a newer event counts again.

## 4. Showcase

- [x] 4.1 Implement the showcase settings and the `/profiles/{handle}/showcase` read. Verify: foreign or revoked share gives 422 `unknown_share`, at most 3, anonymous sees only public featured shares, and profile privacy is respected.

## 5. Integration, contracts, pages, readiness

- [x] 5.1 Add the export and deletion sections, regenerate contracts, update routes and boundaries, and check that inspiration never grants items. Verify the full v2 suite and the drift check.
- [x] 5.2 Add Share controls on looks, Feed (Friends plus What's New), Notifications with an unread badge, Showcase settings, and public profile showcase, shares and week sections. Verify typecheck, the build guard and a two-user e2e flow: share → friend's feed and notification → unfriend → gone.
- [x] 5.3 Record evidence in `docs/architecture/social-readiness.md` and update the API README.
