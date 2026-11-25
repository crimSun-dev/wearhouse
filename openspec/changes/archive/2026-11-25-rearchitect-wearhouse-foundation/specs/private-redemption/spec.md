## Purpose

Allow a verified user to claim a serialized garment exactly once using a private activation credential while public tags remain discovery-only and attempts are durably constrained.

## ADDED Requirements

### Requirement: Public tags never grant ownership
Public tag lookup SHALL return product discovery metadata without creating ownership. Public QR contents or serials submitted as activation credentials MUST NOT grant ownership. Public output MUST omit private credentials, owner identity and claim-attempt details.

#### Scenario: Scan or preview a public link
- **GIVEN** an issued unclaimed unit
- **WHEN** any caller repeatedly reads/previews its public tag
- **THEN** no owned item/claim event is created and the private key remains required.

#### Scenario: Copied public contents submitted for claim
- **WHEN** a verified user submits a public serial or QR URL as an activation key
- **THEN** the generic invalid-activation response is returned and no ownership is created.

### Requirement: Atomic private-key ownership
An eligible private credential SHALL atomically establish one owned item for the verified actor, mark the credential redeemed and append ownership/delivery events. No unit SHALL be owned twice. Actor-bound credentials MUST be rejected for other actors.

#### Scenario: Successful private claim
- **GIVEN** an eligible unused private key and an allowed authenticated customer
- **WHEN** that customer redeems the key
- **THEN** exactly one owned item is assigned to that customer in its source-derived category and the key cannot create a second item.

#### Scenario: Different actors race
- **GIVEN** an unused bearer credential and two authenticated customers using different operation keys
- **WHEN** both redeem concurrently
- **THEN** exactly one succeeds and one receives the generic invalid response, with one item/claim event committed.

#### Scenario: Failure between claim effects
- **WHEN** an internal failure occurs after credential transition but before the full claim commits
- **THEN** no partial ownership, credential transition or ownership/outbox event remains committed and a subsequent eligible retry can claim once.

### Requirement: Claim retry is durable and scoped
Redemption SHALL require an idempotency key scoped to actor, route and request. An identical committed retry SHALL return its prior success without another effect or attempt reservation, including after restart. Reuse with a different body SHALL return 409.

#### Scenario: Lost claim response
- **GIVEN** a committed claim whose response was lost
- **WHEN** the same customer retries the same operation after restart
- **THEN** the same owned-item result is returned and counters/events/item count are unchanged.

#### Scenario: Different request reuses operation key
- **WHEN** a customer submits another activation payload under an existing operation key
- **THEN** the service returns 409 without evaluating or consuming that new credential.

### Requirement: Uniform invalid-credential behaviour
Unknown, malformed, altered, revoked, wrong-actor and already-used credentials SHALL return the same generic 400 invalid-activation code/message without item, owner or credential-state disclosure. Authentication and rate-limit responses SHALL remain distinguishable.

#### Scenario: Compare invalid states
- **WHEN** a verified caller submits each invalid credential state under fresh operation keys while below admission limits
- **THEN** every response has the same invalid-activation status/code/message apart from request identifiers, with no ownership effects.

### Requirement: Durable multi-process admission limits
The service SHALL admit at most 10 new activation attempts per actor in a rolling hour across processes and restarts. Failed claims SHALL retain their attempt reservations. Additional configured IP/global limits SHALL fail closed when their backing state is unavailable.

#### Scenario: Concurrent limit boundary
- **GIVEN** nine admitted attempts by a customer within the previous hour
- **WHEN** several workers concurrently submit new attempts
- **THEN** at most one new attempt is admitted and the others return 429 with retry guidance.

#### Scenario: Restart and failed claim
- **GIVEN** failed admitted attempts that reached the hourly limit
- **WHEN** the API restarts and another new operation is submitted before expiry
- **THEN** that operation remains rate limited and previous claim rollbacks have not erased attempts.
