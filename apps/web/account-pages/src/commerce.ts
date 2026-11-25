/**
 * TEMPORARY sandbox commerce pages (add-wearhouse-sandbox-commerce 5.2). No real payment ever happens: every price is
 * labelled sandbox. Keys are revealed only on an explicit "Show key" click (each reveal is audited server-side).
 */
import type {Cart, OrdersPage, PublicOffer, Receipt, StaffOffer, UnitKey, Wishlist} from '@wearhouse/contracts';

import {ApiFailure, newIdempotencyKey, type ApiClient} from './api.ts';
import {usualSizes} from './sizes.ts';
import {act, button, el, field, select, view} from './ui.ts';

type Ctx = {api: () => ApiClient; signedIn: () => boolean};
let ctx: Ctx;

export function initCommerce(c: Ctx) {
  ctx = c;
}

const rupiah = new Intl.NumberFormat('id-ID', {style: 'currency', currency: 'IDR', maximumFractionDigits: 0});
export const idr = (n: number | null | undefined) => (n === null || n === undefined ? '—' : rupiah.format(n));
const SANDBOX = 'Sandbox price (no real payment)';

// ------------------------------------------------------------------ product page box
export async function offerBox(productId: string): Promise<HTMLElement> {
  const box = el('section', {className: 'offer', ariaLabel: 'Buy'});
  let offer: PublicOffer | null = null;
  try {
    offer = await ctx.api().call<PublicOffer>('GET', `/commerce/products/${productId}/offer`, {anonymous: true});
  } catch (err) {
    if (!(err instanceof ApiFailure && err.status === 404)) throw err;
  }
  box.append(offer
    ? el('p', {}, el('strong', {text: idr(offer.price_idr)}), ` · ${SANDBOX} · ${offer.in_stock ? 'In stock' : 'Out of stock'}`)
    : el('p', {text: 'Not on sale in the sandbox shop.'}));
  if (!ctx.signedIn()) {
    box.append(el('p', {className: 'hint'}, el('a', {href: '#/', text: 'Sign in'}), ' to use the wishlist and cart.'));
    return box;
  }
  box.append(button('Add to wishlist', b => act(b, async () => {
    await ctx.api().call('PUT', `/me/wishlist/${productId}`);
    return 'Added to your wishlist.';
  })));
  if (offer?.in_stock) {
    let picker: HTMLSelectElement | null = null;
    if (offer.sizes.length) {
      const usual = await usualSizes();
      const options = offer.sizes.map(s => [s.code, s.in_stock ? s.label : `${s.label} (sold out)`] as [string, string]);
      const preferred = offer.sizes.find(s => s.in_stock && usual[s.system] === s.code) ?? offer.sizes.find(s => s.in_stock);
      picker = select('size', options, preferred?.code ?? '');
      picker.id = 'buy-size';
      for (const opt of Array.from(picker.options)) opt.disabled = !offer.sizes.find(s => s.code === opt.value)?.in_stock;
      box.append(field('Size', picker));
    }
    box.append(button('Add to cart', b => act(b, async () => {
      const size = picker?.value || undefined;
      const cart = await ctx.api().call<Cart>('GET', '/me/cart');
      const current = cart.lines.find(l => l.product_id === productId && (l.size?.code ?? undefined) === size)?.quantity ?? 0;
      await ctx.api().call('PUT', `/me/cart/${productId}`, {body: {quantity: Math.min(current + 1, 5), ...(size ? {size} : {})}});
      return size ? `Added size ${size} to your cart.` : 'Added to your cart.';
    }), 'primary'));
  }
  return box;
}

// ------------------------------------------------------------------ wishlist / cart
export async function wishlistPage() {
  const w = await ctx.api().call<Wishlist>('GET', '/me/wishlist');
  view(`Wishlist (${w.items.length})`,
       el('ul', {className: 'list'}, ...w.items.map(i => el('li', {className: 'card'},
         el('span', {className: 'who'}, i.available ? el('a', {href: `#/store/product/${i.product_id}`, text: i.name ?? i.product_id})
           : el('span', {text: `${i.name ?? i.product_id} (no longer available)`}),
            el('br'), el('small', {text: i.offer ? `${idr(i.offer.price_idr)} · sandbox` : 'Not on sale'})),
         button('Remove', b => act(b, async () => {
           await ctx.api().call('DELETE', `/me/wishlist/${i.product_id}`);
           await wishlistPage();
           return 'Removed from your wishlist.';
         }))))),
       w.items.length ? '' : el('p', {text: 'Your wishlist is empty. Browse the Store to add products.'}));
}

