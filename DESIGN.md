---
name: Wearhouse
description: A media-console wardrobe in luminous plum; the focused tile repaints the room.
colors:
  plum: "#632947"
  blush: "#f1e0e6"
  paper: "#faf6f3"
  ink: "#2b1624"
  aubergine-top: "#4d1e40"
  aubergine-bottom: "#2a1230"
  surface-0: "#2f1430"
  surface-1: "#3d1937"
  surface-2: "#53213f"
  surface-3: "#6a2c51"
  text: "#ffffff"
  text-2: "#f6dfe7"
  text-3: "#dcb3c6"
  rose-accent: "#e07aa0"
  rose-accent-strong: "#f39bbc"
  ok: "#8ad9b0"
  warn: "#f2c46d"
  danger: "#ff9b9b"
  info: "#a9c8ff"
  light-bg-bottom: "#f4e9ee"
  light-surface-0: "#f6eef1"
  light-surface-1: "#ffffff"
  light-surface-3: "#e8cfd9"
  light-text-2: "#4e2f43"
  light-text-3: "#6f4f62"
  light-accent: "#8e3561"
  light-primary-hover: "#74315a"
  light-ok: "#1f7a4d"
  light-warn: "#8a5a00"
  light-danger: "#b3261e"
  light-info: "#2a5db0"
  thumb: "#ffffff"
  backdrop-dim: "rgba(26, 8, 22, 0.55)"
typography:
  display:
    fontFamily: "Figtree Variable, system-ui, sans-serif"
    fontSize: "clamp(2rem, 4.4vw, 3.4rem)"
    fontWeight: 820
    lineHeight: 1.05
    letterSpacing: "-0.02em"
  headline:
    fontFamily: "Figtree Variable, system-ui, sans-serif"
    fontSize: "2.25rem"
    fontWeight: 820
    lineHeight: 1.1
    letterSpacing: "-0.02em"
  title:
    fontFamily: "Figtree Variable, system-ui, sans-serif"
    fontSize: "1.75rem"
    fontWeight: 820
    lineHeight: 1.12
    letterSpacing: "-0.02em"
  title-sm:
    fontFamily: "Figtree Variable, system-ui, sans-serif"
    fontSize: "1.25rem"
    fontWeight: 720
    lineHeight: 1.3
  body:
    fontFamily: "Figtree Variable, system-ui, sans-serif"
    fontSize: "1.0625rem"
    fontWeight: 420
    lineHeight: 1.5
    fontFeature: "tnum"
  body-sm:
    fontFamily: "Figtree Variable, system-ui, sans-serif"
    fontSize: "0.9375rem"
    fontWeight: 560
    lineHeight: 1.4
  label-caps:
    fontFamily: "Figtree Variable, system-ui, sans-serif"
    fontSize: "0.9375rem"
    fontWeight: 720
    lineHeight: 1.3
    letterSpacing: "0.09em"
  meta:
    fontFamily: "Figtree Variable, system-ui, sans-serif"
    fontSize: "0.8125rem"
    fontWeight: 420
    lineHeight: 1.4
rounded:
  r-1: "6px"
  r-2: "8px"
  r-3: "12px"
  pill: "999px"
spacing:
  s-1: "4px"
  s-2: "8px"
  s-3: "12px"
  s-4: "16px"
  s-5: "24px"
  s-6: "32px"
  s-7: "48px"
  s-8: "64px"
  gutter: "clamp(16px, 3.9vw, 56px)"
  target: "44px"
  hint-bar: "56px"
components:
  button-primary:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.pill}"
    padding: "0 24px"
    height: "44px"
  button-primary-hover:
    backgroundColor: "{colors.text}"
    textColor: "{colors.ink}"
  button-primary-light:
    backgroundColor: "{colors.plum}"
    textColor: "{colors.light-surface-1}"
    rounded: "{rounded.pill}"
  button-primary-light-hover:
    backgroundColor: "{colors.light-primary-hover}"
  button-large:
    rounded: "{rounded.pill}"
    padding: "0 32px"
    height: "52px"
  chip:
    textColor: "{colors.text-2}"
    rounded: "{rounded.pill}"
    padding: "0 16px"
    height: "36px"
  chip-selected:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.pill}"
  tab:
    textColor: "{colors.text-3}"
    typography: "{typography.label-caps}"
    padding: "12px 0"
  tab-active:
    textColor: "{colors.text}"
  input:
    textColor: "{colors.text}"
    rounded: "{rounded.r-2}"
    padding: "0 16px"
    height: "44px"
  tile-media:
    backgroundColor: "{colors.surface-2}"
    rounded: "{rounded.r-2}"
  menu-panel:
    backgroundColor: "{colors.surface-1}"
    rounded: "{rounded.r-3}"
    padding: "8px"
  hint-bar:
    backgroundColor: "{colors.surface-0}"
    textColor: "{colors.text-2}"
    height: "56px"
  keycap:
    backgroundColor: "{colors.text}"
    textColor: "{colors.aubergine-bottom}"
    rounded: "{rounded.r-1}"
    height: "26px"
  tag:
    textColor: "{colors.text-2}"
    rounded: "{rounded.pill}"
    padding: "2px 9px"
