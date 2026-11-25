// add-wearhouse-settings-security 3.1: email/password account (e2e broker fake), synced settings that change the page,
// password policy + change, per-device sign-out, security activity, password reset by link, About.
// Passwords here are throwaway test values for the fake broker only.
import {expect, test} from '@playwright/test';

test('settings, password and security flows', async ({browser}) => {
  const tag = Math.random().toString(36).slice(2, 7);
  const email = `st_${tag}@example.invalid`;
  const page = await (await browser.newContext()).newPage();
  await page.goto('/#/');

  // sign-up refuses a weak password before anything reaches the broker
  await page.getByLabel('Name').fill(`Sam ${tag}`);
  await page.locator('#signup-email').fill(email);
  await page.locator('#signup-password').fill('password123');
  await expect(page.getByText(/Strength: weak\. This is one of the most common passwords/)).toBeVisible();
  await page.locator('#signup-password-again').fill('password123');
  await page.getByRole('button', {name: 'Create account'}).click();
  await expect(page.getByRole('status')).toContainText('most common passwords');
  await page.locator('#signup-password').fill('Linen-Sunday-Brunch-7');
  await page.locator('#signup-password-again').fill('Linen-Sunday-Brunch-7');
  await page.getByRole('button', {name: 'Create account'}).click();
  await page.getByLabel('Choose your handle').fill(`st_${tag}`);
  await page.getByRole('button', {name: 'Save handle'}).click();
  await expect(page.getByRole('heading', {name: 'Your profile'})).toBeVisible();

  // settings: rendered from the schema, saved instantly, synced (theme survives a reload)
  await page.goto('/#/settings');
  await expect(page.getByRole('heading', {name: 'Style & Recommendations'})).toBeVisible();
  await page.getByLabel('Dark').check();
  await expect(page.getByRole('status')).toHaveText('Theme saved.');
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await page.getByLabel('Recommendation style').selectOption('adventurous');
  await expect(page.getByRole('status')).toHaveText('Recommendation style saved.');
  await page.getByLabel('Appear in search').uncheck();
  await expect(page.getByRole('status')).toHaveText('Appear in search saved.');
  await page.reload();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await expect(page.getByLabel('Recommendation style')).toHaveValue('adventurous');
  await expect(page.getByLabel('Appear in search')).not.toBeChecked();

  // security: password change (wrong current refused), another device signed out, activity listed
  await page.goto('/#/security');
  await page.getByLabel('Current password').fill('not-my-password-1');
  await page.getByLabel('New password', {exact: true}).fill('Velvet-Autumn-Coat-42');
  await page.getByLabel('Repeat new password').fill('Velvet-Autumn-Coat-42');
  await page.getByLabel('Sign out my other devices').uncheck();
  await page.getByRole('button', {name: 'Change password'}).click();
  await expect(page.getByRole('status')).toHaveText('Invalid password');
  await page.getByLabel('Current password').fill('Linen-Sunday-Brunch-7');
  await page.getByLabel('New password', {exact: true}).fill('Velvet-Autumn-Coat-42');
  await page.getByLabel('Repeat new password').fill('Velvet-Autumn-Coat-42');
  await page.getByRole('button', {name: 'Change password'}).click();
  await expect(page.getByRole('status')).toHaveText('Password changed.');
  const devices = page.getByRole('list', {name: 'Signed-in devices'});
  await expect(devices.getByText(/\(this device\)/)).toBeVisible();
  await devices.getByRole('button', {name: 'Sign out this device'}).click();
  await expect(page.getByRole('status')).toHaveText('That device is signed out.');
  await expect(devices.getByRole('button', {name: 'Sign out this device'})).toHaveCount(0);
  await expect(page.getByRole('list', {name: 'Security activity'}).getByText(/Settings changed/).first()).toBeVisible();

  // sign out; the old password no longer works, the new one does
  await page.goto('/#/account');
  await page.getByRole('button', {name: 'Sign out', exact: true}).click();
  await page.locator('#signin-email').fill(email);
  await page.locator('#signin-password').fill('Linen-Sunday-Brunch-7');
  await page.getByRole('button', {name: 'Sign in', exact: true}).click();
  await expect(page.getByRole('status')).toHaveText('Invalid email or password');
  await page.locator('#signin-password').fill('Velvet-Autumn-Coat-42');
  await page.getByRole('button', {name: 'Sign in', exact: true}).click();
  await expect(page.getByRole('heading', {name: 'Your profile'})).toBeVisible();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');  // settings followed the account

  // forgot password: the reset link (the fake broker's "email") sets a new password
  await page.goto('/#/account');
  await page.getByRole('button', {name: 'Sign out', exact: true}).click();
  await page.getByText('Forgot your password?').click();
  await page.locator('#forgot-email').fill(email);
  await page.getByRole('button', {name: 'Email me a reset link'}).click();
  await expect(page.getByRole('status')).toHaveText('If that email has an account, a reset link is on its way.');
  const link = await page.evaluate(() => localStorage.getItem('e2e_last_reset_link'));
  expect(link).toContain('token=');
  await page.goto(link!);
  await page.getByLabel('New password', {exact: true}).fill('Silk-Scarf-Winter-88');
  await page.getByLabel('Repeat new password').fill('Silk-Scarf-Winter-88');
  await page.getByRole('button', {name: 'Set new password'}).click();
  await expect(page.getByRole('heading', {name: 'Password updated'})).toBeVisible();
  expect(page.url()).not.toContain('token=');  // the token is dropped from the address bar
  await page.getByRole('link', {name: 'Go to sign in'}).click();
  await page.locator('#signin-email').fill(email);
  await page.locator('#signin-password').fill('Silk-Scarf-Winter-88');
  await page.getByRole('button', {name: 'Sign in', exact: true}).click();
  await expect(page.getByRole('heading', {name: 'Your profile'})).toBeVisible();

  // About is public and lists the sources
  await page.goto('/#/about');
  await expect(page.getByText(/Polyvore Outfits/)).toBeVisible();
  await expect(page.getByText(/Learning Type-Aware Embeddings for Fashion Compatibility/)).toBeVisible();
});
