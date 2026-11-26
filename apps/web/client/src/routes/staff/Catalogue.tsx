import {useEffect, useState, type FormEvent} from 'react';
import {Link, useNavigate} from 'react-router';
import {useQuery, useQueryClient} from '@tanstack/react-query';
import {ArrowDown, ArrowUp, Plus, Trash2, X} from 'lucide-react';
import {useI18n} from '../../i18n/index.tsx';
import {useSession} from '../../session/SessionProvider.tsx';
import {Button, Select, Skeleton, TextField, Toggle} from '../../components/ui.tsx';
import {Overlay} from '../../components/Overlay.tsx';
import {toast} from '../../components/toast.tsx';
import {useFail} from '../wardrobe/shared.tsx';
import {StaffError} from './Staff.tsx';

const today = () => new Date().toISOString().slice(0, 10);
const text = (v: unknown) => (v == null ? '' : String(v));
export function useStaffKey() { const {userKey} = useSession(); return (...k: unknown[]) => [...userKey, 'staff', ...k]; }

export function ReviewScreen() {
  const {t} = useI18n();
  const {api} = useSession();
  const key = useStaffKey();
  const review = useQuery({queryKey: key('review'), queryFn: ({signal}) => api.call('get', '/api/v2/admin/catalogue/review', {signal, query: {limit: 200}})});
  if (review.isPending) return <Skeleton ratio="6 / 1" />;
  if (review.isError) return <StaffError error={review.error} onRetry={() => review.refetch()} />;
  return <><h2>{t('sf.review')}</h2>
    {!review.data.length ? <p className="muted">{t('sf.none')}</p> : <table className="staff-table">
      <thead><tr><th>{t('sf.product')}</th><th>{t('in.externalId')}</th><th>{t('rv.state')}</th><th>{t('rv.latest')}</th><th>{t('rv.published')}</th><th /></tr></thead>
      <tbody>{review.data.map(r => <tr key={r.product_id}><td>{r.name ?? '—'}</td><td><code>{r.namespace}/{r.external_id}</code></td><td><span className="tag tag-quiet">{r.publication_state}</span></td>
        <td>{r.latest_revision_no}</td><td>{r.published_revision_no ?? '—'}</td><td><Link to={`/admin/products/${r.product_id}`}>{t('sf.open')}</Link></td></tr>)}</tbody>
    </table>}</>;
}

