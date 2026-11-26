import {expect, test} from '@playwright/test';
import {onboarded, signIn, unique} from './helpers.ts';

/**
 * web-motion "Signature moments": each plays only after the server confirmed the action, never on a plain page load,
 * and its reduced variant is static (task 9.1).
 */
test.use({viewport: {width: 1440, height: 900}});
const today = () => new Intl.DateTimeFormat('en-CA', {timeZone: 'Asia/Jakarta'}).format(new Date());

test('Plan and wear: the worn stamp plays after a confirmed wear, not on reload; reduced motion keeps it static', async ({page}) => {
  const sub = unique('stamp');
  const call = await onboarded(sub, {garments: 3, look: true});
  const [look] = await call<Array<{current: {id: string}}>>('GET', '/me/looks');
  await call('PUT', `/me/planner/${today()}`, {look_revision_id: look!.current.id, occasion: 'casual'});
  await signIn(page, sub);
  await page.goto('/app/#/wardrobe/planner');
  const day = page.locator('.plan-day.is-today');
  await expect(day.locator('.plan-look')).not.toHaveClass(/is-dropped/);   // planned elsewhere: no drop-in on load
  await day.getByRole('button', {name: 'Mark worn'}).click();
  await expect(day.locator('.plan-worn')).toHaveClass(/is-stamped/);
  const tag = day.locator('.plan-worn li').last().locator('.tag');
  expect(await tag.evaluate(el => getComputedStyle(el).animationName)).toBe('worn-stamp');
  await page.reload();
  await expect(page.locator('.plan-day.is-today .plan-worn')).not.toHaveClass(/is-stamped/);
  await page.evaluate(() => { document.documentElement.dataset.motion = 'reduced'; });
  await page.locator('.plan-day.is-today').getByRole('button', {name: 'Mark worn'}).click();
  await expect(page.locator('.plan-day.is-today .plan-worn')).toHaveClass(/is-stamped/);
  expect(await page.locator('.plan-day.is-today .plan-worn li').last().locator('.tag').evaluate(el => getComputedStyle(el).animationName)).toBe('none');
});

test('Plan: a look planned here drops into its day once', async ({page}) => {
  const sub = unique('drop');
  await onboarded(sub, {garments: 3, look: true});
  await signIn(page, sub);
  await page.goto('/app/#/wardrobe/planner');
  const day = page.locator('.plan-day.is-today');
  await day.getByRole('button', {name: 'Plan a look'}).click();
  await page.getByRole('dialog', {name: 'Plan a look'}).getByRole('button', {name: 'Save plan'}).click();
  await expect(day.locator('.plan-look')).toHaveClass(/is-dropped/);
  await page.reload();
  await expect(page.locator('.plan-day.is-today .plan-look')).not.toHaveClass(/is-dropped/);
});

test('Suggestions: choosing Plan folds the other cards away; they stay in place and usable', async ({page}) => {
  const sub = unique('fold');
  await onboarded(sub, {garments: 9});
  await signIn(page, sub);
  await page.goto('/app/#/wardrobe/suggestions');
  const cards = page.locator('.suggest-card');
  await expect(cards.first()).toBeVisible();
  const n = await cards.count();
  test.skip(n < 2, 'needs at least two suggestions');
  // Layout position (offset), not the painted box: folding scales the card slightly but must never reflow the grid.
  const layout = () => cards.nth(1).evaluate(el => [(el as HTMLElement).offsetLeft, (el as HTMLElement).offsetTop]);
  const before = await layout();
  await cards.first().getByRole('button', {name: 'Plan', exact: true}).click();
  await expect(cards.first()).toHaveClass(/is-picked/);
  await expect(page.locator('.suggest-card.is-folded')).toHaveCount(n - 1);
  expect(await layout()).toEqual(before);
  await expect(cards.nth(1).getByRole('button', {name: 'Try on'})).toBeEnabled();
});
