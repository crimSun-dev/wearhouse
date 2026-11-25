/**
 * TEMPORARY social pages (add-wearhouse-social-profile-services 5.2): share controls, Feed (Friends + What's New),
 * Notifications, Showcase/sharing settings and a public profile view (showcase, shares, week). Plain DOM.
 * Everything shown comes from safe projections: no serials, keys, item ids, photos, wear or location.
 */
import type {BrowsePage, Feed, MyShowcase, Notifications, Share, SharesPage, Showcase, Unread, Week} from '@wearhouse/contracts';

import {ApiFailure, type ApiClient} from './api.ts';
import {act, button, el, field, select, view} from './ui.ts';

type Ctx = {api: () => ApiClient; handle: () => string | null};
let ctx: Ctx;

export function initSocial(c: Ctx) {
  ctx = c;
}

const ACCENTS = ['plum', 'ivory', 'blush', 'noir', 'sage', 'sky'];

function shareCard(s: Share): HTMLElement {
  const items = (s.look?.items ?? []).map(i => el('li', {},
    `${i.slot}: ${i.name ?? '(no longer available)'}${i.colour ? ` · ${i.colour}` : ''}${i.verified ? ' · verified' : ''} `,
    i.product_id ? el('a', {href: `#/store/product/${i.product_id}`, text: 'View in store'}) : ''));
  return el('li', {className: 'card share'},
    el('span', {className: 'who'},
       el('strong', {text: s.look?.look_name ?? 'Look'}), ' by ',
       s.owner?.handle ? el('a', {href: `#/u/${s.owner.handle}`, text: `@${s.owner.handle}`}) : 'a deleted account',
       el('br'), el('small', {text: `${new Date(s.created_at).toLocaleString()} · ${s.audience}${s.caption ? ` · “${s.caption}”` : ''}`}),
       el('ul', {}, ...items)));
}

export function shareControls(lookId: string): HTMLElement {
  const audience = select('audience', [['friends', 'Friends'], ['public', 'Public']]);
  audience.ariaLabel = 'Share audience';
  const caption = el('input', {name: 'caption', maxLength: 140, placeholder: 'Caption (optional)'});
  caption.ariaLabel = 'Share caption';
  return el('div', {className: 'share-controls'}, audience, caption, button('Share look', b => act(b, async () => {
    const s = await ctx.api().call<Share>('POST', '/me/shares', {body: {look_id: lookId, audience: audience.value,
                                                                        caption: caption.value || null}});
    return s.effective_audience === 'private'
      ? 'Shared, but nobody can see it: your wardrobe privacy is private (change it on the Privacy page).'
      : `Shared with ${s.effective_audience}.`;
  })));
}

// ================================================================== feed
export async function feedPage(parts: string[]) {
  const api = ctx.api();
  const tabs = el('p', {className: 'subnav'}, el('a', {href: '#/feed', text: 'Friends'}), ' · ',
                  el('a', {href: '#/feed/new', text: "What's New"}));
  if (parts[0] === 'new') {
    const page = await api.call<BrowsePage>('GET', '/catalogue/products', {anonymous: true, query: {sort: 'newest', limit: '12'}});
    return view("What's New", tabs, el('ul', {className: 'list grid'}, ...page.items.map(p => el('li', {className: 'card'},
      el('a', {href: `#/store/product/${p.id}`, text: p.name ?? p.id}), ' ', el('small', {text: [p.category, p.colour].filter(Boolean).join(' · ')})))));
  }
  const list = el('ul', {className: 'list'});
  const more = el('div', {});
  async function load(cursor?: string) {
    const f = await api.call<Feed>('GET', '/me/feed', {query: {limit: '10', cursor}});
    list.append(...f.items.map(shareCard));
    more.replaceChildren(f.next_cursor ? button('Load more', b => act(b, () => load(f.next_cursor!), 'Loaded more.')) : '');
    if (!list.children.length) list.append(el('li', {text: 'Nothing yet. When friends share looks, they appear here.'}));
  }
  view('Friends feed', tabs, list, more);
  await load();
}

// ================================================================== notifications
export async function unreadCount(): Promise<number> {
  try {
    return (await ctx.api().call<Unread>('GET', '/me/notifications/unread-count')).unread;
  } catch {
    return 0;
  }
}

