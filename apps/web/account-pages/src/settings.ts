/**
 * TEMPORARY settings + security pages (add-wearhouse-settings-security 3.1). Sections follow the owner's settings mock
 * (Assets/5b18d145-…png): General, Wardrobe, Style & Recommendations, Sync & Backup, Display, Audio, Notifications,
 * Friends & Community, Downloads, Beta Features, About. The controls are rendered from the API's settings schema.
 * Passwords go only to the identity broker (auth port); the Wearhouse API never receives one.
 */
import type {About, Security, SettingSchema, Settings} from '@wearhouse/contracts';

import {ApiFailure, type ApiClient} from './api.ts';
import type {AuthPort, DeviceSession} from './auth/port.ts';
import {checkPassword} from './password.ts';
import {act, button, el, field, say, select, view} from './ui.ts';

type Ctx = {api: () => ApiClient; auth: () => AuthPort; handle: () => string | null; afterSignIn: () => Promise<void>;
            afterSignOut: () => Promise<void>};
let ctx: Ctx;

export function initSettings(c: Ctx) {
  ctx = c;
}

// ------------------------------------------------------------------ labels (copy from the mock)
const SECTION_TITLES: Record<string, string> = {
  general: 'General', wardrobe: 'Wardrobe', style: 'Style & Recommendations', display: 'Display', audio: 'Audio',
  notifications: 'Notifications', community: 'Friends & Community', beta: 'Beta Features',
};
const LABELS: Record<string, [string, string]> = {
  language: ['Preferred language', 'Set the interface language for Wearhouse.'],
  wardrobe_view: ['Default view', 'Choose how your wardrobe is displayed.'],
  wardrobe_group_by_slot: ['Auto-categorize clothing', 'Automatically group items by slot (tops, bottoms, outerwear).'],
  style_suggestions: ['Style suggestions', 'Get outfit recommendations based on your wardrobe, occasion and weather.'],
  weather_in_suggestions: ['Weather integration', 'Use weather data (BMKG) to suggest suitable outfits.'],
  recommendation_style: ['Recommendation style', 'Balanced weighs everything; Classic favours proven combinations; '
                         + 'Adventurous favours pieces you have not worn lately.'],
  theme: ['Theme', 'Choose your preferred appearance.'],
  reduce_motion: ['Reduce motion', 'Turn off animations and transitions.'],
  sound_effects: ['Sound effects', 'Play short sounds for actions such as saving a look.'],
  sound_volume: ['Volume', 'How loud sound effects are.'],
  notify_friend_requests: ['Friend requests', 'Notify me when someone sends me a friend request.'],
  notify_request_accepted: ['Accepted requests', 'Notify me when someone accepts my friend request.'],
  notify_friend_shares: ['Friends\' shared looks', 'Notify me when a friend shares a look.'],
  friend_requests_from: ['Who can send me friend requests', 'Choose "Nobody" to close requests; you can still send them.'],
  discoverable: ['Appear in search', 'Others can find you by typing part of your handle. Your exact @handle always works.'],
  beta_features: ['Beta features', 'Try new features before they are finished.'],
};
const CHOICE_LABELS: Record<string, string> = {
  en: 'English', id: 'Bahasa Indonesia', grid: 'Grid', list: 'List', outfit: 'Outfit', balanced: 'Balanced (Recommended)',
  classic: 'Classic', adventurous: 'Adventurous', dark: 'Dark', light: 'Light', system: 'System', everyone: 'Everyone',
  nobody: 'Nobody',
};

// the mock shows these as dropdowns; other short choices are segmented buttons
const DROPDOWNS = new Set(['language', 'recommendation_style']);
const segmented = (s: SettingSchema) => s.type === 'choice' && s.choices.length <= 3 && !DROPDOWNS.has(s.key);

// ------------------------------------------------------------------ display settings applied to the page
let cached: Settings | null = null;

export function applyDisplay(s: Settings | null) {
  const root = document.documentElement;
  root.dataset.theme = String(s?.values.theme ?? 'system');
  root.classList.toggle('reduce-motion', s?.values.reduce_motion === true);
}

export async function loadSettings(): Promise<Settings | null> {
  try {
    cached = await ctx.api().call<Settings>('GET', '/me/settings');
  } catch {
    cached = null;
  }
  applyDisplay(cached);
  return cached;
}

export const currentSettings = () => cached;

