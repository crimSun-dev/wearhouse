import {useRef, useState} from 'react';
import {Link, useNavigate} from 'react-router';
import {AlertTriangle, Trash2} from 'lucide-react';
import {useI18n} from '../../i18n/index.tsx';
import {ApiFailure, createIntent} from '../../api/index.ts';
import {useCart, useCartLine, useCheckout, useWishlist, useWishlistToggle} from '../../data/store.ts';
import {Button, Skeleton, Stepper} from '../../components/ui.tsx';
import {SimulatedLabel} from '../../components/labels.tsx';
import {EmptyState, ErrorState} from '../../components/states.tsx';
import {toast} from '../../components/toast.tsx';
import {FocusZone, focusItemProps} from '../../focus/FocusZone.tsx';
import type {MessageKey} from '../../i18n/en.ts';
import './store.css';

function useFail() {
  const {t, errorText} = useI18n();
  return (e: unknown) => toast(e instanceof ApiFailure ? errorText(e.code, e.message) : t('common.offline'), 'error');
}

export function WishlistRoute() {
  const {t, idr} = useI18n();
  const wishlist = useWishlist();
  const toggle = useWishlistToggle();
  const fail = useFail();
  if (wishlist.isPending) return <div className="page store"><Skeleton ratio="6 / 1" /><Skeleton ratio="6 / 1" /></div>;
  if (wishlist.isError) return <div className="page store"><ErrorState error={wishlist.error} onRetry={() => wishlist.refetch()} /></div>;
  const {items, limit} = wishlist.data;
  return <div className="page store">
    <header className="store-head"><h1>{t('wish.title')}</h1><p className="muted">{t('wish.count', {n: items.length, limit})}</p></header>
    {!items.length ? <EmptyState title={t('wish.empty')} body={t('wish.emptyBody')}>
      <Link className="btn btn-primary btn-md" to="/catalogue">{t('home.browse')}</Link></EmptyState>
      : <FocusZone kind="grid" label={t('wish.title')} className="bag-list" version={items.length} autoFocus>
        {items.map(i => <div key={i.product_id} className={`bag-line ${i.available ? '' : 'is-off'}`}>
          <Link to={`/catalogue/products/${i.product_id}`} className="bag-name" {...focusItemProps({id: `wish:${i.product_id}`, title: i.name ?? ''})}>
            {i.name ?? i.product_id}</Link>
          <span className="bag-meta">{!i.available ? t('wish.unavailable') : i.offer
            ? <>{idr(i.offer.price_idr)} · {i.offer.in_stock ? t('wish.inStock') : t('wish.soldOut')}</> : t('prod.noOffer')}</span>
          <Button variant="ghost" loading={toggle.isPending && toggle.variables?.id === i.product_id}
            onClick={() => toggle.mutate({id: i.product_id, on: false}, {onSuccess: () => toast(t('wish.removed')), onError: fail})}>
            <Trash2 size={16} aria-hidden /> {t('wish.remove')}</Button>
        </div>)}
      </FocusZone>}
  </div>;
}

export function CartRoute() {
  const {t, idr} = useI18n();
  const navigate = useNavigate();
  const cart = useCart();
  const line = useCartLine();
  const fail = useFail();
  if (cart.isPending) return <div className="page store"><Skeleton ratio="6 / 1" /><Skeleton ratio="6 / 1" /></div>;
  if (cart.isError) return <div className="page store"><ErrorState error={cart.error} onRetry={() => cart.refetch()} /></div>;
  const c = cart.data;
  return <div className="page store">
    <header className="store-head"><h1>{t('cart.title')}</h1><p className="muted">{t('cart.lines', {n: c.lines.length, limit: c.limit})}</p></header>
    {!c.lines.length ? <EmptyState title={t('cart.empty')} body={t('cart.emptyBody')}>
      <Link className="btn btn-primary btn-md" to="/catalogue">{t('home.browse')}</Link></EmptyState> : <>
      <FocusZone kind="grid" label={t('cart.title')} className="bag-list" version={c.lines.length} autoFocus>
        {c.lines.map(l => {
          const size = l.size ? l.size.code : null;   // the cart addresses a line by its size code
          const busy = line.isPending && line.variables?.id === l.product_id && line.variables?.size === size;
          return <div key={l.product_id + (size ?? '')} className={`bag-line ${l.available ? '' : 'is-off'}`}>
            <Link to={`/catalogue/products/${l.product_id}`} className="bag-name" {...focusItemProps({id: `cart:${l.product_id}:${size}`, title: l.name ?? ''})}>
              {l.name ?? l.product_id}{l.size && <span className="bag-sub">{t('cart.size', {size: l.size.label})}</span>}</Link>
            {l.available ? <>
              <Stepper label={t('cart.quantity')} value={l.quantity} min={1} max={5}
                onChange={q => line.mutate({id: l.product_id, quantity: q, size}, {onError: fail})} />
              <span className="bag-price">{l.line_total_idr !== null ? idr(l.line_total_idr) : ''}</span>
            </> : <span className="bag-reason" role="status"><AlertTriangle size={16} aria-hidden /> {t('cart.unavailable')}</span>}
            <Button variant="ghost" loading={busy} onClick={() => line.mutate({id: l.product_id, quantity: 0, size},
              {onSuccess: () => toast(t('cart.removed')), onError: fail})}><Trash2 size={16} aria-hidden /> {t('cart.remove')}</Button>
          </div>;
        })}
      </FocusZone>
      <div className="bag-total">
        <span>{t('cart.total')} <SimulatedLabel /></span><strong>{idr(c.total_idr)}</strong>
        {!c.checkout_ready && <p className="bag-reason" role="status">{t('cart.notReady')}</p>}
        <Button variant="primary" size="lg" disabled={!c.checkout_ready} onClick={() => navigate('/checkout')}>{t('cart.review')}</Button>
      </div>
    </>}
  </div>;
}

