import {expect, test, type Page} from '@playwright/test';
import jsQR from 'jsqr';
import {API, as, onboarded, signIn, unique} from './helpers.ts';

test.use({viewport: {width: 1440, height: 900}});
const grant = (sub: string, role: string) => fetch(`${API}/__e2e/grant?sub=${sub}&role=${role}`, {method: 'POST'});
async function staffer(page: Page, role: string) {
  const sub = unique(role.slice(0, 4));
  await onboarded(sub);
  await grant(sub, role);
  await signIn(page, sub);
  return {sub, call: await as(sub)};
}

test('Moderator scope: only moderation is listed and other screens say not permitted', async ({page}) => {
  await staffer(page, 'moderator');
  await page.goto('/app/#/admin');
  const nav = page.getByRole('navigation', {name: 'Staff workspace'});
  await expect(nav.getByRole('link')).toHaveCount(1);
  await expect(nav.getByRole('link', {name: 'Moderation'})).toBeVisible();
  await page.goto('/app/#/admin/units');
  await expect(page.getByRole('alert')).toContainText('Not permitted');
});

test('The customer bundle never loads the staff chunk', async ({page}) => {
  const chunks: string[] = [];
  page.on('request', r => { if (/\/assets\/Staff-[^/]+\.js$/.test(r.url())) chunks.push(r.url()); });
  const sub = unique('cust');
  await onboarded(sub, {garments: 3, look: true});
  await signIn(page, sub);
  for (const route of ['#/', '#/catalogue', '#/wardrobe', '#/community', '#/settings']) { await page.goto(`/app/${route}`); await page.waitForLoadState('networkidle'); }
  expect(chunks).toEqual([]);
});

test('Imports: rejected rows are listed with their row number and errors', async ({page}) => {
  await staffer(page, 'catalogue_editor');
  await page.goto('/app/#/admin/imports');
  const run = unique('csv');
  const csv = ['article_id,prod_name,product_type_name,product_group_name,colour_group_name',
    `${run}1,Imported tee,T-shirt,Garment Upper body,White`, `${run}2,,T-shirt,Garment Upper body,Black`].join('\n');
  await page.locator('input[type=file]').setInputFiles({name: 'import.csv', mimeType: 'text/csv', buffer: Buffer.from(csv)});
  await expect(page.getByText('SHA-256 (computed from the file)')).toBeVisible();
  await page.getByLabel('Namespace').fill(`e2e-${run}`);
  await page.getByLabel('Accepted by').fill('e2e');
  await page.getByRole('button', {name: 'Start import'}).click();
  const rows = page.getByTestId('job-rows');
  await expect(rows).toBeVisible();
  const rejected = rows.locator('tr.is-rejected');
  await expect(rejected).toHaveCount(1);
  await expect(rejected.locator('td').first()).toHaveText(/\d+/);
  await expect(rejected.locator('td').nth(3)).not.toBeEmpty();
});

test('Staff publishes a product that then appears in browse', async ({page}) => {
  await staffer(page, 'catalogue_editor');
  const run = unique('pub');
  await page.goto('/app/#/admin/ingest');
  await page.getByLabel('External id').fill(run);
  await page.getByLabel('Product name').fill(`Staff tote ${run}`);
  await page.getByLabel('Category').fill('Bag');
  await page.getByLabel('Accepted by').fill('e2e');
  await page.getByRole('button', {name: 'Ingest product'}).click();
  await page.getByRole('button', {name: 'Publish this revision'}).click();
  await expect(page.getByText('Revision 1 published')).toBeVisible();
  await page.goto(`/app/#/catalogue?q=${encodeURIComponent(run)}`);
  await expect(page.getByRole('link', {name: new RegExp(`Staff tote ${run}`)})).toBeVisible();
});

test('Media: keyboard reorder saves with PUT …/media/order', async ({page}) => {
  const {call} = await staffer(page, 'admin');
  const run = unique('med');
  const {product_id} = await call<{product_id: string}>('POST', '/admin/source-products', {
    source: {namespace: 'wearhouse-e2e', name: 'e2e', url: 'https://wearhouse.invalid/e2e'},
    snapshot: {sha256: '06a15714b84fef5c12fb5c99fd7ac58bfc06142eb427dc8e68e38d733233aa28', file_name: 'e2e.json', acquired_on: '2026-11-26'},
    permission: {basis: 'synthetic-test-fixture', scope: 'tests only', accepted_on: '2026-11-26', accepted_by: 'e2e', terms_url: 'https://wearhouse.invalid/e2e/terms'},
    external_id: run, original_fields: {article_id: run, prod_name: 'Media test', product_type_name: 'Bag'},
    facts: {product_name: {value: 'Media test', source_field: 'prod_name'}, category: {value: 'Bag', source_field: 'product_type_name'}},
  });
  await call('POST', `/admin/catalogue/products/${product_id}/media/generate`);
  await call('POST', `/admin/catalogue/products/${product_id}/media/generate`);
  await page.goto(`/app/#/admin/media/${product_id}`);
  const handles = page.locator('.media-handle');
  await expect(handles).toHaveCount(2);
  const order = page.waitForRequest(r => r.url().includes('/media/order') && r.method() === 'PUT');
  await handles.nth(1).focus();
  await page.keyboard.press('Alt+ArrowUp');
  expect((await order).postDataJSON().media_ids).toHaveLength(2);
});

