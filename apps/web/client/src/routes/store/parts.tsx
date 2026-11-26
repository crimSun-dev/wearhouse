import {useEffect, useRef} from 'react';
import {flushSync} from 'react-dom';
import {useI18n} from '../../i18n/index.tsx';
import {Tile, accentFor} from '../../components/tiles.tsx';
import type {MessageKey} from '../../i18n/en.ts';

export type Card = {id: string; name: string | null; thumbnail: string | null; slot: string | null; colour: string | null; category: string | null};

/** The product whose image is morphing between a tile and the detail hero (a CSS view transition). */
let hero: string | null = null;
const reduced = () => document.documentElement.dataset.motion === 'reduced';

/** Runs a route change inside a view transition when the browser supports it and motion is allowed. */
export function withTransition(productId: string | null, update: () => void | Promise<void>) {
  const start = (document as Document & {startViewTransition?: (cb: () => void | Promise<void>) => {finished: Promise<void>}}).startViewTransition;
  if (!start || reduced()) { void update(); return; }
  hero = productId;
  const transition = start.call(document, async () => { await update(); });
  void transition.finished.finally(() => { hero = null; });
}

/** The product last opened from a grid: its tile takes focus again when the grid is shown on Back. */
let lastOpened: string | null = null;

/** Navigate to a product with the tile image morphing into the detail hero. */
export function openProduct(navigate: (to: string) => void, id: string) {
  lastOpened = id;
  withTransition(id, () => flushSync(() => navigate(`/catalogue/products/${id}`)));
}

export const heroStyle = (id: string) => (hero === id ? {viewTransitionName: 'product-hero'} : undefined);

export function ProductTile({p, onOpen}: {p: Card; onOpen?: (id: string) => void}) {
  const {t} = useI18n();
  const title = p.name ?? p.category ?? '';
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (lastOpened !== p.id) return;
    lastOpened = null;
    // After scroll restoration: refocus without moving the page, unless the tile is off-screen.
    requestAnimationFrame(() => {
      const a = ref.current?.querySelector<HTMLElement>('a');
      if (!a) return;
      a.focus({preventScroll: true});
      const r = a.getBoundingClientRect();
      if (r.bottom < 0 || r.top > innerHeight) a.scrollIntoView({block: 'center'});
    });
  }, [p.id]);
  return <div ref={ref} className="store-tile" style={heroStyle(p.id)} onClickCapture={e => {
    if (!onOpen || e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return;
    e.preventDefault(); onOpen(p.id);
  }}>
    <Tile href={`#/catalogue/products/${p.id}`} title={title} meta={p.category ?? undefined} ratio="portrait" image={p.thumbnail}
      slot={p.slot} descriptor={{id: `product:${p.id}`, meta: p.category ?? undefined, image: p.thumbnail, accent: accentFor(p.colour),
        actions: [{key: 'Enter', label: t('home.viewProduct')}]}} />
  </div>;
}

export function slotLabel(t: (k: MessageKey) => string, slot: string) {
  const key = `slot.${slot}` as MessageKey;
  const text = t(key);
  return text === key ? slot : text;
}

/** Normalises an activation key: any case, dashes or spaces in, XXXX-XXXX-XXXX-XXXX out (16 characters). */
export function normaliseKey(raw: string) {
  const clean = raw.toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 16);
  return {clean, display: clean.replace(/(.{4})(?=.)/g, '$1-')};
}

/** Finds an activation key in scanned text (a bare key, with or without dashes, or inside a link/payload). */
export function keyFrom(text: string): string | null {
  const m = text.toUpperCase().match(/(?:^|[^A-Z0-9])([A-Z2-7]{4})-?([A-Z2-7]{4})-?([A-Z2-7]{4})-?([A-Z2-7]{4})(?![A-Z0-9])/);
  return m ? m.slice(1, 5).join('-') : null;
}

/** Extracts a tag serial from a pasted link (…#/items/<serial>) or a bare serial. */
export function serialFrom(input: string): string | null {
  const text = input.trim();
  const fromLink = text.match(/#\/items\/([A-Za-z0-9_-]{4,64})/);
  if (fromLink) return fromLink[1];
  try { const url = new URL(text); const m = url.pathname.match(/\/items\/([A-Za-z0-9_-]{4,64})/); if (m) return m[1]; } catch { /* not a URL */ }
  return /^[A-Za-z0-9_-]{4,64}$/.test(text) ? text : null;
}

/** In-memory hand-off of a revealed key to the Redeem screen: never the URL, history state or storage. */
let pendingKey: string | null = null;
export function handOffKey(key: string) { pendingKey = key; }
/** Read once: cleared after the current task, so StrictMode's double initialiser call still sees it. */
export function takeKey() { const k = pendingKey; queueMicrotask(() => { pendingKey = null; }); return k; }
