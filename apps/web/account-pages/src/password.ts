/**
 * Client password policy (add-wearhouse-settings-security D5). Checked before anything is sent to the broker; the
 * broker (Neon Auth) enforces its own server-side minimum too. Nothing here ever leaves the page: no breach-check
 * service is called, because password material must never go anywhere but the identity broker.
 */
export const MIN_LENGTH = 10;
export const MAX_LENGTH = 128;

// The most common leaked passwords (and obvious keyboard/brand patterns), compared case-insensitively.
const COMMON = new Set([
  '123456', '123456789', '12345678', 'password', 'qwerty', '123123', '1234567890', '111111', '12345', '1234567',
  'password1', 'password123', 'qwerty123', 'qwertyuiop', 'abc123', 'iloveyou', '000000', 'admin', 'admin123',
  'welcome', 'welcome1', 'letmein', 'monkey', 'dragon', 'football', 'baseball', 'sunshine', 'princess', 'master',
  'superman', 'starwars', 'trustno1', 'passw0rd', 'p@ssw0rd', 'p@ssword', 'zaq12wsx', '1q2w3e4r', '1qaz2wsx',
  'asdfghjkl', 'zxcvbnm', 'qazwsx', 'changeme', 'secret', 'login', 'hello123', 'whatever', 'freedom', 'shadow',
  'michael', 'jennifer', 'indonesia', 'jakarta', 'bismillah', 'wearhouse', 'wearhouse123', 'wardrobe', 'fashion',
]);

export type Strength = 'weak' | 'fair' | 'strong';

export interface PasswordCheck {
  ok: boolean;
  problems: string[];
  strength: Strength;
}

function classes(pw: string): number {
  return [/[a-z]/, /[A-Z]/, /[0-9]/, /[^A-Za-z0-9]/].filter(r => r.test(pw)).length;
}

/** `context`: the email and handle the password must not contain. */
export function checkPassword(pw: string, context: {email?: string | null; handle?: string | null} = {}): PasswordCheck {
  const problems: string[] = [];
  const lower = pw.toLowerCase();
  if (pw.length < MIN_LENGTH) problems.push(`Use at least ${MIN_LENGTH} characters.`);
  if (pw.length > MAX_LENGTH) problems.push(`Use at most ${MAX_LENGTH} characters.`);
  if (COMMON.has(lower) || COMMON.has(lower.replace(/[0-9!@#$%^&*.]+$/, ''))) {
    problems.push('This is one of the most common passwords. Choose something less predictable.');
  }
  if (pw.length && new Set(pw).size <= 2) problems.push('Use more than one or two different characters.');
  const local = (context.email ?? '').split('@')[0].toLowerCase();
  if (local.length >= 3 && lower.includes(local)) problems.push('Do not include your email name.');
  const handle = (context.handle ?? '').toLowerCase();
  if (handle.length >= 3 && lower.includes(handle)) problems.push('Do not include your handle.');
  const score = (pw.length >= 16 ? 2 : pw.length >= 12 ? 1 : 0) + Math.max(0, classes(pw) - 1);
  const strength: Strength = problems.length ? 'weak' : score >= 4 ? 'strong' : score >= 2 ? 'fair' : 'weak';
  return {ok: problems.length === 0, problems, strength};
}