export function ProductScreen({id}: {id: string}) {
  const {t} = useI18n();
  const {api} = useSession();
  const qc = useQueryClient();
  const key = useStaffKey();
  const fail = useFail();
  const [retiring, setRetiring] = useState(false);
  const product = useQuery({queryKey: key('product', id), enabled: !!id,
    queryFn: ({signal}) => api.call('get', '/api/v2/admin/catalogue/products/{product_id}', {signal, path: {product_id: id}})});
  const sizes = useQuery({queryKey: key('product-sizes', id), enabled: !!id,
    queryFn: ({signal}) => api.call('get', '/api/v2/admin/catalogue/products/{product_id}/sizes', {signal, path: {product_id: id}})});
  const registry = useQuery({queryKey: key('size-registry'), queryFn: ({signal}) => api.call('get', '/api/v2/admin/catalogue/sizes', {signal})});
  const [addSize, setAddSize] = useState('');
  if (product.isPending) return <Skeleton ratio="6 / 1" />;
  if (product.isError) return <StaffError error={product.error} onRetry={() => product.refetch()} />;
  const p = product.data;
  const refresh = () => qc.invalidateQueries({queryKey: key()});
  const publish = (revision_id: string, n: number) => void api.call('post', '/api/v2/admin/catalogue/products/{product_id}/publish', {path: {product_id: id}, body: {revision_id}})
    .then(() => { toast(t('rv.publishedOk', {n}), 'success'); return refresh(); }, fail);
  const retire = () => void api.call('post', '/api/v2/admin/catalogue/products/{product_id}/retire', {path: {product_id: id}})
    .then(() => { setRetiring(false); toast(t('rv.retired')); return refresh(); }, fail);
  const putSizes = (list: Array<{system: string; code: string}>) => void api.call('put', '/api/v2/admin/catalogue/products/{product_id}/sizes', {path: {product_id: id}, body: {sizes: list}})
    .then(() => { toast(t('sf.saved'), 'success'); return refresh(); }, fail);
  const current = sizes.data?.sizes ?? [];
  return <>
    <div className="staff-row-head"><h2>{text(p.revisions.at(-1)?.facts && (p.revisions.at(-1)!.facts as Record<string, {value?: unknown}>).product_name?.value) || p.id}</h2>
      <span className="tag tag-quiet">{p.publication_state}</span>
      <Link className="btn btn-ghost btn-md" to={`/admin/media/${p.id}`}>{t('rv.mediaLink')}</Link>
      {p.publication_state !== 'retired' && <Button variant="danger" onClick={() => setRetiring(true)}>{t('rv.retire')}</Button>}</div>
    <p className="muted small"><code>{p.source.namespace}/{p.source.external_id}</code> · {p.source.name}</p>
    <h3>{t('rv.revisions')}</h3>
    <table className="staff-table"><thead><tr><th>#</th><th>{t('rv.facts')}</th><th>{t('sf.status')}</th><th /></tr></thead>
      <tbody>{[...p.revisions].reverse().map(r => <tr key={r.id}><td>{r.revision_no}</td>
        <td className="small">{Object.entries(r.facts as Record<string, {value?: unknown}>).map(([k, v]) => `${k}: ${text(v?.value)}`).join(' · ')}</td>
        <td>{r.id === p.published_revision_id ? <span className="tag tag-ok">{t('rv.published')}</span> : r.id === p.current_revision_id ? <span className="tag tag-quiet">{t('rv.latest')}</span> : ''}</td>
        <td>{r.id !== p.published_revision_id && p.publication_state !== 'retired' && <Button onClick={() => publish(r.id, r.revision_no)}>{t('rv.publish')}</Button>}</td></tr>)}</tbody></table>
    <h3>{t('rv.sizes')}</h3>
    {sizes.data?.one_size || !current.length ? <p className="muted">{t('rv.oneSize')}</p> : null}
    <ul className="chip-row">{current.map(s => <li key={s.system + s.code} className="tag tag-quiet">{s.label} <span className="muted small">({s.origin})</span>
      <button type="button" className="chip-x" aria-label={`${t('sf.remove')} ${s.label}`} onClick={() => putSizes(current.filter(x => x !== s))}><X size={12} /></button></li>)}</ul>
    <div className="staff-inline">
      <Select label={t('rv.addSize')} value={addSize} onChange={e => setAddSize(e.target.value)}>
        <option value="">—</option>{registry.data?.systems.map(s => <optgroup key={s.code} label={s.label}>{s.sizes.map(z => <option key={z.code} value={`${s.code}:${z.code}`}>{z.label}</option>)}</optgroup>)}
      </Select>
      <Button disabled={!addSize} onClick={() => { const [system, code] = addSize.split(':') as [string, string]; putSizes([...current.map(s => ({system: s.system, code: s.code})), {system, code}]); setAddSize(''); }}>
        <Plus size={16} aria-hidden /> {t('rv.addSize')}</Button>
    </div>
    <Overlay open={retiring} onClose={() => setRetiring(false)} side="center" title={t('rv.retire')}>
      <div className="confirm"><p>{t('rv.retireWarn')}</p><div className="buy-actions"><Button data-autofocus onClick={() => setRetiring(false)}>{t('sf.cancel')}</Button>
        <Button variant="danger" onClick={retire}>{t('rv.retire')}</Button></div></div>
    </Overlay>
  </>;
}

