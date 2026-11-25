## Purpose

Lets catalogue staff load many permitted source products at once from the source's own file format. Original data is preserved, row outcomes are reported, and nothing is invented.

## ADDED Requirements

### Requirement: Bulk import jobs over source rows
A catalogue editor SHALL be able to start an import job by supplying, for one source snapshot, all of the following:
- the source record;
- the snapshot checksum;
- a permission record;
- the rows in the source's CSV format.

Each row SHALL be processed independently and recorded with an outcome: `created`, `revised`, `unchanged` or `rejected` with field errors. A rejected row SHALL NOT stop the other rows. The job SHALL report totals and be readable afterwards.

#### Scenario: Mixed valid and invalid rows
- **GIVEN** a CSV with three valid rows and one row missing its product type
- **WHEN** an editor runs the import
- **THEN** three products are created as drafts, one row is `rejected` with a field error, and the job totals report 3 created and 1 rejected

#### Scenario: Re-running the same file
- **WHEN** the same rows are imported again
- **THEN** every row is `unchanged`, and no product or revision is duplicated

#### Scenario: Changed source facts
- **WHEN** a row's product name differs from the product's latest revision
- **THEN** that row is `revised`, and a new immutable draft revision exists while earlier revisions remain

### Requirement: Versioned field mapping that never invents facts
The import SHALL map source columns to verified facts through a named, versioned mapping. Every original field SHALL be kept unchanged. Identifiers SHALL stay strings with their leading zeros. A wardrobe `slot` SHALL be derived only from a documented rule table, recorded as a `rule` annotation with the mapping version. Rows whose type the rule table does not cover SHALL get no slot.

#### Scenario: Unknown garment type
- **WHEN** a row's product group is not in the slot rule table
- **THEN** the product is imported with no slot annotation, rather than with a guessed one

### Requirement: Import requires catalogue capability and bounded input
Only accounts with the catalogue-editor or admin capability SHALL run or read import jobs. Each job SHALL be limited to 5000 rows and 10 MB. Malformed CSV, unknown required columns or an oversized job SHALL be rejected before any row is processed.

#### Scenario: Customer attempts an import
- **WHEN** a customer submits an import job
- **THEN** the service returns 403 and creates no job or product
