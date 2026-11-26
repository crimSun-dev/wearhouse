import {useEffect, useRef, useState, type FormEvent} from 'react';
import {useNavigate} from 'react-router';
import {useQuery, useQueryClient} from '@tanstack/react-query';
import {ArrowDown, ArrowUp, GripVertical, Sparkles, Trash2, Upload} from 'lucide-react';
import {useI18n} from '../../i18n/index.tsx';
import {useSession} from '../../session/SessionProvider.tsx';
import {mediaUrl} from '../../api/index.ts';
import {API_BASE} from '../../session/SessionProvider.tsx';
import {Button, Skeleton, TextField, Toggle} from '../../components/ui.tsx';
import {toast} from '../../components/toast.tsx';
import {useFail} from '../wardrobe/shared.tsx';
import {StaffError} from './Staff.tsx';
import {useStaffKey} from './Catalogue.tsx';

export function MediaScreen({productId}: {productId: string}) {
  const {t} = useI18n();
  const {api} = useSession();
  const navigate = useNavigate();
  const fail = useFail();
  const [pick, setPick] = useState(productId);
  const generateMissing = () => void api.call('post', '/api/v2/admin/catalogue/media/generate-missing', {query: {limit: 200}})
    .then(r => toast(t('md.generated', {n: r.generated, more: r.more_remaining ? t('sz.more') : ''}), 'success'), fail);
  return <>
    <div className="staff-row-head"><h2>{t('sf.media')}</h2><Button onClick={generateMissing}><Sparkles size={16} aria-hidden /> {t('md.generateMissing')}</Button></div>
    <form className="staff-inline" onSubmit={e => { e.preventDefault(); navigate(`/admin/media/${pick.trim()}`); }}>
      <TextField label={t('md.pick')} value={pick} onChange={e => setPick(e.target.value)} placeholder={t('sf.productId')} />
      <Button type="submit">{t('sf.open')}</Button>
    </form>
    {productId && <ProductMedia key={productId} productId={productId} />}
  </>;
}

