import {expect, test, type Browser, type ConsoleMessage, type Page} from '@playwright/test';
import {API, onboarded, signIn, unique} from './helpers.ts';

/**
 * web-quality "Full ecosystem path": one two-user story through the UI against a fresh harness database.
 * The API is used only to arrange preconditions that are not the step under test (accounts, declared garments,
 * the staff role grant). Every numbered step of the requirement is performed by clicking in the app.
 */
test.use({viewport: {width: 1440, height: 900}});
test.setTimeout(180_000);

type Problem = {page: string; text: string};

/** Console errors and uncaught exceptions on every page in the story. Steps that deliberately provoke a refusal
 * (B redeeming A's key, B opening A's item or profile) may log the browser's own "Failed to load resource" line for
 * that 4xx response: that is the network layer reporting the refusal under test, not an application error. */
function watch(page: Page, name: string, problems: Problem[], expectRefusal: () => boolean) {
  page.on('pageerror', error => problems.push({page: name, text: `pageerror: ${error.message}`}));
  page.on('console', (message: ConsoleMessage) => {
    if (message.type() !== 'error') return;
    const text = message.text();
    if (expectRefusal() && /Failed to load resource: the server responded with a status of 4(00|03|04|09)/.test(text)) return;
    problems.push({page: name, text});
  });
}

async function userPage(browser: Browser, sub: string, name: string, problems: Problem[], refusal: () => boolean) {
  const context = await browser.newContext({baseURL: test.info().project.use.baseURL, viewport: {width: 1440, height: 900}});
  const page = await context.newPage();
  watch(page, name, problems, refusal);
  await signIn(page, sub);
  return page;
}

