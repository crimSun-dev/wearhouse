## Why

Wearhouse currently rests on a single-user demo with a shared write key, public-QR ownership claims and duplicated Python/Node business rules. Before rebuilding its frontend from scratch, the project needs a coherent structure and a proven authenticated ownership foundation that matches its research and preserves the course demo independently.

## What Changes

- Establish `apps/api` as the canonical Python/FastAPI v2 application; isolate existing Python, Node and frontend demo runtimes under `legacy/` and update their launch, fixture, build and CI paths together.
- Introduce domain boundaries, versioned migrations, explicit environment/database separation and a generated OpenAPI/TypeScript contract package. Reserve `apps/web` for the later fresh frontend rather than transplanting the existing renderer.
- Add verified identity, server-managed roles and owner-scoped access, with an explicit test-only principal adapter.
- Add a narrow source-backed product/serialized-unit workflow: authorised source-product ingestion, unit/private-key issuance, public discovery-only lookup, atomic redemption and persisted owned-item reads.
- **BREAKING for v2:** public QR/serials never establish ownership; client owner IDs and the legacy browser API key confer no authority. Legacy v1 stays an isolated demo rather than becoming a second v2 writer.
- Prove concurrency, rollback, retry, rate-limit, migration and isolation contracts before frontend implementation. Record deployment/identity/source-permission prerequisites as concrete tasks rather than assumed resources.
- Provide a dependency roadmap covering the remaining ecosystem services, complete frontend rebuild using supplied Wearhouse logos and Steam references, research intelligence and final cutover.

## Capabilities

### New Capabilities

- `foundation-environments`: Independently runnable v2 and legacy environments, explicit migration/startup behaviour, test isolation and usable build/launch workflows.
- `identity-access`: Verified principals, server-controlled capabilities, private resource scoping and fail-closed deployment configuration.
- `source-product-units`: Source-preserving product identity, authorised narrow ingestion, immutable product revisions and serialized unit/private-key issuance.
- `private-redemption`: Public discovery without ownership, private authenticated one-time claims, durable attempt limits, transactional ownership and retry guarantees.
- `versioned-api-contracts`: Versioned API errors/pagination/idempotency, reproducible client contracts and honest model-serving metadata.

### Modified Capabilities

None. `openspec/specs/` currently has no authored capability specifications; all v2 behaviours are ADDED requirements. Observed changes from legacy behaviour are documented in design rather than invented as existing MODIFIED requirements.

## Impact

Impacts the future locations of `backend/`, `neon-backend/`, `Frontend/frontend/`, `run_demo.ps1`, `scripts/build_pages.py`, API type generation, tests and `.github/workflows/{ci,pages}.yml`. PostgreSQL migrations, OIDC verification and encrypted short-lived issuance delivery add server-side dependencies to select/pin during implementation. Neon v1 deployment paths and relative imports must migrate as one unit; no cloud resource or production data is changed by this proposal.

The existing TDD and latest user direction govern: canonical Python backend first, entirely fresh UI later. Product feature completion, bulk catalogue administration, mock commerce, full planner/social APIs, trained models, visual design implementation and production cutover are later changes described in `roadmap.md`. Existing Assets/Reference/research originals and user modifications remain preserved.