// ------------------------------------------------------------------ Settings page
function control(s: SettingSchema, value: unknown, save: (v: unknown) => Promise<void>): HTMLElement {
  const [label, hint] = LABELS[s.key] ?? [s.key, ''];
  const id = `setting-${s.key}`;
  let input: HTMLElement;
  if (s.type === 'flag') {
    const box = el('input', {type: 'checkbox', id, checked: value === true, role: 'switch'});
    box.addEventListener('change', () => void save(box.checked));
    input = box;
  } else if (s.type === 'range') {
    const range = el('input', {type: 'range', id, min: String(s.min), max: String(s.max), value: String(value)});
    range.addEventListener('change', () => void save(Number(range.value)));
    input = range;
  } else if (segmented(s)) {  // a segmented control, like the mock
    const group = el('div', {className: 'segmented', role: 'radiogroup', id});
    group.setAttribute('aria-label', label);
    for (const c of s.choices) {
      const r = el('input', {type: 'radio', name: id, value: c, id: `${id}-${c}`, checked: value === c});
      r.addEventListener('change', () => { if (r.checked) void save(c); });
      group.append(el('label', {htmlFor: `${id}-${c}`, className: 'seg'}, r, ' ' + (CHOICE_LABELS[c] ?? c)));
    }
    input = group;
  } else {
    const sel = select(s.key, s.choices.map(c => [c, CHOICE_LABELS[c] ?? c] as [string, string]), String(value));
    sel.id = id;
    sel.addEventListener('change', () => void save(sel.value));
    input = sel;
  }
  const labelEl = segmented(s)
    ? el('span', {className: 'setting-label', text: label}) : el('label', {htmlFor: id, className: 'setting-label', text: label});
  return el('div', {className: 'setting-row'}, el('div', {}, labelEl, el('br'), el('small', {className: 'hint', text: hint})), input);
}

export async function settingsPage(sectionParam?: string) {
  const s = (await loadSettings())!;
  let version = s.version;
  const save = (key: string) => async (value: unknown) => {
    await act(null, async () => {
      try {
        const out = await ctx.api().call<Settings>('PATCH', '/me/settings', {body: {version, values: {[key]: value}}});
        version = out.version;
        cached = out;
        applyDisplay(out);
        synced.textContent = `Saved to your account ${new Date(out.updated_at!).toLocaleTimeString()}.`;
        return `${LABELS[key]?.[0] ?? key} saved.`;
      } catch (err) {
        if (err instanceof ApiFailure && err.code === 'SETTINGS_CHANGED') {
          await settingsPage(sectionParam);  // another device saved first: show its values
          throw err;
        }
        throw err;
      }
    });
  };
  const synced = el('span', {text: s.updated_at ? `Last saved ${new Date(s.updated_at).toLocaleString()}.` : 'Using the defaults.'});
  const sections = s.sections.map(sec => el('section', {className: 'settings-card', id: `settings-${sec}`},
    el('h2', {text: SECTION_TITLES[sec] ?? sec}),
    ...s.schema.filter(x => x.section === sec).map(x => control(x, s.values[x.key], save(x.key)))));
  const side = el('nav', {className: 'settings-nav', ariaLabel: 'Settings sections'},
    ...s.sections.map(sec => el('a', {href: `#/settings/${sec}`, text: SECTION_TITLES[sec] ?? sec})),
    el('a', {href: '#/settings/sync', text: 'Sync & Backup'}), el('a', {href: '#/settings/downloads', text: 'Downloads'}),
    el('a', {href: '#/security', text: 'Security & password'}), el('a', {href: '#/sizes', text: 'My sizes'}),
    el('a', {href: '#/privacy', text: 'Privacy'}), el('a', {href: '#/about', text: 'About'}));
  const sync = el('section', {className: 'settings-card', id: 'settings-sync'}, el('h2', {text: 'Sync & Backup'}),
    el('p', {className: 'hint', text: 'Your wardrobe, looks and settings are stored in your Wearhouse account, so every device you sign in on sees the same thing.'}),
    el('p', {}, synced, ' ', button('Sync now', b => act(b, async () => { await settingsPage(sectionParam); return 'Up to date.'; }))));
  const downloads = el('section', {className: 'settings-card', id: 'settings-downloads'}, el('h2', {text: 'Downloads'}),
    el('p', {className: 'hint', text: 'A JSON copy of everything Wearhouse holds about you (5 per hour).'}),
    button('Download my data (JSON)', b => act(b, async () => {
      const res = await ctx.api().raw('/me/export');
      if (!res.ok) throw new Error(`Export failed (${res.status}).`);
      const link = el('a', {href: URL.createObjectURL(await res.blob()), download: 'wearhouse-export.json'});
      document.body.append(link);
      link.click();
      link.remove();
    }, 'Export downloaded.')));
  view('Settings', el('p', {className: 'hint', text: 'Customize how Wearhouse looks, works and fits your style. Changes save instantly.'}),
       el('div', {className: 'settings-layout'}, side, el('div', {}, ...sections, sync, downloads)));
  if (sectionParam) document.getElementById(`settings-${sectionParam}`)?.scrollIntoView();
}

