import {useEffect, useState} from 'react';
import type {Schemas} from '@wearhouse/contracts';
import {useProduct} from '../data/queries.ts';
import {useSession} from '../session/SessionProvider.tsx';
import {Media} from './Media.tsx';
import {Silhouette} from './Silhouette.tsx';
import {useI18n} from '../i18n/index.tsx';

type Item = Schemas['WardrobeItemOut'];

/** A private photo is fetched with the bearer token and shown through a blob URL that is revoked on unmount. */
function PrivatePhoto({item}: {item: Item}) {
  const {api} = useSession();
  const {t} = useI18n();
  const [url, setUrl] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    const ctrl = new AbortController();
    let objectUrl: string | null = null;
    api.blob('/api/v2/me/wardrobe/items/{item_id}/photo', {path: {item_id: item.id}, signal: ctrl.signal})
      .then(b => { objectUrl = URL.createObjectURL(b); setUrl(objectUrl); })
      .catch(() => { if (!ctrl.signal.aborted) setFailed(true); });
    return () => { ctrl.abort(); if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [api, item.id]);
  if (failed) return <Silhouette slot={item.slot} label={t('label.imageUnavailable')} />;
  return url ? <img className="media" src={url} alt="" /> : <span className="skeleton" style={{height: '100%'}} aria-hidden />;
}

function ProductPhoto({item, quiet}: {item: Item; quiet?: boolean}) {
  const product = useProduct(item.product_id);
  if (product.isPending) return <span className="skeleton" style={{height: '100%'}} aria-hidden />;
  return <Media src={product.data?.media[0]?.uri} alt="" slot={item.slot} quiet={quiet} />;
}

/** `quiet` drops the "Image unavailable" caption in small collage cells (the tile title still names the look). */
export function ItemImage({item, quiet}: {item: Item; quiet?: boolean}) {
  if (item.has_photo) return <PrivatePhoto item={item} />;
  if (item.product_id) return <ProductPhoto item={item} quiet={quiet} />;
  return <Media src={null} alt="" slot={item.slot} quiet={quiet} />;
}
