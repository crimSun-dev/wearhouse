import {useState} from 'react';
import {Link, useLocation, useNavigate, useParams} from 'react-router';
import {useQueryClient} from '@tanstack/react-query';
import {Copy, Eye, EyeOff, KeyRound, RefreshCw} from 'lucide-react';
import {useI18n} from '../../i18n/index.tsx';
import {useSession} from '../../session/SessionProvider.tsx';
import {ApiFailure} from '../../api/index.ts';
import {useOrder, useOrders} from '../../data/store.ts';
import {Button, Skeleton} from '../../components/ui.tsx';
import {Overlay} from '../../components/Overlay.tsx';
import {EmptyState, ErrorState} from '../../components/states.tsx';
import {toast} from '../../components/toast.tsx';
import {FocusZone, focusItemProps} from '../../focus/FocusZone.tsx';
import {handOffKey} from './parts.tsx';
import {renderSVG} from 'uqr';
import {QrCode} from 'lucide-react';
import './store.css';

export function OrdersRoute() {
  const {t, idr, date} = useI18n();
  const orders = useOrders();
  if (orders.isPending) return <div className="page store"><Skeleton ratio="6 / 1" /><Skeleton ratio="6 / 1" /></div>;
  if (orders.isError) return <div className="page store"><ErrorState error={orders.error} onRetry={() => orders.refetch()} /></div>;
  const items = orders.data.pages.flatMap(p => p.items);
  return <div className="page store">
    <header className="store-head"><h1>{t('ord.title')}</h1></header>
    {!items.length ? <EmptyState title={t('ord.empty')} body={t('ord.emptyBody')}>
      <Link className="btn btn-primary btn-md" to="/catalogue">{t('home.browse')}</Link></EmptyState> : <>
      <FocusZone kind="grid" label={t('ord.title')} className="bag-list" version={items.length} autoFocus>
        {items.map(o => <Link key={o.id} to={`/orders/${o.id}`} className="bag-line order-row"
          {...focusItemProps({id: `order:${o.id}`, title: o.names.join(', ')})}>
          <span className="bag-name">{o.names.slice(0, 3).join(', ')}{o.names.length > 3 ? '…' : ''}</span>
          <span className="bag-meta">{t('ord.placedOn', {date: date(o.created_at)})} · {t('ord.items', {n: o.item_count})}</span>
          <span className={`tag ${o.status === 'cancelled' ? 'tag-warn' : 'tag-ok'}`}>{o.status === 'cancelled' ? t('ord.cancelled') : t('ord.fulfilled')}</span>
          <span className="bag-price">{idr(o.total_idr)}</span>
        </Link>)}
      </FocusZone>
      {orders.hasNextPage && <div className="store-more"><Button loading={orders.isFetchingNextPage} onClick={() => void orders.fetchNextPage()}>{t('cat.loadMore')}</Button></div>}
    </>}
  </div>;
}

