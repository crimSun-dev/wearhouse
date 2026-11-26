---
version: 1
slug: "apps-web-client-app"
primary_target: "apps/web/client/app"
related_targets: ["apps/web/client/src"]
---

# Wearhouse app (`/app/`)

**Scope and mode:** the signed-in and signed-out customer app shell plus Home (task group 2 of `add-wearhouse-frontend`), with later groups inheriting it. Mode: Operate, at console craft in Focus mode.

**Audience, job, constraints:** Indonesian Gen Z dressing for Jakarta weather from clothes they own. The job is today's outfit first, then discovery, community and profile. Focus mode is the default on desktop. Mobile gets its own layout. Everything is honest (simulated prices, baseline ranking, BMKG source), and every input (mouse, keyboard, touch) reaches the same actions; no gamepad controls.

**Memorable moment:** moving focus repaints the page. The backdrop, hero art and detail zone follow the focused tile, as on the PS5 and Big Picture homes.

**Unresolved:** real garment imagery is generated placeholders (slot silhouette fallback); the deployment host is not decided.

## Direction contract

THESIS: The category standard, played straight and finished at console craft: Steam Big Picture's focus rail, a PS5-style hero that the focused tile repaints, Netflix/Apple TV rail speed and Zalando/Zara product clarity. It refuses the e-commerce banner-and-grid home and any bespoke metaphor costume.

OWN-WORLD: Luminous plum, never near-black. The ground is a vertical gradient from #4a1d3c to #2a1230, washed by the focused item's tint. Raised surfaces are #5a2448 and #3a1730. Focus is a solid #e07aa0 3px ring with a 3px gap plus a lift shadow with real offset; there is no glow. Text is #ffffff and #f6dfe7. Primary buttons are paper #faf6f3 on plum. Type is Figtree variable, with uppercase tracked tab labels. Tiles are flat with an 8px radius: 2:3 garments and 16:9 heroes. Hints sit in circled glyphs in a footer bar. Desktop light theme: paper #faf6f3, ink #2b1624, plum #632947, blush #f1e0e6.

STORY: The visitor sees today's outfit from their own clothes with the BMKG weather, acts (Wear today, Plan, Try on, Get suggestions), then moves along the rails to the wardrobe, catalogue picks and friends. Every claim is labelled.

FIRST VIEWPORT: Focus Home at 1440×900. The logo is top-left. Top-right: search, notifications with a count, feed, a Jakarta clock and the avatar. Below that, the "Today" rail: the focused 16:9 today card (about 620×350) at the left third, then 2:3 tiles for recent looks and garments, running off the right edge. Under the rail sits the detail zone: the focused title at 28px/800, a meta line, and the primary action button. Below it, the tabs Recently added / Friends / For you, then a peeking row of wide cards. The footer hint bar shows Menu on the left and Enter Select · / Search · M Menu · Esc Back on the right.

FORM: canon (category standard), chosen in safer re-roll round 2 over Night Fitting Room, Evening Vitrines and Show Programme; seed: seed:3f72a0777eebfedb. Signature interaction: selection repaints the page (backdrop crossfade, detail slide 8px with fade, a spring scale on the tile). Motion grammar: springs for focus, exponential ease-out for reveals, overlays sliding from their edges, crossfades only under reduced motion.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
