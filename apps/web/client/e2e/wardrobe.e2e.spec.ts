import {expect, test} from '@playwright/test';
import {API, as, onboarded, signIn, unique} from './helpers.ts';

test.use({viewport: {width: 1440, height: 900}});
type Call = Awaited<ReturnType<typeof as>>;
const declare = (call: Call, name: string, slot: string) => call<{id: string}>('POST', '/me/wardrobe/items', {name, slot});
const today = () => new Intl.DateTimeFormat('en-CA', {timeZone: 'Asia/Jakarta'}).format(new Date());

test('Default view from settings: wardrobe_view list opens the library in list view', async ({page}) => {
  const sub = unique('view');
  const call = await onboarded(sub, {garments: 3});
  const s = await call<{version: number}>('GET', '/me/settings');
  await call('PATCH', '/me/settings', {version: s.version, values: {wardrobe_view: 'list'}});
  await signIn(page, sub);
  await page.goto('/app/#/wardrobe');
  await expect(page.locator('[data-view="list"]')).toBeVisible();
  await expect(page.locator('.wr-row')).toHaveCount(3);
  await expect(page.locator('.wr-status')).toContainText('3 of 3 shown');
});

test('Declared item appears: marked declared, with no serial', async ({page}) => {
  const sub = unique('decl');
  await onboarded(sub);
  await signIn(page, sub);
  await page.goto('/app/#/wardrobe/add');
  await page.getByLabel('Name').fill('Thrifted denim jacket');
  await page.getByLabel('Slot').selectOption('outer');
  await page.getByRole('button', {name: 'Add to wardrobe'}).click();
  await expect(page.getByRole('heading', {level: 1, name: 'Thrifted denim jacket'})).toBeVisible();
  await expect(page.getByText('Outerwear · Declared')).toBeVisible();
  await expect(page.getByText('Serial')).toHaveCount(0);
  await page.goto('/app/#/wardrobe');
  await expect(page.getByRole('link', {name: /Thrifted denim jacket/})).toBeVisible();
});

test('Oversized photo shows the server error', async ({page}) => {
  const sub = unique('photo');
  const call = await onboarded(sub);
  const {id} = await declare(call, 'Big photo shirt', 'top');
  await signIn(page, sub);
  await page.goto(`/app/#/wardrobe/items/${id}`);
  const big = Buffer.alloc(2.5 * 1024 * 1024, 1);
  big.write('\x89PNG\r\n\x1a\n', 0, 'binary');
  await page.locator('input[type=file]').setInputFiles({name: 'big.png', mimeType: 'image/png', buffer: big});
  await expect(page.locator('.inspector-photo [role=alert]')).toContainText('larger than 2 MB');
});

test('Shelves: create and reorder with the keyboard', async ({page}) => {
  const sub = unique('shelf');
  const call = await onboarded(sub);
  const a = await declare(call, 'Alpha tee', 'top');
  const b = await declare(call, 'Beta tee', 'top');
  const shelf = await call<{id: string}>('POST', '/me/wardrobe/shelves', {name: 'Campus', item_ids: [a.id, b.id]});
  await signIn(page, sub);
  await page.goto('/app/#/wardrobe');
  await page.getByRole('button', {name: 'Manage shelf: Campus'}).click();
  const first = page.locator('.shelf-item').first();
  await expect(first).toHaveText('Alpha tee');
  await first.focus();
  await page.keyboard.press('Alt+ArrowDown');
  await expect(page.locator('.shelf-item').first()).toHaveText('Beta tee');
  await page.getByRole('button', {name: 'Save'}).click();
  await expect.poll(async () => (await call<Array<{id: string; item_ids: string[]}>>('GET', '/me/wardrobe/shelves')).find(s => s.id === shelf.id)?.item_ids).toEqual([b.id, a.id]);
});

