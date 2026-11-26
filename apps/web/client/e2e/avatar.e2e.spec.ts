import {expect, test, type Page} from '@playwright/test';
import {API, as, onboarded, signIn, unique} from './helpers.ts';

test.use({viewport: {width: 1440, height: 900}});
type Call = Awaited<ReturnType<typeof as>>;
const NO_WEBGL = () => {
  const real = HTMLCanvasElement.prototype.getContext;
  HTMLCanvasElement.prototype.getContext = function (this: HTMLCanvasElement, kind: string, ...rest: unknown[]) {
    return /webgl/.test(kind) ? null : (real as (...a: unknown[]) => unknown).call(this, kind, ...rest);
  } as typeof real;
};
async function wardrobe(page: Page, pieces: Array<[string, string]>) {
  const sub = unique('av');
  const call: Call = await onboarded(sub);
  for (const [name, slot] of pieces) await call('POST', '/me/wardrobe/items', {name, slot});
  await signIn(page, sub);
  return call;
}
const hasWebGL = (page: Page) => page.evaluate(() => { const c = document.createElement('canvas'); return !!(c.getContext('webgl2') || c.getContext('webgl')); });

test('Manifest lists every slot and accessory position from GET /wardrobe/slots', async ({request}) => {
  const registry = await (await fetch(`${API}/api/v2/wardrobe/slots`)).json() as {slots: Array<{slot: string; capacity: number}>};
  const manifest = await (await request.get('/avatar/manifest.json')).json() as {slots: Record<string, {capacity: number; positions: string[]}>};
  for (const {slot, capacity} of registry.slots) {
    expect(manifest.slots[slot], slot).toBeTruthy();
    expect(manifest.slots[slot]!.positions.length, slot).toBeGreaterThanOrEqual(capacity);
  }
});

test('WebGL unavailable: the 2D view renders the look and the fitting room stays usable', async ({page}) => {
  await page.addInitScript(NO_WEBGL);
  const call = await wardrobe(page, [['Linen top', 'top'], ['Wide trousers', 'bottom'], ['Watch', 'wrist'], ['Bangle', 'wrist']]);
  await page.goto('/app/#/wardrobe/fitting-room');
  await expect(page.getByText('Showing the 2D view: this browser has no WebGL.')).toBeVisible();
  const closet = page.locator('.fit-closet');
  for (const n of ['Linen top', 'Wide trousers', 'Watch', 'Bangle']) await closet.getByRole('button', {name: new RegExp(n)}).click();
  await expect(page.locator('.avatar-flat .avatar-top')).toHaveCount(1);
  await expect(page.locator('.avatar-flat .avatar-wrist')).toHaveCount(2);     // Two wrist items: one at each wrist
  await page.getByLabel('Look name').fill('Flat look');
  await page.getByRole('button', {name: 'Save look'}).click();
  await expect(page.getByRole('heading', {name: 'Flat look'})).toBeVisible();
  expect((await call<unknown[]>('GET', '/me/looks')).length).toBe(1);
});

test('Mode label: a model load failure falls back to 2D and says so', async ({page}) => {
  await page.route('**/avatar/*.glb', route => route.fulfill({status: 404, body: ''}));
  await wardrobe(page, [['Linen top', 'top']]);
  await page.goto('/app/#/wardrobe/fitting-room');
  test.skip(!(await hasWebGL(page)), 'this browser has no WebGL; covered by the WebGL test');
  await expect(page.getByText('Showing the 2D view: the 3D models could not load.')).toBeVisible({timeout: 15000});
  await expect(page.locator('.avatar-mode')).toHaveText('2D view');
});

test('Composing and saving work before Three.js has loaded', async ({page}) => {
  let release = () => {};
  const gate = new Promise<void>(r => { release = r; });
  await page.route(/\/assets\/scene-[^/]+\.js$/, async route => { await gate; await route.continue(); });
  await wardrobe(page, [['Linen top', 'top'], ['Wide trousers', 'bottom']]);
  await page.goto('/app/#/wardrobe/fitting-room');
  const closet = page.locator('.fit-closet');
  await closet.getByRole('button', {name: /Linen top/}).click();
  await closet.getByRole('button', {name: /Wide trousers/}).click();
  await page.getByLabel('Look name').fill('Before 3D');
  await page.getByRole('button', {name: 'Save look'}).click();
  await expect(page.getByRole('heading', {name: 'Before 3D'})).toBeVisible();
  release();
});

test('Low frame rate: below 30 fps the fitting room switches to 2D and discloses it', async ({page, context}) => {
  // Simulated slow device: every animation frame does ~45 ms of main-thread work (about 20 fps). CDP CPU throttling
  // alone does not slow software WebGL, which renders in the GPU process.
  await context.addInitScript(() => {
    if (sessionStorage.getItem('slow-frames') !== '1') return;
    const real = window.requestAnimationFrame.bind(window);
    window.requestAnimationFrame = cb => real(t => { const end = performance.now() + 45; while (performance.now() < end) { /* busy */ } cb(t); });
  });
  await wardrobe(page, [['Linen top', 'top']]);
  await page.goto('/app/#/wardrobe');
  test.skip(!(await hasWebGL(page)), 'this browser has no WebGL');
  await page.evaluate(() => sessionStorage.setItem('slow-frames', '1'));
  await page.goto('/app/#/wardrobe/fitting-room');
  await page.reload();
  await expect(page.getByText('Showing the 2D view: this device rendered 3D below 30 fps.')).toBeVisible({timeout: 30000});
  await page.evaluate(() => sessionStorage.removeItem('slow-frames'));
  await page.reload();
  await expect(page.locator('.avatar-mode')).toHaveText('2D view');               // remembered on this device
  await expect(page.getByRole('button', {name: 'Try 3D again'})).toBeVisible();
});
