// build-wearhouse-wardrobe-planning-services 7.2: declare items (with a private photo) -> wardrobe -> look -> plan today
// -> "I wore this" -> suggestions. No weather location is set, so nothing calls BMKG (weather shows as unavailable).
import {expect, test, type Browser, type Page} from '@playwright/test';

const PNG = Buffer.concat([Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]), Buffer.alloc(32)]);

async function signIn(browser: Browser, sub: string): Promise<Page> {
  const page = await (await browser.newContext()).newPage();
  await page.goto(`/?e2e_sub=${sub}#/`);
  await page.getByRole('button', {name: 'Sign in with Google'}).click();
  await page.getByLabel('Choose your handle').fill(sub);
  await page.getByRole('button', {name: 'Save handle'}).click();
  await expect(page.getByRole('heading', {name: 'Your profile'})).toBeVisible();
  return page;
}

async function declare(page: Page, name: string, slot: string, photo = false) {
  await page.goto('/#/wardrobe/add');
  await page.getByLabel('Name').fill(name);
  await page.getByLabel('Slot').selectOption(slot);
  if (photo) await page.getByLabel('Photo (private, max 2 MB)').setInputFiles({name: 'top.png', mimeType: 'image/png', buffer: PNG});
  await page.getByRole('button', {name: 'Add to wardrobe'}).click();
  await expect(page.getByRole('status')).toHaveText(`${name} added.`);
}

test('wardrobe: declare, look, plan, wear and get suggestions', async ({browser}) => {
  const tag = Math.random().toString(36).slice(2, 7);
  const page = await signIn(browser, `wa_${tag}`);
  await declare(page, 'Linen shirt', 'top', true);
  await declare(page, 'Wide trousers', 'bottom');
  await declare(page, 'Canvas shoes', 'footwear');

  await page.goto('/#/wardrobe');
  await expect(page.getByRole('heading', {name: 'Wardrobe (3)'})).toBeVisible();
  await expect(page.getByText('declared (not verified)').first()).toBeVisible();
  await expect(page.locator('img.thumb')).toHaveCount(1);  // private photo loaded with the owner's token

  await page.goto('/#/looks');
  const newLook = page.locator('form').last();
  await newLook.getByLabel('Look name').fill('Easy Friday');
  await newLook.getByLabel('top', {exact: true}).selectOption({label: 'Linen shirt'});
  await newLook.getByLabel('bottom', {exact: true}).selectOption({label: 'Wide trousers'});
  await newLook.getByLabel('footwear', {exact: true}).selectOption({label: 'Canvas shoes'});
  await newLook.getByRole('button', {name: 'Create look'}).click();
  await expect(page.getByRole('heading', {name: 'Easy Friday (revision 1)'})).toBeVisible();

  await page.goto('/#/planner');
  const today = page.locator('li.day').first();
  await expect(today).toContainText('(today)');
  await expect(today).toContainText('No forecast (no_location)');
  await today.getByRole('combobox').selectOption({label: 'Easy Friday'});
  await today.getByRole('button', {name: 'Plan'}).click();
  await expect(page.getByRole('status')).toHaveText(/^Planned for /);
  await expect(page.locator('li.day').first()).toContainText('Planned: Easy Friday (r1)');
  await page.locator('li.day').first().getByRole('button', {name: 'I wore this'}).click();
  await expect(page.getByRole('status')).toHaveText('Wear logged.');
  await expect(page.locator('li.day').first()).toContainText('Worn: 1 entry');

  await page.goto('/#/wardrobe');
  await expect(page.getByText(/worn 1×/).first()).toBeVisible();

  await page.goto('/#/suggestions');
  // thesis rule c: rain needs rain-suitable footwear or outerwear; canvas shoes are not (appendix lookup)
  await page.getByLabel('Rain').selectOption('true');
  await page.getByRole('button', {name: 'Suggest outfits'}).click();
  await expect(page.getByRole('status')).toHaveText('0 suggestion(s).');
  await expect(page.getByText(/no outfit passes the rules: rain: needs rain-suitable footwear or outerwear/)).toBeVisible();
  // rule d: worship needs long sleeves (the linen shirt) and a long bottom (the trousers)
  await page.getByLabel('Rain').selectOption('false');
  await page.getByLabel('Occasion').selectOption('worship');
  await page.getByRole('button', {name: 'Suggest outfits'}).click();
  await expect(page.getByRole('status')).toHaveText('1 suggestion(s).');
  await expect(page.getByText(/heuristic_baseline/)).toBeVisible();
  await expect(page.getByText(/wardrobe-rules@1/)).toBeVisible();
  await expect(page.getByText('Linen shirt + Wide trousers + Canvas shoes')).toBeVisible();
  await expect(page.getByText('Worship: long sleeves and a long bottom.')).toBeVisible();
  await page.getByRole('button', {name: 'Save as look'}).click();  // also records the choice (Eq. 8)
  await expect(page.getByRole('status')).toHaveText('Saved as a look.');
});
