/**
 * Neon Auth (Managed Better Auth) through `@neon/auth` 0.8.2 with the vanilla adapter.
 * ACCESS TOKEN: the Neon wrapper copies the `set-auth-jwt` response header into
 * `getSession().data.session.token` (dist/adapter-core.js onSuccess; its own getJWTToken() reads it there).
 * That is the JWT the v2 API verifies. `token()` is only a fallback: in the first real Google sign-in
 * (task 9.2) it returned nothing, so every API call went out without a token and got 401.
 * Checked against the installed package (task 8.1): it exposes getSession, signIn.social, token,
 * signOut, revokeSessions, listAccounts and deleteUser. There is no linkSocial or unlinkAccount, so linked
 * methods are shown read-only. Whether the managed server permits deleteUser is only knowable against a
 * real Auth branch, so a failure is reported as 'unsupported' and the pages show the disclosure.
 * add-wearhouse-settings-security: email/password, reset, change, verification and per-device sessions use the
 * Better Auth client methods the same package exposes (signIn.email, signUp.email, requestPasswordReset,
 * resetPassword, changePassword, sendVerificationEmail, listSessions, revokeSession, revokeOtherSessions).
 * A reset creates the password for a Google-only account (better-auth utils/password resetCredentialPassword).
 */
import {createAuthClient} from '@neon/auth';
import {BetterAuthVanillaAdapter} from '@neon/auth/vanilla/adapters';

import {AuthFailure, resetRedirect, type AuthPort, type BrokerDeletion, type BrokerSession, type DeviceSession,
  type LinkedMethod} from './port.ts';

type Result<T> = Promise<{data: T | null; error: unknown}>;

/** The small, structurally typed subset of the managed client these pages use. */
type RawSession = {id?: string; token?: string; createdAt?: string | Date; expiresAt?: string | Date;
                    userAgent?: string | null; ipAddress?: string | null};

export interface ManagedClient {
  getSession(): Result<{user: {id: string; name?: string | null; email?: string | null; emailVerified?: boolean | null};
                       session?: {id?: string; token?: string}} | null>;
  signIn: {social(args: {provider: 'google'; callbackURL: string}): Result<unknown>;
           email(args: {email: string; password: string}): Result<unknown>};
  signUp: {email(args: {name: string; email: string; password: string}): Result<unknown>};
  requestPasswordReset(args: {email: string; redirectTo: string}): Result<unknown>;
  resetPassword(args: {newPassword: string; token: string}): Result<unknown>;
  changePassword(args: {currentPassword: string; newPassword: string; revokeOtherSessions?: boolean}): Result<unknown>;
  sendVerificationEmail(args: {email: string; callbackURL?: string}): Result<unknown>;
  listSessions(): Result<RawSession[]>;
  revokeSession(args: {token: string}): Result<unknown>;
  revokeOtherSessions(): Result<unknown>;
  token(): Result<{token: string}>;
  signOut(): Result<unknown>;
  revokeSessions(): Result<unknown>;
  listAccounts(): Result<Array<{providerId?: string; provider?: string}>>;
  deleteUser(args?: {callbackURL?: string}): Result<unknown>;
}

const JWT = /^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$/;

export function createNeonAuth(authUrl: string): AuthPort {
  const client = createAuthClient(authUrl, {
    adapter: BetterAuthVanillaAdapter({fetchOptions: {credentials: 'include'}}),
  }) as unknown as ManagedClient;
  return fromManagedClient(client);
}

/** Exported for unit tests: wraps any object with the managed client's shape. */
/** Turns a broker `{error}` into an AuthFailure carrying the broker's own message. */
async function must(call: Result<unknown>, fallback: string): Promise<void> {
  const {error} = await call;
  if (error) {
    const e = error as {message?: string; code?: string; statusText?: string};
    throw new AuthFailure(e.message || e.statusText || fallback, e.code ?? null);
  }
}

const iso = (v: string | Date | undefined) => (v === undefined ? null : new Date(v).toISOString());

export function fromManagedClient(client: ManagedClient): AuthPort {
  return {
    kind: 'neon',
    async session(): Promise<BrokerSession | null> {
      const {data} = await client.getSession();
      return data?.user ? {userId: data.user.id, name: data.user.name ?? null, email: data.user.email ?? null,
                           emailVerified: data.user.emailVerified ?? null} : null;
    },
    async signInWithEmail(email, password) {
      await must(client.signIn.email({email, password}), 'Sign-in failed.');
    },
    async signUpWithEmail(name, email, password) {
      await must(client.signUp.email({name, email, password}), 'Could not create the account.');
    },
    async requestPasswordReset(email) {
      await must(client.requestPasswordReset({email, redirectTo: resetRedirect()}), 'Could not send the reset email.');
    },
    async resetPassword(token, newPassword) {
      await must(client.resetPassword({token, newPassword}), 'The reset link is invalid or expired.');
    },
    async changePassword(currentPassword, newPassword, signOutOtherDevices) {
      await must(client.changePassword({currentPassword, newPassword, revokeOtherSessions: signOutOtherDevices}),
                 'Could not change the password.');
    },
    async sendVerificationEmail(email) {
      await must(client.sendVerificationEmail({email, callbackURL: location.origin + location.pathname}),
                 'Could not send the verification email.');
    },
    async listSessions(): Promise<DeviceSession[] | null> {
      const [{data, error}, {data: cur}] = await Promise.all([client.listSessions(), client.getSession()]);
      if (error || !data) return null;
      const currentId = cur?.session?.id;
      return data.map(s => ({id: String(s.id ?? ''), token: String(s.token ?? ''), current: !!currentId && s.id === currentId,
                             createdAt: iso(s.createdAt), expiresAt: iso(s.expiresAt), userAgent: s.userAgent ?? null,
                             ipAddress: s.ipAddress ?? null}));
    },
    async revokeSession(token) {
      await must(client.revokeSession({token}), 'Could not sign that device out.');
    },
    async revokeOtherSessions() {
      await must(client.revokeOtherSessions(), 'Could not sign the other devices out.');
    },
    async signInWithGoogle() {
      const {error} = await client.signIn.social({provider: 'google', callbackURL: location.origin + location.pathname});
      if (error) throw new Error('Google sign-in did not start.');
    },
    async token() {
      const {data} = await client.getSession();  // the SDK refreshes the JWT here when it is close to expiry
      const fromSession = data?.session?.token;
      if (fromSession && JWT.test(fromSession)) return fromSession;
      if (!data?.user) return null;
      try {
        const {data: t} = await client.token();
        return t?.token && JWT.test(t.token) ? t.token : null;
      } catch {
        return null;
      }
    },
    async signOut() {
      await client.signOut();
    },
    async revokeSessions() {
      await client.revokeSessions();
    },
    async listMethods(): Promise<LinkedMethod[] | null> {
      const {data, error} = await client.listAccounts();
      if (error || !data) return null;
      return data.map(a => ({provider: String(a.providerId ?? a.provider ?? 'unknown')}));
    },
    async deleteBrokerUser(): Promise<BrokerDeletion> {
      try {
        const {error} = await client.deleteUser({callbackURL: location.origin + location.pathname});
        return error ? 'unsupported' : 'deleted';
      } catch {
        return 'unsupported';
      }
    },
  };
}
