# Hardening readiness (harden-wearhouse-services-api)

Date: 2026-11-25. Local PostgreSQL 18 (port 55432), Windows 11, Python 3.11 API venv.

## What changed

| Area | Change | Pool grounding |
|---|---|---|
| Edge limits | `RateLimitMiddleware` (`platform/http.py`): sliding 60 s windows per client IP (trusted-proxy rule) and process-wide. Health endpoints exempt; `OPTIONS` passes. Refusals return `429 RATE_LIMITED`, `Retry-After` and the standard error body (request id included) | SYSTEM_DESIGN RULE-033, TRAP-018 |
| Write limit | Per **verified user id** inside `current_principal`, after token verification, for `POST`/`PUT`/`PATCH`/`DELETE` | SNHU CS-305 TRAP-054 |
| Settings | `WEARHOUSE_RATE_WRITES_PER_MIN` (120), `WEARHOUSE_RATE_IP_PER_MIN` (600), `WEARHOUSE_RATE_GLOBAL_PER_MIN` (6000). `0` disables a layer outside deployments; staging and production refuse `0` | — |
| Acceptance | `tests/test_ecosystem_acceptance.py`: the F11 thread over HTTP, restart with a fresh app, isolation | roadmap F11 |

### Deviation from the first design

The first implementation keyed the write limit by a digest of the `Authorization` header at the edge. The test that minted three tokens for one user showed the flaw: a client can mint fresh tokens from a valid session, and each one reset the count. The write layer now runs after authentication, keyed by the verified user id, so:
- fresh tokens share one budget;
- a forged token is rejected before it can spend anyone's quota.

The spec, proposal and design were updated to match.

## Scope stated honestly

- The limits are **per process**. N instances allow N times each value. Redemption keeps its database-backed per-user/IP/global limits, which are shared across processes and remain the security-critical limiter for key guessing.
- The windows live in memory and reset when the process restarts.

## Evidence

| Check | Result |
|---|---|
| `tests/test_rate_limits.py` | 6 passed: write flood (4th write → 429, other user unaffected, reads not write-limited); fresh tokens do not reset; IP limit; global limit with health exempt; window slides and keys hold only `ip:<addr>`; `Retry-After` maths; deployment refuses `0` |
| `tests/test_ecosystem_acceptance.py` | 1 passed. The thread runs through HTTP:<br>1. admin grants roles in the app<br>2. import, publish 3, generate 3 placeholders, bulk offers 3<br>3. search, then the media object serves as `image/svg+xml`<br>4. wishlist, checkout, key reveal, claim (verified item)<br>5. look, plan, wear (`wear_count` 1), share<br>6. the friend's feed and the `friend_shared_look` notification<br>7. similar and personal recommendations declare `heuristic_baseline`; the owned product is excluded<br><br>A fresh app instance returns byte-identical item, order, look and share, plus the notification and the plan.<br><br>A stranger gets 403/404 on the order, key, both wardrobe items, the owned item, the look, the look revision, the friends-only share and the week view. The stranger's own order, look, feed and planner lists show none of it. |
| Full API suite | 595 passed (plus `test_cli_import_recommendations`, run separately: 5/5 in the file) |
| Contracts | up to date (two clean generations match) |
| Pages e2e (Playwright) | 11 passed |

## Not covered here

- Distributed (cross-instance) rate limiting. This is only needed for a multi-instance deployment, and the per-process scope is documented.
- The deployed Neon environment still runs legacy v1. These limits apply once v2 is deployed, and deployment requires the owner's confirmation.
