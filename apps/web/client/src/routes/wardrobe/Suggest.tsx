import {useEffect, useRef, useState} from 'react';
import {Link, useNavigate} from 'react-router';
import {useQuery} from '@tanstack/react-query';
import {CalendarDays, RefreshCw, Save, Shirt, Sparkles} from 'lucide-react';
import {useI18n} from '../../i18n/index.tsx';
import {useSession} from '../../session/SessionProvider.tsx';
import {ApiFailure, createIntent} from '../../api/index.ts';
import {jakartaDate, useRefresh, useRegistry} from '../../data/wardrobe.ts';
import {Button, Select, Skeleton, TextField} from '../../components/ui.tsx';
import {ModelLabel} from '../../components/labels.tsx';
import {ItemImage} from '../../components/ItemImage.tsx';
import {EmptyState, ErrorState} from '../../components/states.tsx';
import {toast} from '../../components/toast.tsx';
import {FocusZone, focusItemProps} from '../../focus/FocusZone.tsx';
import type {Schemas} from '@wearhouse/contracts';
import {WardrobeNav, itemTitle, useFail, useLabels} from './shared.tsx';

type Suggestion = Schemas['SuggestionOut'];
/** Runs whose `displayed` / `chosen` event was already sent (module scope: survives StrictMode remounts). */
const displayedRuns = new Set<string>();
const chosenRuns = new Set<string>();

