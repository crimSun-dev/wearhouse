import {expect, test, type Page} from '@playwright/test';
import {API, as, onboarded, signIn, unique} from './helpers.ts';

test.use({viewport: {width: 1440, height: 900}});

type Call = Awaited<ReturnType<typeof as>>;
const run = unique('s');
let curator: Call;

/** Publishes a synthetic one-size product with a simulated offer. Not H&M data. */
async function product(name: string, category: string, colour: string, offer: {price: number; stock: number} | null) {
  const id = `${run}-${name.replace(/\W+/g, '').toLowerCase()}`;
  const {product_id} = await curator<{product_id: string}>('POST', '/admin/source-products', {
    source: {namespace: 'wearhouse-e2e', name: 'Wearhouse e2e fixtures', url: 'https://wearhouse.invalid/e2e'},
    snapshot: {sha256: '06a15714b84fef5c12fb5c99fd7ac58bfc06142eb427dc8e68e38d733233aa28', file_name: 'e2e.json', acquired_on: '2026-11-26'},
    permission: {basis: 'synthetic-test-fixture', scope: 'tests only', accepted_on: '2026-11-26', accepted_by: 'e2e', terms_url: 'https://wearhouse.invalid/e2e/terms'},
    external_id: id, original_fields: {article_id: id, prod_name: name, product_type_name: category, colour_group_name: colour},
    facts: {product_name: {value: name, source_field: 'prod_name'}, category: {value: category, source_field: 'product_type_name'},
      colour: {value: colour, source_field: 'colour_group_name'}},
    annotations: {slot: {value: 'accessory', origin: 'rule', note: 'e2e fixture'}},
  });
  const staff = await curator<{revisions: Array<{id: string}>}>('GET', `/admin/catalogue/products/${product_id}`);
  await curator('POST', `/admin/catalogue/products/${product_id}/publish`, {revision_id: staff.revisions.at(-1)!.id});
  if (offer) await curator('PUT', `/admin/commerce/offers/${product_id}`, {price_idr: offer.price, stock: offer.stock});
  return product_id;
}

async function buy(call: Call, productId: string) {
  await call('PUT', `/me/cart/${productId}`, {quantity: 1, size: null});
  const cart = await call<{total_idr: number}>('GET', '/me/cart');
  return call<{id: string; lines: Array<{units: Array<{unit_id: string; public_serial: string | null}>}>}>(
    'POST', '/me/checkout', {expected_total_idr: cart.total_idr}, `e2e-${unique('co')}`);
}

const shopper = async (page: Page, name: string) => { const sub = unique(name); const call = await onboarded(sub); await signIn(page, sub); return {sub, call}; };

test.beforeAll(async () => {
  await fetch(`${API}/__e2e/grant?sub=curator${run}&role=admin`, {method: 'POST'});
  curator = await as(`curator${run}`);
  await curator('GET', '/me');
});

test('Filter restore: category and colour survive opening a product and coming back', async ({page}) => {
  const category = `Scarf${run}`;
  await product('Silk scarf', category, 'Red', {price: 99000, stock: 5});
  await product('Wool scarf', category, 'Grey', {price: 129000, stock: 5});
  await page.goto('/app/#/catalogue?all=1');
  await page.getByLabel('Category').selectOption(category);
  await page.getByLabel('Colour').selectOption('Red');
  await expect(page.locator('.store-grid .tile')).toHaveCount(1);
  const url = page.url();
  await page.getByRole('link', {name: /Silk scarf/}).click();
  await expect(page.getByRole('heading', {level: 1, name: 'Silk scarf'})).toBeVisible();
  await page.getByRole('button', {name: 'Back'}).click();
  await expect(page).toHaveURL(url);
  await expect(page.getByLabel('Category')).toHaveValue(category);
  await expect(page.getByLabel('Colour')).toHaveValue('Red');
  await expect(page.locator('.store-grid .tile')).toHaveCount(1);
});

test('Out of stock: add-to-cart unavailable with a reason, wishlisting still works', async ({page}) => {
  const id = await product('Sold-out tote', `Tote${run}`, 'Beige', {price: 249000, stock: 0});
  await shopper(page, 'oos');
  await page.goto(`/app/#/catalogue/products/${id}`);
  await expect(page.getByRole('button', {name: 'Add to cart'})).toBeDisabled();
  await expect(page.getByText('Out of stock. You can still save it to your wishlist.')).toBeVisible();
  await page.getByRole('button', {name: 'Save to wishlist'}).click();
  await expect(page.getByRole('button', {name: 'Remove from wishlist'})).toBeVisible();
});

