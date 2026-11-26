import {useEffect, useMemo, useState} from 'react';
import {useNavigate, useSearchParams} from 'react-router';
import {AlertTriangle, Save, X} from 'lucide-react';
import {useI18n} from '../../i18n/index.tsx';
import {useSession} from '../../session/SessionProvider.tsx';
import {ApiFailure} from '../../api/index.ts';
import {useItems, useLook, useRefresh, useRegistry, type Item} from '../../data/wardrobe.ts';
import {Button, Skeleton, TextField} from '../../components/ui.tsx';
import {Overlay} from '../../components/Overlay.tsx';
import {ItemImage} from '../../components/ItemImage.tsx';
import {Silhouette} from '../../components/Silhouette.tsx';
import {ErrorState} from '../../components/states.tsx';
import {toast} from '../../components/toast.tsx';
import {FocusZone, focusItemProps} from '../../focus/FocusZone.tsx';
import {WardrobeNav, itemTitle, useFail, useLabels} from './shared.tsx';
import {Avatar} from '../../avatar/Avatar.tsx';

export type Equipped = Record<string, string[]>;
type Registry = {slots: Array<{slot: string; capacity: number}>; exclusions: string[][]};

/** What equipping `item` would displace, given capacities and exclusions. Pure, so it is unit-testable. */
export function planEquip(equipped: Equipped, slot: string, itemId: string, registry: Registry): {next: Equipped; removed: string[]} {
  const capacity = registry.slots.find(s => s.slot === slot)?.capacity ?? 1;
  const next: Equipped = Object.fromEntries(Object.entries(equipped).map(([k, v]) => [k, [...v]]));
  const removed: string[] = [];
  for (const pair of registry.exclusions) {
    if (!pair.includes(slot)) continue;
    for (const other of pair.filter(s => s !== slot)) { removed.push(...(next[other] ?? [])); delete next[other]; }
  }
  const current = (next[slot] ?? []).filter(id => id !== itemId);
  while (current.length >= capacity) removed.push(current.shift()!);
  next[slot] = [...current, itemId];
  return {next, removed};
}

