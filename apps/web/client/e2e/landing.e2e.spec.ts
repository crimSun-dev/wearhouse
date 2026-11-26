import {expect, test} from '@playwright/test';

test.use({viewport: {width: 1440, height: 900}});
const PUBLIC = [/\/api\/v2\/catalogue\/facets$/, /\/api\/v2\/catalogue\/products\?/, /\/api\/v2\/catalogue\/collections/, /\/api\/v2\/about$/];

test('Calls to action reachable: a keyboard user reaches both and they open the app routes', async ({page}) => {
  await page.goto('/');
  const reached = new Set<string>();
  for (let i = 0; i < 20 && reached.size < 2; i++) {
    await page.keyboard.press('Tab');
    const text = await page.evaluate(() => document.activeElement?.textContent?.trim() ?? '');
    if (/^Open Wearhouse$|^browse the catalogue$/i.test(text)) reached.add(text.toLowerCase());
  }
  expect([...reached].sort()).toEqual(['browse the catalogue', 'open wearhouse']);
  await expect(page.getByRole('link', {name: 'Open Wearhouse'}).first()).toHaveAttribute('href', /app\/#\/$/);
  await expect(page.getByRole('link', {name: /browse the catalogue/i}).first()).toHaveAttribute('href', /app\/#\/catalogue$/);
  await page.getByRole('link', {name: /browse the catalogue/i}).first().click();
  await expect(page).toHaveURL(/app\/#\/catalogue/);
});

test('Public endpoints only, no authentication, no suggestion request', async ({page}) => {
  const calls: Array<{url: string; auth: boolean}> = [];
  page.on('request', r => { if (r.url().includes('/api/v2/')) calls.push({url: r.url(), auth: !!r.headers().authorization}); });
  await page.goto('/');
  await page.waitForLoadState('networkidle');
  await page.mouse.wheel(0, 20000);
  await page.waitForTimeout(500);
  expect(calls.length).toBeGreaterThan(0);
  for (const c of calls) {
    expect(c.auth, c.url).toBe(false);
    expect(PUBLIC.some(re => re.test(c.url)), c.url).toBe(true);
    expect(c.url).not.toContain('recommendations');
  }
});

test('API unreachable: the page renders fully with no live tiles, counts or errors', async ({page}) => {
  await page.route('**/api/v2/**', route => route.abort());
  await page.goto('/');
  for (const h of ['Your clothes, kept like a library.', 'A store where every piece says where it came from.',
    'Dressed for the weather Jakarta actually has.', 'Shared with friends, private until you say so.']) {
    await expect(page.getByRole('heading', {name: h})).toBeAttached();
  }
  await page.waitForTimeout(1000);
  await expect(page.locator('[data-live]:visible')).toHaveCount(0);
  await expect(page.getByText(/error|went wrong|failed to load/i)).toHaveCount(0);
  await expect(page.locator('[data-live-products]')).toBeEmpty();
});

test('Reduced motion landing: static, complete composition that does not move with scroll', async ({page}) => {
  await page.emulateMedia({reducedMotion: 'reduce'});
  await page.goto('/#key');
  await page.waitForTimeout(500);
  const state = () => page.evaluate(() => ({
    door: getComputedStyle(document.querySelector('.door--l')!).transform,
    piece: getComputedStyle(document.querySelector('.wardrobe__piece')!).opacity,
  }));
  const first = await state();
  expect(first.door).not.toBe('none');                    // doors already open
  expect(Number(first.piece)).toBe(1);                    // the piece is already on the shelf
  await page.mouse.wheel(0, 900); await page.waitForTimeout(400);
  expect(await state()).toEqual(first);                    // scrolling changes nothing in the scene
  await expect(page.getByText('Example key, not a real one')).toBeVisible();
});

test('Readable with JavaScript disabled', async ({browser}) => {
  const ctx = await browser.newContext({javaScriptEnabled: false, baseURL: test.info().project.use.baseURL});
  const page = await ctx.newPage();
  await page.goto('/');
  for (const text of ['Your clothes, kept like a library.', 'Then the doors open, and the piece is yours.', 'Dressed for the weather Jakarta actually has.']) {
    const el = page.getByText(text).first();
    await expect(el).toBeVisible();
    expect(Number(await el.evaluate(e => getComputedStyle(e).opacity))).toBe(1);
  }
  await expect(page.getByRole('link', {name: 'Open Wearhouse'}).first()).toBeVisible();
  await ctx.close();
});
