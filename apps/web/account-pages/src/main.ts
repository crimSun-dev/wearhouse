/**
 * TEMPORARY Wearhouse account pages (add-wearhouse-accounts §8). Plain DOM, hash routing, no styling ambitions.
 * Every value that comes from the API is rendered with textContent (never innerHTML).
 */
import type {Card, FriendRequestOut, FriendsPage, BlocksPage, OwnProfile, Privacy, PublicProfile, RequestsPage,
  SearchResults} from '@wearhouse/contracts';

import {createApi, newIdempotencyKey, type ApiClient} from './api.ts';
import {createAuth} from './auth/provider.ts';
import type {AuthPort} from './auth/port.ts';
import {catalogueRoutes, catalogueNav} from './catalogue.ts';
import {aboutPage, applyDisplay, initSettings, loadSettings, resetPage, securityPage, settingsPage, signInPanel}
  from './settings.ts';
import {initSizes, usualSizesPage} from './sizes.ts';
import {initStaff} from './staff.ts';
import {cartPage, initCommerce, ordersPage, wishlistPage} from './commerce.ts';
import {initWardrobe, looksPage, plannerPage, suggestionsPage, wardrobePage} from './wardrobe.ts';
import {feedPage, initSocial, inspirationPage, notificationsPage, profileViewPage, sharePage, showcaseSettingsPage,
  unreadCount} from './social.ts';
import {describe} from './messages.ts';
import {act, beginRoute, button, el, field, say, view} from './ui.ts';
import './style.css';

type Me = {user_id: string; handle: string | null; needs_onboarding: boolean; roles: string[]; capabilities: string[]};

const API_BASE = (import.meta.env.VITE_WEARHOUSE_API_BASE as string | undefined) ?? 'http://127.0.0.1:8100/api/v2';
const PRESETS = ['plum', 'ivory', 'blush', 'noir', 'sage', 'sky'];

let auth: AuthPort;
let api: ApiClient;
let me: Me | null = null;

const main = document.getElementById('main')!;
const nav = document.getElementById('nav')!;

function avatarNode(c: Card): HTMLElement {
  if (c.avatar.kind === 'provider' && c.avatar.url) {
    return el('img', {className: 'avatar', src: c.avatar.url, alt: '', referrerPolicy: 'no-referrer', width: 40, height: 40});
  }
  return el('span', {className: `avatar preset-${c.avatar.preset ?? 'plum'}`, ariaHidden: 'true'});
}

function cardRow(c: Card, ...actions: HTMLElement[]): HTMLElement {
  return el('li', {className: 'card'}, avatarNode(c),
            el('span', {className: 'who'}, el('strong', {text: c.display_name}), ' ', el('span', {text: '@' + (c.handle ?? '?')})),
            ...actions);
}

// ------------------------------------------------------------------ routing
const ROUTES: Record<string, () => Promise<void>> = {
  '': home, profile: profilePage, privacy: privacyPage, friends: friendsPage, blocks: blocksPage,
  preview: previewPage, account: accountPage, onboarding: onboardingPage, sizes: usualSizesPage,
};

const API_ORIGIN = new URL(API_BASE).origin;
const mediaUrl = (uri: string) => (uri.startsWith('/') ? API_ORIGIN + uri : uri);  // media objects live on the API
const catalogue = catalogueRoutes({api: () => api, caps: () => me?.capabilities ?? [], mediaUrl});
initStaff({api: () => api, caps: () => me?.capabilities ?? []});
initCommerce({api: () => api, signedIn: () => !!me && !me.needs_onboarding});
initWardrobe({api: () => api});
initSocial({api: () => api, handle: () => me?.handle ?? null});
initSizes({api: () => api, signedIn: () => !!me && !me.needs_onboarding});
initSettings({api: () => api, auth: () => auth, handle: () => me?.handle ?? null,
              afterSignIn: async () => { await refreshMe(); location.hash = '#/'; await route(); },
              afterSignOut: async () => { me = null; applyDisplay(null); renderNav(); await home(); }});

function renderNav() {
  nav.replaceChildren();
  const links: Array<[string, string]> = [...catalogueNav(me?.capabilities ?? [])];
  if (me) {
    links.push(['feed', 'Feed'], ['inspiration', 'Inspiration'], ['notifications', 'Notifications'], ['sharing', 'Sharing'], ['wardrobe', 'Wardrobe'], ['planner', 'Planner'], ['wishlist', 'Wishlist'], ['cart', 'Cart'], ['orders', 'Orders'], ['profile', 'Profile'], ['settings', 'Settings'], ['security', 'Security'], ['sizes', 'My sizes'], ['privacy', 'Privacy'], ['friends', 'Friends'], ['blocks', 'Blocks'],
               ['preview', 'Public preview'], ['account', 'Account']);
  } else {
    links.push(['', 'Sign in'], ['about', 'About']);
  }
  for (const [hash, label] of links) nav.append(el('a', {href: '#/' + hash, text: label, id: 'nav-' + (hash || 'home')}));
  if (me && !me.needs_onboarding) {
    void unreadCount().then(n => {
      const link = document.getElementById('nav-notifications');
      if (link && n > 0) link.textContent = `Notifications (${n})`;
    });
  }
}

