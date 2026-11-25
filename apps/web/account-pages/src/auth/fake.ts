// E2E-ONLY broker fake (WEARHOUSE_E2E_FAKE_AUTH). Built only with `vite build --mode e2e`.
// Mimics the real broker: ?e2e_sub=<subject> is the "Google account" the user would pick; signing in sets a
// session cookie (like Neon Auth's), so the session survives reloads until sign-out. Signed EdDSA access
// tokens come from the local test issuer served by e2e/harness.py and are never stored.
// add-wearhouse-settings-security: email/password accounts, reset links, password change and per-device sessions
// are modelled in localStorage so the pages' flows can be tested without the real broker. Test passwords only.
import {AuthFailure, resetRedirect, type AuthPort, type BrokerDeletion, type DeviceSession} from './port.ts';

export const E2E_MARKER = 'WEARHOUSE_E2E_FAKE_AUTH';
const COOKIE = 'e2e_broker_session';
const USERS = 'e2e_broker_users';
const RESETS = 'e2e_broker_resets';

type FakeUser = {sub: string; name: string; password: string | null; google: boolean; verified: boolean};

function sessionSubject(): string | null {
  const m = document.cookie.split('; ').find(c => c.startsWith(COOKIE + '='));
  return m ? decodeURIComponent(m.slice(COOKIE.length + 1)) : null;
}

const read = <T>(key: string, empty: T): T => JSON.parse(localStorage.getItem(key) ?? 'null') ?? empty;
const write = (key: string, value: unknown) => localStorage.setItem(key, JSON.stringify(value));
const users = () => read<Record<string, FakeUser>>(USERS, {});
const byEmail = (email: string) => users()[email.trim().toLowerCase()];
const emailOf = (sub: string) => Object.entries(users()).find(([, u]) => u.sub === sub)?.[0] ?? null;

function save(email: string, user: FakeUser) {
  write(USERS, {...users(), [email.trim().toLowerCase()]: user});
}

function startSession(sub: string) {
  document.cookie = `${COOKIE}=${encodeURIComponent(sub)}; path=/; SameSite=Lax`;
  const key = `e2e_broker_sessions_${sub}`;
  const now = new Date().toISOString();
  const others = read<DeviceSession[]>(key, []).filter(s => !s.current);
  if (!others.length) {  // a second, older device so "sign this device out" can be exercised
    others.push({id: 'other-device', token: 'tok-other', current: false, createdAt: now, expiresAt: null,
                 userAgent: 'Other browser (e2e fake)', ipAddress: '198.51.100.7'});
  }
  write(key, [{id: 'this-device', token: 'tok-this', current: true, createdAt: now, expiresAt: null,
               userAgent: navigator.userAgent, ipAddress: '127.0.0.1'}, ...others]);
}

function signedIn(): string {
  const s = sessionSubject();
  if (!s) throw new AuthFailure('Not signed in.');
  return s;
}

export function createAuth(): AuthPort {
  (globalThis as Record<string, unknown>)[E2E_MARKER] = true; // keeps the marker in the bundle for the build guard
  const tokenUrl = (import.meta.env.VITE_E2E_TOKEN_URL as string | undefined) ?? 'http://127.0.0.1:8199/__e2e/token';
  return {
    kind: 'e2e-fake',
    async session() {
      const s = sessionSubject();
      if (!s) return null;
      const email = emailOf(s);
      const u = email ? users()[email] : undefined;
      return {userId: s, name: u?.name ?? `Test ${s}`, email, emailVerified: u?.verified ?? null};
    },
    async signInWithGoogle() {
      const pick = new URLSearchParams(location.search).get('e2e_sub');
      if (!pick) throw new Error('e2e: add ?e2e_sub=<subject> to the URL');
      const email = `${pick}@e2e.invalid`;
      if (!byEmail(email)) save(email, {sub: pick, name: `Test ${pick}`, password: null, google: true, verified: true});
      startSession(pick);
    },
    async signUpWithEmail(name, email, password) {
      if (byEmail(email)) throw new AuthFailure('User already exists. Use another email.', 'USER_ALREADY_EXISTS');
      const sub = 'pw_' + email.split('@')[0].toLowerCase().replace(/[^a-z0-9_]/g, '_');
      save(email, {sub, name, password, google: false, verified: false});
      startSession(sub);
    },
    async signInWithEmail(email, password) {
      const u = byEmail(email);
      if (!u || u.password === null || u.password !== password) {
        throw new AuthFailure('Invalid email or password', 'INVALID_EMAIL_OR_PASSWORD');
      }
      startSession(u.sub);
    },
    async requestPasswordReset(email) {
      if (byEmail(email)) {  // like the real broker: the same answer whether or not the email exists
        const token = Math.random().toString(36).slice(2);
        write(RESETS, {...read<Record<string, string>>(RESETS, {}), [token]: email.trim().toLowerCase()});
        const link = new URL(resetRedirect());
        link.searchParams.set('token', token);
        localStorage.setItem('e2e_last_reset_link', link.toString());  // the "email" the test opens
      }
    },
    async resetPassword(token, newPassword) {
      const resets = read<Record<string, string>>(RESETS, {});
      const email = resets[token];
      if (!email) throw new AuthFailure('Invalid token', 'INVALID_TOKEN');
      save(email, {...users()[email], password: newPassword});  // creates the password for a Google-only account
      delete resets[token];
      write(RESETS, resets);
    },
    async changePassword(currentPassword, newPassword, signOutOtherDevices) {
      const sub = signedIn();
      const email = emailOf(sub)!;
      const u = users()[email];
      if (u.password === null || u.password !== currentPassword) throw new AuthFailure('Invalid password', 'INVALID_PASSWORD');
      save(email, {...u, password: newPassword});
      if (signOutOtherDevices) await this.revokeOtherSessions();
    },
    async sendVerificationEmail(email) {
      const u = byEmail(email);
      if (u) save(email, {...u, verified: true});  // the fake "clicks" the link immediately
    },
    async listSessions() {
      return read<DeviceSession[]>(`e2e_broker_sessions_${signedIn()}`, []);
    },
    async revokeSession(token) {
      const key = `e2e_broker_sessions_${signedIn()}`;
      write(key, read<DeviceSession[]>(key, []).filter(s => s.token !== token));
    },
    async revokeOtherSessions() {
      const key = `e2e_broker_sessions_${signedIn()}`;
      write(key, read<DeviceSession[]>(key, []).filter(s => s.current));
    },
    async token() {
      const s = sessionSubject();
      if (!s) return null;
      const r = await fetch(`${tokenUrl}?sub=${encodeURIComponent(s)}`);
      return r.ok ? ((await r.json()) as {token: string}).token : null;
    },
    async signOut() {
      document.cookie = `${COOKIE}=; path=/; max-age=0`;
    },
    async revokeSessions() {},
    async listMethods() {
      const s = sessionSubject();
      const email = s ? emailOf(s) : null;
      const u = email ? users()[email] : undefined;
      if (!u) return [{provider: 'google'}];
      return [...(u.google ? [{provider: 'google'}] : []), ...(u.password !== null ? [{provider: 'credential'}] : [])];
    },
    async deleteBrokerUser(): Promise<BrokerDeletion> {
      return 'unsupported';
    },
  };
}
