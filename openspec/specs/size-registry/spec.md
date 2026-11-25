# size-registry Specification

## Purpose
Commercial clothing sizes as managed objects, and which sizes each product comes in.

## Requirements

### Requirement: Size systems and sizes are managed objects
The API SHALL serve the size registry publicly. It lists the active systems in their configured order, and each system's active sizes in rank order. Staff with `catalogue:ingest` SHALL be able to add or edit a system (label, position, default slots, active) and a size (label, rank, common, active). The seeded systems SHALL be:
- Letter XXS–3XL;
- EU clothing 32–52;
- EU shoe 35–47.

Retiring a size SHALL hide it from pickers and from assignment, while keeping existing references readable. Every change SHALL be audited.

#### Scenario: Staff add a size
- **WHEN** an editor adds `4XL` to the letter system with a rank after `3XL`
- **THEN** the registry lists it last for that system, and customers can filter by it

#### Scenario: Customers cannot edit
- **WHEN** a customer tries to change the registry
- **THEN** they get 403, and nothing changes

### Requirement: Product sizes
Staff SHALL be able to set a product's sizes from exactly one system (replacing the set) or clear them. A product with no sizes SHALL be one-size. "Assign missing" SHALL give each published product without sizes the common active sizes of the active system whose default slots include the product's slot, with origin `rule`. It is bounded per call and reports whether more remain. Product detail SHALL list the sizes in rank order with their origin. Browse cards SHALL show the sizes.

#### Scenario: Rule assignment
- **WHEN** assign-missing runs over a published top and a published pair of shoes
- **THEN** the top gets XS–XXL and the shoes get EU 36–45, both with origin `rule`, and accessories stay one-size

#### Scenario: One system only
- **WHEN** staff set sizes mixing `alpha:M` and `eu_shoe:42`
- **THEN** the request is refused with 422, and the sizes are unchanged