test('Scanning does not claim: opening a tag sends no redemption and leaves the wardrobe unchanged', async ({page}) => {
  const id = await product('Tagged cap', `Cap${run}`, 'Navy', {price: 89000, stock: 5});
  const buyer = await onboarded(unique('tagbuyer'));
  const order = await buy(buyer, id);
  const serial = order.lines[0]!.units[0]!.public_serial!;
  const {call} = await shopper(page, 'scan');
  const redemptions: string[] = [];
  page.on('request', r => { if (r.url().includes('/redemptions')) redemptions.push(r.url()); });
  await page.goto('/app/#/items');
  await page.getByLabel('Tag link or serial').fill(`https://crimsun-dev.github.io/wearhouse/app/#/items/${serial}`);
  await page.getByRole('button', {name: 'Open tag'}).click();
  await expect(page.getByRole('heading', {name: 'Tagged cap'})).toBeVisible();
  await expect(page.getByText('Scanning it never makes you the owner.', {exact: false})).toBeVisible();
  expect(redemptions).toEqual([]);
  expect((await call<{items: unknown[]}>('GET', '/me/items')).items).toHaveLength(0);
});

test('Sized product: choosing a size and adding to cart puts that size in the cart', async ({page}) => {
  const id = await product('Sized linen shirt', `Shirt${run}`, 'White', null);
  await curator('PUT', `/admin/catalogue/products/${id}/sizes`, {sizes: [{system: 'alpha', code: 'S'}, {system: 'alpha', code: 'M'}]});
  await curator('PUT', `/admin/commerce/offers/${id}`, {price_idr: 199000, stock: 10, size_stock: {S: 0, M: 5}});
  await shopper(page, 'sized');
  await page.goto(`/app/#/catalogue/products/${id}`);
  await expect(page.getByRole('button', {name: 'S (out of stock)'})).toBeDisabled();
  await expect(page.getByRole('button', {name: 'Choose a size first'})).toBeDisabled();
  await page.getByRole('button', {name: 'M', exact: true}).click();
  await page.getByRole('button', {name: 'Add to cart'}).click();
  await expect(page.getByText('Added to your cart')).toBeVisible();
  await page.goto('/app/#/cart');
  await expect(page.getByText('Size M')).toBeVisible();
  await page.getByRole('button', {name: 'Remove'}).click();
  await expect(page.getByText('Your cart is empty')).toBeVisible();
});

test('Unavailable line: a retired product is flagged and checkout readiness follows the server', async ({page}) => {
  const id = await product('Retiring belt', `Belt${run}`, 'Brown', {price: 159000, stock: 5});
  const {call} = await shopper(page, 'retire');
  await call('PUT', `/me/cart/${id}`, {quantity: 1, size: null});
  await curator('POST', `/admin/catalogue/products/${id}/retire`);
  await page.goto('/app/#/cart');
  await expect(page.getByText('No longer available. Remove it to check out.')).toBeVisible();
  await expect(page.getByRole('button', {name: 'Review order'})).toBeDisabled();
});

test('Price changed: the new total is shown and the order needs a second confirmation', async ({page}) => {
  const id = await product('Repriced hat', `Hat${run}`, 'Black', {price: 100000, stock: 5});
  const {call} = await shopper(page, 'price');
  await call('PUT', `/me/cart/${id}`, {quantity: 1, size: null});
  await page.goto('/app/#/checkout');
  await expect(page.getByText('Rp 100.000', {exact: false}).first()).toBeVisible();
  await curator('PUT', `/admin/commerce/offers/${id}`, {price_idr: 120000, stock: 5});
  await page.getByRole('button', {name: 'Place simulated order'}).click();
  await expect(page.getByRole('alert')).toContainText('a price changed');
  await expect(page.getByText('Rp 120.000', {exact: false}).first()).toBeVisible();
  expect((await call<{items: unknown[]}>('GET', '/me/orders')).items).toHaveLength(0);
  await page.getByRole('button', {name: 'Place simulated order'}).click();
  await expect(page.getByRole('heading', {name: 'Receipt'})).toBeVisible();
});

