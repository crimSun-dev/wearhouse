/**
 * TEMPORARY staff workspace (add-wearhouse-object-management 5.2). Sections appear per CAPABILITY from /me; the
 * server enforces every capability regardless of what is shown here. Plain DOM, no polish.
 */
import type {MediaObject, StaffAccount, StaffOrdersPage, StaffUnitsPage} from '@wearhouse/contracts';

import {newIdempotencyKey, type ApiClient} from './api.ts';
import {act, button, el, field, select, view} from './ui.ts';

type Ctx = {api: () => ApiClient; caps: () => string[]};
let ctx: Ctx;

export function initStaff(c: Ctx) {
  ctx = c;
}

export const SECTIONS: Array<{hash: string; label: string; cap: string}> = [
  {hash: 'staff/review', label: 'Review queue', cap: 'catalogue:ingest'},
  {hash: 'staff/import', label: 'Import CSV', cap: 'catalogue:ingest'},
  {hash: 'staff/products', label: 'Products & media', cap: 'catalogue:media'},
  {hash: 'staff/collections', label: 'Collections', cap: 'catalogue:ingest'},
  {hash: 'staff/sizes', label: 'Sizes', cap: 'catalogue:ingest'},
  {hash: 'staff/offers', label: 'Offers', cap: 'commerce:offers'},
  {hash: 'staff/units', label: 'Units', cap: 'inventory:issue'},
  {hash: 'staff/orders', label: 'Orders', cap: 'commerce:orders'},
  {hash: 'staff/moderation', label: 'Moderation', cap: 'social:moderate'},
  {hash: 'staff/roles', label: 'Roles', cap: 'identity:manage_roles'},
];

export const can = (cap: string) => ctx.caps().includes(cap);
export const hasStaffAccess = (caps: string[]) => SECTIONS.some(s => caps.includes(s.cap));

export function staffNav(): HTMLElement {
  const links = SECTIONS.filter(s => can(s.cap));
  const p = el('p', {className: 'subnav', ariaLabel: 'Staff sections'});
  links.forEach((s, i) => { if (i) p.append(' · '); p.append(el('a', {href: `#/${s.hash}`, text: s.label})); });
  return p;
}

export function staffHome() {
  const links = SECTIONS.filter(s => can(s.cap));
  view('Staff workspace', links.length
    ? el('ul', {className: 'list'}, ...links.map(s => el('li', {}, el('a', {href: `#/${s.hash}`, text: s.label}))))
    : el('p', {text: 'Your account has no staff role. An admin can grant one.'}));
}

export function denied(section: string) {
  view(section, staffNav(), el('p', {text: 'Your account does not have the role this section needs.'}));
}

// ================================================================== product media (inside the staff product page)
export async function mediaPanel(productId: string, rerender: () => Promise<void>): Promise<HTMLElement> {
  const api = ctx.api();
  const items = await api.call<MediaObject[]>('GET', `/admin/catalogue/products/${productId}/media`);
  const list = el('ul', {className: 'list media-list', ariaLabel: 'Media objects'});
  items.forEach((m, i) => {
    const img = el('img', {className: 'thumb', alt: m.alt_text ?? '', width: 64, height: 80});
    void api.raw(`/media/${m.id}`).then(async r => { if (r.ok) img.src = URL.createObjectURL(await r.blob()); });
    const move = (delta: number) => act(null, async () => {
      const ids = items.map(x => x.id);
      [ids[i], ids[i + delta]] = [ids[i + delta], ids[i]];
      await api.call('PUT', `/admin/catalogue/products/${productId}/media/order`, {body: {media_ids: ids}});
      await rerender();
      return 'Order saved.';
    });
    list.append(el('li', {className: 'card'}, img,
      el('span', {className: 'who'}, el('strong', {text: `${i === 0 ? 'Thumbnail · ' : ''}${m.kind}`}), el('br'),
         el('small', {text: `${m.content_type} · ${Math.round(m.byte_size / 1024)} KB · rights: ${String(m.rights.basis ?? '?')}`})),
      i > 0 ? button('↑', () => move(-1)) : '', i < items.length - 1 ? button('↓', () => move(1)) : '',
      button('Remove', b => act(b, async () => {
        await api.call('DELETE', `/admin/catalogue/media/${m.id}`);
        await rerender();
        return 'Media removed.';
      }), 'danger')));
  });
  const file = el('input', {type: 'file', accept: 'image/jpeg,image/png,image/webp', name: 'media_file'});
  const basis = el('input', {name: 'rights_basis', placeholder: 'e.g. own-photo, licensed', maxLength: 200});
  const alt = el('input', {name: 'alt', maxLength: 200});
  const form = el('form', {}, field('Image (JPEG/PNG/WebP, max 5 MB)', file), field('Rights basis', basis), field('Alt text', alt),
                  el('button', {type: 'submit', text: 'Upload image'}));
  form.addEventListener('submit', e => {
    e.preventDefault();
    act(form.querySelector('button'), async () => {
      if (!file.files?.[0]) throw new Error('Choose an image first.');
      const q = new URLSearchParams({rights_basis: basis.value, alt: alt.value}).toString();
      await api.upload('POST', `/admin/catalogue/products/${productId}/media?${q}`, file.files[0]);
      await rerender();
      return 'Image uploaded.';
    });
  });
  return el('section', {}, el('h2', {text: `Media (${items.length})`}), list,
    items.length ? '' : el('p', {text: 'No media. Generate a placeholder or upload an image.'}),
    button('Generate placeholder', b => act(b, async () => {
      await api.call('POST', `/admin/catalogue/products/${productId}/media/generate`);
      await rerender();
      return 'Placeholder generated.';
    })), form);
}

