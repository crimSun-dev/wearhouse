import {useEffect, useState, type FormEvent} from 'react';
import {useQuery} from '@tanstack/react-query';
import {Check, CloudRain, MapPin, Sun} from 'lucide-react';
import {useI18n} from '../../i18n/index.tsx';
import {useSession} from '../../session/SessionProvider.tsx';
import {useMyWeather} from '../../data/queries.ts';
import {useRefresh, useUsualSizes} from '../../data/wardrobe.ts';
import {useSizeRegistry} from '../../data/store.ts';
import {Button, Select, Skeleton, TextField} from '../../components/ui.tsx';
import {ErrorState} from '../../components/states.tsx';
import {DEFAULT_PLACE, QUICK_PLACES, placeLabel, shortCity, useCityRegions, usePlace, useRegionIndex} from '../../data/regions.ts';
import {toast} from '../../components/toast.tsx';
import {WardrobeNav, useFail} from './shared.tsx';

export const ADM4 = /^\d{2}\.\d{2}\.\d{2}\.\d{4}$/;

type Forecast = NonNullable<ReturnType<typeof useMyWeather>['data']>;

/** Forecast for any BMKG village code (signed-in lookup; nothing is stored). */
function useForecast(adm4: string | null) {
  const {api, userKey, status} = useSession();
  return useQuery({queryKey: [...userKey, 'forecast', adm4], enabled: !!adm4 && status === 'ready', staleTime: 10 * 60_000,
    queryFn: ({signal}) => api.call('get', '/api/v2/weather/forecast', {signal, query: {adm4: adm4!}})});
}

export function WeatherRoute() {
  const {t} = useI18n();
  const {api} = useSession();
  const refresh = useRefresh();
  const fail = useFail();
  const weather = useMyWeather();
  const saved = weather.data?.adm4 ?? null;
  const [chosen, setChosen] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  // Like the legacy app: with nothing saved, Kemayoran (Jakarta Pusat) is shown until you pick your own area.
  const shown = chosen ?? saved ?? (weather.isSuccess ? DEFAULT_PLACE : null);
  const isSaved = !!shown && shown === saved;
  const other = useForecast(shown && !isSaved ? shown : null);
  const data: Forecast | undefined = isSaved ? weather.data : other.data;
  const loading = isSaved ? weather.isPending : !shown || other.isPending;
  const failed = isSaved ? weather.error : other.error;
  const place = usePlace(shown);

  const save = async (adm4: string) => {
    setBusy(true);
    try { await api.call('put', '/api/v2/me/weather/location', {body: {adm4}}); toast(t('we.saved'), 'success'); setChosen(null); await refresh('weather', 'planner'); }
    catch (err) { fail(err); } finally { setBusy(false); }
  };
  const clear = async () => {
    setBusy(true);
    try { await api.call('delete', '/api/v2/me/weather/location', {}); setChosen(null); toast(t('we.cleared')); await refresh('weather', 'planner'); }
    catch (err) { fail(err); } finally { setBusy(false); }
  };
  return <div className="page wr weather">
    <WardrobeNav />
    <header className="store-head weather-head">
      <div><h1>{t('we.title')}</h1>
        <p className="weather-place"><MapPin size={18} aria-hidden /> <strong>{place ? placeLabel(place) : shown ?? '…'}</strong>
          {place && <span className="muted"> · {place.province}</span>}</p>
        <p className="muted small" data-testid="weather-saved">{isSaved ? t('we.isSaved') : t('we.notSaved')}</p></div>
      <div className="buy-actions">
        {shown && !isSaved && <Button variant="primary" loading={busy} onClick={() => void save(shown)}><Check size={18} aria-hidden /> {t('we.set')}</Button>}
        {isSaved && <Button variant="ghost" onClick={() => void clear()} disabled={busy}>{t('we.clearLoc')}</Button>}
      </div>
    </header>
    {loading ? <Skeleton ratio="4 / 1" /> : failed ? <ErrorState error={failed} onRetry={() => void (isSaved ? weather.refetch() : other.refetch())} />
      : data ? <ForecastDays w={data} /> : null}
    <LocationPicker current={shown} onPick={setChosen} />
    <p className="muted small">{t('we.credit')}</p>
  </div>;
}

function ForecastDays({w}: {w: Forecast}) {
  const {t, date, time} = useI18n();
  if (w.source === 'MANUAL_REQUIRED' || !w.slots.length) return <p className="co-alert" role="status">{t('we.manual')}</p>;
  const days = new Map<string, Forecast['slots']>();
  for (const s of w.slots) days.set(s.local_date, [...(days.get(s.local_date) ?? []), s]);
  return <>
    <p className="muted small">{t('we.source', {source: w.source})}{w.fetched_at && ` · ${t('we.fetched', {time: `${date(w.fetched_at)} ${time(w.fetched_at)}`})}`}</p>
    <div className="weather-days">{[...days.entries()].map(([day, slots]) => <section key={day} className="weather-day">
      <h2>{date(day)}</h2>
      <ul>{slots.map(s => <li key={s.at}>
        <span className="weather-time">{time(s.at)}</span><strong>{Math.round(s.temp_c)}°C</strong>
        <span className="weather-desc">{s.description}
          {s.rain && <span className="tag tag-quiet"><CloudRain size={12} aria-hidden /> {t('we.rain')}</span>}
          {s.hot && <span className="tag tag-quiet"><Sun size={12} aria-hidden /> {t('we.hot')}</span>}</span>
        <span className="muted small">{s.humidity}%</span>
      </li>)}</ul>
    </section>)}</div>
  </>;
}