async function route() {
  beginRoute();
  const name = location.hash.replace(/^#\/?/, '').split('?')[0];
  const parts = name.split('/');
  if (parts[0] === 'store') return catalogue.store(parts.slice(1));  // the store is public
  if (parts[0] === 'u' && parts[1]) return profileViewPage(parts[1]);  // public profile view
  if (parts[0] === 'share' && parts[1]) return sharePage(parts[1]);
  if (parts[0] === 'reset') return resetPage();  // password reset links arrive signed out
  if (parts[0] === 'about') return aboutPage();
  if (!me) return home();
  if (me.needs_onboarding && name !== 'account') return onboardingPage();
  if (parts[0] === 'staff') return catalogue.staff(parts.slice(1));
  if (parts[0] === 'orders') return ordersPage(parts.slice(1));
  if (parts[0] === 'wishlist') return wishlistPage();
  if (parts[0] === 'cart') return cartPage();
  if (parts[0] === 'wardrobe') return wardrobePage(parts.slice(1));
  if (parts[0] === 'looks') return looksPage();
  if (parts[0] === 'planner') return plannerPage();
  if (parts[0] === 'suggestions') return suggestionsPage();
  if (parts[0] === 'feed') return feedPage(parts.slice(1));
  if (parts[0] === 'notifications') { await notificationsPage(); renderNav(); return; }
  if (parts[0] === 'sharing') return showcaseSettingsPage();
  if (parts[0] === 'settings') return settingsPage(parts[1]);
  if (parts[0] === 'security') return securityPage();
  if (parts[0] === 'inspiration') return inspirationPage();
  await (ROUTES[name] ?? profilePage)();
}

async function refreshMe() {
  const session = await auth.session();
  me = session ? await api.call<Me>('GET', '/me') : null;
  if (me) await loadSettings(); else applyDisplay(null);  // theme + reduced motion follow the account
  renderNav();
}

// ------------------------------------------------------------------ pages
async function home() {
  if (me) return profilePage();
  view('Sign in to Wearhouse',
       el('p', {text: 'Sign in with Google, or with your email and password.'}),
       ...signInPanel());
}

async function onboardingPage() {
  const input = el('input', {name: 'handle', autocomplete: 'username', required: true, maxLength: 20,
                             placeholder: 'e.g. dravenstyle'});
  const form = el('form', {}, field('Choose your handle', input),
                  el('p', {className: 'hint', text: '3–20 characters: a–z, 0–9 and _, starting with a letter.'}),
                  el('button', {type: 'submit', text: 'Save handle', className: 'primary'}));
  form.addEventListener('submit', e => {
    e.preventDefault();
    act(form.querySelector('button'), async () => {
      await api.call<OwnProfile>('PATCH', '/me/profile', {body: {handle: input.value}});
      await refreshMe();
      location.hash = '#/profile';
      await route();
    }, 'Handle saved.');
  });
  view('Welcome! Pick a handle', form);
}

async function profilePage() {
  const p = await api.call<OwnProfile>('GET', '/me/profile');
  const handle = el('input', {value: p.handle ?? '', maxLength: 20});
  const name = el('input', {value: p.display_name, maxLength: 32});
  const bio = el('textarea', {value: p.bio, maxLength: 160, rows: 3});
  const avatar = el('select', {});
  for (const preset of PRESETS) avatar.append(el('option', {value: 'preset:' + preset, text: `Preset: ${preset}`}));
  avatar.append(el('option', {value: 'provider', text: 'My Google picture'}));
  avatar.value = p.avatar.kind === 'provider' ? 'provider' : 'preset:' + (p.avatar.preset ?? 'plum');
  const form = el('form', {}, field('Handle', handle), field('Display name', name), field('Bio', bio),
                  field('Avatar', avatar), el('button', {type: 'submit', text: 'Save profile', className: 'primary'}));
  form.addEventListener('submit', e => {
    e.preventDefault();
    const body: Record<string, unknown> = {display_name: name.value, bio: bio.value,
      avatar: avatar.value === 'provider' ? {kind: 'provider'} : {kind: 'preset', preset: avatar.value.slice(7)}};
    if (handle.value.trim().toLowerCase() !== (p.handle ?? '')) body.handle = handle.value;
    act(form.querySelector('button'), async () => {
      await api.call<OwnProfile>('PATCH', '/me/profile', {body});
      await refreshMe();
    }, 'Profile saved.');
  });
  view('Your profile', el('p', {}, avatarNode(p), ' Member since ', p.member_since), form);
}

async function privacyPage() {
  const cur = await api.call<Privacy>('GET', '/me/privacy');
  const selects = (['profile', 'wardrobe', 'friends_list'] as const).map(key => {
    const s = el('select', {name: key, id: 'privacy-' + key});
    for (const v of ['public', 'friends', 'private']) s.append(el('option', {value: v, text: v}));
    s.value = cur[key];
    return s;
  });
  const labels = ['Who can see my profile details', 'Who can see my wardrobe', 'Who can see my friends list'];
  const form = el('form', {}, ...selects.map((s, i) => field(labels[i], s)),
                  el('button', {type: 'submit', text: 'Save privacy', className: 'primary'}));
  form.addEventListener('submit', e => {
    e.preventDefault();
    act(form.querySelector('button'), () => api.call<Privacy>('PUT', '/me/privacy', {
      body: {profile: selects[0].value, wardrobe: selects[1].value, friends_list: selects[2].value}}), 'Privacy saved.');
  });
  view('Privacy', el('p', {text: 'Blocked accounts never see anything, whatever these say.'}), form);
}

async function friendsPage() {
  const [incoming, outgoing, friends] = await Promise.all([
    api.call<RequestsPage>('GET', '/me/friend-requests', {query: {direction: 'incoming'}}),
    api.call<RequestsPage>('GET', '/me/friend-requests', {query: {direction: 'outgoing'}}),
    api.call<FriendsPage>('GET', '/me/friends')]);
  const q = el('input', {type: 'search', maxLength: 21, placeholder: 'handle (3+ letters) or @exact'});
  const results = el('ul', {className: 'list', ariaLabel: 'Search results'});
  const searchForm = el('form', {role: 'search'}, field('Find people', q), el('button', {type: 'submit', text: 'Search'}));
  searchForm.addEventListener('submit', e => {
    e.preventDefault();
    act(searchForm.querySelector('button'), async () => {
      const r = await api.call<SearchResults>('GET', '/users/search', {query: {q: q.value}});
      results.replaceChildren(...r.results.filter(c => c.handle !== me?.handle).map(c => cardRow(c,
        button('Add friend', b => act(b, async () => {
          const out = await api.call<FriendRequestOut>('POST', '/me/friend-requests',
                                                       {body: {handle: c.handle}, idem: newIdempotencyKey()});
          await friendsPage();
          return out.status === 'accepted' ? `You and @${c.handle} are now friends.` : `Request sent to @${c.handle}.`;
        })))));
      if (!r.results.length) results.append(el('li', {text: 'No matches.'}));
    }, 'Search done.');
  });
  const rerender = (msg: string) => async () => { await friendsPage(); say(msg); };
  view('Friends', searchForm, results,
       el('h2', {text: `Incoming requests (${incoming.requests.length})`}),
       el('ul', {className: 'list'}, ...incoming.requests.map(r => cardRow(r.account,
         button('Accept', b => act(b, () => api.call('POST', `/me/friend-requests/${r.request_id}/accept`))
           .then(rerender(`You and @${r.account.handle} are now friends.`)), 'primary'),
         button('Decline', b => act(b, () => api.call('POST', `/me/friend-requests/${r.request_id}/decline`))
           .then(rerender('Request declined.')))))),
       el('h2', {text: `Sent requests (${outgoing.requests.length})`}),
       el('ul', {className: 'list'}, ...outgoing.requests.map(r => cardRow(r.account,
         button('Cancel', b => act(b, () => api.call('DELETE', `/me/friend-requests/${r.request_id}`))
           .then(rerender('Request cancelled.')))))),
       el('h2', {text: `Your friends (${friends.friends.length})`}),
       el('ul', {className: 'list'}, ...friends.friends.map(f => cardRow(f,
         button('Remove', b => act(b, () => api.call('DELETE', `/me/friends/${f.handle}`))
           .then(rerender(`Removed @${f.handle}.`))),
         button('Block', b => act(b, () => api.call('PUT', `/me/blocks/${f.handle}`))
           .then(rerender(`Blocked @${f.handle}.`)), 'danger')))));
}

async function blocksPage() {
  const blocks = await api.call<BlocksPage>('GET', '/me/blocks');
  const input = el('input', {maxLength: 20, placeholder: 'handle'});
  const form = el('form', {}, field('Block a handle', input), el('button', {type: 'submit', text: 'Block', className: 'danger'}));
  form.addEventListener('submit', e => {
    e.preventDefault();
    act(form.querySelector('button'), async () => {
      await api.call('PUT', `/me/blocks/${encodeURIComponent(input.value.trim())}`);
      await blocksPage();
    }, 'Blocked.');
  });
  view('Blocked accounts', el('p', {text: 'Blocking ends any friendship and pending requests. They are not told.'}), form,
       el('ul', {className: 'list'}, ...blocks.blocks.map(c => cardRow(c,
         button('Unblock', b => act(b, async () => { await api.call('DELETE', `/me/blocks/${c.handle}`); await blocksPage(); },
                                    `Unblocked @${c.handle}.`))))));
}

async function previewPage() {
  const handle = me?.handle ?? '';
  const anon = await api.call<PublicProfile>('GET', `/profiles/${handle}`, {anonymous: true});
  const lines = [`Profile visibility: ${anon.profile_visibility}`];
  if (anon.bio !== undefined && anon.bio !== null) lines.push(`Bio: ${anon.bio || '(empty)'}`);
  if (anon.sections) lines.push(`Wardrobe: ${anon.sections.wardrobe}`, `Friends list: ${anon.sections.friends_list}`);
  view('Your public profile (as a signed-out visitor sees it)',
       el('ul', {className: 'list'}, cardRow(anon)), el('ul', {}, ...lines.map(t => el('li', {text: t}))));
}

async function accountPage() {
  const methods = await auth.listMethods();
  const confirm = el('input', {autocomplete: 'off', placeholder: me?.handle ?? 'DELETE'});
  const deleteForm = el('form', {}, field(`Type ${me?.handle ? 'your handle' : 'DELETE'} to confirm`, confirm),
                        el('button', {type: 'submit', text: 'Delete my account', className: 'danger'}));
  const outcome = el('div', {className: 'outcome'});
  deleteForm.addEventListener('submit', e => {
    e.preventDefault();
    act(deleteForm.querySelector('button'), async () => {
      await api.call('DELETE', '/me', {body: {confirm: confirm.value}});
      const broker = await auth.deleteBrokerUser();
      await auth.signOut();
      me = null;
      renderNav();
      outcome.replaceChildren(el('p', {text: 'Your Wearhouse account was deleted. Claimed garments stay claimed so nobody else can redeem them.'}),
        broker === 'deleted'
          ? el('p', {text: 'Your sign-in identity was also deleted from our sign-in provider.'})
          : el('p', {className: 'warn', text: 'Your sign-in identity (including the email our sign-in provider holds) was NOT deleted, '
            + 'because the provider does not allow self-deletion. Email the Wearhouse team to have it removed; '
            + 'we will confirm when it is done.'}));
      main.replaceChildren(el('h1', {text: 'Account deleted'}), outcome);
    }, 'Account deleted.');
  });
  view('Account',
       el('h2', {text: 'Sign-in methods'}),
       methods ? el('ul', {}, ...methods.map(m => el('li', {text: m.provider}))) : el('p', {text: 'Your sign-in provider did not report your linked methods.'}),
       el('p', {className: 'hint', text: 'Linking and unlinking sign-in methods is managed by the sign-in provider; your Wearhouse account stays the same.'}),
       el('h2', {text: 'Sessions'}),
       button('Sign out everywhere', b => act(b, async () => {
         await api.call('POST', '/me/sessions/revoke-all');
         await auth.revokeSessions();
         await auth.signOut();
         me = null;
         renderNav();
         await home();
       }, 'Signed out on every device.')),
       button('Sign out', b => act(b, async () => { await auth.signOut(); me = null; renderNav(); await home(); }, 'Signed out.')),
       el('h2', {text: 'Your data'}),
       button('Download my data (JSON)', b => act(b, async () => {
         const res = await api.raw('/me/export');
         if (!res.ok) throw new Error(`Export failed (${res.status}).`);
         const blob = await res.blob();
         const link = el('a', {href: URL.createObjectURL(blob), download: 'wearhouse-export.json'});
         document.body.append(link);
         link.click();
         link.remove();
       }, 'Export downloaded.')),
       el('h2', {text: 'Delete account'}), deleteForm, outcome);
}

// ------------------------------------------------------------------ boot
async function boot() {
  try {
    auth = createAuth();
    api = createApi(auth, API_BASE);
    await refreshMe();
  } catch (err) {
    say(describe(err), 'error');
  }
  await route().catch(err => say(describe(err), 'error'));
}

// Routes run one at a time, in order: a slow render for a route the user already left finishes first and is then
// skipped by view() (its hash is no longer current), so it can never overwrite the page that follows it.
let routing: Promise<void> = Promise.resolve();
window.addEventListener('hashchange', () => {
  routing = routing.then(() => route()).catch(err => say(describe(err), 'error'));
});
void boot();