export function productsPage() {
  if (!can('catalogue:media')) return denied('Products & media');
  const id = el('input', {name: 'product_id', placeholder: 'product id', required: true});
  const form = el('form', {}, field('Open a product by id', id), el('button', {type: 'submit', text: 'Open'}));
  form.addEventListener('submit', e => { e.preventDefault(); location.hash = `#/staff/product/${id.value.trim()}`; });
  const gen = button('Generate placeholders for products without media', b => act(b, async () => {
    let total = 0;
    for (let i = 0; i < 20; i++) {
      const r = await ctx.api().call<{generated: number; more_remaining: boolean}>('POST', '/admin/catalogue/media/generate-missing', {query: {limit: '2000'}});
      total += r.generated;
      if (!r.more_remaining) break;
    }
    return `Generated ${total} placeholder(s).`;
  }));
  view('Products & media', staffNav(), el('p', {className: 'hint', text: 'Find products in the Store (or the review queue), then open them here to manage their images.'}),
       el('p', {}, el('a', {href: '#/store', text: 'Search the store'})), form, gen);
}

// ================================================================== units
export async function unitsPage() {
  if (!can('inventory:issue')) return denied('Units');
  const api = ctx.api();
  const params = new URLSearchParams(location.hash.split('?')[1] ?? '');
  const pid = el('input', {name: 'product_id', value: params.get('product') ?? '', required: true, placeholder: 'product id'});
  const qty = select('qty', ['1', '2', '3', '5', '10'].map(v => [v, v]), '1');
  const out = el('div', {});
  const form = el('form', {}, field('Product id', pid), field('Units to issue', qty),
                  el('button', {type: 'submit', text: 'Issue units', className: 'primary'}));
  form.addEventListener('submit', e => {
    e.preventDefault();
    act(form.querySelector('button'), async () => {
      const keys: HTMLElement[] = [];
      for (let i = 0; i < Number(qty.value); i++) {
        const u = await api.call<{public_serial: string; delivery: {status: string; activation_key?: string}}>(
          'POST', '/admin/unit-batches', {body: {product_id: pid.value.trim()}, idem: newIdempotencyKey()});
        keys.push(el('li', {}, el('code', {text: u.public_serial}), ' key: ', el('code', {text: u.delivery.activation_key ?? `(${u.delivery.status})`})));
      }
      out.replaceChildren(el('h2', {text: 'Issued (keys shown once to you; keep them private)'}), el('ul', {}, ...keys));
      await loadList();
      return `Issued ${keys.length} unit(s).`;
    });
  });
  const list = el('ul', {className: 'list', ariaLabel: 'Units'});
  async function loadList() {
    if (!pid.value.trim()) return;
    const page = await api.call<StaffUnitsPage>('GET', '/admin/units', {query: {product_id: pid.value.trim(), limit: '50'}});
    list.replaceChildren(...page.items.map(u => el('li', {className: 'card'},
      el('span', {className: 'who'}, el('code', {text: u.public_serial}), el('br'),
         el('small', {text: `${u.status} · issued ${new Date(u.created_at).toLocaleString()}`})),
      u.status === 'issued' && can('inventory:reissue') ? button('Reissue key', b => act(b, async () => {
        const r = await api.call<{delivery: {activation_key?: string; status: string}}>('POST', `/admin/units/${u.unit_id}/reissue`, {idem: newIdempotencyKey()});
        out.replaceChildren(el('p', {}, 'New key for ', el('code', {text: u.public_serial}), ': ', el('code', {text: r.delivery.activation_key ?? r.delivery.status})));
        return 'Key reissued; the old key no longer works.';
      })) : '')));
    if (!page.items.length) list.append(el('li', {text: 'No units yet.'}));
  }
  pid.addEventListener('change', () => act(null, async () => { await loadList(); return 'Units loaded.'; }));
  view('Units', staffNav(), form, out, el('h2', {text: 'Units of this product'}), list);
  await loadList().catch(() => undefined);
}

