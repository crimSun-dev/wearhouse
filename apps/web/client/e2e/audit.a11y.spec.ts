import AxeBuilder from '@axe-core/playwright';
import {expect, test, type Browser, type Page} from '@playwright/test';
import {as, onboarded, ownProduct, signIn, unique} from './helpers.ts';

/**
 * Task 9.2 audit (web-quality "Accessibility" and "Responsive layouts"):
 *   axe      every route, signed out and signed in, in Desktop dark, Desktop light and Focus: no serious or critical
 *            WCAG 2.2 A/AA violation (axe computes contrast from the rendered, composited colours);
 *   reflow   no horizontal page scroll at 360, 390, 768, 1440 and 1920 px, nor at 200% zoom (1440 px window = 720 CSS px);
 *   targets  controls are at least 44 px in both dimensions at phone width (text links inside prose are exempt).
 */
test.setTimeout(900_000);

type Look = {name: string; presentation: 'desktop' | 'focus'; scheme: 'dark' | 'light'};
const LOOKS: Look[] = [
  {name: 'desktop-dark', presentation: 'desktop', scheme: 'dark'},
  {name: 'desktop-light', presentation: 'desktop', scheme: 'light'},
  {name: 'focus', presentation: 'focus', scheme: 'dark'},
];
const PUBLIC = ['/', '/about', '/catalogue', '/items', '/signin', '/signup'];

let sub = '';
let routes: string[] = [];
let productRoute = '';

test.beforeAll(async () => {
  sub = unique('aud');
  const call = await onboarded(sub, {garments: 4, look: true});
  await ownProduct(call, 'Audit tote');
  const {id: itemId} = await call<{id: string}>('POST', '/me/wardrobe/items', {name: 'Audit shirt', slot: 'top'});
  const [look] = await call<Array<{id: string}>>('GET', '/me/looks');
  const orders = await call<{items: Array<{id: string}>}>('GET', '/me/orders');
  const detail = await call<{lines: Array<{product_id: string; units: Array<{public_serial: string | null}>}>}>('GET', `/me/orders/${orders.items[0]!.id}`);
  productRoute = `/catalogue/products/${detail.lines[0]!.product_id}`;
  routes = ['/', '/about', '/catalogue', productRoute, `/items/${detail.lines[0]!.units[0]!.public_serial}`,
    '/wishlist', '/cart', '/checkout', '/orders', `/orders/${orders.items[0]!.id}`, '/redeem',
    '/wardrobe', '/wardrobe/add', `/wardrobe/items/${itemId}`, '/wardrobe/looks', `/wardrobe/looks/${look!.id}`,
    '/wardrobe/fitting-room', '/wardrobe/suggestions', '/wardrobe/planner', '/wardrobe/wear', '/weather', '/sizes',
    `/u/${sub}`, '/community', '/notifications', '/profile', '/settings', '/settings/privacy', '/settings/security',
    '/settings/account'];
  void as;
});

async function open(browser: Browser, look: Look, width = 1440, height = 900, signedIn = true) {
  const context = await browser.newContext({baseURL: test.info().project.use.baseURL, viewport: {width, height},
    colorScheme: look.scheme, reducedMotion: 'reduce'});
  await context.addInitScript(p => localStorage.setItem('wearhouse.presentation', JSON.stringify(p)), look.presentation);
  const page = await context.newPage();
  if (signedIn) { await signIn(page, sub); await page.waitForURL(/#\/$/); }
  return page;
}

async function visit(page: Page, route: string) {
  await page.goto(`/app/#${route}`);
  await expect.poll(() => page.locator('#main').evaluate(el => (el as HTMLElement).innerText.trim().length > 0 && !el.querySelector('.skeleton'))
    .catch(() => false), {timeout: 20_000}).toBe(true);
  await page.evaluate(() => document.fonts.ready);
}

for (const look of LOOKS) {
  test(`axe: no serious or critical violations on any route (${look.name})`, async ({browser}) => {
    const report: string[] = [];
    for (const signedIn of [false, true]) {
      const page = await open(browser, look, 1440, 900, signedIn);
      for (const route of signedIn ? routes : [...PUBLIC, productRoute]) {
        await visit(page, route);
        const result = await new AxeBuilder({page}).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa']).analyze();
        for (const v of result.violations.filter(v => v.impact === 'serious' || v.impact === 'critical')) {
          report.push(`${signedIn ? 'in ' : 'out'} ${route} [${v.impact}] ${v.id}: ${v.nodes.slice(0, 3).map(n => n.target.join(' ')).join(' | ')}`);
        }
      }
      await page.context().close();
    }
    await test.info().attach(`axe-${look.name}.txt`, {body: report.join('\n') || 'none'});
    expect(report, report.join('\n')).toEqual([]);
  });
}

test('reflow: no horizontal page scroll at the five widths and at 200% zoom', async ({browser}) => {
  const report: string[] = [];
  const sizes: Array<[number, number, Look]> = [
    [360, 800, LOOKS[0]!], [390, 844, LOOKS[0]!], [768, 1024, LOOKS[0]!], [1440, 900, LOOKS[0]!], [1920, 1080, LOOKS[0]!],
    [1440, 900, LOOKS[2]!], [1920, 1080, LOOKS[2]!],
    [720, 450, LOOKS[0]!],   // a 1440 x 900 window at 200% zoom
  ];
  for (const [width, height, look] of sizes) {
    const page = await open(browser, look, width, height);
    for (const route of routes) {
      await visit(page, route);
      const over = await page.evaluate(() => document.documentElement.scrollWidth - innerWidth);
      if (over > 1) report.push(`${width}x${height} ${look.name} ${route}: ${over}px horizontal overflow`);
    }
    await page.context().close();
  }
  await test.info().attach('reflow.txt', {body: report.join('\n') || 'none'});
  expect(report, report.join('\n')).toEqual([]);
});

test('targets: controls are at least 44 px at phone width', async ({browser}) => {
  const report: string[] = [];
  const page = await open(browser, LOOKS[0]!, 390, 844);
  for (const route of routes) {
    await visit(page, route);
    const small = await page.evaluate(() => [...document.querySelectorAll<HTMLElement>('button, a[href], input:not([type=hidden]), select, textarea, [role=switch], [role=radio], [role=tab], [role=checkbox]')]
      .filter(el => {
        const r = el.getBoundingClientRect();
        if (r.width === 0 || r.height === 0 || getComputedStyle(el).visibility === 'hidden') return false;
        // Text links inside running prose are exempt (WCAG 2.5.8 inline exception).
        if (el.tagName === 'A' && el.closest('p, li, dd, figcaption, h1, h2, h3, h4') && !el.classList.contains('btn')) return false;
        // A native control wrapped in a label: the label is the target.
        const label = el.closest('label');
        const box = label && (el.tagName === 'INPUT') ? label.getBoundingClientRect() : r;
        return box.width < 44 || box.height < 44;
      })
      .map(el => { const r = el.getBoundingClientRect(); return `${el.tagName.toLowerCase()}${el.className ? '.' + String(el.className).split(' ')[0] : ''} "${(el.getAttribute('aria-label') ?? el.textContent ?? '').trim().slice(0, 30)}" ${Math.round(r.width)}x${Math.round(r.height)}`; }));
    for (const s of [...new Set(small)]) report.push(`${route}: ${s}`);
  }
  await page.context().close();
  await test.info().attach('targets.txt', {body: report.join('\n') || 'none'});
  expect(report, report.join('\n')).toEqual([]);
});
