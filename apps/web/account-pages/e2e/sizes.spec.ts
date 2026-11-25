// add-wearhouse-sizes 4.1: staff set sizes -> per-size offer -> a shopper sets "My sizes", filters "In my size",
// buys in her size -> the receipt and the wardrobe keep the size, sorted by size. Synthetic H&M-format row.
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

test('shop in my size and keep the size in the wardrobe', async ({browser}) => {
  const tag = Math.random().toString(36).slice(2, 7);
  const editor = await signIn(browser, `sz_${tag}`);
  expect((await editor.request.post(`${HARNESS}/__e2e/grant?sub=sz_${tag}&role=catalogue_editor`)).ok()).toBeTruthy();
  await editor.reload();
  await editor.goto('/#/staff/import');
  await editor.getByLabel('Basis').fill('synthetic-test-fixture');
  await editor.getByLabel('Scope').fill('automated tests only');
  await editor.getByLabel('Accepted by').fill('wearhouse e2e');
  await editor.getByLabel('Terms URL').fill('https://wearhouse.invalid/terms');
  await editor.getByLabel('CSV text').fill(['article_id,prod_name,product_type_name,product_group_name,colour_group_name',
    `09${tag}01,Linen ${tag} shirt,Shirt,Garment Upper body,White`].join('\n'));
  await editor.getByRole('button', {name: 'Run import'}).click();
  await expect(editor.getByRole('status')).toHaveText('Import finished: 1 created, 0 rejected.');
  await editor.getByRole('link', {name: new RegExp(`Row 1 \\(09${tag}01\\): created`)}).click();
  await editor.getByRole('button', {name: 'Publish revision 1'}).click();
  await expect(editor.getByRole('status')).toHaveText('Published revision 1.');
  const productId = (await editor.locator('main code').first().textContent())!.trim();

  await editor.getByLabel('Sizes (codes, space separated)').fill('S M L');
  await editor.getByRole('button', {name: 'Save sizes'}).click();
  await expect(editor.getByRole('status')).toHaveText('Sizes saved. Re-save the offer so each size gets stock.');
  await expect(editor.getByText('S, M, L', {exact: true})).toBeVisible();

  await editor.goto('/#/staff/offers');
  await editor.getByLabel('Product id').fill(productId);
  await editor.getByLabel('Sandbox price (IDR)', {exact: true}).fill('150000');
  await editor.getByLabel('Sandbox stock', {exact: true}).fill('2');
  await editor.getByRole('button', {name: 'Save offer'}).click();
  await expect(editor.getByRole('status')).toHaveText('Offer saved.');
  await expect(editor.getByText(/stock 6 \(S:2 M:2 L:2\)/)).toBeVisible();  // stock per size

  const shopper = await signIn(browser, `sh_${tag}`);
  await shopper.goto('/#/sizes');
  await shopper.getByLabel('Letter (international)').selectOption('M');
  await shopper.getByRole('button', {name: 'Save my sizes'}).click();
  await expect(shopper.getByRole('status')).toHaveText('Your sizes are saved.');

  await shopper.goto('/#/store');
  await shopper.getByLabel('Search', {exact: true}).fill(`linen ${tag}`);
  await shopper.getByLabel(/In my size/).check();
  await shopper.getByRole('button', {name: 'Search'}).click();
  const results = shopper.getByRole('list', {name: 'Products'});  // the browse results, not "Recommended for you"
  await expect(results.getByRole('link', {name: `Linen ${tag} shirt`})).toBeVisible();
  await expect(results.getByText(/sizes S–L/)).toBeVisible();

  await shopper.goto(`/#/store/product/${productId}`);
  await expect(shopper.getByLabel('Size', {exact: true})).toHaveValue('M');  // preselected: her usual size
  await shopper.getByRole('button', {name: 'Add to cart'}).click();
  await expect(shopper.getByRole('status')).toHaveText('Added size M to your cart.');
  await shopper.goto('/#/cart');
  await expect(shopper.getByRole('link', {name: `Linen ${tag} shirt (size M)`})).toBeVisible();
  await shopper.getByRole('button', {name: /Check out/}).click();
  await expect(shopper.getByRole('status')).toHaveText('Order placed (sandbox, nothing was charged).');
  await expect(shopper.getByRole('heading', {name: new RegExp(`Linen ${tag} shirt \\(size M\\) × 1`)})).toBeVisible();
  await shopper.getByRole('button', {name: 'Show key'}).click();
  await shopper.getByRole('button', {name: 'Claim into my wardrobe'}).click();
  await expect(shopper.getByRole('status')).toHaveText('Claimed: it is now in your wardrobe.');

  await shopper.goto('/#/wardrobe/add');
  await shopper.getByLabel('Name').fill(`Small ${tag} knit`);
  await shopper.getByLabel('Size', {exact: true}).selectOption('alpha:S');
  await shopper.getByRole('button', {name: 'Add to wardrobe'}).click();
  await expect(shopper.getByRole('status')).toHaveText(`Small ${tag} knit added.`);
  await shopper.getByLabel('Sort by').selectOption('size');
  const names = shopper.locator('main li.card strong');
  await expect(names).toHaveText([`Small ${tag} knit`, `Linen ${tag} shirt`]);  // S before M
  await expect(shopper.getByText(/size M \(bought\)/)).toBeVisible();
});
