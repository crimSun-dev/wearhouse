/** The seam between the pages and the identity broker. Production: Neon Auth. E2E builds: a test fake.
 * Passwords only ever travel between the page and the broker: the Wearhouse API never receives one. */
export interface BrokerSession {
  userId: string;
  name: string | null;
  email?: string | null;
  emailVerified?: boolean | null;
}

export interface LinkedMethod {
  provider: string;  // 'google', 'credential' (email + password), ...
}

/** One signed-in device as the broker reports it. */
export interface DeviceSession {
  id: string;
  token: string;       // the broker's session handle used to revoke it (never shown)
  current: boolean;
  createdAt: string | null;
  expiresAt: string | null;
  userAgent: string | null;
  ipAddress: string | null;
}

export type BrokerDeletion = 'deleted' | 'unsupported';

/** A broker refusal with its message (e.g. "Invalid email or password"). */
export class AuthFailure extends Error {
  readonly code: string | null;
  constructor(message: string, code: string | null = null) {  // no parameter properties: node --test strips types only
    super(message);
    this.code = code;
  }
}

export interface AuthPort {
  readonly kind: 'neon' | 'e2e-fake';
  /** The current broker session, restored after a reload, or null when signed out. */
  session(): Promise<BrokerSession | null>;
  /** Starts Google sign-in (may navigate away and come back). */
  signInWithGoogle(): Promise<void>;
  /** Email + password sign-in and sign-up (add-wearhouse-settings-security). */
  signInWithEmail(email: string, password: string): Promise<void>;
  signUpWithEmail(name: string, email: string, password: string): Promise<void>;
  /** Sends a reset link that comes back to `#/reset?token=…` (also how a Google-only account sets a password). */
  requestPasswordReset(email: string): Promise<void>;
  resetPassword(token: string, newPassword: string): Promise<void>;
  changePassword(currentPassword: string, newPassword: string, signOutOtherDevices: boolean): Promise<void>;
  sendVerificationEmail(email: string): Promise<void>;
  listSessions(): Promise<DeviceSession[] | null>;
  revokeSession(token: string): Promise<void>;
  revokeOtherSessions(): Promise<void>;
  /** A fresh access token for the v2 API, or null when signed out. Never stored by the caller. */
  token(): Promise<string | null>;
  signOut(): Promise<void>;
  /** Ends every broker session (the API's own revocation is a separate call). */
  revokeSessions(): Promise<void>;
  /** Linked sign-in methods as the broker reports them; null when the broker does not say. */
  listMethods(): Promise<LinkedMethod[] | null>;
  /** Deletes the broker identity when the broker allows self-deletion. */
  deleteBrokerUser(): Promise<BrokerDeletion>;
}

/** Where reset links should land: this page, `#/reset` (the broker adds `?token=`). */
export function resetRedirect(): string {
  return `${location.origin}${location.pathname}#/reset`;
}
