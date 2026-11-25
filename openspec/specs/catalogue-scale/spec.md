# catalogue-scale Specification

## Purpose
Keeps the store front fast with the full real catalogue.

## Requirements

### Requirement: Indexed search and filters
Literal substring search over published products SHALL use a trigram index. Category, colour and slot filters SHALL use indexes limited to published products. With 105,542 published products on the reference machine, the median latency SHALL be below 50 ms for both a common term and a term that matches nothing.

#### Scenario: Search at full scale
- **WHEN** a visitor searches "dress" over the full catalogue
- **THEN** the median latency over 20 requests is below 50 ms

### Requirement: Facet caching
Facet counts SHALL be served from a per-process cache with a time-to-live of 60 seconds or less. A publish, retire or import-job publish in the same process SHALL invalidate it. Counts SHALL NOT include drafts or retired products.

#### Scenario: Publish refreshes facets
- **WHEN** an editor publishes a product
- **THEN** the next facets read in that process includes it
