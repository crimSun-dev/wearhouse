import {useMemo, useState, type FormEvent} from 'react';
import {Link, useNavigate, useSearchParams} from 'react-router';
import {ArrowDown, ArrowUp, GripVertical, Plus, Settings2, Trash2, X} from 'lucide-react';
import {useI18n} from '../../i18n/index.tsx';
import {useSession} from '../../session/SessionProvider.tsx';
import {useSettings} from '../../settings/SettingsProvider.tsx';
import {ApiFailure} from '../../api/index.ts';
import {useItems, useRefresh, useRegistry, useShelves, type Item, type Shelf} from '../../data/wardrobe.ts';
import {useSizeRegistry} from '../../data/store.ts';
import {Button, Segmented, Select, Skeleton, TextField, Toggle} from '../../components/ui.tsx';
import {Overlay} from '../../components/Overlay.tsx';
import {EmptyState, ErrorState} from '../../components/states.tsx';
import {toast} from '../../components/toast.tsx';
import {FocusZone, focusItemProps} from '../../focus/FocusZone.tsx';
import {ItemImage} from '../../components/ItemImage.tsx';
import {ALL_SLOTS, ItemTile, WardrobeNav, itemTitle, useFail, useLabels} from './shared.tsx';

type View = 'grid' | 'list' | 'outfit';
const ZONES: Array<[string, string[]]> = [
  ['head', ['headwear', 'eyewear', 'earrings', 'necklace', 'scarf', 'tie']], ['body', ['outer', 'top', 'dress']],
  ['legs', ['bottom', 'belt']], ['feet', ['footwear']], ['extras', ['bag', 'wrist', 'ring', 'accessory']],
];