test('Dress conflict preview, and two wrist items fit', async ({page}) => {
  const sub = unique('dress');
  const call = await onboarded(sub);
  for (const [n, s] of [['Linen top', 'top'], ['Wide trousers', 'bottom'], ['Slip dress', 'dress'], ['Watch', 'wrist'], ['Bangle', 'wrist']] as const) await declare(call, n, s);
  await signIn(page, sub);
  await page.goto('/app/#/wardrobe/fitting-room');
  const closet = page.locator('.fit-closet');
  await closet.getByRole('button', {name: /Linen top/}).click();
  await closet.getByRole('button', {name: /Wide trousers/}).click();
  await closet.getByRole('button', {name: /Slip dress/}).click();
  const dialog = page.getByRole('dialog', {name: 'Equipping this removes:'});
  await expect(dialog).toContainText('Linen top');
  await expect(dialog).toContainText('Wide trousers');
  await dialog.getByRole('button', {name: 'Keep current'}).click();
  await expect(page.locator('.fit-figure')).toContainText('Linen top');
  await closet.getByRole('button', {name: /Slip dress/}).click();
  await page.getByRole('dialog', {name: 'Equipping this removes:'}).getByRole('button', {name: 'Equip and remove'}).click();
  await expect(page.locator('.fit-figure')).toContainText('Slip dress');
  await expect(page.locator('.fit-figure')).not.toContainText('Linen top');
  await closet.getByRole('button', {name: /Watch/}).click();
  await closet.getByRole('button', {name: /Bangle/}).click();
  await expect(page.getByRole('dialog', {name: 'Equipping this removes:'})).toHaveCount(0);
  await expect(page.locator('.fit-wrist')).toContainText('2/2');
});

test('Revision history: saving a changed look adds a revision and keeps the previous one viewable', async ({page}) => {
  const sub = unique('rev');
  const call = await onboarded(sub, {garments: 3, look: true});
  const [look] = await call<Array<{id: string}>>('GET', '/me/looks');
  await signIn(page, sub);
  await page.goto(`/app/#/wardrobe/fitting-room?look=${look!.id}`);
  await page.locator('.fit-figure').getByRole('button', {name: /Take off/}).first().click();
  await page.getByRole('button', {name: 'Save new revision'}).click();
  await expect(page.getByText('Revision 2').first()).toBeVisible();
  await page.locator('.look-history').getByRole('button', {name: /Revision 1/}).click();
  await expect(page.getByText('Viewing revision 1 (read-only)')).toBeVisible();
  await expect(page.locator('.look-piece')).toHaveCount(3);
});

test('Suggestions: one displayed event per run, nothing on hover, ALREADY_CHOSEN explained', async ({page}) => {
  const sub = unique('sugg');
  await onboarded(sub, {garments: 9});
  await signIn(page, sub);
  const gets: string[] = []; const events: string[] = [];
  page.on('request', r => {
    if (r.url().includes('/recommendations/outfits') && r.method() === 'GET') gets.push(r.url());
    if (r.url().includes('/events') && r.method() === 'POST') events.push(r.postData() ?? '');
  });
  await page.goto('/app/#/wardrobe/suggestions');
  await expect(page.locator('.suggest-card').first()).toBeVisible();
  for (let i = 0; i < 3; i++) { await page.mouse.wheel(0, 600); await page.mouse.wheel(0, -600); }
  await page.locator('.suggest-card').first().hover();
  await page.waitForTimeout(800);
  expect(gets).toHaveLength(1);
  expect(events.filter(e => e.includes('displayed'))).toHaveLength(1);
  // Another client already chose from this run: the app explains instead of failing.
  await page.route('**/recommendations/outfits/*/events', route => route.request().postData()?.includes('chosen')
    ? route.fulfill({status: 409, contentType: 'application/json', headers: {'Access-Control-Allow-Origin': new URL(page.url()).origin},
      body: JSON.stringify({code: 'ALREADY_CHOSEN', message: 'Already chosen.', field_errors: [], request_id: 'e2e'})}) : route.continue());
  await page.locator('.suggest-card').first().getByRole('button', {name: 'Try on'}).click();
  await expect(page.getByText('You already picked an outfit from this set.')).toBeVisible();
});

test('Planned is not worn: marking worn keeps the plan, undoing the wear keeps it too', async ({page}) => {
  const sub = unique('plan');
  const call = await onboarded(sub, {garments: 3, look: true});
  const [look] = await call<Array<{current: {id: string}}>>('GET', '/me/looks');
  await call('PUT', `/me/planner/${today()}`, {look_revision_id: look!.current.id, occasion: 'casual'});
  await signIn(page, sub);
  await page.goto('/app/#/wardrobe/planner');
  const day = page.locator('.plan-day.is-today');
  await day.getByRole('button', {name: 'Mark worn'}).click();
  await expect(day.locator('.plan-worn')).toContainText('Worn');
  await expect(day.locator('.plan-look-name')).toBeVisible();
  await day.getByRole('button', {name: 'Undo'}).click();
  await expect(day.locator('.plan-worn')).toHaveCount(0);
  await expect(day.locator('.plan-look-name')).toBeVisible();
});

