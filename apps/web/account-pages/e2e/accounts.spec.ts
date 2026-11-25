// add-wearhouse-accounts 8.3: the temporary account pages against the real local v2 API (e2e AuthPort fake).
import {expect, test, type Browser, type Page} from '@playwright/test';

const API = 'http://127.0.0.1:8199/api/v2';

async function signIn(browser: Browser, sub: string, handle?: string): Promise<Page> {
  const page = await (await browser.newContext({acceptDownloads: true})).newPage();
  await page.goto(`/?e2e_sub=${sub}#/`);
  await expect(page.getByRole('note')).toContainText('Temporary account pages');
  await page.getByRole('button', {name: 'Sign in with Google'}).click();
  if (handle) {
    await expect(page.getByRole('heading', {name: 'Welcome! Pick a handle'})).toBeVisible();
    await page.getByLabel('Choose your handle').fill(handle);
    await page.getByRole('button', {name: 'Save handle'}).click();
    await expect(page.getByRole('heading', {name: 'Your profile'})).toBeVisible();
  }
  return page;
}

function uniq(base: string) {
  return `${base}_${Math.random().toString(36).slice(2, 7)}`;
}

test('first sign-in onboarding, reload persistence and no token storage', async ({browser}) => {
  const h = uniq('ada');
  const page = await signIn(browser, h, h);
  await page.reload();
  await expect(page.getByRole('heading', {name: 'Your profile'})).toBeVisible();
  await expect(page.getByLabel('Handle')).toHaveValue(h);
  const stored = await page.evaluate(() => JSON.stringify({ls: {...localStorage}, ss: {...sessionStorage}, url: location.href}));
  expect(stored).not.toMatch(/eyJ[A-Za-z0-9_-]+\./);  // no JWT anywhere
  await page.getByLabel('Display name').fill('Ada Lovelace');
  await page.getByLabel('Bio').fill('Plum enjoyer');
  await page.getByRole('button', {name: 'Save profile'}).click();
  await expect(page.getByRole('status')).toHaveText('Profile saved.');
});

test('readable error codes keep the user input', async ({browser}) => {
  const taken = uniq('taken');
  await signIn(browser, taken, taken);
  const page = await signIn(browser, uniq('late'));
  await page.getByLabel('Choose your handle').fill(taken);
  await page.getByRole('button', {name: 'Save handle'}).click();
  await expect(page.getByRole('status')).toContainText('taken or reserved');
  await expect(page.getByRole('status')).toContainText('[HANDLE_UNAVAILABLE]');
  await expect(page.getByLabel('Choose your handle')).toHaveValue(taken);
  await page.getByLabel('Choose your handle').fill('1bad');
  await page.getByRole('button', {name: 'Save handle'}).click();
  await expect(page.getByRole('status')).toContainText('[VALIDATION_FAILED]');
});

test('two-user friend flow, privacy and block', async ({browser}) => {
  const a = uniq('anna');
  const b = uniq('bert');
  const pa = await signIn(browser, a, a);
  const pb = await signIn(browser, b, b);
  await pa.goto(`/?e2e_sub=${a}#/friends`);
  await pa.getByLabel('Find people').fill('@' + b);
  await pa.getByRole('button', {name: 'Search'}).click();
  await pa.getByRole('list', {name: 'Search results'}).getByRole('button', {name: 'Add friend'}).click();
  await expect(pa.getByRole('status')).toHaveText(`Request sent to @${b}.`);
  await pb.goto(`/?e2e_sub=${b}#/friends`);
  await expect(pb.getByRole('heading', {name: 'Incoming requests (1)'})).toBeVisible();
  await pb.getByRole('button', {name: 'Accept'}).click();
  await expect(pb.getByRole('heading', {name: 'Your friends (1)'})).toBeVisible();
  await pa.reload();
  await expect(pa.getByRole('heading', {name: 'Your friends (1)'})).toBeVisible();

  await pa.goto(`/?e2e_sub=${a}#/privacy`);
  await pa.getByLabel('Who can see my profile details').selectOption('private');
  await pa.getByRole('button', {name: 'Save privacy'}).click();
  await expect(pa.getByRole('status')).toHaveText('Privacy saved.');
  await pa.goto(`/?e2e_sub=${a}#/preview`);
  await expect(pa.getByText('Profile visibility: private')).toBeVisible();
  const anon = await (await fetch(`${API}/profiles/${a}`)).json();
  expect(Object.keys(anon).sort()).toEqual(['avatar', 'display_name', 'handle', 'profile_visibility']);

  await pb.reload();
  await pb.getByRole('button', {name: 'Block'}).click();
  await expect(pb.getByRole('status')).toHaveText(`Blocked @${a}.`);
  await expect(pb.getByRole('heading', {name: 'Your friends (0)'})).toBeVisible();
  await pa.goto(`/?e2e_sub=${a}#/friends`);
  await expect(pa.getByRole('heading', {name: 'Your friends (0)'})).toBeVisible();
  await pa.getByLabel('Find people').fill('@' + b);
  await pa.getByRole('button', {name: 'Search'}).click();
  await expect(pa.getByText('No matches.')).toBeVisible();  // a blocked account is invisible
  await pb.goto(`/?e2e_sub=${b}#/blocks`);
  await pb.getByRole('button', {name: 'Unblock'}).click();
  await expect(pb.getByRole('status')).toHaveText(`Unblocked @${a}.`);
});

test('export then delete with the broker disclosure', async ({browser}) => {
  const h = uniq('gone');
  const page = await signIn(browser, h, h);
  await page.goto(`/?e2e_sub=${h}#/account`);
  const download = page.waitForEvent('download');
  await page.getByRole('button', {name: 'Download my data (JSON)'}).click();
  const file = await download;
  expect(file.suggestedFilename()).toBe('wearhouse-export.json');
  const doc = JSON.parse(await (await file.createReadStream()).toArray().then(c => Buffer.concat(c).toString()));
  expect(doc.profile.handle).toBe(h);
  await page.getByLabel('Type your handle to confirm').fill('wrong');
  await page.getByRole('button', {name: 'Delete my account'}).click();
  await expect(page.getByRole('status')).toContainText('[VALIDATION_FAILED]');
  await page.getByLabel('Type your handle to confirm').fill(h);
  await page.getByRole('button', {name: 'Delete my account'}).click();
  await expect(page.getByRole('heading', {name: 'Account deleted'})).toBeVisible();
  await expect(page.getByText('was NOT deleted')).toBeVisible();  // fake broker has no self-deletion
  expect((await fetch(`${API}/profiles/${h}`)).status).toBe(404);
});

test('keyboard-only sign out everywhere', async ({browser}) => {
  const h = uniq('keys');
  const page = await signIn(browser, h, h);
  await page.goto(`/?e2e_sub=${h}#/account`);
  await expect(page.getByRole('heading', {name: 'Account', exact: true})).toBeVisible();
  const target = page.getByRole('button', {name: 'Sign out everywhere'});
  for (let i = 0; i < 40 && !(await target.evaluate(el => el === document.activeElement)); i++) {
    await page.keyboard.press('Tab');
  }
  await expect(target).toBeFocused();
  const outline = await target.evaluate(el => getComputedStyle(el).outlineStyle);
  expect(outline).not.toBe('none');  // visible focus indicator
  await page.keyboard.press('Enter');
  await expect(page.getByRole('heading', {name: 'Sign in to Wearhouse'})).toBeVisible();
  await expect(page.getByRole('status')).toHaveText('Signed out on every device.');
});