export function SuggestRoute() {
  const {t, date: fmtDate} = useI18n();
  const labels = useLabels();
  const {api, userKey} = useSession();
  const navigate = useNavigate();
  const refresh = useRefresh();
  const fail = useFail();
  const registry = useRegistry();
  const [date, setDate] = useState(jakartaDate());
  const [occasion, setOccasion] = useState('');
  const [rain, setRain] = useState('');
  const [hot, setHot] = useState('');
  const [nonce, setNonce] = useState(0);
  const query = {date, limit: 5, ...(occasion ? {occasion} : {}), ...(rain ? {rain: rain === 'yes'} : {}), ...(hot ? {hot: hot === 'yes'} : {})};
  // Explicit triggers only: the key changes on open (gcTime 0), date/occasion/override changes, and Refresh (nonce).
  const run = useQuery({queryKey: [...userKey, 'suggestions', query, nonce], staleTime: Infinity, gcTime: 0, retry: false,
    queryFn: ({signal}) => api.call('get', '/api/v2/me/recommendations/outfits', {signal, query})});
  const results = useRef<HTMLDivElement>(null);
  const runId = run.data?.run_id ?? null;

  useEffect(() => {
    const el = results.current;
    if (!el || !runId || !run.data?.suggestions.length || displayedRuns.has(runId)) return;
    const io = new IntersectionObserver(entries => {
      if (!entries.some(e => e.isIntersecting) || displayedRuns.has(runId)) return;
      displayedRuns.add(runId); io.disconnect();
      void api.call('post', '/api/v2/me/recommendations/outfits/{run_id}/events', {path: {run_id: runId}, body: {kind: 'displayed'}}).catch(() => displayedRuns.delete(runId));
    }, {threshold: 0.2});
    io.observe(el);
    return () => io.disconnect();
  }, [runId, run.data, api]);

  const choose = async (index: number) => {
    if (!runId || chosenRuns.has(runId)) return;
    chosenRuns.add(runId);
    try { await api.call('post', '/api/v2/me/recommendations/outfits/{run_id}/events', {path: {run_id: runId}, body: {kind: 'chosen', index}}); }
    catch (e) { if (e instanceof ApiFailure && e.code === 'ALREADY_CHOSEN') toast(t('sg.alreadyChosen')); }
  };
  // A suggestion's `slots` maps item id -> slot; a look's `slots` maps slot -> item ids (several for multi-capacity slots).
  const slotsOf = (s: Suggestion) => {
    const out: Record<string, string[]> = {};
    for (const [id, slot] of Object.entries(s.slots)) (out[slot] ??= []).push(id);
    return out;
  };
  const saveLook = async (s: Suggestion, index: number) => {
    const look = await api.call('post', '/api/v2/me/looks', {body: {name: `${t('sg.outfit', {n: index + 1})} · ${fmtDate(date)}`, slots: slotsOf(s)}});
    void refresh('looks');
    return look;
  };
  const act = async (kind: 'try' | 'save' | 'plan' | 'wear', s: Suggestion, index: number) => {
    void choose(index);
    try {
      if (kind === 'try') navigate(`/wardrobe/fitting-room?items=${s.item_ids.join(',')}`);
      else if (kind === 'save') { const look = await saveLook(s, index); toast(t('sg.savedLook'), 'success'); navigate(`/wardrobe/looks/${look.id}`); }
      else if (kind === 'plan') {
        const look = await saveLook(s, index);
        await api.call('put', '/api/v2/me/planner/{plan_date}', {path: {plan_date: date}, body: {look_revision_id: look.current.id}});
        void refresh('planner'); toast(t('sg.planned', {date: fmtDate(date)}), 'success');
      } else {
        await api.call('post', '/api/v2/me/wear', {body: {worn_on: jakartaDate(), item_ids: s.item_ids}, intent: createIntent()});
        void refresh('wear', 'planner', 'wardrobe-items'); toast(t('sg.worn'), 'success');
      }
    } catch (e) { fail(e); }
  };

  const occasions = registry.data?.occasions ?? [];
  const d = run.data;
  return <div className="page wr suggest">
    <WardrobeNav />
    <header className="store-head"><h1><Sparkles size={28} aria-hidden /> {t('sg.title')}</h1></header>
    <div className="store-filters suggest-controls">
      <TextField label={t('sg.date')} type="date" value={date} min={jakartaDate()} max={jakartaDate(30)} onChange={e => e.target.value && setDate(e.target.value)} />
      <Select label={t('sg.occasion')} value={occasion} onChange={e => setOccasion(e.target.value)}>
        <option value="">{t('sg.anyOccasion')}</option>{occasions.map(o => <option key={o} value={o}>{labels.occasion(o)}</option>)}
      </Select>
      <Select label={t('sg.rain')} value={rain} onChange={e => setRain(e.target.value)}>
        <option value="">{t('sg.auto')}</option><option value="yes">{t('sg.yes')}</option><option value="no">{t('sg.no')}</option></Select>
      <Select label={t('sg.hot')} value={hot} onChange={e => setHot(e.target.value)}>
        <option value="">{t('sg.auto')}</option><option value="yes">{t('sg.yes')}</option><option value="no">{t('sg.no')}</option></Select>
      <Button onClick={() => setNonce(n => n + 1)} loading={run.isFetching}><RefreshCw size={18} aria-hidden /> {t('sg.refresh')}</Button>
    </div>
    {run.isPending ? <div className="suggest-grid">{Array.from({length: 3}, (_, i) => <Skeleton key={i} ratio="4 / 5" />)}</div>
      : run.isError ? <ErrorState error={run.error} onRetry={() => setNonce(n => n + 1)} />
      : d!.enabled === false ? <EmptyState title={t('sg.disabled')} body={t('sg.disabledBody')}><Link className="btn btn-primary btn-md" to="/settings">{t('sg.openSettings')}</Link></EmptyState>
      : <>
        <p className="suggest-meta">
          <span className="tag tag-quiet">{t('sg.weather', {source: d!.weather.source})}{d!.weather.rain ? ` · ${t('we.rain')}` : ''}{d!.weather.hot ? ` · ${t('we.hot')}` : ''}</span>
          {d!.ruleset && <span className="tag tag-quiet">{t('sg.ruleset', {ruleset: d!.ruleset})}</span>}
          {d!.model && <ModelLabel mode={d!.model.mode} />}
          {d!.weights && <span className="muted small">{t('sg.weights')}: {Object.entries(d!.weights).map(([k, v]) => `${k} ${v}`).join(' · ')}</span>}
          <span className="muted small">{t('sg.considered', {n: d!.candidates_considered, ready: d!.ready_items})}</span>
        </p>
        {!d!.suggestions.length || d!.suggestions.length < 5 ? (d!.reasons.length > 0 || Object.keys(d!.removed_by_rule ?? {}).length > 0) && <div className="suggest-reasons">
          {!d!.suggestions.length && <h2>{t('sg.none')}</h2>}
          <ul>{d!.reasons.map(r => <li key={r}>{r}</li>)}</ul>
          {Object.keys(d!.removed_by_rule ?? {}).length > 0 && <p className="muted small">{t('sg.removed')}: {Object.entries(d!.removed_by_rule!).map(([k, v]) => `${k} ${v}`).join(' · ')}</p>}
        </div> : null}
        <div ref={results}>
          <FocusZone kind="rail" label={t('sg.title')} className="suggest-grid" version={runId}>
            {d!.suggestions.map((s, i) => <article key={`${runId}-${i}`} className="suggest-card" style={{'--deal': i} as never}
              {...focusItemProps({id: `sg:${runId}:${i}`, title: t('sg.outfit', {n: i + 1}), meta: s.score !== null ? t('sg.score', {score: s.score.toFixed(2)}) : undefined})} tabIndex={0}>
              <header><h2>{t('sg.outfit', {n: i + 1})}</h2>{s.score !== null && <span className="tag tag-quiet">{t('sg.score', {score: s.score.toFixed(2)})}</span>}</header>
              <div className="suggest-items">{s.items.map(it => <figure key={it.id}><span className="fit-thumb"><ItemImage item={it} quiet /></span>
                <figcaption>{itemTitle(it)}<span className="muted small">{labels.slot(it.slot)}</span></figcaption></figure>)}</div>
              {!!s.explanation?.length && <details open><summary>{t('sg.why')}</summary><ul>{s.explanation.map(x => <li key={x}>{x}</li>)}</ul></details>}
              <details><summary>{t('sg.components')}</summary><dl className="suggest-components">
                {Object.entries(s.components).map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v === null ? '—' : v.toFixed(2)}</dd></div>)}</dl></details>
              <div className="buy-actions">
                <Button variant="primary" onClick={() => void act('try', s, i)}><Shirt size={16} aria-hidden /> {t('sg.tryOn')}</Button>
                <Button onClick={() => void act('save', s, i)}><Save size={16} aria-hidden /> {t('sg.saveLook')}</Button>
                <Button onClick={() => void act('plan', s, i)}><CalendarDays size={16} aria-hidden /> {t('sg.plan')}</Button>
                {date === jakartaDate() && <Button variant="ghost" onClick={() => void act('wear', s, i)}>{t('sg.wear')}</Button>}
              </div>
            </article>)}
          </FocusZone>
        </div>
      </>}
  </div>;
}
