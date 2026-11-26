// Wardrobe data (task group 4). Every key starts with the session's userKey, so sign-out clears it.
import {useQuery, useQueryClient} from '@tanstack/react-query';
import {useSession} from '../session/SessionProvider.tsx';
import type {Schemas} from '@wearhouse/contracts';

export type Item = Schemas['WardrobeItemOut'];
export type Look = Schemas['LookOut'];
export type LookRevision = Schemas['LookRevisionOut'];
export type Shelf = Schemas['ShelfOut'];
export type ItemFilters = {slot?: string; care_state?: string; shelf_id?: string; size?: string; sort?: string};

export function useItems(filters: ItemFilters = {}) {
  const {api, userKey, status} = useSession();
  const query = Object.fromEntries(Object.entries(filters).filter(([, v]) => v));
  return useQuery({queryKey: [...userKey, 'wardrobe-items', query], enabled: status === 'ready',
    queryFn: ({signal}) => api.call('get', '/api/v2/me/wardrobe/items', {signal, query})});
}

export function useItem(id: string) {
  const {api, userKey, status} = useSession();
  return useQuery({queryKey: [...userKey, 'wardrobe-item', id], enabled: status === 'ready' && !!id,
    queryFn: ({signal}) => api.call('get', '/api/v2/me/wardrobe/items/{item_id}', {signal, path: {item_id: id}})});
}

/** Provenance of a verified item. A verified wardrobe item's id is its owned-item id (wardrobe/application.py). */
export function useOwnedItem(id: string, enabled: boolean) {
  const {api, userKey, status} = useSession();
  return useQuery({queryKey: [...userKey, 'owned-item', id], enabled: status === 'ready' && enabled,
    queryFn: ({signal}) => api.call('get', '/api/v2/me/items/{item_id}', {signal, path: {item_id: id}})});
}

export function useShelves() {
  const {api, userKey, status} = useSession();
  return useQuery({queryKey: [...userKey, 'shelves'], enabled: status === 'ready',
    queryFn: ({signal}) => api.call('get', '/api/v2/me/wardrobe/shelves', {signal})});
}

export function useRegistry() {
  const {api} = useSession();
  return useQuery({queryKey: ['public', 'slot-registry'], staleTime: 60 * 60_000,
    queryFn: ({signal}) => api.call('get', '/api/v2/wardrobe/slots', {signal, anonymous: true})});
}

export function useLook(id: string) {
  const {api, userKey, status} = useSession();
  return useQuery({queryKey: [...userKey, 'look', id], enabled: status === 'ready' && !!id,
    queryFn: ({signal}) => api.call('get', '/api/v2/me/looks/{look_id}', {signal, path: {look_id: id}})});
}

export function useWearLog(from: string, to: string) {
  const {api, userKey, status} = useSession();
  return useQuery({queryKey: [...userKey, 'wear', from, to], enabled: status === 'ready',
    queryFn: ({signal}) => api.call('get', '/api/v2/me/wear', {signal, query: {from, to}})});
}

export function useUsualSizes() {
  const {api, userKey, status} = useSession();
  return useQuery({queryKey: [...userKey, 'usual-sizes'], enabled: status === 'ready',
    queryFn: ({signal}) => api.call('get', '/api/v2/me/sizes', {signal})});
}

/** Invalidates the given private keys (prefix match), e.g. after a write that touches several views. */
export function useRefresh() {
  const {userKey} = useSession();
  const qc = useQueryClient();
  return (...keys: string[]) => Promise.all(keys.map(k => qc.invalidateQueries({queryKey: [...userKey, k]})));
}

/** Local date (Asia/Jakarta) as YYYY-MM-DD, optionally offset by whole days. */
export function jakartaDate(offsetDays = 0, from?: string) {
  const base = from ? new Date(`${from}T12:00:00+07:00`) : new Date();
  base.setUTCDate(base.getUTCDate() + offsetDays);
  return new Intl.DateTimeFormat('en-CA', {timeZone: 'Asia/Jakarta'}).format(base);
}

/** Planner days planned in this page session, so the planner plays its drop-in moment once for each (web-motion 5). */
export const justPlanned = new Set<string>();
