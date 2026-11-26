import {useState} from 'react';
import {Link, useLocation, useNavigate, useParams} from 'react-router';
import {ArrowLeft, Check, Heart, ShoppingBag} from 'lucide-react';
import {useI18n} from '../../i18n/index.tsx';
import {useSession} from '../../session/SessionProvider.tsx';
import {ApiFailure} from '../../api/index.ts';
import {useProduct} from '../../data/queries.ts';
import {useCartLine, useCollection, useOffer, useOwnedProductIds, useSimilar, useWishlist, useWishlistToggle} from '../../data/store.ts';
import {Button, Chip, Skeleton} from '../../components/ui.tsx';
import {Media} from '../../components/Media.tsx';
import {Rail} from '../../components/Rail.tsx';
import {ModelLabel, SimulatedLabel} from '../../components/labels.tsx';
import {EmptyState, ErrorState} from '../../components/states.tsx';
import {toast} from '../../components/toast.tsx';
import {FocusZone, focusItemProps} from '../../focus/FocusZone.tsx';
import {ProductTile, openProduct, slotLabel, withTransition} from './parts.tsx';
import './store.css';

const text = (v: unknown) => (v === null || v === undefined ? '' : String(v));

/** Signals the top bar's cart button to play its landing pulse (the fly-to-cart moment). */
function pulseCart() { window.dispatchEvent(new CustomEvent('wh:cart-landed')); }

export function ProductRoute() {
  const {id = ''} = useParams();
  const {t, idr} = useI18n();
  const navigate = useNavigate();
  const location = useLocation();
  const {status} = useSession();
  const product = useProduct(id);
  const offer = useOffer(id);
  const owned = useOwnedProductIds();
  const [image, setImage] = useState(0);

  if (product.isPending) return <div className="page store product"><div className="product-layout">
    <Skeleton ratio="3 / 4" /><div className="product-info"><Skeleton ratio="6 / 1" /><Skeleton ratio="4 / 1" /></div></div></div>;
  if (product.isError) {
    if (product.error instanceof ApiFailure && product.error.status === 404) return <div className="page store">
      <EmptyState title={t('prod.notFound')}><Link to="/catalogue">{t('cat.backToFront')}</Link></EmptyState></div>;
    return <div className="page store"><ErrorState error={product.error} onRetry={() => product.refetch()} /></div>;
  }
  const p = product.data;
  const name = text(p.facts.product_name?.value) || t('prod.notFound');
  const slot = text(p.annotations.slot?.value) || null;
  const media = p.media.length ? p.media : [{uri: '', version: '0', alt_text: null}];
  const back = () => {
    if (location.key === 'default') { navigate('/catalogue'); return; }
    withTransition(id, () => new Promise<void>(resolve => {
      const done = () => { window.removeEventListener('hashchange', done); requestAnimationFrame(() => resolve()); };
      window.addEventListener('hashchange', done);
      navigate(-1);
      setTimeout(done, 400);
    }));
  };

  return <div className="page store product">
    <div className="product-top">
      <Button variant="ghost" onClick={back}><ArrowLeft size={18} aria-hidden /> {t('common.back')}</Button>
      {owned.data?.has(p.id) && <span className="tag tag-ok"><Check size={14} aria-hidden /> {t('prod.owned')}</span>}
    </div>
    <div className="product-layout">
      <section className="product-gallery" aria-label={t('prod.gallery')}>
        <div className="product-hero" style={{viewTransitionName: 'product-hero'}}>
          <Media src={media[image]?.uri || null} alt={media[image]?.alt_text ?? name} slot={slot} />
        </div>
        {media.length > 1 && <FocusZone kind="rail" label={t('prod.gallery')} className="product-thumbs" version={media.length}>
          {media.map((m, i) => <button key={m.uri + i} type="button" className="product-thumb" aria-pressed={i === image}
            aria-label={t('prod.image', {n: i + 1, total: media.length})}
            {...focusItemProps({id: `media:${i}`, title: name})} onClick={() => setImage(i)}>
            <Media src={m.uri} alt="" slot={slot} quiet /></button>)}
        </FocusZone>}
      </section>
      <section className="product-info">
        <p className="eyebrow">{[text(p.facts.category?.value), slot && slotLabel(t, slot)].filter(Boolean).join(' · ')}</p>
        <h1>{name}</h1>
        <Buy productId={p.id} oneSize={p.one_size} signedIn={status === 'ready'} offer={offer} idr={idr} />
        <dl className="product-facts" aria-label={t('prod.facts')}>
          <h2>{t('prod.facts')}</h2>
          {Object.entries(p.facts).map(([k, f]) => <div key={k}><dt>{k.replace(/_/g, ' ')}</dt>
            <dd>{text(f.value)}{f.source_field && <span className="muted small"> · {t('prod.factField', {field: f.source_field})}</span>}</dd></div>)}
        </dl>
        {Object.keys(p.annotations).length > 0 && <dl className="product-facts">
          <h2>{t('prod.annotations')}</h2>
          {Object.entries(p.annotations).map(([k, a]) => <div key={k}><dt>{k.replace(/_/g, ' ')}</dt>
            <dd>{k === 'slot' ? slotLabel(t, text(a.value)) : text(a.value)}
              {a.origin && <span className="tag tag-quiet">{t('prod.origin', {origin: a.origin})}</span>}
              {a.note && <span className="muted small"> · {a.note}</span>}</dd></div>)}
        </dl>}
        <p className="muted small">{t('prod.source')}: {p.source.name} · {t('prod.sourceId', {namespace: p.source.namespace, id: p.source.external_id})}</p>
      </section>
    </div>
    <Similar id={p.id} />
  </div>;
}