test('Tag never carries key: the printed QR decodes to the serial URL only', async ({page}) => {
  const {call} = await staffer(page, 'admin');
  const run = unique('qr');
  const {product_id} = await call<{product_id: string}>('POST', '/admin/source-products', {
    source: {namespace: 'wearhouse-e2e', name: 'e2e', url: 'https://wearhouse.invalid/e2e'},
    snapshot: {sha256: '06a15714b84fef5c12fb5c99fd7ac58bfc06142eb427dc8e68e38d733233aa28', file_name: 'e2e.json', acquired_on: '2026-11-26'},
    permission: {basis: 'synthetic-test-fixture', scope: 'tests only', accepted_on: '2026-11-26', accepted_by: 'e2e', terms_url: 'https://wearhouse.invalid/e2e/terms'},
    external_id: run, original_fields: {article_id: run, prod_name: 'QR tee', product_type_name: 'T-shirt'},
    facts: {product_name: {value: 'QR tee', source_field: 'prod_name'}, category: {value: 'T-shirt', source_field: 'product_type_name'}},
  });
  const staff = await call<{revisions: Array<{id: string}>}>('GET', `/admin/catalogue/products/${product_id}`);
  await call('POST', `/admin/catalogue/products/${product_id}/publish`, {revision_id: staff.revisions.at(-1)!.id});
  await page.goto('/app/#/admin/units');
  await page.getByLabel('Product id', {exact: true}).fill(product_id);
  await page.getByRole('button', {name: 'Issue units'}).click();
  await page.getByRole('button', {name: 'Show'}).click();
  const key = (await page.locator('.issued .unit-key').innerText()).trim();
  expect(key).toMatch(/^[A-Z2-7]{4}(-[A-Z2-7]{4}){3}$/);
  await page.locator('.issued').getByRole('button', {name: 'Print tag'}).click();
  const qr = page.getByTestId('tag-qr');
  await expect(qr).toBeVisible();
  const pixels = await qr.locator('svg').evaluate(async (svg: SVGSVGElement) => {
    const img = new Image(); const size = 400;
    img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(new XMLSerializer().serializeToString(svg));
    await img.decode();
    const c = document.createElement('canvas'); c.width = size; c.height = size;
    const ctx = c.getContext('2d')!; ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, size, size); ctx.drawImage(img, 0, 0, size, size);
    return Array.from(ctx.getImageData(0, 0, size, size).data);
  });
  const decoded = jsQR(Uint8ClampedArray.from(pixels), 400, 400);
  expect(decoded?.data).toMatch(/#\/items\/[A-Za-z0-9_-]+$/);
  expect(decoded!.data).toBe(await qr.getAttribute('data-url'));
  expect(decoded!.data).not.toContain(key);
  expect(decoded!.data).not.toContain(key.replace(/-/g, ''));
});

test('Last admin protected: revoking your own admin role is refused, explained, and the role remains', async ({page}) => {
  const {sub} = await staffer(page, 'admin');
  await page.goto('/app/#/admin/roles');
  // The shared test database has several admins, so the "only admin" case is simulated at the API boundary;
  // the real self-revoke refusal is exercised first.
  const row = page.locator('tr', {hasText: `@${sub}`});
  await row.getByRole('button', {name: 'Revoke admin'}).click();
  await expect(page.locator('.co-alert[role=alert]')).toBeVisible();
  await expect(row).toContainText('admin');
  await page.route(`**/admin/staff/${sub}/roles/admin`, route => route.request().method() === 'DELETE'
    ? route.fulfill({status: 409, contentType: 'application/json', headers: {'Access-Control-Allow-Origin': new URL(page.url()).origin},
      body: JSON.stringify({code: 'LAST_ADMIN', message: 'The last admin cannot be removed.', field_errors: [], request_id: 'e2e'})}) : route.continue());
  await row.getByRole('button', {name: 'Revoke admin'}).click();
  await expect(page.locator('.co-alert[role=alert]')).not.toBeEmpty();
  await page.reload();
  await expect(page.locator('tr', {hasText: `@${sub}`})).toContainText('admin');
});
