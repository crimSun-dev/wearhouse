import {expect, test} from '@playwright/test';
import {onboarded, signIn, unique} from './helpers.ts';

test('New account onboarding: a first sign-in goes to onboarding before anything private, and keeps its language', async ({page}) => {
  const sub = unique('newbie');
  await signIn(page, sub);
  await expect(page.getByRole('heading', {name: 'Set up your profile'})).toBeVisible();
  await page.goto(`/app/?e2e_sub=${sub}#/wardrobe`);
  await expect(page.getByRole('heading', {name: 'Set up your profile'})).toBeVisible();   // private routes wait for onboarding
  await page.getByLabel('Handle').fill(sub);
  await page.getByRole('radio', {name: 'Bahasa Indonesia'}).click();
  await page.getByRole('button', {name: 'Finish setup'}).click();
  // The empty wardrobe leads with discovery, now in Indonesian because onboarding saved the choice.
  await expect(page.getByRole('heading', {name: 'Lemarimu masih kosong, untuk sekarang'})).toBeVisible();
  await expect(page.locator('html')).toHaveAttribute('lang', 'id');
});

test('Empty wardrobe home: discovery first with redeem and add actions, and no suggestion request on load', async ({page}) => {
  const sub = unique('empty');
  await onboarded(sub);
  const suggestionCalls: string[] = [];
  page.on('request', r => { if (r.url().includes('/recommendations/outfits')) suggestionCalls.push(r.url()); });
  await signIn(page, sub);
  await expect(page.getByRole('heading', {name: 'Your wardrobe is empty, for now'})).toBeVisible();
  await expect(page.getByRole('button', {name: 'Redeem a garment'})).toBeVisible();
  await expect(page.getByRole('button', {name: 'Add a garment'})).toBeVisible();
  await page.waitForLoadState('networkidle');
  expect(suggestionCalls).toEqual([]);
});

test('Customer sees no staff entry', async ({page}) => {
  const sub = unique('cust');
  await onboarded(sub, {garments: 3});
  await signIn(page, sub);
  await page.getByRole('button', {name: 'Account menu'}).click();
  await expect(page.getByRole('menuitem', {name: 'Orders'})).toBeVisible();
  await expect(page.getByRole('menuitem', {name: 'Staff workspace'})).toHaveCount(0);
  await expect(page.getByText(/staff|admin/i)).toHaveCount(0);
});

test('Sign-out clears private data', async ({page}) => {
  const a = unique('alpha'); const b = unique('bravo');
  await onboarded(a, {garments: 3, look: true});
  await onboarded(b, {garments: 3});
  await signIn(page, a);
  await expect(page.getByText(`${a} campus look`).first()).toBeVisible();
  await page.getByRole('button', {name: 'Account menu'}).click();
  await page.getByRole('menuitem', {name: 'Sign out'}).click();
  await expect(page.getByRole('button', {name: 'Sign in'}).first()).toBeVisible();
  await signIn(page, b);
  await expect(page.getByRole('button', {name: 'Account menu'})).toContainText(`@${b}`);
  await expect(page.getByText(`${a} campus look`)).toHaveCount(0);
  await expect(page.getByText(`${a} piece`)).toHaveCount(0);
});
