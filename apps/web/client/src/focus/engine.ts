// DOM-first spatial navigation. Zones are rails or grids of real links/buttons marked [data-focus-item].
// One item per zone is tabbable (roving tabindex); arrows move inside a zone and between neighbouring zones,
// and each zone remembers the index it was last left at.
import {dispatchIntent} from './store.ts';
import {playSound} from '../sound/uiSound.ts';

export type ZoneKind = 'rail' | 'grid';
export type Direction = 'left' | 'right' | 'up' | 'down';
type Zone = {el: HTMLElement; kind: ZoneKind; last: number};

const zones = new Set<Zone>();
const byEl = new WeakMap<HTMLElement, Zone>();

export function items(zone: HTMLElement): HTMLElement[] {
  return [...zone.querySelectorAll<HTMLElement>('[data-focus-item]')].filter(el => el.closest('[data-focus-zone]') === zone);
}

export function registerZone(el: HTMLElement, kind: ZoneKind) {
  const zone: Zone = {el, kind, last: 0};
  zones.add(zone);
  byEl.set(el, zone);
  refresh(el);
  return () => { zones.delete(zone); byEl.delete(el); };
}

/** Re-apply the roving tabindex after items change. */
export function refresh(el: HTMLElement) {
  const zone = byEl.get(el);
  if (!zone) return;
  const list = items(el);
  zone.last = Math.min(zone.last, Math.max(0, list.length - 1));
  list.forEach((item, i) => item.setAttribute('tabindex', i === zone.last ? '0' : '-1'));
}

function zoneOf(el: Element | null): Zone | undefined {
  const z = el?.closest<HTMLElement>('[data-focus-zone]');
  return z ? byEl.get(z) : undefined;
}

function center(r: DOMRect) { return {x: r.left + r.width / 2, y: r.top + r.height / 2}; }

/** Columns of a grid, measured from the rendered rows. */
export function columnsOf(list: HTMLElement[]) {
  if (list.length === 0) return 1;
  const top = list[0].offsetTop;
  const n = list.findIndex(el => el.offsetTop !== top);
  return n === -1 ? list.length : n;
}

/** Index movement inside one zone; null when the move leaves the zone. Pure, so it is unit-tested. */
export function stepWithin(kind: ZoneKind, index: number, count: number, columns: number, dir: Direction): number | null {
  if (kind === 'rail') {
    if (dir === 'left') return index > 0 ? index - 1 : null;
    if (dir === 'right') return index < count - 1 ? index + 1 : null;
    return null;
  }
  const col = index % columns;
  if (dir === 'left') return col > 0 ? index - 1 : null;
  if (dir === 'right') return col < columns - 1 && index < count - 1 ? index + 1 : null;
  if (dir === 'up') return index - columns >= 0 ? index - columns : null;
  const next = index + columns;
  if (next < count) return next;
  const lastRowStart = count - (count % columns || columns);
  return index < lastRowStart ? count - 1 : null;
}

function neighbourZone(from: Zone, dir: Direction): Zone | undefined {
  const r = from.el.getBoundingClientRect();
  let best: Zone | undefined;
  let bestDist = Infinity;
  const modal = document.querySelector('dialog[open]');
  for (const z of zones) {
    if (z === from || !z.el.isConnected || items(z.el).length === 0) continue;
    if (modal && !modal.contains(z.el)) continue;   // a modal confines movement to itself
    if (z.el.closest('[inert]')) continue;
    const zr = z.el.getBoundingClientRect();
    if (zr.width === 0 && zr.height === 0) continue;
    let d: number;
    if (dir === 'down') d = zr.top >= r.bottom - 4 ? zr.top - r.bottom : Infinity;
    else if (dir === 'up') d = zr.bottom <= r.top + 4 ? r.top - zr.bottom : Infinity;
    else if (dir === 'right') d = zr.left >= r.right - 4 ? zr.left - r.right + Math.abs(center(zr).y - center(r).y) : Infinity;
    else d = zr.right <= r.left + 4 ? r.left - zr.right + Math.abs(center(zr).y - center(r).y) : Infinity;
    if (d < bestDist) { bestDist = d; best = z; }
  }
  return best;
}

export function focusIndex(zone: HTMLElement, index: number, opts: {reduced?: boolean} = {}) {
  const z = byEl.get(zone);
  const list = items(zone);
  const target = list[index];
  if (!z || !target) return;
  z.last = index;
  list.forEach((item, i) => item.setAttribute('tabindex', i === index ? '0' : '-1'));
  target.focus({preventScroll: true});
  const behavior: ScrollBehavior = opts.reduced ? 'auto' : 'smooth';
  if (z.kind === 'rail') {
    const pad = parseFloat(getComputedStyle(zone).paddingLeft) || 0;
    zone.scrollTo({left: Math.max(0, target.offsetLeft - pad), behavior});
  }
  target.scrollIntoView({block: 'nearest', inline: 'nearest', behavior});
}

/** Big Picture behaviour: a screen opens with its first tile selected, without scrolling the page. */
export function focusFirst(zone: HTMLElement) {
  const active = document.activeElement;
  if (active && active !== document.body && active.id !== 'main') return;   // never steal focus from the user
  const first = items(zone)[0];
  if (!first) return;
  refresh(zone);
  first.focus({preventScroll: true});
}

export function move(dir: Direction, opts: {reduced?: boolean} = {}): boolean {
  const active = document.activeElement as HTMLElement | null;
  const zone = zoneOf(active);
  if (!zone || !active?.hasAttribute('data-focus-item')) return false;
  const list = items(zone.el);
  const index = list.indexOf(active);
  const next = stepWithin(zone.kind, index, list.length, zone.kind === 'grid' ? columnsOf(list) : 1, dir);
  if (next !== null) { focusIndex(zone.el, next, opts); playSound('move'); return true; }
  zone.last = index;
  const target = neighbourZone(zone, dir);
  if (!target) return false;
  const targetItems = items(target.el);
  focusIndex(target.el, Math.min(target.last, targetItems.length - 1), opts);
  playSound('move');
  return true;
}

const keyDir: Record<string, Direction> = {ArrowLeft: 'left', ArrowRight: 'right', ArrowUp: 'up', ArrowDown: 'down'};

function typing(el: Element | null) {
  return !!el && (el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement || el instanceof HTMLSelectElement
    || (el as HTMLElement).isContentEditable);
}

/** Installs the keyboard mapping. Returns a disposer. */
export function installKeyboard(getReduced: () => boolean) {
  const onKey = (e: KeyboardEvent) => {
    if (e.defaultPrevented || e.altKey || e.ctrlKey || e.metaKey) return;
    const dir = keyDir[e.key];
    if (dir && !typing(document.activeElement)) {
      if (move(dir, {reduced: getReduced()})) e.preventDefault();
      return;
    }
    if (typing(document.activeElement)) return;
    if (document.querySelector('dialog[open]')) return;   // a modal handles its own keys (Escape closes it)
    if (e.key === 'Escape') { playSound('back'); dispatchIntent('back'); }
    else if (e.key === '/') { e.preventDefault(); dispatchIntent('search'); }
    else if (e.key === '[') dispatchIntent('tabPrev');
    else if (e.key === ']') dispatchIntent('tabNext');
    else if (e.key === 'm' || e.key === 'M') dispatchIntent('menu');
    else if (e.key === 'q' || e.key === 'Q') dispatchIntent('quick');
  };
  document.addEventListener('keydown', onKey);
  return () => document.removeEventListener('keydown', onKey);
}