export async function cartPage() {
  const c = await ctx.api().call<Cart>('GET', '/me/cart');
  const lines = c.lines.map(l => {
    const sizeBody = l.size ? {size: l.size.code} : {};
    const named = `${l.name ?? l.product_id}${l.size ? ` (size ${l.size.label})` : ''}`;
    const qty = el('select', {id: `qty-${l.product_id}-${l.size?.code ?? 'os'}`, ariaLabel: `Quantity of ${named}`});
    for (let i = 1; i <= 5; i++) qty.append(el('option', {value: String(i), text: String(i)}));
    qty.value = String(l.quantity);
    qty.addEventListener('change', () => act(null, async () => {
      await ctx.api().call('PUT', `/me/cart/${l.product_id}`, {body: {quantity: Number(qty.value), ...sizeBody}});
      await cartPage();
      return 'Cart updated.';
    }));
    return el('li', {className: 'card'},
      el('span', {className: 'who'}, el('a', {href: `#/store/product/${l.product_id}`, text: named}),
         el('br'), el('small', {text: `${idr(l.unit_price_idr)} each · ${idr(l.line_total_idr)}${l.available ? '' : ' · not available in this quantity'}`})),
      qty,
      button('Remove', b => act(b, async () => {
        await ctx.api().call('DELETE', `/me/cart/${l.product_id}`, {query: l.size ? {size: l.size.code} : {}});
        await cartPage();
        return 'Removed from your cart.';
      })));
  });
  const pay = button(`Check out (${idr(c.total_idr)}, sandbox)`, b => act(b, async () => {
    const receipt = await ctx.api().call<Receipt>('POST', '/me/checkout',
                                                    {body: {expected_total_idr: c.total_idr}, idem: newIdempotencyKey()});
    location.hash = `#/orders/${receipt.id}`;
    return 'Order placed (sandbox, nothing was charged).';
  }), 'primary');
  pay.disabled = !c.checkout_ready;
  view('Cart', el('p', {className: 'hint', text: `${SANDBOX}. Checkout issues real garment units with private keys for you.`}),
       el('ul', {className: 'list'}, ...lines),
       c.lines.length ? el('p', {}, el('strong', {text: `Total: ${idr(c.total_idr)}`})) : el('p', {text: 'Your cart is empty.'}),
       c.lines.length ? pay : '');
}

// ------------------------------------------------------------------ orders / receipt
export async function ordersPage(parts: string[]) {
  if (parts[0]) return receiptPage(parts[0]);
  const page = await ctx.api().call<OrdersPage>('GET', '/me/orders', {query: {limit: '50'}});
  view('Orders',
       el('ul', {className: 'list'}, ...page.items.map(o => el('li', {className: 'card'},
         el('span', {className: 'who'}, el('a', {href: `#/orders/${o.id}`, text: o.names.join(', ') || o.id}),
            el('br'), el('small', {text: `${new Date(o.created_at).toLocaleString()} · ${o.item_count} item(s) · ${idr(o.total_idr)} · ${o.status} · sandbox`}))))),
       page.items.length ? '' : el('p', {text: 'No orders yet.'}));
}

async function receiptPage(id: string) {
  const api = ctx.api();
  const r = await api.call<Receipt>('GET', `/me/orders/${encodeURIComponent(id)}`);
  const unitRow = (u: Receipt['lines'][number]['units'][number]) => {
    const out = el('span', {className: 'key'});
    const actions: HTMLElement[] = [];
    if (u.state === 'issued' && u.delivery.status === 'available') {
      actions.push(button('Show key', b => act(b, async () => {
        const k = await api.call<UnitKey>('GET', `/me/orders/${r.id}/units/${u.unit_id}/key`);
        out.replaceChildren(el('code', {text: k.activation_key ?? `(${k.status})`}));
        if (k.activation_key) {
          out.append(' ', button('Claim into my wardrobe', b2 => act(b2, async () => {
            await api.call('POST', '/redemptions', {body: {activation_key: k.activation_key}, idem: newIdempotencyKey()});
            await receiptPage(id);
            return 'Claimed: it is now in your wardrobe.';
          }), 'primary'));
        }
        return 'Key shown. Keep it private.';
      })));
    }
    if (u.state === 'issued' && r.status === 'fulfilled') {
      actions.push(button('Get a new key', b => act(b, async () => {
        await api.call('POST', `/me/orders/${r.id}/units/${u.unit_id}/renew-key`, {idem: newIdempotencyKey()});
        await receiptPage(id);
        return 'New key issued; the old key no longer works.';
      })));
    }
    const status = u.state === 'claimed' ? 'claimed (in your wardrobe)' : u.state === 'retired' ? 'cancelled'
      : `key ${u.delivery.status}`;
    return el('li', {className: 'card'}, el('span', {className: 'who'}, el('code', {text: u.public_serial ?? u.unit_id}),
              el('br'), el('small', {text: status}), el('br'), out), ...actions);
  };
  view(`Order ${r.id.slice(0, 8)}`,
       el('p', {text: `${r.status} · ${new Date(r.created_at).toLocaleString()} · total ${idr(r.total_idr)} · ${r.payment_ref} (sandbox, nothing charged)`}),
       ...r.lines.map(l => el('section', {},
         el('h2', {text: `${l.product_name}${l.size ? ` (size ${l.size.label})` : ''} × ${l.quantity} · ${idr(l.line_total_idr)}`}),
         el('ul', {className: 'list'}, ...l.units.map(unitRow)))),
       r.cancellable ? el('p', {}, button('Cancel order', b => act(b, async () => {
         await api.call('POST', `/me/orders/${r.id}/cancel`);
         await receiptPage(id);
         return 'Order cancelled: keys revoked, claimed garments revoked (sandbox) and stock restored.';
       }), 'danger'), el('small', {className: 'hint', text: ' Cancelling also removes any garment you already claimed from this order (sandbox only).'}))
         : el('p', {className: 'hint', text: 'This order was cancelled.'}),
       el('p', {}, el('a', {href: '#/orders', text: '← All orders'})));
}