export function FittingRoute() {
  const {t, date} = useI18n();
  const labels = useLabels();
  const {api} = useSession();
  const navigate = useNavigate();
  const refresh = useRefresh();
  const fail = useFail();
  const [params] = useSearchParams();
  const lookId = params.get('look') ?? '';
  const items = useItems();
  const registry = useRegistry();
  const look = useLook(lookId);
  const [equipped, setEquipped] = useState<Equipped>({});
  const [name, setName] = useState('');
  const [pending, setPending] = useState<{item: Item; next: Equipped; removed: string[]} | null>(null);
  const [slotErrors, setSlotErrors] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [landed, setLanded] = useState<string | null>(null);
  const byId = useMemo(() => new Map((items.data?.items ?? []).map(i => [i.id, i])), [items.data]);

  useEffect(() => {
    if (look.data) { setEquipped(look.data.current.slots); setName(look.data.name); }
  }, [look.data]);
  useEffect(() => {
    // ?item=<id> (from the inspector) or ?items=<id,id> (from a suggestion) are equipped on arrival.
    const ids = [...(params.get('items')?.split(',') ?? []), ...(params.get('item') ? [params.get('item')!] : [])];
    const reg = registry.data;
    if (!ids.length || !reg || !byId.size) return;
    setEquipped(e => ids.reduce((acc, id) => {
      const item = byId.get(id);
      return item && item.slot_source !== 'unknown' ? planEquip(acc, item.slot, item.id, reg).next : acc;
    }, e));
  }, [params, byId, registry.data]);

  if (items.isPending || registry.isPending || (lookId && look.isPending)) return <div className="page wr"><WardrobeNav /><Skeleton ratio="3 / 1" /></div>;
  if (items.isError) return <div className="page wr"><WardrobeNav /><ErrorState error={items.error} onRetry={() => items.refetch()} /></div>;
  const reg = registry.data!;
  const apply = (next: Equipped, slot: string) => { setEquipped(next); setSlotErrors({}); setLanded(slot); setTimeout(() => setLanded(null), 700); };
  const equip = (item: Item) => {
    const plan = planEquip(equipped, item.slot, item.id, reg);
    if (plan.removed.length) setPending({item, ...plan}); else apply(plan.next, item.slot);
  };
  const unequip = (slot: string, id: string) => setEquipped(e => {
    const next = {...e, [slot]: (e[slot] ?? []).filter(x => x !== id)};
    if (!next[slot]!.length) delete next[slot];
    return next;
  });
  const equippedIds = new Set(Object.values(equipped).flat());
  const count = equippedIds.size;
  const save = async () => {
    setSaving(true); setSlotErrors({});
    try {
      if (lookId && look.data) {
        const out = await api.call('patch', '/api/v2/me/looks/{look_id}', {path: {look_id: lookId}, body: {name: name.trim() || look.data.name, slots: equipped}});
        toast(t('fr.revisionSaved', {n: out.current_revision_no}), 'success');
        await refresh('looks', 'look'); navigate(`/wardrobe/looks/${out.id}`);
      } else {
        const out = await api.call('post', '/api/v2/me/looks', {body: {name: name.trim() || `${t('lk.title')} · ${date(new Date().toISOString())}`, slots: equipped}});
        toast(t('fr.saved'), 'success');
        await refresh('looks'); navigate(`/wardrobe/looks/${out.id}`);
      }
    } catch (e) {
      if (e instanceof ApiFailure && e.fieldErrors.length) {
        const errs: Record<string, string> = {};
        for (const f of e.fieldErrors as Array<{field: string; message: string}>) errs[f.field.split('.').pop() ?? ''] = f.message;
        setSlotErrors(errs);
      }
      fail(e);
    } finally { setSaving(false); }
  };
  const closet = (items.data?.items ?? []).filter(i => !i.archived);
  const groups = reg.slots.map(s => [s.slot, closet.filter(i => i.slot === s.slot && i.slot_source !== 'unknown')] as const).filter(([, l]) => l.length);

  return <div className="page wr fitting">
    <WardrobeNav />
    <header className="store-head"><div><h1>{t('fr.title')}</h1><p className="head-meta">{look.data ? t('fr.editing', {name: look.data.name}) : t('fr.newLook')}</p></div></header>
    <div className="fit-layout">
      <section className="fit-stage" aria-label={t('fr.figure')}>
        <Avatar pieces={reg.slots.flatMap(s => (equipped[s.slot] ?? []).map(id => ({slot: s.slot, colour: byId.get(id)?.colour})))} />
        <div className="fit-figure">
          {reg.slots.filter(s => equipped[s.slot]?.length).map(s => <div key={s.slot} className={`fit-slot fit-${s.slot} ${landed === s.slot ? 'is-landed' : ''} ${slotErrors[s.slot] ? 'has-error' : ''}`}>
            <span className="fit-slot-name">{labels.slot(s.slot)}{s.capacity > 1 && <span className="muted small"> {equipped[s.slot]!.length}/{s.capacity}</span>}</span>
            {equipped[s.slot]!.map(id => { const it = byId.get(id); return <div key={id} className="fit-piece">
              <span className="fit-thumb">{it ? <ItemImage item={it} quiet /> : <Silhouette slot={s.slot} />}</span>
              <span className="fit-piece-name">{it ? itemTitle(it) : t('lk.missing')}
                {it && it.care_state !== 'ready' && <span className="fit-warn"><AlertTriangle size={14} aria-hidden /> {t('fr.notReady', {care: labels.care(it.care_state)})}</span>}</span>
              <button type="button" className="wr-side-icon" aria-label={`${t('fr.unequip')}: ${it ? itemTitle(it) : id}`} onClick={() => unequip(s.slot, id)}><X size={16} /></button>
            </div>; })}
            {slotErrors[s.slot] && <p className="form-error" role="alert">{slotErrors[s.slot]}</p>}
          </div>)}
          {!count && <p className="muted fit-empty">{t('fr.nothing')}</p>}
        </div>
        <div className="fit-save">
          <TextField label={t('fr.lookName')} value={name} maxLength={80} onChange={e => setName(e.target.value)} />
          <Button variant="primary" size="lg" loading={saving} disabled={!count} onClick={() => void save()}>
            <Save size={18} aria-hidden /> {lookId ? t('fr.saveRevision') : t('fr.save')}</Button>
          {count > 0 && <Button variant="ghost" onClick={() => setEquipped({})}>{t('fr.clear')}</Button>}
        </div>
      </section>
      <section className="fit-closet" aria-label={t('fr.closet')}>
        <h2>{t('fr.closet')}</h2>
        {groups.map(([slot, list]) => <div key={slot} className="fit-group">
          <h3>{labels.slot(slot)}</h3>
          <FocusZone kind="grid" label={labels.slot(slot)} className="fit-items" version={list.length}>
            {list.map(i => { const on = equippedIds.has(i.id); return <button key={i.id} type="button" className={`fit-item ${on ? 'is-on' : ''}`} aria-pressed={on}
              {...focusItemProps({id: `fit:${i.id}`, title: itemTitle(i), meta: labels.slot(i.slot), actions: [{key: 'Enter', label: on ? t('fr.unequip') : t('fr.equip')}]})}
              onClick={() => (on ? unequip(i.slot, i.id) : equip(i))}>
              <span className="fit-thumb"><ItemImage item={i} quiet /></span>
              <span className="fit-item-name">{itemTitle(i)}{i.care_state !== 'ready' && <span className="fit-warn"><AlertTriangle size={14} aria-hidden /> {labels.care(i.care_state)}</span>}</span>
            </button>; })}
          </FocusZone>
        </div>)}
      </section>
    </div>
    <Overlay open={!!pending} onClose={() => setPending(null)} side="center" title={t('fr.conflictTitle')}>
      {pending && <div className="confirm">
        <ul className="fit-removed">{pending.removed.map(id => <li key={id}>{byId.get(id) ? `${itemTitle(byId.get(id)!)} (${labels.slot(byId.get(id)!.slot)})` : id}</li>)}</ul>
        <div className="buy-actions">
          <Button data-autofocus onClick={() => setPending(null)}>{t('fr.cancel')}</Button>
          <Button variant="primary" onClick={() => { apply(pending.next, pending.item.slot); setPending(null); }}>{t('fr.confirm')}</Button>
        </div>
      </div>}
    </Overlay>
  </div>;
}