function ProductMedia({productId}: {productId: string}) {
  const {t} = useI18n();
  const {api} = useSession();
  const qc = useQueryClient();
  const key = useStaffKey();
  const fail = useFail();
  const [removed, setRemoved] = useState(false);
  const [order, setOrder] = useState<string[]>([]);
  const [dragging, setDragging] = useState<string | null>(null);
  const [alt, setAlt] = useState(''); const [rights, setRights] = useState('owned-by-wearhouse'); const file = useRef<HTMLInputElement>(null);
  const media = useQuery({queryKey: key('media', productId, removed),
    queryFn: ({signal}) => api.call('get', '/api/v2/admin/catalogue/products/{product_id}/media', {signal, path: {product_id: productId}, query: {include_removed: removed}})});
  useEffect(() => { if (media.data) setOrder(media.data.filter(m => m.status === 'active').sort((a, b) => a.position - b.position).map(m => m.id)); }, [media.data]);
  if (media.isPending) return <Skeleton ratio="6 / 1" />;
  if (media.isError) return <StaffError error={media.error} onRetry={() => media.refetch()} />;
  const byId = new Map(media.data.map(m => [m.id, m]));
  const refresh = () => qc.invalidateQueries({queryKey: key('media', productId)});
  const saveOrder = (ids: string[]) => void api.call('put', '/api/v2/admin/catalogue/products/{product_id}/media/order', {path: {product_id: productId}, body: {media_ids: ids}})
    .then(() => { toast(t('sf.saved'), 'success'); return refresh(); }, fail);
  const move = (id: string, d: number) => {
    const i = order.indexOf(id), j = i + d;
    if (i < 0 || j < 0 || j >= order.length) return;
    const next = [...order]; [next[i], next[j]] = [next[j]!, next[i]!]; setOrder(next); saveOrder(next);
  };
  const upload = async (e: FormEvent) => {
    e.preventDefault(); const f = file.current?.files?.[0]; if (!f) return;
    try { await api.call('post', '/api/v2/admin/catalogue/products/{product_id}/media', {path: {product_id: productId}, query: {alt, rights_basis: rights}, body: f as never});
      setAlt(''); if (file.current) file.current.value = ''; toast(t('sf.saved'), 'success'); await refresh(); }
    catch (err) { fail(err); }
  };
  const removedItems = media.data.filter(m => m.status === 'removed');
  return <>
    <div className="staff-inline">
      <Button onClick={() => void api.call('post', '/api/v2/admin/catalogue/products/{product_id}/media/generate', {path: {product_id: productId}}).then(refresh, fail)}>
        <Sparkles size={16} aria-hidden /> {t('md.generate')}</Button>
      <Toggle label={t('md.includeRemoved')} checked={removed} onChange={setRemoved} />
    </div>
    <p className="muted small">{t('md.reorderHint')}</p>
    <ol className="media-list" aria-label={t('sf.media')}>{order.map((id, i) => { const m = byId.get(id); if (!m) return null; return <li key={id} draggable
      className={dragging === id ? 'is-dragging' : ''} onDragStart={() => setDragging(id)}
      onDragEnd={() => { setDragging(null); saveOrder(order); }}
      onDragOver={e => { e.preventDefault(); if (dragging && dragging !== id) setOrder(o => { const f = o.indexOf(dragging); const to = o.indexOf(id); const n = [...o]; n.splice(f, 1); n.splice(to, 0, dragging); return n; }); }}>
      <GripVertical size={16} aria-hidden className="grip" />
      <img src={mediaUrl(m.url, API_BASE)} alt={m.alt_text ?? ''} className="media-thumb" />
      <button type="button" className="media-handle" aria-label={`${m.alt_text || m.kind} ${i + 1} / ${order.length}`}
        onKeyDown={e => { if (e.altKey && (e.key === 'ArrowUp' || e.key === 'ArrowDown')) { e.preventDefault(); e.stopPropagation(); move(id, e.key === 'ArrowUp' ? -1 : 1);
          requestAnimationFrame(() => (e.target as HTMLElement).focus()); } }}>{m.kind}{m.generator ? ` · ${m.generator}` : ''}</button>
      <AltEditor id={m.id} value={m.alt_text ?? ''} onSaved={refresh} />
      <span className="shelf-actions">
        <button type="button" aria-label={t('sf.moveUp')} disabled={i === 0} onClick={() => move(id, -1)}><ArrowUp size={16} /></button>
        <button type="button" aria-label={t('sf.moveDown')} disabled={i === order.length - 1} onClick={() => move(id, 1)}><ArrowDown size={16} /></button>
        <button type="button" aria-label={t('sf.remove')} onClick={() => void api.call('delete', '/api/v2/admin/catalogue/media/{media_id}', {path: {media_id: m.id}}).then(refresh, fail)}><Trash2 size={16} /></button>
      </span></li>; })}</ol>
    {removed && removedItems.length > 0 && <ul className="media-list is-removed">{removedItems.map(m => <li key={m.id}><img src={mediaUrl(m.url, API_BASE)} alt="" className="media-thumb" />
      <span className="tag tag-warn">{t('md.removed')}</span><span className="muted small">{m.alt_text}</span></li>)}</ul>}
    <form className="staff-inline" onSubmit={e => void upload(e)}>
      <label className="field"><span className="field-label">{t('md.upload')}</span><input ref={file} type="file" accept="image/jpeg,image/png,image/webp" required /></label>
      <TextField label={t('md.alt')} value={alt} required onChange={e => setAlt(e.target.value)} />
      <TextField label={t('md.rights')} value={rights} required onChange={e => setRights(e.target.value)} />
      <Button type="submit"><Upload size={16} aria-hidden /> {t('md.upload')}</Button>
    </form>
  </>;
}

function AltEditor({id, value, onSaved}: {id: string; value: string; onSaved: () => unknown}) {
  const {t} = useI18n();
  const {api} = useSession();
  const fail = useFail();
  const [v, setV] = useState(value);
  return <span className="inline-edit"><input aria-label={t('md.alt')} value={v} onChange={e => setV(e.target.value)} />
    {v !== value && <Button onClick={() => void api.call('patch', '/api/v2/admin/catalogue/media/{media_id}', {path: {media_id: id}, body: {alt_text: v || null}}).then(onSaved, fail)}>{t('sf.save')}</Button>}</span>;
}