export function LibraryRoute() {
  const {t} = useI18n();
  const labels = useLabels();
  const navigate = useNavigate();
  const {values, update} = useSettings();
  const [params, setParams] = useSearchParams();
  const filters = {slot: params.get('slot') ?? '', care_state: params.get('care') ?? '', shelf_id: params.get('shelf') ?? '',
    size: params.get('size') ?? '', sort: params.get('sort') ?? ''};
  const items = useItems(filters);
  const all = useItems();
  const shelves = useShelves();
  const registry = useRegistry();
  const sizes = useSizeRegistry();
  const [text, setText] = useState('');
  const [archived, setArchived] = useState(false);
  const [managing, setManaging] = useState<Shelf | 'new' | null>(null);
  const view = ((values.wardrobe_view as View | undefined) ?? 'grid');
  const grouped = values.wardrobe_group_by_slot !== false;
  const set = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value); else next.delete(key);
    setParams(next, {replace: true});
  };
  const shown = useMemo(() => {
    const q = text.trim().toLowerCase();
    return (items.data?.items ?? []).filter(i => (archived || !i.archived) && (!q || `${i.name ?? ''} ${i.category ?? ''} ${i.colour ?? ''}`.toLowerCase().includes(q)));
  }, [items.data, text, archived]);
  const total = (all.data?.items ?? []).filter(i => !i.archived).length;
  const counts = useMemo(() => {
    const c: Record<string, number> = {};
    for (const i of all.data?.items ?? []) if (!i.archived) c[i.slot_source === 'unknown' ? 'unknown' : i.slot] = (c[i.slot_source === 'unknown' ? 'unknown' : i.slot] ?? 0) + 1;
    return c;
  }, [all.data]);

  if (all.isSuccess && total === 0 && !all.data.items.length) return <div className="page wr">
    <WardrobeNav />
    <EmptyState title={t('wr.emptyTitle')} body={t('wr.emptyBody')}>
      <Button variant="primary" onClick={() => navigate('/redeem')}>{t('wr.redeem')}</Button>
      <Button onClick={() => navigate('/wardrobe/add')}>{t('wr.add')}</Button>
      <Link className="btn btn-ghost btn-md" to="/catalogue">{t('wr.browse')}</Link>
    </EmptyState>
  </div>;

  const slotList = (registry.data?.slots.map(s => s.slot) ?? [...ALL_SLOTS]).filter(s => counts[s]);
  return <div className="page wr wr-library">
    <WardrobeNav />
    <div className="wr-layout">
      <aside className="wr-side" aria-label={t('wr.slots')}>
        <FocusZone kind="grid" label={t('wr.slots')} className="wr-side-list" version={slotList.length + (shelves.data?.length ?? 0)}>
          <button type="button" className={`wr-side-link ${!filters.slot && !filters.shelf_id ? 'is-active' : ''}`}
            {...focusItemProps({id: 'side:all', title: t('wr.allItems')})} onClick={() => setParams(new URLSearchParams(), {replace: true})}>
            <span>{t('wr.allItems')}</span><span className="count">{total}</span></button>
          {slotList.map(s => <button key={s} type="button" className={`wr-side-link ${filters.slot === s ? 'is-active' : ''}`}
            {...focusItemProps({id: `side:${s}`, title: labels.slot(s)})} onClick={() => set('slot', filters.slot === s ? '' : s)}>
            <span>{labels.slot(s)}</span><span className="count">{counts[s]}</span></button>)}
          {counts.unknown ? <span className="wr-side-link is-static"><span>{t('wslot.unknown')}</span><span className="count">{counts.unknown}</span></span> : null}
          <h2 className="wr-side-head">{t('sh.title')}</h2>
          {shelves.data?.map(s => <div key={s.id} className="wr-side-row">
            <button type="button" className={`wr-side-link ${filters.shelf_id === s.id ? 'is-active' : ''}`}
              {...focusItemProps({id: `shelf:${s.id}`, title: s.name})} onClick={() => set('shelf', filters.shelf_id === s.id ? '' : s.id)}>
              <span>{s.name}</span><span className="count">{s.count}</span></button>
            <button type="button" className="wr-side-icon" aria-label={`${t('sh.manage')}: ${s.name}`} onClick={() => setManaging(s)}><Settings2 size={16} /></button>
          </div>)}
          <button type="button" className="wr-side-link wr-side-new" onClick={() => setManaging('new')}><Plus size={16} aria-hidden /> {t('sh.new')}</button>
        </FocusZone>
      </aside>
      <section className="wr-main">
        <div className="wr-toolbar">
          <TextField label={t('wr.filter')} value={text} onChange={e => setText(e.target.value)} type="search" />
          <Select label={t('wr.care')} value={filters.care_state} onChange={e => set('care', e.target.value)}>
            <option value="">{t('wr.any')}</option>{['ready', 'laundry', 'repair', 'stored'].map(c => <option key={c} value={c}>{labels.care(c)}</option>)}
          </Select>
          <Select label={t('wr.size')} value={filters.size} onChange={e => set('size', e.target.value)}>
            <option value="">{t('wr.any')}</option>
            {sizes.data?.systems.map(s => <optgroup key={s.code} label={s.label}>{s.sizes.map(z => <option key={z.code} value={`${s.code}:${z.code}`}>{z.label}</option>)}</optgroup>)}
          </Select>
          <Select label={t('wr.sort')} value={filters.sort} onChange={e => set('sort', e.target.value)}>
            <option value="">{t('wr.sortRecent')}</option><option value="name">{t('wr.sortName')}</option>
            <option value="worn">{t('wr.sortWear')}</option><option value="size">{t('wr.sortSize')}</option>
          </Select>
          <Segmented label={t('wr.views')} value={view} onChange={v => void update({wardrobe_view: v})}
            options={[{value: 'grid', label: t('wr.grid')}, {value: 'list', label: t('wr.list')}, {value: 'outfit', label: t('wr.outfit')}]} />
          <div className="wr-toolbar-toggles">
            <Toggle label={t('wr.groupBySlot')} checked={grouped} onChange={on => void update({wardrobe_group_by_slot: on})} />
            <Toggle label={t('wr.showArchived')} checked={archived} onChange={setArchived} />
          </div>
          <Button variant="primary" onClick={() => navigate('/wardrobe/add')}><Plus size={18} aria-hidden /> {t('wr.add')}</Button>
        </div>
        {items.isPending ? <div className="wr-grid">{Array.from({length: 8}, (_, i) => <Skeleton key={i} />)}</div>
          : items.isError ? <ErrorState error={items.error} onRetry={() => items.refetch()} />
          : !shown.length ? <EmptyState title={t('wr.noMatch')}><Button onClick={() => { setText(''); setParams(new URLSearchParams(), {replace: true}); }}>{t('wr.clear')}</Button></EmptyState>
          : <Items items={shown} view={view} grouped={grouped} />}
      </section>
    </div>
    <footer className="wr-status" role="status">{t('wr.shown', {n: shown.length, total})}</footer>
    {managing && <ShelfManager shelf={managing === 'new' ? null : managing} items={all.data?.items ?? []} onClose={() => setManaging(null)} />}
  </div>;
}

