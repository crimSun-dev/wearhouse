# foundation-environments Specification

## Purpose
Provide independently runnable Wearhouse v2 and legacy demo environments with explicit state ownership, migration safety and reproducible developer workflows.

## Requirements

### Requirement: Independent runtime and data environments
The system SHALL keep v2 customer state separate from legacy demo/test state. Runtime startup and destructive utilities MUST reject targets designated for the other environment.

#### Scenario: Wrong database target
- **GIVEN** a database designated as the legacy demo
- **WHEN** v2 is configured to use that database
- **THEN** startup fails with an actionable configuration error and no data mutation.

#### Scenario: Destructive demo traffic
- **GIVEN** the v2 database contains a claimed item
- **WHEN** a legacy reset or measurement utility is directed at that target
- **THEN** the utility refuses before any reset, seed or write occurs.

### Requirement: Explicit reproducible migrations
The system SHALL apply schema changes through explicit versioned migration commands. Normal v2 startup MUST NOT create schemas, migrate, reset or seed customer data; incompatible schemas MUST fail readiness.

#### Scenario: Fresh migration and repeat execution
- **GIVEN** an empty disposable v2 database
- **WHEN** the documented migration command is run twice
- **THEN** the database reaches the expected version without duplicate fixtures or destructive second-run effects.

#### Scenario: Startup with wrong schema version
- **GIVEN** a database at an unsupported schema version
- **WHEN** the v2 process starts
- **THEN** readiness fails and the existing schema/data remain unchanged.

### Requirement: Relocated legacy workflows remain usable
The system SHALL preserve documented local demo, offline demo, measurement and frontend build workflows after source relocation, including paths containing spaces/apostrophes. Legacy API/base-path behaviour SHALL remain isolated from v2.

#### Scenario: Offline demo from the workspace path
- **GIVEN** the relocated legacy dependencies are installed
- **WHEN** the root demo launcher is run in offline mode from the repository path
- **THEN** the legacy API and local frontend operate using the legacy SQLite/mock-weather environment without v2 access.

#### Scenario: Pages artifact compatibility
- **WHEN** the documented legacy Pages build is executed
- **THEN** the artifact supports `/LIVE-DEMO/` and `/LIVE-DEMO/app/`, includes only permitted public frontend files and still targets the configured legacy API.

### Requirement: Existing source and local work preservation
The restructuring SHALL preserve user modifications, supplied brand/reference/research originals and historical evidence. It MUST NOT publish secrets, local databases, dependency directories or research datasets as frontend assets.

#### Scenario: Build inputs include private local files
- **GIVEN** local environment secrets and database files exist outside public assets
- **WHEN** a frontend build is produced after restructuring
- **THEN** those files are absent from the public artifact and original logo/research inputs remain intact.

### Requirement: Foundation readiness has an executable ownership proof
Foundation completion SHALL require a source-backed admin issuance, public lookup, authenticated private claim and owner-read integration proof with restart, race and rollback checks. A synthetic fixture-only test MUST NOT be reported as the source-backed proof.

#### Scenario: Complete thread
- **GIVEN** a migrated isolated database, verified staff/customer identities and a permitted source fixture
- **WHEN** staff ingests the product and issues its key, customer A claims it and the service restarts
- **THEN** customer A retains exactly one item, customer B cannot read or claim it, and public lookup has created no ownership.

#### Scenario: Source fixture unavailable
- **WHEN** only fabricated or unverified catalogue metadata is available
- **THEN** lower-level invariant results are labelled separately and foundation source-backed readiness remains pending.
