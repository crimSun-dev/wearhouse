import {useEffect, useMemo, useRef, useState, type FormEvent} from 'react';
import {useSearchParams} from 'react-router';
import {ChevronLeft, ChevronRight, CloudRain, Sun, Undo2} from 'lucide-react';
import {useI18n} from '../../i18n/index.tsx';
import {useSession} from '../../session/SessionProvider.tsx';
import {createIntent} from '../../api/index.ts';
import {useLooks, usePlanner} from '../../data/queries.ts';
import {jakartaDate, useItems, useRefresh, useWearLog} from '../../data/wardrobe.ts';
import {Button, Select, Skeleton, TextField} from '../../components/ui.tsx';
import {Overlay} from '../../components/Overlay.tsx';
import {ItemImage} from '../../components/ItemImage.tsx';
import {EmptyState, ErrorState} from '../../components/states.tsx';
import {toast} from '../../components/toast.tsx';
import {FocusZone, focusItemProps} from '../../focus/FocusZone.tsx';
import type {Schemas} from '@wearhouse/contracts';
import {WardrobeNav, itemTitle, useFail, useLabels} from './shared.tsx';

type Day = Schemas['DayOut'];
const PLAN_OCCASIONS = ['casual', 'work', 'formal', 'sport', 'event'] as const;
/** One intent per day for "Mark worn": a repeat tap or a retried request logs one entry. */
const wearIntents = new Map<string, ReturnType<typeof createIntent>>();
const intentFor = (date: string) => { if (!wearIntents.has(date)) wearIntents.set(date, createIntent()); return wearIntents.get(date)!; };

export function PlannerRoute() {
  const {t, date: fmt} = useI18n();
  const [params, setParams] = useSearchParams();
  const today = jakartaDate();
  const from = params.get('from') ?? today;
  const planner = usePlanner(from);
  const [selected, setSelected] = useState(from);
  const [editing, setEditing] = useState<{date: string; revision?: string} | null>(null);
  const preset = params.get('look');
  useEffect(() => { if (preset) setEditing({date: today, revision: preset}); }, [preset, today]);
  useEffect(() => setSelected(s => (planner.data?.days.some(d => d.date === s) ? s : planner.data?.days[0]?.date ?? s)), [planner.data]);
  const go = (offset: number) => { const next = new URLSearchParams(params); next.set('from', jakartaDate(offset, from)); next.delete('look'); setParams(next, {replace: true}); };
  return <div className="page wr planner">
    <WardrobeNav />
    <header className="store-head"><h1>{t('pl.title')}</h1>
      <div className="buy-actions">
        <Button variant="ghost" onClick={() => go(-7)}><ChevronLeft size={18} aria-hidden /> {t('pl.prev')}</Button>
        {from !== today && <Button variant="ghost" onClick={() => { const n = new URLSearchParams(params); n.delete('from'); setParams(n, {replace: true}); }}>{t('pl.thisWeek')}</Button>}
        <Button variant="ghost" onClick={() => go(7)}>{t('pl.next')} <ChevronRight size={18} aria-hidden /></Button>
      </div></header>
    {planner.isPending ? <div className="plan-week">{Array.from({length: 7}, (_, i) => <Skeleton key={i} ratio="1 / 2" />)}</div>
      : planner.isError ? <ErrorState error={planner.error} onRetry={() => planner.refetch()} />
      : <>
        <FocusZone kind="rail" label={t('pl.title')} className="plan-strip" version={from}>
          {planner.data.days.map(d => <button key={d.date} type="button" className={`plan-chip ${d.date === selected ? 'is-active' : ''} ${d.is_today ? 'is-today' : ''}`}
            aria-pressed={d.date === selected} {...focusItemProps({id: `strip:${d.date}`, title: fmt(d.date)})} onClick={() => setSelected(d.date)}>
            <span>{new Intl.DateTimeFormat(undefined, {weekday: 'short', timeZone: 'Asia/Jakarta'}).format(new Date(`${d.date}T12:00:00+07:00`))}</span>
            <strong>{d.date.slice(8)}</strong>{d.plan && <span className="plan-dot" aria-hidden />}</button>)}
        </FocusZone>
        <div className="plan-week">
          {planner.data.days.map(d => <DayCard key={d.date} day={d} selected={d.date === selected} onPlan={() => setEditing({date: d.date})} />)}
        </div>
      </>}
    {editing && <PlanEditor date={editing.date} revision={editing.revision} onClose={() => { setEditing(null); if (preset) { const n = new URLSearchParams(params); n.delete('look'); setParams(n, {replace: true}); } }} />}
  </div>;
}

