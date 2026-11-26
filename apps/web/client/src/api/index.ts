import type {ApiError, paths} from '@wearhouse/contracts';
import type {AuthPort} from '../auth/port';

type Method = 'get' | 'post' | 'patch' | 'put' | 'delete';
type Route<M extends Method> = {[P in keyof paths]: paths[P][M] extends object ? P : never}[keyof paths];
type JsonContent<T> = T extends {content: {'application/json': infer J}} ? J : Blob;
type Params<T> = T extends {parameters: infer P} ? Pick<P, Extract<keyof P, 'path' | 'query'>> : never;
type Body<T> = T extends {requestBody: infer B} ? {body: JsonContent<B>} :
  T extends {requestBody?: infer B} ? {body?: JsonContent<NonNullable<B>>} : {body?: never};
type Result<T> = T extends {responses: infer R} ? JsonContent<R[Extract<keyof R, 200 | 201 | 202>]> |
  (204 extends keyof R ? void : never) : never;
type Options<T> = Params<T> & Body<T> & {
  anonymous?: boolean;
  signal?: AbortSignal;
  intent?: ReturnType<typeof createIntent>;
};

export function createIntent() {
  let previous: string | undefined;
  let key: string;
  return (serialized: string) => {
    if (previous !== serialized) {
      previous = serialized;
      key = 'web-' + crypto.randomUUID();
    }
    return key;
  };
}

export class ApiFailure extends Error {
  constructor(readonly status: number, readonly code: string, message: string,
    readonly fieldErrors: NonNullable<ApiError['field_errors']>, readonly retryAfter: number | null,
    readonly requestId: string | null) { super(message); }
}

function retryDelay(header: string | null) {
  if (!header) return null;
  if (/^\d+$/.test(header)) return Number(header);
  const date = Date.parse(header);
  return Number.isFinite(date) ? Math.max(0, Math.ceil((date - Date.now()) / 1000)) : null;
}

const protectedPosts = new Set<string>(['/api/v2/me/friend-requests', '/api/v2/me/checkout',
  '/api/v2/redemptions', '/api/v2/me/wear', '/api/v2/admin/unit-batches']);

export function mediaUrl(uri: string, base: string) {
  const media = new URL(uri, new URL(base).origin);
  if (!['https:', 'http:'].includes(media.protocol)) throw new Error('Unsupported media URL');
  return media.href;
}

export function createApi(auth: Pick<AuthPort, 'token'>, base: string, fetcher = fetch, timeout = 15000) {
  async function request(method: Method, route: keyof paths,
    opts: {path?: object; query?: object; body?: unknown; signal?: AbortSignal;
      anonymous?: boolean; intent?: ReturnType<typeof createIntent>}, binary: boolean) {
    const timeoutSignal = AbortSignal.timeout(timeout);
    const signal = opts.signal ? AbortSignal.any([opts.signal, timeoutSignal]) : timeoutSignal;
    signal.throwIfAborted();
    const params = (opts.path ?? {}) as Record<string, unknown>;
    const path = route.slice('/api/v2'.length).replace(/\{([^}]+)\}/g, (_, name) => {
      if (params[name] == null) throw new Error('Missing route parameter: ' + name);
      return encodeURIComponent(String(params[name]));
    });
    const url = new URL(base.replace(/\/$/, '') + path);
    for (const [name, value] of Object.entries(opts.query ?? {})) {
      if (value != null) for (const entry of Array.isArray(value) ? value : [value]) url.searchParams.append(name, String(entry));
    }
    const headers = new Headers({Accept: binary ? '*/*' : 'application/json'});
    const body = opts.body instanceof Blob ? opts.body : JSON.stringify(opts.body);
    if (body !== undefined) headers.set('Content-Type', body instanceof Blob ? body.type || 'application/octet-stream' : 'application/json');
    if (method === 'post' && protectedPosts.has(route) && !opts.intent) throw new Error('An idempotency intent is required');
    if (opts.intent) headers.set('Idempotency-Key', opts.intent(JSON.stringify([method, url.href, body])));
    let onAbort: () => void = () => {};
    const aborted = new Promise<never>((_, reject) => {
      onAbort = () => reject(signal.reason);
      signal.addEventListener('abort', onAbort, {once: true});
    });
    async function send(retried = false): Promise<unknown> {
      const token = opts.anonymous ? null : await auth.token();
      signal.throwIfAborted();
      if (token) headers.set('Authorization', 'Bearer ' + token);
      const res = await fetcher(url, {method: method.toUpperCase(), body, signal, headers, redirect: 'error'});
      signal.throwIfAborted();
      if (!res.ok) {
        const e: Partial<ApiError> = await res.json().catch(() => ({}));
        if (e?.code === 'REQUEST_IN_PROGRESS' && opts.intent && !retried) {
          const wait = (retryDelay(res.headers.get('Retry-After')) ?? 1) * 1000;
          await Promise.race([new Promise(resolve => setTimeout(resolve, Math.min(wait, timeout))), aborted]);
          signal.throwIfAborted();
          return send(true);
        }
        throw new ApiFailure(res.status, e?.code ?? 'HTTP_ERROR', e?.message ?? 'Request failed.',
          e?.field_errors ?? [], retryDelay(res.headers.get('Retry-After')), e?.request_id ?? res.headers.get('X-Request-ID'));
      }
      if (res.status === 204) return undefined;
      return binary ? res.blob() : res.json();
    }
    try { return await Promise.race([send(), aborted]); }
    finally { signal.removeEventListener('abort', onAbort); }
  }
  return {
    async call<M extends Method, P extends Route<M>>(method: M, path: P, opts: Options<paths[P][M]>): Promise<Result<paths[P][M]>> {
      return await request(method, path, opts, false) as Result<paths[P][M]>;
    },
    async blob<P extends Route<'get'>>(path: P, opts: Options<paths[P]['get']>): Promise<Blob> {
      return await request('get', path, opts, true) as Blob;
    },
  };
}

export function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  try { link.click(); } finally { setTimeout(() => URL.revokeObjectURL(url), 0); }
}
