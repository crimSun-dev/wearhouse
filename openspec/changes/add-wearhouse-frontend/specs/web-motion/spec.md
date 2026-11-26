## Purpose

Defines motion and effects in the Wearhouse app: the selection effect, control states, transitions, in-app scroll animation and signature moments. Each one has a reduced-motion variant and a performance budget.

## ADDED Requirements

### Requirement: Motion system and budget
All motion SHALL use shared duration, easing and spring tokens. Only transform, opacity, clip-path and limited filter SHALL be animated. Animations SHALL be interruptible and SHALL NOT delay input or navigation. Focus navigation SHALL hold a median of at least 55 fps on the documented mid-range laptop profile.

#### Scenario: Navigation not blocked
- **WHEN** a user presses Back while a tile transition is still running
- **THEN** navigation happens immediately and the running animation is cancelled or reversed

### Requirement: Reduced motion
When `prefers-reduced-motion: reduce` is set **or** the `reduce_motion` setting is true, every animation SHALL use its reduced variant: a crossfade of 150 ms or less, or an instant change. Parallax, scale effects, shared-element flights and View Transitions SHALL be disabled. Content and state changes SHALL remain perceivable.

#### Scenario: Setting overrides OS
- **WHEN** the OS has no reduced-motion preference and the user turns `reduce_motion` on
- **THEN** focus moves without scale or lift, and route changes crossfade

### Requirement: Selection effect
The focused tile SHALL scale and lift with a spring and show a crisp focus ring with an offset gap. Its shadow SHALL have real offset and blur; zero-offset neon halos are not allowed. Neighbouring tiles SHALL recede. The rail SHALL scroll with snap so the focused tile stays at the rail's anchor position.

#### Scenario: Focus ring is visible
- **WHEN** a tile receives keyboard focus in either theme
- **THEN** a focus indicator with at least 3:1 contrast against its surroundings is visible

### Requirement: Control state animation
Buttons, icon buttons, chips, toggles, segmented controls, tabs, selects, sliders and steppers SHALL each define rest, hover, focus-visible, pressed, loading, success and disabled states. The loading state SHALL preserve the control's size, so no layout shift occurs. Tabs and segmented controls SHALL move a shared indicator.

#### Scenario: Loading keeps width
- **WHEN** a primary button enters its loading state
- **THEN** its rendered width and height do not change

### Requirement: Transitions and in-app scroll animation
Opening a tile SHALL transition its image into the detail view, and Back SHALL reverse it. Overlays and mobile sheets SHALL enter from their edges, and sheets SHALL dismiss on a drag with velocity. Rails and grids SHALL reveal with a capped stagger as they scroll into view. The top bar SHALL turn from transparent to solid after a small scroll over hero areas. Back navigation SHALL restore the scroll position and focus to the previously opened tile.

#### Scenario: Back restores position
- **WHEN** a user opens the 40th product in a browse grid and presses Back
- **THEN** the grid is at the same scroll position with that tile focused

### Requirement: Signature moments
Six moments SHALL be animated, each tied to a confirmed server result:
1. **Redemption:** the four key groups lock in, the card turns into the garment, and the garment moves into the Wardrobe navigation.
2. **Simulated checkout:** the receipt emerges with a simulated stamp.
3. **Suggestions:** outfit cards deal in, and choosing one folds the rest away.
4. **Equip:** the garment settles onto the avatar slot, with a conflict preview before replacement.
5. **Plan and wear:** a look drops into a planner day, and marking it worn stamps the day.
6. **Friend acceptance:** the acceptance is shown in its notification.

A failed action SHALL NOT play a success animation.

#### Scenario: Failed redemption
- **WHEN** a redemption returns `INVALID_ACTIVATION_CODE`
- **THEN** no unlock animation plays and the generic invalid message is shown