function Items({items, view, grouped}: {items: Item[]; view: View; grouped: boolean}) {
  const {t} = useI18n();
  const labels = useLabels();
  if (view === 'outfit') return <div className="wr-outfit" data-view="outfit">
    {ZONES.map(([zone, slots]) => {
      const inZone = items.filter(i => slots.includes(i.slot));
      return inZone.length ? <FocusZone key={zone} kind="rail" label={zone} className="wr-zone">
        {inZone.map(i => <ItemTile key={i.id} item={i} />)}</FocusZone> : null;
    })}
  </div>;
  const groups: Array<[string, Item[]]> = grouped
    ? [...new Set(items.map(i => (i.slot_source === 'unknown' ? 'unknown' : i.slot)))].map(s => [s, items.filter(i => (i.slot_source === 'unknown' ? 'unknown' : i.slot) === s)])
    : [['', items]];
  return <div data-view={view}>{groups.map(([slot, list]) => <section key={slot || 'all'} className="wr-group">
    {slot && <h2>{slot === 'unknown' ? t('wslot.unknown') : labels.slot(slot)} <span className="muted small">{list.length}</span></h2>}
    {view === 'grid' ? <FocusZone kind="grid" label={slot || t('wr.allItems')} className="wr-grid" version={list.length}>
      {list.map(i => <ItemTile key={i.id} item={i} />)}</FocusZone>
      : <FocusZone kind="grid" label={slot || t('wr.allItems')} className="wr-list" version={list.length}>
        {list.map(i => <ListRow key={i.id} item={i} />)}</FocusZone>}
  </section>)}</div>;
}

function ListRow({item}: {item: Item}) {
  const {t, date} = useI18n();
  const labels = useLabels();
  return <Link to={`/wardrobe/items/${item.id}`} className={`wr-row ${item.archived ? 'is-archived' : ''}`} {...focusItemProps({id: `item:${item.id}`, title: itemTitle(item)})}>
    <span className="wr-row-img"><ItemImage item={item} quiet /></span>
    <span className="wr-row-name">{itemTitle(item)}<span className="muted small">{[item.category, item.colour].filter(Boolean).join(' · ')}</span></span>
    <span>{labels.slot(item.slot_source === 'unknown' ? null : item.slot)}</span>
    <span>{labels.care(item.care_state)}</span>
    <span>{item.size?.label ?? '—'}</span>
    <span>{item.wear_count ? t('wr.worn', {n: item.wear_count}) : t('wr.neverWorn')}{item.last_worn_on && <span className="muted small"> · {date(item.last_worn_on)}</span>}</span>
    <span className={`tag ${item.verified ? 'tag-ok' : 'tag-quiet'}`}>{item.verified ? t('wr.verified') : t('wr.declared')}</span>
  </Link>;
}

