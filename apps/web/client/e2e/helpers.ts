import type {Page} from '@playwright/test';

export const API = 'http://127.0.0.1:' + (process.env.E2E_API_PORT || '8199');

/** Direct API access as a harness subject, for arranging data the test is not about. */
export async function as(sub: string) {
  const {token} = await (await fetch(`${API}/__e2e/token?sub=${sub}`)).json() as {token: string};
  return async <T = unknown>(method: string, path: string, body?: unknown, idem?: string): Promise<T> => {
    const res = await fetch(`${API}/api/v2${path}`, {method, body: body === undefined ? undefined : JSON.stringify(body),
      headers: {Authorization: `Bearer ${token}`, 'Content-Type': 'application/json', ...(idem ? {'Idempotency-Key': idem} : {})}});
    const text = await res.text();
    if (!res.ok) throw new Error(`${method} ${path} -> ${res.status} ${text}`);
    return (text ? JSON.parse(text) : undefined) as T;
  };
}

/** An onboarded user, optionally with declared garments and a look. */
export async function onboarded(sub: string, opts: {garments?: number; look?: boolean} = {}) {
  const call = await as(sub);
  await call('GET', '/me');
  await call('PATCH', '/me/profile', {handle: sub, display_name: `Test ${sub}`, avatar: {kind: 'preset', preset: 'plum'}});
  const slots = ['top', 'bottom', 'footwear', 'outer', 'bag', 'scarf', 'headwear', 'top', 'bottom', 'footwear'];
  const ids: string[] = [];
  for (let i = 0; i < (opts.garments ?? 0); i++) {
    ids.push((await call<{id: string}>('POST', '/me/wardrobe/items', {name: `${sub} piece ${i + 1}`, slot: slots[i % slots.length]})).id);
  }
  if (opts.look && ids.length >= 3) {
    await call('POST', '/me/looks', {name: `${sub} campus look`, slots: {top: [ids[0]], bottom: [ids[1]], footwear: [ids[2]]}});
  }
  return call;
}

export async function signIn(page: Page, sub: string) {
  await page.goto(`/app/?e2e_sub=${sub}#/signin`);
  await page.getByRole('button', {name: 'Continue with Google'}).click();
}

/** Unique subjects per test run, so reruns against one harness never collide. */
export const unique = (name: string) => `${name}${Date.now().toString(36).slice(-5)}`;

/** Publishes a synthetic product (not H&M data) and has `call`'s user buy and redeem one: a verified owned item. */
export async function ownProduct(call: Awaited<ReturnType<typeof as>>, name = 'Owned test piece') {
  const run = unique('own');
  await fetch(`${API}/__e2e/grant?sub=cur${run}&role=admin`, {method: 'POST'});
  const curator = await as(`cur${run}`);
  await curator('GET', '/me');
  const id = `${run}-owned`;
  const {product_id} = await curator<{product_id: string}>('POST', '/admin/source-products', {
    source: {namespace: 'wearhouse-e2e', name: 'Wearhouse e2e fixtures', url: 'https://wearhouse.invalid/e2e'},
    snapshot: {sha256: '06a15714b84fef5c12fb5c99fd7ac58bfc06142eb427dc8e68e38d733233aa28', file_name: 'e2e.json', acquired_on: '2026-11-26'},
    permission: {basis: 'synthetic-test-fixture', scope: 'tests only', accepted_on: '2026-11-26', accepted_by: 'e2e', terms_url: 'https://wearhouse.invalid/e2e/terms'},
    external_id: id, original_fields: {article_id: id, prod_name: name, product_type_name: 'Bag', colour_group_name: 'Black'},
    facts: {product_name: {value: name, source_field: 'prod_name'}, category: {value: 'Bag', source_field: 'product_type_name'}},
    annotations: {slot: {value: 'accessory', origin: 'rule', note: 'e2e fixture'}},
  });
  const staff = await curator<{revisions: Array<{id: string}>}>('GET', `/admin/catalogue/products/${product_id}`);
  await curator('POST', `/admin/catalogue/products/${product_id}/publish`, {revision_id: staff.revisions.at(-1)!.id});
  await curator('PUT', `/admin/commerce/offers/${product_id}`, {price_idr: 50000, stock: 5});
  await call('PUT', `/me/cart/${product_id}`, {quantity: 1, size: null});
  const cart = await call<{total_idr: number}>('GET', '/me/cart');
  const order = await call<{id: string; lines: Array<{units: Array<{unit_id: string}>}>}>('POST', '/me/checkout', {expected_total_idr: cart.total_idr}, `e2e-${unique('co')}`);
  const key = await call<{activation_key: string}>('GET', `/me/orders/${order.id}/units/${order.lines[0]!.units[0]!.unit_id}/key`);
  return call<{id: string}>('POST', '/redemptions', {activation_key: key.activation_key}, `e2e-${unique('rd')}`);
}