type Provenance = {namespace: string; name: string; url: string; acquired: string; basis: string; scope: string; acceptedOn: string; acceptedBy: string; terms: string};
function ProvenanceFields({v, set}: {v: Provenance; set: (p: Provenance) => void}) {
  const {t} = useI18n();
  const f = (k: keyof Provenance, label: string, type = 'text') => <TextField label={label} type={type} required value={v[k]} onChange={e => set({...v, [k]: e.target.value})} />;
  return <>
    <fieldset className="staff-fieldset"><legend>{t('im.source')}</legend>{f('namespace', t('im.namespace'))}{f('name', t('im.name'))}{f('url', t('im.url'), 'url')}</fieldset>
    <fieldset className="staff-fieldset"><legend>{t('im.permission')}</legend>{f('basis', t('im.basis'))}{f('scope', t('im.scope'))}{f('acceptedOn', t('im.acceptedOn'), 'date')}
      {f('acceptedBy', t('im.acceptedBy'))}{f('terms', t('im.terms'), 'url')}</fieldset>
  </>;
}
const blankProvenance = (): Provenance => ({namespace: 'wearhouse-synthetic-demo', name: 'Wearhouse synthetic demo catalogue', url: 'https://wearhouse.invalid/demo',
  acquired: today(), basis: 'synthetic-demo-fixture', scope: 'public demo; synthetic records only', acceptedOn: today(), acceptedBy: '', terms: 'https://wearhouse.invalid/demo/terms'});
const provenanceBody = (v: Provenance, file: string, sha: string) => ({
  source: {namespace: v.namespace, name: v.name, url: v.url}, snapshot: {sha256: sha, file_name: file, acquired_on: v.acquired},
  permission: {basis: v.basis, scope: v.scope, accepted_on: v.acceptedOn, accepted_by: v.acceptedBy, terms_url: v.terms}});
async function sha256(data: ArrayBuffer | string) {
  const bytes = typeof data === 'string' ? new TextEncoder().encode(data) : new Uint8Array(data);
  return [...new Uint8Array(await crypto.subtle.digest('SHA-256', bytes))].map(b => b.toString(16).padStart(2, '0')).join('');
}

export function ImportsScreen({jobId}: {jobId: string}) {
  const {t} = useI18n();
  const {api} = useSession();
  const navigate = useNavigate();
  const key = useStaffKey();
  const fail = useFail();
  const [v, setV] = useState(blankProvenance);
  const [file, setFile] = useState<{name: string; text: string; sha: string} | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const job = useQuery({queryKey: key('job', jobId), enabled: !!jobId,
    queryFn: ({signal}) => api.call('get', '/api/v2/admin/catalogue/import-jobs/{job_id}', {signal, path: {job_id: jobId}})});
  const pick = async (f: File) => {
    setError(null);
    if (f.size > 10 * 1024 * 1024) { setError(t('im.tooBig')); return; }
    const text = await f.text();
    setFile({name: f.name, text, sha: await sha256(text)});
  };
  const start = async (e: FormEvent) => {
    e.preventDefault(); if (!file) return; setBusy(true);
    try { const out = await api.call('post', '/api/v2/admin/catalogue/import-jobs', {body: {csv: file.text, mapping: 'hm-articles@1', ...provenanceBody(v, file.name, file.sha)}}); navigate(`/admin/imports/${out.id}`); }
    catch (err) { fail(err); } finally { setBusy(false); }
  };
  const publishJob = () => void api.call('post', '/api/v2/admin/catalogue/import-jobs/{job_id}/publish', {path: {job_id: jobId}})
    .then(r => toast(t('im.publishedJob', {n: r.published, already: r.already_published, skipped: r.retired_skipped}), 'success'), fail);
  if (jobId) {
    if (job.isPending) return <Skeleton ratio="6 / 1" />;
    if (job.isError) return <StaffError error={job.error} onRetry={() => job.refetch()} />;
    const j = job.data;
    return <><div className="staff-row-head"><h2>{t('im.job')}</h2><span className="tag tag-quiet">{j.status}</span><span className="muted">{t('im.rows', {n: j.row_count})}</span>
      <span className="muted small">{Object.entries(j.totals).map(([k, n]) => `${k} ${n}`).join(' · ')}</span>
      <Button variant="primary" onClick={publishJob}>{t('im.publishJob')}</Button></div>
      <table className="staff-table" data-testid="job-rows"><thead><tr><th>{t('im.row')}</th><th>{t('in.externalId')}</th><th>{t('im.outcome')}</th><th>{t('im.errors')}</th></tr></thead>
        <tbody>{j.rows.map(r => <tr key={r.row_no} className={r.outcome === 'rejected' ? 'is-rejected' : ''}><td>{r.row_no}</td><td>{r.external_id ?? '—'}</td>
          <td><span className={`tag ${r.outcome === 'rejected' ? 'tag-warn' : 'tag-quiet'}`}>{r.outcome}</span></td>
          <td className="small">{(r.errors as Array<{field?: string; message?: string}>).map((e, k) => <div key={k}>{e.field ? `${e.field}: ` : ''}{e.message ?? JSON.stringify(e)}</div>)}</td></tr>)}</tbody></table></>;
  }
  return <form className="staff-form" onSubmit={e => void start(e)}>
    <h2>{t('sf.imports')}</h2>
    <label className="field"><span className="field-label">{t('im.file')}</span><input type="file" accept=".csv,text/csv" required onChange={e => { const f = e.target.files?.[0]; if (f) void pick(f); }} /></label>
    {error && <p className="form-error" role="alert">{error}</p>}
    {file && <p className="muted small">{t('im.sha')}: <code>{file.sha}</code></p>}
    <TextField label={t('im.acquired')} type="date" value={v.acquired} onChange={e => setV({...v, acquired: e.target.value})} />
    <ProvenanceFields v={v} set={setV} />
    <Button type="submit" variant="primary" loading={busy} disabled={!file}>{t('im.start')}</Button>
  </form>;
}