test('Full ecosystem path: staff, purchase, redeem, styling, friends, sharing and blocking, with no console errors', async ({browser}) => {
  const run = unique('eco');
  const problems: Problem[] = [];
  let refusal = false;
  const allowRefusal = () => refusal;

  // Arrange: three accounts. A has nine declared garments (enough for suggestions); staff gets the admin role.
  const staffSub = `staff${run}`; const aSub = `ann${run}`; const bSub = `ben${run}`;
  await onboarded(staffSub);
  await fetch(`${API}/__e2e/grant?sub=${staffSub}&role=admin`, {method: 'POST'});
  await onboarded(aSub, {garments: 9});
  await onboarded(bSub);
  const productName = `Ecosystem tote ${run}`;

  // 1. Staff publishes a product and sets an offer.
  const staff = await userPage(browser, staffSub, 'staff', problems, allowRefusal);
  await staff.goto('/app/#/admin/ingest');
  await staff.getByLabel('External id').fill(run);
  await staff.getByLabel('Product name').fill(productName);
  await staff.getByLabel('Category').fill('Bag');
  await staff.getByLabel('Accepted by').fill('e2e');
  await staff.getByRole('button', {name: 'Ingest product'}).click();
  await expect(staff).toHaveURL(/#\/admin\/products\/[^/?]+/);
  const productId = /#\/admin\/products\/([^/?]+)/.exec(staff.url())![1]!;
  await staff.getByRole('button', {name: 'Publish this revision'}).click();
  await expect(staff.getByText('Revision 1 published')).toBeVisible();
  await staff.goto('/app/#/admin/offers');
  const offerForm = staff.locator('form.staff-inline');
  await offerForm.getByLabel('Product id').fill(productId);
  await offerForm.getByRole('button', {name: 'Edit offer'}).click();
  const offer = staff.getByRole('dialog', {name: 'Edit offer'});
  await offer.getByLabel('Price (IDR)').fill('150000');
  await offer.getByLabel('Stock').fill('3');
  await offer.getByRole('button', {name: 'Save'}).click();
  await expect(staff.getByText('Saved', {exact: true}).first()).toBeVisible();
  await staff.context().close();

  // 2. A wishlists it, adds it to the cart, checks out, reveals the key and redeems it.
  const a = await userPage(browser, aSub, 'A', problems, allowRefusal);
  await a.goto(`/app/#/catalogue/products/${productId}`);
  await expect(a.getByRole('heading', {level: 1, name: productName})).toBeVisible();
  await a.getByRole('button', {name: 'Save to wishlist'}).click();
  await expect(a.getByRole('button', {name: 'Remove from wishlist'})).toBeVisible();
  await a.getByRole('button', {name: 'Add to cart'}).click();
  await expect(a.getByText('Added to your cart')).toBeVisible();
  await a.goto('/app/#/cart');
  await a.getByRole('button', {name: 'Review order'}).click();
  await a.getByRole('button', {name: 'Place simulated order'}).click();
  await expect(a.getByRole('heading', {name: 'Receipt'})).toBeVisible();
  await a.getByRole('button', {name: 'Reveal key'}).click();
  await a.getByRole('button', {name: 'Show', exact: true}).click();
  const key = (await a.locator('.unit-key').innerText()).trim();
  expect(key).toMatch(/^[A-Z2-7]{4}(-[A-Z2-7]{4}){3}$/);
  await a.getByRole('button', {name: 'Redeem now'}).click();
  await expect(a.locator('.redeem-input')).toHaveValue(key);
  await a.getByRole('button', {name: 'Redeem', exact: true}).click();
  await expect(a.getByRole('heading', {name: new RegExp(`${productName} is now in your wardrobe`)})).toBeVisible();
  await a.goto('/app/#/wardrobe');
  await a.getByRole('link', {name: new RegExp(productName)}).first().click();
  await expect(a).toHaveURL(/#\/wardrobe\/items\/[^/?]+/);
  await expect(a.getByRole('heading', {level: 1, name: productName})).toBeVisible();
  const itemUrl = '/app/' + new URL(a.url()).hash;

  // 3. B cannot redeem the same key or open A's item.
  const b = await userPage(browser, bSub, 'B', problems, allowRefusal);
  refusal = true;
  await b.goto('/app/#/redeem');
  await b.locator('.redeem-input').fill(key);
  await b.getByRole('button', {name: 'Redeem', exact: true}).click();
  await expect(b.locator('#redeem-msg')).toHaveText('That key can’t be redeemed. Check it and try again.');
  await b.goto(itemUrl);
  await expect(b.getByRole('alert')).toContainText('We couldn’t find that.');
  await expect(b.getByText(productName)).toHaveCount(0);
  refusal = false;

  // 4. A saves a look, gets suggestions and chooses one, plans the week, marks a day worn and shares the look.
  const lookName = `Campus day ${run}`;
  await a.goto('/app/#/wardrobe/fitting-room');
  for (const n of [1, 2, 3]) await a.locator('.fit-item', {hasText: `${aSub} piece ${n}`}).click();
  await a.getByLabel('Look name').fill(lookName);
  await a.getByRole('button', {name: 'Save look'}).click();
  await expect(a.getByText('Look saved').first()).toBeVisible();

  await a.goto('/app/#/wardrobe/suggestions');
  const card = a.locator('.suggest-card').first();
  await expect(card).toBeVisible();
  const chosen = a.waitForRequest(r => /\/recommendations\/outfits\/[^/]+\/events$/.test(r.url()) && (r.postData() ?? '').includes('chosen'));
  await card.getByRole('button', {name: 'Plan', exact: true}).click();
  await chosen;
  await expect(a.getByText(/^Planned for /).first()).toBeVisible();

  await a.goto('/app/#/wardrobe/planner');
  const days = a.locator('.plan-day');
  await expect(days).toHaveCount(7);
  // Plan the saved look on every other day of the visible week that is still open.
  const openDays = days.filter({has: a.getByRole('button', {name: 'Plan a look'})});
  const toPlan = Math.min(await openDays.count(), 3);
  expect(toPlan).toBeGreaterThan(0);
  for (let i = 0; i < toPlan; i++) {
    await openDays.first().getByRole('button', {name: 'Plan a look'}).click();
    const sheet = a.getByRole('dialog', {name: 'Plan a look'});
    await sheet.getByLabel('Look').selectOption({label: lookName});
    await sheet.getByRole('button', {name: 'Save plan'}).click();
    await expect(sheet).toHaveCount(0);
  }
  await expect(a.locator('.plan-look-name', {hasText: lookName})).toHaveCount(toPlan);
  const today = a.locator('.plan-day.is-today');
  await today.getByRole('button', {name: 'Mark worn'}).click();
  await expect(today.locator('.plan-worn')).toContainText('Worn');

  await a.goto('/app/#/profile');
  await a.getByRole('radio', {name: 'Friends'}).click();
  await expect(a.getByRole('heading', {name: 'What friends see'})).toBeVisible();

  // A wardrobe is private by default, which narrows every share to nobody; A opens it to friends first.
  await a.goto('/app/#/settings/privacy');
  await a.getByRole('radiogroup', {name: 'Wardrobe'}).getByText('Friends').click();
  await expect(a.getByText('Privacy saved')).toBeVisible();

  const caption = `Rainy campus ${run}`;
  await a.goto('/app/#/community?tab=shares');
  await a.getByRole('combobox', {name: 'Look', exact: true}).selectOption({label: lookName});
  await a.getByRole('combobox', {name: 'Audience'}).selectOption('friends');
  await a.getByLabel('Caption').fill(caption);
  await a.getByRole('button', {name: 'Share', exact: true}).click();
  await expect(a.getByText('Shared', {exact: true}).first()).toBeVisible();
  await expect(a.locator('.share-caption', {hasText: caption})).toBeVisible();

  // 5. B sends a friend request, A accepts it, and B sees the share and A's week.
  await b.goto('/app/#/community?tab=friends');
  await b.getByLabel('Find people by handle or name').fill(aSub);
  await b.getByRole('button', {name: 'Search', exact: true}).click();
  await b.getByRole('button', {name: 'Add friend'}).click();
  await expect(b.getByText('Request sent')).toBeVisible();

  await a.goto('/app/#/community?tab=friends');
  await a.getByRole('button', {name: 'Accept'}).click();
  await expect(a.getByText('You’re now friends')).toBeVisible();

  await b.goto('/app/#/community');
  await expect(b.getByText(caption)).toBeVisible();
  await b.goto(`/app/#/u/${aSub}`);
  await expect(b.getByRole('heading', {name: 'This week'})).toBeVisible();
  await expect(b.locator('.week-strip').getByText(lookName).first()).toBeVisible();

  // 6. A blocks B, and B loses access.
  await a.goto('/app/#/community?tab=friends');
  await a.locator('section', {hasText: 'Your friends'}).getByRole('button', {name: 'Block'}).click();
  await a.getByRole('dialog', {name: `Block @${bSub}?`}).getByRole('button', {name: 'Block'}).click();
  await expect(a.getByText('Blocked', {exact: true}).first()).toBeVisible();

  // B's tab may still hold A's profile for the 30 s query staleTime; a fresh load must ask the server again.
  refusal = true;
  await b.goto(`/app/#/u/${aSub}`);
  await b.reload();
  await expect(b.getByText('This profile isn’t available')).toBeVisible();
  await expect(b.getByText(lookName)).toHaveCount(0);
  await b.goto('/app/#/community');
  await b.reload();
  await expect(b.getByRole('heading', {level: 1})).toBeVisible();
  await expect(b.getByText(caption)).toHaveCount(0);
  refusal = false;

  await a.context().close();
  await b.context().close();
  expect(problems, 'console errors during the ecosystem path').toEqual([]);
});