function Weather({w}: {w: Day['weather']}) {
  const {t} = useI18n();
  if (w.status === 'beyond_forecast') return <p className="plan-weather muted small">{t('pl.weatherBeyond')}</p>;
  if (w.status === 'unavailable') return <p className="plan-weather muted small" title={w.reason ?? undefined}>{t('pl.weatherUnavailable')}</p>;
  return <p className="plan-weather small">
    {w.min_temp_c != null && w.max_temp_c != null && <strong>{t('pl.temp', {min: Math.round(w.min_temp_c), max: Math.round(w.max_temp_c)})}</strong>}
    {w.rain && <span className="tag tag-quiet"><CloudRain size={12} aria-hidden /> {t('we.rain')}</span>}
    {w.hot && <span className="tag tag-quiet"><Sun size={12} aria-hidden /> {t('we.hot')}</span>}
    {w.descriptions?.[0] && <span className="muted"> {w.descriptions[0]}</span>}
  </p>;
}

function DayCard({day, selected, onPlan}: {day: Day; selected: boolean; onPlan: () => void}) {
  const {t, date: fmt} = useI18n();
  const labels = useLabels();
  const {api} = useSession();
  const refresh = useRefresh();
  const fail = useFail();
  const [busy, setBusy] = useState(false);
  const today = jakartaDate();
  const beyond = day.date > jakartaDate(30);
  const canPlan = !day.past && !beyond;
  const run = async (fn: () => Promise<unknown>, msg: string) => {
    setBusy(true);
    try { await fn(); toast(msg, 'success'); await refresh('planner', 'wear', 'wardrobe-items'); } catch (e) { fail(e); } finally { setBusy(false); }
  };
  const clear = () => run(() => api.call('delete', '/api/v2/me/planner/{plan_date}', {path: {plan_date: day.date}}), t('pl.cleared'));
  const markWorn = () => run(() => api.call('post', '/api/v2/me/wear', {body: {worn_on: day.date, look_revision_id: day.plan!.look_revision.id}, intent: intentFor(day.date)}), t('pl.wornLogged'));
  const undo = (id: string) => run(() => api.call('delete', '/api/v2/me/wear/{wear_id}', {path: {wear_id: id}}), t('wl.undone'));
  return <article className={`plan-day ${selected ? 'is-selected' : ''} ${day.is_today ? 'is-today' : ''} ${day.past ? 'is-past' : ''}`} aria-label={fmt(day.date)}>
    <header><h2>{fmt(day.date)}</h2>{day.is_today && <span className="tag tag-ok">{t('pl.today')}</span>}{day.past && !day.is_today && <span className="muted small">{t('pl.past')}</span>}</header>
    <Weather w={day.weather} />
    {day.plan ? <div className="plan-look">
      <p className="plan-look-name">{day.plan.look_revision.name}</p>
      <p className="muted small">{labels.occasion(day.plan.occasion)}{day.plan.note ? ` · ${day.plan.note}` : ''}</p>
      <div className="plan-thumbs">{day.plan.look_revision.items.slice(0, 4).map((i, k) => <span key={k} className="fit-thumb">{i.item ? <ItemImage item={i.item} quiet /> : null}</span>)}</div>
    </div> : <p className="muted">{t('pl.nothing')}</p>}
    {day.worn.length > 0 && <ul className="plan-worn">{day.worn.map(w => <li key={w.id}><span className="tag tag-ok">{t('pl.worn')}</span> {t('wl.entry', {n: w.item_ids.length})}
      <Button variant="ghost" onClick={() => void undo(w.id)} disabled={busy}><Undo2 size={14} aria-hidden /> {t('wl.undo')}</Button></li>)}</ul>}
    <div className="plan-actions">
      {canPlan ? <Button {...focusItemProps({id: `plan:${day.date}`, title: fmt(day.date)})} onClick={onPlan}>{day.plan ? t('pl.replace') : t('pl.plan')}</Button>
        : beyond ? <p className="muted small">{t('pl.beyond')}</p> : null}
      {day.plan && canPlan && <Button variant="ghost" onClick={() => void clear()} disabled={busy}>{t('pl.clear')}</Button>}
      {day.plan && day.date <= today && <Button variant="primary" loading={busy} onClick={() => void markWorn()}>{t('pl.markWorn')}</Button>}
    </div>
  </article>;
}

