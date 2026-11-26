import {useRef, useState} from 'react';
import {Link, useNavigate, useParams} from 'react-router';
import {useQueryClient} from '@tanstack/react-query';
import {AlertTriangle, ArrowLeft, Camera, ShieldCheck, Shirt} from 'lucide-react';
import {useI18n} from '../../i18n/index.tsx';
import {useSession} from '../../session/SessionProvider.tsx';
import {ApiFailure} from '../../api/index.ts';
import {useItem, useOwnedItem, useRefresh, useRegistry, type Item} from '../../data/wardrobe.ts';
import {useSizeRegistry} from '../../data/store.ts';
import {Button, Segmented, Select, Skeleton, TextField} from '../../components/ui.tsx';
import {ItemImage} from '../../components/ItemImage.tsx';
import {ErrorState} from '../../components/states.tsx';
import {toast} from '../../components/toast.tsx';
import {ALL_SLOTS, WardrobeNav, itemTitle, useFail, useLabels} from './shared.tsx';

const PHOTO_TYPES = ['image/jpeg', 'image/png', 'image/webp'];
const MAX_PHOTO = 2 * 1024 * 1024;

export function ItemRoute() {
  const {id = ''} = useParams();
  const {t} = useI18n();
  const item = useItem(id);
  return <div className="page wr">
    <WardrobeNav />
    <Link to="/wardrobe" className="wr-back"><ArrowLeft size={18} aria-hidden /> {t('it.back')}</Link>
    {item.isPending ? <Skeleton ratio="3 / 1" /> : item.isError ? <ErrorState error={item.error} onRetry={() => item.refetch()} />
      : <Inspector key={item.data.id} item={item.data} />}
  </div>;
}

