import {useState} from 'react';
import {mediaUrl} from '../api/index.ts';
import {API_BASE} from '../session/SessionProvider.tsx';
import {useI18n} from '../i18n/index.tsx';
import {Silhouette} from './Silhouette.tsx';

export function resolveMedia(uri: string | null | undefined): string | null {
  if (!uri) return null;
  try { return mediaUrl(uri, API_BASE); } catch { return null; }
}

/** Product or garment image with the honest silhouette fallback. */
export function Media({src, alt, slot, quiet}: {src: string | null | undefined; alt: string; slot: string | null | undefined; quiet?: boolean}) {
  const {t} = useI18n();
  const url = resolveMedia(src);
  const [failed, setFailed] = useState(false);
  if (!url || failed) return <Silhouette slot={slot} label={quiet ? undefined : t('label.imageUnavailable')} />;
  // The garment stays fully visible (contain); a blurred copy fills the letterbox instead of flat bars.
  return <span className="media-frame">
    <img className="media-fill" src={url} alt="" aria-hidden loading="lazy" decoding="async" />
    <img className="media" src={url} alt={alt} loading="lazy" decoding="async" onError={() => setFailed(true)} />
  </span>;
}
