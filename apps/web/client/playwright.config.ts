import {defineConfig} from '@playwright/test';

export default defineConfig({
  testDir: './e2e', globalSetup: './e2e/setup.ts', workers: 1,
  use: {baseURL: 'http://127.0.0.1:' + (process.env.E2E_PREVIEW_PORT || '4174'), screenshot: 'only-on-failure'},
  // Reviewed visual snapshots live in e2e/__screenshots__ under fixed names (one reviewed set, rendered by this
  // repo's Playwright Chromium; see README "Tests").
  snapshotPathTemplate: '{testDir}/__screenshots__/{arg}{ext}',
  projects: ['e2e', 'visual', 'a11y'].map(name => ({name, testMatch: '**/*.' + name + '.spec.ts'})),
});
