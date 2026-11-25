// publish-wearhouse-catalogue 5.2: staff import -> publish -> public store -> retire -> gone (real local v2 API).
// CSV rows are SYNTHETIC rows in the H&M articles.csv column format, not H&M data.
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

test('import, publish, find in the store, retire and disappear', async ({browser}) => {
  const tag = Math.random().toString(36).slice(2, 7);
  const editor = `ed_${tag}`;
  const page = await signIn(browser, editor);
  const granted = await page.request.post(`${HARNESS}/__e2e/grant?sub=${editor}&role=catalogue_editor`);
  expect(granted.ok()).toBeTruthy();
  await page.reload();
  await expect(page.getByRole('link', {name: 'Staff workspace'})).toBeVisible();

  await page.goto('/#/staff/import');
  await page.getByLabel('Basis').fill('synthetic-test-fixture');
  await page.getByLabel('Scope').fill('automated tests only');
  await page.getByLabel('Accepted by').fill('wearhouse e2e');
  await page.getByLabel('Terms URL').fill('https://wearhouse.invalid/terms');
  const csv = [
    'article_id,prod_name,product_type_name,product_group_name,colour_group_name,detail_desc',
    `09${tag}01,Plum ${tag} wrap dress,Dress,Garment Full body,Purple,Synthetic dress`,
    `09${tag}02,Ivory ${tag} shirt,Shirt,Garment Upper body,White,Synthetic shirt`,
    `09${tag}03,Broken ${tag},,Garment Upper body,Red,missing type`,
  ].join('\n');
  await page.getByLabel('CSV text').fill(csv);
  await page.getByRole('button', {name: 'Run import'}).click();
  await expect(page.getByRole('status')).toHaveText('Import finished: 2 created, 1 rejected.');
  await expect(page.getByText('product_type_name: product_type_name is empty.')).toBeVisible();

  // Drafts are not public yet.
  const visitor = await (await browser.newContext()).newPage();
  await visitor.goto(`/#/store?q=${tag}`);
  await expect(visitor.getByText('No published products match.')).toBeVisible();

  await page.getByRole('link', {name: new RegExp(`Row 1 \\(09${tag}01\\): created`)}).click();
  await page.getByRole('button', {name: 'Publish revision 1'}).click();
  await expect(page.getByRole('status')).toHaveText('Published revision 1.');

  await visitor.goto('/#/store');
  await visitor.getByRole('searchbox').fill(`${tag} wrap`);
  await visitor.getByRole('button', {name: 'Search', exact: true}).click();
  await visitor.getByRole('link', {name: `Plum ${tag} wrap dress`}).click();
  await expect(visitor.getByRole('heading', {name: `Plum ${tag} wrap dress`})).toBeVisible();
  await expect(visitor.getByText(/slot: dress \(annotation, origin rule, hm-articles@1\)/)).toBeVisible();

  await page.getByRole('button', {name: 'Retire product'}).click();
  await expect(page.getByRole('status')).toHaveText('Product retired.');
  await visitor.goto(`/#/store?q=${tag}`);
  await expect(visitor.getByText('No published products match.')).toBeVisible();
});

test('customers see the store but not the staff pages', async ({browser}) => {
  const page = await signIn(browser, `cu_${Math.random().toString(36).slice(2, 7)}`);
  await expect(page.getByRole('link', {name: 'Store'})).toBeVisible();
  await expect(page.getByRole('link', {name: 'Staff workspace'})).toHaveCount(0);
  await page.goto('/#/staff/import');
  await expect(page.getByText('Your account does not have the role this section needs.')).toBeVisible();
});
