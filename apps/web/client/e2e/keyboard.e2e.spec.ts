import {expect, test, type Locator, type Page} from '@playwright/test';
import {API, as, onboarded, signIn, unique} from './helpers.ts';

/**
 * web-quality "Keyboard-only purchase and redeem": after sign-in, the shopper never touches the mouse. Each step
 * presses Tab until focus lands on the named control (proving it is reachable in the tab order) and activates it
 * with Enter (proving it is operable from the keyboard). No click() is used for any shopper step.
 */
test.use({viewport: {width: 1440, height: 900}});
test.setTimeout(120_000);

/** Tab forward until `target` holds focus (at most `limit` presses), then press Enter. */
async function tabToAndPress(page: Page, target: Locator, limit = 150) {
  await expect(target).toBeVisible();
  for (let i = 0; i < limit; i++) {
    if (await target.evaluate(el => el === document.activeElement)) {
      await expect(target).toBeFocused();
      await page.keyboard.press('Enter');
      return;
    }
    await page.keyboard.press('Tab');
  }
  throw new Error(`Not reachable with Tab within ${limit} presses: ${target}`);
}

test('Keyboard-only purchase and redeem: browse, add to cart, check out, reveal the key and redeem it', async ({page}) => {
  // Arrange (not under test): a published one-size product with a simulated offer, and a signed-in shopper.
  const run = unique('kbd');
  await fetch(`${API}/__e2e/grant?sub=cur${run}&role=admin`, {method: 'POST'});
  const curator = await as(`cur${run}`);
  await curator('GET', '/me');
  const name = `Keyboard scarf ${run}`;
  const {product_id} = await curator<{product_id: string}>('POST', '/admin/source-products', {
    source: {namespace: 'wearhouse-e2e', name: 'Wearhouse e2e fixtures', url: 'https://wearhouse.invalid/e2e'},
    snapshot: {sha256: '06a15714b84fef5c12fb5c99fd7ac58bfc06142eb427dc8e68e38d733233aa28', file_name: 'e2e.json', acquired_on: '2026-11-26'},
    permission: {basis: 'synthetic-test-fixture', scope: 'tests only', accepted_on: '2026-11-26', accepted_by: 'e2e', terms_url: 'https://wearhouse.invalid/e2e/terms'},
    external_id: run, original_fields: {article_id: run, prod_name: name, product_type_name: 'Scarf'},
    facts: {product_name: {value: name, source_field: 'prod_name'}, category: {value: 'Scarf', source_field: 'product_type_name'}},
  });
  const staff = await curator<{revisions: Array<{id: string}>}>('GET', `/admin/catalogue/products/${product_id}`);
  await curator('POST', `/admin/catalogue/products/${product_id}/publish`, {revision_id: staff.revisions.at(-1)!.id});
  await curator('PUT', `/admin/commerce/offers/${product_id}`, {price_idr: 89000, stock: 5});
  const sub = unique('kb');
  await onboarded(sub);
  await signIn(page, sub);
  await page.goto(`/app/#/catalogue?q=${encodeURIComponent(name)}`);
  await page.locator('body').focus();

  // Browse: reach the product tile and open it.
  await tabToAndPress(page, page.getByRole('link', {name: new RegExp(name)}).first());
  await expect(page.getByRole('heading', {level: 1, name})).toBeVisible();

  // Add to cart.
  await tabToAndPress(page, page.getByRole('button', {name: 'Add to cart'}));
  await expect(page.getByText('Added to your cart')).toBeVisible();

  // Open the cart from the top bar, review and place the simulated order.
  await tabToAndPress(page, page.getByRole('button', {name: /^Cart/}));
  await expect(page).toHaveURL(/#\/cart/);
  await tabToAndPress(page, page.getByRole('button', {name: 'Review order'}));
  await expect(page).toHaveURL(/#\/checkout/);
  await tabToAndPress(page, page.getByRole('button', {name: 'Place simulated order'}));
  await expect(page.getByRole('heading', {name: 'Receipt'})).toBeVisible();

  // Reveal the key, show it, and go to Redeem with it.
  await tabToAndPress(page, page.getByRole('button', {name: 'Reveal key'}));
  await tabToAndPress(page, page.getByRole('button', {name: 'Show', exact: true}));
  const key = (await page.locator('.unit-key').innerText()).trim();
  expect(key).toMatch(/^[A-Z2-7]{4}(-[A-Z2-7]{4}){3}$/);
  await tabToAndPress(page, page.getByRole('button', {name: 'Redeem now'}));
  await expect(page.locator('.redeem-input')).toHaveValue(key);

  // Redeem it.
  await tabToAndPress(page, page.getByRole('button', {name: 'Redeem', exact: true}));
  await expect(page.getByRole('heading', {name: new RegExp(`${name} is now in your wardrobe`)})).toBeVisible();
});
