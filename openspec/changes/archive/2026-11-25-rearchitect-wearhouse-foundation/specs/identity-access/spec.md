## Purpose

Establish verified account identity and server-enforced access boundaries so Wearhouse customers and staff cannot act as other users or obtain unintended capabilities.

## ADDED Requirements

### Requirement: Verified deployment principals
Protected v2 operations SHALL derive their actor from a token whose signature, issuer, audience and validity interval are verified. Missing/invalid credentials MUST return 401 without performing the operation. Legacy demo keys and client-supplied identity fields MUST NOT confer v2 authority.

#### Scenario: Invalid identity variants
- **GIVEN** a missing, expired, wrongly signed, wrong-issuer or wrong-audience credential
- **WHEN** the caller requests a protected operation
- **THEN** the service returns 401 and creates no ownership or administrative mutation.

#### Scenario: Client attempts impersonation
- **GIVEN** a verified customer token and a different user's identifier supplied in the request
- **WHEN** the customer attempts to select that identifier as owner
- **THEN** the request is rejected as invalid and the actor cannot be changed from the verified principal.

### Requirement: Stable private account mapping
The system SHALL map a verified issuer/subject pair to one local private account and SHALL preserve that mapping across restarts. New-account creation MUST NOT grant staff roles.

#### Scenario: Repeated authenticated requests
- **WHEN** a previously unseen verified subject accesses the account endpoint repeatedly across restart
- **THEN** exactly one local customer account is used and no administrative capability is granted.

### Requirement: Server-controlled staff capabilities
Source-product ingestion SHALL require catalogue-editor or admin capability; unit issuance/reissue SHALL require inventory-manager or admin capability. Customers MUST NOT grant themselves roles through API inputs or untrusted profile/token attributes. Staff mutations SHALL produce actor-scoped audit records without secrets.

#### Scenario: Customer attempts staff operation
- **GIVEN** a verified customer without staff grants
- **WHEN** that customer attempts product ingestion, unit issuance or key reissue
- **THEN** the operation returns 403 and changes no product, unit or credential state.

#### Scenario: Editor capability is limited
- **GIVEN** a verified catalogue editor without inventory-manager capability
- **WHEN** the editor successfully ingests a product and then attempts unit issuance
- **THEN** ingestion is audited and issuance is denied with 403.

### Requirement: Owner-scoped private reads
Private item lists and detail views SHALL expose only the authenticated actor's items. An inaccessible private item identifier SHALL return the same 404 shape as an absent identifier.

#### Scenario: Cross-account item probe
- **GIVEN** an item owned by customer A
- **WHEN** customer B lists items or requests A's item identifier
- **THEN** the list excludes A's item and the detail request returns 404 without private item metadata.

### Requirement: Test identities are unavailable in deployment mode
Deployment startup SHALL fail if production identity configuration is missing or a fixed/test-principal adapter is selected. Clients MUST NOT enable test identity through headers or query parameters.

#### Scenario: Test adapter selected for deployment
- **WHEN** deployment-mode configuration requests a test identity adapter
- **THEN** startup fails before serving protected requests.
