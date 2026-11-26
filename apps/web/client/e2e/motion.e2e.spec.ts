import {expect, test} from '@playwright/test';
import {API, as, unique} from './helpers.ts';

test.use({viewport: {width: 1440, height: 900}});
type Call = Awaited<ReturnType<typeof as>>;
let curator: Call;
const run = unique('mo');

async function product(i: number, category: string) {
  const id = `${run}-${category}-${i}`;
  const {product_id} = await curator<{product_id: string}>('POST', '/admin/source-products', {
    source: {namespace: 'wearhouse-e2e', name: 'e2e', url: 'https://wearhouse.invalid/e2e'},
    snapshot: {sha256: '06a15714b84fef5c12fb5c99fd7ac58bfc06142eb427dc8e68e38d733233aa28', file_name: 'e2e.json', acquired_on: '2026-11-26'},
    permission: {basis: 'synthetic-test-fixture', scope: 'tests only', accepted_on: '2026-11-26', accepted_by: 'e2e', terms_url: 'https://wearhouse.invalid/e2e/terms'},
    external_id: id, original_fields: {article_id: id, prod_name: `${category} piece ${String(i).padStart(2, '0')}`, product_type_name: category},
    facts: {product_name: {value: `${category} piece ${String(i).padStart(2, '0')}`, source_field: 'prod_name'}, category: {value: category, source_field: 'product_type_name'}},
  });
  const staff = await curator<{revisions: Array<{id: string}>}>('GET', `/admin/catalogue/products/${product_id}`);
  await curator('POST', `/admin/catalogue/products/${product_id}/publish`, {revision_id: staff.revisions.at(-1)!.id});
}
const grid = `Grid${run}`;

test.beforeAll(async () => {
  await fetch(`${API}/__e2e/grant?sub=cur${run}&role=admin`, {method: 'POST'});
  curator = await as(`cur${run}`);
  await curator('GET', '/me');
  for (let i = 1; i <= 45; i++) await product(i, grid);
  for (let i = 1; i <= 2; i++) { await product(i, `Alpha${run}`); await product(i, `Beta${run}`); }
});

test('Back restores position: the 40th product, then Back, returns to the same place with that tile focused', async ({page}) => {
  await page.goto(`/app/#/catalogue?category=${grid}&sort=name`);
  const tiles = page.locator('.store-grid .tile');
  await expect(tiles).toHaveCount(24);
  await page.getByRole('button', {name: 'Load more'}).click();
  await expect(tiles).toHaveCount(45);
  const fortieth = tiles.nth(39);
  await fortieth.scrollIntoViewIfNeeded();
  const before = await page.evaluate(() => scrollY);
  await fortieth.click();
  await expect(page.getByRole('heading', {level: 1, name: `${grid} piece 40`})).toBeVisible();
  await page.goBack();
  await expect(tiles).toHaveCount(45);
  await expect(tiles.nth(39)).toBeFocused();
  expect(Math.abs((await page.evaluate(() => scrollY)) - before)).toBeLessThan(120);
});

test('Navigation not blocked: Back during the tile transition navigates at once', async ({page}) => {
  await page.goto(`/app/#/catalogue?category=${grid}&sort=name`);
  await page.locator('.store-grid .tile').first().click();
  await page.waitForURL(/catalogue\/products\//);   // the tile's 420 ms morph is still running here
  await page.goBack();
  await expect(page).toHaveURL(new RegExp(`catalogue\\?category=${grid}`), {timeout: 1500});
  await expect(page.locator('.product-hero')).toHaveCount(0);
});

test('The tile-to-detail transition plays forward and reverses on Back', async ({page}) => {
  await page.addInitScript(() => {
    const w = window as unknown as {__vt: number};
    w.__vt = 0;
    const real = document.startViewTransition?.bind(document);
    if (real) (document as unknown as {startViewTransition: typeof real}).startViewTransition = ((cb: never) => { w.__vt++; return real(cb); }) as typeof real;
  });
  await page.goto(`/app/#/catalogue?category=${grid}&sort=name`);
  const count = () => page.evaluate(() => (window as unknown as {__vt: number}).__vt);
  await page.locator('.store-grid .tile').first().click();
  await expect(page.locator('.product-hero')).toBeVisible();
  expect(await count()).toBe(1);
  await expect(page.locator('.product-hero')).toHaveCSS('view-transition-name', 'product-hero');
  await page.getByRole('button', {name: 'Back'}).first().click();
  await expect(page).toHaveURL(new RegExp(`catalogue\\?category=${grid}`));
  expect(await count()).toBe(2);
});

test('Out-of-order response dropped: a late answer for an old filter never replaces the current results', async ({page}) => {
  let delayed = false;
  await page.route(`**/api/v2/catalogue/products?*category=Alpha${run}*`, async route => {
    if (!delayed) { delayed = true; await new Promise(r => setTimeout(r, 2500)); }
    await route.continue();
  });
  await page.goto('/app/#/catalogue?all=1');
  await page.getByLabel('Category').selectOption(`Alpha${run}`);
  await page.getByLabel('Category').selectOption(`Beta${run}`);
  await expect(page.locator('.store-grid .tile')).toHaveCount(2);
  await expect(page.locator('.store-grid')).toContainText(`Beta${run} piece`);
  await page.waitForTimeout(3000);
  await expect(page.locator('.store-grid')).not.toContainText(`Alpha${run} piece`);
  await expect(page.locator('.store-grid')).toContainText(`Beta${run} piece`);
});
