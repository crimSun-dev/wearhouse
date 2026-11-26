import {useEffect, useState, useSyncExternalStore} from 'react';

/** What the focused object tells the page: the backdrop, detail zone and hint bar read it. */
/** A keyboard key shown in the hint bar for the focused object, e.g. {key: 'Enter', label: 'Open'}. */
export type FocusAction = {key: string; label: string};
export type Descriptor = {
  id: string;
  title: string;
  meta?: string;
  /** Tints the backdrop wash; a CSS colour. */
  accent?: string;
  /** Image washed behind the rail; null for silhouette items. */
  image?: string | null;
  actions?: FocusAction[];
};

let current: Descriptor | null = null;
const listeners = new Set<() => void>();

export function publishFocus(d: Descriptor | null) {
  if (d?.id === current?.id && d?.title === current?.title) return;
  current = d;
  for (const l of listeners) l();
}
export function getFocused() { return current; }
export function subscribeFocus(l: () => void) { listeners.add(l); return () => { listeners.delete(l); }; }
export function useFocused(): Descriptor | null {
  return useSyncExternalStore(subscribeFocus, getFocused, () => null);
}

/** App-wide intents; keyboard and gamepad both dispatch them. */
export type Intent = 'back' | 'menu' | 'quick' | 'search' | 'tabPrev' | 'tabNext' | 'actionX' | 'actionY';
export function dispatchIntent(intent: Intent) {
  window.dispatchEvent(new CustomEvent<Intent>('wh:intent', {detail: intent}));
}
export function onIntent(handler: (intent: Intent) => void) {
  const listener = (e: Event) => handler((e as CustomEvent<Intent>).detail);
  window.addEventListener('wh:intent', listener);
  return () => window.removeEventListener('wh:intent', listener);
}

/** The focused descriptor once selection has rested for `delay` ms, so fast scrubbing does not flicker or stack effects. */
export function useSettledFocus(delay = 90): Descriptor | null {
  const [value, setValue] = useState(getFocused);
  useEffect(() => {
    let timer = 0;
    const off = subscribeFocus(() => { clearTimeout(timer); timer = window.setTimeout(() => setValue(getFocused()), delay); });
    return () => { clearTimeout(timer); off(); };
  }, [delay]);
  return value;
}
