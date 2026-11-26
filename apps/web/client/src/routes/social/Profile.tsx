import {useEffect, useState, type FormEvent} from 'react';
import {Link, useParams} from 'react-router';
import {useQuery, useQueryClient} from '@tanstack/react-query';
import {Check, ExternalLink} from 'lucide-react';
import {useI18n} from '../../i18n/index.tsx';
import {useSession} from '../../session/SessionProvider.tsx';
import {ApiFailure} from '../../api/index.ts';
import {Button, Segmented, Skeleton, TextField} from '../../components/ui.tsx';
import {EmptyState, ErrorState} from '../../components/states.tsx';
import {toast} from '../../components/toast.tsx';
import {useRefresh} from '../../data/wardrobe.ts';
import {useFail, useLabels} from '../wardrobe/shared.tsx';
import {LookCard, PersonChip, Report} from './Community.tsx';
import './social.css';

const PRESETS = ['plum', 'ivory', 'blush', 'noir', 'sage', 'sky'] as const;

/** One page for blocked, deleted and unknown handles: identical DOM, so nothing leaks which case it is. */
export function ProfileNotFound() {
  const {t} = useI18n();
  return <div className="page profile"><EmptyState title={t('pf.notFound')} body={t('pf.notFoundBody')}><Link to="/">{t('common.goHome')}</Link></EmptyState></div>;
}

export function NotificationsRoute() {
  const {t, date, time} = useI18n();
  const {api, userKey} = useSession();
  const qc = useQueryClient();
  const fail = useFail();
  const list = useQuery({queryKey: [...userKey, 'notifications'], queryFn: ({signal}) => api.call('get', '/api/v2/me/notifications', {signal})});
  const markRead = async () => {
    try {
      const out = await api.call('post', '/api/v2/me/notifications/read', {});
      qc.setQueryData([...userKey, 'unread'], out);
      await qc.invalidateQueries({queryKey: [...userKey, 'notifications']});
    } catch (e) { fail(e); }
  };
  if (list.isPending) return <div className="page"><Skeleton ratio="4 / 1" /></div>;
  if (list.isError) return <div className="page"><ErrorState error={list.error} onRetry={() => list.refetch()} /></div>;
  const unread = list.data.items.some(i => i.unread);
  return <div className="page notifications">
    <header className="store-head"><h1>{t('nt.title')}</h1>{unread && <Button onClick={() => void markRead()}><Check size={16} aria-hidden /> {t('nt.markRead')}</Button>}</header>
    {!list.data.items.length ? <EmptyState title={t('nt.empty')} /> : <ul className="note-list">{list.data.items.map((n, k) => <li key={k}
      className={`note ${n.unread ? 'is-unread' : ''} note-${n.kind}`}>
      {n.unread && <span className="note-dot" aria-label={t('nt.unread')} />}
      <span className="note-text">{t(`nt.${n.kind}` as 'nt.friend_request', {handle: n.account.handle ?? n.account.display_name})}</span>
      <span className="muted small">{date(n.at)} {time(n.at)}</span>
      <Link to={n.kind === 'friend_shared_look' ? '/community' : n.kind === 'friend_request' ? '/community?tab=friends' : `/u/${n.account.handle}`}>{t('nt.open')}</Link>
    </li>)}</ul>}
  </div>;
}

