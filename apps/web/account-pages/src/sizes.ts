/**
 * TEMPORARY size pages (add-wearhouse-sizes 4.1): "My sizes", store size filter options, the staff size registry and
 * the per-product sizes panel. Size systems and sizes are API data (never hardcoded here). Plain DOM, no polish.
 */
import type {ProductSizes, SizeRegistry, UsualSizes} from '@wearhouse/contracts';

import type {ApiClient} from './api.ts';
import {act, button, el, field, select, view} from './ui.ts';

type Ctx = {api: () => ApiClient; signedIn: () => boolean};
let ctx: Ctx;
let registry: Promise<SizeRegistry> | null = null;

export function initSizes(c: Ctx) {
  ctx = c;
}

/** The public registry, fetched once per page load (staff edits call `forgetRegistry`). */
export function sizeRegistry(): Promise<SizeRegistry> {
  registry ??= ctx.api().call<SizeRegistry>('GET', '/catalogue/sizes', {anonymous: true});
  return registry;
}

export function forgetRegistry() {
  registry = null;
}

/** `system:code` options grouped by system label, for filters ("Letter (international) M"). */
export async function sizeOptions(any: string): Promise<Array<[string, string]>> {
  const r = await sizeRegistry();
  return [['', any], ...r.systems.flatMap(s => s.sizes.map(z => [`${s.code}:${z.code}`, `${s.label} ${z.label}`] as [string, string]))];
}

/** The signed-in user's usual size per system (`{alpha: 'M'}`), or {} when signed out. */
export async function usualSizes(): Promise<Record<string, string>> {
  if (!ctx.signedIn()) return {};
  const u = await ctx.api().call<UsualSizes>('GET', '/me/sizes');
  return Object.fromEntries(u.systems.filter(s => s.usual).map(s => [s.system, s.usual!.code]));
}

// ------------------------------------------------------------------ My sizes
export async function usualSizesPage() {
  const api = ctx.api();
  const [reg, mine] = await Promise.all([sizeRegistry(), api.call<UsualSizes>('GET', '/me/sizes')]);
  const current = Object.fromEntries(mine.systems.map(s => [s.system, s.usual?.code ?? '']));
  const pickers = reg.systems.map(s => {
    const pick = select(`usual-${s.code}`, [['', 'Not set'], ...s.sizes.map(z => [z.code, z.label] as [string, string])],
                        current[s.code] ?? '');
    pick.id = `usual-${s.code}`;
    return {system: s.code, node: field(s.label, pick), pick};
  });
  const form = el('form', {}, ...pickers.map(p => p.node),
                  el('p', {className: 'hint', text: 'Used for "In my size" in the store and to size your recommendations. Only you see them.'}),
                  el('button', {type: 'submit', text: 'Save my sizes', className: 'primary'}));
  form.addEventListener('submit', e => {
    e.preventDefault();
    act(form.querySelector('button'), async () => {
      await api.call('PUT', '/me/sizes', {body: {usual: Object.fromEntries(pickers.map(p => [p.system, p.pick.value || null]))}});
      return 'Your sizes are saved.';
    });
  });
  view('My sizes', form);
}

