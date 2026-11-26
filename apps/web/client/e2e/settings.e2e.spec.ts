import {expect, test} from '@playwright/test';
import {onboarded, signIn, unique} from './helpers.ts';

test.use({viewport: {width: 1440, height: 900}});

test('Setting overrides OS: reduce_motion on removes lift and scale even when the OS allows motion', async ({page}) => {
  const sub = unique('motion');
  await onboarded(sub, {garments: 4, look: true});
  await signIn(page, sub);                                         // OS preference: no-preference (Playwright default)
  const first = page.getByRole('group', {name: 'Continue styling'}).locator('[data-focus-item]').first();
  await expect(first).toBeFocused();
  await expect(page.locator('html')).toHaveAttribute('data-motion', 'full');
  await page.keyboard.press('q');
  await page.getByRole('dialog', {name: 'Quick access'}).getByRole('switch', {name: 'Reduce motion'}).click();
  await expect(page.locator('html')).toHaveAttribute('data-motion', 'reduced');
  await page.keyboard.press('Escape');
  await expect(first).toBeFocused();
  const transform = await first.locator('.tile-media').evaluate(el => getComputedStyle(el).transform);
  expect(transform === 'none' || transform === 'matrix(1, 0, 0, 1, 0, 0)').toBe(true);
});

test('UI sounds play only while enabled', async ({page}) => {
  await page.addInitScript(() => {
    const w = window as unknown as {__audioContexts: number};
    w.__audioContexts = 0;
    const Real = window.AudioContext;
    window.AudioContext = class extends Real { constructor() { super(); w.__audioContexts++; } } as typeof AudioContext;
  });
  const sub = unique('sound');
  await onboarded(sub, {garments: 4});
  await signIn(page, sub);
  const contexts = () => page.evaluate(() => (window as unknown as {__audioContexts: number}).__audioContexts);
  await expect(page.getByRole('group', {name: 'Continue styling'}).locator('[data-focus-item]').first()).toBeFocused();
  await page.keyboard.press('ArrowRight');
  expect(await contexts()).toBe(0);                                // off by default: no audio at all
  await page.keyboard.press('q');
  await page.getByRole('dialog', {name: 'Quick access'}).getByRole('switch', {name: 'UI sounds'}).click();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog', {name: 'Quick access'})).toBeHidden();
  await expect(page.locator('.rail-track [data-focus-item]:focus')).toHaveCount(1);   // focus returned to the rail
  await page.keyboard.press('ArrowRight');
  await expect.poll(contexts).toBe(1);                             // enabled: a move ticks
});