export function PublicProfileRoute() {
  const {handle = ''} = useParams();
  const {t, lang} = useI18n();
  // member_since is month precision: show "November 2026", never an invented day.
  const monthYear = (v: string) => new Intl.DateTimeFormat(lang === 'id' ? 'id-ID' : 'en-GB', {month: 'long', year: 'numeric', timeZone: 'Asia/Jakarta'}).format(new Date(`${v.slice(0, 7)}-15T12:00:00+07:00`));
  const {api, userKey, status} = useSession();
  const [reporting, setReporting] = useState<string | null>(null);
  const anonymous = status !== 'ready';
  const key = [...(anonymous ? ['public'] : userKey), 'profile', handle];
  const profile = useQuery({queryKey: key, retry: false,
    queryFn: ({signal}) => api.call('get', '/api/v2/profiles/{handle}', {signal, anonymous, path: {handle}})});
  const ok = profile.isSuccess;
  const visible = ok && profile.data.sections != null;
  const showcase = useQuery({queryKey: [...key, 'showcase'], enabled: visible, retry: false,
    queryFn: ({signal}) => api.call('get', '/api/v2/profiles/{handle}/showcase', {signal, anonymous, path: {handle}})});
  const shares = useQuery({queryKey: [...key, 'shares'], enabled: visible, retry: false,
    queryFn: ({signal}) => api.call('get', '/api/v2/profiles/{handle}/shares', {signal, anonymous, path: {handle}})});
  const wardrobe = useQuery({queryKey: [...key, 'wardrobe'], enabled: visible, retry: false,
    queryFn: ({signal}) => api.call('get', '/api/v2/profiles/{handle}/wardrobe', {signal, anonymous, path: {handle}})});
  const friends = useQuery({queryKey: [...key, 'friends'], enabled: visible, retry: false,
    queryFn: ({signal}) => api.call('get', '/api/v2/profiles/{handle}/friends', {signal, anonymous, path: {handle}})});
  const week = useQuery({queryKey: [...key, 'week'], enabled: visible && !anonymous, retry: false,
    queryFn: ({signal}) => api.call('get', '/api/v2/profiles/{handle}/week', {signal, path: {handle}})});
  if (profile.isPending) return <div className="page profile"><Skeleton ratio="4 / 1" /></div>;
  if (profile.isError) return profile.error instanceof ApiFailure && profile.error.status === 404 ? <ProfileNotFound />
    : <div className="page"><ErrorState error={profile.error} onRetry={() => profile.refetch()} /></div>;
  const p = profile.data;
  const accent = showcase.data?.accent ?? p.avatar.preset ?? 'plum';
  return <div className={`page profile accent-${accent}`} data-testid="profile">
    <header className="profile-head">
      <span className={`profile-avatar sw-${p.avatar.preset ?? 'plum'}`} aria-hidden />
      <div><h1>{p.display_name}</h1>{p.handle && <p className="muted">@{p.handle}</p>}
        {p.member_since && <p className="muted small">{t('pf.memberSince', {date: monthYear(p.member_since)})}</p>}</div>
    </header>
    {p.bio && <p className="profile-bio">{p.bio}</p>}
    {!visible ? <p className="co-alert">{p.profile_visibility === 'private' ? t('pf.private') : t('pf.friendsOnly')}</p> : <>
      {showcase.data && (showcase.data.headline || showcase.data.featured.length > 0) && <section className="profile-showcase">
        {showcase.data.headline && <h2>{showcase.data.headline}</h2>}
        <div className="share-grid">{showcase.data.featured.map(s => s.look && <article key={s.id} className="share"><p className="eyebrow">{t('pf.featured')}</p>
          {s.caption && <p className="share-caption">{s.caption}</p>}<LookCard look={s.look} /></article>)}</div>
      </section>}
      {!!shares.data?.items.length && <section><h2>{t('pf.shares')}</h2><div className="share-grid">{shares.data.items.map(s => <article key={s.id} className="share">
        {s.caption && <p className="share-caption">{s.caption}</p>}{s.look && <LookCard look={s.look} />}
        {!anonymous && <Button variant="ghost" onClick={() => setReporting(s.id)}>{t('cm.report')}</Button>}</article>)}</div></section>}
      {wardrobe.isSuccess && wardrobe.data.items.length > 0 && <section data-section="wardrobe"><h2>{t('pf.wardrobe')}</h2>
        <ul className="chip-list">{wardrobe.data.items.map((w, k) => <li key={k}><Link to={`/catalogue/products/${w.product.id}`}>{w.product.name}</Link></li>)}</ul></section>}
      {friends.isSuccess && friends.data.friends.length > 0 && <section><h2>{t('pf.friends')}</h2>
        <ul className="person-list">{friends.data.friends.map(f => <li key={f.handle ?? f.display_name} className="person-row"><PersonChip card={f} /></li>)}</ul></section>}
      {week.isSuccess && week.data.days.some(d => d.look) && <section><h2>{t('pf.week')}</h2><WeekStrip days={week.data.days} /></section>}
    </>}
    {reporting && <Report shareId={reporting} onClose={() => setReporting(null)} />}
  </div>;
}

