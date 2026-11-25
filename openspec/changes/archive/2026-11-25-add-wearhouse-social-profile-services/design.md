## Context

`add-wearhouse-accounts` owns profiles, privacy (`profile`, `wardrobe`, `friends_list`), friendships, requests and blocks, plus the single policy function `can_view(section, setting, relation)`. The wardrobe planning change owns looks, immutable revisions and plans. This change adds social read models on top of both and changes neither policy.

## Goals / Non-Goals

**Goals:**
- sharing, feed, week, notifications and showcase that all reuse the accounts policy at read time, so reversals take effect immediately;
- projections that cannot leak private fields.

**Non-Goals:**
- comments or likes;
- real-time push;
- e-mail notifications;
- public discovery of strangers' shares, beyond profiles and direct links.

## Decisions

### D1: Visibility is computed at read time with a privacy ceiling

`visible(owner, viewer, audience)` is evaluated in this order:
1. The owner viewing their own share sees it.
2. A deleted owner (no profile) means not visible.
3. Otherwise the relation comes from `accounts.relationship()`.
4. The effective audience is the stricter of the share audience and the owner's `wardrobe` setting (public < friends < private).
5. The answer is `can_view(Section.WARDROBE, effective, relation)`.

Nothing is cached or copied, so unfriending, blocking or tightening privacy applies on the next read.

### D2: Projections come from the wardrobe application layer

`WardrobeService.projection(uow, owner, revision_id)` returns, per slot entry, `{slot, name, category, colour, verified, product_id}`. `product_id` is set only for verified items whose product is currently on sale or published, as checked by `RevisionReader.on_sale`. Social never touches wardrobe tables directly. A test asserts that the serialised projection contains no serial and no wardrobe item id.

### D3: Notifications are derived, not stored

Notifications are built per request:
- pending incoming requests (accounts `list_requests`);
- accepted outgoing requests from the last 30 days (new accounts port `accepted_outgoing`);
- friends' visible shares from the last 30 days.

These are merged, sorted and cut to 50. Only the read marker `notification_state.read_through` is stored. Because notifications are derived, a block or unfriend removes them immediately, and nothing is ever stale.

### D4: Tables (migration `0008_social`)

| Table | Columns and constraints |
|---|---|
| `look_share` | id, owner_id, look_id, revision_id, audience CHECK (friends, public), caption ≤ 140, created_at, revoked_at; index on (owner_id, created_at) |
| `plan_share_setting` | user PK, audience CHECK (none, friends), updated_at |
| `notification_state` | user PK, read_through |
| `profile_showcase` | user PK, headline ≤ 80, accent CHECK, featured JSONB (≤ 3 share ids), updated_at |

### D5: Feed paging

Feed paging uses an encrypted cursor over `(created_at, id)` of shares whose owners are the caller's friends. Pages are filled after filtering, so the service keeps fetching until the page is full or the shares run out.

### D6: Account integration

Social contributes:
- **export section:** your shares, plan-sharing setting and showcase;
- **eraser:** deletes your shares, settings and showcase.

Other users' shares need no cleanup, because visibility checks fail once the owner is deleted.

## Risks / Trade-offs

- **[Read-time policy costs a few queries per share.]** Feed pages are at most 100, and friend lists at most 1000. This is acceptable for the thesis scale, and a materialised feed can come later.
- **[A share pins a revision.]** Later edits do not leak into an existing share; the owner re-pins explicitly.

## Migration Plan

Run `0008` (additive), then deploy.
