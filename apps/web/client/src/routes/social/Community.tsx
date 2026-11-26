import {useRef, useState, type FormEvent} from 'react';
import {Link, useSearchParams} from 'react-router';
import {useInfiniteQuery, useQuery} from '@tanstack/react-query';
import {BookmarkPlus, Copy, Flag, Search, ShieldBan, Trash2, UserMinus, UserPlus} from 'lucide-react';
import {useI18n} from '../../i18n/index.tsx';
import {useSession} from '../../session/SessionProvider.tsx';
import {ApiFailure, createIntent} from '../../api/index.ts';
import {useLooks} from '../../data/queries.ts';
import {useRefresh} from '../../data/wardrobe.ts';
import {Button, Select, Skeleton, Tabs, TextField} from '../../components/ui.tsx';
import {Overlay} from '../../components/Overlay.tsx';
import {EmptyState, ErrorState} from '../../components/states.tsx';
import {toast} from '../../components/toast.tsx';
import type {Schemas} from '@wearhouse/contracts';
import {useFail, useLabels} from '../wardrobe/shared.tsx';
import './social.css';

type Share = Schemas['ShareOut'];
type ProjectedLook = Schemas['ProjectedLookOut'];
type Card = Schemas['Card'];
type Tab = 'feed' | 'inspirations' | 'friends' | 'shares';

export function PersonChip({card}: {card: {display_name: string; handle: string | null; avatar: {kind: string; preset?: string | null}}}) {
  return <span className="person"><span className={`person-dot sw-${card.avatar.preset ?? 'plum'}`} aria-hidden />
    {card.handle ? <Link to={`/u/${card.handle}`}>{card.display_name}</Link> : <span>{card.display_name}</span>}
    {card.handle && <span className="muted small">@{card.handle}</span>}</span>;
}

/** A shared look as the server projected it. Pieces never become the viewer's own items. */
export function LookCard({look, owned}: {look: ProjectedLook; owned?: boolean}) {
  const {t} = useI18n();
  const labels = useLabels();
  return <div className="look-card">
    <p className="look-card-name">{look.look_name} <span className="muted small">· {t('cm.pieces', {n: look.items.length})}</span></p>
    <ul className="look-card-items">{look.items.map((i, k) => <li key={k}>
      <span className="muted small">{labels.slot(i.slot)}</span>
      <span>{i.name ?? i.category ?? '—'}{i.colour && <span className="muted small"> · {i.colour}</span>}</span>
      {i.verified && <span className="tag tag-ok">{t('cm.verified')}</span>}
      {!owned && (i.product_id ? <Link to={`/catalogue/products/${i.product_id}`}>{t('cm.find')}</Link>
        : <Link to={`/catalogue?q=${encodeURIComponent(i.name ?? i.category ?? '')}`}>{t('cm.find')}</Link>)}
    </li>)}</ul>
  </div>;
}

export function audienceLabel(t: (k: never) => string, a: string | null | undefined) {
  return a === 'public' ? t('cm.audiencePublic' as never) : a === 'friends' ? t('cm.audienceFriends' as never) : t('cm.audiencePrivate' as never);
}

export function CommunityRoute() {
  const {t} = useI18n();
  const [params, setParams] = useSearchParams();
  const tab = (params.get('tab') as Tab | null) ?? 'feed';
  return <div className="page community">
    <header className="store-head"><h1>{t('cm.title')}</h1></header>
    <Tabs label={t('cm.title')} value={tab} onChange={v => setParams(new URLSearchParams({tab: v}), {replace: true})}
      tabs={[{value: 'feed', label: t('cm.feed')}, {value: 'inspirations', label: t('cm.inspirations')}, {value: 'friends', label: t('cm.friends')}, {value: 'shares', label: t('cm.shares')}]} />
    {tab === 'feed' ? <Feed /> : tab === 'inspirations' ? <Inspirations /> : tab === 'friends' ? <Friends /> : <MyShares />}
  </div>;
}

