import {useEffect, useState, type FormEvent} from 'react';
import {NavLink, useLocation, useNavigate, useParams, useSearchParams} from 'react-router';
import {useQuery} from '@tanstack/react-query';
import {Download, KeyRound, LogOut, MailCheck, MonitorSmartphone, ShieldCheck, Trash2} from 'lucide-react';
import {useI18n} from '../../i18n/index.tsx';
import {useSession, loadAuth} from '../../session/SessionProvider.tsx';
import {useSettings} from '../../settings/SettingsProvider.tsx';
import {ApiFailure, downloadBlob} from '../../api/index.ts';
import {checkPassword} from '../../auth/password.ts';
import {AuthFailure, type DeviceSession, type LinkedMethod} from '../../auth/port.ts';
import {Button, Segmented, Select, Skeleton, Slider, TextField, Toggle} from '../../components/ui.tsx';
import {Overlay} from '../../components/Overlay.tsx';
import {ErrorState} from '../../components/states.tsx';
import {toast} from '../../components/toast.tsx';
import {useRefresh} from '../../data/wardrobe.ts';
import {useFail} from '../wardrobe/shared.tsx';
import type {MessageKey} from '../../i18n/en.ts';
import '../social/social.css';

const EXTRA = ['privacy', 'security', 'account'] as const;
const RESUME_KEY = 'wearhouse.resumeDelete';
const human = (key: string) => key.replace(/_/g, ' ').replace(/^./, c => c.toUpperCase());

export function SettingsRoute() {
  const {section = ''} = useParams();
  const {t, date, time} = useI18n();
  const {api, userKey} = useSession();
  const data = useQuery({queryKey: [...userKey, 'settings'], queryFn: ({signal}) => api.call('get', '/api/v2/me/settings', {signal})});
  const label = (s: string) => { const k = `st.section.${s}` as MessageKey; const v = t(k); return v === k ? human(s) : v; };
  if (data.isPending) return <div className="page"><Skeleton ratio="4 / 1" /></div>;
  if (data.isError) return <div className="page"><ErrorState error={data.error} onRetry={() => data.refetch()} /></div>;
  const sections = [...data.data.sections, ...EXTRA];
  const current = sections.includes(section as never) ? section : sections[0]!;
  return <div className="page settings">
    <header className="store-head"><h1>{t('st.title')}</h1>
      <p className="muted small">{data.data.updated_at ? t('st.synced', {time: `${date(data.data.updated_at)} ${time(data.data.updated_at)}`}) : t('st.neverSynced')}</p></header>
    <div className="settings-layout">
      <nav className="settings-rail" aria-label={t('st.title')}>
        {sections.map(s => <NavLink key={s} to={`/settings/${s}`} className={() => `wr-side-link ${s === current ? 'is-active' : ''}`}>{label(s)}</NavLink>)}
      </nav>
      <section className="settings-panel" aria-label={label(current)}>
        <h2>{label(current)}</h2>
        {current === 'privacy' ? <Privacy /> : current === 'security' ? <Security /> : current === 'account' ? <AccountData />
          : <SchemaSection section={current} schema={data.data.schema.filter(k => k.section === current)} />}
      </section>
    </div>
  </div>;
}

/** Every key the server returns for a section, rendered by its type: no client change for new keys. */
function SchemaSection({section, schema}: {section: string; schema: Array<{key: string; type: 'choice' | 'flag' | 'range'; choices: string[]; min: number | null; max: number | null}>}) {
  const {t} = useI18n();
  const {values, update} = useSettings();
  const label = (key: string) => { const k = `set.${key}` as MessageKey; const v = t(k); return v === k ? human(key) : v; };
  const choiceLabel = (key: string, c: string) => { const k = `set.${key}.${c}` as MessageKey; const v = t(k); return v === k ? human(c) : v; };
  return <div className="settings-keys" data-section={section}>{schema.map(k => {
    const value = values[k.key];
    if (k.type === 'flag') return <Toggle key={k.key} label={label(k.key)} checked={!!value} onChange={on => void update({[k.key]: on})} />;
    if (k.type === 'range') return <Slider key={k.key} label={label(k.key)} value={Number(value ?? k.min ?? 0)} min={k.min ?? 0} max={k.max ?? 100}
      onCommit={v => void update({[k.key]: v})} />;
    return k.choices.length <= 4
      ? <div key={k.key} className="field"><span className="field-label">{label(k.key)}</span>
        <Segmented label={label(k.key)} value={String(value)} onChange={v => void update({[k.key]: v})} options={k.choices.map(c => ({value: c, label: choiceLabel(k.key, c)}))} /></div>
      : <Select key={k.key} label={label(k.key)} value={String(value)} onChange={e => void update({[k.key]: e.target.value})}>
        {k.choices.map(c => <option key={c} value={c}>{choiceLabel(k.key, c)}</option>)}</Select>;
  })}</div>;
}