function WeekStrip({days}: {days: Array<{date: string; look: {look_name: string} | null; occasion: string | null}>}) {
  const {t, date} = useI18n();
  const labels = useLabels();
  return <ol className="week-strip">{days.map(d => <li key={d.date}><span className="muted small">{date(d.date)}</span>
    <strong>{d.look?.look_name ?? t('pf.nothingPlanned')}</strong>{d.occasion && <span className="muted small">{labels.occasion(d.occasion)}</span>}</li>)}</ol>;
}

export function ProfileEditRoute() {
  const {t, errorText} = useI18n();
  const {api, userKey, me, refresh: refreshSession} = useSession();
  const refresh = useRefresh();
  const fail = useFail();
  const own = useQuery({queryKey: [...userKey, 'own-profile'], queryFn: ({signal}) => api.call('get', '/api/v2/me/profile', {signal})});
  const showcase = useQuery({queryKey: [...userKey, 'my-showcase'], queryFn: ({signal}) => api.call('get', '/api/v2/me/showcase', {signal})});
  const shares = useQuery({queryKey: [...userKey, 'my-shares'], queryFn: ({signal}) => api.call('get', '/api/v2/me/shares', {signal})});
  const sharing = useQuery({queryKey: [...userKey, 'plan-sharing'], queryFn: ({signal}) => api.call('get', '/api/v2/me/plan-sharing', {signal})});
  const week = useQuery({queryKey: [...userKey, 'own-week'], enabled: !!me?.handle,
    queryFn: ({signal}) => api.call('get', '/api/v2/profiles/{handle}/week', {signal, path: {handle: me!.handle!}})});
  const [form, setForm] = useState({display_name: '', bio: '', handle: '', preset: 'plum'});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [show, setShow] = useState({headline: '', accent: 'plum', featured: [] as string[]});
  useEffect(() => { if (own.data) setForm({display_name: own.data.display_name, bio: own.data.bio, handle: own.data.handle ?? '', preset: own.data.avatar.preset ?? 'plum'}); }, [own.data]);
  useEffect(() => { if (showcase.data) setShow({headline: showcase.data.headline ?? '', accent: showcase.data.accent, featured: showcase.data.featured}); }, [showcase.data]);
  const saveProfile = async (e: FormEvent) => {
    e.preventDefault(); setErrors({});
    try {
      const body: Record<string, unknown> = {display_name: form.display_name.trim(), bio: form.bio.trim(), avatar: {kind: 'preset', preset: form.preset}};
      if (form.handle.replace(/^@/, '') !== (own.data?.handle ?? '')) body.handle = form.handle.replace(/^@/, '');
      await api.call('patch', '/api/v2/me/profile', {body: body as never});
      toast(t('pf.saved'), 'success'); await refresh('own-profile'); await refreshSession();
    } catch (err) {
      if (err instanceof ApiFailure && ['HANDLE_UNAVAILABLE', 'HANDLE_CHANGE_TOO_SOON'].includes(err.code)) setErrors({handle: errorText(err.code, err.message)});
      else if (err instanceof ApiFailure && err.fieldErrors.length) setErrors(Object.fromEntries((err.fieldErrors as Array<{field: string; message: string}>).map(f => [f.field.split('.').pop()!, f.message])));
      else fail(err);
    }
  };
  const saveShowcase = async () => {
    try { await api.call('put', '/api/v2/me/showcase', {body: {headline: show.headline.trim() || null, accent: show.accent as never, featured_share_ids: show.featured}}); toast(t('pf.saved'), 'success'); await refresh('my-showcase'); }
    catch (e) { fail(e); }
  };
  const setSharing = async (audience: 'none' | 'friends') => {
    try { await api.call('put', '/api/v2/me/plan-sharing', {body: {audience}}); await refresh('plan-sharing'); } catch (e) { fail(e); }
  };
  if (own.isPending) return <div className="page"><Skeleton ratio="4 / 1" /></div>;
  if (own.isError) return <div className="page"><ErrorState error={own.error} onRetry={() => own.refetch()} /></div>;
  return <div className="page profile-edit">
    <header className="store-head"><h1>{t('pf.editTitle')}</h1>
      {own.data.handle && <Link className="btn btn-ghost btn-md" to={`/u/${own.data.handle}`}><ExternalLink size={16} aria-hidden /> {t('pf.view')}</Link>}</header>
    <form className="wr-panel profile-form" onSubmit={e => void saveProfile(e)}>
      <TextField label={t('pf.displayName')} value={form.display_name} maxLength={60} onChange={e => setForm(f => ({...f, display_name: e.target.value}))} error={errors.display_name} />
      <TextField label={t('pf.handle')} value={form.handle} maxLength={31} hint={t('pf.handleRules')} error={errors.handle} pattern="@?[A-Za-z0-9_]{3,30}"
        onChange={e => setForm(f => ({...f, handle: e.target.value}))} />
      <TextField label={t('pf.bio')} value={form.bio} maxLength={280} onChange={e => setForm(f => ({...f, bio: e.target.value}))} error={errors.bio} />
      <fieldset className="swatches"><legend className="field-label">{t('pf.avatar')}</legend>
        {PRESETS.map(id => <label key={id} className={`swatch sw-${id}`}><input type="radio" name="avatar" value={id} checked={form.preset === id}
          onChange={() => setForm(f => ({...f, preset: id}))} /><span className="swatch-dot" aria-hidden /><span className="visually-hidden">{id}</span></label>)}
      </fieldset>
      <Button type="submit" variant="primary">{t('common.save')}</Button>
    </form>
    <section className="wr-panel"><h2>{t('pf.showcase')}</h2>
      <TextField label={t('pf.headline')} value={show.headline} maxLength={80} onChange={e => setShow(s => ({...s, headline: e.target.value}))} />
      <Segmented label={t('pf.accent')} value={show.accent} onChange={v => setShow(s => ({...s, accent: v}))} options={PRESETS.map(p => ({value: p, label: p}))} />
      <fieldset className="wear-items"><legend className="field-label">{t('pf.featuredPick')}</legend>
        {(shares.data ?? []).map(s => <label key={s.id} className="wear-check"><input type="checkbox" checked={show.featured.includes(s.id)}
          disabled={!show.featured.includes(s.id) && show.featured.length >= 6}
          onChange={e => setShow(x => ({...x, featured: e.target.checked ? [...x.featured, s.id] : x.featured.filter(i => i !== s.id)}))} />
          {s.look?.look_name ?? s.id}{s.caption ? ` · ${s.caption}` : ''}</label>)}
      </fieldset>
      <Button variant="primary" onClick={() => void saveShowcase()}>{t('common.save')}</Button>
    </section>
    <section className="wr-panel"><h2>{t('pf.planSharing')}</h2>
      <Segmented label={t('pf.planSharing')} value={sharing.data?.audience ?? 'none'} onChange={v => void setSharing(v)}
        options={[{value: 'none', label: t('pf.planNone')}, {value: 'friends', label: t('pf.planFriends')}]} />
      {sharing.data?.audience === 'friends' && week.data && <><h3>{t('pf.weekPreview')}</h3><WeekStrip days={week.data.days} /></>}
    </section>
  </div>;
}

/** #/shares/:id: one shared look, as the server projects it for this viewer (signed out sees public shares only). */
export function ShareRoute() {
  const {id = ''} = useParams();
  const {t, date} = useI18n();
  const {api, userKey, status} = useSession();
  const anonymous = status !== 'ready';
  const share = useQuery({queryKey: [...(anonymous ? ['public'] : userKey), 'share', id], retry: false,
    queryFn: ({signal}) => api.call('get', '/api/v2/shares/{share_id}', {signal, anonymous, path: {share_id: id}})});
  if (share.isPending) return <div className="page"><Skeleton ratio="4 / 1" /></div>;
  if (share.isError) return share.error instanceof ApiFailure && share.error.status === 404 ? <ProfileNotFound />
    : <div className="page"><ErrorState error={share.error} onRetry={() => share.refetch()} /></div>;
  const s = share.data;
  return <div className="page profile"><article className="share">
    <header>{s.owner && <PersonChip card={s.owner} />}<span className="muted small">{date(s.created_at)}</span></header>
    {s.caption && <p className="share-caption">{s.caption}</p>}
    {s.look && <LookCard look={s.look} />}
    {!anonymous && <Link to="/community">{t('cm.title')}</Link>}
  </article></div>;
}
