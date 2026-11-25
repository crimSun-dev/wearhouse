# weather-forecast Specification

## Purpose
Supplies real, attributed BMKG forecast data with a safe fallback, and never fabricated weather.

## Requirements

### Requirement: Gateway with persisted cache and fallback
`GET /weather/forecast?adm4=` SHALL return validated forecast slots for a BMKG administrative code, choosing its data in this order:
1. a fresh cache entry, without fetching;
2. otherwise a live fetch, whose result is stored with a 3 h freshness window;
3. if the fetch fails, a cache entry up to 6 h old;
4. otherwise `MANUAL_REQUIRED` with no slots.

The response SHALL state its source (`LIVE`, `CACHED` or `MANUAL_REQUIRED`), when the data was fetched, and the reason for any fallback. If any feed entry fails validation, the service SHALL reject the whole feed. An `adm4` that does not match `^\d{2}\.\d{2}\.\d{2}\.\d{4}$` SHALL be rejected.

#### Scenario: BMKG down with a recent cache
- **GIVEN** a cache entry fetched 4 hours ago
- **WHEN** the live fetch times out
- **THEN** the response is `CACHED`, with the original fetch time and the reason

#### Scenario: Malformed feed
- **WHEN** BMKG returns an entry with humidity 140
- **THEN** that feed is not used, and the decision falls back as if the fetch had failed

### Requirement: User location
A user SHALL be able to set and clear their BMKG `adm4` location. `GET /me/weather` SHALL return the forecast for that location, or `MANUAL_REQUIRED` when no location is set.

#### Scenario: No location
- **WHEN** a user without a location reads `/me/weather`
- **THEN** the source is `MANUAL_REQUIRED`, with reason `no_location`
