// Read hooks shared across screens. Private keys start with the session's userKey; sign-out clears the cache.
import {useQuery} from '@tanstack/react-query';
import {useSession} from '../session/SessionProvider.tsx';

const visibleOnly = {refetchIntervalInBackground: false} as const;

export function useMyWeather() {
  const {api, userKey, status} = useSession();
  return useQuery({queryKey: [...userKey, 'weather'], enabled: status === 'ready', staleTime: 10 * 60_000,
    queryFn: ({signal}) => api.call('get', '/api/v2/me/weather', {signal})});
}

export function useWardrobeItems() {
  const {api, userKey, status} = useSession();
  return useQuery({queryKey: [...userKey, 'wardrobe-items'], enabled: status === 'ready',
    queryFn: ({signal}) => api.call('get', '/api/v2/me/wardrobe/items', {signal, query: {}})});
}

export function useLooks() {
  const {api, userKey, status} = useSession();
  return useQuery({queryKey: [...userKey, 'looks'], enabled: status === 'ready',
    queryFn: ({signal}) => api.call('get', '/api/v2/me/looks', {signal})});
}

/** The planner's seven days starting at `from` (a Jakarta local date). A read with no side effects. */
export function usePlanner(from: string) {
  const {api, userKey, status} = useSession();
  return useQuery({queryKey: [...userKey, 'planner', from], enabled: status === 'ready',
    queryFn: ({signal}) => api.call('get', '/api/v2/me/planner', {signal, query: {from}})});
}

export function useFeed() {
  const {api, userKey, status} = useSession();
  return useQuery({queryKey: [...userKey, 'feed'], enabled: status === 'ready',
    queryFn: ({signal}) => api.call('get', '/api/v2/me/feed', {signal, query: {limit: 12}})});
}

export function useForMe() {
  const {api, userKey, status} = useSession();
  return useQuery({queryKey: [...userKey, 'for-me'], enabled: status === 'ready',
    queryFn: ({signal}) => api.call('get', '/api/v2/me/recommendations/products', {signal, query: {limit: 12}})});
}

export function useCounts() {
  const {api, userKey, status} = useSession();
  const on = status === 'ready';
  const unread = useQuery({queryKey: [...userKey, 'unread'], enabled: on, refetchInterval: 60_000, ...visibleOnly,
    queryFn: ({signal}) => api.call('get', '/api/v2/me/notifications/unread-count', {signal})});
  const wishlist = useQuery({queryKey: [...userKey, 'wishlist'], enabled: on,
    queryFn: ({signal}) => api.call('get', '/api/v2/me/wishlist', {signal})});
  const cart = useQuery({queryKey: [...userKey, 'cart'], enabled: on,
    queryFn: ({signal}) => api.call('get', '/api/v2/me/cart', {signal})});
  return {
    unread: unread.data?.unread ?? 0,
    wishlist: wishlist.data?.items.length ?? 0,
    cart: cart.data?.lines.reduce((n, l) => n + l.quantity, 0) ?? 0,
  };
}

export function useCollections() {
  const {api} = useSession();
  return useQuery({queryKey: ['public', 'collections'], staleTime: 5 * 60_000,
    queryFn: ({signal}) => api.call('get', '/api/v2/catalogue/collections', {signal, anonymous: true})});
}

export function useNewest(limit = 16) {
  const {api} = useSession();
  return useQuery({queryKey: ['public', 'newest', limit], staleTime: 5 * 60_000,
    queryFn: ({signal}) => api.call('get', '/api/v2/catalogue/products', {signal, anonymous: true, query: {sort: 'newest', limit}})});
}

/** Public product detail (cached); used to show a verified garment's catalogue image. */
export function useProduct(id: string | null | undefined) {
  const {api} = useSession();
  return useQuery({queryKey: ['public', 'product', id], enabled: !!id, staleTime: 30 * 60_000,
    queryFn: ({signal}) => api.call('get', '/api/v2/catalogue/products/{product_id}', {signal, anonymous: true, path: {product_id: id!}})});
}
