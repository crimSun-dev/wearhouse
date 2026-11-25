# sandbox-revocation Specification

## Purpose
Sandbox cancellation after a claim (TDD §10.2).

## Requirements

### Requirement: Cancelling revokes sandbox entitlements
Cancelling a fulfilled sandbox order SHALL succeed whether or not its units were claimed. In one transaction:
- unclaimed units SHALL be retired and their keys revoked;
- claimed items SHALL be marked `revoked_sandbox`, with an ownership event and an audit entry;
- stock SHALL be restored.

Revoked items SHALL leave the wardrobe inventory, look validation and suggestions. They SHALL show their revoked state in the private item view, and their unit SHALL never be claimable again.

#### Scenario: Cancel after claim
- **WHEN** a buyer claims one of two units and then cancels the order
- **THEN** the order is cancelled, the claimed item shows `revoked_sandbox` and is gone from the wardrobe, the other key no longer works, and stock is back
