import {lazy, StrictMode, Suspense, type ReactNode} from 'react';
import {createRoot} from 'react-dom/client';
import {createHashRouter, Navigate, RouterProvider, useLocation} from 'react-router';
import {QueryClient, QueryClientProvider} from '@tanstack/react-query';
import {ApiFailure} from './api/index.ts';
import {SessionProvider, useSession} from './session/SessionProvider.tsx';
import {SettingsProvider} from './settings/SettingsProvider.tsx';
import {FocusRoot} from './focus/FocusZone.tsx';
import {AppShell} from './shell/AppShell.tsx';
import {HomeRoute} from './routes/Home.tsx';
import {BuildingRoute, NotFoundRoute} from './routes/misc.tsx';

// Screens that are not on the first paint load on demand, keeping the app entry inside its size budget.
const AboutRoute = lazy(() => import('./routes/About.tsx').then(m => ({default: m.AboutRoute})));
const SignInRoute = lazy(() => import('./routes/Auth.tsx').then(m => ({default: m.SignInRoute})));
const SignUpRoute = lazy(() => import('./routes/Auth.tsx').then(m => ({default: m.SignUpRoute})));
const ResetRoute = lazy(() => import('./routes/Auth.tsx').then(m => ({default: m.ResetRoute})));
const OnboardingRoute = lazy(() => import('./routes/Onboarding.tsx').then(m => ({default: m.OnboardingRoute})));
const DevKitRoute = lazy(() => import('./routes/misc.tsx').then(m => ({default: m.DevKitRoute})));
const page = (node: ReactNode) => <Suspense fallback={null}>{node}</Suspense>;
import './theme/global.css';

const queryClient = new QueryClient({defaultOptions: {queries: {
  staleTime: 30_000, refetchOnWindowFocus: false,
  retry: (count, error) => !(error instanceof ApiFailure && error.status < 500) && count < 2,
}}});

/** Private routes need a session; onboarding comes before anything private. */
function Private({children}: {children: ReactNode}) {
  const {status} = useSession();
  const location = useLocation();
  if (status === 'loading') return null;
  if (status === 'onboarding') return <Navigate to="/onboarding" replace />;
  if (status !== 'ready') return <Navigate to="/signin" replace state={{from: location.pathname}} />;
  return <>{children}</>;
}
function OnboardingGate({children}: {children: ReactNode}) {
  const {status} = useSession();
  return status === 'onboarding' ? <Navigate to="/onboarding" replace /> : <>{children}</>;
}
function SignedOutOnly({children}: {children: ReactNode}) {
  const {status} = useSession();
  return status === 'ready' || status === 'onboarding' ? <Navigate to="/" replace /> : <>{children}</>;
}

const building = <Private><BuildingRoute /></Private>;
const router = createHashRouter([{
  element: <AppShell />,
  children: [
    {path: '/', element: <OnboardingGate><HomeRoute /></OnboardingGate>},
    {path: '/about', element: page(<AboutRoute />)},
    {path: '/signin', element: <SignedOutOnly>{page(<SignInRoute />)}</SignedOutOnly>},
    {path: '/signup', element: <SignedOutOnly>{page(<SignUpRoute />)}</SignedOutOnly>},
    {path: '/reset', element: page(<ResetRoute />)},
    {path: '/onboarding', element: page(<OnboardingRoute />)},
    {path: '/dev/kit', element: page(<DevKitRoute />)},
    // Public surfaces built in later task groups.
    {path: '/catalogue/*', element: <BuildingRoute />}, {path: '/catalogue', element: <BuildingRoute />},
    {path: '/collections/*', element: <BuildingRoute />}, {path: '/items/*', element: <BuildingRoute />},
    {path: '/u/*', element: <BuildingRoute />}, {path: '/shares/*', element: <BuildingRoute />},
    // Private surfaces built in later task groups.
    ...['/wardrobe/*', '/wardrobe', '/community/*', '/community', '/profile/*', '/profile', '/settings/*', '/settings', '/redeem',
      '/orders/*', '/orders', '/wishlist', '/cart', '/checkout', '/notifications', '/sizes', '/weather', '/admin/*', '/admin']
      .map(path => ({path, element: building})),
    {path: '*', element: <NotFoundRoute />},
  ],
}]);

createRoot(document.getElementById('app')!).render(<StrictMode>
  <QueryClientProvider client={queryClient}>
    <SessionProvider>
      <SettingsProvider>
        <FocusRoot><RouterProvider router={router} /></FocusRoot>
      </SettingsProvider>
    </SessionProvider>
  </QueryClientProvider>
</StrictMode>);
