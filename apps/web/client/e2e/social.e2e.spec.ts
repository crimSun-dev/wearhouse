import {expect, test, type Browser, type Page} from '@playwright/test';
import {as, onboarded, ownProduct, signIn, unique} from './helpers.ts';

test.use({viewport: {width: 1440, height: 900}});
type Call = Awaited<ReturnType<typeof as>>;
const idem = () => `e2e-${unique('k')}-${Math.random().toString(36).slice(2, 8)}`;
async function befriend(a: Call, b: Call, bHandle: string) {
  const r = await a<{request_id: string}>('POST', '/me/friend-requests', {handle: bHandle}, idem());
  await b('POST', `/me/friend-requests/${r.request_id}/accept`);
}
async function pageFor(browser: Browser, sub: string): Promise<Page> {
  const ctx = await browser.newContext({baseURL: test.info().project.use.baseURL, viewport: {width: 1440, height: 900}});
  const p = await ctx.newPage(); await signIn(p, sub); return p;
}

test('Inspiration does not grant: saving leaves the wardrobe unchanged and links to catalogue search', async ({page}) => {
  const a = unique('ia'); const b = unique('ib');
  const ca = await onboarded(a, {garments: 3, look: true}); const cb = await onboarded(b);
  await befriend(ca, cb, b);
  await ca('PUT', '/me/privacy', {profile: 'friends', wardrobe: 'friends', friends_list: 'friends'});
  const [look] = await ca<Array<{id: string}>>('GET', '/me/looks');
  await ca('POST', '/me/shares', {look_id: look!.id, audience: 'friends', caption: 'Campus rain'});
  await signIn(page, b);
  await page.goto('/app/#/community');
  await page.getByRole('button', {name: 'Save as inspiration'}).first().click();
  await expect(page.getByText('Saved to inspirations')).toBeVisible();
  await page.getByRole('tab', {name: 'Inspirations'}).click();
  await expect(page.getByText('Saving a look never adds its pieces to your wardrobe.')).toBeVisible();
  await expect(page.getByRole('link', {name: 'Find in catalogue'}).first()).toHaveAttribute('href', /#\/catalogue\?q=/);
  expect((await cb<{items: unknown[]}>('GET', '/me/wardrobe/items')).items).toHaveLength(0);
});

test('Friends: request, accept and remove between two users; requests closed is explained', async ({page, browser}) => {
  const a = unique('fa'); const b = unique('fb'); const c = unique('fc');
  await onboarded(a); await onboarded(b); const cc = await onboarded(c);
  const s = await cc<{version: number}>('GET', '/me/settings');
  await cc('PATCH', '/me/settings', {version: s.version, values: {friend_requests_from: 'nobody'}});
  await signIn(page, a);
  await page.goto('/app/#/community?tab=friends');
  await page.getByLabel('Find people by handle or name').fill(b);
  await page.getByRole('button', {name: 'Search', exact: true}).click();
  await page.getByRole('button', {name: 'Add friend'}).click();
  await expect(page.getByText('Request sent')).toBeVisible();
  const pb = await pageFor(browser, b);
  await pb.goto('/app/#/community?tab=friends');
  await pb.getByRole('button', {name: 'Accept'}).click();
  await expect(pb.getByText('You’re now friends')).toBeVisible();
  await page.reload();
  await expect(page.locator('section', {hasText: 'Your friends'}).getByText(`@${b}`)).toBeVisible();
  await page.locator('section', {hasText: 'Your friends'}).getByRole('button', {name: 'Remove friend'}).click();
  await expect(page.locator('section', {hasText: 'Your friends'}).getByText('No friends yet.')).toBeVisible();
  // Requests closed
  await page.getByLabel('Find people by handle or name').fill(c);
  await page.getByRole('button', {name: 'Search', exact: true}).click();
  await page.getByRole('button', {name: 'Add friend'}).click();
  await expect(page.locator('.person-row [role=alert]')).toBeVisible();
  await expect(page.locator('.person-row [role=alert]')).not.toBeEmpty();
});

test('My shares: effective audience narrower than chosen, and ALREADY_REPORTED explained', async ({page, browser}) => {
  const a = unique('sa'); const b = unique('sb');
  const ca = await onboarded(a, {garments: 3, look: true}); const cb = await onboarded(b);
  await befriend(ca, cb, b);
  await ca('PUT', '/me/privacy', {profile: 'public', wardrobe: 'friends', friends_list: 'friends'});
  const [look] = await ca<Array<{id: string}>>('GET', '/me/looks');
  await ca('POST', '/me/shares', {look_id: look!.id, audience: 'public'});
  await signIn(page, a);
  await page.goto('/app/#/community?tab=shares');
  await expect(page.getByText('Seen by: Friends')).toBeVisible();
  await expect(page.getByText('Your wardrobe privacy narrows this share.')).toBeVisible();
  const pb = await pageFor(browser, b);
  await pb.goto('/app/#/community');
  for (let i = 0; i < 2; i++) {
    await pb.getByRole('button', {name: 'Report'}).first().click();
    await pb.getByLabel('What’s wrong?').fill('Testing reports');
    await pb.getByRole('button', {name: 'Send report'}).click();
  }
  await expect(pb.getByRole('dialog').locator('.field-error, [role=alert], .error').first()).toBeVisible();
});

test('Notifications: mark read clears the badge; no polling while the tab is hidden', async ({page}) => {
  const a = unique('na'); const b = unique('nb');
  const ca = await onboarded(a); await onboarded(b);
  await ca('POST', '/me/friend-requests', {handle: b}, idem());
  await page.clock.install();
  await signIn(page, b);
  await page.goto('/app/#/notifications');
  await expect(page.locator('.note.is-unread')).toHaveCount(1);
  await page.getByRole('button', {name: 'Mark all as read'}).click();
  await expect(page.locator('.note.is-unread')).toHaveCount(0);
  await expect(page.getByRole('button', {name: /^Notifications/})).not.toContainText('1');
  const polls: string[] = [];
  page.on('request', r => { if (r.url().includes('/notifications/unread-count')) polls.push(r.url()); });
  await page.evaluate(() => { Object.defineProperty(document, 'visibilityState', {configurable: true, get: () => 'hidden'});
    Object.defineProperty(document, 'hidden', {configurable: true, get: () => true}); document.dispatchEvent(new Event('visibilitychange')); });
  await page.clock.fastForward('03:00');
  await page.waitForTimeout(300);
  expect(polls).toHaveLength(0);
});

test('Not-found parity: a blocked viewer sees exactly the unknown-handle page', async ({page}) => {
  const a = unique('pa'); const b = unique('pb');
  const ca = await onboarded(a); await onboarded(b);
  await ca('PUT', `/me/blocks/${b}`);
  await signIn(page, b);
  await page.goto(`/app/#/u/${a}`);
  await expect(page.getByText('This profile isn’t available')).toBeVisible();
  const blocked = await page.locator('#main').innerHTML();
  await page.goto(`/app/#/u/nobody${unique('x')}`);
  await expect(page.getByText('This profile isn’t available')).toBeVisible();
  expect(await page.locator('#main').innerHTML()).toBe(blocked);
});

test('Settings: an unknown future key renders as a toggle', async ({page}) => {
  const sub = unique('st');
  await onboarded(sub);
  await page.route('**/api/v2/me/settings', async route => {
    if (route.request().method() !== 'GET') return route.continue();
    const res = await route.fetch(); const body = await res.json();
    body.schema.push({key: 'future_flag', section: 'general', type: 'flag', default: false, choices: [], min: null, max: null});
    body.values.future_flag = false;
    await route.fulfill({response: res, json: body});
  });
  await signIn(page, sub);
  await page.goto('/app/#/settings/general');
  await expect(page.getByRole('switch', {name: 'Future flag'})).toBeVisible();
});

test('Privacy saved: wardrobe private hides the wardrobe section from a friend', async ({page, browser}) => {
  const a = unique('pva'); const b = unique('pvb');
  const ca = await onboarded(a); const cb = await onboarded(b);
  await befriend(ca, cb, b);
  await ca('PUT', '/me/privacy', {profile: 'friends', wardrobe: 'friends', friends_list: 'friends'});
  await ownProduct(ca, 'Visible tote');
  const pb = await pageFor(browser, b);
  await pb.goto(`/app/#/u/${a}`);
  await expect(pb.locator('[data-section="wardrobe"]')).toContainText('Visible tote');
  await signIn(page, a);
  await page.goto('/app/#/settings/privacy');
  const put = page.waitForRequest(r => r.url().includes('/me/privacy') && r.method() === 'PUT');
  await page.getByRole('radiogroup', {name: 'Wardrobe'}).getByText('Only me').click();
  expect((await put).postDataJSON().wardrobe).toBe('private');
  await expect(page.getByText('Privacy saved')).toBeVisible();
  await pb.reload();
  await expect(pb.getByRole('heading', {level: 1})).toBeVisible();
  await expect(pb.locator('[data-section="wardrobe"]')).toHaveCount(0);
});

test('Security: weak password refused before sending, broker flows, sign out everywhere', async ({page}) => {
  const email = `${unique('sec')}@example.com`;
  await page.goto('/app/#/signup');
  await page.getByLabel('Your name').fill('Sec Tester'); await page.getByLabel('Email').fill(email);
  await page.getByLabel('Password').fill('Correct-horse-42!'); await page.getByRole('button', {name: 'Create account'}).click();
  await page.waitForURL(/onboarding/);
  await page.getByLabel('Handle').fill(unique('sec')); await page.getByRole('button', {name: 'Finish setup'}).click();
  await page.waitForURL(u => !u.hash.includes('onboarding'));
  await page.evaluate(() => {
    const sub = document.cookie.match(/e2e_sub=([^;]+)/)?.[1] ?? Object.keys(localStorage).find(k => k.startsWith('e2e_session'))?.slice(12) ?? '';
    void sub;
    for (const key of Object.keys(localStorage).filter(k => k.startsWith('e2e_broker_sessions_'))) localStorage.removeItem(key);
  });
  await page.goto('/app/#/settings/security');
  await page.getByLabel('Current password').fill('wrong-current');
  await page.getByLabel('New password').fill('password123');
  await page.getByRole('button', {name: 'Change password'}).click();
  await expect(page.locator('.field-error')).toContainText('This is one of the most common passwords');
  await expect(page.getByText('Invalid password')).toHaveCount(0);                // the broker was never called
  await expect(page.getByRole('heading', {name: 'Signed-in devices'})).toBeVisible();
  await expect(page.getByRole('button', {name: /Resend verification email|Email verified/}).or(page.getByText('Email verified'))).toBeVisible();
  await page.getByRole('button', {name: 'Sign out everywhere'}).click();
  await page.getByRole('dialog').getByRole('button', {name: 'Sign out everywhere'}).click();
  await page.waitForURL(/#\/signin/);
});

test('Account: export downloads JSON; stale session delete asks to sign in again, then returns', async ({page}) => {
  const sub = unique('del');
  await onboarded(sub);
  await signIn(page, sub);
  await page.goto('/app/#/settings/account');
  const download = page.waitForEvent('download');
  await page.getByRole('button', {name: 'Download my data'}).click();
  expect((await download).suggestedFilename()).toMatch(/\.json$/);
  let first = true;
  await page.route('**/api/v2/me', route => {
    if (route.request().method() !== 'DELETE' || !first) return route.continue();
    first = false;
    return route.fulfill({status: 403, contentType: 'application/json', headers: {'Access-Control-Allow-Origin': new URL(page.url()).origin},
      body: JSON.stringify({code: 'REAUTHENTICATION_REQUIRED', message: 'Sign in again.', field_errors: [], request_id: 'e2e'})});
  });
  await page.getByLabel(`Type @${sub} to confirm`).fill(sub);
  await page.getByRole('button', {name: 'Delete my account'}).click();
  await page.waitForURL(/#\/signin/);
  // Sign in again on the same page, keeping the app's own return state (the fake broker reads ?e2e_sub=).
  await page.evaluate(s => history.replaceState(history.state, '', `${location.pathname}?e2e_sub=${s}${location.hash}`), sub);
  await page.getByRole('button', {name: 'Continue with Google'}).click();
  await expect(page.getByText('You’re signed in again. Confirm deletion below.')).toBeVisible();
});