// ------------------------------------------------------------------ staff: registry
export async function staffSizesPage(staffNav: HTMLElement) {
  const api = ctx.api();
  const reg = await api.call<SizeRegistry>('GET', '/admin/catalogue/sizes');
  const reload = async () => { forgetRegistry(); await staffSizesPage(staffNav); };
  const systems = reg.systems.map(s => {
    const code = el('input', {name: 'size_code', maxLength: 8, required: true, placeholder: 'e.g. 4XL'});
    const rank = el('input', {name: 'rank', type: 'number', min: '1', max: '100000', required: true,
                              value: String((s.sizes.at(-1)?.rank ?? 0) + 10)});
    code.id = `size-code-${s.code}`; rank.id = `size-rank-${s.code}`;
    const add = el('form', {className: 'inline'}, field('New size code', code), field('Rank (order)', rank),
                   el('button', {type: 'submit', text: `Add size to ${s.label}`}));
    add.addEventListener('submit', e => {
      e.preventDefault();
      act(add.querySelector('button'), async () => {
        await api.call('PUT', `/admin/catalogue/size-systems/${s.code}/sizes/${encodeURIComponent(code.value.trim())}`,
                       {body: {label: code.value.trim(), rank: Number(rank.value)}});
        await reload();
        return `Added ${code.value.trim()}.`;
      });
    });
    return el('section', {},
      el('h2', {text: `${s.label} (${s.code})${s.active === false ? ' · retired' : ''}`}),
      el('p', {className: 'hint', text: s.slots.length ? `Default for: ${s.slots.join(', ')}` : 'Not a default for any slot.'}),
      el('ul', {className: 'list'}, ...s.sizes.map(z => el('li', {className: 'card'},
        el('span', {className: 'who', text: `${z.label} · rank ${z.rank}${z.common ? ' · common' : ''}${z.active === false ? ' · retired' : ''}`}),
        button(z.active === false ? 'Restore' : 'Retire', b => act(b, async () => {
          await api.call('PUT', `/admin/catalogue/size-systems/${s.code}/sizes/${encodeURIComponent(z.code)}`,
                         {body: {label: z.label, rank: z.rank, common: z.common, active: z.active === false}});
          await reload();
          return `${z.label} ${z.active === false ? 'restored' : 'retired'}.`;
        }))))),
      add);
  });
  const assign = button('Assign sizes to unsized products', b => act(b, async () => {
    let total = 0;
    for (;;) {
      const r = await api.call<{assigned: number; more_remaining: boolean}>('POST', '/admin/catalogue/sizes/assign-missing');
      total += r.assigned;
      if (!r.more_remaining || !r.assigned) break;
    }
    return `Assigned mock sizes to ${total} product(s).`;
  }), 'primary');
  view('Sizes', staffNav,
       el('p', {className: 'hint', text: 'The source catalogue has no sizes: product sizes are mock data from these rules or set by staff. Re-save offers after changing a product\'s sizes.'}),
       assign, ...systems);
}

// ------------------------------------------------------------------ staff: one product's sizes
export async function productSizesPanel(productId: string, reload: () => Promise<void>): Promise<HTMLElement> {
  const api = ctx.api();
  const [reg, current] = await Promise.all([sizeRegistry(),
    api.call<ProductSizes>('GET', `/admin/catalogue/products/${encodeURIComponent(productId)}/sizes`)]);
  const system = select('size_system', reg.systems.map(s => [s.code, s.label] as [string, string]),
                        current.sizes[0]?.system ?? reg.systems[0]?.code ?? '');
  system.id = 'product-size-system';
  const codes = el('input', {name: 'size_codes', id: 'product-size-codes', value: current.sizes.map(s => s.code).join(' '),
                             placeholder: 'e.g. S M L'});
  const form = el('form', {}, field('Size system', system), field('Sizes (codes, space separated)', codes),
                  el('button', {type: 'submit', text: 'Save sizes', className: 'primary'}),
                  button('Make one size', b => act(b, async () => {
                    await api.call('PUT', `/admin/catalogue/products/${productId}/sizes`, {body: {sizes: []}});
                    await reload();
                    return 'Now one size.';
                  })));
  form.addEventListener('submit', e => {
    e.preventDefault();
    act(form.querySelector('button'), async () => {
      await api.call('PUT', `/admin/catalogue/products/${productId}/sizes`, {body: {
        sizes: codes.value.split(/\s+/).filter(Boolean).map(code => ({system: system.value, code}))}});
      await reload();
      return 'Sizes saved. Re-save the offer so each size gets stock.';
    });
  });
  return el('section', {}, el('h2', {text: 'Sizes'}),
            el('p', {text: current.one_size ? 'One size.' : current.sizes.map(s => `${s.label}${s.origin === 'rule' ? '*' : ''}`).join(', ')}),
            current.sizes.some(s => s.origin === 'rule') ? el('p', {className: 'hint', text: '* generated by the size rule (mock data).'}) : '',
            form);
}