function Privacy() {
  const {t} = useI18n();
  const {api, userKey} = useSession();
  const refresh = useRefresh();
  const fail = useFail();
  const privacy = useQuery({queryKey: [...userKey, 'privacy'], queryFn: ({signal}) => api.call('get', '/api/v2/me/privacy', {signal})});
  if (privacy.isPending) return <Skeleton ratio="4 / 1" />;
  if (privacy.isError) return <ErrorState error={privacy.error} onRetry={() => privacy.refetch()} />;
  const set = async (key: 'profile' | 'wardrobe' | 'friends_list', value: 'public' | 'friends' | 'private') => {
    try { await api.call('put', '/api/v2/me/privacy', {body: {...privacy.data, [key]: value}}); toast(t('pv.saved'), 'success'); await refresh('privacy', 'own-profile', 'my-shares'); }
    catch (e) { fail(e); }
  };
  return <div className="settings-keys">{(['profile', 'wardrobe', 'friends_list'] as const).map(key => <div key={key} className="field">
    <span className="field-label">{t(`pv.${key}`)}</span>
    <Segmented label={t(`pv.${key}`)} value={privacy.data[key]} onChange={v => void set(key, v)}
      options={(['public', 'friends', 'private'] as const).map(v => ({value: v, label: t(`pv.${v}`)}))} />
    <span className="muted small">{t(`pv.${privacy.data[key]}Help`)}</span>
  </div>)}</div>;
}

function Security() {
  const {t, date} = useI18n();
  const {api, userKey, broker, me, signOut} = useSession();
  const navigate = useNavigate();
  const fail = useFail();
  const info = useQuery({queryKey: [...userKey, 'security'], queryFn: ({signal}) => api.call('get', '/api/v2/me/security', {signal})});
  const [devices, setDevices] = useState<DeviceSession[] | null | undefined>(undefined);
  const [methods, setMethods] = useState<LinkedMethod[] | null>(null);
  const [confirmAll, setConfirmAll] = useState(false);
  const [current, setCurrent] = useState(''); const [next, setNext] = useState(''); const [others, setOthers] = useState(true);
  const [pwError, setPwError] = useState<string | null>(null); const [busy, setBusy] = useState(false);
  const loadDevices = async () => { const auth = await loadAuth(); setDevices(await auth?.listSessions().catch(() => null) ?? null); setMethods(await auth?.listMethods().catch(() => null) ?? null); };
  useEffect(() => { void loadDevices(); }, []);
  const check = checkPassword(next, {email: broker?.email, handle: me?.handle});
  const change = async (e: FormEvent) => {
    e.preventDefault(); setPwError(null);
    if (!check.ok) { setPwError(check.problems.join(' ')); return; }          // refused before anything is sent to the broker
    setBusy(true);
    try { await (await loadAuth())!.changePassword(current, next, others); setCurrent(''); setNext(''); toast(t('se.changed'), 'success'); void loadDevices(); }
    catch (err) { setPwError(err instanceof AuthFailure ? err.message : t('common.offline')); } finally { setBusy(false); }
  };
  const everywhere = async () => {
    try { await api.call('post', '/api/v2/me/sessions/revoke-all', {}); await (await loadAuth())?.revokeSessions(); } catch (e) { fail(e); return; }
    await signOut(); navigate('/signin', {replace: true});
  };
  const ageText = (s: number | null | undefined) => (s == null ? '—' : s < 3600 ? `${Math.round(s / 60)} min` : `${Math.round(s / 3600)} h`);
  return <div className="settings-keys">
    {info.isSuccess && <div className="security-overview">
      <p><ShieldCheck size={18} aria-hidden /> {info.data.account_created_at && t('se.created', {date: date(info.data.account_created_at)})}</p>
      <p className="muted">{t('se.session', {age: ageText(info.data.current_session.age_seconds)})}</p>
      <p className="muted small">{t('se.broker', {broker: info.data.password_managed_by})}</p>
    </div>}
    <form className="wr-panel" onSubmit={e => void change(e)}>
      <h3><KeyRound size={18} aria-hidden /> {t('se.password')}</h3>
      <TextField label={t('se.current')} type="password" autoComplete="current-password" value={current} onChange={e => setCurrent(e.target.value)} />
      <TextField label={t('se.new')} type="password" autoComplete="new-password" value={next} onChange={e => { setNext(e.target.value); setPwError(null); }}
        hint={next ? `${t('se.strength', {s: t(`se.${check.strength}` as MessageKey)})}${check.problems.length ? ' · ' + check.problems.join(' ') : ''}` : undefined} error={pwError ?? undefined} />
      <Toggle label={t('se.signOutOthers')} checked={others} onChange={setOthers} />
      <Button type="submit" variant="primary" loading={busy} disabled={!current || !next}>{t('se.password')}</Button>
    </form>
    {broker?.email && <div className="buy-actions">{broker.emailVerified ? <span className="tag tag-ok"><MailCheck size={14} aria-hidden /> {t('se.verified')}</span>
      : <Button onClick={() => void loadAuth().then(a => a!.sendVerificationEmail(broker.email!)).then(() => toast(t('se.verifySent'), 'success'), fail)}>
        <MailCheck size={16} aria-hidden /> {t('se.verify')}</Button>}</div>}
    <section><h3><MonitorSmartphone size={18} aria-hidden /> {t('se.devices')}</h3>
      {devices === undefined ? <Skeleton ratio="8 / 1" /> : !devices ? <p className="muted">{t('se.noDevices')}</p> : <ul className="person-list">
        {devices.map(d => <li key={d.id} className="person-row"><span>{d.userAgent ?? d.id}{d.current && <span className="tag tag-ok">{t('se.thisDevice')}</span>}
          <span className="muted small"> {d.createdAt && date(d.createdAt)}{d.ipAddress ? ` · ${d.ipAddress}` : ''}</span></span>
          {!d.current && <Button variant="ghost" onClick={() => void loadAuth().then(a => a!.revokeSession(d.token)).then(loadDevices, fail)}>{t('se.revoke')}</Button>}</li>)}
      </ul>}
      {!!devices?.some(d => !d.current) && <Button onClick={() => void loadAuth().then(a => a!.revokeOtherSessions()).then(loadDevices, fail)}>{t('se.revokeOthers')}</Button>}
    </section>
    {methods && <section><h3>{t('se.methods')}</h3><p>{methods.map(m => m.provider).join(', ')}</p><p className="muted small">{t('se.methodsNote')}</p></section>}
    {info.isSuccess && info.data.events.length > 0 && <section><h3>{t('se.events')}</h3><ul className="person-list">{info.data.events.map((e, k) => <li key={k} className="person-row">
      <span>{human(e.action)}{e.by_you && <span className="muted small"> · {t('se.byYou')}</span>}</span><span className="muted small">{date(e.at)}</span></li>)}</ul></section>}
    <section className="danger-zone"><Button variant="danger" onClick={() => setConfirmAll(true)}><LogOut size={16} aria-hidden /> {t('se.everywhere')}</Button></section>
    <Overlay open={confirmAll} onClose={() => setConfirmAll(false)} side="center" title={t('se.everywhere')}>
      <div className="confirm"><p>{t('se.everywhereWarn')}</p><div className="buy-actions">
        <Button data-autofocus onClick={() => setConfirmAll(false)}>{t('common.cancel')}</Button>
        <Button variant="danger" onClick={() => void everywhere()}>{t('se.everywhere')}</Button></div></div>
    </Overlay>
  </div>;
}

