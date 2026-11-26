import {useState, type FormEvent} from 'react';
import {Link, useNavigate, useParams} from 'react-router';
import {Heart, KeyRound, Tag as TagIcon} from 'lucide-react';
import {QrScanner as Scanner} from '../../components/QrScanner.tsx';
import {useI18n} from '../../i18n/index.tsx';
import {useSession} from '../../session/SessionProvider.tsx';
import {ApiFailure} from '../../api/index.ts';
import {useProduct} from '../../data/queries.ts';
import {usePublicItem, useWishlist, useWishlistToggle} from '../../data/store.ts';
import {Button, Skeleton, TextField} from '../../components/ui.tsx';
import {Media} from '../../components/Media.tsx';
import {EmptyState, ErrorState} from '../../components/states.tsx';
import {toast} from '../../components/toast.tsx';
import {serialFrom} from './parts.tsx';
import './store.css';


/** #/items and #/items/:serial: discovery only. Nothing here sends a redemption or changes the wardrobe. */
export function TagRoute() {
  const {serial = ''} = useParams();
  const {t} = useI18n();
  return <div className="page store tag-page">
    <header className="store-head"><h1><TagIcon size={28} aria-hidden /> {t('tag.title')}</h1></header>
    {serial && <TagResult serial={serial} />}
    <Lookup />
  </div>;
}

function TagResult({serial}: {serial: string}) {
  const {t, errorText} = useI18n();
  const {status} = useSession();
  const item = usePublicItem(serial);
  const detail = useProduct(item.data?.product.id);
  const wishlist = useWishlist();
  const toggle = useWishlistToggle();
  if (item.isPending) return <Skeleton ratio="5 / 2" />;
  if (item.isError) {
    if (item.error instanceof ApiFailure && item.error.status === 404) return <EmptyState title={t('tag.notFound')} />;
    return <ErrorState error={item.error} onRetry={() => item.refetch()} />;
  }
  const {product, source, catalogue_status} = item.data;
  const saved = !!wishlist.data?.items.some(i => i.product_id === product.id);
  const slot = detail.data?.annotations.slot?.value ? String(detail.data.annotations.slot.value) : null;
  return <section className="tag-card">
    <div className="tag-media"><Media src={detail.data?.media[0]?.uri ?? null} alt={product.name} slot={slot} /></div>
    <div className="tag-body">
      <p className="eyebrow">{product.category}</p>
      <h2>{product.name}</h2>
      <p className="muted small">{t('tag.serial', {serial: item.data.public_serial})} · {source.namespace} · {source.external_id}</p>
      <p className="muted small">{t('tag.status', {status: catalogue_status})}</p>
      <p className="tag-note">{t('tag.discovery')}</p>
      <p className="tag-note"><KeyRound size={16} aria-hidden /> {t('tag.ownership')}</p>
      <div className="buy-actions">
        <Link className="btn btn-secondary btn-md" to={`/catalogue/products/${product.id}`}>{t('tag.viewProduct')}</Link>
        {status === 'ready' && <Button aria-pressed={saved} loading={toggle.isPending}
          onClick={() => toggle.mutate({id: product.id, on: !saved}, {
            onSuccess: () => toast(saved ? t('wish.removed') : t('prod.wishlisted'), 'success'),
            onError: e => toast(e instanceof ApiFailure ? errorText(e.code, e.message) : t('common.offline'), 'error')})}>
          <Heart size={18} aria-hidden fill={saved ? 'currentColor' : 'none'} /> {saved ? t('prod.unwishlist') : t('prod.wishlist')}</Button>}
        <Link className="btn btn-ghost btn-md" to="/redeem">{t('nav.redeem')}</Link>
      </div>
    </div>
  </section>;
}

function Lookup() {
  const {t} = useI18n();
  const navigate = useNavigate();
  const [value, setValue] = useState('');
  const [error, setError] = useState<string | null>(null);
  const open = (raw: string) => {
    const serial = serialFrom(raw);
    if (!serial) { setError(t('tag.invalid')); return false; }
    setError(null); setValue(''); navigate(`/items/${encodeURIComponent(serial)}`);
    return true;
  };
  const submit = (e: FormEvent) => { e.preventDefault(); open(value); };
  return <section className="store-section tag-lookup">
    <h2>{t('tag.lookup')}</h2>
    <Scanner onCode={open} />
    <form className="tag-paste" onSubmit={submit}>
      <TextField label={t('tag.paste')} hint={t('tag.pasteHint')} error={error ?? undefined} value={value}
        onChange={e => setValue(e.target.value)} autoComplete="off" spellCheck={false} />
      <Button type="submit" variant="primary">{t('tag.open')}</Button>
    </form>
  </section>;
}