/** Pick a place by name: one-tap common places, a city search, then province → city → district → village. */
function LocationPicker({current, onPick}: {current: string | null; onPick: (adm4: string) => void}) {
  const {t} = useI18n();
  const index = useRegionIndex();
  const [province, setProvince] = useState('');
  const [city, setCity] = useState('');
  const [district, setDistrict] = useState('');
  const [query, setQuery] = useState('');
  const [code, setCode] = useState('');
  const [codeError, setCodeError] = useState<string | null>(null);
  const regions = useCityRegions(city || null);
  // Follow the place being shown so the selects always describe it.
  useEffect(() => {
    if (!current || !ADM4.test(current)) return;
    setProvince(current.slice(0, 2)); setCity(current.slice(0, 5)); setDistrict(current.slice(6, 8));
  }, [current]);
  const cities = (index.data?.cities ?? []).filter(([c]) => c.startsWith(`${province}.`));
  const q = query.trim().toLowerCase();
  const matches = q.length < 2 ? [] : (index.data?.cities ?? []).filter(([, n]) => shortCity(n).toLowerCase().includes(q)).slice(0, 8);
  const villages = regions.data?.find(d => d[0] === district)?.[2] ?? [];
  const provinceName = (c: string) => index.data?.provinces.find(p => p[0] === c.slice(0, 2))?.[1] ?? '';
  const pickCity = (c: string) => { setProvince(c.slice(0, 2)); setCity(c); setDistrict(''); setQuery(''); };
  const manual = (e: FormEvent) => {
    e.preventDefault();
    if (!ADM4.test(code.trim())) { setCodeError(t('we.adm4Invalid')); return; }
    setCodeError(null); onPick(code.trim());
  };
  return <section className="weather-picker" aria-labelledby="we-pick">
    <h2 id="we-pick">{t('we.change')}</h2>
    <div className="weather-quick" role="group" aria-label={t('we.quick')}>
      {QUICK_PLACES.map(([c, label]) => <button key={c} type="button" className={`chip ${c === current ? 'is-active' : ''}`} aria-pressed={c === current} onClick={() => onPick(c)}>{label}</button>)}
    </div>
    <div className="weather-search">
      <TextField label={t('we.search')} placeholder={t('we.searchHint')} value={query} onChange={e => setQuery(e.target.value)} autoComplete="off" />
      {matches.length > 0 && <ul className="weather-matches">{matches.map(([c, n]) => <li key={c}>
        <button type="button" onClick={() => pickCity(c)}><strong>{shortCity(n)}</strong> <span className="muted small">{provinceName(c)}</span></button></li>)}</ul>}
      {q.length >= 2 && !matches.length && index.isSuccess && <p className="muted small">{t('we.noMatch')}</p>}
    </div>
    {index.isError ? <ErrorState error={index.error} onRetry={() => index.refetch()} /> : <div className="weather-selects">
      <Select label={t('we.province')} value={province} onChange={e => { setProvince(e.target.value); setCity(''); setDistrict(''); }}>
        <option value="">{t('we.choose')}</option>
        {index.data?.provinces.map(([c, n]) => <option key={c} value={c}>{n}</option>)}
      </Select>
      <Select label={t('we.city')} value={city} disabled={!province} onChange={e => { setCity(e.target.value); setDistrict(''); }}>
        <option value="">{t('we.choose')}</option>
        {cities.map(([c, n]) => <option key={c} value={c}>{shortCity(n)}</option>)}
      </Select>
      <Select label={t('we.district')} value={district} disabled={!regions.data} onChange={e => setDistrict(e.target.value)}>
        <option value="">{t('we.choose')}</option>
        {regions.data?.map(([c, n]) => <option key={c} value={c}>{n}</option>)}
      </Select>
      <Select label={t('we.village')} value={current?.startsWith(`${city}.${district}.`) ? current.slice(9) : ''} disabled={!villages.length}
        onChange={e => { if (e.target.value) onPick(`${city}.${district}.${e.target.value}`); }}>
        <option value="">{t('we.choose')}</option>
        {villages.map(([c, n]) => <option key={c} value={c}>{n}</option>)}
      </Select>
    </div>}
    <details className="weather-code">
      <summary>{t('we.byCode')}</summary>
      <form onSubmit={manual}>
        <TextField label={t('we.adm4')} hint={t('we.adm4Hint')} error={codeError ?? undefined} value={code} inputMode="decimal" maxLength={13}
          onChange={e => { setCode(e.target.value); setCodeError(null); }} placeholder="31.71.03.1001" />
        <Button type="submit">{t('we.preview')}</Button>
      </form>
    </details>
    <p className="muted small">{t('we.regionsSource')}</p>
  </section>;
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
