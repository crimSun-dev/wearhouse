import {useEffect, useRef, useState, type FormEvent} from 'react';
import {useLocation, useNavigate, useSearchParams} from 'react-router';
import {Search, SlidersHorizontal, X} from 'lucide-react';
import {useI18n} from '../../i18n/index.tsx';
import {useSession} from '../../session/SessionProvider.tsx';
import {useBrowse, useFacets, useSizeRegistry, type BrowseFilters} from '../../data/store.ts';
import {useCollections} from '../../data/queries.ts';
import {Button, Chip, Select, Skeleton, Toggle} from '../../components/ui.tsx';
import {Rail} from '../../components/Rail.tsx';
import {Tile} from '../../components/tiles.tsx';
import {EmptyState, ErrorState} from '../../components/states.tsx';
import {FocusZone, focusItemProps} from '../../focus/FocusZone.tsx';
import {ProductTile, openProduct, slotLabel} from './parts.tsx';
import './store.css';

const KEYS = ['q', 'category', 'colour', 'slot', 'size', 'sort'] as const;

function readFilters(params: URLSearchParams): BrowseFilters {
  const f: BrowseFilters = {};
  for (const k of KEYS) { const v = params.get(k); if (v) (f as Record<string, string>)[k] = v; }
  if (params.get('my_sizes') === '1') f.my_sizes = true;
  if (params.get('hide_owned') === '1') f.hide_owned = true;
  return f;
}

export function CatalogueRoute() {
  const {t} = useI18n();
  const [params, setParams] = useSearchParams();
  const filters = readFilters(params);
  const browsing = params.has('all') || Object.keys(filters).length > 0;
  const set = (key: string, value: string | null) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value); else next.delete(key);
    if (!next.toString()) next.set('all', '1');
    setParams(next, {replace: true});
  };
  const clear = () => setParams(new URLSearchParams({all: '1'}), {replace: true});
  return <div className="page store">
    <header className="store-head">
      <h1>{t('cat.title')}</h1>
      <SearchForm initial={filters.q ?? ''} onSearch={q => set('q', q || null)} />
    </header>
    <FilterBar filters={filters} set={set} clear={clear} browsing={browsing} onFront={() => setParams(new URLSearchParams(), {replace: true})} />
    {browsing ? <BrowseGrid filters={filters} onClear={clear} /> : <Front onCategory={c => set('category', c)} />}
  </div>;
}

function SearchForm({initial, onSearch}: {initial: string; onSearch: (q: string) => void}) {
  const {t} = useI18n();
  const [q, setQ] = useState(initial);
  const input = useRef<HTMLInputElement>(null);
  const location = useLocation();
  useEffect(() => setQ(initial), [initial]);
  useEffect(() => { if ((location.state as {search?: boolean} | null)?.search) input.current?.focus(); }, [location.state]);
  const submit = (e: FormEvent) => { e.preventDefault(); onSearch(q.trim()); };
  return <form role="search" className="store-search" onSubmit={submit}>
    <Search size={18} aria-hidden />
    <input ref={input} type="search" aria-label={t('cat.search')} placeholder={t('cat.searchPlaceholder')} value={q} maxLength={100}
      onChange={e => setQ(e.target.value)} />
    {q && <button type="button" className="store-search-clear" aria-label={t('cat.clear')} onClick={() => { setQ(''); onSearch(''); }}><X size={16} /></button>}
  </form>;
}

/** The contextual sub-bar (Steam Store style): every filter lives in the route, so a view can be shared and restored. */
function FilterBar({filters, set, clear, browsing, onFront}: {
  filters: BrowseFilters; set: (k: string, v: string | null) => void; clear: () => void; browsing: boolean; onFront: () => void;
}) {
  const {t} = useI18n();
  const {status} = useSession();
  const facets = useFacets();
  const registry = useSizeRegistry();
  const active = Object.keys(filters).filter(k => k !== 'sort' && k !== 'q').length;
  const [open, setOpen] = useState(false);
  return <div className={`store-filters ${open ? 'is-open' : ''}`} role="group" aria-label={t('cat.filters')}>
    <Button className="store-filters-toggle" aria-expanded={open} onClick={() => setOpen(o => !o)}>
      <SlidersHorizontal size={18} aria-hidden /> {t('cat.filters')}{active > 0 ? ` (${active})` : ''}</Button>
    <Select label={t('cat.category')} value={filters.category ?? ''} onChange={e => set('category', e.target.value || null)}>
      <option value="">{t('cat.any')}</option>
      {facets.data?.category.map(f => <option key={f.value} value={f.value}>{f.value} ({f.count})</option>)}
    </Select>
    <Select label={t('cat.colour')} value={filters.colour ?? ''} onChange={e => set('colour', e.target.value || null)}>
      <option value="">{t('cat.any')}</option>
      {facets.data?.colour.map(f => <option key={f.value} value={f.value}>{f.value} ({f.count})</option>)}
    </Select>
    <Select label={t('cat.slot')} value={filters.slot ?? ''} onChange={e => set('slot', e.target.value || null)}>
      <option value="">{t('cat.any')}</option>
      {facets.data?.slot.map(f => <option key={f.value} value={f.value}>{slotLabel(t, f.value)} ({f.count})</option>)}
    </Select>
    <Select label={t('cat.size')} value={filters.size ?? ''} onChange={e => set('size', e.target.value || null)}>
      <option value="">{t('cat.any')}</option>
      {registry.data?.systems.filter(s => s.active !== false).map(s => <optgroup key={s.code} label={s.label}>
        {s.sizes.filter(z => z.active !== false).map(z => <option key={z.code} value={`${s.code}:${z.code}`}>{z.label}</option>)}
      </optgroup>)}
    </Select>
    <Select label={t('cat.sort')} value={filters.sort ?? 'newest'} onChange={e => set('sort', e.target.value === 'newest' ? null : e.target.value)}>
      <option value="newest">{t('cat.sortNewest')}</option>
      <option value="name">{t('cat.sortName')}</option>
    </Select>
    {status === 'ready' && <div className="store-toggles">
      <Toggle label={t('cat.mySizes')} checked={!!filters.my_sizes} onChange={on => set('my_sizes', on ? '1' : null)} />
      <Toggle label={t('cat.hideOwned')} checked={!!filters.hide_owned} onChange={on => set('hide_owned', on ? '1' : null)} />
    </div>}
    <div className="store-filter-actions">
      {active > 0 && <Button variant="ghost" onClick={clear}>{t('cat.clear')}</Button>}
      {browsing && <Button variant="ghost" onClick={onFront}>{t('cat.backToFront')}</Button>}
    </div>
  </div>;
}

