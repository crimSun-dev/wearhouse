import {defineConfig} from '@playwright/test';

export default defineConfig({
  testDir:'./e2e',
  testMatch:'pages.spec.js',
  workers:1,
  timeout:45000,
  use:{baseURL:process.env.PAGES_TEST_URL || 'http://127.0.0.1:4173/LIVE-DEMO/', channel:process.env.PLAYWRIGHT_CHANNEL, screenshot:'only-on-failure'},
  webServer:process.env.PAGES_TEST_URL ? undefined : {
    command:'npm run preview -- --port 4173',
    env:{VITE_BASE_PATH:'/LIVE-DEMO/'},
    url:'http://127.0.0.1:4173/LIVE-DEMO/',
    reuseExistingServer:false,
  },
});
