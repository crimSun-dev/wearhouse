## Purpose

Represent source-backed clothing definitions separately from serialized garment units and credentials, preserving provenance without inventing catalogue facts or identifiers.

## ADDED Requirements

### Requirement: Source-preserving product ingestion
Authorised staff SHALL ingest a product using a source namespace, preserved external string identifier, source snapshot/checksum and permission record. Identical repeated ingestion MUST retain one product identity. Missing required provenance SHALL be rejected; unknown product attributes MUST remain distinguishable from verified facts.

#### Scenario: Leading-zero identifier and retry
- **GIVEN** a permitted source record with a leading-zero article identifier
- **WHEN** staff ingests the same record twice
- **THEN** one product identity exists, the identifier retains its zeros, and the repeated record does not duplicate a revision.

#### Scenario: Product metadata is incomplete
- **WHEN** staff submits missing provenance or unverified attributes as verified source facts
- **THEN** the input is rejected with field errors and no misleading published/source record is created.

### Requirement: Stable definition and revision identity
Changes to product data SHALL create an immutable revision while preserving product identity and acquisition references. External article IDs MUST NOT be represented as real GTINs without legitimate identifier evidence.

#### Scenario: Revised source description
- **GIVEN** an issued unit referencing product revision A
- **WHEN** staff ingests changed product facts creating revision B
- **THEN** the unit retains its acquisition/source revision reference and revision A remains auditable.

### Requirement: Separate uniquely serialized units
Authorised issuance SHALL create a distinct serialized unit and private credential for each request. Multiple units of one product SHALL have independent identities and claim lifecycles. Public serials MUST NOT reveal private keys.

#### Scenario: Two physical-unit representations of one product
- **WHEN** staff issues two units for the same product with different operation keys
- **THEN** two distinct public serials/private credentials exist and claiming one leaves the other unclaimed.

### Requirement: Issuance retries and restricted delivery
Issuance SHALL be idempotent for the same actor, route, operation key and payload. Credential delivery SHALL be restricted to the issuing actor, audited, excluded from caches/logs and recoverable for 24 hours while the unit remains unclaimed. Expired delivery MUST NOT silently mint another unit.

#### Scenario: Response lost after issuance
- **GIVEN** issuance committed but the response was lost
- **WHEN** the same staff actor retries within the delivery interval with the same operation key/payload
- **THEN** the same unit and secret delivery are returned without a second unit.

#### Scenario: Envelope expired or already deleted
- **GIVEN** issuance delivery expired or the unit has been claimed
- **WHEN** a retry requests the old secret delivery
- **THEN** the response reports delivery unavailable without revealing the secret or creating a replacement unit.

#### Scenario: Another actor probes delivery
- **GIVEN** a staff issuance operation belonging to actor A
- **WHEN** actor B requests A's delivery
- **THEN** the service reveals neither the secret nor a reusable delivery handle.

### Requirement: Audited reissue invalidates prior credentials
Authorised staff SHALL be able to revoke/reissue a credential only for an unclaimed unit. Reissue MUST preserve unit identity, invalidate the prior key and produce an audit event. Claimed units MUST reject reissue with 409.

#### Scenario: Unclaimed unit key recovery
- **GIVEN** an unclaimed unit whose original delivery is unavailable
- **WHEN** authorised staff explicitly reissues its credential
- **THEN** a new key is delivered for the same unit, the previous key cannot claim it, and the change is audited.