// ------------------------------------------------------------------ password helpers
function passwordInput(name: string, id: string, autocomplete: string): HTMLInputElement {
  return el('input', {type: 'password', name, id, autocomplete: autocomplete as AutoFill, required: true, maxLength: 128});
}

function strengthMeter(input: HTMLInputElement, context: () => {email?: string | null; handle?: string | null}) {
  const out = el('p', {className: 'hint', ariaLive: 'polite'});
  input.addEventListener('input', () => {
    const c = checkPassword(input.value, context());
    out.textContent = input.value ? `Strength: ${c.strength}.${c.problems.length ? ' ' + c.problems.join(' ') : ''}` : '';
  });
  return out;
}

function requireGood(pw: string, again: string, context: {email?: string | null; handle?: string | null}) {
  const c = checkPassword(pw, context);
  if (!c.ok) throw new Error(c.problems.join(' '));
  if (pw !== again) throw new Error('The two passwords do not match.');
}

// ------------------------------------------------------------------ sign in (Google + email/password)
export function signInPanel(): HTMLElement[] {
  const auth = ctx.auth();
  const email = el('input', {type: 'email', name: 'email', id: 'signin-email', autocomplete: 'username', required: true});
  const pw = passwordInput('password', 'signin-password', 'current-password');
  const signIn = el('form', {}, el('h2', {text: 'Sign in with email'}), field('Email', email), field('Password', pw),
                    el('button', {type: 'submit', text: 'Sign in', className: 'primary'}));
  signIn.addEventListener('submit', e => {
    e.preventDefault();
    act(signIn.querySelector('button'), async () => {
      await auth.signInWithEmail(email.value.trim(), pw.value);
      pw.value = '';
      await ctx.afterSignIn();
    }, 'Signed in.');
  });
  const name = el('input', {name: 'name', id: 'signup-name', autocomplete: 'name', required: true, maxLength: 60});
  const email2 = el('input', {type: 'email', name: 'email', id: 'signup-email', autocomplete: 'username', required: true});
  const pw1 = passwordInput('new-password', 'signup-password', 'new-password');
  const pw2 = passwordInput('confirm-password', 'signup-password-again', 'new-password');
  const signUp = el('form', {}, el('h2', {text: 'Create an account'}), field('Name', name), field('Email', email2),
                    field('Password', pw1), strengthMeter(pw1, () => ({email: email2.value})), field('Repeat password', pw2),
                    el('button', {type: 'submit', text: 'Create account', className: 'primary'}));
  signUp.addEventListener('submit', e => {
    e.preventDefault();
    act(signUp.querySelector('button'), async () => {
      requireGood(pw1.value, pw2.value, {email: email2.value});
      await auth.signUpWithEmail(name.value.trim(), email2.value.trim(), pw1.value);
      pw1.value = pw2.value = '';
      await ctx.afterSignIn();
    }, 'Account created.');
  });
  const forgotEmail = el('input', {type: 'email', name: 'email', id: 'forgot-email', autocomplete: 'username', required: true});
  const forgot = el('form', {}, field('Email', forgotEmail),
                    el('button', {type: 'submit', text: 'Email me a reset link'}));
  forgot.addEventListener('submit', e => {
    e.preventDefault();
    act(forgot.querySelector('button'), async () => {
      await auth.requestPasswordReset(forgotEmail.value.trim());
      return 'If that email has an account, a reset link is on its way.';  // never reveals whether it exists
    });
  });
  return [
    button('Sign in with Google', b => act(b, async () => { await auth.signInWithGoogle(); await ctx.afterSignIn(); }, 'Signed in.'), 'primary'),
    signIn,
    el('details', {}, el('summary', {text: 'Forgot your password?'}), forgot),
    signUp,
  ];
}

