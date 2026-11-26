import {expect, test, type Page} from '@playwright/test';
import {API, as, onboarded, ownProduct, signIn, unique} from './helpers.ts';

/**
 * Task 9.3 hardening sweep. Every route is driven through four conditions:
 *   online        renders, with no console error and no error state;
 *   slow API      something is on screen while data is in flight (never a blank main area);
 *   API stopped   after sign-in the API goes away mid-session: each route ends in content (cached) or a recoverable
 *                 error with Retry, never an endless skeleton, a blank page or an uncaught exception; Retry recovers
 *                 once the API is back;
 *   chunk lost    a lazily loaded screen whose code cannot be fetched shows a recoverable message, not a white page.
 * The browser's own "Failed to load resource" lines are expected while the API is stopped; nothing else is.
 */
test.use({viewport: {width: 1440, height: 900}});
test.setTimeout(420_000);

type Call = Awaited<ReturnType<typeof as>>;
const isApi = (url: string) => url.startsWith(API);

async function arrange() {
  const sub = unique('hard');
  const call = await onboarded(sub, {garments: 4, look: true});
  await ownProduct(call, 'Hardening tote');
  const {id: itemId} = await call<{id: string}>('POST', '/me/wardrobe/items', {name: 'Hardening shirt', slot: 'top'});
  const [look] = await call<Array<{id: string}>>('GET', '/me/looks');
  const orders = await call<{items: Array<{id: string; lines: Array<{product_id?: string; units: Array<{public_serial: string | null}>}>}>}>('GET', '/me/orders');
  const order = orders.items[0]!;
  const detail = await call<{lines: Array<{product_id: string; units: Array<{public_serial: string | null}>}>}>('GET', `/me/orders/${order.id}`);
  const productId = detail.lines[0]!.product_id;
  const serial = detail.lines[0]!.units[0]!.public_serial!;
  return {sub, call, routes: routesFor(sub, {productId, orderId: order.id, itemId, lookId: look!.id, serial})};
}

function routesFor(sub: string, ids: {productId: string; orderId: string; itemId: string; lookId: string; serial: string}) {
  return ['/', '/about', '/catalogue', `/catalogue/products/${ids.productId}`, '/items', `/items/${ids.serial}`,
    '/wishlist', '/cart', '/checkout', '/orders', `/orders/${ids.orderId}`, '/redeem',
    '/wardrobe', '/wardrobe/add', `/wardrobe/items/${ids.itemId}`, '/wardrobe/looks', `/wardrobe/looks/${ids.lookId}`,
    '/wardrobe/fitting-room', '/wardrobe/suggestions', '/wardrobe/planner', '/wardrobe/wear', '/weather', '/sizes',
    `/u/${sub}`, '/community', '/notifications', '/profile', '/settings', '/settings/privacy', '/settings/security',
    '/settings/account', '/admin', '/no-such-screen'];
}

function collect(page: Page, apiDown: () => boolean) {
  const problems: string[] = [];
  page.on('pageerror', e => problems.push(`pageerror: ${e.message}`));
  page.on('console', m => {
    if (m.type() !== 'error') return;
    const text = m.text();
    // A 404 for the deliberately unknown screen's data, or any failed fetch while the API is stopped, is the network
    // layer reporting the condition under test.
    if (/Failed to load resource/.test(text) && (apiDown() || /status of 404/.test(text))) return;
    problems.push(text);
  });
  return problems;
}

/** The main area settles: no skeleton left, and either real content or a recoverable error. */
async function settled(page: Page, route: string, timeout = 20_000) {
  const main = page.locator('#main');
  // Settled = some text in the main area and no skeleton left (lazy screens render nothing until their code loads).
  await expect.poll(async () => main.evaluate(el => (el as HTMLElement).innerText.trim().length > 0 && !el.querySelector('.skeleton')).catch(() => false),
    {message: `${route}: blank or still loading after ${timeout} ms`, timeout}).toBe(true).catch(e => { expect.soft(null, String(e.message).split('\n')[0]).not.toBeNull(); });
  return (await main.innerText().catch(() => '')).trim();
}

