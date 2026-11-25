/**
 * v2 API client. Before every call it asks the AuthPort for a fresh token and puts it in the
 * Authorization header of that one request. The token is never stored (no localStorage, sessionStorage,
 * cookie, URL or log); it lives only in this function's local variable.
 */
import type {ErrorCode} from '@wearhouse/contracts';

import type {AuthPort} from './auth/port.ts';

export class ApiFailure extends Error {
  readonly status: number;
  readonly code: ErrorCode | string;
  readonly fieldErrors: Array<{field: string; code: string; message: string}>;
  readonly retryAfter: number | null;

  constructor(status: number, code: ErrorCode | string, message: string,
              fieldErrors: Array<{field: string; code: string; message: string}> = [],
              retryAfter: number | null = null) {
    super(message);
    this.status = status;
    this.code = code;
    this.fieldErrors = fieldErrors;
    this.retryAfter = retryAfter;
  }
}

export interface ApiClient {
  call<T>(method: string, path: string, opts?: {body?: unknown; idem?: string; anonymous?: boolean;
                                                query?: Record<string, string | undefined>}): Promise<T>;
  raw(path: string): Promise<Response>;
  upload<T>(method: string, path: string, body: Blob): Promise<T>;
}

export function createApi(auth: AuthPort, base: string, fetchImpl: typeof fetch = fetch): ApiClient {
  async function headersFor(anonymous: boolean, extra: Record<string, string>) {
    const headers: Record<string, string> = {Accept: 'application/json', ...extra};
    if (!anonymous) {
      const token = await auth.token();
      if (token) headers.Authorization = `Bearer ${token}`;
    }
    return headers;
  }

  return {
    async call<T>(method: string, path: string, opts: {body?: unknown; idem?: string; anonymous?: boolean;
                                                       query?: Record<string, string | undefined>} = {}) {
      const url = new URL(base.replace(/\/$/, '') + path);
      for (const [k, v] of Object.entries(opts.query ?? {})) if (v !== undefined) url.searchParams.set(k, v);
      const extra: Record<string, string> = {};
      if (opts.body !== undefined) extra['Content-Type'] = 'application/json';
      if (opts.idem) extra['Idempotency-Key'] = opts.idem;
      const res = await fetchImpl(url, {method, headers: await headersFor(!!opts.anonymous, extra),
                                        body: opts.body === undefined ? undefined : JSON.stringify(opts.body)});
      if (res.status === 204) return undefined as T;
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        const ra = res.headers.get('Retry-After');
        throw new ApiFailure(res.status, data.code ?? 'HTTP_ERROR', data.message ?? 'Request failed.',
                             data.field_errors ?? [], ra ? Number(ra) : null);
      }
      return data as T;
    },
    async raw(path: string) {
      return fetchImpl(base.replace(/\/$/, '') + path, {headers: await headersFor(false, {})});
    },
    async upload<T>(method: string, path: string, body: Blob) {
      const res = await fetchImpl(base.replace(/\/$/, '') + path, {
        method, body, headers: await headersFor(false, {'Content-Type': body.type || 'application/octet-stream'})});
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new ApiFailure(res.status, data.code ?? 'HTTP_ERROR', data.message ?? 'Upload failed.', data.field_errors ?? []);
      }
      return data as T;
    },
  };
}

export function newIdempotencyKey(): string {
  return 'web-' + crypto.randomUUID();
}
