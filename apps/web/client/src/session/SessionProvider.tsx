import {createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode} from 'react';
import {useQuery, useQueryClient} from '@tanstack/react-query';
import type {MeResponse} from '@wearhouse/contracts';
import type {AuthPort, BrokerSession} from '../auth/port.ts';
import {createApi} from '../api/index.ts';

export const API_BASE = (import.meta.env.VITE_WEARHOUSE_API_BASE as string | undefined) || 'http://127.0.0.1:8100/api/v2';
export type Api = ReturnType<typeof createApi>;
export type SessionStatus = 'loading' | 'signedOut' | 'onboarding' | 'ready' | 'unavailable';

type Session = {
  auth: AuthPort | null;
  api: Api;
  status: SessionStatus;
  me: MeResponse | null;
  broker: BrokerSession | null;
  /** Prefix for every private query key, so one user's cache never serves another. */
  userKey: readonly unknown[];
  can: (capability: string) => boolean;
  isStaff: boolean;
  refresh: () => Promise<void>;
  signOut: () => Promise<void>;
};

const STAFF = ['catalogue:ingest', 'catalogue:media', 'commerce:offers', 'commerce:orders', 'inventory:issue',
  'inventory:reissue', 'social:moderate', 'identity:manage_roles', 'ops:read'];
const Ctx = createContext<Session | null>(null);

// The identity broker client is large, so it loads in its own chunk once, right after the shell renders.
let authLoad: Promise<AuthPort | null> | null = null;
export function loadAuth(): Promise<AuthPort | null> {
  authLoad ??= import('../auth/provider.ts').then(m => { try { return m.createAuth(); } catch { return null; } }, () => null);
  return authLoad;
}
// A plain per-device hint (no token, no identity): did this browser have a session last time? When it did not,
// screens can show their signed-out form at once instead of waiting for the identity broker to answer.
const HAD_SESSION = 'wearhouse.hadSession';
export function likelySignedIn(): boolean {
  try { return localStorage.getItem(HAD_SESSION) === '1'; } catch { return false; }
}
function rememberSession(had: boolean) {
  try { if (had) localStorage.setItem(HAD_SESSION, '1'); else localStorage.removeItem(HAD_SESSION); } catch { /* not persisted */ }
}
const lazyToken: Pick<AuthPort, 'token'> = {token: async () => (await loadAuth())?.token() ?? null};

export function SessionProvider({children}: {children: ReactNode}) {
  const client = useQueryClient();
  const [auth, setAuth] = useState<AuthPort | null>(null);
  useEffect(() => { void loadAuth().then(setAuth); }, []);
  const api = useMemo(() => createApi(lazyToken, API_BASE), []);

  const query = useQuery({
    queryKey: ['session'],
    staleTime: Infinity, retry: false,
    queryFn: async () => {
      const auth = await loadAuth();
      if (!auth) return {broker: null, me: null, unavailable: true};
      const broker = await auth.session();
      if (!broker) return {broker: null, me: null, unavailable: false};
      const me = await api.call('get', '/api/v2/me', {});
      return {broker, me, unavailable: false};
    },
  });

  const refresh = useCallback(async () => { await client.invalidateQueries({queryKey: ['session']}); }, [client]);
  const signOut = useCallback(async () => {
    try { await (await loadAuth())?.signOut(); } finally {
      // Private data never survives a sign-out: drop every private query, then re-read the (now empty) session.
      client.removeQueries({predicate: q => q.queryKey[0] !== 'session' && q.queryKey[0] !== 'public'});
      await client.refetchQueries({queryKey: ['session']});
    }
  }, [client]);

  const value = useMemo<Session>(() => {
    const data = query.data;
    const me = data?.me ?? null;
    const status: SessionStatus = query.isPending ? 'loading'
      : query.isError ? 'signedOut'
      : data?.unavailable ? 'unavailable'
      : !me ? 'signedOut'
      : me.needs_onboarding ? 'onboarding' : 'ready';
    const caps = new Set(me?.capabilities ?? []);
    return {
      auth, api, status, me, broker: data?.broker ?? null,
      userKey: ['u', me?.user_id ?? 'anon'],
      can: c => caps.has(c), isStaff: STAFF.some(c => caps.has(c)),
      refresh, signOut,
    };
  }, [auth, api, query.data, query.isPending, query.isError, refresh, signOut]);

  useEffect(() => {
    if (value.status === 'ready' || value.status === 'onboarding') rememberSession(true);
    else if (value.status === 'signedOut') rememberSession(false);
  }, [value.status]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useSession(): Session {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error('useSession outside SessionProvider');
  return ctx;
}
