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
