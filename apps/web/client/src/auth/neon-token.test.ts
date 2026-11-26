// add-wearhouse-accounts 9.2 finding: the Neon wrapper delivers the API JWT in getSession().session.token.
import assert from 'node:assert/strict';
import {test} from 'vitest';

import {fromManagedClient, type ManagedClient} from './neon.ts';

const JWT = 'eyJhbGciOiJFZERTQSJ9.eyJzdWIiOiJ1In0.c2ln';

function client(session: unknown, token: unknown = {data: null, error: null}): ManagedClient {
  return {
    getSession: async () => ({data: session as never, error: null}),
    token: async () => token as never,
    signIn: {social: async () => ({data: null, error: null}), email: async () => ({data: null, error: null})},
    signUp: {email: async () => ({data: null, error: null})},
    requestPasswordReset: async () => ({data: null, error: null}),
    resetPassword: async () => ({data: null, error: null}),
    changePassword: async () => ({data: null, error: null}),
    sendVerificationEmail: async () => ({data: null, error: null}),
    listSessions: async () => ({data: [], error: null}),
    revokeSession: async () => ({data: null, error: null}),
    revokeOtherSessions: async () => ({data: null, error: null}),
    signOut: async () => ({data: null, error: null}),
    revokeSessions: async () => ({data: null, error: null}),
    listAccounts: async () => ({data: [], error: null}),
    deleteUser: async () => ({data: null, error: null}),
  };
}

test('uses the JWT the SDK injects into session.token', async () => {
  assert.equal(await fromManagedClient(client({user: {id: 'u'}, session: {token: JWT}})).token(), JWT);
});

test('falls back to token() only when the session carries no JWT', async () => {
  const c = client({user: {id: 'u'}, session: {token: 'opaque-session-token'}}, {data: {token: JWT}, error: null});
  assert.equal(await fromManagedClient(c).token(), JWT);
});

test('never sends an opaque session token or anything when signed out', async () => {
  assert.equal(await fromManagedClient(client({user: {id: 'u'}, session: {token: 'opaque'}})).token(), null);
  assert.equal(await fromManagedClient(client(null)).token(), null);
});

