// Catalogue and commerce data (task group 3). Public reads are keyed under 'public' and shared across sessions;
// private reads start with the session's userKey so sign-out clears them. Activation keys are never cached here.
import {useInfiniteQuery, useMutation, useQuery, useQueryClient} from '@tanstack/react-query';
import {useSession} from '../session/SessionProvider.tsx';
import type {createIntent} from '../api/index.ts';

export type BrowseFilters = {
  q?: string; category?: string; colour?: string; slot?: string; size?: string; sort?: 'newest' | 'name';
  my_sizes?: boolean; hide_owned?: boolean;
};
const PAGE = 24;

/** Cursor-paged browse. Each filter set is its own query key, so a late response for an old filter set
 *  can never replace the results on screen (the "out-of-order response dropped" rule). */
export function useBrowse(filters: BrowseFilters) {
  const {api, userKey, status} = useSession();
  const personal = status === 'ready' && (filters.my_sizes || filters.hide_owned);
  const query = Object.fromEntries(Object.entries({...filters, limit: PAGE}).filter(([, v]) => v !== undefined && v !== '' && v !== false));
  return useInfiniteQuery({
    queryKey: [...(personal ? userKey : ['public']), 'browse', query],
    initialPageParam: undefined as string | undefined,
    queryFn: ({signal, pageParam}) => api.call('get', '/api/v2/catalogue/products',
      {signal, anonymous: !personal, query: {...query, ...(pageParam ? {cursor: pageParam} : {})}}),
    getNextPageParam: last => last.next_cursor ?? undefined,
  });
}

export function useFacets() {
  const {api} = useSession();
  return useQuery({queryKey: ['public', 'facets'], staleTime: 5 * 60_000,
    queryFn: ({signal}) => api.call('get', '/api/v2/catalogue/facets', {signal, anonymous: true})});
}

export function useSizeRegistry() {
  const {api} = useSession();
  return useQuery({queryKey: ['public', 'size-registry'], staleTime: 30 * 60_000,
    queryFn: ({signal}) => api.call('get', '/api/v2/catalogue/sizes', {signal, anonymous: true})});
}

export function useCollection(slug: string) {
  const {api} = useSession();
  return useQuery({queryKey: ['public', 'collection', slug],
    queryFn: ({signal}) => api.call('get', '/api/v2/catalogue/collections/{slug}', {signal, anonymous: true, path: {slug}})});
}

export function useOffer(id: string) {
  const {api} = useSession();
  return useQuery({queryKey: ['public', 'offer', id], staleTime: 15_000,
    queryFn: ({signal}) => api.call('get', '/api/v2/commerce/products/{product_id}/offer', {signal, anonymous: true, path: {product_id: id}})});
}

export function useSimilar(id: string) {
  const {api} = useSession();
  return useQuery({queryKey: ['public', 'similar', id], staleTime: 5 * 60_000,
    queryFn: ({signal}) => api.call('get', '/api/v2/catalogue/products/{product_id}/similar',
      {signal, anonymous: true, path: {product_id: id}, query: {limit: 12}})});
}

export function usePublicItem(serial: string) {
  const {api} = useSession();
  return useQuery({queryKey: ['public', 'item', serial], enabled: !!serial,
    queryFn: ({signal}) => api.call('get', '/api/v2/items/{serial}', {signal, anonymous: true, path: {serial}})});
}

/** Product ids the user owns (first 100 owned items), for the "in your wardrobe" marker. */
export function useOwnedProductIds() {
  const {api, userKey, status} = useSession();
  return useQuery({queryKey: [...userKey, 'owned-items'], enabled: status === 'ready',
    queryFn: ({signal}) => api.call('get', '/api/v2/me/items', {signal, query: {limit: 100}}),
    select: page => new Set(page.items.map(i => i.product.id))});
}

export function useWishlist() {
  const {api, userKey, status} = useSession();
  return useQuery({queryKey: [...userKey, 'wishlist'], enabled: status === 'ready',
    queryFn: ({signal}) => api.call('get', '/api/v2/me/wishlist', {signal})});
}

export function useWishlistToggle() {
  const {api, userKey} = useSession();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({id, on}: {id: string; on: boolean}) => {
      if (on) await api.call('put', '/api/v2/me/wishlist/{product_id}', {path: {product_id: id}});
      else await api.call('delete', '/api/v2/me/wishlist/{product_id}', {path: {product_id: id}});
    },
    onSettled: () => qc.invalidateQueries({queryKey: [...userKey, 'wishlist']}),
  });
}

export function useCart() {
  const {api, userKey, status} = useSession();
  return useQuery({queryKey: [...userKey, 'cart'], enabled: status === 'ready',
    queryFn: ({signal}) => api.call('get', '/api/v2/me/cart', {signal})});
}

export function useCartLine() {
  const {api, userKey} = useSession();
  const qc = useQueryClient();
  const key = [...userKey, 'cart'];
  return useMutation({
    mutationFn: ({id, quantity, size}: {id: string; quantity: number; size?: string | null}) => quantity > 0
      ? api.call('put', '/api/v2/me/cart/{product_id}', {path: {product_id: id}, body: {quantity, size: size ?? null}})
      : api.call('delete', '/api/v2/me/cart/{product_id}', {path: {product_id: id}, query: size ? {size} : {}}),
    onSuccess: cart => qc.setQueryData(key, cart),
    onError: () => qc.invalidateQueries({queryKey: key}),
  });
}

export function useCheckout() {
  const {api, userKey} = useSession();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({expected, intent}: {expected: number; intent: ReturnType<typeof createIntent>}) =>
      api.call('post', '/api/v2/me/checkout', {body: {expected_total_idr: expected}, intent}),
    onSuccess: receipt => {
      qc.setQueryData([...userKey, 'order', receipt.id], receipt);
      void qc.invalidateQueries({queryKey: [...userKey, 'cart']});
      void qc.invalidateQueries({queryKey: [...userKey, 'orders']});
    },
  });
}

export function useOrders() {
  const {api, userKey, status} = useSession();
  return useInfiniteQuery({
    queryKey: [...userKey, 'orders'], enabled: status === 'ready',
    initialPageParam: undefined as string | undefined,
    queryFn: ({signal, pageParam}) => api.call('get', '/api/v2/me/orders', {signal, query: {limit: 20, ...(pageParam ? {cursor: pageParam} : {})}}),
    getNextPageParam: last => last.next_cursor ?? undefined,
  });
}

export function useOrder(id: string) {
  const {api, userKey, status} = useSession();
  return useQuery({queryKey: [...userKey, 'order', id], enabled: status === 'ready',
    queryFn: ({signal}) => api.call('get', '/api/v2/me/orders/{order_id}', {signal, path: {order_id: id}})});
}
