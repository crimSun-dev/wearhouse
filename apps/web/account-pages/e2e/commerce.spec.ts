// add-wearhouse-sandbox-commerce 5.2: offer -> add to cart -> checkout -> receipt -> show key -> claim (real local v2 API).
// The product is a SYNTHETIC row in the H&M articles.csv column format; the price is a sandbox value.
import {expect, test, type Browser, type Page} from '@playwright/test';

const HARNESS = 'http://127.0.0.1:8199';

async function signIn(browser: Browser, sub: string): Promise<Page> {
  const page = await (await browser.newContext()).newPage();
  await page.goto(`/?e2e_sub=${sub}#/`);
  await page.getByRole('button', {name: 'Sign in with Google'}).click();
  await page.getByLabel('Choose your handle').fill(sub);
  await page.getByRole('button', {name: 'Save handle'}).click();
  await expect(page.getByRole('heading', {name: 'Your profile'})).toBeVisible();
  return page;
}

test('sandbox purchase ends with the garment claimed into the wardrobe', async ({browser}) => {
  const tag = Math.random().toString(36).slice(2, 7);
  const editor = await signIn(browser, `ed_${tag}`);
  expect((await editor.request.post(`${HARNESS}/__e2e/grant?sub=ed_${tag}&role=catalogue_editor`)).ok()).toBeTruthy();
  await editor.reload();
  await editor.goto('/#/staff/import');
  await editor.getByLabel('Basis').fill('synthetic-test-fixture');
  await editor.getByLabel('Scope').fill('automated tests only');
  await editor.getByLabel('Accepted by').fill('wearhouse e2e');
  await editor.getByLabel('Terms URL').fill('https://wearhouse.invalid/terms');
  await editor.getByLabel('CSV text').fill(['article_id,prod_name,product_type_name,product_group_name,colour_group_name',
    `08${tag}01,Sage ${tag} cardigan,Cardigan,Garment Upper body,Green`].join('\n'));
  await editor.getByRole('button', {name: 'Run import'}).click();
  await expect(editor.getByRole('status')).toHaveText('Import finished: 1 created, 0 rejected.');
  await editor.getByRole('link', {name: new RegExp(`Row 1 \\(08${tag}01\\): created`)}).click();
  await editor.getByRole('button', {name: 'Publish revision 1'}).click();
  await expect(editor.getByRole('status')).toHaveText('Published revision 1.');
  const productId = (await editor.locator('main code').first().textContent())!.trim();

  await editor.goto('/#/staff/offers');
  await editor.getByLabel('Product id').fill(productId);
  await editor.getByLabel('Sandbox price (IDR)', {exact: true}).fill('175000');
  await editor.getByLabel('Sandbox stock', {exact: true}).fill('3');
  await editor.getByRole('button', {name: 'Save offer'}).click();
  await expect(editor.getByRole('status')).toHaveText('Offer saved.');

  const buyer = await signIn(browser, `bu_${tag}`);
  await buyer.goto('/#/store');
  await expect(buyer.getByRole('heading', {name: 'Recommended for you'})).toBeVisible();
  await expect(buyer.getByText(/Ranked by baseline: sandbox-order-popularity/)).toBeVisible();  // declared mode
  await buyer.goto(`/#/store/product/${productId}`);
  await expect(buyer.getByText('Sandbox price (no real payment)')).toBeVisible();
  await buyer.getByRole('button', {name: 'Add to wishlist'}).click();
  await expect(buyer.getByRole('status')).toHaveText('Added to your wishlist.');
  await buyer.getByRole('button', {name: 'Add to cart'}).click();
  await expect(buyer.getByRole('status')).toHaveText('Added to your cart.');

  await buyer.goto('/#/wishlist');
  await expect(buyer.getByRole('link', {name: `Sage ${tag} cardigan`})).toBeVisible();
  await buyer.goto('/#/cart');
  await buyer.getByRole('button', {name: /Check out/}).click();
  await expect(buyer.getByRole('status')).toHaveText('Order placed (sandbox, nothing was charged).');
  await expect(buyer.getByRole('heading', {name: /^Order /})).toBeVisible();
  await expect(buyer.getByText('key available')).toBeVisible();
  await expect(buyer.locator('main code').filter({hasText: /^[A-Z2-7]{4}-/})).toHaveCount(0);  // no key until asked

  await buyer.getByRole('button', {name: 'Show key'}).click();
  await expect(buyer.getByRole('status')).toHaveText('Key shown. Keep it private.');
  await buyer.getByRole('button', {name: 'Claim into my wardrobe'}).click();
  await expect(buyer.getByRole('status')).toHaveText('Claimed: it is now in your wardrobe.');
  await expect(buyer.getByText('claimed (in your wardrobe)')).toBeVisible();
  await expect(buyer.getByText(/Cancelling also removes any garment you already claimed/)).toBeVisible();  // sandbox revocation

  await buyer.goto('/#/orders');
  await expect(buyer.getByRole('link', {name: `Sage ${tag} cardigan`})).toBeVisible();
});