function Buy({productId, oneSize, signedIn, offer, idr}: {
  productId: string; oneSize: boolean; signedIn: boolean; offer: ReturnType<typeof useOffer>; idr: (n: number) => string;
}) {
  const {t, errorText} = useI18n();
  const wishlist = useWishlist();
  const toggle = useWishlistToggle();
  const cart = useCartLine();
  const [size, setSize] = useState<string | null>(null);
  const [burst, setBurst] = useState(0);
  const saved = !!wishlist.data?.items.some(i => i.product_id === productId);
  const o = offer.data;
  const sized = !oneSize && !!o?.sizes.length;
  const canBuy = !!o?.in_stock && (!sized || !!size);
  const fail = (e: unknown) => toast(e instanceof ApiFailure ? errorText(e.code, e.message) : t('common.offline'), 'error');

  if (!signedIn) return <div className="buy">
    {o && <p className="price">{idr(o.price_idr)} <SimulatedLabel /></p>}
    <Link className="btn btn-primary btn-lg" to="/signin">{t('prod.signInToBuy')}</Link>
  </div>;
  return <div className="buy">
    {offer.isPending ? <Skeleton ratio="8 / 1" /> : offer.isError
      ? <p className="muted">{offer.error instanceof ApiFailure && offer.error.status === 404 ? t('prod.noOffer') : t('common.error')}</p>
      : o && <>
        <p className="price">{idr(o.price_idr)} <SimulatedLabel /></p>
        {sized ? <FocusZone kind="rail" label={t('prod.sizes')} className="buy-sizes" version={o.sizes.length}>
          {o.sizes.map(s => <Chip key={s.system + s.code} selected={size === `${s.system}:${s.code}`} disabled={!s.in_stock}
            aria-label={s.in_stock ? s.label : t('prod.sizeOut', {size: s.label})}
            {...focusItemProps({id: `size:${s.code}`, title: s.label})}
            onClick={() => setSize(`${s.system}:${s.code}`)}>{s.label}</Chip>)}
        </FocusZone> : <p className="muted">{t('prod.oneSize')}</p>}
        {!o.in_stock && <p className="buy-reason" role="status">{t('prod.outOfStock')}</p>}
      </>}
    <div className="buy-actions">
      {o && <Button variant="primary" size="lg" disabled={!canBuy} loading={cart.isPending}
        title={!o.in_stock ? t('prod.outOfStock') : sized && !size ? t('prod.chooseSize') : undefined}
        onClick={() => cart.mutate({id: productId, quantity: 1, size: sized ? size : null},
          {onSuccess: () => { pulseCart(); toast(t('prod.added'), 'success'); }, onError: fail})}>
        <ShoppingBag size={18} aria-hidden /> {sized && !size && o.in_stock ? t('prod.chooseSize') : t('prod.addToCart')}</Button>}
      <Button size="lg" aria-pressed={saved} className={`heart ${saved ? 'is-on' : ''}`} loading={toggle.isPending}
        onClick={() => toggle.mutate({id: productId, on: !saved}, {
          onSuccess: () => { if (!saved) setBurst(b => b + 1); toast(saved ? t('wish.removed') : t('prod.wishlisted'), 'success'); },
          onError: fail})}>
        <span className="heart-icon" key={burst} data-burst={burst > 0 || undefined}><Heart size={18} aria-hidden fill={saved ? 'currentColor' : 'none'} /></span>
        {saved ? t('prod.unwishlist') : t('prod.wishlist')}</Button>
    </div>
  </div>;
}

function Similar({id}: {id: string}) {
  const {t} = useI18n();
  const navigate = useNavigate();
  const similar = useSimilar(id);
  if (similar.isPending || similar.isError || !similar.data.items.length) return null;
  const {model} = similar.data;
  return <Rail title={t('prod.similar')} version={similar.data.items.length}
    note={<><ModelLabel mode={model.mode} />{model.fallback && <span className="muted small"> {t('prod.similarFallback', {reason: model.fallback})}</span>}</>}>
    {similar.data.items.map(p => <ProductTile key={p.id} p={p} onOpen={pid => openProduct(navigate, pid)} />)}
  </Rail>;
}

export function CollectionRoute() {
  const {slug = ''} = useParams();
  const {t} = useI18n();
  const navigate = useNavigate();
  const collection = useCollection(slug);
  if (collection.isPending) return <div className="page store"><div className="store-grid">{Array.from({length: 6}, (_, i) => <Skeleton key={i} />)}</div></div>;
  if (collection.isError) return <div className="page store"><ErrorState error={collection.error} onRetry={() => collection.refetch()} /></div>;
  const c = collection.data;
  return <div className="page store">
    <header className="store-head"><div><p className="eyebrow">{t('coll.title')}</p><h1>{c.title}</h1>
      <p className="muted">{t('coll.pieces', {n: c.items.length})}</p></div></header>
    <FocusZone kind="grid" label={c.title} className="store-grid" version={c.items.length} autoFocus>
      {c.items.map(p => <ProductTile key={p.id} p={p} onOpen={pid => openProduct(navigate, pid)} />)}
    </FocusZone>
  </div>;
}