export function ReceiptRoute() {
  const {id = ''} = useParams();
  const {t, idr, date, errorText} = useI18n();
  const location = useLocation();
  const {api, userKey} = useSession();
  const qc = useQueryClient();
  const order = useOrder(id);
  const [confirmCancel, setConfirmCancel] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const placed = (location.state as {placed?: boolean} | null)?.placed;
  if (order.isPending) return <div className="page store"><Skeleton ratio="3 / 1" /></div>;
  if (order.isError) return <div className="page store"><ErrorState error={order.error} onRetry={() => order.refetch()} /></div>;
  const r = order.data;
  const cancel = async () => {
    setCancelling(true);
    try {
      const next = await api.call('post', '/api/v2/me/orders/{order_id}/cancel', {path: {order_id: r.id}});
      qc.setQueryData([...userKey, 'order', r.id], next);
      void qc.invalidateQueries({queryKey: [...userKey, 'orders']});
      setConfirmCancel(false); toast(t('ord.cancelDone'), 'success');
    } catch (e) { toast(e instanceof ApiFailure ? errorText(e.code, e.message) : t('common.offline'), 'error'); }
    finally { setCancelling(false); }
  };
  let unitNo = 0;
  return <div className="page store receipt-page">
    <article className={`receipt ${placed ? 'is-new' : ''}`} aria-labelledby="receipt-title">
      <header className="receipt-head">
        <p className="eyebrow">{t('ord.signature')}</p>
        <h1 id="receipt-title">{t('ord.receipt')}</h1>
        <p className="muted small">{t('ord.placedOn', {date: date(r.created_at)})}</p>
        <span className={`tag ${r.status === 'cancelled' ? 'tag-warn' : 'tag-ok'}`}>{r.status === 'cancelled' ? t('ord.cancelled') : t('ord.fulfilled')}</span>
      </header>
      <p className="co-statement" role="note"><span className="tag tag-quiet">{t('ord.simulatedTag')}</span> {t('co.simulated')}</p>
      <dl className="receipt-ref"><dt>{t('ord.paymentRef')}</dt><dd><code>{r.payment_ref}</code> <span className="tag tag-quiet">{t('ord.simulatedTag')}</span></dd></dl>
      {r.lines.map(l => <section key={l.line_no} className="receipt-line">
        <h2><Link to={`/catalogue/products/${l.product_id}`}>{l.product_name}</Link>
          {l.size && <span className="muted small"> · {t('cart.size', {size: l.size.label})}</span>}</h2>
        <p className="bag-meta">{l.quantity} × {idr(l.unit_price_idr)} = <strong>{idr(l.line_total_idr)}</strong></p>
        <ul className="units">{l.units.map(u => { unitNo += 1; return <Unit key={u.unit_id} orderId={r.id} unit={u} n={unitNo} cancelled={r.status === 'cancelled'} />; })}</ul>
      </section>)}
      <footer className="receipt-total"><span>{t('cart.total')}</span><strong>{idr(r.total_idr)}</strong></footer>
      <p className="muted small"><KeyRound size={14} aria-hidden /> {t('ord.keyNote')}</p>
      {r.cancellable && <Button variant="danger" onClick={() => setConfirmCancel(true)}>{t('ord.cancel')}</Button>}
    </article>
    <Overlay open={confirmCancel} onClose={() => setConfirmCancel(false)} side="center" title={t('ord.cancel')}>
      <div className="confirm"><p>{t('ord.cancelWarn')}</p>
        <div className="buy-actions"><Button data-autofocus onClick={() => setConfirmCancel(false)}>{t('common.back')}</Button>
          <Button variant="danger" loading={cancelling} onClick={() => void cancel()}>{t('ord.cancelConfirm')}</Button></div></div>
    </Overlay>
  </div>;
}

type UnitOut = {unit_id: string; public_serial: string | null; state: string;
  delivery: {status: 'available' | 'expired' | 'unavailable' | 'claimed'; expires_at?: string | null; reason?: string | null}};