export function IngestScreen() {
  const {t} = useI18n();
  const {api} = useSession();
  const navigate = useNavigate();
  const fail = useFail();
  const [v, setV] = useState(blankProvenance);
  const [p, setP] = useState({externalId: '', name: '', category: '', colour: '', slot: ''});
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const record = {article_id: p.externalId, prod_name: p.name, product_type_name: p.category, colour_group_name: p.colour};
    try {
      const out = await api.call('post', '/api/v2/admin/source-products', {body: {
        ...provenanceBody(v, 'single-ingest.json', await sha256(JSON.stringify(record))), external_id: p.externalId, original_fields: record,
        facts: {product_name: {value: p.name, source_field: 'prod_name'}, category: {value: p.category, source_field: 'product_type_name'},
          ...(p.colour ? {colour: {value: p.colour, source_field: 'colour_group_name'}} : {})},
        ...(p.slot ? {annotations: {slot: {value: p.slot, origin: 'rule', note: 'staff single ingest'}}} : {}),
      }});
      toast(t('in.done', {n: out.revision_no}), 'success'); navigate(`/admin/products/${out.product_id}`);
    } catch (err) { fail(err); }
  };
  const f = (k: keyof typeof p, label: string, required = true) => <TextField label={label} required={required} value={p[k]} onChange={e => setP({...p, [k]: e.target.value})} />;
  return <form className="staff-form" onSubmit={e => void submit(e)}>
    <h2>{t('sf.ingest')}</h2>
    {f('externalId', t('in.externalId'))}{f('name', t('in.productName'))}{f('category', t('in.category'))}{f('colour', t('in.colour'), false)}
    <Select label={t('in.slot')} value={p.slot} onChange={e => setP({...p, slot: e.target.value})}><option value="">—</option>
      {['top', 'outer', 'bottom', 'dress', 'footwear', 'accessory', 'bag', 'headwear'].map(s => <option key={s} value={s}>{s}</option>)}</Select>
    <ProvenanceFields v={v} set={setV} />
    <Button type="submit" variant="primary">{t('in.submit')}</Button>
  </form>;
}

