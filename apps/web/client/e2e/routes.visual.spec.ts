import {expect, test, type Browser, type Page} from '@playwright/test';
import {API, as, onboarded, signIn} from './helpers.ts';

/**
 * web-quality "Visual regression": primary routes at the five widths, in Desktop (dark and light) and Focus
 * (always dark), reduced motion on. Run with `npm run test:visual`; a changed screen fails until its snapshot is
 * updated deliberately (`npm run test:visual -- --update-snapshots`) and the new image is reviewed.
 *
 * Fixtures are fixed names in the run's fresh harness database, so content is identical between runs. Routes whose
 * content is mostly today's date or per-run serials (planner, receipts, the signed-in Today card) are left to the e2e
 * suite; the live clock and <time> elements are masked.
 */
test.setTimeout(900_000);
test.describe.configure({mode: 'serial'});

const WIDTHS: Array<[number, number]> = [[360, 800], [390, 844], [768, 1024], [1440, 900], [1920, 1080]];
type Look = {name: string; presentation: 'desktop' | 'focus'; scheme: 'dark' | 'light'; widths: number[]};
const LOOKS: Look[] = [
  {name: 'desktop-dark', presentation: 'desktop', scheme: 'dark', widths: [360, 390, 768, 1440, 1920]},
  {name: 'desktop-light', presentation: 'desktop', scheme: 'light', widths: [360, 390, 768, 1440, 1920]},
  {name: 'focus', presentation: 'focus', scheme: 'dark', widths: [768, 1440, 1920]},
];
const SUB = 'visual';
let productRoute = '';

test.beforeAll(async () => {
  await fetch(`${API}/__e2e/grant?sub=viscurator&role=admin`, {method: 'POST'});
  const cur = await as('viscurator');
  await cur('GET', '/me');
  const pieces: Array<[string, string, string, number]> = [['Linen shirt', 'Shirt', 'White', 189000], ['Pleated skirt', 'Skirt', 'Plum', 229000],
    ['Canvas tote', 'Bag', 'Beige', 149000], ['Rain jacket', 'Jacket', 'Navy', 459000], ['Wide trousers', 'Trousers', 'Black', 279000],
    ['Knit cardigan', 'Cardigan', 'Blush', 319000]];
  const ids: string[] = [];
  for (const [i, [name, category, colour, price]] of pieces.entries()) {
    const id = `visual-${i}`;
    const {product_id} = await cur<{product_id: string}>('POST', '/admin/source-products', {
      source: {namespace: 'wearhouse-visual', name: 'Wearhouse visual fixtures', url: 'https://wearhouse.invalid/visual'},
      snapshot: {sha256: '06a15714b84fef5c12fb5c99fd7ac58bfc06142eb427dc8e68e38d733233aa28', file_name: 'visual.json', acquired_on: '2026-11-26'},
      permission: {basis: 'synthetic-test-fixture', scope: 'tests only', accepted_on: '2026-11-26', accepted_by: 'visual', terms_url: 'https://wearhouse.invalid/visual/terms'},
      external_id: id, original_fields: {article_id: id, prod_name: name, product_type_name: category, colour_group_name: colour},
      facts: {product_name: {value: name, source_field: 'prod_name'}, category: {value: category, source_field: 'product_type_name'}, colour: {value: colour, source_field: 'colour_group_name'}},
    });
    const staff = await cur<{revisions: Array<{id: string}>}>('GET', `/admin/catalogue/products/${product_id}`);
    await cur('POST', `/admin/catalogue/products/${product_id}/publish`, {revision_id: staff.revisions.at(-1)!.id});
    await cur('PUT', `/admin/commerce/offers/${product_id}`, {price_idr: price, stock: 8});
    ids.push(product_id);
  }
  productRoute = `/catalogue/products/${ids[0]}`;
  const call = await onboarded(SUB, {garments: 6, look: true});
  await call('PUT', `/me/cart/${ids[1]}`, {quantity: 1, size: null});
});

const PUBLIC = () => [['home-out', '/'], ['catalogue', '/catalogue?all=1'], ['product', productRoute], ['signin', '/signin']];
const PRIVATE = [['wardrobe', '/wardrobe'], ['looks', '/wardrobe/looks'], ['fitting-room', '/wardrobe/fitting-room'], ['cart', '/cart'],
  ['redeem', '/redeem'], ['community', '/community'], ['settings', '/settings'], ['profile', '/profile'], ['not-found', '/no-such-screen']];

async function open(browser: Browser, look: Look, [width, height]: [number, number], signedIn: boolean) {
  const context = await browser.newContext({baseURL: test.info().project.use.baseURL, viewport: {width, height},
    colorScheme: look.scheme, reducedMotion: 'reduce'});
  await context.addInitScript(p => localStorage.setItem('wearhouse.presentation', JSON.stringify(p)), look.presentation);
  const page = await context.newPage();
  if (signedIn) { await signIn(page, SUB); await page.waitForURL(/#\/$/); }
  return page;
}

async function shoot(page: Page, name: string, route: string) {
  await page.goto(`/app/#${route}`);
  await expect.poll(() => page.locator('#main').evaluate(el => (el as HTMLElement).innerText.trim().length > 0 && !el.querySelector('.skeleton'))
    .catch(() => false), {timeout: 20_000}).toBe(true);
  await page.evaluate(async () => {
    await document.fonts.ready;
    await Promise.all([...document.images].map(i => (i.complete ? null : i.decode().catch(() => null))));
  });
  await page.mouse.move(0, 0);
  await expect(page).toHaveScreenshot(`${name}.png`, {animations: 'disabled', caret: 'hide', maxDiffPixels: 40,
    // The 3D avatar renders continuously; it has its own FPS and fallback tests, so its canvas is masked here.
    mask: [page.locator('.clock'), page.locator('time'), page.locator('.toast'), page.locator('canvas')]});
}

for (const look of LOOKS) {
  test(`routes in ${look.name}`, async ({browser}) => {
    for (const size of WIDTHS.filter(([w]) => look.widths.includes(w))) {
      for (const signedIn of [false, true]) {
        const page = await open(browser, look, size, signedIn);
        for (const [name, route] of signedIn ? PRIVATE : PUBLIC()) await shoot(page, `${name}-${look.name}-${size[0]}`, route!);
        await page.context().close();
      }
    }
  });
}
