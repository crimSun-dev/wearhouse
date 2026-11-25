## Purpose

Lets onboarded accounts connect as mutual friends through requests, remove friends, and block other accounts. Spam and abuse are limited by bounded, rate-limited operations.

## ADDED Requirements

### Requirement: Friend request lifecycle
An onboarded account SHALL be able to send a friend request to another onboarded account by handle. The sender SHALL be able to cancel it. The recipient SHALL be able to accept or decline it. Accepting SHALL create exactly one mutual friendship. Requests to oneself, to a current friend, or across a block SHALL be rejected. A request to an account that already has a pending request to the sender SHALL accept that existing request instead of creating a second one.

#### Scenario: Send and accept
- **WHEN** A sends a request to B and B accepts it
- **THEN** A and B each list the other as a friend, and the request is no longer pending

#### Scenario: Requests in both directions
- **GIVEN** B has a pending request to A
- **WHEN** A sends a request to B
- **THEN** A and B become friends, and no second pending request exists

#### Scenario: Duplicate send
- **WHEN** A sends a second request to B while the first is pending
- **THEN** the response returns the existing pending request, and the request count is unchanged

#### Scenario: Concurrent accept and cancel
- **WHEN** B accepts a request at the same time as A cancels it
- **THEN** exactly one outcome is committed, either friendship or cancellation, never both

#### Scenario: Request across a block or to oneself
- **WHEN** A requests B while either account blocks the other, or A requests A
- **THEN** the service returns the same 404 as for an unknown handle (block) or 422 (self), and creates no request

### Requirement: Removing a friend
Either friend SHALL be able to end the friendship. Removal SHALL take effect in both directions immediately, and SHALL NOT notify or reveal anything new to the other account.

#### Scenario: Remove
- **WHEN** A removes B
- **THEN** neither lists the other as a friend, and friends-only content is no longer visible to either

### Requirement: Blocking
An onboarded account SHALL be able to block another account by handle and later unblock it. Blocking SHALL, atomically:
- end any friendship;
- delete pending requests in both directions;
- hide each account from the other everywhere, as defined in `privacy-settings`.

Unblocking SHALL NOT restore the friendship or the requests. The blocked account SHALL NOT be told it was blocked.

#### Scenario: Block a friend
- **GIVEN** A and B are friends with no pending requests
- **WHEN** A blocks B
- **THEN** the friendship is gone, B cannot find or request A, and B's view of A is the unknown-handle 404

#### Scenario: Unblock
- **WHEN** A later unblocks B
- **THEN** they are not friends, and either may send a new request

### Requirement: Bounded and rate-limited social operations
The following limits SHALL apply:
- at most 50 new outgoing friend requests per rolling 24 hours, after which the service returns 429 with `Retry-After`;
- at most 200 pending outgoing requests per account;
- at most 1000 friends per account;
- at most 1000 blocks per account.

Sends, accepts, blocks and unblocks SHALL be idempotent per operation. Friend, request and block lists SHALL use stable cursor pagination, owner-scoped, with a default page of 24 and a maximum of 100.

#### Scenario: Request flood
- **WHEN** an account sends its 51st new request within 24 hours
- **THEN** the service returns 429 `RATE_LIMITED` with `Retry-After`, and creates no request

#### Scenario: Friend limit reached
- **WHEN** accepting a request would give either account more than 1000 friends
- **THEN** the service returns 409 `FRIEND_LIMIT_REACHED`, and no friendship is created

### Requirement: Social lists are private to their owner
Incoming requests, outgoing requests and blocks SHALL be readable only by their owner. A cursor issued to one account SHALL be rejected when presented by another.

#### Scenario: Reading another account's requests
- **WHEN** B presents a request-list cursor issued to A
- **THEN** the service returns 422 `invalid_cursor` and reveals nothing about A's requests
