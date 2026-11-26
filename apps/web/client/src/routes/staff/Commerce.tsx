import {useMemo, useRef, useState, type FormEvent} from 'react';
import {useInfiniteQuery, useQuery, useQueryClient} from '@tanstack/react-query';
import {renderSVG} from 'uqr';
import {Copy, Eye, EyeOff, Plus, Printer, RefreshCw, Trash2} from 'lucide-react';
import {useI18n} from '../../i18n/index.tsx';
import {useSession} from '../../session/SessionProvider.tsx';
import {createIntent} from '../../api/index.ts';
import {Button, Select, Skeleton, TextField, Toggle} from '../../components/ui.tsx';
import {Overlay} from '../../components/Overlay.tsx';
import {toast} from '../../components/toast.tsx';
import type {Schemas} from '@wearhouse/contracts';
import {useFail} from '../wardrobe/shared.tsx';
import {StaffError} from './Staff.tsx';
import {useStaffKey} from './Catalogue.tsx';

type Offer = Schemas['StaffOfferOut'];

export function OffersScreen() {
  const {t, idr} = useI18n();
  const {api} = useSession();
  const qc = useQueryClient();
  const key = useStaffKey();
  const fail = useFail();
  const offers = useQuery({queryKey: key('offers'), queryFn: ({signal}) => api.call('get', '/api/v2/admin/commerce/offers', {signal})});
  const [editing, setEditing] = useState<Offer | {product_id: string} | null>(null);
  const [rules, setRules] = useState([{category: '', slot: '', price_idr: 199000, stock: 10}]);
  const [overwrite, setOverwrite] = useState(false);
  const [results, setResults] = useState<Schemas['BulkRuleResultOut'][] | null>(null);
  const [newId, setNewId] = useState('');
  if (offers.isPending) return <Skeleton ratio="6 / 1" />;
  if (offers.isError) return <StaffError error={offers.error} onRetry={() => offers.refetch()} />;
  const refresh = () => qc.invalidateQueries({queryKey: key('offers')});
  const bulk = (e: FormEvent) => {
    e.preventDefault();
    void api.call('post', '/api/v2/admin/commerce/offers/bulk', {body: {overwrite, rules: rules.map(r => ({category: r.category || null, slot: r.slot || null, price_idr: Number(r.price_idr), stock: Number(r.stock)}))}})
      .then(r => { setResults(r.results); return refresh(); }, fail);
  };
  return <>
    <div className="staff-row-head"><h2>{t('sf.offers')}</h2><span className="tag tag-quiet">{t('sf.sandbox')}</span>
      <form className="staff-inline" onSubmit={e => { e.preventDefault(); if (newId.trim()) setEditing({product_id: newId.trim()}); }}>
        <TextField label={t('sf.productId')} value={newId} onChange={e => setNewId(e.target.value)} /><Button type="submit"><Plus size={16} aria-hidden /> {t('of.edit')}</Button></form></div>
    <table className="staff-table"><thead><tr><th>{t('sf.product')}</th><th>{t('of.price')}</th><th>{t('of.stock')}</th><th>{t('of.sizeStock')}</th><th>{t('of.onSale')}</th><th /></tr></thead>
      <tbody>{offers.data.map(o => <tr key={o.product_id}><td>{o.name ?? o.product_id}</td><td>{idr(o.price_idr)}</td><td>{o.stock}</td>
        <td className="small">{o.sizes?.map(s => `${s.label} ${s.stock}`).join(' · ') ?? '—'}</td><td>{o.on_sale ? '✓' : '—'}</td>
        <td><Button onClick={() => setEditing(o)}>{t('of.edit')}</Button>
          <Button variant="ghost" onClick={() => void api.call('delete', '/api/v2/admin/commerce/offers/{product_id}', {path: {product_id: o.product_id}}).then(() => { toast(t('of.removed')); return refresh(); }, fail)}>
            <Trash2 size={16} aria-label={t('sf.remove')} /></Button></td></tr>)}</tbody></table>
    <form className="staff-form" onSubmit={bulk}><h3>{t('of.bulk')}</h3>
      {rules.map((r, i) => <div key={i} className="staff-inline">
        <TextField label={`${t('of.rule')} ${i + 1}: ${t('in.category')}`} value={r.category} onChange={e => setRules(rs => rs.map((x, k) => (k === i ? {...x, category: e.target.value} : x)))} />
        <TextField label={t('in.slot')} value={r.slot} onChange={e => setRules(rs => rs.map((x, k) => (k === i ? {...x, slot: e.target.value} : x)))} />
        <TextField label={t('of.price')} type="number" value={String(r.price_idr)} onChange={e => setRules(rs => rs.map((x, k) => (k === i ? {...x, price_idr: Number(e.target.value)} : x)))} />
        <TextField label={t('of.stock')} type="number" value={String(r.stock)} onChange={e => setRules(rs => rs.map((x, k) => (k === i ? {...x, stock: Number(e.target.value)} : x)))} />
      </div>)}
      <div className="staff-inline"><Button onClick={() => setRules(rs => [...rs, {category: '', slot: '', price_idr: 199000, stock: 10}])}><Plus size={16} aria-hidden /> {t('of.addRule')}</Button>
        <Toggle label={t('of.overwrite')} checked={overwrite} onChange={setOverwrite} /><Button type="submit" variant="primary">{t('of.apply')}</Button></div>
      {results && <ul className="person-list">{results.map((r, k) => <li key={k} className="person-row">{t('of.results', {category: r.category ?? '', slot: r.slot ? ` / ${r.slot}` : '', matched: r.matched, written: r.written})}</li>)}</ul>}
    </form>
    {editing && <OfferEditor offer={editing} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); void refresh(); }} />}
  </>;
}

