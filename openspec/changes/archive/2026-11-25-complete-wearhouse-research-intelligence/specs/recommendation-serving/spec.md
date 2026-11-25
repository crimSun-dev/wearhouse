## Purpose

Brings research outputs into the product honestly: served models always say what they are.

## ADDED Requirements

### Requirement: Versioned recommendation artifacts
Staff with `catalogue:ingest` SHALL be able to import a recommendation artifact (via CLI) consisting of:
- a JSON manifest with name, version, mode, model hash, dataset hashes and the report reference;
- item-to-item neighbour lists, or a per-segment ranking.

The sha256 of each artifact file SHALL be verified against the manifest. One artifact per kind SHALL be active. Activation SHALL be audited.

#### Scenario: Tampered artifact
- **WHEN** an artifact file's checksum differs from its manifest
- **THEN** the import is refused, and the active artifact is unchanged

### Requirement: Recommendation endpoints with truthful modes
`GET /catalogue/products/{id}/similar` and `GET /me/recommendations/products` SHALL return published products only. Every response SHALL carry `ModelInfo`. The mode SHALL be `trained` (with artifact hash) only when served from an imported trained artifact. Otherwise it SHALL be `heuristic_baseline`:
- content similarity over published facts for similar items;
- sandbox-order popularity, with a catalogue-recency fallback, for personal recommendations.

Personal recommendations SHALL exclude products the caller already owns.

#### Scenario: No artifact imported
- **WHEN** no trained artifact is active
- **THEN** responses declare `heuristic_baseline` with the baseline name, never `trained`

#### Scenario: Owned products excluded
- **WHEN** a user owns a product
- **THEN** it never appears in their personal recommendations
