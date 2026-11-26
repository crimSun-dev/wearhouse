import {useRef, useState} from 'react';
import {Link, useNavigate, useParams} from 'react-router';
import {useQuery} from '@tanstack/react-query';
import {CalendarDays, History, Shirt, Trash2} from 'lucide-react';
import {useI18n} from '../../i18n/index.tsx';
import {useSession} from '../../session/SessionProvider.tsx';
import {createIntent} from '../../api/index.ts';
import {useLooks} from '../../data/queries.ts';
import {jakartaDate, useLook, useRefresh, type LookRevision} from '../../data/wardrobe.ts';
import {Button, Skeleton} from '../../components/ui.tsx';
import {Overlay} from '../../components/Overlay.tsx';
import {ItemImage} from '../../components/ItemImage.tsx';
import {Silhouette} from '../../components/Silhouette.tsx';
import {EmptyState, ErrorState} from '../../components/states.tsx';
import {Tile} from '../../components/tiles.tsx';
import {toast} from '../../components/toast.tsx';
import {FocusZone, focusItemProps} from '../../focus/FocusZone.tsx';
import {WardrobeNav, itemTitle, useFail, useLabels} from './shared.tsx';

export function LooksRoute() {
  const {t} = useI18n();
  const looks = useLooks();
  return <div className="page wr">
    <WardrobeNav />
    <header className="store-head"><h1>{t('lk.title')}</h1>
      <Link className="btn btn-primary btn-md" to="/wardrobe/fitting-room">{t('fr.newLook')}</Link></header>
    {looks.isPending ? <div className="wr-grid">{Array.from({length: 4}, (_, i) => <Skeleton key={i} ratio="4 / 3" />)}</div>
      : looks.isError ? <ErrorState error={looks.error} onRetry={() => looks.refetch()} />
      : !looks.data.length ? <EmptyState title={t('lk.empty')} body={t('lk.emptyBody')}><Link className="btn btn-primary btn-md" to="/wardrobe/fitting-room">{t('wr.nav.fitting')}</Link></EmptyState>
      : <FocusZone kind="grid" label={t('lk.title')} className="wr-grid wr-grid-wide" version={looks.data.length} autoFocus>
        {looks.data.map(l => { const first = l.current.items.find(i => i.item)?.item; const n = l.current.items.length;
          return <Tile key={l.id} href={`#/wardrobe/looks/${l.id}`} title={l.name} meta={`${t('lk.pieces', {n})} · ${t('lk.revision', {n: l.current_revision_no})}`} ratio="look"
            descriptor={{id: `look:${l.id}`, meta: t('lk.pieces', {n}), actions: [{key: 'Enter', label: t('lk.open')}]}}>
            <span className="look-collage">{l.current.items.slice(0, 4).map((i, k) => <span key={k} className="look-cell">
              {i.item ? <ItemImage item={i.item} quiet /> : <Silhouette slot={i.slot} />}</span>)}
              {!first && !n && <Silhouette slot="top" />}</span>
          </Tile>; })}
      </FocusZone>}
  </div>;
}