function Inspector({item}: {item: Item}) {
  const {t, date} = useI18n();
  const labels = useLabels();
  const {api, userKey} = useSession();
  const qc = useQueryClient();
  const refresh = useRefresh();
  const fail = useFail();
  const navigate = useNavigate();
  const owned = useOwnedItem(item.id, item.verified);
  const registry = useRegistry();
  const sizes = useSizeRegistry();
  const [name, setName] = useState(item.name ?? '');
  const [photoError, setPhotoError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const file = useRef<HTMLInputElement>(null);
  const unknownSlot = item.slot_source === 'unknown';
  const revoked = owned.data?.state === 'revoked_sandbox';

  const patch = async (body: Record<string, unknown>) => {
    try {
      const next = await api.call('patch', '/api/v2/me/wardrobe/items/{item_id}', {path: {item_id: item.id}, body: body as never});
      qc.setQueryData([...userKey, 'wardrobe-item', item.id], next);
      void refresh('wardrobe-items', 'looks');
      toast(t('it.saved'), 'success');
    } catch (e) { fail(e); }
  };
  const upload = async (f: File) => {
    setPhotoError(null);
    if (!PHOTO_TYPES.includes(f.type)) { setPhotoError(t('it.photoType')); return; }
    setUploading(true);
    try {
      // Sizes over 2 MB are sent anyway so the server's own error is shown (it is the authority on the limit).
      const next = await api.call('put', '/api/v2/me/wardrobe/items/{item_id}/photo', {path: {item_id: item.id}, body: f as never});
      qc.setQueryData([...userKey, 'wardrobe-item', item.id], next);
      void refresh('wardrobe-items');
      toast(t('it.saved'), 'success');
    } catch (e) {
      if (e instanceof ApiFailure) setPhotoError(e.status === 413 || f.size > MAX_PHOTO ? `${t('it.photoTooBig')} (${e.message})` : e.message);
      else fail(e);
    } finally { setUploading(false); if (file.current) file.current.value = ''; }
  };
  const slots = registry.data?.slots.map(s => s.slot) ?? [...ALL_SLOTS];
  const sizeSystems = sizes.data?.systems.filter(s => !s.slots.length || s.slots.includes(item.slot)) ?? [];
  const attrs = registry.data?.attributes ?? Object.keys(item.attributes ?? {});

  return <div className="inspector">
    <section className="inspector-media">
      <div className="inspector-image"><ItemImage item={item} /></div>
      {item.kind === 'declared' && <div className="inspector-photo">
        <input ref={file} type="file" accept={PHOTO_TYPES.join(',')} hidden onChange={e => { const f = e.target.files?.[0]; if (f) void upload(f); }} />
        <Button loading={uploading} onClick={() => file.current?.click()}><Camera size={18} aria-hidden /> {item.has_photo ? t('it.replacePhoto') : t('it.uploadPhoto')}</Button>
        <p className={photoError ? 'form-error' : 'muted small'} role={photoError ? 'alert' : undefined}>{photoError ?? t('it.photoHint')}</p>
      </div>}
    </section>
    <section className="inspector-info">
      <p className="eyebrow">{labels.slot(unknownSlot ? null : item.slot)} · {item.verified ? t('wr.verified') : t('wr.declared')}</p>
      <h1>{itemTitle(item)}</h1>
      {revoked && <p className="co-alert" role="alert"><AlertTriangle size={18} aria-hidden /> {t('it.revoked', {reason: owned.data?.revoked_reason ?? ''})}</p>}
      {unknownSlot && <div className="co-alert" role="alert"><AlertTriangle size={18} aria-hidden /> {t('it.unknownSlot')}</div>}
      <div className="buy-actions">
        <Button variant="primary" disabled={unknownSlot || item.archived} title={unknownSlot ? t('fr.needsSlot') : undefined}
          onClick={() => navigate(`/wardrobe/fitting-room?item=${item.id}`)}><Shirt size={18} aria-hidden /> {t('it.tryOn')}</Button>
        {item.product_id && <Link className="btn btn-ghost btn-md" to={`/catalogue/products/${item.product_id}`}>{t('it.viewProduct')}</Link>}
      </div>

      <dl className="product-facts">
        <h2>{t('it.details')}</h2>
        <div><dt>{t('it.name')}</dt><dd className="inline-edit">
          <input aria-label={t('it.name')} value={name} maxLength={120} onChange={e => setName(e.target.value)} />
          {name.trim() && name !== (item.name ?? '') && <Button onClick={() => void patch({name: name.trim()})}>{t('common.save')}</Button>}</dd></div>
        <div><dt>{t('it.slotSource', {source: labels.source(item.slot_source)})}</dt><dd>
          <Select label={t('it.overrideSlot')} value={item.slot_source === 'override' ? item.slot : ''} onChange={e => void patch({slot_override: e.target.value || null})}>
            <option value="">{unknownSlot ? t('fr.pickSlot') : `${t('it.useDefault')}`}</option>
            {slots.map(s => <option key={s} value={s}>{labels.slot(s)}</option>)}
          </Select></dd></div>
        <div><dt>{t('wr.care')}</dt><dd>
          <Segmented label={t('wr.care')} value={item.care_state} onChange={v => void patch({care_state: v})}
            options={(['ready', 'laundry', 'repair', 'stored'] as const).map(c => ({value: c, label: labels.care(c)}))} /></dd></div>
        <div><dt>{item.size_source ? t('it.sizeSource', {source: labels.source(item.size_source)}) : t('wr.size')}</dt><dd>
          {sizeSystems.length ? <Select label={t('wr.size')} value={item.size ? `${item.size.system}:${item.size.code}` : ''}
            onChange={e => { const [system, code] = e.target.value.split(':'); void patch({size: system && code ? {system, code} : null}); }}>
            <option value="">{t('it.noSize')}</option>
            {sizeSystems.map(s => <optgroup key={s.code} label={s.label}>{s.sizes.map(z => <option key={z.code} value={`${s.code}:${z.code}`}>{z.label}</option>)}</optgroup>)}
          </Select> : item.size?.label ?? t('it.noSize')}</dd></div>
        <div><dt>{t('it.wear')}</dt><dd>{item.wear_count ? t('wr.worn', {n: item.wear_count}) : t('wr.neverWorn')}
          {item.last_worn_on && <span className="muted small"> · {t('wr.lastWorn', {date: date(item.last_worn_on)})}</span>}</dd></div>
      </dl>

      <dl className="product-facts">
        <h2>{t('it.attributes')}</h2>
        {attrs.map(a => { const v = item.attributes?.[a]; return <div key={a}><dt>{labels.attr(a)}</dt><dd>
          <Select label={labels.attr(a)} value={v === undefined ? '' : String(v.value)}
            onChange={e => void patch({attributes: {[a]: e.target.value === '' ? null : e.target.value === 'true' ? true : e.target.value === 'false' ? false : e.target.value}})}>
            <option value="">{t('attr.unknown')}</option><option value="true">{t('attr.yes')}</option><option value="false">{t('attr.no')}</option>
            {v && typeof v.value === 'string' && <option value={v.value}>{v.value}</option>}
          </Select>
          {v && <span className="tag tag-quiet">{t('it.origin', {origin: labels.source(v.origin)})}</span>}</dd></div>; })}
      </dl>

      {item.verified && <dl className="product-facts">
        <h2><ShieldCheck size={18} aria-hidden /> {t('it.provenance')}</h2>
        {owned.isPending ? <Skeleton ratio="6 / 1" /> : owned.data && <>
          <div><dt>{t('it.serial')}</dt><dd><code>{owned.data.public_serial}</code> <Link to={`/items/${owned.data.public_serial}`}>{t('tag.title')}</Link></dd></div>
          <div><dt>{t('it.sourceNs')}</dt><dd>{owned.data.acquisition.source_namespace}</dd></div>
          <div><dt>{t('it.externalId')}</dt><dd>{owned.data.acquisition.external_id}</dd></div>
          <div><dt>{t('it.revision')}</dt><dd>{owned.data.acquisition.revision_no}</dd></div>
          <div><dt>{t('it.snapshot')}</dt><dd><code className="small">{owned.data.acquisition.snapshot_sha256.slice(0, 16)}…</code></dd></div>
          <div><dt>{t('it.claimed', {date: ''}).trim()}</dt><dd>{date(owned.data.claimed_at)}</dd></div>
        </>}
      </dl>}

      <Button variant={item.archived ? 'secondary' : 'ghost'} onClick={() => void patch({archived: !item.archived})}>{item.archived ? t('it.unarchive') : t('it.archive')}</Button>
    </section>
  </div>;
}
