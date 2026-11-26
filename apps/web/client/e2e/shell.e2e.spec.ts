import {expect, test} from '@playwright/test';
import {onboarded, signIn, unique} from './helpers.ts';

test.use({viewport: {width: 1440, height: 900}});   // Focus mode is the desktop default

test('Rail memory: moving down and back up returns to the same tile', async ({page}) => {
  const sub = unique('rails');
  await onboarded(sub, {garments: 10, look: true});
  await signIn(page, sub);
  const first = page.getByRole('group', {name: 'Continue styling'});
  await expect(first.locator('[data-focus-item]').first()).toBeFocused();   // Big Picture: the first tile is selected
  for (let i = 0; i < 3; i++) await page.keyboard.press('ArrowRight');
  const fourth = first.locator('[data-focus-item]').nth(3);
  await expect(fourth).toBeFocused();
  // The detail zone follows the selection.
  await expect(page.locator('.detail-title')).toHaveText((await fourth.locator('.tile-title').textContent())!.trim());
  await page.keyboard.press('ArrowDown');
  await expect(page.getByRole('group', {name: 'Recently added'}).locator('[data-focus-item]').first()).toBeFocused();
  await page.keyboard.press('ArrowUp');
  await expect(fourth).toBeFocused();
});

test('Overlay focus return: Q opens Quick access, Escape closes it and focus returns', async ({page}) => {
  const sub = unique('quick');
  await onboarded(sub, {garments: 4});
  await signIn(page, sub);
  const tile = page.getByRole('group', {name: 'Continue styling'}).locator('[data-focus-item]').first();
  await expect(tile).toBeFocused();
  await page.keyboard.press('q');
  const dialog = page.getByRole('dialog', {name: 'Quick access'});
  await expect(dialog).toBeVisible();
  await expect(dialog.getByText('Weather data: BMKG').or(dialog.getByText('Set your location to see the BMKG forecast.'))).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(dialog).toBeHidden();
  await expect(tile).toBeFocused();
  await page.keyboard.press('m');
  await expect(page.getByRole('dialog', {name: 'Main menu'})).toBeVisible();
});

test('Settings applied app-wide: theme changes immediately in Desktop view', async ({page}) => {
  const sub = unique('theme');
  await onboarded(sub, {garments: 2});
  await page.addInitScript(() => localStorage.setItem('wearhouse.presentation', JSON.stringify('desktop')));
  await signIn(page, sub);
  await page.getByRole('button', {name: /Notifications/}).click();
  const dialog = page.getByRole('dialog', {name: 'Quick access'});
  await dialog.getByRole('radio', {name: 'Light'}).click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
  await dialog.getByRole('radio', {name: 'Dark'}).click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
});