export async function notificationsPage() {
  const api = ctx.api();
  const n = await api.call<Notifications>('GET', '/me/notifications');
  const text = (k: string, who: string) => k === 'friend_request' ? `@${who} sent you a friend request`
    : k === 'request_accepted' ? `@${who} accepted your friend request` : `@${who} shared a look`;
  view('Notifications',
       button('Mark all read', b => act(b, async () => {
         await api.call('POST', '/me/notifications/read');
         const badge = document.getElementById('nav-notifications');
         if (badge) badge.textContent = 'Notifications';
         await notificationsPage();
         return 'All read.';
       })),
       el('ul', {className: 'list'}, ...n.items.map(i => el('li', {className: `card${i.unread ? ' unread' : ''}`},
         el('span', {className: 'who'}, i.unread ? el('strong', {text: '● '}) : '',
            i.kind === 'friend_shared_look' ? el('a', {href: `#/share/${i.ref}`, text: text(i.kind, i.account.handle ?? '?')})
              : i.kind === 'friend_request' ? el('a', {href: '#/friends', text: text(i.kind, i.account.handle ?? '?')})
              : el('span', {text: text(i.kind, i.account.handle ?? '?')}),
            el('br'), el('small', {text: new Date(i.at).toLocaleString()}))))),
       n.items.length ? '' : el('p', {text: 'No notifications.'}));
}

export async function sharePage(id: string) {
  const api = ctx.api();
  const s = await api.call<Share>('GET', `/shares/${encodeURIComponent(id)}`);
  const mine = ctx.handle() !== null && s.owner?.handle === ctx.handle();
  const reason = el('input', {name: 'reason', id: 'report-reason', maxLength: 300, placeholder: 'What is wrong with it?'});
  const report = el('form', {}, field('Report this look', reason), el('button', {type: 'submit', text: 'Report'}));
  report.addEventListener('submit', e => {
    e.preventDefault();
    act(report.querySelector('button'), async () => {
      await api.call('POST', `/shares/${s.id}/report`, {body: {reason: reason.value}});
      return 'Reported. A moderator will review it.';
    });
  });
  view('Shared look', el('ul', {className: 'list'}, shareCard(s)),
       s.moderation === 'hidden' ? el('p', {className: 'warn', text: 'Hidden by moderation: only you can see this share.'}) : '',
       el('p', {className: 'hint', text: 'Inspiration only: viewing a look never adds anything to your wardrobe.'}),
       ctx.handle() && !mine ? el('div', {},
         button('Save as inspiration', b => act(b, async () => {
           await api.call('POST', '/me/inspirations', {body: {share_id: s.id}});
           return 'Saved to your inspiration.';
         }), 'primary'),
         report) : '');
}

// ================================================================== inspiration (complete-wearhouse-tdd)
type Inspiration = {id: string; saved_at: string; caption: string | null; from: {handle: string | null} | null;
                    look: Share['look']};

export async function inspirationPage() {
  const api = ctx.api();
  const r = await api.call<{items: Inspiration[]}>('GET', '/me/inspirations');
  view(`Inspiration (${r.items.length})`,
       el('p', {className: 'hint', text: 'Snapshots of looks you saved. They never add items to your wardrobe; missing pieces link to the store.'}),
       el('ul', {className: 'list'}, ...r.items.map(i => el('li', {className: 'card share'},
         el('span', {className: 'who'}, el('strong', {text: i.look?.look_name ?? 'Look'}),
            i.from?.handle ? ` from @${i.from.handle}` : '', el('br'),
            el('small', {text: `saved ${new Date(i.saved_at).toLocaleString()}${i.caption ? ` · “${i.caption}”` : ''}`}),
            el('ul', {}, ...(i.look?.items ?? []).map(x => el('li', {}, `${x.slot}: ${x.name ?? '(unavailable)'} `,
              x.product_id ? el('a', {href: `#/store/product/${x.product_id}`, text: 'View in store'}) : '')))),
         button('Remove', b => act(b, async () => {
           await api.call('DELETE', `/me/inspirations/${i.id}`);
           await inspirationPage();
           return 'Removed.';
         }))))),
       r.items.length ? '' : el('p', {text: 'Nothing saved yet. Open a friend\'s shared look and choose "Save as inspiration".'}));
}