function OfferEditor({offer, onClose, onSaved}: {offer: Offer | {product_id: string}; onClose: () => void; onSaved: () => void}) {
  const {t} = useI18n();
  const {api} = useSession();
  const fail = useFail();
  const existing = 'price_idr' in offer ? offer : null;
  const [price, setPrice] = useState(existing?.price_idr ?? 199000);
  const [stock, setStock] = useState(existing?.stock ?? 10);
  const [sizeStock, setSizeStock] = useState<Record<string, number>>(Object.fromEntries((existing?.sizes ?? []).map(s => [s.code, s.stock])));
  const save = (e: FormEvent) => {
    e.preventDefault();
    void api.call('put', '/api/v2/admin/commerce/offers/{product_id}', {path: {product_id: offer.product_id},
      body: {currency: 'IDR', price_idr: Number(price), stock: Number(stock), size_stock: Object.keys(sizeStock).length ? sizeStock : null}}).then(() => { toast(t('sf.saved'), 'success'); onSaved(); }, fail);
  };
  return <Overlay open onClose={onClose} side="right" title={t('of.edit')}>
    <form className="wr-panel" onSubmit={save}><p className="muted small"><code>{offer.product_id}</code></p>
      <TextField label={t('of.price')} type="number" value={String(price)} onChange={e => setPrice(Number(e.target.value))} data-autofocus />
      <TextField label={t('of.stock')} type="number" value={String(stock)} onChange={e => setStock(Number(e.target.value))} />
      {Object.keys(sizeStock).length > 0 && <fieldset className="staff-fieldset"><legend>{t('of.sizeStock')}</legend>
        {Object.entries(sizeStock).map(([code, n]) => <TextField key={code} label={code} type="number" value={String(n)} onChange={e => setSizeStock(s => ({...s, [code]: Number(e.target.value)}))} />)}</fieldset>}
      <Button type="submit" variant="primary">{t('sf.save')}</Button></form>
  </Overlay>;
}

