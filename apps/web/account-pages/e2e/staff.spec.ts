// add-wearhouse-object-management 5.2: admin grants a role in the app -> the editor's staff view appears -> the editor
// replaces a product's generated placeholder with an uploaded image -> the store shows the new image.
// The product is a SYNTHETIC row in the H&M articles.csv column format.
import {expect, test, type Browser, type Page} from '@playwright/test';

const HARNESS = 'http://127.0.0.1:8199';
const PNG = Buffer.from('89504e470d0a1a0a0000000d4948445200000001000000010806000000' +
  '1f15c4890000000d49444154789c6360f8cf00000301010018dd8db00000000049454e44ae426082', 'hex');

async function signIn(browser: Browser, sub: string): Promise<Page> {
  const page = await (await browser.newContext()).newPage();
  await page.goto(`/?e2e_sub=${sub}#/`);
  await page.getByRole('button', {name: 'Sign in with Google'}).click();
  await page.getByLabel('Choose your handle').fill(sub);
  await page.getByRole('button', {name: 'Save handle'}).click();
  await expect(page.getByRole('heading', {name: 'Your profile'})).toBeVisible();
  return page;
}

test('admin grants editor; editor replaces the placeholder; store shows the image', async ({browser}) => {
  const tag = Math.random().toString(36).slice(2, 7);
  const boss = await signIn(browser, `bo_${tag}`);
  expect((await boss.request.post(`${HARNESS}/__e2e/grant?sub=bo_${tag}&role=admin`)).ok()).toBeTruthy();
  const ed = await signIn(browser, `ed_${tag}`);
  await expect(ed.getByRole('link', {name: 'Staff workspace'})).toHaveCount(0);

  await boss.reload();
  await boss.goto('/#/staff/roles');
  await boss.getByLabel('Account handle').fill(`ed_${tag}`);
  await boss.getByLabel('Role').selectOption('catalogue_editor');
  await boss.getByRole('button', {name: 'Grant role'}).click();
  await expect(boss.getByRole('status')).toHaveText(`Granted catalogue_editor to @ed_${tag}.`);

  await ed.reload();
  await ed.getByRole('link', {name: 'Staff workspace'}).click();
  await expect(ed.getByRole('link', {name: 'Products & media'})).toBeVisible();
  await expect(ed.getByRole('link', {name: 'Roles'})).toHaveCount(0);  // editors cannot manage roles
  await ed.goto('/#/staff/import');
  await ed.getByLabel('Basis').fill('synthetic-test-fixture');
  await ed.getByLabel('Scope').fill('automated tests only');
  await ed.getByLabel('Accepted by').fill('wearhouse e2e');
  await ed.getByLabel('Terms URL').fill('https://wearhouse.invalid/terms');
  await ed.getByLabel('CSV text').fill(['article_id,prod_name,product_type_name,product_group_name,colour_group_name',
    `07${tag}01,Blush ${tag} blouse,Blouse,Garment Upper body,Light Pink`].join('\n'));
  await ed.getByRole('button', {name: 'Run import'}).click();
  await expect(ed.getByRole('status')).toHaveText('Import finished: 1 created, 0 rejected.');
  await ed.getByRole('link', {name: new RegExp(`Row 1 \\(07${tag}01\\): created`)}).click();
  await ed.getByRole('button', {name: 'Publish revision 1'}).click();
  await expect(ed.getByRole('status')).toHaveText('Published revision 1.');

  await ed.getByRole('button', {name: 'Generate placeholder'}).click();
  await expect(ed.getByRole('heading', {name: 'Media (1)'})).toBeVisible();
  await ed.getByLabel('Image (JPEG/PNG/WebP, max 5 MB)').setInputFiles({name: 'front.png', mimeType: 'image/png', buffer: PNG});
  await ed.getByLabel('Rights basis').fill('own-photo');
  await ed.getByRole('button', {name: 'Upload image'}).click();
  await expect(ed.getByRole('heading', {name: 'Media (2)'})).toBeVisible();
  const mediaList = ed.getByRole('list', {name: 'Media objects'});
  await mediaList.getByRole('button', {name: 'Remove'}).first().click();  // removes the placeholder (first)
  await expect(ed.getByRole('heading', {name: 'Media (1)'})).toBeVisible();
  await expect(mediaList).toContainText('uploaded');

  const visitor = await (await browser.newContext()).newPage();
  const productId = (await ed.locator('main code').first().textContent())!.trim();
  await visitor.goto(`/#/store/product/${productId}`);
  const img = visitor.locator('img.media').first();
  await expect(img).toHaveAttribute('src', /\/api\/v2\/media\//);
  await expect.poll(() => img.evaluate((i: HTMLImageElement) => i.naturalWidth)).toBe(1);  // the uploaded 1x1 PNG
});