function Front({onCategory}: {onCategory: (c: string) => void}) {
  const {t} = useI18n();
  const collections = useCollections();
  const facets = useFacets();
  return <>
    {collections.isError ? <ErrorState error={collections.error} onRetry={() => collections.refetch()} />
      : !!collections.data?.length && <Rail title={t('home.featured')} version={collections.data.length} autoFocus>
        {collections.data.map(c => <Tile key={c.slug} href={`#/collections/${c.slug}`} title={c.title}
          meta={t('coll.pieces', {n: c.items.length})} ratio="wide" image={c.items[0]?.thumbnail} slot={c.items[0]?.slot}
          descriptor={{id: `collection:${c.slug}`, image: c.items[0]?.thumbnail, actions: [{key: 'Enter', label: t('hint.open')}]}} />)}
      </Rail>}
    {!!facets.data?.category.length && <section className="store-section">
      <h2>{t('cat.categories')}</h2>
      <FocusZone kind="rail" label={t('cat.categories')} className="store-chips" version={facets.data.category.length}>
        {facets.data.category.map(f => <Chip key={f.value} {...focusItemProps({id: `category:${f.value}`, title: f.value,
          meta: t('cat.products', {n: f.count}), actions: [{key: 'Enter', label: t('hint.open')}]})}
          onClick={() => onCategory(f.value)}>{f.value} <span className="muted">{f.count}</span></Chip>)}
      </FocusZone>
    </section>}
    <section className="store-section">
      <h2>{t('cat.newest')}</h2>
      <BrowseGrid filters={{sort: 'newest'}} />
    </section>
  </>;
}

function BrowseGrid({filters, onClear}: {filters: BrowseFilters; onClear?: () => void}) {
  const {t} = useI18n();
  const navigate = useNavigate();
  const browse = useBrowse(filters);
  const sentinel = useRef<HTMLDivElement>(null);
  const items = browse.data?.pages.flatMap(p => p.items) ?? [];
  const {hasNextPage, isFetchingNextPage, fetchNextPage} = browse;
  useEffect(() => {
    const el = sentinel.current;
    if (!el || !hasNextPage) return;
    const io = new IntersectionObserver(entries => { if (entries[0]?.isIntersecting && !isFetchingNextPage) void fetchNextPage(); },
      {rootMargin: '600px 0px'});
    io.observe(el);
    return () => io.disconnect();
  }, [hasNextPage, isFetchingNextPage, fetchNextPage]);
  if (browse.isPending) return <div className="store-grid" aria-busy="true">{Array.from({length: 8}, (_, i) => <Skeleton key={i} />)}</div>;
  if (browse.isError) return <ErrorState error={browse.error} onRetry={() => browse.refetch()} />;
  if (!items.length) return <EmptyState title={t('cat.emptyTitle')} body={t('cat.emptyBody')}>
    {onClear && <Button variant="primary" onClick={onClear}>{t('cat.clear')}</Button>}
  </EmptyState>;
  return <>
    <p className="muted small" aria-live="polite">{t('cat.results', {n: items.length})}</p>
    <FocusZone kind="grid" label={t('cat.all')} className="store-grid" version={items.length}>
      {items.map(p => <ProductTile key={p.id} p={p} onOpen={id => openProduct(navigate, id)} />)}
    </FocusZone>
    <div ref={sentinel} className="store-more">
      {hasNextPage ? <Button loading={isFetchingNextPage} onClick={() => void fetchNextPage()}>{t('cat.loadMore')}</Button>
        : <p className="muted small">{t('cat.end')}</p>}
    </div>
  </>;
}