function PlanEditor({date, revision, onClose}: {date: string; revision?: string; onClose: () => void}) {
  const {t, date: fmt} = useI18n();
  const labels = useLabels();
  const {api} = useSession();
  const refresh = useRefresh();
  const fail = useFail();
  const looks = useLooks();
  const [look, setLook] = useState(revision ?? '');
  const [occasion, setOccasion] = useState('');
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (!look && looks.data?.[0]) setLook(looks.data[0].current.id); }, [looks.data, look]);
  const save = async (e: FormEvent) => {
    e.preventDefault(); setBusy(true);
    try {
      await api.call('put', '/api/v2/me/planner/{plan_date}', {path: {plan_date: date}, body: {look_revision_id: look, occasion: (occasion || null) as never, note: note.trim() || null}});
      toast(t('pl.saved'), 'success'); await refresh('planner'); onClose();
    } catch (err) { fail(err); } finally { setBusy(false); }
  };
  return <Overlay open onClose={onClose} side="right" title={t('pl.plan')}>
    <form className="wr-panel" onSubmit={e => void save(e)}>
      <h2>{t('pl.plan')}</h2><p className="muted">{fmt(date)}</p>
      {!looks.data?.length ? <p className="muted">{t('pl.noLooks')}</p> : <>
        <Select label={t('pl.look')} value={look} onChange={e => setLook(e.target.value)} data-autofocus>
          {revision && !looks.data.some(l => l.current.id === revision) && <option value={revision}>{t('pl.chooseLook')}</option>}
          {looks.data.map(l => <option key={l.id} value={l.current.id}>{l.name}</option>)}
        </Select>
        <Select label={t('pl.occasion')} value={occasion} onChange={e => setOccasion(e.target.value)}>
          <option value="">{t('occ.none')}</option>{PLAN_OCCASIONS.map(o => <option key={o} value={o}>{labels.occasion(o)}</option>)}
        </Select>
        <TextField label={t('pl.note')} value={note} maxLength={200} onChange={e => setNote(e.target.value)} />
        <Button type="submit" variant="primary" size="lg" loading={busy} disabled={!look}>{t('pl.save')}</Button>
      </>}
    </form>
  </Overlay>;
}

export function WearRoute() {
  const {t, date: fmt} = useI18n();
  const {api} = useSession();
  const refresh = useRefresh();
  const fail = useFail();
  const [from, setFrom] = useState(jakartaDate(-30));
  const [to, setTo] = useState(jakartaDate());
  const log = useWearLog(from, to);
  const items = useItems();
  const byId = useMemo(() => new Map((items.data?.items ?? []).map(i => [i.id, i])), [items.data]);
  const [day, setDay] = useState(jakartaDate(-1));
  const [picked, setPicked] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const intent = useRef(createIntent());
  const submit = async (e: FormEvent) => {
    e.preventDefault(); setError(null);
    if (!picked.length) { setError(t('wl.pick')); return; }
    if (day < jakartaDate(-60) || day > jakartaDate()) { setError(t('wl.limit')); return; }
    setBusy(true);
    try { await api.call('post', '/api/v2/me/wear', {body: {worn_on: day, item_ids: picked}, intent: intent.current}); intent.current = createIntent();
      setPicked([]); toast(t('wl.logged'), 'success'); await refresh('wear', 'planner', 'wardrobe-items'); }
    catch (err) { fail(err); } finally { setBusy(false); }
  };
  const undo = async (id: string) => {
    try { await api.call('delete', '/api/v2/me/wear/{wear_id}', {path: {wear_id: id}}); toast(t('wl.undone')); await refresh('wear', 'planner', 'wardrobe-items'); } catch (err) { fail(err); }
  };
  const entries = [...(log.data?.entries ?? [])].sort((a, b) => b.worn_on.localeCompare(a.worn_on));
  return <div className="page wr">
    <WardrobeNav />
    <header className="store-head"><h1>{t('wl.title')}</h1></header>
    <div className="wear-layout">
      <section>
        <div className="store-filters">
          <TextField label={t('wl.from')} type="date" value={from} onChange={e => e.target.value && setFrom(e.target.value)} />
          <TextField label={t('wl.to')} type="date" value={to} onChange={e => e.target.value && setTo(e.target.value)} />
        </div>
        {log.isPending ? <Skeleton ratio="4 / 1" /> : log.isError ? <ErrorState error={log.error} onRetry={() => log.refetch()} />
          : !entries.length ? <EmptyState title={t('wl.empty')} />
          : <ul className="bag-list wear-list">{entries.map(w => <li key={w.id} className="bag-line">
            <span className="bag-name">{fmt(w.worn_on)}<span className="bag-sub">{w.item_ids.map(id => (byId.get(id) ? itemTitle(byId.get(id)!) : '…')).join(', ')}</span></span>
            <span className="bag-meta">{t('wl.entry', {n: w.item_ids.length})}</span>
            <Button variant="ghost" onClick={() => void undo(w.id)}><Undo2 size={16} aria-hidden /> {t('wl.undo')}</Button>
          </li>)}</ul>}
      </section>
      <form className="wr-panel wear-form" onSubmit={e => void submit(e)}>
        <h2>{t('wl.log')}</h2>
        <TextField label={t('wl.date')} type="date" value={day} min={jakartaDate(-60)} max={jakartaDate()} hint={t('wl.limit')} onChange={e => setDay(e.target.value)} />
        <fieldset className="wear-items"><legend className="field-label">{t('wl.items')}</legend>
          {(items.data?.items ?? []).filter(i => !i.archived).map(i => <label key={i.id} className="wear-check">
            <input type="checkbox" checked={picked.includes(i.id)} onChange={e => setPicked(p => (e.target.checked ? [...p, i.id] : p.filter(x => x !== i.id)))} />
            {itemTitle(i)}</label>)}
        </fieldset>
        {error && <p className="form-error" role="alert">{error}</p>}
        <Button type="submit" variant="primary" loading={busy}>{t('wl.logIt')}</Button>
      </form>
    </div>
  </div>;
}
