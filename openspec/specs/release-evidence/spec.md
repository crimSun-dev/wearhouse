# release-evidence Specification

## Purpose
Operational visibility and measured release bars (TDD §14).

## Requirements

### Requirement: Ops summary and measured budgets
`GET /admin/ops` (admin only) SHALL return counts only:
- claim failures and rate-limited attempts in the last 24 hours;
- the import job and outbox backlogs;
- the active recommendation artifact and mode;
- the schema head.

A measurement tool SHALL record, with hardware, data size and warm/cold state:
- catalogue first-page p95 under 20 concurrent clients;
- personal recommendation p95;
- outfit suggestion p95 at 80 items.

A backup/restore rehearsal SHALL restore a dump into a fresh database and pass readiness checks with equal row counts.

#### Scenario: Budgets recorded
- **WHEN** the measurement tool runs against the dev catalogue
- **THEN** each result is compared with its TDD budget and written to the evidence document, pass or fail