export function CollectionsScreen() {
  const {t} = useI18n();
  const {api} = useSession();
  const qc = useQueryClient();
  const key = useStaffKey();
  const fail = useFail();
  const list = useQuery({queryKey: key('collections'), queryFn: ({signal}) => api.call('get', '/api/v2/admin/catalogue/collections', {signal})});
  const [edit, setEdit] = useState<{slug: string; title: string; ids: string[]; names: Record<string, string>} | null>(null);
  const [q, setQ] = useState('');
  const search = useQuery({queryKey: key('collection-search', q), enabled: q.length >= 2,
    queryFn: ({signal}) => api.call('get', '/api/v2/catalogue/products', {signal, anonymous: true, query: {q, limit: 10}})});
  if (list.isPending) return <Skeleton ratio="6 / 1" />;
  if (list.isError) return <StaffError error={list.error} onRetry={() => list.refetch()} />;
  const save = () => edit && void api.call('put', '/api/v2/admin/catalogue/collections/{slug}', {path: {slug: edit.slug}, body: {title: edit.title, product_ids: edit.ids}})
    .then(() => { toast(t('sf.saved'), 'success'); setEdit(null); return qc.invalidateQueries({queryKey: key('collections')}); }, fail);
  const move = (i: number, d: number) => edit && setEdit({...edit, ids: (() => { const n = [...edit.ids]; const j = i + d; if (j < 0 || j >= n.length) return n; [n[i], n[j]] = [n[j]!, n[i]!]; return n; })()});
  return <>
    <div className="staff-row-head"><h2>{t('sf.collections')}</h2><Button onClick={() => setEdit({slug: '', title: '', ids: [], names: {}})}><Plus size={16} aria-hidden /> {t('co.new')}</Button></div>
    <table className="staff-table"><thead><tr><th>{t('co.slug')}</th><th>{t('co.titleField')}</th><th>{t('co.products')}</th><th /></tr></thead>
      <tbody>{list.data.map(c => <tr key={c.slug}><td><code>{c.slug}</code></td><td>{c.title}</td><td>{c.items.length}</td>
        <td><Button onClick={() => setEdit({slug: c.slug, title: c.title, ids: c.items.map(i => i.id), names: Object.fromEntries(c.items.map(i => [i.id, i.name ?? i.id]))})}>{t('sf.open')}</Button>
          <Button variant="ghost" onClick={() => void api.call('delete', '/api/v2/admin/catalogue/collections/{slug}', {path: {slug: c.slug}}).then(() => qc.invalidateQueries({queryKey: key('collections')}), fail)}>
            <Trash2 size={16} aria-label={t('co.deleteCollection')} /></Button></td></tr>)}</tbody></table>
    {edit && <Overlay open onClose={() => setEdit(null)} side="right" title={edit.title || t('co.new')}>
      <div className="wr-panel">
        <TextField label={t('co.slug')} value={edit.slug} pattern="[a-z0-9-]+" required onChange={e => setEdit({...edit, slug: e.target.value})} data-autofocus />
        <TextField label={t('co.titleField')} value={edit.title} required onChange={e => setEdit({...edit, title: e.target.value})} />
        <h3>{t('co.products')}</h3>
        <ol className="shelf-order">{edit.ids.map((id, i) => <li key={id}><span className="shelf-item">{edit.names[id] ?? id}</span><span className="shelf-actions">
          <button type="button" aria-label={t('sf.moveUp')} disabled={i === 0} onClick={() => move(i, -1)}><ArrowUp size={16} /></button>
          <button type="button" aria-label={t('sf.moveDown')} disabled={i === edit.ids.length - 1} onClick={() => move(i, 1)}><ArrowDown size={16} /></button>
          <button type="button" aria-label={t('sf.remove')} onClick={() => setEdit({...edit, ids: edit.ids.filter(x => x !== id)})}><X size={16} /></button></span></li>)}</ol>
        <TextField label={t('co.addProduct')} value={q} onChange={e => setQ(e.target.value)} type="search" />
        <ul className="person-list">{search.data?.items.filter(p => !edit.ids.includes(p.id)).map(p => <li key={p.id} className="person-row"><span>{p.name}</span>
          <Button onClick={() => setEdit({...edit, ids: [...edit.ids, p.id], names: {...edit.names, [p.id]: p.name ?? p.id}})}><Plus size={14} aria-hidden /></Button></li>)}</ul>
        <Button variant="primary" disabled={!edit.slug || !edit.title} onClick={save}>{t('sf.save')}</Button>
      </div>
    </Overlay>}
  </>;
}

