// add-wearhouse-social-profile-services 5.2: two users. Share a look -> friend's feed + notification -> unfriend -> gone.
import {expect, test, type Browser, type Page} from '@playwright/test';

async function signIn(browser: Browser, sub: string): Promise<Page> {
  const page = await (await browser.newContext()).newPage();
  await page.goto(`/?e2e_sub=${sub}#/`);
  await page.getByRole('button', {name: 'Sign in with Google'}).click();
  await page.getByLabel('Choose your handle').fill(sub);
  await page.getByRole('button', {name: 'Save handle'}).click();
  await expect(page.getByRole('heading', {name: 'Your profile'})).toBeVisible();
  return page;
}

test('shared look reaches a friend and disappears after unfriending', async ({browser}) => {
  const tag = Math.random().toString(36).slice(2, 7);
  const a = await signIn(browser, `sa_${tag}`);
  const b = await signIn(browser, `sb_${tag}`);

  // Friendship: b requests, a accepts.
  await b.goto('/#/friends');
  await b.getByLabel('Find people').fill(`@sa_${tag}`);
  await b.getByRole('button', {name: 'Search', exact: true}).click();
  await b.getByRole('button', {name: 'Add friend'}).click();
  await expect(b.getByRole('status')).toHaveText(`Request sent to @sa_${tag}.`);
  await a.goto('/#/friends');
  await a.getByRole('button', {name: 'Accept'}).click();
  await expect(a.getByRole('status')).toHaveText(`You and @sb_${tag} are now friends.`);

  // a opens the wardrobe to friends, declares a top, builds and shares a look.
  await a.goto('/#/privacy');
  await a.getByLabel('Who can see my wardrobe').selectOption('friends');
  await a.getByRole('button', {name: 'Save privacy'}).click();
  await expect(a.getByRole('status')).toHaveText('Privacy saved.');
  await a.goto('/#/wardrobe/add');
  await a.getByLabel('Name').fill('Striped tee');
  await a.getByLabel('Slot').selectOption('top');
  await a.getByRole('button', {name: 'Add to wardrobe'}).click();
  await expect(a.getByRole('status')).toHaveText('Striped tee added.');
  await a.goto('/#/looks');
  const form = a.locator('form').last();
  await form.getByLabel('Look name').fill('Gallery day');
  await form.getByLabel('top', {exact: true}).selectOption({label: 'Striped tee'});
  await form.getByRole('button', {name: 'Create look'}).click();
  await expect(a.getByRole('heading', {name: 'Gallery day (revision 1)'})).toBeVisible();
  await a.getByLabel('Share caption').fill('Museum trip');
  await a.getByRole('button', {name: 'Share look'}).click();
  await expect(a.getByRole('status')).toHaveText('Shared with friends.');

  // b sees it in the feed and gets a notification badge.
  await b.goto('/#/feed');
  await expect(b.getByText('Gallery day')).toBeVisible();
  await expect(b.getByText('“Museum trip”', {exact: false})).toBeVisible();
  await expect(b.getByText('top: Striped tee')).toBeVisible();
  await b.reload();
  await expect(b.getByRole('link', {name: /Notifications \(\d+\)/})).toBeVisible();
  await b.goto('/#/notifications');
  await expect(b.getByRole('link', {name: `@sa_${tag} shared a look`})).toBeVisible();
  await b.getByRole('button', {name: 'Mark all read'}).click();
  await expect(b.getByRole('status')).toHaveText('All read.');
  await expect(b.getByRole('link', {name: 'Notifications', exact: true})).toBeVisible();

  // Unfriending invalidates access immediately.
  await a.goto('/#/friends');
  await a.getByRole('button', {name: 'Remove'}).click();
  await expect(a.getByRole('status')).toHaveText(`Removed @sb_${tag}.`);
  await b.goto('/#/feed');
  await expect(b.getByText('Nothing yet. When friends share looks, they appear here.')).toBeVisible();
  await b.goto(`/#/u/sa_${tag}`);
  await expect(b.getByText('No looks you can see.')).toBeVisible();
});
