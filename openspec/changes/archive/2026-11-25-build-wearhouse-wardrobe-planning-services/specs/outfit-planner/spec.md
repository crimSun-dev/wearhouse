## Purpose

Lets users plan looks for upcoming days, see a truthful seven-day view, and record what they actually wore.

## ADDED Requirements

### Requirement: Date plans
A user SHALL be able to set, replace and clear a plan for a local date (Asia/Jakarta) from today to 30 days ahead. A plan holds a look revision of their own, an optional occasion (`casual`, `work`, `formal`, `sport`, `event`) and an optional note of up to 200 characters. Dates in the past or more than 30 days ahead SHALL be rejected.

#### Scenario: Plan beyond the window
- **WHEN** a user plans 31 days ahead
- **THEN** the service returns 422

### Requirement: Seven-day view with forecast-horizon labels
`GET /me/planner?from=YYYY-MM-DD` SHALL return 7 consecutive local dates, each with:
- its plan (or none);
- its wear entries;
- a `weather` block that is `forecast`, with summarised slots and the source, only when the date is inside the BMKG horizon and forecast data exists;
- otherwise `beyond_forecast` or `unavailable`.

The service SHALL NOT synthesise weather for any date.

#### Scenario: Day five has no forecast
- **WHEN** the view covers today through six days ahead
- **THEN** dates past the forecast horizon are labelled `beyond_forecast`, with no temperature or rain values

### Requirement: Actual wear log
`POST /me/wear` SHALL record that the user wore either a look revision or a set of their own items on a date. It SHALL require an `Idempotency-Key`, and the date SHALL be today or up to 60 days back. A wear entry SHALL be separate from the plan: planned is not worn. A user SHALL be able to delete a wear entry. Each item's wear count and last-worn date SHALL derive from the wear log.

#### Scenario: Retry does not double count
- **WHEN** the same wear request is retried with the same key
- **THEN** one wear entry exists, and the item's wear count rises by 1

#### Scenario: Future wear
- **WHEN** a user logs wear for tomorrow
- **THEN** the service returns 422
