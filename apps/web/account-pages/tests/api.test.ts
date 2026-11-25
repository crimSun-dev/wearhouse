// add-wearhouse-accounts 8.2: tokens are fetched per call, kept in memory only, and gone after sign-out.
import assert from 'node:assert/strict';
import test from 'node:test';

import {ApiFailure, createApi} from '../src/api.ts';
import type {AuthPort} from '../src/auth/port.ts';
import {describe} from '../src/messages.ts';

function fakeAuth() {
  let n = 0;
  let signedIn = true;
  const port: AuthPort = {
    kind: 'e2e-fake',
    async session() { return signedIn ? {userId: 'u', name: null} : null; },
    async signInWithGoogle() { signedIn = true; },
    async token() { return signedIn ? `tok-${++n}` : null; },
    async signOut() { signedIn = false; },
    async revokeSessions() {},
    async listMethods() { return []; },
    async deleteBrokerUser() { return 'unsupported'; },
    async signInWithEmail() {}, async signUpWithEmail() {}, async requestPasswordReset() {}, async resetPassword() {},
    async changePassword() {}, async sendVerificationEmail() {}, async listSessions() { return []; },
    async revokeSession() {}, async revokeOtherSessions() {},
  };
  return {port, calls: () => n};
}

function recordingFetch(status = 200, body: unknown = {ok: true}, headers: Record<string, string> = {}) {
  const seen: {url: string; headers: Record<string, string>; body?: string}[] = [];
  const impl = (async (url: URL | string, init: RequestInit = {}) => {
    seen.push({url: String(url), headers: (init.headers ?? {}) as Record<string, string>, body: init.body as string});
    return new Response(status === 204 ? null : JSON.stringify(body), {status, headers});
  }) as typeof fetch;
  return {impl, seen};
}

function trapStorageAndConsole() {
  const writes: string[] = [];
  const store = {setItem: (k: string) => writes.push(k), getItem: () => null, removeItem: () => {}, clear: () => {}};
  const g = globalThis as Record<string, unknown>;
  const saved = {ls: g.localStorage, ss: g.sessionStorage, log: console.log, debug: console.debug,
                 info: console.info, warn: console.warn, error: console.error};
  const logged: string[] = [];
  g.localStorage = store;
  g.sessionStorage = store;
  for (const k of ['log', 'debug', 'info', 'warn', 'error'] as const) console[k] = (...a: unknown[]) => logged.push(a.join(' '));
  return {writes, logged, restore() {
    g.localStorage = saved.ls; g.sessionStorage = saved.ss;
    Object.assign(console, {log: saved.log, debug: saved.debug, info: saved.info, warn: saved.warn, error: saved.error});
  }};
}

test('a fresh token per call, only in the Authorization header', async () => {
  const {port, calls} = fakeAuth();
  const f = recordingFetch();
  const trap = trapStorageAndConsole();
  try {
    const api = createApi(port, 'http://api.test/api/v2', f.impl);
    await api.call('GET', '/me');
    await api.call('POST', '/me/friend-requests', {body: {handle: 'x'}, idem: 'web-1'});
    assert.equal(calls(), 2);
    assert.equal(f.seen[0].headers.Authorization, 'Bearer tok-1');
    assert.equal(f.seen[1].headers.Authorization, 'Bearer tok-2');
    assert.equal(f.seen[1].headers['Idempotency-Key'], 'web-1');
    for (const s of f.seen) assert.ok(!s.url.includes('tok-'), 'token must never be in the URL');
    assert.deepEqual(trap.writes, [], 'nothing written to localStorage/sessionStorage');
    assert.ok(!trap.logged.join(' ').includes('tok-'), 'token never logged');
  } finally {
    trap.restore();
  }
});

test('after sign-out no token is sent (nothing was cached)', async () => {
  const {port} = fakeAuth();
  const f = recordingFetch();
  const api = createApi(port, 'http://api.test/api/v2', f.impl);
  await api.call('GET', '/me');
  await port.signOut();
  await api.call('GET', '/profiles/x', {anonymous: false});
  assert.equal(f.seen[1].headers.Authorization, undefined);
});

test('anonymous calls never ask for a token', async () => {
  const {port, calls} = fakeAuth();
  const f = recordingFetch();
  await createApi(port, 'http://api.test/api/v2', f.impl).call('GET', '/profiles/x', {anonymous: true});
  assert.equal(calls(), 0);
  assert.equal(f.seen[0].headers.Authorization, undefined);
});

test('errors map to ApiFailure with readable messages', async () => {
  const {port} = fakeAuth();
  const f = recordingFetch(429, {code: 'RATE_LIMITED', message: 'Too many', request_id: 'r'}, {'Retry-After': '7200'});
  const api = createApi(port, 'http://api.test/api/v2', f.impl);
  await assert.rejects(api.call('POST', '/me/friend-requests', {body: {handle: 'x'}}), (err: unknown) => {
    assert.ok(err instanceof ApiFailure);
    assert.equal(err.code, 'RATE_LIMITED');
    assert.equal(err.retryAfter, 7200);
    assert.match(describe(err), /Too many attempts.*about 2 hours.*RATE_LIMITED/);
    return true;
  });
  const v = new ApiFailure(422, 'VALIDATION_FAILED', 'bad', [{field: 'body.handle', code: 'x', message: 'Handles are 3-20.'}]);
  assert.match(describe(v), /Handles are 3-20/);
  assert.match(describe(new ApiFailure(409, 'HANDLE_UNAVAILABLE', '')), /taken or reserved/);
});