test('Retry after a lost response: exactly one order exists', async ({page}) => {
  const id = await product('Lost-response gloves', `Gloves${run}`, 'Black', {price: 75000, stock: 5});
  const {call} = await shopper(page, 'lost');
  await call('PUT', `/me/cart/${id}`, {quantity: 1, size: null});
  let first = true;
  await page.route('**/api/v2/me/checkout', async route => {
    if (!first) return route.continue();
    first = false;
    await route.fetch();          // the server places the order...
    await route.abort('timedout'); // ...but the browser never hears back
  });
  await page.goto('/app/#/checkout');
  await page.getByRole('button', {name: 'Place simulated order'}).click();
  await expect(page.getByText('Placing it again is safe', {exact: false})).toBeVisible();
  await page.getByRole('button', {name: 'Place simulated order'}).click();
  await expect(page.getByRole('heading', {name: 'Receipt'})).toBeVisible();
  expect((await call<{items: unknown[]}>('GET', '/me/orders')).items).toHaveLength(1);
});

test('Keys: reveal, redeem, claimed unit links to the item, and the key never lands in URL, storage or console', async ({page, browser}) => {
  const id = await product('Key-test beanie', `Beanie${run}`, 'Green', {price: 69000, stock: 5});
  const {call} = await shopper(page, 'keys');
  const order = await buy(call, id);
  const logs: string[] = [];
  page.on('console', m => logs.push(m.text()));
  await page.goto(`/app/#/orders/${order.id}`);
  await page.getByRole('button', {name: 'Reveal key'}).click();
  const code = page.locator('.unit-key');
  await expect(code).toContainText('•');
  await page.getByRole('button', {name: 'Show', exact: true}).click();
  const key = (await code.innerText()).trim();
  expect(key).toMatch(/^[A-Z2-7]{4}(-[A-Z2-7]{4}){3}$/);
  await page.getByRole('button', {name: 'Redeem now'}).click();
  await expect(page.locator('.redeem-input')).toHaveValue(key);
  await page.getByRole('button', {name: 'Redeem', exact: true}).click();
  await expect(page.getByRole('heading', {name: /is now in your wardrobe/})).toBeVisible();
  const leaks = await page.evaluate(k => [location.href, JSON.stringify(localStorage), JSON.stringify(sessionStorage), JSON.stringify(history.state)]
    .filter(s => s.includes(k) || s.includes(k.replace(/-/g, ''))), key);
  expect(leaks).toEqual([]);
  expect(logs.filter(l => l.includes(key))).toEqual([]);
  await page.goto(`/app/#/orders/${order.id}`);
  await expect(page.getByText('Redeemed')).toBeVisible();
  await expect(page.getByRole('button', {name: 'Reveal key'})).toHaveCount(0);
  await expect(page.getByRole('link', {name: 'View item'})).toBeVisible();

  // Second redemption rejected: another user gets the same generic message as a mistyped key.
  const other = unique('thief');
  await onboarded(other);
  const context = await browser.newContext({baseURL: test.info().project.use.baseURL, viewport: {width: 1440, height: 900}});
  const thief = await context.newPage();
  await signIn(thief, other);
  await thief.goto('/app/#/redeem');
  await thief.locator('.redeem-input').fill(key.toLowerCase().replace(/-/g, ' '));
  await expect(thief.locator('.redeem-input')).toHaveValue(key);
  await thief.getByRole('button', {name: 'Redeem', exact: true}).click();
  const generic = 'That key can’t be redeemed. Check it and try again.';
  await expect(thief.locator('#redeem-msg')).toHaveText(generic);
  await thief.locator('.redeem-input').fill('AAAA-BBBB-CCCC-DDDD');
  await thief.getByRole('button', {name: 'Redeem', exact: true}).click();
  await expect(thief.locator('#redeem-msg')).toHaveText(generic);
  await context.close();
});

test('Rate limit countdown on redemption', async ({page}) => {
  await shopper(page, 'limit');
  await page.route('**/api/v2/redemptions', route => route.fulfill({status: 429, headers: {'Retry-After': '3', 'Content-Type': 'application/json',
      'Access-Control-Allow-Origin': new URL(page.url()).origin, 'Access-Control-Expose-Headers': 'Retry-After'},
    body: JSON.stringify({code: 'RATE_LIMITED', message: 'Too many requests.', field_errors: [], request_id: 'e2e'})}));
  await page.goto('/app/#/redeem');
  await page.locator('.redeem-input').fill('AAAABBBBCCCCDDDD');
  await page.getByRole('button', {name: 'Redeem', exact: true}).click();
  await expect(page.locator('#redeem-msg')).toContainText(/Try again in [23] s/);
  await expect(page.getByRole('button', {name: 'Redeem', exact: true})).toBeDisabled();
  await expect(page.getByRole('button', {name: 'Redeem', exact: true})).toBeEnabled({timeout: 6000});
});
