// The staff workspace (task group 7): one lazy chunk, loaded only from #/admin routes. Operate mode: dense, desktop-first.
import type {ReactNode} from 'react';
import {Link, NavLink, useParams} from 'react-router';
import {ShieldX} from 'lucide-react';
import {useI18n} from '../../i18n/index.tsx';
import {useSession} from '../../session/SessionProvider.tsx';
import {ApiFailure} from '../../api/index.ts';
import {ErrorState} from '../../components/states.tsx';
import type {MessageKey} from '../../i18n/en.ts';
import {CollectionsScreen, ImportsScreen, IngestScreen, ProductScreen, ReviewScreen, SizesScreen} from './Catalogue.tsx';
import {MediaScreen} from './Media.tsx';
import {OffersScreen, OrdersScreen, UnitsScreen} from './Commerce.tsx';
import {ModerationScreen, OpsScreen, RolesScreen} from './People.tsx';
import './staff.css';

type Screen = {key: string; label: MessageKey; caps: string[]; render: (rest: string) => ReactNode};
export const SCREENS: Screen[] = [
  {key: 'review', label: 'sf.review', caps: ['catalogue:ingest'], render: () => <ReviewScreen />},
  {key: 'products', label: 'sf.review', caps: ['catalogue:ingest'], render: rest => <ProductScreen id={rest} />},
  {key: 'imports', label: 'sf.imports', caps: ['catalogue:ingest'], render: rest => <ImportsScreen jobId={rest} />},
  {key: 'ingest', label: 'sf.ingest', caps: ['catalogue:ingest'], render: () => <IngestScreen />},
  {key: 'collections', label: 'sf.collections', caps: ['catalogue:ingest'], render: () => <CollectionsScreen />},
  {key: 'sizes', label: 'sf.sizes', caps: ['catalogue:ingest'], render: () => <SizesScreen />},
  {key: 'media', label: 'sf.media', caps: ['catalogue:media'], render: rest => <MediaScreen productId={rest} />},
  {key: 'offers', label: 'sf.offers', caps: ['commerce:offers'], render: () => <OffersScreen />},
  {key: 'orders', label: 'sf.orders', caps: ['commerce:orders'], render: () => <OrdersScreen />},
  {key: 'units', label: 'sf.units', caps: ['inventory:issue', 'inventory:reissue'], render: () => <UnitsScreen />},
  {key: 'moderation', label: 'sf.moderation', caps: ['social:moderate'], render: () => <ModerationScreen />},
  {key: 'roles', label: 'sf.roles', caps: ['identity:manage_roles'], render: () => <RolesScreen />},
  {key: 'ops', label: 'sf.ops', caps: ['ops:read'], render: () => <OpsScreen />},
];
const NAV = SCREENS.filter(s => s.key !== 'products');
export const STAFF_CAPS = [...new Set(SCREENS.flatMap(s => s.caps))];

export function NotPermitted() {
  const {t} = useI18n();
  return <div className="state staff-denied" role="alert"><ShieldX size={32} aria-hidden /><h2>{t('sf.notPermitted')}</h2><p className="muted">{t('sf.notPermittedBody')}</p>
    <Link to="/">{t('common.goHome')}</Link></div>;
}
/** Server 403s render the same not-permitted state as a missing capability. */
export function StaffError({error, onRetry}: {error: unknown; onRetry?: () => void}) {
  return error instanceof ApiFailure && error.status === 403 ? <NotPermitted /> : <ErrorState error={error} onRetry={onRetry} />;
}

export function StaffRoute() {
  const {t} = useI18n();
  const {me} = useSession();
  const params = useParams();
  const caps = new Set(me?.capabilities ?? []);
  const allowed = (s: Screen) => s.caps.some(c => caps.has(c));
  const visible = NAV.filter(allowed);
  const key = params.screen ?? visible[0]?.key;
  const screen = SCREENS.find(s => s.key === key);
  return <div className="page staff" data-mode="operate">
    <header className="staff-head"><h1>{t('sf.title')}</h1><span className="tag tag-quiet">{t('sf.sandbox')}</span></header>
    {!visible.length ? <NotPermitted /> : <div className="staff-layout">
      <nav className="staff-nav" aria-label={t('sf.title')}>
        {visible.map(s => <NavLink key={s.key} to={`/admin/${s.key}`} className={() => `wr-side-link ${s.key === key || (key === 'products' && s.key === 'review') ? 'is-active' : ''}`}>{t(s.label)}</NavLink>)}
      </nav>
      <section className="staff-main">{!screen || !allowed(screen) ? <NotPermitted /> : screen.render(params['*'] ?? '')}</section>
    </div>}
  </div>;
}
