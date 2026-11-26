import {expect, test, type Page} from '@playwright/test';
import jsQR from 'jsqr';
import {API, as, onboarded, signIn, unique} from './helpers.ts';

test.use({viewport: {width: 1440, height: 900}});
type Call = Awaited<ReturnType<typeof as>>;

/** A camera that "sees" whatever window.__qr holds: fake BarcodeDetector + a canvas stream for getUserMedia. */
const FAKE_CAMERA = () => {
  const w = window as unknown as {__qr: string | null; BarcodeDetector: unknown};
  w.__qr = null;
  w.BarcodeDetector = class { async detect() { return w.__qr ? [{rawValue: w.__qr}] : []; } };
  navigator.mediaDevices.getUserMedia = async () => { const c = document.createElement('canvas'); c.width = 8; c.height = 8; c.getContext('2d'); return c.captureStream(); };
};

async function boughtKey(call: Call) {
  const run = unique('qrk');
  await fetch(`${API}/__e2e/grant?sub=cur${run}&role=admin`, {method: 'POST'});
  const curator = await as(`cur${run}`);
  await curator('GET', '/me');
  const {product_id} = await curator<{product_id: string}>('POST', '/admin/source-products', {
    source: {namespace: 'wearhouse-e2e', name: 'e2e', url: 'https://wearhouse.invalid/e2e'},
    snapshot: {sha256: '06a15714b84fef5c12fb5c99fd7ac58bfc06142eb427dc8e68e38d733233aa28', file_name: 'e2e.json', acquired_on: '2026-11-26'},
    permission: {basis: 'synthetic-test-fixture', scope: 'tests only', accepted_on: '2026-11-26', accepted_by: 'e2e', terms_url: 'https://wearhouse.invalid/e2e/terms'},
    external_id: run, original_fields: {article_id: run, prod_name: 'Scanned scarf', product_type_name: 'Scarf'},
    facts: {product_name: {value: 'Scanned scarf', source_field: 'prod_name'}, category: {value: 'Scarf', source_field: 'product_type_name'}},
  });
  const staff = await curator<{revisions: Array<{id: string}>}>('GET', `/admin/catalogue/products/${product_id}`);
  await curator('POST', `/admin/catalogue/products/${product_id}/publish`, {revision_id: staff.revisions.at(-1)!.id});
  await curator('PUT', `/admin/commerce/offers/${product_id}`, {currency: 'IDR', price_idr: 50000, stock: 5});
  await call('PUT', `/me/cart/${product_id}`, {quantity: 1, size: null});
  const cart = await call<{total_idr: number}>('GET', '/me/cart');
  const order = await call<{id: string; lines: Array<{units: Array<{unit_id: string}>}>}>('POST', '/me/checkout', {expected_total_idr: cart.total_idr}, `e2e-${unique('co')}`);
  const unit = order.lines[0]!.units[0]!.unit_id;
  const key = await call<{activation_key: string}>('GET', `/me/orders/${order.id}/units/${unit}/key`);
  return {orderId: order.id, key: key.activation_key};
}
const scan = (page: Page, value: string) => page.evaluate(v => { (window as unknown as {__qr: string}).__qr = v; }, value);

test('Redeem by scanning a key QR; a scanned tag link is explained, never redeemed', async ({page}) => {
  await page.addInitScript(FAKE_CAMERA);
  const sub = unique('scan');
  const call = await onboarded(sub);
  const {key} = await boughtKey(call);
  await signIn(page, sub);
  await page.goto('/app/#/redeem');
  const redemptions: string[] = [];
  page.on('request', r => { if (r.url().includes('/redemptions')) redemptions.push(r.url()); });
  await scan(page, 'https://crimsun-dev.github.io/wearhouse/app/#/items/abcdEFGH1234');
  await page.getByRole('button', {name: 'Scan a key QR'}).click();
  await expect(page.getByTestId('scan-note')).toContainText('That’s a garment tag');
  expect(redemptions).toEqual([]);
  await scan(page, key.toLowerCase().replace(/-/g, ''));
  await page.getByRole('button', {name: 'Scan a key QR'}).click();
  await expect(page.locator('.redeem-input')).toHaveValue(key);
  await page.getByRole('button', {name: 'Redeem', exact: true}).click();
  await expect(page.getByRole('heading', {name: /Scanned scarf is now in your wardrobe/})).toBeVisible();
});

test('The receipt can show a revealed key as a QR that decodes to exactly that key', async ({page}) => {
  const sub = unique('kqr');
  const call = await onboarded(sub);
  const {orderId, key} = await boughtKey(call);
  await signIn(page, sub);
  await page.goto(`/app/#/orders/${orderId}`);
  await page.getByRole('button', {name: 'Reveal key'}).click();
  await page.getByRole('button', {name: 'Show as QR'}).click();
  const svg = page.getByTestId('key-qr').locator('svg');
  await expect(svg).toBeVisible();
  const pixels = await svg.evaluate(async (el: SVGSVGElement) => {
    const img = new Image(); const size = 400;
    img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(new XMLSerializer().serializeToString(el));
    await img.decode();
    const c = document.createElement('canvas'); c.width = size; c.height = size;
    const ctx = c.getContext('2d')!; ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, size, size); ctx.drawImage(img, 0, 0, size, size);
    return Array.from(ctx.getImageData(0, 0, size, size).data);
  });
  expect(jsQR(Uint8ClampedArray.from(pixels), 400, 400)?.data).toBe(key);
});
