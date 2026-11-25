## 1. Rate limits

- [x] 1.1 Add the edge rate-limit middleware (write/ip/global sliding windows, digest keys, health exempt, 429 + `Retry-After` + `RATE_LIMITED` body, memory sweep) and settings with deployment safeguards; document the per-process scope. Verify: write flood gets 429 while another caller passes, the IP limit, health exempt, no token text in keys, deployment refuses 0.

## 2. Acceptance

- [x] 2.1 Write the F11 ecosystem acceptance test (HTTP-only thread, restart with a fresh app, second-customer isolation over every private object). Verify it passes, and run the full suite and e2e.

## 3. Readiness

- [x] 3.1 Record evidence in `docs/architecture/hardening-readiness.md` and update the API README and the operations runbook.
