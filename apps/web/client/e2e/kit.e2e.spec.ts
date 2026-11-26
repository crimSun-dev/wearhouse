import {expect, test} from '@playwright/test';
import {onboarded, signIn, unique} from './helpers.ts';

test.use({viewport: {width: 1440, height: 900}});

test('Loading keeps width: a button entering its loading state does not change size', async ({page}) => {
  await page.goto('/app/#/dev/kit');
  const button = page.getByTestId('kit-loading');
  const before = await button.boundingBox();
  await button.click();
  await expect(button).toHaveAttribute('aria-busy', 'true');
  const during = await button.boundingBox();
  expect(during!.width).toBeCloseTo(before!.width, 0);
  expect(during!.height).toBeCloseTo(before!.height, 0);
});

test('Focus navigation holds the frame budget (median >= 55 fps)', async ({page}) => {
  const sub = unique('fps');
  await onboarded(sub, {garments: 10, look: true});
  await signIn(page, sub);
  await expect(page.getByRole('group', {name: 'Continue styling'}).locator('[data-focus-item]').first()).toBeFocused();
  const sample = (n: number) => page.evaluate(count => new Promise<number[]>(resolve => {
    const frames: number[] = []; let last = performance.now();
    const tick = (now: number) => { frames.push(now - last); last = now; frames.length < count ? requestAnimationFrame(tick) : resolve(frames.slice(3)); };
    requestAnimationFrame(tick);
  }), n);
  const median = (xs: number[]) => [...xs].sort((a, b) => a - b)[Math.floor(xs.length / 2)];
  const idleFps = 1000 / median(await sample(90));
  const blank = await page.evaluate(() => new Promise<number>(resolve => {
    // The same browser on an empty document: what this machine's renderer delivers with no page cost at all.
    const frames: number[] = []; let last = performance.now();
    const div = document.createElement('div'); div.style.cssText = 'position:fixed;inset:0;background:#000;z-index:99999';
    document.body.append(div);
    const tick = (now: number) => { frames.push(now - last); last = now;
      if (frames.length < 90) requestAnimationFrame(tick); else { div.remove(); const s = frames.slice(3).sort((a, b) => a - b); resolve(1000 / s[Math.floor(s.length / 2)]); } };
    requestAnimationFrame(tick);
  }));
  console.log(`idle home ${idleFps.toFixed(1)} fps; opaque cover ${blank.toFixed(1)} fps`);
  await page.evaluate(() => {
    const w = window as unknown as {__frames: number[]};
    w.__frames = [];
    let last = performance.now();
    const tick = (now: number) => { w.__frames.push(now - last); last = now; if (w.__frames.length < 400) requestAnimationFrame(tick); };
    requestAnimationFrame(tick);
  });
  for (let i = 0; i < 24; i++) {                          // scrub along both rails while frames are sampled
    await page.keyboard.press(i % 12 < 6 ? 'ArrowRight' : 'ArrowLeft');
    if (i === 12) await page.keyboard.press('ArrowDown');
    await page.waitForTimeout(90);
  }
  const frames = await page.evaluate(() => (window as unknown as {__frames: number[]}).__frames.slice(5));
  const fps = 1000 / median(frames);
  test.info().annotations.push({type: 'median fps', description: fps.toFixed(1)});
  console.log(`focus navigation: ${frames.length} frames, median ${fps.toFixed(1)} fps`);
  expect(fps).toBeGreaterThanOrEqual(55);
});