// ================================================================== orders
export async function ordersStaffPage() {
  if (!can('commerce:orders')) return denied('Orders');
  const status = select('status', [['', 'All'], ['fulfilled', 'Fulfilled'], ['cancelled', 'Cancelled']]);
  status.ariaLabel = 'Order status';
  const list = el('ul', {className: 'list'});
  const more = el('div', {});
  async function load(cursor?: string) {
    const page = await ctx.api().call<StaffOrdersPage>('GET', '/admin/commerce/orders',
      {query: {status: status.value || undefined, cursor, limit: '25'}});
    if (!cursor) list.replaceChildren();
    list.append(...page.items.map(o => el('li', {className: 'card'}, el('span', {className: 'who'},
      el('strong', {text: `${o.buyer_handle ? '@' + o.buyer_handle : '(deleted account)'} · ${o.item_count} item(s)`}), el('br'),
      el('small', {text: `${new Date(o.created_at).toLocaleString()} · ${o.status} · ${o.total_idr.toLocaleString('id-ID')} IDR (sandbox) · ${o.lines.map(l => l.product_name).join(', ')}`})))));
    if (!list.children.length) list.append(el('li', {text: 'No orders.'}));
    more.replaceChildren(page.next_cursor ? button('Load more', b => act(b, () => load(page.next_cursor!), 'Loaded more.')) : '');
  }
  status.addEventListener('change', () => act(null, async () => { await load(); return 'Filtered.'; }));
  view('Orders', staffNav(), field('Status', status), list, more);
  await load();
}

// ================================================================== roles
const ROLES = ['catalogue_editor', 'inventory_manager', 'moderator', 'admin'];

export async function rolesPage() {
  if (!can('identity:manage_roles')) return denied('Roles');
  const api = ctx.api();
  const staff = await api.call<StaffAccount[]>('GET', '/admin/staff');
  const handle = el('input', {name: 'handle', placeholder: 'handle', maxLength: 20, required: true});
  const role = select('role', ROLES.map(r => [r, r]), 'catalogue_editor');
  const form = el('form', {}, field('Account handle', handle), field('Role', role),
                  el('button', {type: 'submit', text: 'Grant role', className: 'primary'}));
  form.addEventListener('submit', e => {
    e.preventDefault();
    act(form.querySelector('button'), async () => {
      await api.call('PUT', `/admin/staff/${encodeURIComponent(handle.value.trim().replace(/^@/, ''))}/roles/${role.value}`);
      await rolesPage();
      return `Granted ${role.value} to @${handle.value.trim().replace(/^@/, '')}.`;
    });
  });
  view('Roles', staffNav(), el('p', {className: 'hint', text: 'Roles take effect on the account’s next request. The last admin cannot be removed.'}), form,
       el('ul', {className: 'list'}, ...staff.map(s => el('li', {className: 'card'},
         el('span', {className: 'who'}, el('strong', {text: s.handle ? '@' + s.handle : '(no handle)'}), el('br'),
            el('small', {text: s.roles.join(', ')})),
         ...s.roles.map(r => button(`Revoke ${r}`, b => act(b, async () => {
           await api.call('DELETE', `/admin/staff/${s.handle}/roles/${r}`);
           await rolesPage();
           return `Revoked ${r} from @${s.handle}.`;
         }), 'danger'))))));
}


// ------------------------------------------------------------------ moderation (complete-wearhouse-tdd)
type Reported = {id: string; caption: string | null; owner: {handle: string | null} | null; moderation?: string;
                 reports: number; reasons: string[]; look: {look_name: string} | null};

export async function moderationPage() {
  const api = ctx.api();
  const q = await api.call<{items: Reported[]}>('GET', '/admin/moderation/reports');
  const act1 = (s: Reported, action: 'hide' | 'restore' | 'dismiss', label: string) => button(label, b => act(b, async () => {
    const reason = prompt(`Reason to ${action}:`) ?? '';
    await api.call('POST', `/admin/moderation/shares/${s.id}`, {body: {action, reason}});
    await moderationPage();
    return `Share ${action === 'dismiss' ? 'reports dismissed' : action === 'hide' ? 'hidden' : 'restored'}.`;
  }), action === 'hide' ? 'danger' : '');
  view('Moderation', staffNav(),
       el('p', {className: 'hint', text: 'Reported shared looks. Moderators can hide, restore or dismiss; every action is audited. No access to keys, orders or wardrobes.'}),
       el('ul', {className: 'list', ariaLabel: 'Reported shares'}, ...q.items.map(s => el('li', {className: 'card'},
         el('span', {className: 'who'}, el('strong', {text: s.look?.look_name ?? 'Look'}),
            s.owner?.handle ? ` by @${s.owner.handle}` : '', el('br'),
            el('small', {text: `${s.reports} report(s): ${s.reasons.join(' · ')} · state ${s.moderation ?? 'visible'}`})),
         act1(s, 'hide', 'Hide'), act1(s, 'restore', 'Restore'), act1(s, 'dismiss', 'Dismiss reports')))),
       q.items.length ? '' : el('p', {text: 'No open reports.'}));
}