function Feed() {
  const {t, date} = useI18n();
  const {api, userKey} = useSession();
  const refresh = useRefresh();
  const fail = useFail();
  const [reporting, setReporting] = useState<string | null>(null);
  const feed = useInfiniteQuery({queryKey: [...userKey, 'feed-page'], initialPageParam: undefined as string | undefined,
    queryFn: ({signal, pageParam}) => api.call('get', '/api/v2/me/feed', {signal, query: {limit: 20, ...(pageParam ? {cursor: pageParam} : {})}}),
    getNextPageParam: last => last.next_cursor ?? undefined});
  if (feed.isPending) return <Skeleton ratio="4 / 1" />;
  if (feed.isError) return <ErrorState error={feed.error} onRetry={() => feed.refetch()} />;
  const items = feed.data.pages.flatMap(p => p.items);
  if (!items.length) return <EmptyState title={t('cm.feedEmpty')} body={t('cm.feedEmptyBody')}><Link className="btn btn-secondary" to="/community?tab=friends">{t('cm.friends')}</Link></EmptyState>;
  const save = async (id: string) => {
    try { await api.call('post', '/api/v2/me/inspirations', {body: {share_id: id}}); toast(t('cm.saved'), 'success'); await refresh('inspirations'); } catch (e) { fail(e); }
  };
  return <>
    <ul className="share-list">{items.map(s => <li key={s.id} className="share">
      <header>{s.owner && <PersonChip card={s.owner} />}<span className="muted small">{date(s.created_at)}</span></header>
      {s.caption && <p className="share-caption">{s.caption}</p>}
      {s.look && <LookCard look={s.look} />}
      <div className="buy-actions">
        <Button onClick={() => void save(s.id)}><BookmarkPlus size={16} aria-hidden /> {t('cm.save')}</Button>
        <Button variant="ghost" onClick={() => setReporting(s.id)}><Flag size={16} aria-hidden /> {t('cm.report')}</Button>
      </div>
    </li>)}</ul>
    {feed.hasNextPage && <div className="store-more"><Button loading={feed.isFetchingNextPage} onClick={() => void feed.fetchNextPage()}>{t('cm.loadMore')}</Button></div>}
    {reporting && <Report shareId={reporting} onClose={() => setReporting(null)} />}
  </>;
}

export function Report({shareId, onClose}: {shareId: string; onClose: () => void}) {
  const {t, errorText} = useI18n();
  const {api} = useSession();
  const fail = useFail();
  const [reason, setReason] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const send = async (e: FormEvent) => {
    e.preventDefault(); setBusy(true); setError(null);
    try { await api.call('post', '/api/v2/shares/{share_id}/report', {path: {share_id: shareId}, body: {reason: reason.trim()}}); toast(t('rp.sent'), 'success'); onClose(); }
    catch (err) { if (err instanceof ApiFailure && err.code === 'ALREADY_REPORTED') setError(errorText(err.code, err.message)); else fail(err); }
    finally { setBusy(false); }
  };
  return <Overlay open onClose={onClose} side="center" title={t('rp.title')}>
    <form className="confirm" onSubmit={e => void send(e)}>
      <TextField label={t('rp.reason')} value={reason} required maxLength={500} onChange={e => setReason(e.target.value)} error={error ?? undefined} data-autofocus />
      <div className="buy-actions"><Button onClick={onClose}>{t('common.cancel')}</Button>
        <Button type="submit" variant="primary" loading={busy} disabled={!reason.trim()}>{t('rp.send')}</Button></div>
    </form>
  </Overlay>;
}

function Inspirations() {
  const {t, date} = useI18n();
  const {api, userKey} = useSession();
  const refresh = useRefresh();
  const fail = useFail();
  const list = useQuery({queryKey: [...userKey, 'inspirations'], queryFn: ({signal}) => api.call('get', '/api/v2/me/inspirations', {signal})});
  if (list.isPending) return <Skeleton ratio="4 / 1" />;
  if (list.isError) return <ErrorState error={list.error} onRetry={() => list.refetch()} />;
  if (!list.data.items.length) return <EmptyState title={t('cm.insEmpty')} body={t('cm.insEmptyBody')} />;
  return <>
    <p className="muted small">{t('cm.notGranted')}</p>
    <ul className="share-list">{list.data.items.map(i => <li key={i.id} className="share">
      <header>{i.from && <span>{t('cm.from', {name: ''})}<PersonChip card={i.from} /></span>}<span className="muted small">{date(i.saved_at)}</span></header>
      {i.caption && <p className="share-caption">{i.caption}</p>}
      {i.look && <LookCard look={i.look} />}
      <Button variant="ghost" onClick={() => void api.call('delete', '/api/v2/me/inspirations/{inspiration_id}', {path: {inspiration_id: i.id}})
        .then(() => { toast(t('cm.removed')); return refresh('inspirations'); }, fail)}><Trash2 size={16} aria-hidden /> {t('cm.remove')}</Button>
    </li>)}</ul>
  </>;
}

