## Purpose

Provide reproducible versioned integration contracts and honest serving metadata so later Wearhouse clients can depend on tested backend behaviour without inheriting demo-only assumptions.

## ADDED Requirements

### Requirement: Versioned integration surface
New ownership/account operations SHALL be exposed under `/api/v2`, separate from the legacy contract. API generation SHALL describe actual callable operations and MUST NOT expose unimplemented future capabilities as successful handlers.

#### Scenario: Client selects v2
- **WHEN** a client uses the v2 account/claim/item contract
- **THEN** it receives the verified-principal and private-redemption semantics defined by v2 without legacy write-key/serial shortcuts.

### Requirement: Reproducible generated contracts
The system SHALL provide a documented deterministic process producing machine-readable API definitions and client types from the same v2 contract. Generation MUST NOT mutate a database, seed data or require live identity/weather calls. CI SHALL detect stale checked-in contract outputs.

#### Scenario: Offline schema generation
- **GIVEN** installed pinned contract-generation tooling with external services unavailable
- **WHEN** contract generation is run twice on unchanged API declarations
- **THEN** both outputs match and no external state is accessed or modified.

#### Scenario: API contract changes without regeneration
- **WHEN** API declarations differ from checked-in generated definitions/types
- **THEN** the contract-drift check fails with actionable regeneration instructions.

### Requirement: Consistent errors and bounded private pagination
Errors SHALL include a stable code, message and request identifier with structured field errors when applicable. Private lists SHALL use stable bounded pagination, defaulting to 24 and capped at 100, scoped to the authenticated actor. Invalid cursors SHALL be rejected rather than returning another user's data.

#### Scenario: Invalid field
- **WHEN** a request supplies an invalid required field
- **THEN** the API returns 422 with stable code/message, request identifier and field detail excluding secrets.

#### Scenario: Cursor replay under another account
- **GIVEN** a private item-list cursor issued to customer A
- **WHEN** customer B supplies that cursor
- **THEN** the service rejects it and reveals no records from A.

### Requirement: Secret-bearing operations are not cached or logged
Credential issuance, reissue and redemption SHALL prevent secret-bearing request/response content from entering application access/error/audit logs or shared caches. Private responses SHALL disable storage by intermediary/browser caches.

#### Scenario: Claim failure is instrumented
- **WHEN** an invalid-key claim produces a structured error and audit/metrics event
- **THEN** logs retain request/correlation/result metadata but no raw activation key, token, key digest or secret-bearing request body.

### Requirement: Recommendation modes are truthful
Recommendation integration contracts SHALL distinguish a heuristic baseline from trained compatibility/ranking artifacts and include available model/rules version metadata. Untrained adapters MUST NOT claim trained-model performance or fabricate embeddings.

#### Scenario: Only baseline available
- **GIVEN** no trained artifact is loaded
- **WHEN** an internal or future downstream consumer invokes the baseline recommendation adapter
- **THEN** the result identifies heuristic mode and its actual version rather than reporting trained FashionCLIP/type-aware output.
