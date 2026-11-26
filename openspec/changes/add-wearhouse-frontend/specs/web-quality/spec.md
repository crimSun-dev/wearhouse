## Purpose

Defines the release bars for the Wearhouse web frontend: accessibility, responsive layouts, performance, visual regression, and the end-to-end acceptance flows that prove the ecosystem works through the interface.

## ADDED Requirements

### Requirement: Accessibility
Every route SHALL meet WCAG 2.2 AA. Specifically:
- automated axe checks report no serious or critical violations;
- targets are at least 44 px;
- labels are persistent;
- validation and results are announced;
- modal focus returns to the opener;
- badges, swatches, weather chips and the avatar have meaningful text alternatives;
- the layout is usable at 200% zoom;
- each primary flow completes with keyboard only.

#### Scenario: Keyboard-only purchase and redeem
- **WHEN** a tester uses only the keyboard
- **THEN** they can browse, add to cart, check out, reveal the key and redeem it

### Requirement: Responsive layouts
Every route SHALL be usable without horizontal page scrolling at 360, 390, 768, 1440 and 1920 px wide. Layout rules:
- 360–430 px: two-column tiles and bottom navigation;
- tablet: a drawer replaces the sidebar;
- desktop: a sidebar and 5–6 portrait columns.

The planner SHALL become a date strip and a single-day editor on phones.

#### Scenario: Phone planner
- **WHEN** the planner is opened at 390 px
- **THEN** a date strip and one day's editor are shown, and no seven-column form

### Requirement: Performance budgets
Under the documented mobile test profile:
- the app and landing page SHALL have LCP ≤ 2.5 s and CLS ≤ 0.1;
- interactions SHALL have INP ≤ 200 ms;
- skeletons SHALL keep tile dimensions;
- the avatar and staff workspace SHALL be in separate lazy chunks, and CI SHALL fail when the shell chunk exceeds its recorded size budget.

#### Scenario: Shell budget
- **WHEN** a dependency pushes the shell chunk over its budget
- **THEN** the CI size check fails

### Requirement: Visual regression
Snapshots SHALL cover every primary route at the five widths, in the Desktop and Focus presentations, in the dark and light themes, with reduced motion enabled for stability. Snapshot changes SHALL require review.

#### Scenario: Unreviewed visual change
- **WHEN** a change alters a snapshotted screen
- **THEN** the visual test fails until the snapshot is updated deliberately

### Requirement: End-to-end ecosystem acceptance
An automated two-user test against the v2 test harness SHALL complete through the UI:
1. staff publishes a product and sets an offer;
2. user A wishlists it, adds it to the cart, checks out, reveals the key and redeems it;
3. user B cannot redeem the same key or open A's item;
4. A saves a look, gets suggestions and chooses one, plans the week, marks a day worn and shares the look with friends;
5. B sends a friend request, A accepts it, and B sees the share and A's week;
6. A blocks B, and B loses access.

The run SHALL produce no console errors.

#### Scenario: Full ecosystem path
- **WHEN** the e2e suite runs against a fresh harness database
- **THEN** every step above passes and the browser console has no errors