const CHANGED: Record<string, MessageKey> = {
  PRICE_CHANGED: 'co.reasonPrice', OUT_OF_STOCK: 'co.reasonStock', NOT_AVAILABLE: 'co.reasonAvailable', CART_EMPTY: 'co.reasonEmpty',
};

export function CheckoutRoute() {
  const {t, idr} = useI18n();
  const navigate = useNavigate();
  const cart = useCart();
  const checkout = useCheckout();
  const fail = useFail();
  // One intent for this review: a retry of the same total reuses its Idempotency-Key, so a lost response never orders twice.
  const intent = useRef(createIntent());
  const [changed, setChanged] = useState<MessageKey | null>(null);
  const [lost, setLost] = useState(false);
  if (cart.isPending) return <div className="page store"><Skeleton ratio="6 / 1" /></div>;
  if (cart.isError) return <div className="page store"><ErrorState error={cart.error} onRetry={() => cart.refetch()} /></div>;
  const c = cart.data;
  const place = () => {
    setChanged(null);
    checkout.mutate({expected: c.total_idr, intent: intent.current}, {
      onSuccess: r => navigate(`/orders/${r.id}`, {replace: true, state: {placed: true}}),
      onError: e => {
        if (e instanceof ApiFailure && CHANGED[e.code]) { setChanged(CHANGED[e.code]!); setLost(false); void cart.refetch(); }
        else if (!(e instanceof ApiFailure)) setLost(true);
        else fail(e);
      },
    });
  };
  return <div className="page store checkout">
    <header className="store-head"><h1>{t('co.title')}</h1></header>
    <p className="co-statement" role="note"><span className="tag tag-quiet">{t('ord.simulatedTag')}</span> {t('co.simulated')}</p>
    {changed && <p className="co-alert" role="alert"><AlertTriangle size={18} aria-hidden /> {t('co.changed', {reason: t(changed)})}</p>}
    {lost && <p className="co-alert" role="alert">{t('co.lostResponse')}</p>}
    {!c.lines.length ? <EmptyState title={t('cart.empty')}><Link to="/catalogue">{t('home.browse')}</Link></EmptyState> : <>
      <ul className="bag-list co-lines">
        {c.lines.map(l => <li key={l.product_id + (l.size?.code ?? '')} className={`bag-line ${l.available ? '' : 'is-off'}`}>
          <span className="bag-name">{l.name}{l.size && <span className="bag-sub">{t('cart.size', {size: l.size.label})}</span>}</span>
          <span className="bag-meta">× {l.quantity}</span>
          <span className="bag-price">{l.line_total_idr !== null ? idr(l.line_total_idr) : t('wish.unavailable')}</span>
        </li>)}
      </ul>
      <p className="muted small">{t('co.keysNote')}</p>
      <div className="bag-total">
        <span>{t('cart.total')} <SimulatedLabel /></span><strong>{idr(c.total_idr)}</strong>
        <div className="buy-actions">
          <Link className="btn btn-ghost btn-lg" to="/cart">{t('co.backToCart')}</Link>
          <Button variant="primary" size="lg" disabled={!c.checkout_ready} loading={checkout.isPending} onClick={place}>{t('co.place')}</Button>
        </div>
      </div>
    </>}
  </div>;
}
