## Purpose

Defines how the Wearhouse web app talks to the v2 API and the identity broker: sessions, errors, idempotency, caching, secrets and honest labelling, plus the gate that proves every API operation is used.

## ADDED Requirements

### Requirement: Contract-typed single client
The web app SHALL make every API call through one client module typed from `@wearhouse/contracts`. Each request SHALL carry an abort signal. Navigation away from a view or a filter change SHALL abort the obsolete requests, and their responses SHALL be discarded. The app SHALL NOT import code from `legacy/` and SHALL NOT call BMKG, Neon Postgres or any service other than the v2 API and the identity broker.

#### Scenario: Out-of-order response dropped
- **WHEN** a user changes a catalogue filter twice quickly and the first response arrives last
- **THEN** the grid shows only the results of the second filter

#### Scenario: No third-party data calls
- **WHEN** the network log of a full e2e run is inspected
- **THEN** every request goes to the configured API origin, the auth broker origin or the app's own origin

### Requirement: Session and token handling
The app SHALL get a fresh access token from the identity broker for each authenticated request and SHALL send it only in the `Authorization` header. Tokens SHALL NOT be written to URLs, web storage, IndexedDB, cookies set by the app, logs or analytics. After sign-in the app SHALL read `GET /me`. While `needs_onboarding` is true it SHALL route to onboarding before any private screen. Signing out SHALL clear every cached private response.

#### Scenario: New account onboarding
- **WHEN** a first-time user signs in and `/me` returns `needs_onboarding: true`
- **THEN** the app shows onboarding and does not render wardrobe, community or commerce screens until a handle is set

#### Scenario: Sign-out clears private data
- **WHEN** user A signs out and user B signs in on the same tab
- **THEN** no data of A appears in any view or in the client cache

### Requirement: Error envelope handling
The client SHALL parse `{code, message, field_errors?, request_id}` and show copy for every `ErrorCode` in both English and Indonesian. It SHALL map `field_errors` onto the matching inputs and keep what the user typed. On 429 it SHALL show a countdown from `Retry-After`. Unexpected errors SHALL offer the `request_id` for support. `REAUTHENTICATION_REQUIRED` SHALL lead to sign-in and then back to the interrupted action.

#### Scenario: Field error mapped
- **WHEN** a declared-item save returns 422 with a field error on `body.name`
- **THEN** the name input shows the message and the other inputs keep their values

#### Scenario: Rate limit countdown
- **WHEN** a request returns 429 with `Retry-After: 30`
- **THEN** the action is disabled with a visible 30-second countdown and re-enabled afterwards

### Requirement: Idempotent intents
For `POST /me/friend-requests`, `POST /me/checkout`, `POST /redemptions`, `POST /me/wear` and `POST /admin/unit-batches` the client SHALL send an `Idempotency-Key`. A key is created once per user intent and reused when the same intent is retried. A changed body SHALL start a new intent. `REQUEST_IN_PROGRESS` SHALL be retried after a short wait without creating a new key.

#### Scenario: Retry after a lost response
- **WHEN** a checkout request times out on the client and the user presses Retry
- **THEN** the retry sends the same Idempotency-Key and exactly one order exists

### Requirement: Secret handling
Activation keys revealed from receipts or staff deliveries SHALL be masked until the user reveals them. They SHALL be held only in component memory, SHALL be cleared when the user leaves the screen, and SHALL never appear in a URL, storage, log, analytics event or error report. A typed redemption key SHALL be cleared after a successful redemption.

#### Scenario: Key cleared on navigation
- **WHEN** a buyer reveals a key on a receipt, navigates away and presses Back
- **THEN** the key is masked again and revealing it makes a new audited request

### Requirement: Honest labelling
The app SHALL label:
- simulated prices as simulated, and checkout as charging and shipping nothing;
- recommendation and similarity results with their `model.mode` (a `heuristic_baseline` is never described as trained or AI);
- attribute values with `origin: rule` as estimated;
- weather by its source, with BMKG credited wherever forecast data appears, and days beyond the forecast horizon as "Forecast unavailable";
- missing media as "Image unavailable" over a slot silhouette.

The About information (`GET /about`) SHALL be reachable from every screen.

#### Scenario: Beyond-horizon day
- **WHEN** the planner shows a date with weather `status: beyond_forecast`
- **THEN** that day reads "Forecast unavailable" and shows no temperature or rain icon

### Requirement: Endpoint coverage gate
The build SHALL include a check that lists every operation in `packages/contracts/openapi-v2.json` and fails when the client does not use an operation that is not listed, with a reason, in an allowlist. CI SHALL run it.

#### Scenario: Unused operation fails CI
- **WHEN** an operation exists in the OpenAPI file, is unused by the client and is absent from the allowlist
- **THEN** the coverage check exits non-zero and names the operation