export function LookRoute() {
  const {id = ''} = useParams();
  const {t, date} = useI18n();
  const labels = useLabels();
  const {api, userKey} = useSession();
  const navigate = useNavigate();
  const refresh = useRefresh();
  const fail = useFail();
  const look = useLook(id);
  const [viewing, setViewing] = useState<string | null>(null);
  const [renaming, setRenaming] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [busy, setBusy] = useState(false);
  const wearIntent = useRef(createIntent());
  const past = useQuery({queryKey: [...userKey, 'look-revision', viewing], enabled: !!viewing,
    queryFn: ({signal}) => api.call('get', '/api/v2/me/look-revisions/{revision_id}', {signal, path: {revision_id: viewing!}})});
  if (look.isPending) return <div className="page wr"><WardrobeNav /><Skeleton ratio="3 / 1" /></div>;
  if (look.isError) return <div className="page wr"><WardrobeNav /><ErrorState error={look.error} onRetry={() => look.refetch()} /></div>;
  const l = look.data;
  const shown: LookRevision | undefined = viewing ? past.data : l.current;
  const rename = async () => {
    if (!renaming?.trim()) return;
    try { await api.call('patch', '/api/v2/me/looks/{look_id}', {path: {look_id: l.id}, body: {name: renaming.trim()}}); setRenaming(null); toast(t('lk.renamed'), 'success'); await refresh('look', 'looks'); }
    catch (e) { fail(e); }
  };
  const wear = async () => {
    setBusy(true);
    try { await api.call('post', '/api/v2/me/wear', {body: {worn_on: jakartaDate(), look_revision_id: l.current.id}, intent: wearIntent.current}); toast(t('sg.worn'), 'success'); await refresh('wear', 'planner', 'wardrobe-items'); }
    catch (e) { fail(e); } finally { setBusy(false); }
  };
  const remove = async () => {
    setBusy(true);
    try { await api.call('delete', '/api/v2/me/looks/{look_id}', {path: {look_id: l.id}}); toast(t('lk.deleted')); await refresh('looks'); navigate('/wardrobe/looks'); }
    catch (e) { fail(e); } finally { setBusy(false); }
  };
  const revisions = [...(l.revisions ?? [])].sort((a, b) => b.revision_no - a.revision_no);
  return <div className="page wr look-page">
    <WardrobeNav />
    <header className="store-head">
      <div>
        <p className="eyebrow">{t('lk.revision', {n: shown?.revision_no ?? l.current_revision_no})}</p>
        {renaming !== null ? <form className="inline-edit" onSubmit={e => { e.preventDefault(); void rename(); }}>
          <input aria-label={t('lk.rename')} value={renaming} maxLength={80} onChange={e => setRenaming(e.target.value)} autoFocus />
          <Button type="submit" variant="primary">{t('common.save')}</Button><Button onClick={() => setRenaming(null)}>{t('common.cancel')}</Button></form>
          : <h1>{l.name}</h1>}
      </div>
      <div className="buy-actions">
        <Button variant="primary" onClick={() => navigate(`/wardrobe/fitting-room?look=${l.id}`)}><Shirt size={18} aria-hidden /> {t('lk.edit')}</Button>
        <Button onClick={() => navigate(`/wardrobe/planner?look=${l.current.id}`)}><CalendarDays size={18} aria-hidden /> {t('lk.plan')}</Button>
        <Button loading={busy} onClick={() => void wear()}>{t('lk.wear')}</Button>
        {renaming === null && <Button variant="ghost" onClick={() => setRenaming(l.name)}>{t('lk.rename')}</Button>}
        <Button variant="ghost" onClick={() => setConfirmDelete(true)}><Trash2 size={16} aria-hidden /> {t('lk.delete')}</Button>
      </div>
    </header>
    {viewing && <p className="co-alert" role="status"><History size={18} aria-hidden /> {t('lk.viewing', {n: shown?.revision_no ?? ''})}
      <Button variant="ghost" onClick={() => setViewing(null)}>{t('lk.backToCurrent')}</Button></p>}
    <div className="look-layout">
      {!shown ? <Skeleton ratio="3 / 1" /> : <FocusZone kind="grid" label={l.name} className="wr-grid" version={shown.id}>
        {shown.items.map((i, k) => i.item
          ? <Link key={k} to={`/wardrobe/items/${i.item.id}`} className="look-piece" {...focusItemProps({id: `piece:${i.item.id}:${k}`, title: itemTitle(i.item), meta: labels.slot(i.slot)})}>
            <span className="look-piece-img"><ItemImage item={i.item} /></span><span className="tile-title">{itemTitle(i.item)}</span><span className="tile-meta">{labels.slot(i.slot)}</span></Link>
          : <div key={k} className="look-piece is-missing" {...focusItemProps({id: `missing:${k}`, title: t('lk.missing')})} tabIndex={0}>
            <span className="look-piece-img"><Silhouette slot={i.slot} label={t('lk.missing')} /></span><span className="tile-title">{t('lk.missing')}</span><span className="tile-meta">{labels.slot(i.slot)}</span></div>)}
      </FocusZone>}
      <aside className="look-history" aria-label={t('lk.revisions')}>
        <h2><History size={18} aria-hidden /> {t('lk.revisions')}</h2>
        <ol>{revisions.map(r => { const current = r.id === l.current.id; const active = viewing ? viewing === r.id : current;
          return <li key={r.id}><button type="button" className={`wr-side-link ${active ? 'is-active' : ''}`} onClick={() => setViewing(current ? null : r.id)}>
            <span>{t('lk.revision', {n: r.revision_no})}{current && <span className="tag tag-ok">{t('lk.current')}</span>}</span>
            <span className="muted small">{date(r.created_at)}</span></button></li>; })}</ol>
      </aside>
    </div>
    <Overlay open={confirmDelete} onClose={() => setConfirmDelete(false)} side="center" title={t('lk.delete')}>
      <div className="confirm"><h2>{t('lk.delete')}</h2><p>{t('lk.deleteWarn')}</p>
        <div className="buy-actions"><Button data-autofocus onClick={() => setConfirmDelete(false)}>{t('common.back')}</Button>
          <Button variant="danger" loading={busy} onClick={() => void remove()}>{t('lk.delete')}</Button></div></div>
    </Overlay>
  </div>;
}