export function OrdersScreen() {
  const {t, idr, date} = useI18n();
  const {api} = useSession();
  const key = useStaffKey();
  const [status, setStatus] = useState('');
  const orders = useInfiniteQuery({queryKey: key('orders', status), initialPageParam: undefined as string | undefined,
    queryFn: ({signal, pageParam}) => api.call('get', '/api/v2/admin/commerce/orders', {signal, query: {limit: 50, ...(status ? {status} : {}), ...(pageParam ? {cursor: pageParam} : {})}}),
    getNextPageParam: last => last.next_cursor ?? undefined});
  return <>
    <div className="staff-row-head"><h2>{t('sf.orders')}</h2><span className="tag tag-quiet">{t('sf.sandbox')}</span>
      <Select label={t('sf.status')} value={status} onChange={e => setStatus(e.target.value)}><option value="">{t('od.all')}</option><option value="fulfilled">fulfilled</option><option value="cancelled">cancelled</option></Select></div>
    <p className="muted small">{t('od.noKeys')}</p>
    {orders.isPending ? <Skeleton ratio="6 / 1" /> : orders.isError ? <StaffError error={orders.error} onRetry={() => orders.refetch()} /> : <>
      <table className="staff-table"><thead><tr><th>{t('od.buyer')}</th><th>{t('sf.status')}</th><th>{t('od.items')}</th><th>{t('od.total')}</th><th /></tr></thead>
        <tbody>{orders.data.pages.flatMap(p => p.items).map(o => <tr key={o.id}><td>{o.buyer_handle ? `@${o.buyer_handle}` : '—'}</td><td><span className="tag tag-quiet">{o.status}</span></td>
          <td className="small">{o.lines.map(l => `${l.quantity}× ${l.product_name}${l.size ? ` (${l.size.label})` : ''}`).join(', ')}</td><td>{idr(o.total_idr)}</td><td className="small">{date(o.created_at)}</td></tr>)}</tbody></table>
      {orders.hasNextPage && <Button loading={orders.isFetchingNextPage} onClick={() => void orders.fetchNextPage()}>{t('sf.loadMore')}</Button>}</>}
  </>;
}

/** Printable tag: the QR encodes only the public tag URL. The activation key never goes into it. */
export function tagUrl(serial: string) { return `${location.origin}${location.pathname}#/items/${serial}`; }
export function TagQr({serial}: {serial: string}) {
  const svg = useMemo(() => renderSVG(tagUrl(serial), {border: 2}), [serial]);
  return <figure className="tag-print" data-testid="tag-qr" data-url={tagUrl(serial)}>
    <span className="tag-qr" dangerouslySetInnerHTML={{__html: svg}} />
    <figcaption><strong>Wearhouse</strong><code>{serial}</code></figcaption>
  </figure>;
}