function Friends() {
  const {t, errorText} = useI18n();
  const {api, userKey, me} = useSession();
  const refresh = useRefresh();
  const fail = useFail();
  const [q, setQ] = useState('');
  const [term, setTerm] = useState('');
  const [blocking, setBlocking] = useState<string | null>(null);
  const [sendError, setSendError] = useState<Record<string, string>>({});
  const intents = useRef(new Map<string, ReturnType<typeof createIntent>>());
  const search = useQuery({queryKey: [...userKey, 'user-search', term], enabled: term.length >= 2,
    queryFn: ({signal}) => api.call('get', '/api/v2/users/search', {signal, query: {q: term}})});
  const incoming = useQuery({queryKey: [...userKey, 'requests', 'incoming'], queryFn: ({signal}) => api.call('get', '/api/v2/me/friend-requests', {signal, query: {direction: 'incoming'}})});
  const outgoing = useQuery({queryKey: [...userKey, 'requests', 'outgoing'], queryFn: ({signal}) => api.call('get', '/api/v2/me/friend-requests', {signal, query: {direction: 'outgoing'}})});
  const friends = useQuery({queryKey: [...userKey, 'friends'], queryFn: ({signal}) => api.call('get', '/api/v2/me/friends', {signal})});
  const blocks = useQuery({queryKey: [...userKey, 'blocks'], queryFn: ({signal}) => api.call('get', '/api/v2/me/blocks', {signal})});
  const after = (msg: string) => { toast(msg, 'success'); return refresh('requests', 'friends', 'blocks', 'user-search', 'feed-page'); };
  const request = async (handle: string) => {
    setSendError(e => ({...e, [handle]: ''}));
    if (!intents.current.has(handle)) intents.current.set(handle, createIntent());
    try {
      const out = await api.call('post', '/api/v2/me/friend-requests', {body: {handle}, intent: intents.current.get(handle)!});
      await after(out.status === 'accepted' ? t('fd.accepted') : t('fd.requested'));
    } catch (e) {
      if (e instanceof ApiFailure && e.status < 500) setSendError(s => ({...s, [handle]: errorText(e.code, e.message)})); else fail(e);
    }
  };
  const act = (fn: () => Promise<unknown>, msg: string) => () => void fn().then(() => after(msg), fail);
  const row = (c: Card, actions: React.ReactNode, key?: string) => <li key={key ?? c.handle ?? c.display_name} className="person-row">
    <PersonChip card={c} /><span className="buy-actions">{actions}</span>
    {c.handle && sendError[c.handle] && <p className="form-error" role="alert">{sendError[c.handle]}</p>}</li>;
  return <div className="friends">
    <section className="friends-me">
      <span className="muted small">{t('fd.myHandle')}</span><code>@{me?.handle}</code>
      <Button variant="ghost" onClick={() => void navigator.clipboard.writeText(`@${me?.handle ?? ''}`).then(() => toast(t('fd.copied')))}><Copy size={16} aria-hidden /> {t('fd.copy')}</Button>
      <span className="muted small">{t('fd.limits')}</span>
    </section>
    <form className="friends-search" role="search" onSubmit={e => { e.preventDefault(); setTerm(q.trim().replace(/^@/, '')); }}>
      <TextField label={t('fd.search')} value={q} onChange={e => setQ(e.target.value)} />
      <Button type="submit"><Search size={16} aria-hidden /> {t('fd.searchGo')}</Button>
    </form>
    {term && (search.isPending ? <Skeleton ratio="8 / 1" /> : search.data && (!search.data.results.length ? <p className="muted">{t('fd.noResults')}</p>
      : <ul className="person-list">{search.data.results.filter(c => c.handle !== me?.handle).map(c => row(c, <>
        <Button variant="primary" onClick={() => void request(c.handle!)}><UserPlus size={16} aria-hidden /> {t('fd.add')}</Button>
        <Button variant="ghost" onClick={() => setBlocking(c.handle)}><ShieldBan size={16} aria-hidden /> {t('fd.block')}</Button></>))}</ul>))}
    <section><h2>{t('fd.incoming')}</h2>
      {!incoming.data?.requests.length ? <p className="muted">{t('fd.noRequests')}</p> : <ul className="person-list">{incoming.data.requests.map(r => row(r.account, <>
        <Button variant="primary" onClick={act(() => api.call('post', '/api/v2/me/friend-requests/{request_id}/accept', {path: {request_id: r.request_id}}), t('fd.accepted'))}>{t('fd.accept')}</Button>
        <Button onClick={act(() => api.call('post', '/api/v2/me/friend-requests/{request_id}/decline', {path: {request_id: r.request_id}}), t('fd.decline'))}>{t('fd.decline')}</Button></>, r.request_id))}</ul>}
    </section>
    <section><h2>{t('fd.outgoing')}</h2>
      {!outgoing.data?.requests.length ? <p className="muted">{t('fd.noRequests')}</p> : <ul className="person-list">{outgoing.data.requests.map(r => row(r.account,
        <Button onClick={act(() => api.call('delete', '/api/v2/me/friend-requests/{request_id}', {path: {request_id: r.request_id}}), t('fd.cancelReq'))}>{t('fd.cancelReq')}</Button>, r.request_id))}</ul>}
    </section>
    <section><h2>{t('fd.list')}</h2>
      {!friends.data?.friends.length ? <p className="muted">{t('fd.none')}</p> : <ul className="person-list">{friends.data.friends.map(c => row(c, <>
        <Button variant="ghost" onClick={act(() => api.call('delete', '/api/v2/me/friends/{handle}', {path: {handle: c.handle!}}), t('fd.removeFriend'))}><UserMinus size={16} aria-hidden /> {t('fd.removeFriend')}</Button>
        <Button variant="ghost" onClick={() => setBlocking(c.handle)}><ShieldBan size={16} aria-hidden /> {t('fd.block')}</Button></>))}</ul>}
    </section>
    <section><h2>{t('fd.blocks')}</h2>
      {!blocks.data?.blocks.length ? <p className="muted">{t('fd.noBlocks')}</p> : <ul className="person-list">{blocks.data.blocks.map(c => row(c,
        <Button onClick={act(() => api.call('delete', '/api/v2/me/blocks/{handle}', {path: {handle: c.handle!}}), t('fd.unblocked'))}>{t('fd.unblock')}</Button>))}</ul>}
    </section>
    <Overlay open={!!blocking} onClose={() => setBlocking(null)} side="center" title={t('fd.blockTitle', {handle: blocking ?? ''})}>
      <div className="confirm"><p>{t('fd.blockWarn')}</p>
        <div className="buy-actions"><Button data-autofocus onClick={() => setBlocking(null)}>{t('common.cancel')}</Button>
          <Button variant="danger" onClick={() => { const h = blocking!; setBlocking(null); void api.call('put', '/api/v2/me/blocks/{handle}', {path: {handle: h}}).then(() => after(t('fd.blocked')), fail); }}>{t('fd.block')}</Button></div></div>
    </Overlay>
  </div>;
}