---

# Design System: Wearhouse

## Overview

**Creative North Star: "The Plum Console"**

Wearhouse is the media-console home played straight: a Big Picture focus rail, a hero that the focused tile repaints, rail speed from the streaming apps, and retail clarity for garments, sizes and prices. Nothing is a costume or a metaphor; the conventions are the point, and the craft is in how cleanly they are finished. The world is luminous plum, never near-black: a vertical aubergine gradient lit from above, washed by the colour of whatever is selected.

Selection is the signature. One object at a time is "the" object: it lifts, takes a rose ring, dims its neighbours, retitles the detail zone beneath the rail, and (once the selection settles) tints the whole backdrop. Everything else stays quiet so that change reads. Density is console-loose in Focus mode and retail-dense on Desktop; both presentations share one token set, and Focus mode is always the dark world.

The light theme is the same system on paper: paper ground, ink text, plum primary, blush surfaces. It exists for Desktop only.

**Key Characteristics:**
- Luminous aubergine gradient ground (top to bottom, 70% stop), never black.
- Selection = 3px rose ring at 3px gap + lift shadow + spring scale, with neighbours dimmed.
- The backdrop is repainted by the settled selection, not by every keypress.
- Opaque chrome: top bar, hint bar, menus and drawers are solid surfaces.
- One sans (Figtree Variable) carrying everything from 820-weight titles to tracked uppercase tabs.
- Flat 8px tiles in three fixed ratios; authored slot silhouettes as the honest missing-image state.
- Every motion has a reduced variant.

## Colors

A single-family palette: plum and aubergine for ground and surfaces, blush and rose for emphasis, paper as the primary action colour on dark.

### Primary
- **Paper** (paper): the primary button fill on dark, the selected chip, the segmented pill. Paper on plum is the loudest thing on a dark screen and is reserved for the one action that matters.
- **House Plum** (plum): the brand constant; primary action fill, focus ring and strong accent in the light theme.

### Secondary
- **Rose Focus** (rose-accent): the focus ring on dark, tab underline, active nav underline, badges and counts, toggle-on, slider fill, text selection, input caret. It means "here" or "on"; never decoration.
- **Bright Rose** (rose-accent-strong): stronger accent on dark; the warm glow in the Today card.
- **Light Plum Accent** (light-accent): the light theme's accent role.

### Neutral
- **Aubergine Top / Aubergine Bottom** (aubergine-top, aubergine-bottom): the body gradient, 180deg, bottom colour reached at 70% and fixed to the viewport. Aubergine Bottom is also the focus-ring gap colour and keycap ink.
- **Surface 0 to 3** (surface-0 … surface-3): stepped tonal plum. Surface 0 is the hint bar; Surface 1 is menus, drawers, dialogs and cards; Surface 2 is the empty tile; Surface 3 is the high end of the Today card gradient.
- **White / Blush Text / Muted Rose Text** (text, text-2, text-3): primary text, secondary text and meta lines. Muted Rose is the floor for legible text on plum; do not go dimmer.
- **Lines**: white at 14% (hairline) and 32% (strong); in light, ink at 12% and 30%.
- **Thumb** (thumb): the white knob on toggles and sliders in both themes, with the Rest shadow.
- **Backdrop Dim** (backdrop-dim): the plum scrim behind open dialogs.
- **Status** (ok, warn, danger, info and their light counterparts): mint, honey, coral and sky on dark; deepened for contrast on paper. Status colours tint tags at 22–24% mix, never fill large areas.
- **Light theme ground**: paper to light-bg-bottom gradient, light-surface-0 to light-surface-3, ink / light-text-2 / light-text-3 text.