export function resetPage() {
  const token = new URLSearchParams(location.search).get('token');
  if (!token) {
    view('Reset your password', el('p', {text: 'This reset link is incomplete. Request a new one from the sign-in page.'}));
    return;
  }
  const pw1 = passwordInput('new-password', 'reset-password', 'new-password');
  const pw2 = passwordInput('confirm-password', 'reset-password-again', 'new-password');
  const form = el('form', {}, field('New password', pw1), strengthMeter(pw1, () => ({})), field('Repeat new password', pw2),
                  el('button', {type: 'submit', text: 'Set new password', className: 'primary'}));
  form.addEventListener('submit', e => {
    e.preventDefault();
    act(form.querySelector('button'), async () => {
      requireGood(pw1.value, pw2.value, {});
      await ctx.auth().resetPassword(token, pw1.value);
      pw1.value = pw2.value = '';
      // drop the token from the address bar but stay on #/reset (view() ignores renders for a route we left)
      history.replaceState(null, '', `${location.pathname}#/reset`);
      view('Password updated', el('p', {text: 'Your new password is set. Sign in with it.'}), el('a', {href: '#/', text: 'Go to sign in'}));
      return 'Password updated.';
    });
  });
  view('Reset your password', form);
}

// ------------------------------------------------------------------ Security page
function describeDevice(s: DeviceSession): string {
  const ua = s.userAgent ?? 'Unknown device';
  const browser = /Edg\//.test(ua) ? 'Edge' : /Chrome\//.test(ua) ? 'Chrome' : /Firefox\//.test(ua) ? 'Firefox'
    : /Safari\//.test(ua) ? 'Safari' : ua.slice(0, 40);
  const os = /Windows/.test(ua) ? 'Windows' : /Android/.test(ua) ? 'Android' : /iPhone|iPad/.test(ua) ? 'iOS'
    : /Mac OS/.test(ua) ? 'macOS' : /Linux/.test(ua) ? 'Linux' : '';
  return [browser, os].filter(Boolean).join(' on ');
}

const EVENT_TEXT: Record<string, string> = {
  'account.sessions_revoked': 'Signed out everywhere', 'account.handle_changed': 'Handle changed',
  'account.privacy_changed': 'Privacy changed', 'account.settings_changed': 'Settings changed',
  'account.exported': 'Data exported', 'identity.role_granted': 'Staff role granted',
  'identity.role_revoked': 'Staff role removed',
};

