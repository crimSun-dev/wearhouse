## Purpose

Defines the public scroll-driven landing page that introduces Wearhouse and hands visitors into the app. It covers what the page may show, which data it may fetch, and how it must behave without motion or JavaScript.

## ADDED Requirements

### Requirement: Story and calls to action
The landing page at `/` SHALL tell the journey recorded in the saved brief:
1. library;
2. store with simulated prices;
3. private key;
4. the key becomes the garment;
5. the wardrobe opens;
6. weather with an honest forecast horizon;
7. the week;
8. friends.

The wardrobe reveal SHALL be the single largest moment. The page SHALL offer "Open Wearhouse" (`/app/#/`) and "Browse the catalogue" (`/app/#/catalogue`). Any example activation key SHALL be visibly labelled as an example.

#### Scenario: Calls to action reachable
- **WHEN** a keyboard user tabs through the landing page
- **THEN** both calls to action are reachable and open the app routes

### Requirement: Honest public data
The landing page SHALL fetch only public endpoints: collections, products, facets and about. It SHALL make no authenticated call and no suggestion request. Counts SHALL come only from live facet data; when that data is unavailable, no number SHALL be shown. Sources and the AI disclosure from `/about` SHALL appear in the footer when available. Imagery SHALL be generated or supplied brand art, with synthetic people only, no third-party logos and no text baked into images. The owner's mock screenshots SHALL NOT be presented as the product.

#### Scenario: API unreachable
- **WHEN** the API is down while the landing page loads
- **THEN** the page renders fully without live tiles or counts and shows no error

### Requirement: Resilient presentation
The landing page SHALL:
- have a separate mobile composition;
- have a reduced-motion version built from static frames;
- remain readable with JavaScript disabled;
- use semantic headings and links;
- avoid layout shift (CLS ≤ 0.1);
- lazy-load assets below the fold.

#### Scenario: Reduced motion landing
- **WHEN** the page is viewed with reduced motion
- **THEN** every scene is shown as a static composition, the story remains complete, and nothing scrubs or moves with scroll