export function SizesScreen() {
  const {t} = useI18n();
  const {api} = useSession();
  const qc = useQueryClient();
  const key = useStaffKey();
  const fail = useFail();
  const reg = useQuery({queryKey: key('size-registry'), queryFn: ({signal}) => api.call('get', '/api/v2/admin/catalogue/sizes', {signal})});
  const [sys, setSys] = useState({code: '', label: '', position: 100, slots: '', active: true});
  const [val, setVal] = useState({system: '', code: '', label: '', rank: 100, common: true, active: true});
  useEffect(() => { if (!val.system && reg.data?.systems[0]) setVal(v => ({...v, system: reg.data!.systems[0]!.code})); }, [reg.data, val.system]);
  if (reg.isPending) return <Skeleton ratio="6 / 1" />;
  if (reg.isError) return <StaffError error={reg.error} onRetry={() => reg.refetch()} />;
  const done = () => { toast(t('sf.saved'), 'success'); return qc.invalidateQueries({queryKey: key('size-registry')}); };
  const putSystem = (e: FormEvent) => { e.preventDefault(); void api.call('put', '/api/v2/admin/catalogue/size-systems/{code}', {path: {code: sys.code},
    body: {label: sys.label, position: Number(sys.position), slots: sys.slots.split(',').map(s => s.trim()).filter(Boolean), active: sys.active}}).then(done, fail); };
  const putValue = (e: FormEvent) => { e.preventDefault(); void api.call('put', '/api/v2/admin/catalogue/size-systems/{code}/sizes/{size_code}', {path: {code: val.system, size_code: val.code},
    body: {label: val.label, rank: Number(val.rank), common: val.common, active: val.active}}).then(done, fail); };
  const assign = () => void api.call('post', '/api/v2/admin/catalogue/sizes/assign-missing', {query: {limit: 500}})
    .then(r => toast(t('sz.assigned', {n: r.assigned, more: r.more_remaining ? t('sz.more') : ''}), 'success'), fail);
  return <>
    <div className="staff-row-head"><h2>{t('sf.sizes')}</h2><Button onClick={assign}>{t('sz.assign')}</Button></div>
    <table className="staff-table"><thead><tr><th>{t('sz.system')}</th><th>{t('sz.slots')}</th><th>{t('sf.status')}</th><th>{t('sz.label')}</th></tr></thead>
      <tbody>{reg.data.systems.map(s => <tr key={s.code}><td><code>{s.code}</code> {s.label}</td><td className="small">{s.slots.join(', ')}</td>
        <td>{s.active === false ? '—' : t('sz.active')}</td><td className="small">{s.sizes.map(z => `${z.label}${z.common ? '' : '*'}${z.active === false ? ' (off)' : ''}`).join(' · ')}</td></tr>)}</tbody></table>
    <div className="staff-split">
      <form className="staff-form" onSubmit={putSystem}><h3>{t('sz.addSystem')}</h3>
        <TextField label={t('sz.code')} required value={sys.code} onChange={e => setSys({...sys, code: e.target.value})} />
        <TextField label={t('sz.label')} required value={sys.label} onChange={e => setSys({...sys, label: e.target.value})} />
        <TextField label={t('sz.position')} type="number" value={String(sys.position)} onChange={e => setSys({...sys, position: Number(e.target.value)})} />
        <TextField label={t('sz.slots')} value={sys.slots} onChange={e => setSys({...sys, slots: e.target.value})} />
        <Toggle label={t('sz.active')} checked={sys.active} onChange={a => setSys({...sys, active: a})} />
        <Button type="submit" variant="primary">{t('sf.save')}</Button></form>
      <form className="staff-form" onSubmit={putValue}><h3>{t('sz.addValue')}</h3>
        <Select label={t('sz.system')} value={val.system} onChange={e => setVal({...val, system: e.target.value})}>{reg.data.systems.map(s => <option key={s.code} value={s.code}>{s.label}</option>)}</Select>
        <TextField label={t('sz.code')} required maxLength={8} value={val.code} onChange={e => setVal({...val, code: e.target.value})} />
        <TextField label={t('sz.label')} required value={val.label} onChange={e => setVal({...val, label: e.target.value})} />
        <TextField label={t('sz.rank')} type="number" value={String(val.rank)} onChange={e => setVal({...val, rank: Number(e.target.value)})} />
        <Toggle label={t('sz.common')} checked={val.common} onChange={c => setVal({...val, common: c})} />
        <Toggle label={t('sz.active')} checked={val.active} onChange={a => setVal({...val, active: a})} />
        <Button type="submit" variant="primary">{t('sf.save')}</Button></form>
    </div>
  </>;
}