export async function securityPage() {
  const api = ctx.api();
  const auth = ctx.auth();
  const [sec, broker, methods, devices] = await Promise.all([
    api.call<Security>('GET', '/me/security'), auth.session(), auth.listMethods(), auth.listSessions()]);
  const hasPassword = methods?.some(m => m.provider === 'credential') ?? false;
  const email = broker?.email ?? null;
  const context = () => ({email, handle: ctx.handle()});

  // password
  let passwordBox: HTMLElement;
  if (hasPassword) {
    const cur = passwordInput('current-password', 'current-password', 'current-password');
    const pw1 = passwordInput('new-password', 'new-password', 'new-password');
    const pw2 = passwordInput('confirm-password', 'new-password-again', 'new-password');
    const others = el('input', {type: 'checkbox', id: 'pw-signout-others', checked: true});
    const form = el('form', {}, field('Current password', cur), field('New password', pw1), strengthMeter(pw1, context),
                    field('Repeat new password', pw2),
                    el('label', {className: 'check', htmlFor: 'pw-signout-others'}, others, ' Sign out my other devices'),
                    el('button', {type: 'submit', text: 'Change password', className: 'primary'}));
    form.addEventListener('submit', e => {
      e.preventDefault();
      act(form.querySelector('button'), async () => {
        requireGood(pw1.value, pw2.value, context());
        if (pw1.value === cur.value) throw new Error('Choose a password different from your current one.');
        await auth.changePassword(cur.value, pw1.value, others.checked);
        cur.value = pw1.value = pw2.value = '';
        await securityPage();
        return 'Password changed.';
      });
    });
    passwordBox = el('section', {className: 'settings-card'}, el('h2', {text: 'Password'}), form);
  } else {
    passwordBox = el('section', {className: 'settings-card'}, el('h2', {text: 'Password'}),
      el('p', {text: 'You sign in with Google and have no Wearhouse password yet. To add one, we email you a link to set it.'}),
      email ? button('Email me a link to set a password', b => act(b, async () => {
        await auth.requestPasswordReset(email);
        return `A link to set your password was sent to ${email}.`;
      })) : el('p', {className: 'hint', text: 'Your sign-in provider did not share an email address.'}));
  }
  const verify = broker?.emailVerified === false && email
    ? el('p', {className: 'warn'}, `Your email ${email} is not verified. `,
         button('Send verification email', b => act(b, async () => {
           await auth.sendVerificationEmail(email);
           await securityPage();
           return 'Verification email sent.';
         })))
    : email ? el('p', {className: 'hint', text: `Email: ${email}${broker?.emailVerified ? ' (verified)' : ''}`}) : '';

  // sessions
  const deviceList = devices === null
    ? el('p', {className: 'hint', text: 'Your sign-in provider did not list your devices.'})
    : el('ul', {className: 'list', ariaLabel: 'Signed-in devices'}, ...devices.map(d => el('li', {className: 'card'},
        el('span', {className: 'who'}, el('strong', {text: describeDevice(d) + (d.current ? ' (this device)' : '')}), el('br'),
           el('small', {text: [d.ipAddress, d.createdAt ? `signed in ${new Date(d.createdAt).toLocaleString()}` : null].filter(Boolean).join(' · ')})),
        d.current ? '' : button('Sign out this device', b => act(b, async () => {
          await auth.revokeSession(d.token);
          await securityPage();
          return 'That device is signed out.';
        })))));
  const s = sec.current_session;
  view('Security',
       el('p', {className: 'hint', text: 'Your password is kept by our sign-in provider; Wearhouse never receives it.'}),
       verify,
       passwordBox,
       el('section', {className: 'settings-card'}, el('h2', {text: 'Signed-in devices'}), deviceList,
          button('Sign out other devices', b => act(b, async () => {
            await auth.revokeOtherSessions();
            await securityPage();
            return 'Other devices are signed out.';
          })),
          button('Sign out everywhere (including this device)', b => act(b, async () => {
            await api.call('POST', '/me/sessions/revoke-all');
            await auth.revokeSessions();
            await auth.signOut();
            await ctx.afterSignOut();
          }, 'Signed out on every device.'), 'danger'),
          el('p', {className: 'hint', text: s.signed_in_at
            ? `This session signed in ${new Date(s.signed_in_at).toLocaleString()}. `
              + (s.recent_enough_for_sensitive_actions ? 'Recent enough to delete your account.' : 'Sign in again before deleting your account.')
            : ''})),
       el('section', {className: 'settings-card'}, el('h2', {text: 'Sign-in methods'}),
          methods ? el('ul', {}, ...methods.map(m => el('li', {text: m.provider === 'credential' ? 'Email and password' : m.provider === 'google' ? 'Google' : m.provider})))
            : el('p', {text: 'Your sign-in provider did not report your linked methods.'})),
       el('section', {className: 'settings-card'}, el('h2', {text: 'Recent security activity'}),
          sec.events.length ? el('ul', {className: 'list', ariaLabel: 'Security activity'}, ...sec.events.map(e => el('li', {className: 'card'},
            el('span', {className: 'who', text: `${EVENT_TEXT[e.action] ?? e.action}${e.details.keys ? ` (${(e.details.keys as string[]).join(', ')})` : ''}${e.details.role ? `: ${String(e.details.role)}` : ''}`}),
            el('small', {text: `${new Date(e.at).toLocaleString()}${e.by_you ? '' : ' · by staff'}`}))))
            : el('p', {text: 'No security activity yet.'}),
          el('p', {className: 'hint', text: sec.account_created_at ? `Account created ${new Date(sec.account_created_at).toLocaleDateString()}.` : ''})),
       el('p', {}, el('a', {href: '#/account', text: 'Delete account'}), ' · ', el('a', {href: '#/settings', text: 'All settings'})));
}

// ------------------------------------------------------------------ About
export async function aboutPage() {
  const a = await ctx.api().call<About>('GET', '/about', {anonymous: true});
  view('About Wearhouse',
       el('p', {text: `Version ${a.version} · schema ${a.schema_head}`}),
       el('h2', {text: 'Data sources'}),
       el('ul', {}, ...a.sources.map(s => el('li', {},
         el('strong', {text: s.name}), ` (${s.publisher}). ${s.used_for}. Licence: ${s.licence}. `,
         el('a', {href: s.terms_url, text: 'Terms', rel: 'noopener noreferrer', target: '_blank'}),
         s.citation ? el('br') : '', s.citation ? el('small', {text: s.citation}) : ''))),
       el('h2', {text: 'Good to know'}), el('ul', {}, ...a.notices.map(n => el('li', {text: n}))),
       el('p', {className: 'hint', text: a.ai_disclosure}));
  say('');
}