test('Beyond-horizon day cannot be planned', async ({page}) => {
  const sub = unique('far');
  await onboarded(sub, {garments: 3, look: true});
  await signIn(page, sub);
  const from = new Intl.DateTimeFormat('en-CA', {timeZone: 'Asia/Jakarta'}).format(new Date(Date.now() + 28 * 86400000));
  await page.goto(`/app/#/wardrobe/planner?from=${from}`);
  await expect(page.locator('.plan-day').last()).toContainText('You can plan up to 30 days ahead.');
  await expect(page.locator('.plan-day').last().getByRole('button', {name: /Plan a look|Replace/})).toHaveCount(0);
});

test('Phone planner: a date strip and one day at a time', async ({page}) => {
  await page.setViewportSize({width: 390, height: 844});
  const sub = unique('phone');
  await onboarded(sub, {garments: 3, look: true});
  await signIn(page, sub);
  await page.goto('/app/#/wardrobe/planner');
  await expect(page.locator('.plan-strip')).toBeVisible();
  await expect(page.locator('.plan-day:visible')).toHaveCount(1);
  await page.locator('.plan-chip').nth(2).click();
  await expect(page.locator('.plan-day:visible')).toHaveCount(1);
  await expect(page.locator('.plan-chip').nth(2)).toHaveAttribute('aria-pressed', 'true');
});

test('No location: weather prompts for a location instead of erroring', async ({page}) => {
  const sub = unique('wx');
  await onboarded(sub);
  await signIn(page, sub);
  await page.goto('/app/#/weather');
  await expect(page.getByText('Set your location to see the forecast')).toBeVisible();
  await page.getByLabel('BMKG location code (adm4)').fill('3171');
  await page.getByRole('button', {name: 'Save location'}).click();
  await expect(page.getByText('Use the format 12.34.56.7890.')).toBeVisible();
});

test('Unknown slot needs override before the item can be equipped', async ({page}) => {
  const run = unique('u');
  await fetch(`${API}/__e2e/grant?sub=cur${run}&role=admin`, {method: 'POST'});
  const curator = await as(`cur${run}`);
  await curator('GET', '/me');
  const id = `${run}-mystery`;
  const {product_id} = await curator<{product_id: string}>('POST', '/admin/source-products', {
    source: {namespace: 'wearhouse-e2e', name: 'Wearhouse e2e fixtures', url: 'https://wearhouse.invalid/e2e'},
    snapshot: {sha256: '06a15714b84fef5c12fb5c99fd7ac58bfc06142eb427dc8e68e38d733233aa28', file_name: 'e2e.json', acquired_on: '2026-11-26'},
    permission: {basis: 'synthetic-test-fixture', scope: 'tests only', accepted_on: '2026-11-26', accepted_by: 'e2e', terms_url: 'https://wearhouse.invalid/e2e/terms'},
    external_id: id, original_fields: {article_id: id, prod_name: 'Mystery piece', product_type_name: 'Unknown', colour_group_name: 'Grey'},
    facts: {product_name: {value: 'Mystery piece', source_field: 'prod_name'}, category: {value: 'Unknown', source_field: 'product_type_name'}},
  });
  const staff = await curator<{revisions: Array<{id: string}>}>('GET', `/admin/catalogue/products/${product_id}`);
  await curator('POST', `/admin/catalogue/products/${product_id}/publish`, {revision_id: staff.revisions.at(-1)!.id});
  await curator('PUT', `/admin/commerce/offers/${product_id}`, {price_idr: 50000, stock: 3});
  const sub = unique('mystery');
  const call = await onboarded(sub);
  await call('PUT', `/me/cart/${product_id}`, {quantity: 1, size: null});
  const cart = await call<{total_idr: number}>('GET', '/me/cart');
  const order = await call<{id: string; lines: Array<{units: Array<{unit_id: string}>}>}>('POST', '/me/checkout', {expected_total_idr: cart.total_idr}, `e2e-${unique('co')}`);
  const key = await call<{activation_key: string}>('GET', `/me/orders/${order.id}/units/${order.lines[0]!.units[0]!.unit_id}/key`);
  const owned = await call<{id: string}>('POST', '/redemptions', {activation_key: key.activation_key}, `e2e-${unique('rd')}`);
  await signIn(page, sub);
  await page.goto(`/app/#/wardrobe/items/${owned.id}`);
  await expect(page.getByText('We don’t know which slot this goes in.', {exact: false})).toBeVisible();
  await expect(page.getByRole('button', {name: 'Try on'})).toBeDisabled();
  await expect(page.getByText('Provenance')).toBeVisible();
  await page.getByLabel('Slot override').selectOption('accessory');
  await expect(page.getByRole('button', {name: 'Try on'})).toBeEnabled();
});