/** One unit's key. The key lives only in this component's state: it is gone as soon as the receipt unmounts. */
function Unit({orderId, unit, n, cancelled}: {orderId: string; unit: UnitOut; n: number; cancelled: boolean}) {
  const {t, date, errorText} = useI18n();
  const {api, userKey} = useSession();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [key, setKey] = useState<string | null>(null);
  const [shown, setShown] = useState(false);
  const [qr, setQr] = useState(false);
  const [busy, setBusy] = useState(false);
  const [confirmRenew, setConfirmRenew] = useState(false);
  const fail = (e: unknown) => toast(e instanceof ApiFailure ? errorText(e.code, e.message) : t('common.offline'), 'error');
  const reveal = async () => {
    setBusy(true);
    try {
      const k = await api.call('get', '/api/v2/me/orders/{order_id}/units/{unit_id}/key', {path: {order_id: orderId, unit_id: unit.unit_id}});
      if (k.status === 'available' && k.activation_key) { setKey(k.activation_key); setShown(false); }
      else void qc.invalidateQueries({queryKey: [...userKey, 'order', orderId]});
    } catch (e) { fail(e); } finally { setBusy(false); }
  };
  const renew = async () => {
    setBusy(true);
    try {
      await api.call('post', '/api/v2/me/orders/{order_id}/units/{unit_id}/renew-key', {path: {order_id: orderId, unit_id: unit.unit_id}});
      setKey(null); setConfirmRenew(false); toast(t('ord.renewed'), 'success');
      void qc.invalidateQueries({queryKey: [...userKey, 'order', orderId]});
    } catch (e) { fail(e); } finally { setBusy(false); }
  };
  const d = unit.delivery;
  const masked = key ? key.replace(/[A-Z0-9]/g, '•').slice(0, -4) + key.slice(-4) : '';
  return <li className="unit">
    <span className="unit-name">{t('ord.unit', {n})}{unit.public_serial && <span className="muted small"> · {t('tag.serial', {serial: unit.public_serial})}</span>}</span>
    {d.status === 'claimed' ? <span className="unit-state"><span className="tag tag-ok">{t('ord.claimed')}</span>
      {unit.public_serial && <Link to={`/items/${unit.public_serial}`} {...focusItemProps({id: `unit:${unit.unit_id}`, title: t('ord.viewItem')})}>{t('ord.viewItem')}</Link>}</span>
      : d.status === 'available' && !cancelled ? <span className="unit-state">
        {key ? <>
          <code className="unit-key" aria-live="polite">{shown ? key : masked}</code>
          <Button variant="ghost" onClick={() => setShown(s => !s)}>{shown ? <EyeOff size={16} aria-hidden /> : <Eye size={16} aria-hidden />} {shown ? t('ord.hide') : t('ord.show')}</Button>
          <Button variant="ghost" onClick={() => void navigator.clipboard.writeText(key).then(() => toast(t('ord.copied'), 'success'))}><Copy size={16} aria-hidden /> {t('ord.copy')}</Button>
          <Button variant="primary" onClick={() => { handOffKey(key); setKey(null); navigate('/redeem'); }}>{t('ord.redeemNow')}</Button>
          <Button variant="ghost" aria-pressed={qr} onClick={() => setQr(q => !q)}><QrCode size={16} aria-hidden /> {t('ord.qr')}</Button>
          {qr && <figure className="key-qr" data-testid="key-qr"><span dangerouslySetInnerHTML={{__html: renderSVG(key, {border: 2})}} />
            <figcaption className="muted small">{t('ord.qrNote')}</figcaption></figure>}
        </> : <Button loading={busy} onClick={() => void reveal()} {...focusItemProps({id: `unit:${unit.unit_id}`, title: t('ord.reveal')})}>
          <KeyRound size={16} aria-hidden /> {t('ord.reveal')}</Button>}
        <Button variant="ghost" onClick={() => setConfirmRenew(true)}><RefreshCw size={16} aria-hidden /> {t('ord.renew')}</Button>
        {d.expires_at && <span className="muted small">{t('ord.expires', {date: date(d.expires_at)})}</span>}
      </span>
      : <span className="unit-state muted">{d.status === 'expired' ? t('ord.expired') : t('ord.keyUnavailable')}
        {d.status === 'expired' && !cancelled && <Button variant="ghost" onClick={() => setConfirmRenew(true)}><RefreshCw size={16} aria-hidden /> {t('ord.renew')}</Button>}</span>}
    <Overlay open={confirmRenew} onClose={() => setConfirmRenew(false)} side="center" title={t('ord.renew')}>
      <div className="confirm"><p>{t('ord.renewWarn')}</p>
        <div className="buy-actions"><Button data-autofocus onClick={() => setConfirmRenew(false)}>{t('common.back')}</Button>
          <Button variant="primary" loading={busy} onClick={() => void renew()}>{t('ord.renewConfirm')}</Button></div></div>
    </Overlay>
  </li>;
}