// ================================================================== settings: shares, plan sharing, showcase
export async function showcaseSettingsPage() {
  const api = ctx.api();
  const [mine, sc, plan] = await Promise.all([api.call<Share[]>('GET', '/me/shares'), api.call<MyShowcase>('GET', '/me/showcase'),
                                              api.call<{audience: string}>('GET', '/me/plan-sharing')]);
  const active = mine.filter(s => !s.revoked);
  const headline = el('input', {name: 'headline', maxLength: 80, value: sc.headline ?? ''});
  const accent = select('accent', ACCENTS.map(a => [a, a]), sc.accent);
  const boxes = active.map(s => {
    const cb = el('input', {type: 'checkbox', value: s.id, checked: sc.featured.includes(s.id)});
    cb.id = `feat-${s.id}`;
    return el('label', {className: 'check', htmlFor: cb.id}, cb, ` ${s.look?.look_name ?? s.id} (${s.audience})`);
  });
  const form = el('form', {}, field('Headline', headline), field('Accent', accent),
                  el('fieldset', {}, el('legend', {text: 'Featured shares (up to 3)'}), ...boxes),
                  el('button', {type: 'submit', text: 'Save showcase', className: 'primary'}));
  form.addEventListener('submit', e => {
    e.preventDefault();
    const featured = boxes.map(b => b.querySelector('input')!).filter(c => c.checked).map(c => c.value);
    act(form.querySelector('button'), async () => {
      await api.call('PUT', '/me/showcase', {body: {headline: headline.value || null, accent: accent.value, featured_share_ids: featured}});
      return 'Showcase saved.';
    });
  });
  const planSel = select('plan', [['none', 'Nobody'], ['friends', 'Friends']], plan.audience);
  planSel.ariaLabel = 'Who can see my week plan';
  planSel.addEventListener('change', () => act(null, async () => {
    await api.call('PUT', '/me/plan-sharing', {body: {audience: planSel.value}});
    return `Week plan visible to: ${planSel.value}.`;
  }));
  view('Sharing & showcase',
       el('p', {}, ctx.handle() ? el('a', {href: `#/u/${ctx.handle()}`, text: 'View my public profile'}) : ''),
       el('h2', {text: 'Showcase'}), form,
       el('h2', {text: 'Week plan'}), field('Who can see my week plan', planSel),
       el('h2', {text: 'My shares'}),
       el('ul', {className: 'list'}, ...mine.map(s => el('li', {className: 'card'},
         el('span', {className: 'who'}, el('strong', {text: s.look?.look_name ?? 'Look'}), el('br'),
            el('small', {text: s.revoked ? 'revoked' : `audience ${s.audience} · visible to ${s.effective_audience === 'private' ? 'nobody (wardrobe privacy is private)' : s.effective_audience}`})),
         s.revoked ? '' : button('Re-pin to latest', b => act(b, async () => {
           await api.call('PATCH', `/me/shares/${s.id}`, {body: {repin: true}}); await showcaseSettingsPage(); return 'Re-pinned.';
         })),
         s.revoked ? '' : button('Revoke', b => act(b, async () => {
           await api.call('DELETE', `/me/shares/${s.id}`); await showcaseSettingsPage(); return 'Share revoked.';
         }), 'danger')))));
}

// ================================================================== public profile
async function orHidden<T>(p: Promise<T>): Promise<T | null> {
  try {
    return await p;
  } catch (err) {
    if (err instanceof ApiFailure && err.status === 404) return null;
    throw err;
  }
}

export async function profileViewPage(handle: string) {
  const api = ctx.api();
  const h = encodeURIComponent(handle);
  const [sc, shares, week] = await Promise.all([
    orHidden(api.call<Showcase>('GET', `/profiles/${h}/showcase`)), orHidden(api.call<SharesPage>('GET', `/profiles/${h}/shares`)),
    orHidden(api.call<Week>('GET', `/profiles/${h}/week`))]);
  view(`@${handle}`,
       sc ? el('section', {className: `showcase accent-${sc.accent}`}, el('h2', {text: sc.headline ?? sc.owner.display_name}),
               el('ul', {className: 'list'}, ...sc.featured.map(shareCard)))
          : el('p', {text: 'This profile is not visible to you.'}),
       el('h2', {text: 'Shared looks'}),
       shares && shares.items.length ? el('ul', {className: 'list'}, ...shares.items.map(shareCard)) : el('p', {text: 'No looks you can see.'}),
       el('h2', {text: 'Week plan'}),
       week ? el('ul', {className: 'list'}, ...week.days.map(d => el('li', {},
         `${d.date}: ${d.look ? d.look.look_name : '—'}${d.occasion ? ` (${d.occasion})` : ''}`)))
            : el('p', {text: 'Not shared with you.'}));
}