/** Create, rename, reorder (drag or Alt+arrow keys) and delete a shelf. */
function ShelfManager({shelf, items, onClose}: {shelf: Shelf | null; items: Item[]; onClose: () => void}) {
  const {t, errorText} = useI18n();
  const {api} = useSession();
  const refresh = useRefresh();
  const fail = useFail();
  const [name, setName] = useState(shelf?.name ?? '');
  const [order, setOrder] = useState<string[]>(shelf?.item_ids ?? []);
  const [busy, setBusy] = useState(false);
  const [dragging, setDragging] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const byId = new Map(items.map(i => [i.id, i]));
  const move = (id: string, delta: number) => setOrder(o => {
    const i = o.indexOf(id); const j = i + delta;
    if (i < 0 || j < 0 || j >= o.length) return o;
    const next = [...o]; [next[i], next[j]] = [next[j]!, next[i]!]; return next;
  });
  const save = async (e?: FormEvent) => {
    e?.preventDefault(); setBusy(true); setError(null);
    try {
      if (shelf) await api.call('patch', '/api/v2/me/wardrobe/shelves/{shelf_id}', {path: {shelf_id: shelf.id}, body: {name: name.trim(), item_ids: order}});
      else await api.call('post', '/api/v2/me/wardrobe/shelves', {body: {name: name.trim(), item_ids: order}});
      await refresh('shelves', 'wardrobe-items'); toast(t('it.saved'), 'success'); onClose();
    } catch (err) {
      if (err instanceof ApiFailure && err.code === 'SHELF_NAME_TAKEN') setError(errorText(err.code, err.message)); else fail(err);
    } finally { setBusy(false); }
  };
  const remove = async () => {
    if (!shelf) return;
    setBusy(true);
    try { await api.call('delete', '/api/v2/me/wardrobe/shelves/{shelf_id}', {path: {shelf_id: shelf.id}}); await refresh('shelves'); toast(t('sh.deleted')); onClose(); }
    catch (err) { fail(err); } finally { setBusy(false); }
  };
  const available = items.filter(i => !order.includes(i.id) && !i.archived);
  return <Overlay open onClose={onClose} side="right" title={shelf ? t('sh.manage') : t('sh.new')}>
    <form className="wr-panel" onSubmit={e => void save(e)}>
      <h2>{shelf ? t('sh.manage') : t('sh.new')}</h2>
      <TextField label={t('sh.name')} value={name} required maxLength={60} onChange={e => setName(e.target.value)} error={error ?? undefined} data-autofocus />
      <h3>{t('sh.items')}</h3>
      <p className="muted small">{t('sh.reorderHint')}</p>
      {!order.length ? <p className="muted">{t('sh.empty')}</p> : <ol className="shelf-order">
        {order.map((id, idx) => <li key={id} draggable className={dragging === id ? 'is-dragging' : ''}
          onDragStart={() => setDragging(id)} onDragEnd={() => setDragging(null)}
          onDragOver={e => { e.preventDefault(); if (dragging && dragging !== id) setOrder(o => { const f = o.indexOf(dragging); const to = o.indexOf(id); const n = [...o]; n.splice(f, 1); n.splice(to, 0, dragging); return n; }); }}>
          <GripVertical size={16} aria-hidden className="grip" />
          <button type="button" className="shelf-item" aria-label={`${byId.get(id) ? itemTitle(byId.get(id)!) : id}, ${idx + 1} / ${order.length}`}
            onKeyDown={e => { if (e.altKey && (e.key === 'ArrowUp' || e.key === 'ArrowDown')) { e.preventDefault(); e.stopPropagation(); move(id, e.key === 'ArrowUp' ? -1 : 1);
              requestAnimationFrame(() => (e.target as HTMLElement).focus()); } }}>
            {byId.get(id) ? itemTitle(byId.get(id)!) : id}</button>
          <span className="shelf-actions">
            <button type="button" aria-label={t('sh.moveUp')} disabled={idx === 0} onClick={() => move(id, -1)}><ArrowUp size={16} /></button>
            <button type="button" aria-label={t('sh.moveDown')} disabled={idx === order.length - 1} onClick={() => move(id, 1)}><ArrowDown size={16} /></button>
            <button type="button" aria-label={t('sh.remove')} onClick={() => setOrder(o => o.filter(x => x !== id))}><X size={16} /></button>
          </span>
        </li>)}
      </ol>}
      {available.length > 0 && <Select label={t('sh.addItems')} value="" onChange={e => { const v = e.target.value; if (v) setOrder(o => [...o, v]); }}>
        <option value="">{t('sh.addItems')}…</option>{available.map(i => <option key={i.id} value={i.id}>{itemTitle(i)}</option>)}
      </Select>}
      <div className="buy-actions">
        <Button type="submit" variant="primary" loading={busy} disabled={!name.trim()}>{shelf ? t('common.save') : t('sh.create')}</Button>
        {shelf && <Button variant="danger" onClick={() => void remove()} disabled={busy}><Trash2 size={16} aria-hidden /> {t('sh.delete')}</Button>}
      </div>
    </form>
  </Overlay>;
}

