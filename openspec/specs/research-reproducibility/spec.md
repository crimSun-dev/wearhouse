# research-reproducibility Specification

## Purpose
Makes every research result reproducible and traceable, and makes it impossible to tune on test data.

## Requirements

### Requirement: Dataset manifests gate every run
Each experiment SHALL read its datasets only through a manifest that lists each file's path, sha256, permission basis, acceptance date and the account that accepted it. A run SHALL refuse to start if any file is missing or its checksum differs. Datasets SHALL live in git-ignored folders and SHALL never be committed.

#### Scenario: Modified dataset
- **WHEN** a dataset file's sha256 differs from its manifest
- **THEN** the run stops before computing anything, naming the file

### Requirement: Frozen configs, seeds and provenance
Each run SHALL load a versioned config of hyperparameters, bracketed thesis settings, seeds and split definitions. Each report SHALL record:
- the config hash;
- the dataset hashes;
- the code version (git commit, or a "dirty" flag);
- the library versions;
- the seeds;
- the wall time.

Reports SHALL be written as JSON plus a Markdown summary under `research/reports/<rq>/<run-id>/`.

#### Scenario: Same seed, same numbers
- **WHEN** a pipeline runs twice with the same config, data and seed
- **THEN** every reported metric is identical

### Requirement: No tuning on test data
Every chosen setting (α, λc, λd, w1–w3, h, τ) SHALL be selected on the validation split or the tuning group only. A runner SHALL raise an error if code under selection requests test or reporting-group data. Reports SHALL state which split chose each setting.

#### Scenario: Selection touching test data
- **WHEN** the selection step is given the test split
- **THEN** it raises `TestDataAccess`, and no report is written

### Requirement: Synthetic validation stays separate
Pipelines SHALL be validated on small generated datasets marked `synthetic_only`. Results from synthetic data SHALL never be written to `research/reports/`.

#### Scenario: Synthetic run
- **WHEN** a pipeline test runs on generated data
- **THEN** its output goes to a temporary directory, and the report path rejects datasets marked synthetic
