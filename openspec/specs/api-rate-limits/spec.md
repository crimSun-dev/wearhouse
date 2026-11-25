# api-rate-limits Specification

## Purpose
Prevents brute force, scraping and request floods across the whole API, not only redemption.

## Requirements

### Requirement: Layered request limits
The API SHALL limit requests in a sliding 60-second window:
- authenticated mutating requests (POST, PUT, PATCH, DELETE) per verified user id, checked after the bearer token verifies, so minting fresh tokens does not reset the count and a forged token cannot spend another user's quota;
- all requests per client IP;
- all requests process-wide.

The limits SHALL be configurable (defaults: 120 writes per caller, 600 requests per IP, 6000 process-wide). A refused request SHALL return 429 with `Retry-After` in seconds and the standard error body with code `RATE_LIMITED`. `/health` and `/health/ready` SHALL be exempt. Token values SHALL never be stored or used as keys.

#### Scenario: Write flood
- **WHEN** one caller sends more writes in a minute than the limit
- **THEN** the excess requests get 429 with `Retry-After`, and another caller is unaffected

#### Scenario: Fresh tokens do not reset the write limit
- **WHEN** one user sends writes with several distinct valid tokens
- **THEN** they share one write budget

#### Scenario: Health exempt
- **WHEN** the process-wide limit is exhausted
- **THEN** `/health` still answers 200

### Requirement: Per-process scope is declared
Limits SHALL be enforced per API process. The effective ceiling with N instances is N times the configured value, which SHALL be stated in the operations documentation. Redemption keeps its database-backed limits, which are shared across processes.

#### Scenario: Documentation states scope
- **WHEN** an operator reads the configuration docs
- **THEN** the per-process nature and the shared redemption limits are stated