export function AddRoute() {
  const {t, errorText} = useI18n();
  const labels = useLabels();
  const {api} = useSession();
  const navigate = useNavigate();
  const refresh = useRefresh();
  const fail = useFail();
  const registry = useRegistry();
  const sizes = useSizeRegistry();
  const [name, setName] = useState('');
  const [slot, setSlot] = useState('top');
  const [category, setCategory] = useState('');
  const [colour, setColour] = useState('');
  const [size, setSize] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const submit = async (e: FormEvent) => {
    e.preventDefault(); setBusy(true); setError(null);
    try {
      const [system, code] = size ? size.split(':') : [];
      const item = await api.call('post', '/api/v2/me/wardrobe/items', {body: {name: name.trim(), slot: slot as never,
        category: category.trim() || null, colour: colour.trim() || null, size: system && code ? {system, code} : null}});
      await refresh('wardrobe-items');
      toast(t('add.done', {name: item.name ?? name}), 'success');
      navigate(`/wardrobe/items/${item.id}`, {replace: true});
    } catch (err) {
      if (err instanceof ApiFailure && err.code === 'WARDROBE_FULL') setError(errorText(err.code, err.message)); else fail(err);
    } finally { setBusy(false); }
  };
  const slots = registry.data?.slots.map(s => s.slot) ?? [...ALL_SLOTS];
  const sizeSystems = sizes.data?.systems.filter(s => !s.slots.length || s.slots.includes(slot)) ?? [];
  return <div className="page wr">
    <WardrobeNav />
    <form className="wr-form" onSubmit={e => void submit(e)}>
      <h1>{t('add.title')}</h1><p className="muted">{t('add.body')}</p>
      <TextField label={t('add.name')} value={name} required maxLength={120} onChange={e => setName(e.target.value)} />
      <Select label={t('add.slot')} value={slot} onChange={e => { setSlot(e.target.value); setSize(''); }}>
        {slots.map(s => <option key={s} value={s}>{labels.slot(s)}</option>)}
      </Select>
      <TextField label={t('add.category')} value={category} maxLength={100} onChange={e => setCategory(e.target.value)} />
      <TextField label={t('add.colour')} value={colour} maxLength={100} onChange={e => setColour(e.target.value)} />
      {sizeSystems.length > 0 && <Select label={t('add.size')} value={size} onChange={e => setSize(e.target.value)}>
        <option value="">{t('add.noSize')}</option>
        {sizeSystems.map(s => <optgroup key={s.code} label={s.label}>{s.sizes.map(z => <option key={z.code} value={`${s.code}:${z.code}`}>{z.label}</option>)}</optgroup>)}
      </Select>}
      {error && <p className="form-error" role="alert">{error}</p>}
      <Button type="submit" variant="primary" size="lg" loading={busy} disabled={!name.trim()}>{t('add.submit')}</Button>
    </form>
  </div>;
}
