// Landing page behaviour (task 8.3). Public endpoints only: facets, products, collections, about.
// No authenticated call, no suggestion request. Every live element stays hidden unless its data arrives,
// so an unreachable API leaves a complete page with no error and no numbers.
import './landing.css';

const API = ((import.meta.env.VITE_WEARHOUSE_API_BASE as string | undefined) || 'http://127.0.0.1:8100/api/v2').replace(/\/$/, '');
const origin = new URL(API).origin;

async function get<T>(path: string): Promise<T | null> {
  try {
    const res = await fetch(`${API}${path}`, {headers: {Accept: 'application/json'}, signal: AbortSignal.timeout(8000)});
    return res.ok ? (await res.json()) as T : null;
  } catch { return null; }
}
const show = (el: Element | null) => el?.removeAttribute('hidden');

type Facets = {category: Array<{value: string; count: number}>};
type Browse = {items: Array<{id: string; name: string | null; category: string | null; thumbnail: string | null}>};
type About = {sources?: Array<{name?: string; licence?: string; license?: string; terms_url?: string; url?: string}>};

async function live() {
  const [facets, newest, about] = await Promise.all([
    get<Facets>('/catalogue/facets'), get<Browse>('/catalogue/products?sort=newest&limit=4'), get<About>('/about')]);
  if (facets?.category.length) {
    const products = facets.category.reduce((n, c) => n + c.count, 0);
    document.querySelector('[data-live-products]')!.textContent = String(products);
    document.querySelector('[data-live-categories]')!.textContent = String(facets.category.length);
    show(document.querySelector('[data-live="count"]'));
  }
  const items = newest?.items.filter(i => i.name) ?? [];
  if (items.length) {
    const list = document.querySelector('[data-live="newest"]')!;
    list.replaceChildren(...items.map(i => {
      const li = document.createElement('li');
      const a = document.createElement('a');
      a.href = `${import.meta.env.BASE_URL}app/#/catalogue/products/${i.id}`;
      a.textContent = i.name!;
      const meta = document.createElement('span'); meta.textContent = i.category ?? '';
      li.append(a, meta); return li;
    }));
    show(list);
    // The garment that settles on the wardrobe shelf is a real catalogue piece.
    const piece = items.find(i => i.thumbnail) ?? items[0]!;
    const img = document.querySelector<HTMLImageElement>('[data-live-piece]');
    if (img && piece.thumbnail) { img.src = new URL(piece.thumbnail, origin).href; img.alt = ''; }
    const name = document.querySelector('[data-live-piece-name]');
    if (name) name.textContent = piece.name!;
  }
  const sources = about?.sources?.filter(s => s.name) ?? [];
  if (sources.length) {
    const box = document.querySelector('[data-live="sources"]')!;
    box.querySelector('ul')!.replaceChildren(...sources.map(s => {
      const li = document.createElement('li');
      const link = s.terms_url ?? s.url;
      if (link) { const a = document.createElement('a'); a.href = link; a.textContent = s.name!; li.append(a); } else li.append(s.name!);
      const lic = s.licence ?? s.license;
      if (lic) li.append(`, ${lic}`);
      return li;
    }));
    show(box);
  }
}

/** The folio names the chapter currently on screen. */
function folio() {
  const now = document.querySelector('.folio__now');
  const links = new Map([...document.querySelectorAll<HTMLAnchorElement>('[data-chapter]')].map(a => [a.dataset.chapter!, a]));
  const io = new IntersectionObserver(entries => {
    for (const e of entries) {
      if (!e.isIntersecting) continue;
      const id = e.target.id;
      if (now) now.textContent = (e.target as HTMLElement).dataset.chapterTitle ?? '';
      for (const [key, a] of links) a.toggleAttribute('aria-current', key === id);
    }
  }, {rootMargin: '-45% 0px -50% 0px'});
  document.querySelectorAll('[data-chapter-title]').forEach(s => io.observe(s));
}

folio();
void live();
