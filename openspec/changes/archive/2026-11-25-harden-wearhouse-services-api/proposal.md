## Why

Before the frontend starts, the API surface must resist abuse, and the whole ecosystem must be shown to work end to end.

Only redemption has layered admission limits. The understanding pool is explicit:
- **RULE-033** (SYSTEM_DESIGN_FULLSTACK_PRODUCTION): rate-limit per endpoint, per user/IP and system-wide;
- **TRAP-018**: never leave APIs without rate limiting;
- **SNHU CS-305 TRAP-054**: put per-user rate limiting in front of public routes.

F11 in the roadmap requires the complete thread to work across accounts and to survive a restart: admin publishes → customer discovers, wishlists, mock-buys, redeems, equips, plans, wears, shares.

## What Changes

- **Layered request rate limits** at the HTTP edge:
  - per verified user for authenticated writes (checked after token verification);
  - per client IP for public reads;
  - a process-wide ceiling.

  Limits are configurable. A refused request returns `429` with `Retry-After` and the standard error body. Health endpoints are exempt. The redemption ledger, which is DB-backed and per user/IP/global, is unchanged and stays the security-critical limiter.
- **The F11 ecosystem acceptance test.** It runs on one database with signed identities, through the HTTP API only:
  1. An admin grants the editor and inventory roles in the app.
  2. The editor imports and publishes products, generates media and sets bulk offers.
  3. A customer finds a product, wishlists it, buys it, reveals the key and claims it.
  4. The customer builds a look, plans it, wears it and shares it.
  5. A friend sees the share in the feed and notifications.
  6. Recommendations respond with declared modes.
  7. A **fresh app instance** on the same database still serves everything.
  8. A second customer cannot read any of the first customer's private objects.

## Capabilities

### New Capabilities
- `api-rate-limits`: layered request limits at the edge.
- `ecosystem-acceptance`: the F11 end-to-end thread.

### Modified Capabilities
None.

## Impact

`platform/http.py` gains the rate-limit middleware; `bootstrap/config.py` gains limit settings. A new acceptance test. No schema change.
