## Purpose

One synced, validated set of personal preferences that the API also obeys.

## ADDED Requirements

### Requirement: Typed settings registry, synced with optimistic versions
`GET /me/settings` SHALL return `{version, updated_at, values, schema}`. `values` contains every registered key, with its default when unset. `schema` lists each key's section, type (choice, flag or integer range), allowed values and default.

`PATCH /me/settings {version, values}` SHALL behave as follows:
- it SHALL apply only registered keys with valid values;
- it SHALL refuse unknown keys or invalid values with 422, changing nothing;
- it SHALL refuse a `version` other than the current one with `409 SETTINGS_CHANGED`;
- on success it SHALL bump the version and audit the changed keys (not their values).

Settings SHALL be in the account export and erased with the account.

#### Scenario: Two devices
- **WHEN** device A saves with version 3 and device B then saves with version 3
- **THEN** B gets 409 `SETTINGS_CHANGED`, and A's values stand

#### Scenario: Defaults
- **WHEN** a new account reads its settings
- **THEN** every key has its default, and the version is 0

### Requirement: Settings change behaviour
The API SHALL obey these settings:
- `notify_friend_requests`, `notify_request_accepted` and `notify_friend_shares` filter the derived notifications and the unread count;
- `friend_requests_from = nobody` makes new requests to the account fail with `409 REQUESTS_CLOSED` (existing pending requests remain);
- `discoverable = false` removes the account from prefix search, while an exact `@handle` search still finds it;
- `style_suggestions = false` makes outfit suggestions return `enabled: false` with no suggestions;
- `weather_in_suggestions = false` ranks without weather (source `DISABLED`);
- `recommendation_style` selects the weight profile: balanced 0.5/0.3/0.2, classic 0.7/0.25/0.05, or adventurous 0.35/0.25/0.40 (compatibility/weather/rotation).

#### Scenario: Requests closed
- **WHEN** B sets `friend_requests_from` to `nobody` and A sends B a request
- **THEN** A gets 409 `REQUESTS_CLOSED`

#### Scenario: Adventurous favours unworn items
- **WHEN** two otherwise equal outfits differ only in a recently worn item
- **THEN** adventurous ranks the unworn one first by a wider margin than classic does
