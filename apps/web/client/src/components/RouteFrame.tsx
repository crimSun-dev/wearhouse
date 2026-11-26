import {Component, Suspense, type ReactNode} from 'react';
import {useLocation} from 'react-router';
import {useI18n} from '../i18n/index.tsx';
import {Button} from './ui.tsx';
import {Skeleton} from './ui.tsx';

/** Shown while a screen's code or the session is still loading, so a slow network never shows an empty page.
 * It fades in after a short delay (see .page-pending), so fast loads do not flash a placeholder. */
export function PagePending() {
  const {t} = useI18n();
  return <div className="page page-pending" aria-busy="true">
    <span className="visually-hidden" role="status">{t('common.loading')}</span>
    <Skeleton ratio="5 / 1" className="page-pending-head" />
    <Skeleton ratio="3 / 1" />
  </div>;
}

function ScreenFailed() {
  const {t} = useI18n();
  // A screen whose code failed to download stays failed in this page's module cache: reloading is the recovery.
  return <div className="page"><div className="state state-error" role="alert">
    <p>{t('common.offline')}</p>
    <div className="state-actions"><Button variant="secondary" onClick={() => window.location.reload()}>{t('common.retry')}</Button></div>
  </div></div>;
}

class Boundary extends Component<{children: ReactNode}, {failed: boolean}> {
  state = {failed: false};
  static getDerivedStateFromError() { return {failed: true}; }
  render() { return this.state.failed ? <ScreenFailed /> : this.props.children; }
}

/** Wraps every routed screen: a placeholder while it loads, and a recoverable message (never a white page) when its
 * code cannot be fetched or it throws while rendering. The boundary resets on navigation. */
export function RouteFrame({children}: {children: ReactNode}) {
  const location = useLocation();
  return <Boundary key={location.pathname}><Suspense fallback={<PagePending />}>{children}</Suspense></Boundary>;
}
