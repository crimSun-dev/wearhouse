## Purpose

Defines the web avatar used in the fitting room and look views: template-based 3D rendering with accessory positions, a disclosed colour approximation, a 2D fallback, and the frame-rate evidence required by RQ4.

## ADDED Requirements

### Requirement: Non-blocking avatar
The 3D renderer SHALL load lazily after the page is interactive. Selecting, composing and saving looks SHALL work before it loads, without it, and when it fails.

#### Scenario: WebGL unavailable
- **WHEN** the browser has no WebGL
- **THEN** the 2D layered fallback renders the look and the fitting room remains fully usable

### Requirement: Slot templates and accessory positions
Each slot SHALL map to a named template model. Accessory positions (headwear, eyewear, earrings, necklace, scarf, tie, belt, bag, two wrist, two ring) SHALL map to attachment points. Template files SHALL be replaceable by name without code changes. The avatar SHALL support rotate, zoom, equip, remove, and a body option stored as a device preference that is independent of gender identity.

#### Scenario: Two wrist items
- **WHEN** a look has two wrist accessories
- **THEN** both render, one at each wrist attachment point

### Requirement: Disclosed approximation
Garment colour on the avatar SHALL come from the item's colour name through a documented approximation table. Items with unknown colour SHALL use a neutral colour. The interface SHALL state that the avatar is a stylised approximation and SHALL say which mode is active (3D or 2D).

#### Scenario: Mode label
- **WHEN** the avatar falls back to 2D after a model load failure
- **THEN** a visible label states that the 2D view is shown

### Requirement: Frame-rate evidence
A development route SHALL rotate a full look for 60 seconds and record the median FPS and the device. If the median is below 30 FPS, the app SHALL switch to the 2D fallback and say so. The results SHALL be recorded in `docs/architecture/release-evidence-avatar.md`.

#### Scenario: Low frame rate
- **WHEN** the measured median FPS on a device is below 30
- **THEN** the fitting room uses the 2D fallback on that device and discloses it
