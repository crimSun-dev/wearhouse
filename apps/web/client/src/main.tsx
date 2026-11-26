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
const AvatarFpsRoute = lazy(() => import('./routes/dev/AvatarFps.tsx').then(m => ({default: m.AvatarFpsRoute})));
// Catalogue and commerce (task group 3).
const CatalogueRoute = lazy(() => import('./routes/store/Catalogue.tsx').then(m => ({default: m.CatalogueRoute})));
const ProductRoute = lazy(() => import('./routes/store/Product.tsx').then(m => ({default: m.ProductRoute})));
const CollectionRoute = lazy(() => import('./routes/store/Product.tsx').then(m => ({default: m.CollectionRoute})));
const TagRoute = lazy(() => import('./routes/store/Tag.tsx').then(m => ({default: m.TagRoute})));
const WishlistRoute = lazy(() => import('./routes/store/Bag.tsx').then(m => ({default: m.WishlistRoute})));
const CartRoute = lazy(() => import('./routes/store/Bag.tsx').then(m => ({default: m.CartRoute})));
const CheckoutRoute = lazy(() => import('./routes/store/Bag.tsx').then(m => ({default: m.CheckoutRoute})));
const OrdersRoute = lazy(() => import('./routes/store/Orders.tsx').then(m => ({default: m.OrdersRoute})));
const ReceiptRoute = lazy(() => import('./routes/store/Orders.tsx').then(m => ({default: m.ReceiptRoute})));
const RedeemRoute = lazy(() => import('./routes/store/Redeem.tsx').then(m => ({default: m.RedeemRoute})));
// Wardrobe (task group 4).
const LibraryRoute = lazy(() => import('./routes/wardrobe/Library.tsx').then(m => ({default: m.LibraryRoute})));
const AddRoute = lazy(() => import('./routes/wardrobe/Library.tsx').then(m => ({default: m.AddRoute})));
const ItemRoute = lazy(() => import('./routes/wardrobe/ItemRoute.tsx').then(m => ({default: m.ItemRoute})));
const LooksRoute = lazy(() => import('./routes/wardrobe/Looks.tsx').then(m => ({default: m.LooksRoute})));
const LookRoute = lazy(() => import('./routes/wardrobe/Looks.tsx').then(m => ({default: m.LookRoute})));
const FittingRoute = lazy(() => import('./routes/wardrobe/Fitting.tsx').then(m => ({default: m.FittingRoute})));
const SuggestRoute = lazy(() => import('./routes/wardrobe/Suggest.tsx').then(m => ({default: m.SuggestRoute})));
const PlannerRoute = lazy(() => import('./routes/wardrobe/Planner.tsx').then(m => ({default: m.PlannerRoute})));
const WearRoute = lazy(() => import('./routes/wardrobe/Planner.tsx').then(m => ({default: m.WearRoute})));
const WeatherRoute = lazy(() => import('./routes/wardrobe/Weather.tsx').then(m => ({default: m.WeatherRoute})));
const SizesRoute = lazy(() => import('./routes/wardrobe/Weather.tsx').then(m => ({default: m.SizesRoute})));
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
    {path: '/dev/avatar-fps', element: page(<AvatarFpsRoute />)},
    // Catalogue and commerce: public discovery, private bag, orders and redemption.
    {path: '/catalogue', element: <OnboardingGate>{page(<CatalogueRoute />)}</OnboardingGate>},
    {path: '/catalogue/products/:id', element: <OnboardingGate>{page(<ProductRoute />)}</OnboardingGate>},
    {path: '/collections/:slug', element: <OnboardingGate>{page(<CollectionRoute />)}</OnboardingGate>},
    {path: '/items', element: page(<TagRoute />)}, {path: '/items/:serial', element: page(<TagRoute />)},
    {path: '/wishlist', element: <Private>{page(<WishlistRoute />)}</Private>},
    {path: '/cart', element: <Private>{page(<CartRoute />)}</Private>},
    {path: '/checkout', element: <Private>{page(<CheckoutRoute />)}</Private>},
    {path: '/orders', element: <Private>{page(<OrdersRoute />)}</Private>},
    {path: '/orders/:id', element: <Private>{page(<ReceiptRoute />)}</Private>},
    {path: '/redeem', element: <Private>{page(<RedeemRoute />)}</Private>},
    // Wardrobe: library, inspector, looks, fitting room, suggestions, planner, wear log, weather, sizes.
    ...([['/wardrobe', <LibraryRoute />], ['/wardrobe/add', <AddRoute />], ['/wardrobe/items/:id', <ItemRoute />],
      ['/wardrobe/looks', <LooksRoute />], ['/wardrobe/looks/:id', <LookRoute />], ['/wardrobe/fitting-room', <FittingRoute />],
      ['/wardrobe/suggestions', <SuggestRoute />], ['/wardrobe/planner', <PlannerRoute />], ['/wardrobe/wear', <WearRoute />],
      ['/weather', <WeatherRoute />], ['/sizes', <SizesRoute />]] as const).map(([path, el]) => ({path, element: <Private>{page(el)}</Private>})),
    // Public surfaces built in later task groups.
    {path: '/catalogue/*', element: <NotFoundRoute />},
    {path: '/u/*', element: <BuildingRoute />}, {path: '/shares/*', element: <BuildingRoute />},
    // Private surfaces built in later task groups.
    ...['/community/*', '/community', '/profile/*', '/profile', '/settings/*', '/settings',
      '/notifications', '/admin/*', '/admin']
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
