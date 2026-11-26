// Mirrors the motion custom properties in src/theme/tokens.css. Change both together.
export const dur = {d1: 0.12, d2: 0.18, d3: 0.28, d4: 0.42, d5: 0.64} as const;
export const easeOut = [0.16, 1, 0.3, 1] as const;
export const easeInOut = [0.65, 0, 0.35, 1] as const;

/** Spring presets. `focus` is the selection lift; `snappy` for small controls; `sheet` for overlays. */
export const spring = {
  focus: {type: 'spring', stiffness: 420, damping: 32, mass: 0.8},
  snappy: {type: 'spring', stiffness: 600, damping: 38},
  sheet: {type: 'spring', stiffness: 320, damping: 36},
} as const;

/** The reduced variant of every animation: a short crossfade. */
export const reducedFade = {duration: 0.12, ease: 'linear'} as const;