export function UnitsScreen() {
  const {t, date} = useI18n();
  const {api, me} = useSession();
  const key = useStaffKey();
  const fail = useFail();
  const canIssue = me?.capabilities.includes('inventory:issue');
  const [filter, setFilter] = useState('');
  const [form, setForm] = useState({product: '', quantity: 1, size: ''});
  const [issued, setIssued] = useState<Schemas['IssuedUnit'] | null>(null);
  const [shown, setShown] = useState(false);
  const [printing, setPrinting] = useState<string | null>(null);
  const intent = useRef(createIntent());
  // The units list is per product (the API requires product_id).
  const units = useInfiniteQuery({queryKey: key('units', filter), initialPageParam: undefined as string | undefined, enabled: !!filter,
    queryFn: ({signal, pageParam}) => api.call('get', '/api/v2/admin/units', {signal, query: {limit: 50, product_id: filter, ...(pageParam ? {cursor: pageParam} : {})}}),
    getNextPageParam: last => last.next_cursor ?? undefined});
  const issue = (e: FormEvent) => {
    e.preventDefault();
    void api.call('post', '/api/v2/admin/unit-batches', {body: {product_id: form.product.trim(), quantity: Number(form.quantity), size: form.size || null}, intent: intent.current})
      .then(u => { intent.current = createIntent(); setIssued(u); setShown(false); setFilter(u.product_id); toast(t('un.issued', {serial: u.public_serial}), 'success'); void units.refetch(); }, fail);
  };
  const reissue = (id: string) => void api.call('post', '/api/v2/admin/units/{unit_id}/reissue', {path: {unit_id: id}}).then(u => { setIssued(u); setShown(false); }, fail);
  const key1 = issued?.delivery.activation_key ?? null;
  return <>
    <h2>{t('sf.units')}</h2>
    {canIssue && <form className="staff-inline" onSubmit={issue}>
      <TextField label={t('sf.productId')} required value={form.product} onChange={e => setForm({...form, product: e.target.value})} />
      <TextField label={t('un.quantity')} type="number" min={1} max={100} value={String(form.quantity)} onChange={e => setForm({...form, quantity: Number(e.target.value)})} />
      <TextField label={t('un.size')} value={form.size} maxLength={8} onChange={e => setForm({...form, size: e.target.value})} />
      <Button type="submit" variant="primary">{t('un.issue')}</Button></form>}
    {issued && <div className="issued" role="status">
      <p><strong>{t('un.issued', {serial: issued.public_serial})}</strong></p>
      {key1 && <><p className="muted small">{t('un.keyOnce')}</p>
        <div className="staff-inline"><code className="unit-key">{shown ? key1 : key1.replace(/[A-Z0-9]/g, '•')}</code>
          <Button variant="ghost" onClick={() => setShown(s => !s)}>{shown ? <EyeOff size={16} aria-hidden /> : <Eye size={16} aria-hidden />} {shown ? t('un.hide') : t('un.show')}</Button>
          <Button variant="ghost" onClick={() => void navigator.clipboard.writeText(key1).then(() => toast(t('un.copied')))}><Copy size={16} aria-hidden /> {t('un.copy')}</Button>
          <Button onClick={() => setPrinting(issued.public_serial)}><Printer size={16} aria-hidden /> {t('un.printTag')}</Button></div></>}
    </div>}
    <form className="staff-inline" onSubmit={e => { e.preventDefault(); }}><TextField label={t('un.filter')} value={filter} onChange={e => setFilter(e.target.value.trim())} /></form>
    {!filter ? null : units.isPending ? <Skeleton ratio="6 / 1" /> : units.isError ? <StaffError error={units.error} onRetry={() => units.refetch()} /> : <>
      <table className="staff-table"><thead><tr><th>{t('un.serial')}</th><th>{t('sf.status')}</th><th>{t('wr.size')}</th><th /><th /></tr></thead>
        <tbody>{units.data.pages.flatMap(p => p.items).map(u => <tr key={u.unit_id}><td><code>{u.public_serial}</code></td>
          <td>{u.claimed_at ? <span className="tag tag-ok">{t('un.claimed')}</span> : <span className="tag tag-quiet">{t('un.unclaimed')} · {u.status}</span>}</td>
          <td>{u.size?.label ?? '—'}</td><td className="small">{date(u.created_at)}</td>
          <td><Button variant="ghost" onClick={() => setPrinting(u.public_serial)}><Printer size={16} aria-label={t('un.printTag')} /></Button>
            {!u.claimed_at && me?.capabilities.includes('inventory:reissue') && <Button variant="ghost" onClick={() => reissue(u.unit_id)}><RefreshCw size={16} aria-hidden /> {t('un.reissue')}</Button>}</td></tr>)}</tbody></table>
      {units.hasNextPage && <Button onClick={() => void units.fetchNextPage()}>{t('sf.loadMore')}</Button>}</>}
    <Overlay open={!!printing} onClose={() => setPrinting(null)} side="center" title={t('un.printTag')}>
      {printing && <div className="confirm"><TagQr serial={printing} /><p className="muted small">{t('un.tagNote')}</p>
        <Button variant="primary" onClick={() => window.print()} data-autofocus><Printer size={16} aria-hidden /> {t('un.printTag')}</Button></div>}
    </Overlay>
  </>;
}