function AccountData() {
  const {t} = useI18n();
  const {api, me, signOut} = useSession();
  const navigate = useNavigate();
  const location = useLocation();
  const [params] = useSearchParams();
  const fail = useFail();
  const [typed, setTyped] = useState('');
  const [busy, setBusy] = useState(false);
  // Set before the re-authentication sign-out; read once when the user is brought back here after signing in again.
  const [resumed] = useState(() => { let flag = params.get('resume') === 'delete'; try { flag ||= sessionStorage.getItem(RESUME_KEY) === '1'; sessionStorage.removeItem(RESUME_KEY); } catch { /* no storage */ } return flag; });
  const exportData = async () => {
    setBusy(true);
    try {
      const data = await api.call('get', '/api/v2/me/export', {});
      downloadBlob(new Blob([JSON.stringify(data, null, 2)], {type: 'application/json'}), `wearhouse-export-${me?.handle ?? 'me'}.json`);
      toast(t('ac.exported'), 'success');
    } catch (e) { fail(e); } finally { setBusy(false); }
  };
  const remove = async () => {
    setBusy(true);
    try {
      await api.call('delete', '/api/v2/me', {body: {confirm: typed.replace(/^@/, '')}});
      await (await loadAuth())?.deleteBrokerUser().catch(() => 'unsupported');
      await signOut(); toast(t('ac.deleted')); navigate('/', {replace: true});
    } catch (e) {
      if (e instanceof ApiFailure && e.code === 'REAUTHENTICATION_REQUIRED') {
        toast(t('ac.reauth'));
        // Remember to resume, then sign out: the private-route guard sends the user to sign-in with this page as the
        // return path, and sign-in brings them back here to confirm.
        try { sessionStorage.setItem(RESUME_KEY, '1'); } catch { /* the user can still confirm again */ }
        await signOut();
      } else fail(e);
    } finally { setBusy(false); }
  };
  return <div className="settings-keys">
    <div className="wr-panel"><h3>{t('ac.export')}</h3><p className="muted">{t('ac.exportBody')}</p>
      <Button loading={busy} onClick={() => void exportData()}><Download size={16} aria-hidden /> {t('ac.export')}</Button></div>
    <div className="wr-panel danger-zone"><h3>{t('ac.delete')}</h3>
      {resumed && <p className="co-alert" role="status">{t('ac.resume')}</p>}
      <p className="muted">{t('ac.deleteBody')}</p>
      <TextField label={t('ac.typeHandle', {handle: me?.handle ?? ''})} value={typed} onChange={e => setTyped(e.target.value)} autoComplete="off" />
      <Button variant="danger" loading={busy} disabled={typed.replace(/^@/, '') !== me?.handle} onClick={() => void remove()}><Trash2 size={16} aria-hidden /> {t('ac.deleteConfirm')}</Button>
    </div>
  </div>;
}