function MyShares() {
  const {t, date} = useI18n();
  const {api, userKey} = useSession();
  const refresh = useRefresh();
  const fail = useFail();
  const looks = useLooks();
  const shares = useQuery({queryKey: [...userKey, 'my-shares'], queryFn: ({signal}) => api.call('get', '/api/v2/me/shares', {signal})});
  const [look, setLook] = useState('');
  const [audience, setAudience] = useState<'friends' | 'public'>('friends');
  const [caption, setCaption] = useState('');
  const [editing, setEditing] = useState<Share | null>(null);
  const create = async (e: FormEvent) => {
    e.preventDefault();
    try { await api.call('post', '/api/v2/me/shares', {body: {look_id: look || looks.data![0]!.id, audience, caption: caption.trim() || null}}); setCaption(''); toast(t('ss.shared'), 'success'); await refresh('my-shares'); }
    catch (err) { fail(err); }
  };
  const patch = (id: string, body: Schemas['SharePatch'], msg: string) => void api.call('patch', '/api/v2/me/shares/{share_id}', {path: {share_id: id}, body})
    .then(() => { toast(msg, 'success'); setEditing(null); return refresh('my-shares'); }, fail);
  return <div className="my-shares">
    {!looks.data?.length ? <p className="muted">{t('ss.noLooks')}</p> : <form className="store-filters" onSubmit={e => void create(e)}>
      <Select label={t('ss.look')} value={look || looks.data[0]!.id} onChange={e => setLook(e.target.value)}>{looks.data.map(l => <option key={l.id} value={l.id}>{l.name}</option>)}</Select>
      <Select label={t('ss.audience')} value={audience} onChange={e => setAudience(e.target.value as 'friends' | 'public')}>
        <option value="friends">{t('cm.audienceFriends')}</option><option value="public">{t('cm.audiencePublic')}</option></Select>
      <TextField label={t('ss.caption')} value={caption} maxLength={280} onChange={e => setCaption(e.target.value)} />
      <Button type="submit" variant="primary">{t('ss.share')}</Button>
    </form>}
    {shares.isPending ? <Skeleton ratio="4 / 1" /> : shares.isError ? <ErrorState error={shares.error} onRetry={() => shares.refetch()} />
      : !shares.data.length ? <p className="muted">{t('ss.noShares')}</p>
      : <ul className="share-list">{shares.data.map(s => <li key={s.id} className="share">
        <header><span className="tag tag-quiet">{audienceLabel(t as never, s.audience)}</span>
          <span className={`tag ${s.effective_audience !== s.audience ? 'tag-warn' : 'tag-quiet'}`}>{t('ss.effective', {audience: audienceLabel(t as never, s.effective_audience)})}</span>
          {s.moderation === 'hidden' && <span className="tag tag-warn">{t('ss.hidden')}</span>}
          <span className="muted small">{date(s.created_at)}</span></header>
        {s.effective_audience && s.effective_audience !== s.audience && <p className="muted small">{t('ss.narrower')}</p>}
        {s.caption && <p className="share-caption">{s.caption}</p>}
        {s.look && <LookCard look={s.look} owned />}
        <div className="buy-actions">
          <Button onClick={() => setEditing(s)}>{t('ss.edit')}</Button>
          <Button variant="ghost" onClick={() => patch(s.id, {repin: true}, t('ss.repinned'))}>{t('ss.repin')}</Button>
          <Button variant="ghost" onClick={() => void api.call('delete', '/api/v2/me/shares/{share_id}', {path: {share_id: s.id}}).then(() => { toast(t('ss.deletedShare')); return refresh('my-shares'); }, fail)}>
            <Trash2 size={16} aria-hidden /> {t('ss.deleteShare')}</Button>
        </div>
      </li>)}</ul>}
    {editing && <EditShare share={editing} onClose={() => setEditing(null)} onSave={(body) => patch(editing.id, body, t('it.saved'))} />}
  </div>;
}

function EditShare({share, onClose, onSave}: {share: Share; onClose: () => void; onSave: (b: Schemas['SharePatch']) => void}) {
  const {t} = useI18n();
  const [audience, setAudience] = useState(share.audience);
  const [caption, setCaption] = useState(share.caption ?? '');
  return <Overlay open onClose={onClose} side="center" title={t('ss.edit')}>
    <form className="confirm" onSubmit={e => { e.preventDefault(); onSave({audience, caption: caption.trim() || null}); }}>
      <Select label={t('ss.audience')} value={audience} onChange={e => setAudience(e.target.value as typeof audience)} data-autofocus>
        <option value="friends">{t('cm.audienceFriends')}</option><option value="public">{t('cm.audiencePublic')}</option></Select>
      <TextField label={t('ss.caption')} value={caption} maxLength={280} onChange={e => setCaption(e.target.value)} />
      <div className="buy-actions"><Button onClick={onClose}>{t('common.cancel')}</Button><Button type="submit" variant="primary">{t('common.save')}</Button></div>
    </form>
  </Overlay>;
}