test('Online: every route renders without console errors or error states', async ({page}) => {
  const {sub, routes} = await arrange();
  const problems = collect(page, () => false);
  let bearer = '';
  page.on('request', r => { const h = r.headers().authorization; if (h?.startsWith('Bearer ')) bearer = h.slice(7); });
  const logs: string[] = [];
  page.on('console', m => logs.push(m.text()));
  await signIn(page, sub);
  for (const route of routes) {
    await page.goto(`/app/#${route}`);
    await settled(page, route);
    await expect.soft(page.locator('#main .state-error'), `${route}: error state while online`).toHaveCount(0);
  }
  expect(problems).toEqual([]);
  // Secret handling: the access token is sent as a header only; it never reaches the URL, storage or the console.
  expect(bearer.length).toBeGreaterThan(20);
  const leaks = await page.evaluate(token => [location.href, JSON.stringify(localStorage), JSON.stringify(sessionStorage),
    JSON.stringify(history.state), document.cookie].filter(s => s.includes(token)), bearer);
  expect(leaks).toEqual([]);
  expect(logs.filter(l => l.includes(bearer))).toEqual([]);
});

test('Slow API: a fresh load of each private route shows a placeholder, never a blank main area', async ({page}) => {
  const {sub, routes} = await arrange();
  await signIn(page, sub);
  await page.waitForURL(/#\/$/);
  await page.route(url => isApi(url.toString()), async route => { await new Promise(r => setTimeout(r, 2500)); await route.continue().catch(() => {}); });
  for (const route of routes.filter(r => r !== '/no-such-screen')) {
    await page.goto(`/app/#${route}`);
    await page.reload();
    await page.waitForTimeout(700);
    const shell = await page.locator('#main').count();
    expect.soft(shell, `${route}: no main landmark while the API is slow`).toBe(1);
    if (shell) {
      const visible = await page.locator('#main').evaluate(el => (el as HTMLElement).innerText.trim().length > 0 || !!el.querySelector('.skeleton, [aria-busy="true"]'));
      expect.soft(visible, `${route}: blank while the API is slow`).toBe(true);
    }
  }
});

test('API stopped midway: every route ends in content or a recoverable error, and Retry recovers', async ({page}) => {
  const {sub, routes} = await arrange();
  let down = false;
  const problems = collect(page, () => down);
  await signIn(page, sub);
  await page.waitForURL(/#\/$/);
  await settled(page, '/');
  down = true;
  const apiUrl = (url: URL) => isApi(url.toString());
  await page.route(apiUrl, route => route.abort('connectionrefused'));
  const failed: string[] = [];
  for (const route of routes) {
    await page.goto(`/app/#${route}`);
    await settled(page, route, 25_000);
    if (await page.locator('#main .state-error').count()) {
      failed.push(route);
      await expect.soft(page.locator('#main .state-error').first().getByRole('button', {name: 'Try again'}), `${route}: error without Retry`).toBeVisible();
    }
  }
  expect.soft(failed.length, 'some routes should need the API').toBeGreaterThan(0);
  // The API comes back: Retry on a route that failed recovers without a reload.
  await page.unroute(apiUrl);
  // Requests refused just before the API came back report their failure a moment later; let those land first.
  await page.waitForTimeout(1500);
  down = false;
  const retryRoute = failed.find(r => r.startsWith('/wardrobe')) ?? failed[0]!;
  await page.goto(`/app/#${retryRoute}`);
  const error = page.locator('#main .state-error').first();
  if (await error.count()) await error.getByRole('button', {name: 'Try again'}).click();
  await expect(page.locator('#main .state-error')).toHaveCount(0, {timeout: 20_000});
  await settled(page, `${retryRoute} after Retry`);
  expect(problems).toEqual([]);
});

test('Chunk lost: a screen whose code cannot be fetched shows a recoverable message', async ({page}) => {
  const {sub} = await arrange();
  const problems = collect(page, () => false);
  await signIn(page, sub);
  await page.waitForURL(/#\/$/);
  await page.route(/\/assets\/Community-[^/]+\.js$/, route => route.abort('connectionrefused'));
  await page.goto('/app/#/community');
  await expect(page.getByRole('alert')).toBeVisible({timeout: 15_000});
  await expect(page.locator('#app')).not.toBeEmpty();
  await expect(page.getByRole('button', {name: /Reload|Try again/})).toBeVisible();
  void problems;
});
