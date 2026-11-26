import {useEffect, useState, type FormEvent} from 'react';
import {CloudRain, MapPin, Sun} from 'lucide-react';
import {useI18n} from '../../i18n/index.tsx';
import {useSession} from '../../session/SessionProvider.tsx';
import {useMyWeather} from '../../data/queries.ts';
import {useRefresh, useUsualSizes} from '../../data/wardrobe.ts';
import {useSizeRegistry} from '../../data/store.ts';
import {Button, Select, Skeleton, TextField} from '../../components/ui.tsx';
import {EmptyState, ErrorState} from '../../components/states.tsx';
import {toast} from '../../components/toast.tsx';
import {WardrobeNav, useFail} from './shared.tsx';

export const ADM4 = /^\d{2}\.\d{2}\.\d{2}\.\d{4}$/;

export function WeatherRoute() {
  const {t, date, time} = useI18n();
  const {api} = useSession();
  const refresh = useRefresh();
  const fail = useFail();
  const weather = useMyWeather();
  const [adm4, setAdm4] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (weather.data?.adm4) setAdm4(weather.data.adm4); }, [weather.data?.adm4]);
  const save = async (e: FormEvent) => {
    e.preventDefault();
    if (!ADM4.test(adm4.trim())) { setError(t('we.adm4Invalid')); return; }
    setBusy(true); setError(null);
    try { await api.call('put', '/api/v2/me/weather/location', {body: {adm4: adm4.trim()}}); toast(t('we.saved'), 'success'); await refresh('weather', 'planner'); }
    catch (err) { fail(err); } finally { setBusy(false); }
  };
  const clear = async () => {
    setBusy(true);
    try { await api.call('delete', '/api/v2/me/weather/location', {}); setAdm4(''); toast(t('we.cleared')); await refresh('weather', 'planner'); }
    catch (err) { fail(err); } finally { setBusy(false); }
  };
  const w = weather.data;
  const noLocation = w?.note === 'no_location' || (w && !w.adm4);
  const days = new Map<string, NonNullable<typeof w>['slots']>();
  for (const s of w?.slots ?? []) days.set(s.local_date, [...(days.get(s.local_date) ?? []), s]);
  return <div className="page wr weather">
    <WardrobeNav />
    <header className="store-head"><h1>{t('we.title')}</h1>
      {w?.adm4 && <p className="muted"><MapPin size={16} aria-hidden /> {t('we.location', {adm4: w.adm4})}</p>}</header>
    {weather.isPending ? <Skeleton ratio="4 / 1" /> : weather.isError ? <ErrorState error={weather.error} onRetry={() => weather.refetch()} />
      : noLocation ? <EmptyState title={t('we.noLocation')} body={t('we.noLocationBody')} />
      : w!.source === 'MANUAL_REQUIRED' || !w!.slots.length ? <p className="co-alert" role="status">{t('we.manual')}</p>
      : <>
        <p className="muted small">{t('we.source', {source: w!.source})}{w!.fetched_at && ` · ${t('we.fetched', {time: `${date(w!.fetched_at)} ${time(w!.fetched_at)}`})}`}</p>
        <div className="weather-days">{[...days.entries()].map(([day, slots]) => <section key={day} className="weather-day">
          <h2>{date(day)}</h2>
          <ul>{slots.map(s => <li key={s.at}>
            <span className="weather-time">{time(s.at)}</span><strong>{Math.round(s.temp_c)}°C</strong>
            <span>{s.description}</span>
            {s.rain && <span className="tag tag-quiet"><CloudRain size={12} aria-hidden /> {t('we.rain')}</span>}
            {s.hot && <span className="tag tag-quiet"><Sun size={12} aria-hidden /> {t('we.hot')}</span>}
            <span className="muted small">{t('we.humidity', {n: s.humidity})}</span>
          </li>)}</ul>
        </section>)}</div>
      </>}
    <form className="wr-panel weather-form" onSubmit={e => void save(e)}>
      <TextField label={t('we.adm4')} hint={t('we.adm4Hint')} error={error ?? undefined} value={adm4} inputMode="decimal" maxLength={13}
        onChange={e => { setAdm4(e.target.value); setError(null); }} placeholder="31.71.03.1001" />
      <div className="buy-actions">
        <Button type="submit" variant="primary" loading={busy}>{t('we.set')}</Button>
        {w?.adm4 && <Button variant="ghost" onClick={() => void clear()} disabled={busy}>{t('we.clearLoc')}</Button>}
      </div>
    </form>
    <p className="muted small">{t('we.credit')}</p>
  </div>;
}

export function SizesRoute() {
  const {t} = useI18n();
  const {api} = useSession();
  const refresh = useRefresh();
  const fail = useFail();
  const usual = useUsualSizes();
  const registry = useSizeRegistry();
  const [draft, setDraft] = useState<Record<string, string | null>>({});
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (usual.data) setDraft(Object.fromEntries(usual.data.systems.map(s => [s.system, s.usual?.code ?? null]))); }, [usual.data]);
  const save = async () => {
    setBusy(true);
    try { await api.call('put', '/api/v2/me/sizes', {body: {usual: draft}}); toast(t('sz.saved'), 'success'); await refresh('usual-sizes'); }
    catch (e) { fail(e); } finally { setBusy(false); }
  };
  return <div className="page wr">
    <WardrobeNav />
    <header className="store-head"><div><h1>{t('sz.title')}</h1><p className="muted">{t('sz.body')}</p></div></header>
    {usual.isPending || registry.isPending ? <Skeleton ratio="4 / 1" /> : usual.isError ? <ErrorState error={usual.error} onRetry={() => usual.refetch()} />
      : <div className="wr-panel sizes-form">
        {usual.data.systems.map(s => { const sys = registry.data?.systems.find(r => r.code === s.system);
          return <Select key={s.system} label={s.label} value={draft[s.system] ?? ''} onChange={e => setDraft(d => ({...d, [s.system]: e.target.value || null}))}>
            <option value="">{t('sz.none')}</option>{sys?.sizes.filter(z => z.active !== false).map(z => <option key={z.code} value={z.code}>{z.label}</option>)}
          </Select>; })}
        <Button variant="primary" loading={busy} onClick={() => void save()}>{t('common.save')}</Button>
      </div>}
  </div>;
}
