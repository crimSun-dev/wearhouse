import {defineConfig} from '@playwright/test';

// E2E: the real v2 API (test factory + Neon-shaped EdDSA issuer, disposable DB) and the e2e build of the pages.
// Requires WEARHOUSE_TEST_ADMIN_URL pointing at a DISPOSABLE PostgreSQL server.
export default defineConfig({
  testDir: './e2e',
  workers: 1,
  timeout: 60_000,
  use: {baseURL: 'http://127.0.0.1:4174/', screenshot: 'only-on-failure'},
  webServer: [
    {command: 'node e2e/start-harness.mjs', url: 'http://127.0.0.1:8199/api/v2/health', reuseExistingServer: false,
     timeout: 120_000},
    {command: 'npm run build:e2e && npx vite preview --mode e2e --outDir dist-e2e', url: 'http://127.0.0.1:4174/',
     reuseExistingServer: false, timeout: 120_000,
     env: {VITE_WEARHOUSE_API_BASE: 'http://127.0.0.1:8199/api/v2', VITE_E2E_TOKEN_URL: 'http://127.0.0.1:8199/__e2e/token'}},
  ],
});