### Named Rules
**The Luminous Plum Rule.** The darkest colour in the dark world is Aubergine Bottom (#2a1230). No near-black grounds, no grey neutrals; every neutral is plum-tinted.

**The Rose Means Here Rule.** Rose marks focus, the active tab or nav item, counts and on-states. If nothing is selected, active or counted, rose is absent.

**The Wash Is Borrowed Rule.** The only colour the backdrop takes beyond plum is the focused item's own tint at 55% in a radial wash; with no tint it falls back to the accent. The page never invents a decorative colour.

**The Data Is Not Palette Rule.** Two hex lists in source are data, not styling, and are not part of this palette: the colour-name approximation table that tints the backdrop wash from a garment's colour name (`accentFor` in the tiles component), and the six avatar preset swatches offered at onboarding (plum, ivory, blush, noir, sage, sky). Do not reuse their values as UI colours.

## Typography

**Display Font:** Figtree Variable (with system-ui, sans-serif)
**Body Font:** Figtree Variable
**Label Font:** Figtree Variable, uppercase and tracked

**Character:** One friendly geometric sans across the whole ramp. Weight does the hierarchy work (420 / 560 / 720 / 820 on the variable axis); headings tighten to -0.02em and balance their wrap; numerals are tabular everywhere so the clock, temperatures and prices never jitter.

### Hierarchy
- **Display** (820, clamp(2rem, 4.4vw, 3.4rem), 1.05): the signed-out or empty-wardrobe home hero headline only.
- **Headline** (820, 2.25rem, 1.1): page titles.
- **Title** (820, 1.75rem, 1.12): the detail-zone title under the rail, state headings, auth card titles. 1.5rem on phones.
- **Title small** (720, 1.25rem): rail titles, the Focus-mode clock, menu entries.
- **Body** (420, 1.0625rem, 1.5): running text and detail meta lines; reading text caps at 60–70ch.
- **Body small** (560–720, 0.9375rem): buttons (720), field labels, tile titles (720, 1.25, two-line clamp).
- **Label caps** (720, 0.9375rem, 0.09em, uppercase): tabs and top-nav links; at 0.8125rem for hint-bar labels and the quick-access section headings.
- **Meta** (420, 0.8125rem): tile meta lines, hints under fields, tag text, credits.

The Today card's oversized temperature numeral (820, clamp(3rem, 7vw, 6rem), 0.9, -0.04em) is a one-off for that card, not a ramp step.

### Named Rules
**The Weight Not Size Rule.** Step hierarchy with weight before size. A new level gets a new weight from the four variable stops, not a new font.

**The Caps Are Navigation Rule.** Uppercase tracked text names places and controls (tabs, nav links, hint labels, short section headings inside a panel). It never sits above a headline as a decorative label.

## Layout

The page is a stack of full-bleed rows inside a fluid gutter (clamp(16px, 3.9vw, 56px)). The shell is a three-row grid: sticky top bar, main, and in Focus mode a fixed 56px hint bar; main pads its bottom by the hint height plus 32px so nothing hides under it.

Rails are horizontal scrollers with proximity snap, 16px gaps (24px for large rails), 22px top / 24px bottom padding so lifted tiles never clip, scroll padding equal to the gutter, hidden scrollbars, and a 48px fade mask on the right edge so the row visibly runs off. Rail tile widths are fluid: portrait clamp(132px, 12vw, 184px), look clamp(150px, 14vw, 210px), wide clamp(260px, 26vw, 380px); the Today card is clamp(280px, 42vw, 640px). Tiles keep a scroll margin that clears the top bar and hint bar.

Under the rail sits the detail zone (min 112px, max 1040px wide): title, meta line, then actions with 12px gaps. Below it, tabs, then the next rail.

Spacing runs on a 4px base (4, 8, 12, 16, 24, 32, 48, 64). Every interactive target is at least 44px.

Breakpoints: at 600px and below the detail zone compacts (title 1.5rem, meta clamped to two lines, actions at 44px), the top bar shortens to 60px with a 28px logo, the clock hides, and rail prev/next buttons hide (touch swipes). At 430px and below a five-item bottom nav replaces the menu button, top nav and hint bar. On coarse-pointer, no-hover devices the hint bar is hidden.

Desktop presentation shows uppercase top-nav links and a smaller clock; Focus presentation hides top nav, shows the menu button and hint bar.

## Elevation & Depth

A hybrid: tonal plum layering for structure, real offset shadows for lift. Shadows are soft, plum-tinted and directional (they fall downward); there is no glow anywhere.

### Shadow Vocabulary
- **Rest** (`--shadow-1`): buttons and tile media at rest.
- **Raised** (`--shadow-2`): hover on tiles and primary buttons; toasts; the auth card.
- **Lift** (`--shadow-lift`): the focused tile, menus, drawers and dialogs.

Each theme defines its own values for all three (plum-black on dark, ink at lower alpha on light).

### Named Rules
**The Opaque Chrome Rule.** The top bar, hint bar, menus, drawers and dialogs are opaque surfaces with no backdrop-filter. Blur over the crossfading backdrop halved the frame rate. The only blur in the chrome is the dialog's own ::backdrop (6px over Backdrop Dim).

**The Lift Is Selection Rule.** The Lift shadow belongs to the selected object and to surfaces stacked above the page. Nothing at rest wears it.

## Shapes

Gently rounded, never sharp and never blobby. Tiles, fields, skeletons, menu rows and toasts use 8px; panels, menus, dialog and sheet tops and cards use 12px; small chrome (logo link, top-nav and tab focus, keycaps) uses 6px. Every button, chip, tag, toggle, segmented control, stepper, avatar button and badge is a full pill. Borders are 1px hairlines in the line colours; the focus ring is the only 3px stroke.

Media is clipped to its radius. Tiles are flat (no border, no frame); the image or silhouette is the surface.

## Components

### Buttons
Confident pills that move a pixel when you reach for them.
- **Shape:** full pill, 44px minimum height (52px large, 48px in the detail zone), 24px side padding (32px large), weight 720.
- **Primary:** paper on dark, plum on light, with the Rest shadow. Hover lifts 1px, brightens to the hover colour and takes the Raised shadow.
- **Secondary:** 8% text-colour tint with a strong hairline; hover 14% and 1px lift.
- **Ghost:** transparent; 9% tint on hover.
- **Danger:** transparent with danger text and a 60% danger hairline.
- **Press:** scale 0.97 over the press duration. **Disabled:** 50% opacity. **Loading / success:** the label hides in place (width is kept) and a spinner or check overlays it.
- **Icon button:** 44px circle, transparent, 10% tint on hover, scale 0.94 on press; badges are rose pills (18px) that pop in.

### Chips, Toggle, Segmented, Tabs
- **Chip:** 36px pill, strong hairline, Blush Text; selected fills with the primary colour.
- **Toggle:** 50×30 pill; on fills rose with a 22px Thumb carrying the Rest shadow.
- **Segmented:** pill track at 8% tint; the selected segment's primary-coloured pill slides between options.
- **Tabs:** uppercase tracked labels in Muted Rose Text, white when active, over a hairline; the active tab carries a 3px rose underline. Counts sit in rose pills.

### Inputs / Fields
- **Style:** 44px, 8px radius, strong hairline, Surface 0 at 70% fill, label above (560), meta hint below.
- **Focus:** border turns to the focus colour with a 3px focus-colour halo at 35% (the only soft ring in the system, inside fields).
- **Error:** danger border and a danger message under the field. Selects carry an inline chevron; sliders fill rose to the value with the Thumb; steppers are pill-bordered with 44px buttons.

### Tags and Labels
Small pills (meta size, 560) at 12% tint; a quiet variant with only a hairline names provenance (Simulated price, Baseline ranking, weather source LIVE / CACHED / MANUAL). Status tags mix ok or warn at 22–24%. The weather chip always names its source and credits BMKG when data is live or cached.

### Tiles (signature)
One link per tile: media and title together; secondary actions live outside it.
- **Ratios:** 2:3 garments, 3:4 looks (collages), 16:9 wide cards.
- **Media:** 8px radius, Surface 2 under the image, Rest shadow; the image is contained, over a blurred cover copy of itself.
- **Text:** title (720, two-line clamp) and one meta line (Muted Rose, single line, ellipsis) below the media.
- **Hover:** 3px up, Raised shadow.
- **Selected:** 6px up and scale 1.04 on a spring, the 3px rose ring at 3px offset on the media (not around the text), Lift shadow; every other tile in that rail dims to brightness 0.78, saturation 0.9. In Focus mode this shows on `:focus`; on Desktop only on `:focus-visible`, so mouse clicks do not paint rings.
- **Reduced motion:** no transform; ring and dim crossfade in 120ms.
- **Missing image:** an authored slot silhouette (top, outer, bottom, dress, footwear, bag, headwear, eyewear, accessory) in a 16% fill with a 2.2 stroke, over a faint diagonal tint, captioned "Image unavailable". Never a broken image, never a generic placeholder.

### Today Card
The rail's first and largest object: a 16:9 card with a Surface 3 to Surface 1 gradient and a glow top-right in the strong accent at 38%. Its backdrop wash is the featured garment's tint, falling back to the accent. The outfit collage fills the right 62%; label, temperature, condition and source chip sit bottom-left. On phones the collage takes the top band and the info sits beneath.

### Rails
Head row with title, optional note and 36px pill prev/next (60% opacity until the rail is hovered or the button focused). Where a tab names the row, the rail's controls sit up on the tab row instead.

### Navigation
- **Top bar:** sticky, 72px, logo left (42px; 28px on phones), icon buttons, clock and avatar pill right. Transparent at the top of the page, solid at 97% top-of-gradient with a hairline once scrolled 96px (scroll-driven, no blur).
- **Top nav (Desktop):** uppercase tracked links in Blush Text; active is white with a 3px rose underline.
- **Main menu / quick access:** opaque Surface 1 drawers sliding from their edges on the sheet spring; menu entries are 56px, title-small weight, with a 4px nudge right on hover or focus. They open on their first entry.
- **Account menu:** 12px-radius Surface 1 popover with the Lift shadow, 44px rows.
- **Bottom nav (phones ≤430px):** five icon-and-label links; active is white with a rose icon.

### Hint Bar (signature)
Fixed 56px footer on Surface 0 with a top hairline. Menu (M) at the left; the focused object's actions, then / Search, Q Quick access and Esc Back at the right. Each hint is a keycap (white, 26px, 6px radius, aubergine glyph) plus an uppercase tracked label. It describes keyboard keys only; there are no gamepad glyphs. Hidden on touch-only devices.

### Overlays
Native modal dialogs: left/right drawers (min(380px, 92vw), full height), centred dialogs (min(560px, 92vw), 12px radius) and bottom sheets (12px top corners), all opaque Surface 1 with a hairline and the Lift shadow. Panels slide from their edge on the sheet spring with a 180ms fade; centred dialogs rise 16px from 0.98 scale.

### Detail Zone
Below the focused rail: title, meta and actions for the current selection. On selection change it slides 8px up with a fade; the outgoing content leaves 4px up.

### Backdrop (signature behaviour)
A fixed layer behind everything: a radial wash in the focused item's tint plus a heavily blurred (16px), 32%-opacity copy of its image, under a vignette that fades into Aubergine Bottom. It repaints only after the selection has rested for 140ms, crossfading over 420ms. Wash layers render at quarter size and are scaled 4x to hold frame budget.

### Toasts and Skeletons
Toasts stack bottom-centre above the hint bar, 8px radius, strong hairline (coloured for error or success), Raised shadow. Skeletons are 8px-radius shimmer blocks in the tile ratios; the shimmer stops under reduced motion.

### Motion
Durations d1 120ms, d2 180ms, d3 280ms, d4 420ms, d5 640ms, plus press (60ms, button press feedback) and three loop durations: spin (900ms, spinner), ring (900ms, the notification bell's single swing) and shimmer (1400ms, skeletons); exponential ease-out for reveals, ease-in-out for symmetric moves; springs for focus (420/32/0.8), small controls (600/38) and sheets (320/36). Every animation has a reduced variant (a short linear crossfade; loops such as shimmer and the bell ring stop), triggered by the OS setting or the account's reduce-motion setting.

## Do's and Don'ts

### Do:
- **Do** keep the dark ground a plum gradient from Aubergine Top to Aubergine Bottom; Focus mode is always dark.
- **Do** mark selection with the 3px rose ring at a 3px gap, the Lift shadow and the focus spring, and dim the selected tile's rail neighbours.
- **Do** let the settled selection repaint the backdrop with its own tint, after 140ms, never per keypress.
- **Do** keep tiles to one link, 8px radius, in 2:3, 3:4 or 16:9.
- **Do** show the authored slot silhouette with "Image unavailable" when an image is missing.
- **Do** make paper-on-plum (dark) or plum-on-paper (light) the one primary action per view.
- **Do** label provenance with quiet tags: simulated prices, baseline ranking, weather source and BMKG credit.
- **Do** give every animation a reduced variant and keep targets at 44px or more.
- **Do** show keyboard keys in the hint bar.

### Don't:
- **Don't** use near-black or grey grounds, gamer neon, or anything dark, murky or heavy.
- **Don't** put backdrop-filter on the top bar, hint bar, menus or drawers; blur belongs only on the dialog's ::backdrop.
- **Don't** use glow for focus or emphasis; depth is downward offset shadow.
- **Don't** paint focus rings on mouse clicks in the Desktop presentation.
- **Don't** recolour or add effects to the Wearhouse mark or wordmark beyond the supplied white and plum versions; the dark theme uses the supplied white lockup.
- **Don't** put uppercase tracked labels above headlines as decoration.
- **Don't** show gamepad button glyphs.
