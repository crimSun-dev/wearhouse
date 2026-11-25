## Context

The HTTP edge (`platform/http.py`) already assigns request ids, enforces `no-store` on private paths and redacts logs. Redemption has DB-backed attempt buckets. Pool grounding: SYSTEM_DESIGN RULE-033 / TRAP-018 (layered limits); SNHU CS-305 TRAP-054 (per-user limits on public routes).

## Decisions

### D1: In-process sliding windows: IP and global at the edge, writes after authentication

An ASGI middleware keeps per-key deques of timestamps for `ip:<ip>` (trusted-proxy rule) and `global`. It runs before routing, so it is cheap and needs no database round trip.

The write layer is keyed by the verified user id inside `current_principal`, after the token verifies. Implementation first keyed writes by a digest of the Authorization header at the edge. That was revised because any client can mint new tokens from a valid session, resetting the count; a verified user id cannot be dodged or spent by someone else. Expired entries are pruned on access, and idle keys are swept every 10,000 hits to bound memory.

*Alternative considered:* the DB attempt ledger for every request. Rejected because it adds writes to every read; it stays for redemption, where cross-process exactness matters.

### D2: Configuration

Three settings: `WEARHOUSE_RATE_WRITES_PER_MIN` (120), `WEARHOUSE_RATE_IP_PER_MIN` (600) and `WEARHOUSE_RATE_GLOBAL_PER_MIN` (6000). In non-deployment environments `0` disables a layer (tests). Deployments refuse `0`.

### D3: The acceptance test drives HTTP only

The thread uses the test factory's signed identities and the public routes, no service shortcuts, except the CLI-equivalent bootstrap grant of the first admin. The restart check builds a second app from the same settings.