// ------------------------------------------------------------------ staff offers
export async function staffOffersPage(staffNav: HTMLElement) {
  const api = ctx.api();
  const offers = await api.call<StaffOffer[]>('GET', '/admin/commerce/offers');
  const pid = el('input', {name: 'product_id', required: true, placeholder: 'product id'});
  const price = el('input', {name: 'price_idr', type: 'number', min: '1', max: '100000000', required: true});
  const stock = el('input', {name: 'stock', type: 'number', min: '0', max: '100000', required: true, value: '10'});
  const form = el('form', {}, field('Product id', pid), field('Sandbox price (IDR)', price), field('Sandbox stock', stock),
                  el('button', {type: 'submit', text: 'Save offer', className: 'primary'}));
  form.addEventListener('submit', e => {
    e.preventDefault();
    act(form.querySelector('button'), async () => {
      await api.call('PUT', `/admin/commerce/offers/${encodeURIComponent(pid.value.trim())}`,
                     {body: {price_idr: Number(price.value), stock: Number(stock.value)}});
      await staffOffersPage(staffNav);
      return 'Offer saved.';
    });
  });
  const cat = el('input', {name: 'bulk_category', placeholder: 'e.g. Trousers', maxLength: 100});
  const slot = el('input', {name: 'bulk_slot', placeholder: 'e.g. top', maxLength: 32});
  const bprice = el('input', {name: 'bulk_price', type: 'number', min: '1', max: '100000000', required: true});
  const bstock = el('input', {name: 'bulk_stock', type: 'number', min: '0', max: '100000', required: true, value: '20'});
  const overwrite = el('input', {type: 'checkbox', name: 'overwrite'});
  overwrite.id = 'bulk-overwrite';
  const bulk = el('form', {}, el('h2', {text: 'Bulk rule'}), field('Category', cat), field('Slot', slot),
                  field('Sandbox price (IDR) for every match', bprice), field('Sandbox stock for every match (per size)', bstock),
                  el('label', {className: 'check', htmlFor: 'bulk-overwrite'}, overwrite, ' Overwrite existing offers'),
                  el('button', {type: 'submit', text: 'Apply rule', className: 'primary'}));
  bulk.addEventListener('submit', e => {
    e.preventDefault();
    act(bulk.querySelector('button'), async () => {
      const r = await api.call<{results: Array<{matched: number; written: number; sized: number}>}>('POST', '/admin/commerce/offers/bulk', {body: {
        rules: [{category: cat.value || null, slot: slot.value || null, price_idr: Number(bprice.value), stock: Number(bstock.value)}],
        overwrite: overwrite.checked}});
      return `Rule applied: ${r.results[0].matched} matched, ${r.results[0].written} offer(s) written (${r.results[0].sized} with stock per size).`;
    });
  });
  view('Sandbox offers', staffNav, el('p', {className: 'hint', text: 'Mock prices and stock for the sandbox shop. Nothing is ever charged.'}),
       form, bulk,
       el('ul', {className: 'list'}, ...offers.map(o => el('li', {className: 'card'},
         el('span', {className: 'who'}, el('strong', {text: o.name ?? o.product_id}), el('br'),
            el('small', {text: `${idr(o.price_idr)} · stock ${o.stock}${o.sizes.length ? ` (${o.sizes.map(s => `${s.label}:${s.stock}`).join(' ')})` : ''} · ${o.on_sale ? 'on sale' : 'not published'} · ${o.product_id}`})),
         button('Edit', () => { pid.value = o.product_id; price.value = String(o.price_idr); stock.value = String(o.stock); pid.focus(); }),
         button('Withdraw', b => act(b, async () => {
           await api.call('DELETE', `/admin/commerce/offers/${o.product_id}`);
           await staffOffersPage(staffNav);
           return 'Offer withdrawn.';
         }), 'danger')))));
}
